#!/usr/bin/env python3
"""Conservative, research-only PSX discovery with completed-session cutoff.

Curated universe, not full exchange coverage. Provider use is opt-in.
"""
import argparse
from datetime import date, datetime, timezone
import json
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.fetch_psxdata import collect_psxdata_conn
from scripts.freshness_core import expected_weekday
from psx_analysis_feed import MARKET_CODES

# Observed in run 38723513213; mappings are NOT independently PSX-verified.
# These are eligible for research screening only, never automatic trade signals.
OBSERVED_MARKET_CODES = {
    'IMAGE': '0839', 'EFERT': '0809', 'FFC': '0809',
    'ENGROH': '0813', 'HUBC': '0824', 'LUCK': '0804',
    'OGDC': '0820', 'PPL': '0820', 'POL': '0820',
    'UBL': '0807', 'HBL': '0807', 'BAFL': '0807', 'MEBL': '0807',
    'MARI': '0820', 'PSO': '0821', 'ATRL': '0825',
    'DGKC': '0804', 'FCCL': '0804', 'MLCF': '0804',
    'TRG': '0828', 'NETSOL': '0828', 'EPCL': '0805',
    'EPQL': '0824', 'KAPCO': '0824', 'NML': '0829',
    'ILP': '0829', 'COLG': '0810',
}

def allowed_market_codes(symbol):
    if symbol in MARKET_CODES:
        return MARKET_CODES[symbol]
    observed = OBSERVED_MARKET_CODES.get(symbol)
    return ('REG', observed) if observed else ('REG',)


MIN_SESSIONS = 90
BACKFILL_DAYS = 540
MAX_CANDIDATE_WEEKDAY_LAG = 1

def weekday_lag(last_date, cutoff_date):
    start, end = date.fromisoformat(last_date), date.fromisoformat(cutoff_date)
    if start > end:
        return None
    from datetime import timedelta
    count = 0
    current = start
    while current < end:
        current += timedelta(days=1)
        if current.weekday() < 5:
            count += 1
    return count


def selected_rows(conn, symbol, cutoff, limit=120):
    """Select one candle per date using only explicitly mapped market codes.

    Do not infer unknown official codes or combine volumes. Conflicting
    overlapping records are reported and block screening.
    """
    allowed = allowed_market_codes(symbol)
    placeholders = ','.join('?' for _ in allowed)
    rows = conn.execute(f"""
        SELECT trade_date, open, high, low, close, volume, market_code, source_file
        FROM ohlcv
        WHERE symbol=? AND trade_date<=? AND market_code IN ({placeholders})
          AND open>0 AND high>0 AND low>0 AND close>0 AND volume>=0
          AND low<=open AND open<=high AND low<=close AND close<=high
        ORDER BY trade_date DESC
    """, (symbol, cutoff, *allowed)).fetchall()
    priority = {code: i for i, code in enumerate(allowed)}
    by_date, conflicts = {}, []
    for day, op, hi, lo, cl, vol, code, source in rows:
        record = {'date': day, 'open': op, 'high': hi, 'low': lo,
                  'close': cl, 'volume': vol, 'market_code': code,
                  'source_file': source}
        previous = by_date.get(day)
        if previous:
            if (any(abs(float(previous[k])-float(record[k]))>0.005
                    for k in ('open','high','low','close')) or
                    int(previous['volume']) != int(record['volume'])):
                conflicts.append(day)
            if priority[code] <= priority[previous['market_code']]:
                continue
        by_date[day] = record
    selected = [by_date[d] for d in sorted(by_date)[-limit:]]
    unknown_codes = [r[0] for r in conn.execute(
        f"""SELECT DISTINCT market_code FROM ohlcv
             WHERE symbol=? AND trade_date<=? AND market_code NOT IN ({placeholders})""",
        (symbol, cutoff, *allowed)).fetchall()]
    return selected, sorted(set(conflicts)), sorted(unknown_codes)

def history_count(conn, symbol, cutoff):
    rows, _, _ = selected_rows(conn, symbol, cutoff, limit=100000)
    return len(rows)

def screen(conn, symbol, min_sessions=MIN_SESSIONS, cutoff_date=None):
    cutoff_date = cutoff_date or expected_weekday().isoformat()
    rows, conflicts, unknown_codes = selected_rows(conn, symbol, cutoff_date)
    if conflicts:
        return None, 'MARKET_CODE_CONFLICT'
    if len(rows) < min_sessions:
        return None, 'DATA_PENDING'
    dates = [r['date'] for r in rows]
    if len(set(dates)) != len(dates):
        return None, 'DUPLICATE_DATES'
    lag = weekday_lag(dates[-1], cutoff_date)
    if lag is None or lag > MAX_CANDIDATE_WEEKDAY_LAG:
        return None, 'STALE_CANDIDATE'
    closes = [float(r['close']) for r in rows]
    volumes = [int(r['volume']) for r in rows]
    avg20 = sum(volumes[-20:]) / 20
    if avg20 <= 0:
        return None, 'ZERO_AVERAGE_VOLUME'
    sma20 = sum(closes[-20:]) / 20
    sma50 = sum(closes[-50:]) / 50
    relvol = volumes[-1] / avg20
    change20 = (closes[-1] / closes[-21] - 1) * 100
    score = round((2 if closes[-1] > sma20 else 0) +
                  (2 if sma20 > sma50 else 0) +
                  min(relvol, 3) + max(-3, min(3, change20 / 5)), 3)
    return {
        'symbol': symbol, 'date': dates[-1], 'close': closes[-1],
        'sessions': len(rows), 'volume': volumes[-1],
        'sma20': round(sma20, 4), 'sma50': round(sma50, 4),
        'relative_volume': round(relvol, 3),
        'change_20_sessions_pct': round(change20, 3),
        'rank_score': score, 'decision': 'WATCH_RESEARCH_ONLY',
        'data_source': 'Explicitly mapped market codes; per-row provenance in SQLite',
        'latest_market_code': rows[-1]['market_code'],
        'market_code_mapping_verified': False,
        'latest_source_file': rows[-1]['source_file'],
        'unmapped_market_codes_seen': unknown_codes,
        'independent_official_verification': False,
        'completed_session_cutoff': cutoff_date,
        'weekday_lag': lag, 'freshness': 'FRESH',
    }, None

