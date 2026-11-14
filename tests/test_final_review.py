import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from final_review import finalize, editorial_review, ReviewError
CARD={'id':'sample','title':'Learning','body':'A short card','category':'Philosophy','attribution':'MyDayCoach','source':'https://example.org/evidence','takeaway':'Old takeaway','detail':'Earlier draft.'}
SOURCE=[{'title':'Evidence','text':'Supporting record.','url':CARD['source']}]
def verdict(blockers=(),warnings=()):
    return dict(approved=not blockers,complete=not any(b['code']=='INCOMPLETE_ARTICLE' for b in blockers),grounded=not any(b['code']!='INCOMPLETE_ARTICLE' for b in blockers),issues=[b['reason'] for b in blockers],blockers=list(blockers),warnings=list(warnings),researchQuery='',reasonCode=blockers[0]['code'] if blockers else '',failureReason=blockers[0]['reason'] if blockers else '')
class FinalReviewTests(unittest.TestCase):
    @patch('final_review.request_json')
    def test_minor_editorial_objections_are_notes_not_a_veto(self,request):
        request.return_value={**verdict(warnings=['Mild opening wording concern.']), 'approved':False}
        result=editorial_review(CARD,'A full, finished article.',SOURCE)
        self.assertTrue(result['approved']);self.assertEqual([],result['blockers'])
    @patch('final_review.request_json')
    def test_unexplained_doubt_without_material_blockers_is_a_note(self,request):
        request.return_value={**verdict(), 'grounded':False,'approved':False}
        result=editorial_review(CARD,'Complete account.',SOURCE)
        self.assertTrue(result['approved']);self.assertTrue(result['warnings'])
    @patch('final_review.request_json')
    def test_cut_off_source_excerpt_cannot_veto_a_finished_article(self,request):
        request.side_effect=[verdict([{'code':'INCOMPLETE_ARTICLE','reason':'Source excerpt stops mid-sentence.'}]),{'complete':True,'reason':'The actual article has a complete ending.'}]
        result=editorial_review(CARD,'A finished standalone article.',SOURCE)
        self.assertTrue(result['approved']);self.assertEqual([],result['blockers'])
    @patch('final_review.request_json')
    def test_false_quote_and_wrong_subject_remain_blockers(self,request):
        for code in ['FALSE_ATTRIBUTION','WRONG_TOPIC','MATERIAL_FACT_ERROR','INSUFFICIENT_EVIDENCE','INCOMPLETE_ARTICLE']:
            request.return_value=verdict([{'code':code,'reason':'Substantial problem.'}])
            self.assertFalse(editorial_review(CARD,'Article.',SOURCE)['approved'])
    @patch('final_review.request_json')
    def test_missing_blocker_schema_is_retried_not_accepted(self,request):
        request.return_value={'approved':True,'issues':[],'grounded':True,'complete':True}
        with self.assertRaises(ReviewError):editorial_review(CARD,'Article.',SOURCE)
    @patch('final_review.research',return_value=(SOURCE,[]))
    @patch('final_review.compose',return_value={'detail':'A finished article.','takeaway':'A corrected reflection.','source':CARD['source']})
    @patch('final_review.editorial_review',return_value=verdict(warnings=['Could polish opening.']))
    def test_card_takeaway_and_notes_are_saved_with_accepted_article(self,review,compose,research):
        item,audit=finalize(CARD,allow_card_correction=True)
        self.assertTrue(audit['eligible']);self.assertEqual(1,audit['completedReviews'])
        self.assertEqual('A corrected reflection.',item['takeaway'])
        self.assertEqual('A corrected reflection.',review.call_args.args[0]['takeaway'])
        self.assertEqual(['Could polish opening.'],item['reviewNotes']);self.assertNotIn('Review failed',item['detail'])
    @patch('final_review.research',return_value=(SOURCE,[]))
    @patch('final_review.compose')
    @patch('final_review.editorial_review')
    def test_unfinished_article_is_repaired_then_reviewed(self,review,compose,research):
        compose.side_effect=[{'detail':'A sentence that stops at'}, {'detail':'A complete account with an ending.'}]
        review.side_effect=[verdict([{'code':'INCOMPLETE_ARTICLE','reason':'Ends mid-sentence.'}]),verdict()]
        item,audit=finalize(CARD);self.assertTrue(audit['eligible']);self.assertEqual(2,audit['completedReviews'])
        self.assertIn('Ends mid-sentence.',compose.call_args.args[2]);self.assertTrue(item['detail'].endswith('ending.'))
    @patch('final_review.research',return_value=(SOURCE,[]))
    @patch('final_review.compose',return_value={'detail':'Finished but false account.'})
    @patch('final_review.editorial_review',return_value=verdict([{'code':'FALSE_ATTRIBUTION','reason':'Invented quote.'}]))
    @patch('final_review.refresh_evidence',return_value=SOURCE)
    def test_material_failure_after_three_attempts_stays_out_of_feed(self,refresh,review,compose,research):
        item,audit=finalize(CARD);self.assertEqual(3,audit['completedReviews']);self.assertFalse(audit['eligible'])
        self.assertEqual('review_failed',item['status']);self.assertIn('FALSE_ATTRIBUTION',item['detail'])
    @patch('final_review.research',return_value=([],['Source HTTP 403']))
    def test_no_evidence_does_not_publish_a_fabrication(self,research):
        item,audit=finalize(CARD);self.assertFalse(audit['eligible']);self.assertEqual(0,audit['completedReviews'])
    @patch('final_review.evidence',return_value=('A peripheral reference mentioning Hypatia.', ''))
    @patch('final_review.discover',return_value=([{'title':'Hypatia','url':'https://en.wikipedia.org/wiki/Hypatia','text':'Hypatia taught philosophy in Alexandria.'}],[]))
    def test_subject_specific_reference_becomes_primary_citation(self,discover,evidence):
        from final_review import research
        item={**CARD,'title':"Hypatia's Lamp",'attribution':'Socrates Scholasticus','source':'https://example.org/general-history'}
        records,_=research(item,[])
        self.assertEqual('https://en.wikipedia.org/wiki/Hypatia',records[0]['url'])

    @patch('final_review.evidence',return_value=('Inventors Hedy Kiesler Markey and George Antheil describe a secret communication system.', ''))
    @patch('final_review.discover',return_value=([],['Wikipedia HTTP 429']))
    def test_readable_patent_survives_name_alias_and_failed_fallback(self,discover,evidence):
        from final_review import research
        item={**CARD,'title':'Hedy Lamarr and frequency hopping','attribution':'Hedy Lamarr','source':'https://patents.google.com/patent/US2292387A/en'}
        records,_=research(item,[])
        self.assertEqual(item['source'],records[0]['url'])
