import unittest
from scripts.official_source_summary import render, safe_error

class OfficialSourceSummaryTests(unittest.TestCase):
    def test_404_explicit_and_not_verification(self):
        output=render({'download_attempted':True,'download_succeeded':False,
          'download_error':'HTTP_STATUS_404','download_session_date':'2026-10-15',
          'data_freshness':{'fresh':True}})
        self.assertIn('HTTP_STATUS_404',output)
        self.assertIn('NOT ESTABLISHED',output)
        self.assertIn('FRESH',output)
    def test_secret_and_untrusted_error_not_leaked(self):
        secret='https://dps.psx.com.pk/download/?token=secret'
        output=render({'download_attempted':True,'download_succeeded':False,
                       'download_error':secret,
                       'download_session_date':'<secret>'})
        self.assertNotIn('token=secret',output)
        self.assertNotIn('<secret>',output)
        self.assertIn('UNCLASSIFIED_FAILURE',output)
    def test_accepted_format_is_not_verified(self):
        output=render({'download_attempted':True,'download_succeeded':True,
                       'data_freshness':{'fresh':False}})
        self.assertIn('FILE_FORMAT_ACCEPTED_NOT_AUTHENTICATED',output)
        self.assertIn('NOT ESTABLISHED',output)
    def test_no_download_configured(self):
        output=render({'download_attempted':False,'download_succeeded':False})
        self.assertIn('NOT_CONFIGURED',output)
        self.assertEqual(safe_error('HTTP_STATUS_403'),'HTTP_STATUS_403')
if __name__=='__main__':
    unittest.main()
