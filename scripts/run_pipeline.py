#!/usr/bin/env python3
"""Import locally supplied or explicitly authorized closing files, emit feed and status.

Does not discover PSX URLs, bypass access controls, or redistribute automatically.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import sys
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from psx_collector import connect, import_paths, fetch_authorized
from psx_analysis_feed import build
from scripts.fetch_psxdata import collect_psxdata_conn
from scripts.freshness_core import assess


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--db', default='state/psx_ohlcv.sqlite')
    ap.add_argument('--input', default='closing_files')
    ap.add_argument('--publish', default='publish')
    ap.add_argument('--symbols', nargs='+', default=['MCB', 'SYS', 'KOHE'])
    ap.add_argument('--download-url', default=os.getenv('AUTHORIZED_CLOSING_URL', ''))
    ap.add_argument('--psxdata', action='store_true',
                    help='Enable psxdata==1.2.0 historical backfill/incremental collection')
    ap.add_argument('--psxdata-mode', choices=('backfill', 'incremental'), default='backfill')
    ap.add_argument('--psxdata-start', help='YYYY-MM-DD; default depends on psxdata mode')
    ap.add_argument('--psxdata-end', help='YYYY-MM-DD; defaults to today')
    ap.add_argument('--psxdata-backfill-days', type=int, default=430)
    ap.add_argument('--psxdata-overlap-days', type=int, default=10)
    ap.add_argument('--psxdata-min-sessions', type=int, default=250)
    ap.add_argument('--psxdata-no-cache', action='store_true')
    args = ap.parse_args()
    source = Path(args.input)
    source.mkdir(parents=True, exist_ok=True)
    status = {
        'run_at_utc': datetime.now(timezone.utc).isoformat(),
        'download_attempted': bool(args.download_url),
        'download_succeeded': False,
        'import_failures': 0,
        'psxdata': {'enabled': False},
    }
    if args.download_url:
        url = args.download_url.strip()
        parsed = urlparse(url)
        # Deliberately restrict automated downloading to the PSX official host.
        if parsed.scheme != 'https' or parsed.hostname != 'dps.psx.com.pk':
            raise SystemExit('Download URL must be a verified, permitted https://dps.psx.com.pk/... file URL')
        try:
            target = source / ('authorized_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '.lis.Z')
            fetch_authorized(url, target)
            status['download_succeeded'] = True
        except Exception as exc:
            status['download_error'] = str(exc)
            print('Download failed:', exc, file=sys.stderr)
    db = Path(args.db)
    db.parent.mkdir(parents=True, exist_ok=True)
    with connect(db) as conn:
        status['import_failures'] = import_paths(conn, [str(source)])
        if args.psxdata:
            status['psxdata'] = collect_psxdata_conn(
                conn,
                symbols=[s.upper() for s in args.symbols],
                mode=args.psxdata_mode,
                start=args.psxdata_start,
                end=args.psxdata_end,
                backfill_days=args.psxdata_backfill_days,
                overlap_days=args.psxdata_overlap_days,
                min_provider_sessions=args.psxdata_min_sessions,
                cache=not args.psxdata_no_cache,
                apply=True,
            )
        count = conn.execute('SELECT COUNT(*) FROM ohlcv').fetchone()[0]
        status['database_rows'] = count
        if status['import_failures']:
            raise SystemExit('Import errors; refusing to publish')
        stocks = [build(conn, s.upper(), 300) for s in args.symbols]
    publish = Path(args.publish)
    publish.mkdir(parents=True, exist_ok=True)
    status['latest_trade_dates'] = {s['symbol']: s['latest_trade_date'] for s in stocks}
    status['sessions'] = {s['symbol']: s['sessions'] for s in stocks}
    status['data_available'] = all(s['sessions'] > 0 for s in stocks)
    status['new_download_missing'] = not status['download_succeeded']  # Legacy: official archive only.
    # Freshness is independent of the optional direct PSX download.
    with sqlite3.connect(f'file:{db.resolve()}?mode=ro', uri=True) as conn:
        freshness = assess(conn, [s.upper() for s in args.symbols], min_sessions=50, max_business_lag=1)
    status['data_freshness'] = freshness
    psx_ok = bool(status['psxdata'].get('ok'))
    status['sources'] = {
        'official_psx': {'download_attempted': status['download_attempted'],
                         'download_succeeded': status['download_succeeded'],
                         'error': status.get('download_error')},
        'psxdata': {'enabled': bool(status['psxdata'].get('enabled')),
                    'ok': psx_ok, 'inserted_rows': status['psxdata'].get('totals', {}).get('inserted_rows', 0)}
    }
    status['pipeline_status'] = ('fresh' if freshness['fresh'] and status['data_available']
                                 else 'stale_or_insufficient' if status['data_available'] else 'unavailable')
    # The feed intentionally does not assert that data is fresh merely because it was generated now.
    feed = {'schema_version': '1.1', 'generated_at_utc': status['run_at_utc'],
            'source_policy': 'Locally imported official PSX closing files plus psxdata backfill rows only where no existing same-symbol/date row exists; unadjusted; provenance in source_file',
            'collection_status': status, 'stocks': stocks}
    (publish / 'psx_analysis_feed.json').write_text(json.dumps(feed, indent=2, allow_nan=False), encoding='utf-8')
    (publish / 'status.json').write_text(json.dumps(status, indent=2), encoding='utf-8')
    (publish / 'freshness.json').write_text(json.dumps(freshness, indent=2), encoding='utf-8')
    (publish / 'psxdata_status.json').write_text(json.dumps(status['psxdata'], indent=2), encoding='utf-8')
    print(json.dumps(status, indent=2))
    if not status['data_available']:
        raise SystemExit('No data for one or more tracked stocks; no usable feed')
    # A missing new download does not fail if historical data exists; consumers MUST check dates.


if __name__ == '__main__':
    main()
