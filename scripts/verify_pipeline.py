#!/usr/bin/env python3
"""Read-only PSX pipeline health check. Never treats a successful run as fresh data."""
import argparse
from datetime import date, datetime
from pathlib import Path
import sqlite3
import sys


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--db', default='state/psx_ohlcv.sqlite')
    p.add_argument('--symbols', nargs='+', default=['MCB', 'SYS', 'KOHE'])
    p.add_argument('--min-sessions', type=int, default=1)
    p.add_argument('--max-calendar-age', type=int, default=7,
                   help='Calendar days; weekends/holidays require manual interpretation')
    args = p.parse_args()
    if not Path(args.db).is_file():
        print(f'ERROR: missing database: {args.db}')
        return 2
    conn = sqlite3.connect(f'file:{Path(args.db).resolve()}?mode=ro', uri=True)
    try:
        count = conn.execute('SELECT COUNT(*) FROM ohlcv').fetchone()[0]
        print(f'Total database rows: {count}')
        bad = False
        for symbol in args.symbols:
            rows = conn.execute('''SELECT trade_date, COUNT(DISTINCT trade_date) AS n
                FROM ohlcv WHERE symbol=? AND market_code != '40'
                GROUP BY trade_date ORDER BY trade_date DESC LIMIT 1''', (symbol,)).fetchone()
            sessions = conn.execute('''SELECT COUNT(DISTINCT trade_date) FROM ohlcv
                WHERE symbol=? AND market_code != '40' ''', (symbol,)).fetchone()[0]
            latest = rows[0] if rows else None
            age = (date.today() - date.fromisoformat(latest)).days if latest else None
            print(f'{symbol}: sessions={sessions}, latest={latest}, age_calendar_days={age}')
            if sessions < args.min_sessions or age is None or age > args.max_calendar_age:
                bad = True
        if bad:
            print('WARNING: data is insufficient or stale; do not issue current technical signals.')
            return 1
        print('PASS: basic coverage/freshness checks passed; source verification still required.')
        return 0
    finally:
        conn.close()


if __name__ == '__main__':
    sys.exit(main())
