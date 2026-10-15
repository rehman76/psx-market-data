import sqlite3
import unittest
from datetime import date, timedelta
from scripts.discover_candidates import make_report, screen, history_count, MIN_SESSIONS

class MarketCodeReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:')
        self.db.execute("""CREATE TABLE ohlcv (
          trade_date TEXT, symbol TEXT, market_code TEXT, open REAL, high REAL,
          low REAL, close REAL, volume INTEGER, source_file TEXT)""")
    def tearDown(self):
        self.db.close()
    def seed(self, symbol='MCB', code='REG', days=MIN_SESSIONS, last='2026-10-14'):
        end=date.fromisoformat(last)
        for i in range(days):
            day=(end-timedelta(days=days-i-1)).isoformat()
            self.db.execute("INSERT INTO ohlcv VALUES (?,?,?,?,?,?,?,?,?)",
                            (day,symbol,code,100,110,90,100,1000,'fixture'))
    def test_official_code_extends_reg_history(self):
        self.seed(last='2026-10-09')
        for day in ('2026-10-12','2026-10-13','2026-10-14'):
            self.db.execute("INSERT INTO ohlcv VALUES (?,?,?,?,?,?,?,?,?)",
                            (day,'MCB','0807',100,110,90,100,1000,'official'))
        report=make_report(self.db,['MCB'],'2026-10-14')
        self.assertEqual(report['health']['fresh_candidates'],1)
        self.assertEqual(report['candidates'][0]['date'],'2026-10-14')
        self.assertEqual(report['candidates'][0]['latest_market_code'],'0807')
    def test_conflicting_overlap_is_not_ranked(self):
        self.seed()
        self.db.execute("INSERT INTO ohlcv VALUES (?,?,?,?,?,?,?,?,?)",
                        ('2026-10-14','MCB','0807',100,110,90,105,1000,'official'))
        report=make_report(self.db,['MCB'],'2026-10-14')
        self.assertEqual(report['excluded']['MCB'],'MARKET_CODE_CONFLICT')
        self.assertEqual(report['health']['market_code_conflicts'],1)
    def test_unmapped_code_cannot_make_symbol_fresh(self):
        self.seed('MCB',last='2026-10-09')
        self.db.execute("INSERT INTO ohlcv VALUES (?,?,?,?,?,?,?,?,?)",
                        ('2026-10-14','MCB','9999',100,110,90,100,1000,'unknown'))
        report=make_report(self.db,['MCB'],'2026-10-14')
        self.assertEqual(report['excluded']['MCB'],'STALE_CANDIDATE')
        self.assertIn('9999',report['coverage']['MCB']['unmapped_market_codes_seen'])
    def test_same_date_matching_records_not_double_counted(self):
        self.seed()
        self.db.execute("INSERT INTO ohlcv VALUES (?,?,?,?,?,?,?,?,?)",
                        ('2026-10-14','MCB','0807',100,110,90,100,1000,'official'))
        self.assertEqual(history_count(self.db,'MCB','2026-10-14'),MIN_SESSIONS)
if __name__=='__main__':
    unittest.main()
