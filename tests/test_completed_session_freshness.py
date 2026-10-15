import sqlite3
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
from scripts.freshness_core import assess

class CompletedSessionTests(unittest.TestCase):
    def test_intraday_record_does_not_invalidate_yesterday(self):
        with sqlite3.connect(':memory:') as db:
            db.execute('CREATE TABLE ohlcv(symbol TEXT,trade_date TEXT,market_code TEXT,open REAL,high REAL,low REAL,close REAL,volume INTEGER)')
            for day in ('2026-10-14','2026-10-15'):
                db.execute('INSERT INTO ohlcv VALUES (?,?,?,?,?,?,?,?)',('MCB',day,'REG',10,11,9,10,100))
            result = assess(db,['MCB'],min_sessions=1,now=datetime(2026,10,15,13,22,tzinfo=ZoneInfo('Asia/Karachi')))
            self.assertTrue(result['fresh'])
            self.assertEqual(result['stocks']['MCB']['latest'],'2026-10-14')
            self.assertEqual(result['stocks']['MCB']['excluded_uncompleted_dates'],1)
    def test_no_completed_session_still_fails(self):
        with sqlite3.connect(':memory:') as db:
            db.execute('CREATE TABLE ohlcv(symbol TEXT,trade_date TEXT,market_code TEXT,open REAL,high REAL,low REAL,close REAL,volume INTEGER)')
            db.execute('INSERT INTO ohlcv VALUES (?,?,?,?,?,?,?,?)',('MCB','2026-10-15','REG',10,11,9,10,100))
            result=assess(db,['MCB'],min_sessions=1,now=datetime(2026,10,15,13,22,tzinfo=ZoneInfo('Asia/Karachi')))
            self.assertFalse(result['fresh'])
            self.assertEqual(result['stocks']['MCB']['status'],'missing')
if __name__ == '__main__':
    unittest.main()
