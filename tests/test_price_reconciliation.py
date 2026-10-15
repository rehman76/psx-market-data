import unittest
from scripts.price_reconciliation import reconcile

def fixtures(day='2026-10-15'):
    d={'completed_session_cutoff':day,'symbols_requested':['MCB','SYS'],
       'candidates':[{'symbol':'MCB','date':day,'close':373.90},
                     {'symbol':'SYS','date':day,'close':115.96}]}
    t={'completed_session_cutoff':day,'reviews':[]}
    s={'completed_session_cutoff':day,'reviews':[
        {'symbol':'MCB','independently_verified':False},
        {'symbol':'SYS','independently_verified':False}]}
    confirmations={'provenance':'USER_CONFIRMED_IN_CHAT_NOT_OFFICIAL','observations':[
        {'symbol':'MCB','trade_date':'2026-10-15','price_pkr':371.08,
         'price_type':'USER_CONFIRMED_SESSION_PRICE',
         'confirmation_source':'user_chat_confirmation','independently_verified':False},
        {'symbol':'SYS','trade_date':'2026-10-15','price_pkr':115.96,
         'price_type':'USER_CONFIRMED_SESSION_PRICE',
         'confirmation_source':'user_chat_confirmation','independently_verified':False}]}
    return d,t,s,confirmations

class PriceReconciliationTests(unittest.TestCase):
    def test_discrepancy_and_match_but_no_official(self):
        r=reconcile(*fixtures())
        self.assertEqual(r['health']['same_session_discrepancies'],1)
        self.assertEqual(r['health']['matched_unattested'],1)
        self.assertEqual(r['prices'][0]['research_minus_user_pkr'],2.82)
        self.assertEqual(r['prices'][1]['reconciliation_status'],'MATCHED_USER_CONFIRMATION_UNATTESTED')
        self.assertIsNone(r['prices'][0]['official_psx']['price_pkr'])
        self.assertEqual(r['health']['trade_eligible'],0)

    def test_future_session_must_not_reuse_past_confirmation(self):
        d,t,s,c=fixtures('2026-10-16')
        r=reconcile(d,t,s,c)
        self.assertEqual(r['prices'][0]['reconciliation_status'],'DIFFERENT_SESSION_NOT_COMPARABLE')
        self.assertIsNone(r['prices'][0]['research_minus_user_pkr'])

    def test_malformed_and_duplicate_confirmation_rejected(self):
        d,t,s,c=fixtures()
        c['observations'].append(dict(c['observations'][0]))
        with self.assertRaises(ValueError):reconcile(d,t,s,c)
        c['observations'].pop()
        c['observations'][0]['independently_verified']=True
        with self.assertRaises(ValueError):reconcile(d,t,s,c)

    def test_user_confirmation_never_promotes_official(self):
        d,t,s,c=fixtures()
        s['reviews'][0]['independently_verified']=True
        r=reconcile(d,t,s,c)
        self.assertIsNone(r['prices'][0]['official_psx']['price_pkr'])
        self.assertFalse(r['prices'][0]['official_psx']['independently_verified'])
        self.assertFalse(r['prices'][0]['trade_eligible'])

    def test_source_cutoff_mismatch(self):
        d,t,s,c=fixtures()
        s['completed_session_cutoff']='2026-10-14'
        with self.assertRaises(ValueError):reconcile(d,t,s,c)

if __name__=='__main__':
    unittest.main()
