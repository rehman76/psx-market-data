#!/usr/bin/env python3
"""Check stored OHLCV freshness; output diagnostics even on failure."""
import argparse
import json
import os
from pathlib import Path
import sqlite3
from freshness_core import assess


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--db', default='state/psx_ohlcv.sqlite')
    p.add_argument('--publish', default='publish')
    p.add_argument('--symbols', nargs='+', default=['MCB', 'SYS', 'KOHE'])
    p.add_argument('--min-sessions', type=int, default=50)
    p.add_argument('--max-business-lag', type=int, default=1)
    a = p.parse_args()
    if Path(a.db).exists():
        with sqlite3.connect(f'file:{Path(a.db).resolve()}?mode=ro', uri=True) as db:
            status = assess(db, a.symbols, a.min_sessions, a.max_business_lag)
    else:
        status = {'fresh': False, 'status': 'database_missing', 'stocks': {}}
    publish = Path(a.publish)
    publish.mkdir(parents=True, exist_ok=True)
    (publish/'freshness.json').write_text(json.dumps(status, indent=2)+'\n')
    print(json.dumps(status, indent=2))
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
            f.write('fresh=' + str(status['fresh']).lower() + '\n')
    return 0 if status['fresh'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
