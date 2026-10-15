#!/usr/bin/env python3
"""Price-provenance reconciliation: research vs user confirmation vs official.

This report NEVER promotes self-reported prices or source-verification flags
to an independently fetched official PSX quote. Only dated same-session
comparisons are allowed. No trades or feed overrides are performed.
"""
import argparse
from datetime import date, datetime, timezone
import json
import math
from pathlib import Path

TOLERANCE_PKR = .005

def _number(value):
    return type(value) in (int,float) and math.isfinite(value) and value > 0

def _confirmed_entries(document, cutoff, allowed):
    if not isinstance(document,dict) or document.get('provenance')!='USER_CONFIRMED_IN_CHAT_NOT_OFFICIAL':
        raise ValueError('invalid user confirmation provenance')
    items=document.get('observations')
    if not isinstance(items,list) or len(items)>40:
        raise ValueError('invalid confirmation list')
    result={}
    for item in items:
        if not isinstance(item,dict):
            raise ValueError('invalid confirmation entry')
        symbol=item.get('symbol')
        day=item.get('trade_date')
        if symbol not in allowed or not isinstance(day,str) or date.fromisoformat(day)>date.fromisoformat(cutoff):
            raise ValueError('confirmation outside configured universe or cutoff')
        if not _number(item.get('price_pkr')) or item.get('independently_verified') is not False:
            raise ValueError('confirmation has invalid price or verification status')
        if item.get('confirmation_source')!='user_chat_confirmation' or item.get('price_type')!='USER_CONFIRMED_SESSION_PRICE':
            raise ValueError('invalid confirmation type')
        key=(symbol,day)
        if key in result: raise ValueError('duplicate user confirmation')
        result[key]=item
    return result

def reconcile(discovery,technical,source,confirmed):
    cutoff=discovery['completed_session_cutoff']
    date.fromisoformat(cutoff)
    symbols=discovery['symbols_requested']
    if not isinstance(symbols,list) or len(symbols)!=len(set(symbols)):
        raise ValueError('invalid configured symbols')
    if technical.get('completed_session_cutoff')!=cutoff or source.get('completed_session_cutoff')!=cutoff:
        raise ValueError('report completed session mismatch')
    candidates={r['symbol']:r for r in discovery['candidates']}
    verification={r['symbol']:r for r in source['reviews']}
    if set(verification)!=set(symbols):
        raise ValueError('missing official source audit symbol')
    records=_confirmed_entries(confirmed,cutoff,set(symbols))
    rows=[]
    for symbol in symbols:
        candidate=candidates.get(symbol)
        observed_date=candidate.get('date') if candidate else None
        research_price=candidate.get('close') if candidate else None
        if research_price is not None and not _number(research_price):
            raise ValueError('invalid research price')
        prior=[x for (s,d),x in records.items() if s==symbol]
        prior.sort(key=lambda x:x['trade_date'],reverse=True)
        user=prior[0] if prior else None
        aligned=bool(user and candidate and observed_date==user['trade_date'])
        absolute_gap=round(float(research_price)-float(user['price_pkr']),4) if aligned else None
        if not user:
            compare='NO_USER_CONFIRMATION'
        elif not candidate:
            compare='NO_RESEARCH_OBSERVATION'
        elif not aligned:
            compare='DIFFERENT_SESSION_NOT_COMPARABLE'
        elif abs(absolute_gap)<=TOLERANCE_PKR:
            compare='MATCHED_USER_CONFIRMATION_UNATTESTED'
        else:
            compare='RESEARCH_USER_PRICE_DISCREPANCY'
        audit=verification[symbol]
        # The source audit has no actual authenticated quote value/market code.
        # A verification flag is NOT enough to construct a verifiable price.
        official_price=None
        rows.append({
            'symbol':symbol,
            'research':{'price_pkr':research_price,'session_date':observed_date,
                        'provenance':'DISCOVERY_RESEARCH_PROVIDER_NOT_OFFICIAL'},
            'user_confirmation':None if user is None else {
                'price_pkr':user['price_pkr'],'session_date':user['trade_date'],
                'provenance':'USER_CONFIRMED_IN_CHAT_NOT_OFFICIAL',
                'independently_verified':False},
            'official_psx':{'price_pkr':official_price,'session_date':None,
                'provenance':'OFFICIAL_QUOTE_NOT_OBTAINED',
                'independently_verified':False,
                'audit_flag_only':bool(audit.get('independently_verified',False))},
            'reconciliation_status':compare,
            'research_minus_user_pkr':absolute_gap,
            'trade_eligible':False,
            'notes':['The user confirmation must never overwrite the underlying OHLCV, indicators or official-source audit.',
                     'Only compare observations for identical market dates and quote bases. User confirmation is not issuer or PSX attestation.']
        })
    return {'schema_version':'1.0','generated_at_utc':datetime.now(timezone.utc).isoformat(),
      'completed_session_cutoff':cutoff,'provenance':'THREE_SOURCE_PRICE_RECONCILIATION',
      'not_investment_advice':True,'trading_authorized':False,
      'prices':rows,
      'health':{'symbols':len(rows),'user_confirmed':sum(x['user_confirmation'] is not None for x in rows),
                'same_session_discrepancies':sum(x['reconciliation_status']=='RESEARCH_USER_PRICE_DISCREPANCY' for x in rows),
                'matched_unattested':sum(x['reconciliation_status']=='MATCHED_USER_CONFIRMATION_UNATTESTED' for x in rows),
                'independently_verified_official_quotes':0,'trade_eligible':0}}

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--discovery',default='publish/discovery_watchlist.json')
    p.add_argument('--technical',default='publish/research_validation.json')
    p.add_argument('--source',default='publish/source_verification.json')
    p.add_argument('--confirmations',default='config/user_confirmed_prices.json')
    p.add_argument('--out',default='publish/price_reconciliation.json')
    a=p.parse_args()
    def read(name): return json.loads(Path(name).read_text(encoding='utf-8'))
    result=reconcile(read(a.discovery),read(a.technical),read(a.source),read(a.confirmations))
    target=Path(a.out)
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print('Price reconciliation:',result['health'])
if __name__=='__main__': main()
