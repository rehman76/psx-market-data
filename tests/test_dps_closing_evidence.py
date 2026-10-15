import tempfile
import unittest
import zipfile
from pathlib import Path
from scripts.dps_closing_evidence import extract

class AuthorizedClosingEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/'official.lis.Z'
    def tearDown(self):
        self.tmp.cleanup()
    def write(self,lines):
        with zipfile.ZipFile(self.path,'w') as z:
            z.writestr('market.lis','\n'.join(lines).encode())
    def line(self,code='0807',close='372.00',symbol='MCB',day='14OCT2026'):
        return '|'.join([day,symbol,code,'TEST CO','370','375','365',close,'200000','370'])
    def test_extracts_recent_official_code_with_hash(self):
        self.write([self.line()])
        evidence, manifest=extract(self.path,'https://dps.psx.com.pk/closing/file?token=private',
                                  ['MCB'],'2026-10-14')
        self.assertEqual(len(evidence),1)
        self.assertEqual(evidence[0]['volume'],200000)
        self.assertEqual(evidence[0]['source_url'],'https://dps.psx.com.pk/closing/file')
        self.assertEqual(len(manifest['file_sha256']),64)
        self.assertNotIn('private',str(manifest))
        self.assertTrue(manifest['same_source_import_self_comparison_possible'])
    def test_conflicting_market_codes_rejected(self):
        self.write([self.line('REG'),self.line('0807','373.00')])
        with self.assertRaisesRegex(ValueError,'conflicting'):
            extract(self.path,'https://dps.psx.com.pk/closing/file',['MCB'],'2026-10-14')
    def test_rejects_invalid_host(self):
        self.write([self.line()])
        with self.assertRaises(ValueError):
            extract(self.path,'https://dps.psx.com.pk.evil.test/x',['MCB'],'2026-10-14')
    def test_stale_and_future_not_emitted(self):
        self.write([self.line(day='09OCT2026'),self.line(day='15OCT2026')])
        evidence,_=extract(self.path,'https://dps.psx.com.pk/closing/file',['MCB'],'2026-10-14')
        self.assertEqual(evidence,[])
    def test_rejects_unparsed_rows(self):
        self.write([self.line(),'not a candle'])
        with self.assertRaisesRegex(ValueError,'rejected'):
            extract(self.path,'https://dps.psx.com.pk/closing/file',['MCB'],'2026-10-14')
    def test_observed_code_still_unattested(self):
        self.write([self.line(code='0839',symbol='IMAGE')])
        evidence,manifest=extract(self.path,'https://dps.psx.com.pk/closing/file',['IMAGE'],'2026-10-14')
        self.assertEqual(evidence[0]['close'],372)
        self.assertTrue(manifest['evidence_is_not_independently_authenticated'])
if __name__=='__main__':
    unittest.main()
