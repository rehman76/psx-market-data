import json
import sqlite3
from pathlib import Path
import tempfile
import unittest
from scripts.discover_candidates import screen

class DiscoveryTests(unittest.TestCase):
    def test_insufficient_history_is_not_actionable(self):
        with sqlite3.connect(':memory:') as conn:
            conn.execute('CREATE TABLE ohlcv(trade_date TEXT,symbol TEXT,market_code TEXT,close REAL,volume INTEGER,source_file TEXT)')
            conn.execute("INSERT INTO ohlcv VALUES ('2026-10-14','TEST','REG',12,100,'fixture')")
            result, reason = screen(conn, 'TEST')
            self.assertIsNone(result)
            self.assertEqual(reason, 'insufficient_history')

    def test_sufficient_history_is_research_only(self):
        from datetime import date, timedelta
        with sqlite3.connect(':memory:') as conn:
            conn.execute('CREATE TABLE ohlcv(trade_date TEXT,symbol TEXT,market_code TEXT,close REAL,volume INTEGER,source_file TEXT)')
            for i in range(65):
                conn.execute('INSERT INTO ohlcv VALUES (?,?,?,?,?,?)', ((date(2026,1,1)+timedelta(days=i)).isoformat(),'TEST','REG',10+i/10,1000,'fixture'))
            result, reason = screen(conn, 'TEST')
            self.assertIsNone(reason)
            self.assertEqual(result['decision'], 'WATCH_RESEARCH_ONLY')
            self.assertFalse(result['independent_official_verification'])

if __name__ == '__main__':
    unittest.main()
