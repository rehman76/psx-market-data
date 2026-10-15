#!/usr/bin/env python3
"""Separate, non-trading discovery watchlist from an explicitly configured universe.

Uses only locally available OHLCV; optionally backfills via psxdata when its
automated-use authorization is explicitly enabled. Does not claim full PSX coverage.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.fetch_psxdata import collect_psxdata_conn

def screen(conn, symbol, min_sessions=60):
    # REG is the explicitly labeled psxdata market code. Do not merge
    # unknown official market codes into one synthetic candle.
    rows = conn.execute("""
        SELECT trade_date, close, volume, source_file FROM ohlcv
        WHERE symbol=? AND market_code='REG'
          AND close>0 AND volume>=0
        ORDER BY trade_date DESC LIMIT 90
    """, (symbol,)).fetchall()
    rows.reverse()
    if len(rows) < min_sessions:
        return None, 'insufficient_history'
    dates = [r[0] for r in rows]
    if len(set(dates)) != len(dates):
        return None, 'duplicate_dates'
    closes = [float(r[1]) for r in rows]
    volumes = [int(r[2]) for r in rows]
    avg20 = sum(volumes[-20:]) / 20
    if not avg20:
        return None, 'zero_average_volume'
    sma20 = sum(closes[-20:]) / 20
    sma50 = sum(closes[-50:]) / 50
    relvol = volumes[-1] / avg20
    change20 = (closes[-1] / closes[-21] - 1) * 100
    # Heuristic ranking only. Never interpret this as investment approval.
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
        'data_source': 'REG market-code records; per-row provenance in SQLite',
        'independent_official_verification': False,
    }, None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--db', default='state/psx_ohlcv.sqlite')
    ap.add_argument('--config', default='config/discovery_universe.json')
    ap.add_argument('--out', default='publish/discovery_watchlist.json')
    ap.add_argument('--collect-authorized', action='store_true')
    args = ap.parse_args()
    config = json.loads(Path(args.config).read_text())
    symbols = list(dict.fromkeys(s.strip().upper() for s in config['symbols']))
    if not symbols or len(symbols) > 40 or any(not s.isalnum() or len(s)>12 for s in symbols):
        raise SystemExit('Invalid configured discovery universe (1..40 symbols)')
    result = {
        'schema_version': '1.0',
        'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'universe_type': 'curated_subset_not_full_psx',
        'universe_size': len(symbols),
        'symbols_requested': symbols,
        'independent_official_verification': False,
        'not_investment_advice': True,
        'collection': {'enabled': False},
        'candidates': [], 'excluded': {},
    }
    with sqlite3.connect(args.db) as conn:
        if args.collect_authorized:
            result['collection'] = collect_psxdata_conn(
                conn, symbols=symbols, mode='incremental',
                backfill_days=180, min_provider_sessions=60, apply=True
            )
        for symbol in symbols:
            candidate, reason = screen(conn, symbol)
            if candidate:
                result['candidates'].append(candidate)
            else:
                result['excluded'][symbol] = reason
        result['candidates'].sort(key=lambda x: (-x['rank_score'], x['symbol']))
        # A stale candidate is not a new buy setup.
        newest = max((c['date'] for c in result['candidates']), default=None)
        for candidate in result['candidates']:
            candidate['freshest_in_universe'] = candidate['date'] == newest
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(f"Discovery: {len(result['candidates'])}/{len(symbols)} research candidates")
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
