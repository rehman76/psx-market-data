#!/usr/bin/env python3
"""PSX daily closing-file importer and optional authorized downloader.

Requires Python 3.10+; no third-party packages for import/export.
The uploaded .lis.Z sample is ZIP data with a pipe-delimited .lis member.
Only explicitly supplied, authorized download URLs are used.
"""
import argparse
import csv
from datetime import date, datetime, timedelta
from io import BytesIO
from pathlib import Path
import sqlite3
import sys
from urllib.request import Request, urlopen
from urllib.parse import urlparse
import zipfile

SCHEMA = """
CREATE TABLE IF NOT EXISTS ohlcv (
  trade_date TEXT NOT NULL, symbol TEXT NOT NULL, market_code TEXT NOT NULL,
  company TEXT NOT NULL, open REAL NOT NULL, high REAL NOT NULL,
  low REAL NOT NULL, close REAL NOT NULL, volume INTEGER NOT NULL,
  previous_close REAL, source_file TEXT NOT NULL,
  PRIMARY KEY(trade_date, symbol, market_code)
);
CREATE INDEX IF NOT EXISTS idx_ohlcv_symbol_date ON ohlcv(symbol,trade_date);
"""
FIELDS = ('date','symbol','market_code','company','open','high','low','close','volume','previous_close')


def connect(db):
    conn = sqlite3.connect(db)
    conn.executescript(SCHEMA)
    return conn


def parse_lines(data, source):
    text = data.decode('utf-8-sig', errors='replace')
    rows, rejected = [], []
    for line_no, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        cells = line.rstrip('\r').split('|')
        try:
            if len(cells) < 9:
                raise ValueError('fewer than 9 columns')
            dt = datetime.strptime(cells[0].strip().upper(), '%d%b%Y').date().isoformat()
            symbol = cells[1].strip().upper()
            market = cells[2].strip()
            company = cells[3].strip()
            if not symbol or not market:
                raise ValueError('missing symbol or market')
            op, hi, lo, cl = [float(cells[i]) for i in (4, 5, 6, 7)]
            volume = int(float(cells[8]))
            previous = float(cells[9]) if len(cells)>9 and cells[9].strip() else None
            if any(not (float('-inf') < x < float('inf')) for x in (op, hi, lo, cl)):
                raise ValueError('non-finite price')
            if min(op, hi, lo, cl) < 0 or volume < 0:
                raise ValueError('negative price or volume')
            # Zero-volume derivative/special instruments can carry zero O/H/L.
            # Preserve these records but prevent them from being used as equity candles.
            if volume > 0 and (lo > min(op, cl) or hi < max(op, cl) or lo > hi):
                raise ValueError('inconsistent OHLC')
            rows.append((dt, symbol, market, company, op, hi, lo, cl, volume, previous, source))
        except (ValueError, OverflowError) as exc:
            rejected.append((line_no, str(exc)))
    return rows, rejected


def members_from_file(path):
    raw = Path(path).read_bytes()
    if zipfile.is_zipfile(BytesIO(raw)):
        with zipfile.ZipFile(BytesIO(raw)) as z:
            for info in z.infolist():
                if not info.is_dir() and info.filename.lower().endswith('.lis'):
                    yield f'{path.name}:{info.filename}', z.read(info)
    else:
        # Raw text .lis is also supported. True UNIX compress (.Z) is not.
        if raw.startswith(b'\x1f\x9d') or raw.startswith(b'\x1f\xa0'):
            raise ValueError('True UNIX .Z compression is unsupported; decompress externally first')
        yield path.name, raw


def import_file(conn, path):
    count = 0
    rejected_total = []
    found = False
    with conn:
        for source, data in members_from_file(path):
            found = True
            rows, rejected = parse_lines(data, source)
            if not rows:
                raise ValueError(f'{source}: no valid OHLCV records')
            conn.executemany('''INSERT INTO ohlcv
                (trade_date,symbol,market_code,company,open,high,low,close,volume,previous_close,source_file)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(trade_date,symbol,market_code) DO UPDATE SET
                company=excluded.company,open=excluded.open,high=excluded.high,
                low=excluded.low,close=excluded.close,volume=excluded.volume,
                previous_close=excluded.previous_close,source_file=excluded.source_file''', rows)
            count += len(rows)
            rejected_total += [(source, *r) for r in rejected]
    if not found:
        raise ValueError('ZIP has no .lis member')
    return count, rejected_total


def import_paths(conn, paths):
    files = []
    for arg in paths:
        p = Path(arg)
        if p.is_dir():
            files.extend(x for x in p.rglob('*') if x.is_file() and (x.name.lower().endswith(('.lis', '.lis.z', '.zip'))))
        elif p.is_file():
            files.append(p)
        else:
            print(f'NOT FOUND: {p}', file=sys.stderr)
    failures = 0
    for p in sorted(set(files)):
        try:
            n, bad = import_file(conn, p)
            print(f'IMPORTED {p.name}: {n} records, {len(bad)} rejected')
            for source, line, reason in bad[:5]:
                print(f'  rejected {source} line {line}: {reason}', file=sys.stderr)
        except (ValueError, zipfile.BadZipFile, OSError) as e:
            failures += 1
            print(f'FAILED {p}: {e}', file=sys.stderr)
    return failures


