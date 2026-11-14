import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from recover_latest_batch import recover
from generate_batch import generate
from final_review import ReviewError
class RecoveryTests(unittest.TestCase):
    @patch('recover_latest_batch.finalize')
    def test_only_failed_slot_changes_and_rerun_does_not_duplicate(self,finalize):
        accepted={'id':'good','title':'Accepted','detail':'Keep original.'}
        failed={'id':'failed','title':'Repair','category':'Stories'}
        library={'items':[copy.deepcopy(accepted)]}
        reviews={'items':{'failed':{'finalVersion':failed,'reasonCode':'UNSUPPORTED_QUOTE','completedReviews':3}}}
        status={'outcomes':[{'id':'good','eligible':True,'state':'approved','category':'Stories'}, {'id':'failed','eligible':False,'state':'review_failed','category':'Stories'}]}
        finalize.return_value=({**failed,'detail':'Corrected full article.'},{'eligible':True,'state':'approved','reasonCode':'','reason':'','completedReviews':1})
        recover(library,reviews,status);recover(library,reviews,status)
        self.assertEqual([accepted,{**failed,'detail':'Corrected full article.'}],library['items'])
        self.assertEqual(1,finalize.call_count);self.assertEqual(1,len(reviews['items']['failed']['previousAudits']))
        self.assertEqual(2,status['approved']);self.assertEqual('completed',status['state'])
    @patch('recover_latest_batch.generate',return_value={'id':'replacement','title':'New card','category':'Stories'})
    @patch('recover_latest_batch.finalize')
    def test_missing_card_slot_is_regenerated_without_losing_other_outcomes(self,finalize,generate):
        finalize.return_value=({'id':'replacement','title':'New card'},{'eligible':True,'state':'approved','reasonCode':'','reason':'','completedReviews':1})
        library={'items':[]};reviews={'items':{}};status={'outcomes':[{'category':'Stories','eligible':False,'state':'review_failed','reasonCode':'INVALID_CARD'}]}
        recover(library,reviews,status);self.assertEqual('replacement',library['items'][0]['id']);self.assertEqual(1,status['approved'])
    @patch('generate_batch._generate')
    def test_malformed_card_is_repaired_with_bounded_retries(self,generate_once):
        generate_once.side_effect=[ReviewError('INVALID_CARD','Missing field'),{'id':'valid'}]
        self.assertEqual({'id':'valid'},generate('Stories',[]));self.assertEqual(2,generate_once.call_count)
    @patch('generate_batch._generate',side_effect=ReviewError('INVALID_CARD','Missing field'))
    def test_card_repair_stops_after_three_attempts(self,generate_once):
        with self.assertRaises(ReviewError):generate('Stories',[])
        self.assertEqual(3,generate_once.call_count)
