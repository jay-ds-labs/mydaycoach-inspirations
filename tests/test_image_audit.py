import unittest
from scripts.image_audit import verify

class ImageAuditTests(unittest.TestCase):
    def test_cc_by_metadata_passes_only_preliminary_gate(self):
        image={"title":"File:Example.jpg","imageinfo":[{"mime":"image/jpeg",
          "thumburl":"https://upload.wikimedia.org/example.jpg",
          "descriptionurl":"https://commons.wikimedia.org/wiki/File:Example.jpg",
          "extmetadata":{"LicenseShortName":{"value":"CC BY 4.0"},
           "Artist":{"value":"Example Creator"},"LicenseUrl":{"value":"https://creativecommons.org/licenses/by/4.0/"}}}]}
        result=verify(image)
        self.assertEqual(result["state"],"license_metadata_pass")
        self.assertTrue(result["requiresVisualReview"])
        self.assertEqual(result["creator"],"Example Creator")

    def test_unlicensed_image_is_rejected(self):
        image={"title":"File:Unlicensed.jpg","imageinfo":[{"mime":"image/jpeg",
          "thumburl":"https://example.org/image.jpg",
          "descriptionurl":"https://commons.wikimedia.org/wiki/File:Unlicensed.jpg",
          "extmetadata":{}}]}
        self.assertEqual(verify(image)["state"],"needs_manual_license_review")

    def test_noncommercial_restriction_is_rejected(self):
        image={"title":"File:Restricted.jpg","imageinfo":[{"mime":"image/jpeg",
          "thumburl":"https://example.org/image.jpg",
          "descriptionurl":"https://commons.wikimedia.org/wiki/File:Restricted.jpg",
          "extmetadata":{"LicenseShortName":{"value":"CC BY 4.0"},
           "UsageTerms":{"value":"Non-commercial use only"}}}]}
        self.assertEqual(verify(image)["state"],"needs_manual_license_review")

if __name__=="__main__":
    unittest.main()
