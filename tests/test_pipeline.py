import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class PipelineTest(unittest.TestCase):
    def test_sample_import_and_feed(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            (target/'closing_files').mkdir()
            (target/'closing_files'/'20261012_new.lis.Z').write_bytes((ROOT/'sample'/'20261012_new.lis.Z').read_bytes())
            subprocess.run([sys.executable, str(ROOT/'scripts'/'run_pipeline.py'), '--input', str(target/'closing_files'), '--db', str(target/'state'/'db.sqlite'), '--publish', str(target/'publish')], check=True, capture_output=True, text=True)
            feed = json.loads((target/'publish'/'psx_analysis_feed.json').read_text())
            stocks = {s['symbol']:s for s in feed['stocks']}
            self.assertEqual(stocks['MCB']['latest_ohlcv']['close'], 375.08)
            self.assertEqual(stocks['SYS']['latest_ohlcv']['close'], 113.99)
            self.assertEqual(stocks['KOHE']['latest_ohlcv']['close'], 14.90)
            self.assertIsNone(stocks['MCB']['indicators']['sma50'])
            self.assertEqual(feed['collection_status']['new_download_missing'], True)

if __name__ == '__main__':
    unittest.main()
