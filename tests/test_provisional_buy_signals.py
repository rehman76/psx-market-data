import unittest
from scripts.provisional_buy_signals import build

def agenda():
    return {'completed_session_cutoff':'2026-10-15','stocks':[
       {'symbol':'AAA','status':'WATCH','observed_session':'2026-10-15',
        'research_close':110.0,'missing_requirements':['OFFICIAL_PRICE_NOT_INDEPENDENTLY_VERIFIED'],
        'psx_company_page':'https://dps.psx.com.pk/company/AAA',
        'technical':{'sma20':100.0,'sma50':95.0,'rsi14_wilder':60.0,
                     'relative_volume':1.3,'recent_20_session_high':120.0,
                     'recent_20_session_low':90.0}},
       {'symbol':'BBB','status':'WATCH','observed_session':'2026-10-15',
        'research_close':110.0,'technical':{'sma20':100.0,'sma50':95.0,'rsi14_wilder':45.0,
                     'relative_volume':1.3,'recent_20_session_high':120.0,
                     'recent_20_session_low':90.0}},
       {'symbol':'CCC','status':'DATA_PENDING','observed_session':None,
        'research_close':None,'technical':{}}]}

class TestProvisionalBuySignals(unittest.TestCase):
    def test_provisional_signal_remains_unapproved(self):
        x=build(agenda())
        self.assertEqual(x['summary']['provisional_buy_candidates'],1)
        self.assertEqual(x['summary']['early_buy_watch'],0)
        self.assertEqual(x['signals'][0]['screening_passed'],4)
        r=x['signals'][0]
        self.assertEqual(r['signal'],'PROVISIONAL_BUY_CANDIDATE')
        self.assertFalse(r['trade_eligible'])
        self.assertTrue(r['user_approval_required'])
        self.assertEqual(r['approved_shares'],0)
        self.assertIsNone(r['entry_price_pkr'])
        self.assertEqual(r['buy_trigger']['reference_resistance_pkr'],120.0)
        self.assertFalse(r['buy_trigger']['triggered'])
        self.assertIsNone(r['invalidation']['actual_stop_order_price_pkr'])
        self.assertIn('OFFICIAL_PRICE_NOT_INDEPENDENTLY_VERIFIED',r['missing_requirements'])

    def test_early_buy_watch_three_of_four(self):
        a=agenda()
        a['stocks'][0]['technical']['sma50']=105.0
        x=build(a)
        r=x['signals'][0]
        self.assertEqual(r['signal'],'EARLY_BUY_WATCH')
        self.assertEqual(r['screening_passed'],3)
        self.assertFalse(r['screening_checks']['ma20_above_ma50'])
        self.assertFalse(r['trade_eligible'])
        self.assertEqual(r['approved_shares'],0)
        self.assertFalse(r['buy_trigger']['triggered'])
        self.assertIsNone(r['entry_price_pkr'])
        self.assertIsNone(r['target_price_pkr'])
        self.assertIsNone(r['invalidation']['actual_stop_order_price_pkr'])

    def test_early_low_volume(self):
        a=agenda()
        a['stocks'][0]['technical']['relative_volume']=0.35
        r=build(a)['signals'][0]
        self.assertEqual(r['signal'],'EARLY_BUY_WATCH')
        self.assertEqual(r['screening_passed'],3)
        self.assertFalse(r['screening_checks']['relative_volume_at_least_1'])

    def test_wait_and_missing_data(self):
        x=build(agenda())
        self.assertEqual(x['signals'][1]['signal'],'WAIT_FOR_TECHNICAL_CONFIRMATION')
        self.assertEqual(x['signals'][2]['signal'],'INSUFFICIENT_DATA')

    def test_stale_date_never_emits_buy(self):
        a=agenda()
        a['stocks'][0]['observed_session']='2026-10-14'
        self.assertEqual(build(a)['signals'][0]['signal'],'INSUFFICIENT_DATA')

    def test_invalid_prices_and_indicators(self):
        a=agenda()
        a['stocks'][0]['research_close']=140.0
        self.assertEqual(build(a)['signals'][0]['signal'],'INSUFFICIENT_DATA')
        a=agenda()
        a['stocks'][0]['technical']['relative_volume']=0.7
        self.assertEqual(build(a)['signals'][0]['signal'],'EARLY_BUY_WATCH')
        a['stocks'][0]['technical']['sma50']=105.0
        self.assertEqual(build(a)['signals'][0]['signal'],'WAIT_FOR_TECHNICAL_CONFIRMATION')

    def test_duplicate_symbol_rejected(self):
        a=agenda()
        a['stocks'][1]['symbol']='AAA'
        with self.assertRaises(ValueError):build(a)

if __name__=='__main__':unittest.main()
