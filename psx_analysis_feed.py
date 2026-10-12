#!/usr/bin/env python3
"""Build a machine-readable PSX analysis feed from the collector SQLite database.

This program does not fetch PSX data or upload it to ChatGPT. Publish its output
only to an authorized HTTPS location that ChatGPT scheduled tasks can access.
"""
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sqlite3


def ema(values, n):
    if len(values) < n:
        return None
    x = sum(values[:n]) / n
    for v in values[n:]:
        x = (2 / (n + 1)) * v + (1 - 2 / (n + 1)) * x
    return x


def ema_series(values, n):
    out = [None] * len(values)
    if len(values) < n:
        return out
    x = sum(values[:n]) / n
    out[n - 1] = x
    for i in range(n, len(values)):
        x = (2 / (n + 1)) * values[i] + (1 - 2 / (n + 1)) * x
        out[i] = x
    return out


def rsi_wilder(values, period=14):
    if len(values) < period + 1:
        return None
    diffs = [b - a for a, b in zip(values, values[1:])]
    gain = sum(max(d, 0) for d in diffs[:period]) / period
    loss = sum(max(-d, 0) for d in diffs[:period]) / period
    for d in diffs[period:]:
        gain = (gain * (period - 1) + max(d, 0)) / period
        loss = (loss * (period - 1) + max(-d, 0)) / period
    if gain == 0 and loss == 0:
        return 50.0
    if loss == 0:
        return 100.0
    return 100 - 100 / (1 + gain / loss)


def macd_hist(values):
    a, b = ema_series(values, 12), ema_series(values, 26)
    diffs = [a[i] - b[i] for i in range(len(values)) if a[i] is not None and b[i] is not None]
    if len(diffs) < 9:
        return None
    return diffs[-1] - ema(diffs, 9)


def atr_wilder(candles, period=14):
    if len(candles) < period + 1:
        return None
    tr = [max(candles[i]['high'] - candles[i]['low'],
              abs(candles[i]['high'] - candles[i - 1]['close']),
              abs(candles[i]['low'] - candles[i - 1]['close']))
          for i in range(1, len(candles))]
    value = sum(tr[:period]) / period
    for v in tr[period:]:
        value = (value * (period - 1) + v) / period
    return value


def round_or_none(value):
    return round(value, 5) if value is not None and math.isfinite(value) else None


def read_candles(conn, symbol, limit):
    # Market code varies by symbol in the official sample (MCB=0807,
    # SYS=0828, KOHE=0824). Select the most represented valid market code;
    # warn if a symbol has multiple codes that require manual reconciliation.
    codes = conn.execute('''SELECT market_code, COUNT(*) n FROM ohlcv
        WHERE symbol=? AND open>0 AND high>0 AND low>0 AND close>0
        AND volume>=0 AND market_code != '40'
        GROUP BY market_code ORDER BY n DESC, market_code''', (symbol,)).fetchall()
    if not codes:
        return [], None, []
    code = codes[0][0]
    rows = conn.execute('''SELECT trade_date,open,high,low,close,volume,source_file
        FROM ohlcv WHERE symbol=? AND market_code=?
        AND open>0 AND high>0 AND low>0 AND close>0 AND volume>=0
        ORDER BY trade_date DESC LIMIT ?''', (symbol, code, limit)).fetchall()
    candles = [dict(zip(('date','open','high','low','close','volume','source_file'), row))
               for row in reversed(rows)]
    warnings = [f'Multiple market codes for symbol: {codes}; review code selection'] if len(codes)>1 else []
    return candles, code, warnings


def build(conn, symbol, limit):
    candles, market_code, warnings = read_candles(conn, symbol, limit)
    closes = [r['close'] for r in candles]
    vols = [r['volume'] for r in candles]
    last = candles[-1] if candles else None
    volume_avg = sum(vols[-20:]) / 20 if len(vols) >= 20 else None
    indicators = {
        'sma20': round_or_none(sum(closes[-20:]) / 20) if len(closes) >= 20 else None,
        'sma50': round_or_none(sum(closes[-50:]) / 50) if len(closes) >= 50 else None,
        'rsi14_wilder': round_or_none(rsi_wilder(closes)),
        'macd_12_26_9_histogram': round_or_none(macd_hist(closes)),
        'atr14_wilder': round_or_none(atr_wilder(candles)),
        'volume_sma20': round_or_none(volume_avg),
        'relative_volume': round_or_none(vols[-1] / volume_avg) if volume_avg else None,
    }
    return {
        'symbol': symbol, 'market_code': market_code, 'source': 'PSX closing files imported locally',
        'latest_trade_date': last['date'] if last else None,
        'earliest_trade_date': candles[0]['date'] if candles else None,
        'sessions': len(candles), 'latest_ohlcv': last,
        'indicators': indicators, 'indicator_status': 'partial' if any(v is None for v in indicators.values()) else 'computed',
        'candles': candles[-50:],
        'warnings': warnings + (['Fewer than 50 sessions; MA50 or other indicators may be unavailable'] if len(candles) < 50 else [])
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--db', default='psx_ohlcv.sqlite')
    ap.add_argument('--out', default='psx_analysis_feed.json')
    ap.add_argument('--symbols', nargs='+', default=['MCB', 'SYS', 'KOHE'])
    ap.add_argument('--history', type=int, default=250)
    args = ap.parse_args()
    if args.history < 50:
        ap.error('--history must be at least 50')
    with sqlite3.connect(args.db) as conn:
        result = {'schema_version': '1.0', 'generated_at_utc': datetime.now(timezone.utc).isoformat(),
                  'source_policy': 'Official PSX closing files; unadjusted prices; no automatic download',
                  'stocks': [build(conn, s.upper(), args.history) for s in args.symbols]}
    dest = Path(args.out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    temp = dest.with_suffix(dest.suffix + '.tmp')
    temp.write_text(json.dumps(result, indent=2, allow_nan=False), encoding='utf-8')
    temp.replace(dest)
    print(f'Generated {dest}: ' + ', '.join(f"{s['symbol']}={s['sessions']} sessions" for s in result['stocks']))

if __name__ == '__main__':
    main()
