import sqlite3
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
from scripts.freshness_core import assess, expected_weekday


class FreshnessTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.execute('''CREATE TABLE ohlcv (trade_date TEXT, symbol TEXT, market_code TEXT,
                         open REAL, high REAL, low REAL, close REAL, volume INTEGER)''')
        self.now = datetime(2026, 10, 14, 19, 0, tzinfo=ZoneInfo('Asia/Karachi'))

    def tearDown(self):
        self.db.close()

    def add(self, symbol, date='2026-10-14', count=1):
        for i in range(count):
            self.db.execute('INSERT INTO ohlcv VALUES (?,?,?,?,?,?,?,?)',
                            (date if i == 0 else '2026-10-13', symbol, 'REG', 10, 11, 9, 10, 100))

    def test_current_day_fresh_even_if_download_failed(self):
        self.add('MCB')
        s = assess(self.db, ['MCB'], 1, 1, now=self.now)
        self.assertTrue(s['fresh'])

    def test_missing_stock_blocks_freshness(self):
        self.add('MCB')
        s = assess(self.db, ['MCB', 'SYS'], 1, 1, now=self.now)
        self.assertFalse(s['fresh'])
        self.assertEqual(s['stocks']['SYS']['status'], 'missing')

    def test_future_dated_not_fresh(self):
        self.add('MCB', '2026-10-15')
        self.assertEqual(assess(self.db, ['MCB'], 1, 1, now=self.now)['stocks']['MCB']['status'], 'future_dated')

    def test_weekend_uses_previous_friday(self):
        saturday = datetime(2026, 10, 17, 19, 0, tzinfo=ZoneInfo('Asia/Karachi'))
        self.assertEqual(expected_weekday(saturday).isoformat(), '2026-10-16')

    def test_insufficient_history(self):
        self.add('MCB')
        self.assertEqual(assess(self.db, ['MCB'], 50, 1, now=self.now)['stocks']['MCB']['status'], 'insufficient_history')


if __name__ == '__main__':
    unittest.main()
