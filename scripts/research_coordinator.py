#!/usr/bin/env python3
"""Fail-closed research coordinator with official PSX company-page references.

Never scrapes PSX pages, assumes an official quote was verified, or trades.
"""
import argparse
from datetime import date, datetime, timezone
import json
from pathlib import Path
from urllib.parse import quote

MAX_SYMBOLS=40
HOLDINGS={'MCB','SYS','KOHE'}

def official_company_url(symbol):
    if not isinstance(symbol,str) or not (1<=len(symbol)<=12) or not symbol.isascii() or not symbol.isalnum() or symbol!=symbol.upper():
        raise ValueError('Invalid official PSX ticker')
    return 'https://dps.psx.com.pk/company/'+quote(symbol,safe='')

def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def coordinate(discovery,technical,source,fundamentals,documents,previous=None):
    cutoff=discovery['completed_session_cutoff']
    date.fromisoformat(cutoff)
    symbols=discovery['symbols_requested']
    if not isinstance(symbols,list) or not 1<=len(symbols)<=MAX_SYMBOLS or len(symbols)!=len(set(symbols)):
        raise ValueError('Bad universe')
    for symbol in symbols: official_company_url(symbol)
    for label,report in [('technicals',technical),('source',source),('fundamentals',fundamentals)]:
        if report.get('completed_session_cutoff')!=cutoff: raise ValueError(label+' cutoff mismatch')
    data={}
    for label,report,key in [('discovery',discovery,'candidates'),('technical',technical,'reviews'),
                              ('source',source,'reviews'),('fundamentals',fundamentals,'reviews'),
                              ('documents',documents,'reviews')]:
        values=report[key]
        if not isinstance(values,list): raise ValueError('Invalid '+label)
        mapping={x['symbol']:x for x in values}
        if len(mapping)!=len(values) or set(mapping)-set(symbols): raise ValueError('Bad '+label+' symbols')
        if label!='discovery' and set(mapping)!=set(symbols): raise ValueError('Incomplete '+label)
        data[label]=mapping
    old={}
    if previous is not None:
        if not isinstance(previous,dict) or not isinstance(previous.get('entries'),list) or len(previous['entries'])>MAX_SYMBOLS:
            raise ValueError('Invalid prior register')
        for entry in previous['entries']:
            s=entry['symbol']
            if s in old or s not in symbols: raise ValueError('Duplicate/unexpected previous symbol')
            last=entry['last_seen']
            date.fromisoformat(last)
            if last>cutoff: raise ValueError('Future prior observation')
            old[s]=entry
    rows=[]
    entries=[]
    for s in symbols:
        c=data['discovery'].get(s)
        t=data['technical'][s]
        sv=data['source'][s]
        f=data['fundamentals'][s]
        doc=data['documents'][s]
        stamp=c['date'] if c else None
        if stamp and stamp>cutoff: raise ValueError('Future candidate')
        previous_entry=old.get(s)
        first=previous_entry['first_seen'] if previous_entry else stamp
        last=previous_entry['last_seen'] if previous_entry else None
        count=previous_entry['observations'] if previous_entry else 0
        if stamp and (last is None or stamp>last):
            last=stamp
            count+=1
        ready=bool(c and t['status']=='TECHNICAL_REVIEW_READY')
        missing=[]
        if not ready: missing.append('TECHNICAL_DATA_PENDING')
        if not sv['independently_verified']: missing.append('OFFICIAL_PRICE_NOT_INDEPENDENTLY_VERIFIED')
        if not f['fundamentals_verified']: missing.append('ISSUER_FINANCIALS_NOT_AUTHENTICATED')
        if not doc['issuer_authenticity_verified']: missing.append('DOCUMENT_AUTHENTICITY_PENDING')
        if c and not c.get('market_code_mapping_verified'): missing.append('MARKET_CODE_MAPPING_UNVERIFIED')
        tech=t.get('technical',{})
        row={'symbol':s,'psx_company_page':official_company_url(s),
             'psx_page_validation':'LINK_ONLY_NOT_FETCHED_OR_ATTESTED',
             'portfolio_holding':s in HOLDINGS,
             'status':'WATCH' if ready else 'DATA_PENDING',
             'trade_eligible':False,
             'observed_session':stamp,'research_close':c['close'] if c else None,
             'rank_score':c['rank_score'] if c else None,
             'technical':{k:tech.get(k) for k in ('sma20','sma50','rsi14_wilder',
                         'relative_volume','recent_20_session_high','recent_20_session_low','atr14_wilder')},
             'missing_requirements':missing,
             'next_review':'Check dated REG-session official PSX page quote, company announcements, issuer PDFs and risk before any trade'}
        rows.append(row)
        if last:
            entries.append({'symbol':s,'first_seen':first,'last_seen':last,
                'observations':count,'status':row['status']})
    ranked=sorted((r for r in rows if r['status']=='WATCH' and not r['portfolio_holding']),
                  key=lambda r:(-r['rank_score'],r['symbol']))
    meta={'schema_version':'1.0','generated_at_utc':datetime.now(timezone.utc).isoformat(),
          'completed_session_cutoff':cutoff,'scope':'curated_not_full_psx',
          'research_only':True,'automated_trading':False}
    agenda={**meta,'stocks':rows,'watch_shortlist':[r['symbol'] for r in ranked[:5]],
            'health':{'configured':len(symbols),'watch_candidates':len(ranked),
                'shortlisted':min(len(ranked),5),'trade_eligible':0}}
    register={**meta,'entries':entries,'note':'Observations count only once per new dated session; no inferred prior recommendation.'}
    return agenda,register

def main():
    p=argparse.ArgumentParser()
    for key,default in [('discovery','publish/discovery_watchlist.json'),
                         ('technical','publish/research_validation.json'),
                         ('source','publish/source_verification.json'),
                         ('fundamentals','publish/fundamental_review.json'),
                         ('documents','publish/financial_document_integrity.json')]:
        p.add_argument('--'+key,default=default)
    p.add_argument('--previous',help='Optional last validated persisted register')
    p.add_argument('--agenda-out',default='publish/research_agenda.json')
    p.add_argument('--register-out',default='publish/recommendation_register.json')
    a=p.parse_args()
    previous=load(a.previous) if a.previous and Path(a.previous).is_file() else None
    agenda,register=coordinate(*(load(getattr(a,k)) for k in ('discovery','technical','source','fundamentals','documents')),previous)
    for name,content in ((a.agenda_out,agenda),(a.register_out,register)):
        target=Path(name)
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps(content,indent=2,allow_nan=False)+'\n')
    print('Research coordinator:',agenda['health'])
if __name__=='__main__': main()
