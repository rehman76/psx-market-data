import unittest
from scripts.fundamental_review import build, validate_entry

class FundamentalDisclosureReviewTests(unittest.TestCase):
    def filing(self, **changes):
        data={
            'symbol':'MCB',
            'fiscal_period_end':'2026-06-30',
            'published_on':'2026-09-15',
            'report_url':'https://dps.psx.com.pk/company/MCB',
            'report_sha256':'a'*64,
            'currency':'PKR',
            'units':'PKR_absolute',
            'net_income':1000000,
            'equity':6000000,
            'total_assets':10000000,
            'total_liabilities':4000000,
            'revenue':5000000,
            'operating_cash_flow':1200000,
            'shares_outstanding':100000,
            'dividend_per_share':1.5,
            'eps_reported':10,
        }
        data.update(changes)
        return data
    def test_no_disclosure_does_not_invent_figures(self):
        result=build(['MCB','SYS'],'2026-10-14')
        self.assertEqual(result['health']['disclosures_missing'],2)
        self.assertEqual(result['health']['fundamentally_verified'],0)
        self.assertEqual(result['reviews'][0]['metrics'],{})
    def test_valid_figure_arithmetic_is_not_document_authentication(self):
        result=build(['MCB'],'2026-10-14',[self.filing()])
        r=result['reviews'][0]
        self.assertEqual(r['status'],'DOCUMENT_UNATTESTED')
        self.assertEqual(r['metrics']['eps_recomputed_pkr'],10)
        self.assertIsNone(r['metrics']['net_margin_pct'])
        self.assertEqual(r['sector_class'],'BANK')
        self.assertIn('SECTOR_SPECIFIC_VALIDATION_PENDING',r['blocking_reasons'])
        self.assertIn('DOCUMENT_AUTHENTICATION_PENDING',r['blocking_reasons'])
        self.assertFalse(r['trade_eligible'])
    def test_nonbank_margin_is_still_computed(self):
        r=build(['IMAGE'],'2026-10-14',[self.filing(symbol='IMAGE')])['reviews'][0]
        self.assertEqual(r['metrics']['net_margin_pct'],20)
        self.assertEqual(r['sector_class'],'NON_BANK_UNCLASSIFIED')
    def test_stale_disclosure_is_flagged(self):
        r=build(['MCB'],'2026-10-14',[self.filing(fiscal_period_end='2025-12-31',published_on='2026-03-15')])['reviews'][0]
        self.assertEqual(r['status'],'NEEDS_REVIEW')
        self.assertIn('FINANCIAL_REPORT_STALE',r['blocking_reasons'])
    def test_balance_and_eps_reconciliation_are_flagged(self):
        r=build(['MCB'],'2026-10-14',[self.filing(equity=2500000,eps_reported=15)])['reviews'][0]
        self.assertIn('EPS_RECONCILIATION_REVIEW',r['blocking_reasons'])
        self.assertIn('BALANCE_SHEET_RECONCILIATION_REVIEW',r['blocking_reasons'])
    def test_duplicate_and_unknown_symbols_rejected(self):
        with self.assertRaises(ValueError):
            build(['MCB'],'2026-10-14',[self.filing(),self.filing()])
        with self.assertRaises(ValueError):
            build(['SYS'],'2026-10-14',[self.filing()])
    def test_future_filing_and_bad_units_rejected(self):
        with self.assertRaises(ValueError):
            build(['MCB'],'2026-10-14',[self.filing(published_on='2026-10-15')])
        with self.assertRaises(ValueError):
            build(['MCB'],'2026-10-14',[self.filing(units='PKR_millions')])
    def test_bad_url_and_boolean_values_rejected(self):
        with self.assertRaises(ValueError):
            build(['MCB'],'2026-10-14',[self.filing(report_url='http://bad.test/report')])
        with self.assertRaises(ValueError):
            build(['MCB'],'2026-10-14',[self.filing(net_income=True)])
        with self.assertRaises(ValueError):
            build(['MCB'],'2026-10-14',[self.filing(report_url='https://dps.psx.com.pk/company/MCB?secret=token')])
    def test_bank_suppresses_inappropriate_industrial_ratios(self):
        r=build(['MCB'],'2026-10-14',[self.filing()])['reviews'][0]
        self.assertEqual(r['sector_class'],'BANK')
        self.assertIsNone(r['metrics']['net_margin_pct'])
        self.assertIsNone(r['metrics']['operating_cash_flow_to_net_income'])
        self.assertIn('SECTOR_SPECIFIC_VALIDATION_PENDING',r['blocking_reasons'])
        self.assertFalse(r['trade_eligible'])
    def test_nonpositive_equity_yields_no_roe(self):
        r=build(['MCB'],'2026-10-14',[self.filing(equity=-1)])['reviews'][0]
        self.assertIsNone(r['metrics']['return_on_equity_pct'])
        self.assertEqual(r['status'],'NEEDS_REVIEW')
if __name__=='__main__':
    unittest.main()
