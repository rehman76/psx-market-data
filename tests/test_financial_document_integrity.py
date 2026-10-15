import hashlib
import tempfile
import unittest
from pathlib import Path
from scripts.financial_document_integrity import verify

class FinancialDocumentIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.data=b'%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n'
        self.digest=hashlib.sha256(self.data).hexdigest()
    def tearDown(self):
        self.tmp.cleanup()
    def report(self,digest=None,status='DOCUMENT_UNATTESTED'):
        return {'reviews':[{'symbol':'MCB','status':status,'report_sha256':digest or self.digest}]}
    def test_bytes_match_does_not_authenticate_issuer(self):
        (self.root/'MCB.pdf').write_bytes(self.data)
        r=verify(self.report(),self.root)
        self.assertEqual(r['reviews'][0]['status'],'DOCUMENT_BYTES_MATCH')
        self.assertTrue(r['reviews'][0]['document_bytes_verified'])
        self.assertFalse(r['reviews'][0]['issuer_authenticity_verified'])
        self.assertEqual(r['health']['trade_eligible'],0)
    def test_mismatch_and_bad_pdf(self):
        (self.root/'MCB.pdf').write_bytes(self.data)
        r=verify(self.report('f'*64),self.root)
        self.assertEqual(r['reviews'][0]['status'],'REPORT_HASH_MISMATCH')
        (self.root/'MCB.pdf').write_bytes(b'not a pdf')
        r=verify(self.report(),self.root)
        self.assertEqual(r['reviews'][0]['status'],'NOT_A_PDF')
    def test_missing_report(self):
        r=verify(self.report(),self.root)
        self.assertEqual(r['reviews'][0]['status'],'REPORT_FILE_NOT_PROVIDED')
        self.assertEqual(verify({'reviews':[{'symbol':'MCB','status':'DISCLOSURE_MISSING'}]})['health']['document_missing'],1)
    def test_symlink_rejected(self):
        external=self.root/'outside.pdf'
        external.write_bytes(self.data)
        (self.root/'MCB.pdf').symlink_to(external)
        with self.assertRaises(ValueError):
            verify(self.report(),self.root)
if __name__=='__main__':
    unittest.main()
