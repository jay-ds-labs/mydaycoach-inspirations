import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from publication_gate import eligible

class PublicationGateTests(unittest.TestCase):
    def setUp(self):
        self.item={"id":"test","detail":"word "*700,"reviewStatus":"approved"}
        self.review={"state":"approved","reviewedTextMatchesSaved":True}
        self.image={"candidates":[],"selected":None}

    def test_review_approved_without_image(self):
        self.assertTrue(eligible(self.item,self.review,self.image)["eligible"])
        self.assertTrue(eligible(self.item,self.review,self.image)["publishWithoutImage"])

    def test_review_failed_is_publishable(self):
        self.item["reviewStatus"]="review_failed"
        self.review={"state":"review_failed","reviewFailureSummary":"Unsupported chronology"}
        result=eligible(self.item,self.review,self.image)
        self.assertTrue(result["eligible"])
        self.assertEqual(result["reviewFailureSummary"],"Unsupported chronology")

    def test_incomplete_story_is_blocked(self):
        self.item["detail"]="short"
        self.assertFalse(eligible(self.item,self.review,self.image)["eligible"])

    def test_missing_review_cycle_is_blocked(self):
        self.item["reviewStatus"]="not_reviewed"
        self.assertFalse(eligible(self.item,{},self.image)["eligible"])

    def test_unapproved_image_never_displayed(self):
        self.image["selected"]={"fileTitle":"File:X.jpg","descriptionUrl":"https://commons.wikimedia.org/wiki/File:X.jpg"}
        result=eligible(self.item,self.review,self.image)
        self.assertTrue(result["eligible"])
        self.assertFalse(result["imageReady"])

if __name__=="__main__":
    unittest.main()
