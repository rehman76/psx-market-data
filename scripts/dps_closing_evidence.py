#!/usr/bin/env python3
"""Adapt a separately authorized PSX daily closing file to *unattested* evidence.

This does not download data or authenticate its origin. The CLI requires an
explicit DPS URL and the exact downloaded file path. Do NOT use sample files.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from urllib.parse import urlparse

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from psx_collector import members_from_file, parse_lines
from scripts.discover_candidates import allowed_market_codes, weekday_lag
from scripts.source_verification import valid_dps_url

PRICE_TOLERANCE=0.005

def normalized_url(url):
    if not valid_dps_url(url):
        raise ValueError('only an explicitly authorized HTTPS dps.psx.com.pk URL is accepted')
    p=urlparse(url)
    # Never place query credentials or fragments into generated artifacts.
    return p._replace(query='',fragment='').geturl()

def extract(path,source_url,symbols,cutoff,captured_at=None):
    path=Path(path)
    if not path.is_file() or path.stat().st_size>15*1024*1024:
        raise ValueError('authorized closing file missing or exceeds 15 MB')
    display_url=normalized_url(source_url)
    captured_at=captured_at or datetime.now(timezone.utc).isoformat()
    dt=datetime.fromisoformat(captured_at.replace('Z','+00:00'))
    if dt.utcoffset() is None or dt.utcoffset().total_seconds()!=0:
        raise ValueError('capture timestamp must be UTC')
    universe=set(symbols)
    records={}
    parsed_any=False
    for source,data in members_from_file(path):
        parsed_any=True
        rows,rejected=parse_lines(data,source)
        # Do not emit a partial evidence set from a file with unparsed lines.
        if rejected:
            raise ValueError(f'closing file contains {len(rejected)} rejected rows')
        for day,symbol,code,company,op,hi,lo,cl,vol,prev,source_file in rows:
            if symbol not in universe or day>cutoff:
                continue
            if code not in allowed_market_codes(symbol):
                continue
            if min(op,hi,lo,cl)<=0 or not (lo<=min(op,cl)<=max(op,cl)<=hi):
                continue
            key=(symbol,day)
            rec={'symbol':symbol,'trade_date':day,
                 'open':op,'high':hi,'low':lo,'close':cl,'volume':vol,
                 'market_code':code}
            existing=records.get(key)
            if existing:
                if any(abs(float(rec[k])-float(existing[k]))>PRICE_TOLERANCE
                       for k in ('open','high','low','close')) or rec['volume']!=existing['volume']:
                    raise ValueError(f'conflicting mapped closing-file candles: {symbol} {day}')
                if allowed_market_codes(symbol).index(code)<=allowed_market_codes(symbol).index(existing['market_code']):
                    continue
            records[key]=rec
    if not parsed_any:
        raise ValueError('no .lis records found')
    latest={}
    for (symbol,day),rec in records.items():
        if symbol not in latest or latest[symbol]['trade_date']<day:
            latest[symbol]=rec
    evidence=[]
    for symbol in symbols:
        record=latest.get(symbol)
        if not record or weekday_lag(record['trade_date'],cutoff)>1:
            continue
        evidence.append({k:record[k] for k in ('symbol','trade_date','open','high','low','close','volume')}|
            {'source_url':display_url,'captured_at_utc':captured_at})
    manifest={
        'file_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
        'bytes':path.stat().st_size,
        'source_url_without_query':display_url,
        'captured_at_utc':captured_at,
        'completed_session_cutoff':cutoff,
        'configured_symbols':len(symbols),
        'observations_generated':len(evidence),
        'unverified_source_authenticity':True,
        'same_source_import_self_comparison_possible':True,
        'evidence_is_not_independently_authenticated':True,
    }
    return evidence,manifest

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--file',required=True)
    ap.add_argument('--source-url',required=True)
    ap.add_argument('--discovery',default='publish/discovery_watchlist.json')
    ap.add_argument('--out',required=True)
    ap.add_argument('--manifest',required=True)
    args=ap.parse_args()
    discovery=json.loads(Path(args.discovery).read_text())
    evidence,manifest=extract(args.file,args.source_url,discovery['symbols_requested'],
                              discovery['completed_session_cutoff'])
    Path(args.out).write_text(json.dumps(evidence,indent=2,allow_nan=False)+'\n')
    Path(args.manifest).write_text(json.dumps(manifest,indent=2,allow_nan=False)+'\n')
    print(f"Extracted {len(evidence)} UNATTESTED DPS closing observations")
if __name__=='__main__':
    main()
