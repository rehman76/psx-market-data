#!/usr/bin/env python3
"""Best-effort download of a dated PSX archive. Does not bypass access controls."""
import argparse
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
import io
import urllib.request
import urllib.error
import zipfile
import sys

BASE = 'https://dps.psx.com.pk/download/mkt_summary/'

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--directory', default='closing_files')
    p.add_argument('--date', help='YYYY-MM-DD; defaults to today in Asia/Karachi')
    p.add_argument('--authorized', action='store_true', help='Confirm permission to automate this source')
    a = p.parse_args()
    if not a.authorized:
        print('SKIPPED: automatic PSX retrieval not enabled; confirm data-use permission.')
        return 0
    day = a.date or datetime.now(ZoneInfo('Asia/Karachi')).date().isoformat()
    try:
        datetime.strptime(day, '%Y-%m-%d')
    except ValueError:
        print('ERROR: invalid date', file=sys.stderr)
        return 2
    url = BASE + day + '.Z'
    dest = Path(a.directory) / (day.replace('-', '') + '_new.lis.Z')
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and zipfile.is_zipfile(dest):
        print('EXISTS:', dest)
        return 0
    req = urllib.request.Request(url, headers={'Accept': 'application/octet-stream', 'User-Agent': 'PSX-Data-Collector/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            data = resp.read(5_000_001)
        if len(data) > 5_000_000 or not zipfile.is_zipfile(io.BytesIO(data)):
            raise ValueError('response is not a valid ZIP-formatted PSX archive')
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = archive.namelist()
            if not any(name.lower().endswith('.lis') for name in names):
                raise ValueError('archive lacks .lis data')
            if archive.testzip() is not None:
                raise ValueError('archive integrity check failed')
        dest.write_bytes(data)
        print('DOWNLOADED:', dest)
        return 0
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError) as exc:
        print(f'DOWNLOAD_UNAVAILABLE: {type(exc).__name__}: {exc}; no fabricated data')
        return 0  # Pipeline still evaluates freshness and may fail later.

if __name__ == '__main__':
    raise SystemExit(main())
