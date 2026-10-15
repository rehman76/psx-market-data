import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from psx_collector import fetch_authorized, inspect_closing_payload, OfficialDownloadError

URL='https://dps.psx.com.pk/download/closing.lis.Z?secret=TOP_SECRET'
LINE=b'14OCT2026|MCB|0807|MCB BANK|370|375|365|372|200000|369.50\n'

class Response:
    def __init__(self,data,final_url=URL):
        self.data=data
        self.final_url=final_url
    def __enter__(self): return self
    def __exit__(self,*args): return False
    def read(self,n): return self.data[:n]
    def geturl(self): return self.final_url

class ClosingPayloadDiagnosticsTest(unittest.TestCase):
    def test_real_zip_lis(self):
        buffer=io.BytesIO()
        with zipfile.ZipFile(buffer,'w') as z:
            z.writestr('closing.lis',LINE)
        self.assertEqual(inspect_closing_payload(buffer.getvalue()),'ZIP_LIS')
    def test_real_raw_lis(self):
        self.assertEqual(inspect_closing_payload(LINE),'RAW_LIS')
    def test_html_json_and_fake_pipe(self):
        for data,code in [(b'<html>no data | blocked</html>','NON_CLOSING_DOCUMENT'),
                          (b'{"error":"forbidden"}','NON_CLOSING_DOCUMENT'),
                          (b'missing|closing|data','INVALID_CLOSING_ROWS')]:
            with self.subTest(data=data), self.assertRaises(OfficialDownloadError) as cm:
                inspect_closing_payload(data)
            self.assertEqual(cm.exception.code,code)
    def test_unix_compress_is_not_zip(self):
        with self.assertRaises(OfficialDownloadError) as cm:
            inspect_closing_payload(b'\x1f\x9d' + b'fake compressed data')
        self.assertEqual(cm.exception.code,'UNSUPPORTED_UNIX_COMPRESS_Z')
    def test_rejects_cross_domain_redirect_before_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'out.lis.Z'
            with patch('psx_collector.urlopen',return_value=Response(LINE,'https://untrusted.invalid/closing')):
                with self.assertRaises(OfficialDownloadError) as cm:
                    fetch_authorized(URL,target)
            self.assertEqual(cm.exception.code,'REDIRECT_OUTSIDE_AUTHORIZED_HOST')
            self.assertFalse(target.exists())
    def test_no_credentials_in_errors_and_no_invalid_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'out.lis.Z'
            with patch('psx_collector.urlopen',return_value=Response(b'<html>please login</html>')):
                with self.assertRaises(OfficialDownloadError) as cm:
                    fetch_authorized(URL,target)
            self.assertEqual(str(cm.exception),'NON_CLOSING_DOCUMENT')
            self.assertNotIn('TOP_SECRET',str(cm.exception))
            self.assertFalse(target.exists())
    def test_valid_payload_is_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'out.lis.Z'
            with patch('psx_collector.urlopen',return_value=Response(LINE)):
                self.assertEqual(fetch_authorized(URL,target),target)
            self.assertEqual(target.read_bytes(),LINE)
    def test_reject_non_psx_host(self):
        with self.assertRaises(OfficialDownloadError) as cm:
            fetch_authorized('https://dps.psx.com.pk.evil.invalid/file',Path('/tmp/unused'))
        self.assertEqual(cm.exception.code,'SOURCE_URL_NOT_AUTHORIZED')

if __name__=='__main__':
    unittest.main()
