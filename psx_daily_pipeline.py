#!/usr/bin/env python3
"""Local daily pipeline: import authorized downloaded files, publish JSON feed locally."""
import argparse
from pathlib import Path
from psx_collector import connect, import_paths
from psx_analysis_feed import build
from datetime import datetime, timezone
import json


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--input', default='closing_files')
    p.add_argument('--db', default='psx_ohlcv.sqlite')
    p.add_argument('--out', default='publish/psx_analysis_feed.json')
    p.add_argument('--symbols', nargs='+', default=['MCB','SYS','KOHE'])
    args = p.parse_args()
    with connect(args.db) as conn:
        failures = import_paths(conn, [args.input])
        if failures:
            raise SystemExit('Import failures; feed not published')
        stocks = [build(conn, symbol.upper(), 250) for symbol in args.symbols]
    output = {'schema_version':'1.0', 'generated_at_utc':datetime.now(timezone.utc).isoformat(),
              'source_policy':'PSX official closing files, locally imported, unadjusted; no invented OHLCV',
              'stocks':stocks}
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    temp = out.with_suffix('.json.tmp')
    temp.write_text(json.dumps(output, indent=2, allow_nan=False), encoding='utf-8')
    temp.replace(out)
    print(f'Feed ready: {out}')

if __name__ == '__main__':
    main()
