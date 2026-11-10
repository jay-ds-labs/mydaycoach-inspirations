import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from finalize_refresh import summarize

class RefreshStatusTests(unittest.TestCase):
    def test_15_approved_items(self):
        ids=["item-"+str(i) for i in range(15)]
        result=summarize({"generatedIds":ids},
            {"items":{id:{"state":"approved"} for id in ids}},
            {"items":[{"id":id} for id in ids]})
        self.assertEqual(result["approved"],15)
        self.assertEqual(result["state"],"awaiting_editorial_approval")
    def test_unapproved_items_remain_incomplete(self):
        ids=["a","b"]
        result=summarize({"generatedIds":ids},
            {"items":{"a":{"state":"approved"},"b":{"state":"review_pending_retry"}}},
            {"items":[{"id":"a"},{"id":"b"}]})
        self.assertEqual(result["state"],"review_incomplete")
        self.assertEqual(result["reviewOutcomes"]["review_pending_retry"],1)
    def test_missing_generated_item_is_error(self):
        with self.assertRaises(ValueError):
            summarize({"generatedIds":["lost"]},{"items":{}},{"items":[]})

if __name__=="__main__":
    unittest.main()
