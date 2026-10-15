import sqlite3
import unittest

from scripts.source_verification import audit

class SourceVerificationTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:')
        self.db.execute("""CREATE TABLE ohlcv (
            trade_date TEXT, symbol TEXT, market_code TEXT, open REAL,
            high REAL, low REAL, close REAL, volume INTEGER, source_file TEXT)""")
        self.db.execute("INSERT INTO ohlcv VALUES (?,?,?,?,?,?,?,?,?)",
            ('2026-10-14','MCB','0807',370,375,365,372,200000,'sample.lis'))
    def tearDown(self):
        self.db.close()
    def evidence(self, **changes):
        x={
            'symbol':'MCB', 'trade_date':'2026-10-14',
            'open':370, 'high':375, 'low':365, 'close':372,
            'volume':200000,
            'source_url':'https://dps.psx.com.pk/company/MCB',
            'captured_at_utc':'2026-10-15T10:00:00Z'
        }
        x.update(changes)
        return x
    def test_absent_evidence_remains_pending(self):
        result=audit(self.db,['MCB'],'2026-10-14')
        self.assertEqual(result['health']['without_independent_evidence'],1)
        self.assertFalse(result['official_psx_dps_verification_complete'])
    def test_matching_is_not_authenticated(self):
        r=audit(self.db,['MCB'],'2026-10-14',[self.evidence()])
        self.assertEqual(r['reviews'][0]['status'],'SUBMITTED_EVIDENCE_MATCHES_UNATTESTED')
        self.assertEqual(r['health']['matched_observations'],1)
        self.assertFalse(r['reviews'][0]['independently_verified'])
        self.assertEqual(r['health']['trade_eligible'],0)
    def test_price_and_volume_mismatch(self):
        r=audit(self.db,['MCB'],'2026-10-14',[self.evidence(close=373,volume=200001)])
        self.assertEqual(r['reviews'][0]['status'],'DISCREPANCY_REVIEW_REQUIRED')
        self.assertEqual(set(r['reviews'][0]['checks'][0]['different_fields']),{'close','volume'})
    def test_fake_host_rejected(self):
        for url in ['https://dps.psx.com.pk.evil.example/MCB','http://dps.psx.com.pk/company/MCB']:
            with self.subTest(url=url),self.assertRaises(ValueError):
                audit(self.db,['MCB'],'2026-10-14',[self.evidence(source_url=url)])
    def test_future_date_rejected(self):
        with self.assertRaises(ValueError):
            audit(self.db,['MCB'],'2026-10-14',[self.evidence(trade_date='2026-10-15')])
    def test_duplicate_evidence_rejected(self):
        with self.assertRaises(ValueError):
            audit(self.db,['MCB'],'2026-10-14',[self.evidence(),self.evidence()])
if __name__=='__main__':
    unittest.main()
