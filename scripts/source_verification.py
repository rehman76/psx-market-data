#!/usr/bin/env python3
"""Audit independently supplied PSX DPS observations against research candles.

The audit NEVER fetches a web page, trusts an unverified URL as evidence of
authenticity, or marks a stock trade-eligible. Evidence is optional and must be
provided through an authorized, separately reviewed workflow.
"""
import argparse
from datetime import date, datetime, timezone
import json
from pathlib import Path
import sqlite3
import sys
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.discover_candidates import selected_rows

PRICE_TOLERANCE = 0.005

def valid_dps_url(url):
    try:
        parsed = urlparse(url)
        return (parsed.scheme == 'https' and parsed.hostname == 'dps.psx.com.pk'
                and not parsed.username and not parsed.password)
    except (TypeError, ValueError):
        return False

def audit(conn, symbols, cutoff, supplied_evidence=None):
    """A matching observation is MATCHED_SUBMITTED_EVIDENCE, not official verification."""
    evidence = supplied_evidence or []
    if not isinstance(evidence, list):
        raise ValueError('evidence must be a JSON array')
    entries = {}
    for item in evidence:
        if not isinstance(item, dict) or set(item) != {'symbol','trade_date','open','high','low','close','volume','source_url','captured_at_utc'}:
            raise ValueError('each evidence record needs exact required fields')
        symbol = item['symbol']
        day = item['trade_date']
        if not isinstance(symbol,str) or symbol not in symbols:
            raise ValueError('evidence symbol not configured in discovery universe')
        if not isinstance(day,str) or date.fromisoformat(day)>date.fromisoformat(cutoff):
            raise ValueError('evidence date outside completed cutoff')
        if not valid_dps_url(item['source_url']):
            raise ValueError('evidence URL must be HTTPS dps.psx.com.pk')
        captured = datetime.fromisoformat(item['captured_at_utc'].replace('Z','+00:00'))
        if captured.tzinfo is None or captured.utcoffset().total_seconds()!=0:
            raise ValueError('captured_at_utc must include UTC timezone')
        values = []
        for k in ('open','high','low','close','volume'):
            value = item[k]
            if type(value) not in (int,float):
                raise ValueError('numeric OHLCV fields required')
            import math
            if not math.isfinite(value):
                raise ValueError('nonfinite numeric evidence')
            values.append(value)
        op,hi,lo,cl,vol=values
        if min(op,hi,lo,cl)<=0 or vol<0 or int(vol)!=vol or not (lo<=min(op,cl)<=max(op,cl)<=hi):
            raise ValueError('invalid OHLCV evidence')
        key=(symbol,day)
        if key in entries:
            raise ValueError('duplicate evidence symbol/date')
        entries[key]=item
    reviews=[]
    for symbol in symbols:
        rows,conflicts,unknown=selected_rows(conn,symbol,cutoff,limit=100000)
        by_day={r['date']:r for r in rows}
        submitted=[v for (s,d),v in entries.items() if s==symbol]
        checked=[]
        for observation in sorted(submitted,key=lambda v:v['trade_date']):
            row=by_day.get(observation['trade_date'])
            if not row:
                status='LOCAL_CANDLE_MISSING'
                differences=['missing_local_candle']
            else:
                differences=[k for k in ('open','high','low','close')
                             if abs(float(row[k])-float(observation[k]))>PRICE_TOLERANCE]
                if int(row['volume'])!=int(observation['volume']):
                    differences.append('volume')
                status='MATCHED_SUBMITTED_EVIDENCE' if not differences else 'MISMATCH'
            checked.append({
                'trade_date':observation['trade_date'],
                'status':status,
                'different_fields':differences,
                'submitted_source_url':observation['source_url'],
                'submitted_captured_at_utc':observation['captured_at_utc'],
                'local_market_code':row['market_code'] if row else None,
                'local_source_file':row['source_file'] if row else None,
            })
        matched=sum(c['status']=='MATCHED_SUBMITTED_EVIDENCE' for c in checked)
        mismatches=sum(c['status'] in ('MISMATCH','LOCAL_CANDLE_MISSING') for c in checked)
        reviews.append({
            'symbol':symbol,
            'status':'NO_INDEPENDENT_EVIDENCE' if not checked else
                     'DISCREPANCY_REVIEW_REQUIRED' if mismatches or conflicts else
                     'SUBMITTED_EVIDENCE_MATCHES_UNATTESTED',
            'independently_verified':False,
            'submitted_evidence_count':len(checked),
            'matched_count':matched,
            'discrepancy_count':mismatches,
            'mapped_code_conflict_dates':conflicts[:20],
            'unmapped_codes_seen':unknown,
            'checks':checked,
        })
    return {
        'schema_version':'1.0',
        'generated_at_utc':datetime.now(timezone.utc).isoformat(),
        'completed_session_cutoff':cutoff,
        'evidence_provenance':'user_supplied_unattested_not_independently_authenticated',
        'official_psx_dps_verification_complete':False,
        'fundamental_verification_complete':False,
        'not_investment_advice':True,
        'reviews':reviews,
        'health':{
            'symbols':len(reviews),
            'without_independent_evidence':sum(r['status']=='NO_INDEPENDENT_EVIDENCE' for r in reviews),
            'with_submitted_evidence':sum(r['submitted_evidence_count']>0 for r in reviews),
            'matched_observations':sum(r['matched_count'] for r in reviews),
            'discrepancies':sum(r['discrepancy_count'] for r in reviews),
            'independently_verified':0,
            'trade_eligible':0,
        },
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--db',default='state/psx_ohlcv.sqlite')
    ap.add_argument('--discovery',default='publish/discovery_watchlist.json')
    ap.add_argument('--evidence',default=None,help='Optional user-supplied, independently reviewed DPS JSON evidence')
    ap.add_argument('--out',default='publish/source_verification.json')
    args=ap.parse_args()
    discovery=json.loads(Path(args.discovery).read_text())
    evidence=json.loads(Path(args.evidence).read_text()) if args.evidence else []
    with sqlite3.connect(args.db) as conn:
        result=audit(conn,discovery['symbols_requested'],discovery['completed_session_cutoff'],evidence)
    target=Path(args.out)
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print('PSX source evidence audit:',result['health'])
if __name__=='__main__':
    main()
