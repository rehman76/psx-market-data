#!/usr/bin/env python3
"""Non-actionable technical review with explicit missing fundamental/PSX checks.

Uses only completed, conflict-free discovery candles. No prices are fetched here.
No BUY/SELL signal is emitted without separate independently verified inputs.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from scripts.discover_candidates import selected_rows, weekday_lag, MAX_CANDIDATE_WEEKDAY_LAG
from psx_analysis_feed import rsi_wilder, macd_hist, atr_wilder, round_or_none

MIN_TECH_SESSIONS = 200

def evaluate(conn, symbol, cutoff):
    rows, conflicts, unknown = selected_rows(conn, symbol, cutoff, limit=260)
    result = {
        'symbol': symbol, 'status': 'BLOCKED', 'decision': 'RESEARCH_ONLY',
        'independent_psx_dps_verified': False,
        'fundamentals_verified': False, 'market_code_verified': False,
        'trade_eligible': False,
        'blocking_reasons': [],
        'technical': {},
    }
    blocks = result['blocking_reasons']
    if conflicts:
        blocks.append('MARKET_CODE_CONFLICT')
    if len(rows) < MIN_TECH_SESSIONS:
        blocks.append('INSUFFICIENT_200_SESSIONS')
    latest = rows[-1]['date'] if rows else None
    lag = weekday_lag(latest, cutoff) if latest else None
    result['latest_completed_date'] = latest
    result['weekday_lag'] = lag
    if lag is None or lag > MAX_CANDIDATE_WEEKDAY_LAG:
        blocks.append('STALE_CANDIDATE')
    if rows and not conflicts and len(rows) >= MIN_TECH_SESSIONS and lag is not None and lag <= MAX_CANDIDATE_WEEKDAY_LAG:
        closes = [float(r['close']) for r in rows]
        volumes = [int(r['volume']) for r in rows]
        avg20 = sum(volumes[-20:]) / 20
        result['technical'] = {
            'close': closes[-1],
            'sma20': round_or_none(sum(closes[-20:])/20),
            'sma50': round_or_none(sum(closes[-50:])/50),
            'sma200': round_or_none(sum(closes[-200:])/200),
            'rsi14_wilder': round_or_none(rsi_wilder(closes)),
            'macd_histogram_12_26_9': round_or_none(macd_hist(closes)),
            'atr14_wilder': round_or_none(atr_wilder(rows)),
            'volume_sma20': round_or_none(avg20),
            'relative_volume': round_or_none(volumes[-1]/avg20) if avg20 else None,
            'recent_20_session_high': max(float(r['high']) for r in rows[-20:]),
            'recent_20_session_low': min(float(r['low']) for r in rows[-20:]),
        }
        result['status'] = 'TECHNICAL_REVIEW_READY'
    blocks.extend(['PSX_DPS_VERIFICATION_PENDING', 'FUNDAMENTAL_REVIEW_PENDING', 'MARKET_CODE_VERIFICATION_PENDING'])
    result['unmapped_market_codes_seen'] = unknown
    return result

def build(conn, symbols, cutoff):
    reviews = [evaluate(conn, symbol, cutoff) for symbol in symbols]
    return {
        'schema_version': '1.0',
        'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'completed_session_cutoff': cutoff,
        'scope': 'curated_research_universe_not_full_psx',
        'not_investment_advice': True,
        'no_live_quotes': True,
        'reviews': reviews,
        'health': {
            'symbols': len(reviews),
            'technical_review_ready': sum(r['status']=='TECHNICAL_REVIEW_READY' for r in reviews),
            'technical_blocked': sum(r['status']=='BLOCKED' for r in reviews),
            'officially_verified': 0,
            'fundamentally_verified': 0,
            'trade_eligible': 0,
        }
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--db', default='state/psx_ohlcv.sqlite')
    ap.add_argument('--discovery', default='publish/discovery_watchlist.json')
    ap.add_argument('--out', default='publish/research_validation.json')
    args=ap.parse_args()
    discovery=json.loads(Path(args.discovery).read_text())
    symbols=discovery['symbols_requested']
    cutoff=discovery['completed_session_cutoff']
    with sqlite3.connect(args.db) as conn:
        report=build(conn,symbols,cutoff)
    out=Path(args.out)
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print('Research validation: '+str(report['health']))
if __name__=='__main__':
    main()
