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

MIN_SESSIONS = 90
BACKFILL_DAYS = 540

def history_count(conn, symbol, cutoff):
    return conn.execute(
        """SELECT COUNT(DISTINCT trade_date) FROM ohlcv
           WHERE symbol=? AND market_code='REG' AND trade_date<=?
             AND open>0 AND high>=open AND low<=open
             AND close>0 AND high>=close AND low<=close AND volume>=0""",
        (symbol, cutoff)
    ).fetchone()[0]

def screen(conn, symbol, min_sessions=MIN_SESSIONS, cutoff_date=None):
    cutoff_date = cutoff_date or expected_weekday().isoformat()
    rows = conn.execute(
        """SELECT trade_date, close, volume FROM ohlcv
           WHERE symbol=? AND market_code='REG' AND trade_date<=?
             AND open>0 AND high>=open AND low<=open
             AND close>0 AND high>=close AND low<=close AND volume>=0
           ORDER BY trade_date DESC LIMIT 120""",
        (symbol, cutoff_date)
    ).fetchall()
    rows.reverse()
    if len(rows) < min_sessions:
        return None, 'DATA_PENDING'
    dates = [r[0] for r in rows]
    if len(set(dates)) != len(dates):
        return None, 'DUPLICATE_DATES'
    closes = [float(r[1]) for r in rows]
    volumes = [int(r[2]) for r in rows]
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
        'data_source': 'psxdata REG OHLCV; per-row provenance in SQLite',
        'independent_official_verification': False,
        'completed_session_cutoff': cutoff_date,
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
        'schema_version': '1.1',
        'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'completed_session_cutoff': cutoff,
        'universe_type': 'curated_subset_not_full_psx',
        'universe_size': len(symbols),
        'symbols_requested': symbols,
        'independent_official_verification': False,
        'not_investment_advice': True,
        'collection': {'enabled': collect, 'symbols': {}},
        'candidates': [], 'excluded': {}, 'coverage': {},
    }
    if collect:
        result['collection']['symbols'] = collect_discovery(conn, symbols, cutoff, fetcher)
    for symbol in symbols:
        candidate, reason = screen(conn, symbol, cutoff_date=cutoff)
        count = history_count(conn, symbol, cutoff)
        result['coverage'][symbol] = {'completed_sessions': count,
                                     'status': 'READY' if candidate else reason}
        if candidate:
            result['candidates'].append(candidate)
        else:
            result['excluded'][symbol] = reason
    result['candidates'].sort(key=lambda x: (-x['rank_score'], x['symbol']))
    result['health'] = {
        'configured': len(symbols),
        'screened': len(result['candidates']),
        'data_pending': sum(v == 'DATA_PENDING' for v in result['excluded'].values()),
        'excluded_other': sum(v != 'DATA_PENDING' for v in result['excluded'].values()),
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
    print(f"Discovery: {result['health']['screened']}/{len(symbols)} research candidates; "
          f"{result['health']['data_pending']} DATA_PENDING; cutoff {cutoff}")
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
