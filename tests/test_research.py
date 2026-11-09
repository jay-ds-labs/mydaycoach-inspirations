import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from research import specific,discover,evidence_bundle

class ResearchTests(unittest.TestCase):
    def test_reject_homepage(self):
        self.assertFalse(specific("https://www.rgs.org/"))
        self.assertFalse(specific("http://example.org/story"))
        self.assertTrue(specific("https://www.nasa.gov/mission/apollo-11/"))

    def test_preserve_specific_institutional_evidence(self):
        import research
        original=research.wikipedia
        research.wikipedia=lambda query: []
        try:
            records,errors=discover({"title":"Apollo 11","attribution":"NASA"},
                "https://www.nasa.gov/mission/apollo-11/",
                fetch=lambda url: ("historical evidence "*40,""))
            self.assertEqual(len(records),1)
            self.assertIn("nasa.gov",evidence_bundle(records))
        finally:
            research.wikipedia=original

if __name__=="__main__":
    unittest.main()
