import sqlite3
import unittest
from datetime import date, timedelta
from scripts.discover_candidates import make_report, screen, weekday_lag, MIN_SESSIONS

class CandidateFreshnessTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:')
        self.db.execute("""CREATE TABLE ohlcv(
          trade_date TEXT, symbol TEXT, market_code TEXT, open REAL,
          high REAL, low REAL, close REAL, volume INTEGER, source_file TEXT)""")
    def tearDown(self):
        self.db.close()
    def seed(self, symbol, last):
        end=date.fromisoformat(last)
        for i in range(MIN_SESSIONS):
            d=(end-timedelta(days=MIN_SESSIONS-i-1)).isoformat()
            self.db.execute("INSERT INTO ohlcv VALUES (?,?,?,?,?,?,?,?,?)",
                            (d,symbol,'REG',100,110,90,100,1000,'fixture'))
    def test_weekend_not_counted(self):
        self.assertEqual(weekday_lag('2026-10-09','2026-10-12'),1)
        self.assertEqual(weekday_lag('2026-10-14','2026-10-14'),0)
    def test_old_history_is_stale_not_ranked(self):
        self.seed('OLD','2026-10-09')
        report=make_report(self.db,['OLD'],'2026-10-14')
        self.assertEqual(report['health']['fresh_candidates'],0)
        self.assertEqual(report['health']['stale'],1)
        self.assertEqual(report['excluded']['OLD'],'STALE_CANDIDATE')
        self.assertEqual(report['stale_watchlist'][0]['symbol'],'OLD')
    def test_fresh_history_can_be_research_candidate(self):
        self.seed('NEW','2026-10-14')
        report=make_report(self.db,['NEW'],'2026-10-14')
        self.assertEqual(report['health']['fresh_candidates'],1)
        self.assertEqual(report['candidates'][0]['decision'],'WATCH_RESEARCH_ONLY')
    def test_intraday_candle_does_not_make_stale_history_fresh(self):
        self.seed('OLD','2026-10-09')
        self.db.execute("INSERT INTO ohlcv VALUES (?,?,?,?,?,?,?,?)",
                        ('2026-10-15','OLD','REG',100,500,90,450,999999,'intraday'))
        report=make_report(self.db,['OLD'],'2026-10-14')
        self.assertEqual(report['health']['stale'],1)
if __name__=='__main__':
    unittest.main()
