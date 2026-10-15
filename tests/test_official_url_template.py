import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
from scripts.official_url_template import resolve_download_url

ROOT='https://dps.psx.com.pk/download/mkt_summary/'
PKT=ZoneInfo('Asia/Karachi')

class OfficialURLTemplateTests(unittest.TestCase):
    def test_pre_close_uses_last_completed_weekday(self):
        at=datetime(2026,10,15,16,15,tzinfo=PKT)
        self.assertEqual(resolve_download_url(ROOT+'YYYY-MM-dd',at),
                         (ROOT+'2026-10-14','2026-10-14'))
    def test_after_close_uses_today(self):
        at=datetime(2026,10,15,17,1,tzinfo=PKT)
        self.assertEqual(resolve_download_url(ROOT+'YYYY-MM-dd',at),
                         (ROOT+'2026-10-15','2026-10-15'))
    def test_weekend_and_monday_before_close(self):
        for dt in (datetime(2026,10,17,18,tzinfo=PKT),
                   datetime(2026,10,19,9,tzinfo=PKT)):
            with self.subTest(dt=dt):
                self.assertEqual(resolve_download_url(ROOT+'YYYY-MM-DD',dt)[1],'2026-10-16')
    def test_passthrough_static_url(self):
        url=ROOT+'2026-10-14'
        self.assertEqual(resolve_download_url(url,datetime(2026,10,15,9,tzinfo=PKT)),(url,None))
    def test_query_not_replaced(self):
        at=datetime(2026,10,15,18,tzinfo=PKT)
        url=ROOT+'YYYY-MM-dd?private=YYYY-MM-dd'
        self.assertEqual(resolve_download_url(url,at),(ROOT+'2026-10-15?private=YYYY-MM-dd','2026-10-15'))
    def test_rejects_bad_hosts_and_bad_placeholders(self):
        for url in ('https://dps.psx.com.pk.evil.invalid/download/YYYY-MM-dd',
                    'http://dps.psx.com.pk/download/YYYY-MM-dd',
                    ROOT+'YYYY/MM/dd',ROOT+'YYYY-MM-dd/YYYY-MM-dd',
                    ROOT+'YYYY-MM-dd#fragment'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                resolve_download_url(url)
if __name__=='__main__':
    unittest.main()
