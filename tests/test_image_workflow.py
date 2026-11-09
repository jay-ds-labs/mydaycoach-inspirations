import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import audit_images

class ImageWorkflowTests(unittest.TestCase):
    def test_pilot_subject_search(self):
        self.assertIn("Marie Curie",audit_images.subject_queries({"id":"curie-nobel","title":"Persistence in research","attribution":"Nobel Prize"})[0])
        self.assertIn("Wright",audit_images.subject_queries({"id":"wright-flight","title":"Experiment and iteration"})[0])
        self.assertNotIn("Smithsonian",audit_images.subject_queries({"id":"wright-flight","title":"Experiment and iteration"})[0])

    def test_license_metadata_pass_is_not_publication(self):
        page={"title":"File:Curie.jpg","imageinfo":[{"mime":"image/jpeg",
          "thumburl":"https://upload.wikimedia.org/curie.jpg",
          "descriptionurl":"https://commons.wikimedia.org/wiki/File:Curie.jpg",
          "extmetadata":{"LicenseShortName":{"value":"CC BY 4.0"},
           "Artist":{"value":"Photographer"}}}]}
        result=audit_images.verify(page)
        self.assertEqual(result["state"],"license_metadata_pass")
        self.assertTrue(result["requiresVisualReview"])

    def test_missing_license_stays_blocked(self):
        page={"title":"File:Unknown.jpg","imageinfo":[{"mime":"image/jpeg",
          "url":"https://upload.wikimedia.org/unknown.jpg",
          "descriptionurl":"https://commons.wikimedia.org/wiki/File:Unknown.jpg",
          "extmetadata":{}}]}
        self.assertEqual(audit_images.verify(page)["state"],"needs_manual_license_review")

    def test_audit_no_article_mutation(self):
        original=audit_images.search
        audit_images.search=lambda query: []
        try:
            item={"id":"curie-nobel","title":"Persistence in research","detail":"Keep this text unchanged"}
            before=dict(item)
            images,report=audit_images.audit([item])
            self.assertEqual(item,before)
            self.assertEqual(report["processed"],1)
            self.assertEqual(images["items"]["curie-nobel"]["state"],"awaiting_visual_and_license_review")
        finally:
            audit_images.search=original

if __name__=="__main__":
    unittest.main()