def collect_discovery(conn, symbols, cutoff, fetcher=None):
    """Backfill undercovered symbols; use incremental updates only for established history.

    The provider's per-request session count is not a substitute for DB coverage.
    """
    results = {}
    for symbol in symbols:
        before = history_count(conn, symbol, cutoff)
        needs_backfill = before < MIN_SESSIONS
        kwargs = dict(
            symbols=[symbol],
            mode='backfill' if needs_backfill else 'incremental',
            end=cutoff,
            backfill_days=BACKFILL_DAYS,
            min_provider_sessions=MIN_SESSIONS if needs_backfill else 1,
            apply=True,
            today=date.fromisoformat(cutoff),
        )
        if fetcher is not None:
            kwargs['fetcher'] = fetcher
        report = collect_psxdata_conn(conn, **kwargs)
        after = history_count(conn, symbol, cutoff)
        item = report['symbols'][symbol]
        results[symbol] = {
            'mode': kwargs['mode'],
            'sessions_before': before,
            'sessions_after': after,
            'requested_start': item.get('requested_start'),
            'requested_end': item.get('requested_end'),
            'provider_rows': item.get('valid_rows', 0),
            'inserted_rows': item.get('inserted_rows', 0),
            'fetch_error': item.get('fetch_error'),
            'provider_ok': item.get('ok', False),
            'data_coverage': 'READY' if after >= MIN_SESSIONS else 'DATA_PENDING',
        }
    return results

def make_report(conn, symbols, cutoff, collect=False, fetcher=None):
    result = {
        'schema_version': '1.4',
        'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'completed_session_cutoff': cutoff,
        'universe_type': 'curated_subset_not_full_psx',
        'universe_size': len(symbols),
        'symbols_requested': symbols,
        'independent_official_verification': False,
        'not_investment_advice': True,
        'collection': {'enabled': collect, 'symbols': {}},
        'candidates': [], 'excluded': {}, 'coverage': {},
        'stale_watchlist': [],
    }
    if collect:
        result['collection']['symbols'] = collect_discovery(conn, symbols, cutoff, fetcher)
    for symbol in symbols:
        candidate, reason = screen(conn, symbol, cutoff_date=cutoff)
        count = history_count(conn, symbol, cutoff)
        selected, conflicts, unknown_codes = selected_rows(conn, symbol, cutoff)
        latest = selected[-1]['date'] if selected else None
        lag = weekday_lag(latest, cutoff) if latest else None
        result['coverage'][symbol] = {'completed_sessions': count,
                                     'mapped_market_codes': list(allowed_market_codes(symbol)),
                                     'mapping_verification': 'portfolio_existing_mapping' if symbol in MARKET_CODES else 'observed_unverified' if symbol in OBSERVED_MARKET_CODES else 'REG_only',
                                     'unmapped_market_codes_seen': unknown_codes,
                                     'overlap_conflict_dates': conflicts[:20],
                                     'latest_completed_observation': latest,
                                     'weekday_lag': lag,
                                     'status': 'READY' if candidate else reason}
        if candidate:
            result['candidates'].append(candidate)
        else:
            result['excluded'][symbol] = reason
            if reason == 'STALE_CANDIDATE':
                result['stale_watchlist'].append({'symbol': symbol, 'latest_date': latest,
                    'weekday_lag': lag, 'status': 'STALE_RESEARCH_ONLY'})
    result['candidates'].sort(key=lambda x: (-x['rank_score'], x['symbol']))
    result['health'] = {
        'configured': len(symbols),
        'screened': len(result['candidates']),
        'data_pending': sum(v == 'DATA_PENDING' for v in result['excluded'].values()),
        'stale': len(result['stale_watchlist']),
        'market_code_conflicts': sum(v == 'MARKET_CODE_CONFLICT' for v in result['excluded'].values()),
        'fresh_candidates': len(result['candidates']),
        'excluded_other': sum(v not in ('DATA_PENDING', 'STALE_CANDIDATE') for v in result['excluded'].values()),
        'source_verified_candidates': 0,
        'actionable_buy_candidates': 0,
        'research_only': True,
    }
    return result

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--db', default='state/psx_ohlcv.sqlite')
    ap.add_argument('--config', default='config/discovery_universe.json')
    ap.add_argument('--out', default='publish/discovery_watchlist.json')
    ap.add_argument('--collect-authorized', action='store_true')
    args = ap.parse_args()
    symbols = list(dict.fromkeys(str(s).strip().upper() for s in
                                 json.loads(Path(args.config).read_text())['symbols']))
    if not symbols or len(symbols) > 40 or any(not s.isalnum() or len(s)>12 for s in symbols):
        raise SystemExit('Invalid configured discovery universe (1..40 symbols)')
    cutoff = expected_weekday().isoformat()
    with sqlite3.connect(args.db) as conn:
        result = make_report(conn, symbols, cutoff, args.collect_authorized)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(f"Discovery: {result['health']['fresh_candidates']}/{len(symbols)} fresh research candidates; "
          f"{result['health']['stale']} STALE; {result['health']['data_pending']} DATA_PENDING; cutoff {cutoff}")
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
