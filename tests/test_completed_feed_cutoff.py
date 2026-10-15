import sqlite3
import unittest
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from psx_analysis_feed import build, read_candles

class CompletedFeedTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:')
        self.db.execute('CREATE TABLE ohlcv (symbol TEXT,trade_date TEXT,market_code TEXT,open REAL,high REAL,low REAL,close REAL,volume INTEGER,source_file TEXT)')
        for i in range(60):
            from datetime import date,timedelta
            d=(date(2026,7,1)+timedelta(days=i)).isoformat()
            self.db.execute('INSERT INTO ohlcv VALUES (?,?,?,?,?,?,?,?,?)',('MCB',d,'REG',100,105,95,100,1000,'test'))
        self.db.execute('INSERT INTO ohlcv VALUES (?,?,?,?,?,?,?,?,?)',('MCB','2026-10-15','REG',100,500,95,450,999999,'intraday'))
    def tearDown(self):
        self.db.close()
    def test_incomplete_candle_not_exported_or_used_in_indicators(self):
        stock=build(self.db,'MCB',300,'2026-10-14')
        self.assertLessEqual(stock['latest_trade_date'],'2026-10-14')
        self.assertEqual(stock['completed_session_cutoff'],'2026-10-14')
        self.assertEqual(stock['indicators']['sma20'],100)
        self.assertNotIn('2026-10-15',[x['date'] for x in stock['candles']])
    def test_candle_query_cutoff(self):
        rows,_,_=read_candles(self.db,'MCB',300,'2026-10-14')
        self.assertTrue(all(r['date']<='2026-10-14' for r in rows))
if __name__=='__main__':
    unittest.main()
