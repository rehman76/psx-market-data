#!/usr/bin/env python3
"""Check PSX OHLCV freshness against a Karachi-local date, emitting GitHub outputs."""
import argparse
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo
import json
import os
from pathlib import Path
import sqlite3

p = argparse.ArgumentParser()
p.add_argument('--db', default='state/psx_ohlcv.sqlite')
p.add_argument('--symbols', nargs='+', default=['MCB', 'SYS', 'KOHE'])
p.add_argument('--min-sessions', type=int, default=50)
p.add_argument('--max-business-lag', type=int, default=1, help='Weekday lag; holidays are not inferred')
a = p.parse_args()
now = datetime.now(ZoneInfo('Asia/Karachi'))
# Before 17:00 PKT, do not require the current day's closing file.
target = now.date() if now.hour >= 17 else now.date() - timedelta(days=1)
while target.weekday() >= 5:
    target -= timedelta(days=1)

status = {'checked_at_pkt': now.isoformat(), 'expected_latest_weekday': target.isoformat(), 'stocks': {}, 'fresh': False, 'note': 'Weekday-based check; PSX holidays must be handled separately.'}
if Path(a.db).exists():
    with sqlite3.connect(f'file:{Path(a.db).resolve()}?mode=ro', uri=True) as db:
        for symbol in a.symbols:
            latest, sessions = db.execute('SELECT MAX(trade_date), COUNT(DISTINCT trade_date) FROM ohlcv WHERE symbol=? AND market_code != ?', (symbol, '40')).fetchone()
            lag = None
            if latest:
                d = date.fromisoformat(latest)
                lag = sum(1 for n in range(1, max(0, (target-d).days)+1) if (d+timedelta(days=n)).weekday() < 5)
            status['stocks'][symbol] = {'latest': latest, 'sessions': sessions, 'weekday_lag': lag, 'fresh': bool(sessions >= a.min_sessions and lag is not None and lag <= a.max_business_lag and lag >= 0)}
status['fresh'] = len(status['stocks']) == len(a.symbols) and all(x['fresh'] for x in status['stocks'].values())
Path('publish').mkdir(exist_ok=True)
Path('publish/freshness.json').write_text(json.dumps(status, indent=2)+'\n')
print(json.dumps(status, indent=2))
if os.environ.get('GITHUB_OUTPUT'):
    with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
        f.write('fresh=' + str(status['fresh']).lower() + '\n')
raise SystemExit(0 if status['fresh'] else 1)
