import sqlite3
import unittest
from datetime import date, timedelta
from scripts.discover_candidates import screen, make_report, collect_discovery, MIN_SESSIONS

class DiscoveryBackfillTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:')
        self.db.execute("""CREATE TABLE ohlcv(
            trade_date TEXT, symbol TEXT, market_code TEXT, company TEXT,
            open REAL, high REAL, low REAL, close REAL, volume INTEGER,
            previous_close REAL, source_file TEXT)""")
    def tearDown(self):
        self.db.close()
    def seed(self, symbol, count, cutoff=date(2026,10,14)):
        for i in range(count):
            d=(cutoff-timedelta(days=count-i-1)).isoformat()
            self.db.execute("INSERT INTO ohlcv VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                            (d,symbol,'REG',symbol,100,110,90,100,1000,None,'test'))
    def test_incomplete_session_excluded(self):
        self.seed('ABC',MIN_SESSIONS)
        self.db.execute("INSERT INTO ohlcv VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                        ('2026-10-15','ABC','REG','ABC',100,999,90,999,999999,None,'intraday'))
        candidate,reason=screen(self.db,'ABC',cutoff_date='2026-10-14')
        self.assertIsNone(reason)
        self.assertEqual(candidate['close'],100)
        self.assertEqual(candidate['date'],'2026-10-14')
        self.assertEqual(candidate['relative_volume'],1)
    def test_undercovered_is_data_pending(self):
        self.seed('ABC',30)
        result=make_report(self.db,['ABC'],'2026-10-14')
        self.assertEqual(result['excluded']['ABC'],'DATA_PENDING')
        self.assertEqual(result['health']['data_pending'],1)
    def test_undercovered_backfills_and_complete_symbol_incremental(self):
        self.seed('OLD',MIN_SESSIONS)
        calls=[]
        def fake_fetch(symbol,**kwargs):
            calls.append((symbol,kwargs['start'],kwargs['end']))
            return []
        report=collect_discovery(self.db,['NEW','OLD'],'2026-10-14',fetcher=fake_fetch)
        self.assertEqual(report['NEW']['mode'],'backfill')
        self.assertEqual(report['OLD']['mode'],'incremental')
        self.assertLess(calls[0][1],calls[1][1])
        self.assertEqual(report['NEW']['data_coverage'],'DATA_PENDING')
    def test_rejects_future_only_data(self):
        self.db.execute("INSERT INTO ohlcv VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                        ('2026-10-15','ABC','REG','ABC',100,110,90,100,1000,None,'intraday'))
        candidate,reason=screen(self.db,'ABC',cutoff_date='2026-10-14')
        self.assertIsNone(candidate)
        self.assertEqual(reason,'DATA_PENDING')
if __name__=='__main__':
    unittest.main()
