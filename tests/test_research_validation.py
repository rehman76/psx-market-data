import sqlite3
import unittest
from datetime import date, timedelta
from scripts.research_validation import evaluate, build, MIN_TECH_SESSIONS

class ResearchValidationTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:')
        self.db.execute("""CREATE TABLE ohlcv (
          trade_date TEXT, symbol TEXT, market_code TEXT, open REAL, high REAL,
          low REAL, close REAL, volume INTEGER, source_file TEXT)""")
    def tearDown(self):
        self.db.close()
    def seed(self,symbol='IMAGE',count=MIN_TECH_SESSIONS,last='2026-10-14',code='0839'):
        end=date.fromisoformat(last)
        for i in range(count):
            day=(end-timedelta(days=count-i-1)).isoformat()
            self.db.execute("INSERT INTO ohlcv VALUES (?,?,?,?,?,?,?,?,?)",
                (day,symbol,code,100+i/100,110+i/100,90+i/100,100+i/100,1000,'fixture'))
    def test_ready_technicals_not_trade_eligible(self):
        self.seed()
        result=evaluate(self.db,'IMAGE','2026-10-14')
        self.assertEqual(result['status'],'TECHNICAL_REVIEW_READY')
        self.assertFalse(result['trade_eligible'])
        self.assertIsNotNone(result['technical']['sma200'])
        self.assertIn('PSX_DPS_VERIFICATION_PENDING',result['blocking_reasons'])
    def test_short_history_blocked(self):
        self.seed(count=90)
        result=evaluate(self.db,'IMAGE','2026-10-14')
        self.assertEqual(result['status'],'BLOCKED')
        self.assertEqual(result['technical'],{})
    def test_stale_blocked(self):
        self.seed(last='2026-10-09')
        result=evaluate(self.db,'IMAGE','2026-10-14')
        self.assertIn('STALE_CANDIDATE',result['blocking_reasons'])
    def test_market_code_conflict_blocked(self):
        self.seed('MCB',code='REG')
        self.db.execute("INSERT INTO ohlcv VALUES (?,?,?,?,?,?,?,?,?)",
          ('2026-10-14','MCB','0807',100,110,90,105,1000,'official'))
        result=evaluate(self.db,'MCB','2026-10-14')
        self.assertIn('MARKET_CODE_CONFLICT',result['blocking_reasons'])
    def test_no_buy_signals(self):
        self.seed()
        result=build(self.db,['IMAGE'],'2026-10-14')
        self.assertEqual(result['health']['trade_eligible'],0)
        self.assertEqual(result['reviews'][0]['decision'],'RESEARCH_ONLY')
if __name__=='__main__':
    unittest.main()