def export_csv(conn, output, symbols, market='0807'):
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    for symbol in symbols:
        # Market code varies by industry; choose ordinary equities excluding market_code 40
        records = conn.execute('''SELECT trade_date,symbol,market_code,company,open,high,low,close,volume,previous_close
            FROM ohlcv WHERE symbol=? AND market_code != '40' AND open>0 AND high>0 AND low>0
            ORDER BY trade_date,market_code''', (symbol.upper(),)).fetchall()
        path = out / f'{symbol.upper()}_ohlcv.csv'
        with path.open('w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(FIELDS)
            writer.writerows(records)
        print(f'EXPORTED {path} ({len(records)} rows)')


class OfficialDownloadError(ValueError):
    """A safe diagnostic code, never an HTTP response body or credentialed URL."""
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def inspect_closing_payload(data):
    """Recognize actual .lis content, not an HTML page containing a pipe."""
    if not data:
        raise OfficialDownloadError('EMPTY_RESPONSE')
    leading = data[:512].lstrip().lower()
    if leading.startswith((b'<!doctype html', b'<html', b'<?xml', b'{', b'[')):
        raise OfficialDownloadError('NON_CLOSING_DOCUMENT')
    if data.startswith((b'\\x1f\\x9d', b'\\x1f\\xa0')):
        raise OfficialDownloadError('UNSUPPORTED_UNIX_COMPRESS_Z')
    if zipfile.is_zipfile(BytesIO(data)):
        try:
            with zipfile.ZipFile(BytesIO(data)) as archive:
                members = [i for i in archive.infolist()
                           if not i.is_dir() and i.filename.lower().endswith('.lis')]
                if not members or archive.testzip() is not None:
                    raise OfficialDownloadError('INVALID_CLOSING_ZIP')
                for member in members:
                    if member.file_size > 15 * 1024 * 1024:
                        raise OfficialDownloadError('CLOSING_MEMBER_TOO_LARGE')
                    rows, rejected = parse_lines(archive.read(member), member.filename)
                    # Official files can contain a small number of malformed
                    # instrument records; reject pages masquerading as data.
                    if not rows or len(rejected) > max(20, len(rows) // 10):
                        raise OfficialDownloadError('INVALID_CLOSING_ROWS')
        except (zipfile.BadZipFile, RuntimeError):
            raise OfficialDownloadError('INVALID_CLOSING_ZIP') from None
        return 'ZIP_LIS'
    rows, rejected = parse_lines(data, 'downloaded.lis')
    if not rows or len(rejected) > max(20, len(rows) // 10):
        raise OfficialDownloadError('INVALID_CLOSING_ROWS')
    return 'RAW_LIS'


def fetch_authorized(url, output, timeout=25):
    parsed = urlparse(url)
    if (parsed.scheme != 'https' or parsed.hostname != 'dps.psx.com.pk'
            or parsed.username or parsed.password):
        raise OfficialDownloadError('SOURCE_URL_NOT_AUTHORIZED')
    request = Request(url, headers={'User-Agent': 'PSX-Research-Collector/1.0 (authorized access)'})
    try:
        with urlopen(request, timeout=timeout) as response:
            final_url = urlparse(response.geturl())
            if (final_url.scheme != 'https' or final_url.hostname != 'dps.psx.com.pk'
                    or final_url.username or final_url.password):
                raise OfficialDownloadError('REDIRECT_OUTSIDE_AUTHORIZED_HOST')
            data = response.read(15 * 1024 * 1024 + 1)
    except OfficialDownloadError:
        raise
    except Exception as exc:
        # Avoid leaking full URLs, query tokens, or HTTP response bodies in logs.
        raise OfficialDownloadError('DOWNLOAD_TRANSPORT_' + type(exc).__name__.upper()) from None
    if len(data) > 15 * 1024 * 1024:
        raise OfficialDownloadError('DOWNLOAD_TOO_LARGE')
    inspect_closing_payload(data)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(data)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', default='psx_ohlcv.sqlite', help='SQLite database path')
    sub = parser.add_subparsers(dest='command', required=True)
    imp = sub.add_parser('import', help='Import one file or a folder recursively')
    imp.add_argument('paths', nargs='+')
    exp = sub.add_parser('export', help='Export ticker CSVs from SQLite')
    exp.add_argument('--symbols', nargs='+', default=['MCB','SYS','KOHE'])
    exp.add_argument('--out', default='exports')
    dl = sub.add_parser('download', help='Fetch ONE explicitly verified and authorized HTTPS file URL')
    dl.add_argument('--url', required=True, help='Actual PSX closing-file URL (do not guess)')
    dl.add_argument('--out', required=True, help='Local file destination')
    dl.add_argument('--import-after', action='store_true')
    args = parser.parse_args()
    with connect(args.db) as conn:
        if args.command == 'import':
            return int(import_paths(conn, args.paths) > 0)
        if args.command == 'export':
            export_csv(conn, args.out, args.symbols)
        if args.command == 'download':
            downloaded = fetch_authorized(args.url, Path(args.out))
            print(f'DOWNLOADED {downloaded}')
            if args.import_after:
                return int(import_paths(conn, [str(downloaded)]) > 0)
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
