import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from publication_gate import eligible

class PublicationGateTests(unittest.TestCase):
    def setUp(self):
        self.item={"id":"test","detail":"word "*700}
        self.review={"state":"approved","reviewedTextMatchesSaved":True,"sourceAccessible":True,
            "sourceUrls":["https://example.org/article"],"editorialSignoff":True}
        self.candidate={"fileTitle":"File:Test.jpg","descriptionUrl":"https://commons.wikimedia.org/wiki/File:Test.jpg",
            "state":"license_metadata_pass","visualCheck":{"state":"relevant_candidate"},
            "attribution":"Creator","license":"cc-by-4.0"}
        self.image={"candidates":[self.candidate],"selected":{"fileTitle":"File:Test.jpg",
            "descriptionUrl":self.candidate["descriptionUrl"],"editorialApproved":True,"rightsApproved":True}}
    def test_all_gates_pass(self):
        self.assertTrue(eligible(self.item,self.review,self.image)["eligible"])
    def test_no_approval(self):
        self.image["selected"]["rightsApproved"]=False
        self.assertFalse(eligible(self.item,self.review,self.image)["eligible"])
    def test_unverified_image(self):
        self.image["candidates"][0]["state"]="needs_manual_license_review"
        self.assertFalse(eligible(self.item,self.review,self.image)["eligible"])
    def test_mismatched_review(self):
        self.review["reviewedTextMatchesSaved"]=False
        self.assertFalse(eligible(self.item,self.review,self.image)["eligible"])
    def test_missing_image(self):
        self.image["selected"]=None
        self.assertFalse(eligible(self.item,self.review,self.image)["eligible"])

if __name__=="__main__":
    unittest.main()
