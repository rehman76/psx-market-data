import unittest
from scripts.research_coordinator import coordinate, official_company_url

class ResearchCoordinatorTests(unittest.TestCase):
    def test_company_page(self):
        self.assertEqual(official_company_url('MCB'), 'https://dps.psx.com.pk/company/MCB')
        for value in ('mcB','../ABC','MCB?x=1',''):
            with self.assertRaises(ValueError):
                official_company_url(value)

    def test_research_and_persistence(self):
        symbols=['MCB','PSO','TRG']
        day='2026-10-15'
        d={'completed_session_cutoff':day,'symbols_requested':symbols,'candidates':[
            {'symbol':s,'date':day,'close':p,'rank_score':score} for s,p,score in [('MCB',370,2),('PSO',360,9),('TRG',55,6)]]}
        t={'completed_session_cutoff':day,'reviews':[{'symbol':s,'status':'TECHNICAL_REVIEW_READY','technical':{}} for s in symbols]}
        v={'completed_session_cutoff':day,'reviews':[{'symbol':s,'independently_verified':False} for s in symbols]}
        f={'completed_session_cutoff':day,'reviews':[{'symbol':s,'fundamentals_verified':False} for s in symbols]}
        pdf={'reviews':[{'symbol':s,'issuer_authenticity_verified':False} for s in symbols]}
        report,prior=coordinate(d,t,v,f,pdf)
        self.assertEqual(report['watch_shortlist'],['PSO','TRG'])
        self.assertEqual(report['health']['trade_eligible'],0)
        self.assertEqual(report['stocks'][1]['psx_page_validation'],'LINK_ONLY_NOT_FETCHED_OR_ATTESTED')
        _,again=coordinate(d,t,v,f,pdf,prior)
        self.assertEqual(again['entries'][1]['observations'],1)
        t['completed_session_cutoff']='2026-10-14'
        with self.assertRaises(ValueError):coordinate(d,t,v,f,pdf)

if __name__=='__main__': unittest.main()
