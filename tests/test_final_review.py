import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from final_review import finalize

CARD = {"id": "sample", "title": "Learning", "body": "A short card",
        "category": "Philosophy", "attribution": "MyDayCoach",
        "source": "https://example.org/evidence", "takeaway": "Try again.",
        "detail": "The earlier draft."}
SOURCE = [{"title": "Evidence", "text": "The supporting record.", "url": CARD["source"]}]

class FinalReviewTests(unittest.TestCase):
    @patch("final_review.research", return_value=(SOURCE, []))
    @patch("final_review.compose")
    @patch("final_review.editorial_review")
    def test_three_reviews_use_previous_draft_and_keep_last_with_note(self, review, compose, research):
        compose.side_effect = [{"detail": "First.", "changes": "First edit"},
                               {"detail": "Second.", "changes": "Second edit"},
                               {"detail": "Last.", "changes": "Last edit"}]
        review.return_value = {"approved": False, "grounded": True, "complete": True,
                               "reasonCode": "EDITORIAL_QUALITY_FAILED",
                               "issues": ["Closing needs polish"]}
        item, audit = finalize(CARD)
        self.assertEqual(3, audit["completedReviews"])
        self.assertTrue(audit["eligible"])
        self.assertEqual("review_failed", item["reviewStatus"])
        self.assertEqual("ready_for_publish", item["status"])
        self.assertTrue(item["detail"].startswith("Review failed [EDITORIAL_QUALITY_FAILED]"))
        self.assertTrue(item["detail"].endswith("Last."))
        self.assertEqual(("First.", ["Closing needs polish"]), compose.call_args_list[1].args[1:3])

    @patch("final_review.research", return_value=([], ["Source HTTP 403"]))
    def test_source_block_is_terminal_and_not_feed_eligible(self, research):
        item, audit = finalize(CARD)
        self.assertEqual("review_failed", item["status"])
        self.assertEqual("SOURCE_ACCESS_DENIED", audit["reasonCode"])
        self.assertEqual(0, audit["completedReviews"])
        self.assertFalse(audit["eligible"])

if __name__ == "__main__":
    unittest.main()
