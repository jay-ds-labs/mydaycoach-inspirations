import sys
import unittest
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from research import specific,discover,evidence_bundle

class ResearchTests(unittest.TestCase):
    def test_reject_homepage(self):
        self.assertFalse(specific("https://www.rgs.org/"))
        self.assertFalse(specific("http://example.org/story"))
        self.assertTrue(specific("https://www.nasa.gov/mission/apollo-11/"))

    @patch("research.wikipedia_exact", return_value=[])
    def test_preserve_specific_institutional_evidence(self, exact):
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


    def test_relevant_passage_beyond_old_truncation_is_retained(self):
        from research import select_passages
        text=('General background. '*2500)+'Note G describes Bernoulli numbers and the Analytical Engine.'+(' More background.'*1000)
        selected=select_passages(text,'Note G Bernoulli Analytical Engine')
        self.assertIn('Note G describes Bernoulli',selected)
        self.assertLess(len(selected),15000)

    @patch('research.wikipedia_exact',return_value=[])
    @patch('research.wikipedia',return_value=[{'title':'Mythological armor','url':'https://en.wikipedia.org/wiki/Mythological_armor','text':'Armor and helmets. '*50}])
    def test_unrelated_fallback_is_discarded(self,search,exact):
        records,_=discover({'title':'Diogenes and the lamp','attribution':'Diogenes of Sinope'})
        self.assertEqual([],records)
