#!/usr/bin/env python3
"""Fail-closed fundamental disclosure intake; nothing is invented or auto-approved.

Accepts an explicitly supplied JSON list of disclosure-derived figures with
document provenance. Validates arithmetic and freshness, but does NOT
authenticate the uploaded reports. Reports remain research-only.
"""
import argparse
from datetime import date, datetime, timezone
import json
import math
from pathlib import Path
from urllib.parse import urlparse

FIELDS = {
    'symbol', 'fiscal_period_end', 'published_on', 'report_url',
    'report_sha256', 'currency', 'units',
    'net_income', 'equity', 'total_assets', 'total_liabilities',
    'revenue', 'operating_cash_flow', 'shares_outstanding',
    'dividend_per_share', 'eps_reported'
}
NUMERIC = ('net_income','equity','total_assets','total_liabilities','revenue',
           'operating_cash_flow','shares_outstanding','dividend_per_share','eps_reported')

def validate_entry(entry, symbols, cutoff):
    if not isinstance(entry, dict) or set(entry) != FIELDS:
        raise ValueError('disclosure must contain exactly the specified fields')
    if not isinstance(entry['symbol'], str) or entry['symbol'] not in symbols:
        raise ValueError('disclosure symbol not configured')
    period=date.fromisoformat(entry['fiscal_period_end'])
    published=date.fromisoformat(entry['published_on'])
    max_date=date.fromisoformat(cutoff)
    if period>published or published>max_date:
        raise ValueError('disclosure period/publication outside completed cutoff')
    if entry['currency'] != 'PKR' or entry['units'] != 'PKR_absolute':
        raise ValueError('all figures must be in absolute PKR (not millions/thousands)')
    parsed=urlparse(entry['report_url'])
    if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('report URL must be absolute HTTPS without credentials')
    if not isinstance(entry['report_sha256'],str) or len(entry['report_sha256'])!=64 or any(x not in '0123456789abcdef' for x in entry['report_sha256'].lower()):
        raise ValueError('valid SHA-256 of source document required')
    for field in NUMERIC:
        x=entry[field]
        if type(x) not in (int,float) or not math.isfinite(x):
            raise ValueError('all disclosure metrics must be finite numeric values')
    if entry['shares_outstanding']<=0 or entry['total_assets']<=0:
        raise ValueError('positive shares and assets required')
    if entry['total_liabilities']<0 or entry['dividend_per_share']<0:
        raise ValueError('negative liabilities or dividends invalid')
    # Balance sheet and per-share figures may reflect different classifications
    # and restatements. Flag implausibility without guessing the 'correct' data.
    balance_gap=abs(entry['total_assets']-entry['total_liabilities']-entry['equity'])
    balance_tolerance=max(1.0,abs(entry['total_assets'])*0.01)
    eps_calculated=entry['net_income']/entry['shares_outstanding']
    eps_gap=abs(eps_calculated-entry['eps_reported'])
    return {
        'balance_sheet_roughly_reconciles': balance_gap<=balance_tolerance,
        'eps_roughly_reconciles': eps_gap<=max(.01,abs(entry['eps_reported'])*.05),
        'balance_sheet_gap_pkr':round(balance_gap,2),
        'eps_recomputed_pkr':round(eps_calculated,4),
        'net_margin_pct':round(entry['net_income']/entry['revenue']*100,3) if entry['revenue']>0 else None,
        'return_on_equity_pct':round(entry['net_income']/entry['equity']*100,3) if entry['equity']>0 else None,
        'operating_cash_flow_to_net_income':round(entry['operating_cash_flow']/entry['net_income'],3) if entry['net_income']>0 else None,
    }

def build(symbols, cutoff, disclosures=None):
    disclosures=disclosures if disclosures is not None else []
    if not isinstance(disclosures,list):
        raise ValueError('disclosures input must be an array')
    by_symbol={}
    for d in disclosures:
        checks=validate_entry(d,symbols,cutoff)
        symbol=d['symbol']
        if symbol in by_symbol:
            raise ValueError('only one report per symbol accepted (select latest filing)')
        by_symbol[symbol]=(d,checks)
    reviews=[]
    for symbol in symbols:
        item=by_symbol.get(symbol)
        if item is None:
            reviews.append({'symbol':symbol,'status':'DISCLOSURE_MISSING',
              'blocking_reasons':['FUNDAMENTAL_DISCLOSURE_MISSING','DOCUMENT_AUTHENTICATION_PENDING'],
              'fundamentals_verified':False,'trade_eligible':False,'metrics':{}})
            continue
        d,checks=item
        stale=(date.fromisoformat(cutoff)-date.fromisoformat(d['fiscal_period_end'])).days>240
        issues=[]
        if stale: issues.append('FINANCIAL_REPORT_STALE')
        if not checks['balance_sheet_roughly_reconciles']: issues.append('BALANCE_SHEET_RECONCILIATION_REVIEW')
        if not checks['eps_roughly_reconciles']: issues.append('EPS_RECONCILIATION_REVIEW')
        issues.append('DOCUMENT_AUTHENTICATION_PENDING')
        reviews.append({'symbol':symbol,
           'status':'NEEDS_REVIEW' if stale or len(issues)>1 else 'DOCUMENT_UNATTESTED',
           'fiscal_period_end':d['fiscal_period_end'],
           'published_on':d['published_on'],
           'report_url':d['report_url'],
           'report_sha256':d['report_sha256'],
           'blocking_reasons':issues,
           'fundamentals_verified':False, 'trade_eligible':False,
           'metrics':checks})
    return {'schema_version':'1.0',
       'generated_at_utc':datetime.now(timezone.utc).isoformat(),
       'completed_session_cutoff':cutoff,
       'provenance':'user_submitted_unattested_filing_figures',
       'full_psx_coverage':False,
       'fundamental_verification_complete':False,
       'investment_advice':False,
       'reviews':reviews,
       'health':{
         'symbols':len(reviews),
         'disclosures_missing':sum(r['status']=='DISCLOSURE_MISSING' for r in reviews),
         'documents_unattested':sum(r['status']=='DOCUMENT_UNATTESTED' for r in reviews),
         'needs_review':sum(r['status']=='NEEDS_REVIEW' for r in reviews),
         'fundamentally_verified':0,
         'trade_eligible':0,
       }}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--discovery',default='publish/discovery_watchlist.json')
    parser.add_argument('--disclosures',help='Optional operator-reviewed JSON list of filing figures')
    parser.add_argument('--out',default='publish/fundamental_review.json')
    args=parser.parse_args()
    discovery=json.loads(Path(args.discovery).read_text())
    items=json.loads(Path(args.disclosures).read_text()) if args.disclosures else None
    report=build(discovery['symbols_requested'],discovery['completed_session_cutoff'],items)
    dest=Path(args.out)
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print('Fundamentals:',report['health'])
if __name__=='__main__':
    main()
