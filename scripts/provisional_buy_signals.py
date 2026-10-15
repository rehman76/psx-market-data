#!/usr/bin/env python3
"""Human-review technical BUY candidates from research-only PSX data.

This is a *signal of interest*, NOT an executed, independently verified or
risk-approved order. Outputs clear dated evidence and manual checks.
"""
import argparse
from datetime import date, datetime, timezone
import json
import math
from pathlib import Path

def positive(v):
    return type(v) in (int,float) and math.isfinite(v) and v>0

def evaluate(stock, cutoff):
    symbol=stock['symbol']
    session=stock.get('observed_session')
    technical=stock.get('technical') or {}
    price=stock.get('research_close')
    sma20=technical.get('sma20')
    sma50=technical.get('sma50')
    rsi=technical.get('rsi14_wilder')
    volume=technical.get('relative_volume')
    high=technical.get('recent_20_session_high')
    low=technical.get('recent_20_session_low')
    issues=list(stock.get('missing_requirements') or [])
    if session:
        date.fromisoformat(session)
    valid= (session==cutoff and stock.get('status')=='WATCH' and
            all(positive(v) for v in (price,sma20,sma50,volume,high,low)) and
            type(rsi) in (float,int) and math.isfinite(rsi) and 0<=rsi<=100 and
            low<=price<=high and low<high)
    signal='INSUFFICIENT_DATA'
    rationale=[]
    if valid:
        # A watch-level BUY candidate means price is trending constructively and
        # some participation is present; it is not an executed breakout.
        if price>sma20 and sma20>sma50 and 50<=rsi<=70 and volume>=1.0:
            signal='PROVISIONAL_BUY_CANDIDATE'
            rationale=['Research close above MA20','MA20 above MA50',
                       'RSI14 between 50 and 70','Relative volume >= 1.0']
        else:
            signal='WAIT_FOR_TECHNICAL_CONFIRMATION'
            if price<=sma20:rationale.append('Research close not above MA20')
            if sma20<=sma50:rationale.append('MA20 not above MA50')
            if rsi<50 or rsi>70:rationale.append('RSI outside 50-70 constructive range')
            if volume<1:rationale.append('Below-average session volume')
    else:
        issues.append('MISSING_OR_STALE_TECHNICAL_OBSERVATION')
    return {
      'symbol':symbol, 'signal':signal,
      'research_only':True,'trade_eligible':False,'user_approval_required':True,
      'observed_session':session,'research_close_pkr':price,
      'buy_trigger': {'condition':'FUTURE_CLOSE_ABOVE_PRIOR_20_SESSION_HIGH_WITH_VOLUME_CONFIRMATION',
        'reference_resistance_pkr':high if valid else None,
        'required_relative_volume':1.5,'required_rsi_above':50,
        'requires_improving_macd':True,'triggered':False},
      'invalidation':{'reference_20_session_low_pkr':low if valid else None,
                      'actual_stop_order_price_pkr':None,
                      'note':'Research reference, not a position-specific executable stop'},
      'entry_price_pkr':None, 'target_price_pkr':None,
      'approved_shares':0,'reward_to_risk_verified':False,
      'technical_rationale':rationale,
      'manual_verification':[
          'Confirm latest completed-session OHLCV and market code independently on official PSX DPS',
          'Check current tradable price, market depth, spreads and trading liquidity',
          'Review issuer announcements and authenticated financial results',
          'Check support/invalidation, executable stop and target yield reward/risk >=2:1',
          'Verify cash, total position concentration and risk <=1% of portfolio equity'
      ], 'missing_requirements':issues,
      'psx_company_page':stock.get('psx_company_page'),
      'source_status':'RESEARCH_ONLY_UNATTESTED'
    }

def build(agenda):
    cutoff=agenda['completed_session_cutoff']
    date.fromisoformat(cutoff)
    stocks=agenda['stocks']
    if not isinstance(stocks,list) or not stocks:
        raise ValueError('research agenda missing stocks')
    symbols=[s['symbol'] for s in stocks]
    if len(symbols)!=len(set(symbols)) or len(symbols)>40:
        raise ValueError('duplicate or oversized research universe')
    rows=[evaluate(s,cutoff) for s in stocks]
    return {
       'schema_version':'1.0','generated_at_utc':datetime.now(timezone.utc).isoformat(),
       'completed_session_cutoff':cutoff,'provenance':'CURATED_RESEARCH_FEED_NOT_AUTHENTICATED_DPS',
       'purpose':'Human-reviewed provisional technical buy-candidate screening',
       'not_investment_advice':True,'automated_trading':False,
       'signals':rows,
       'summary':{
           'stocks_evaluated':len(rows),
           'provisional_buy_candidates':sum(r['signal']=='PROVISIONAL_BUY_CANDIDATE' for r in rows),
           'technical_wait':sum(r['signal']=='WAIT_FOR_TECHNICAL_CONFIRMATION' for r in rows),
           'insufficient_data':sum(r['signal']=='INSUFFICIENT_DATA' for r in rows),
           'officially_verified_buy_orders':0,'approved_trade_orders':0,
       }
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--agenda',default='publish/research_agenda.json')
    p.add_argument('--out',default='publish/provisional_buy_signals.json')
    a=p.parse_args()
    report=build(json.loads(Path(a.agenda).read_text(encoding='utf-8')))
    output=Path(a.out)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print('Provisional BUY screening:',report['summary'])
if __name__=='__main__':main()
