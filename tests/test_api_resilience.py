import sys
import unittest
import urllib.error
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from api_resilience import call_with_retry, classify_error

def http_error(code,headers=None):
    return urllib.error.HTTPError("https://api.openai.com/v1/responses",code,"test",headers or {},None)

class ApiResilienceTests(unittest.TestCase):
    def test_503_recovers_after_two_waits(self):
        calls=[];waits=[]
        def send():
            calls.append(1)
            if len(calls)<3: raise http_error(503)
            return {"ok":True}
        self.assertEqual(call_with_retry(send,sleep=waits.append),{"ok":True})
        self.assertEqual(len(calls),3)
        self.assertEqual(len(waits),2)
    def test_retry_after_header_takes_priority(self):
        calls=[];waits=[]
        def send():
            calls.append(1)
            if len(calls)==1: raise http_error(503,{"Retry-After":"7"})
            return {"ok":True}
        self.assertEqual(call_with_retry(send,sleep=waits.append),{"ok":True})
        self.assertEqual(waits,[7.0])
    def test_403_never_retried(self):
        calls=[]
        def send():
            calls.append(1)
            raise http_error(403)
        with self.assertRaises(urllib.error.HTTPError):
            call_with_retry(send,sleep=lambda _:None)
        self.assertEqual(len(calls),1)
        self.assertEqual(classify_error(http_error(403)),"REVIEW_API_FORBIDDEN")
    def test_503_exhaustion(self):
        calls=[]
        def send():
            calls.append(1)
            raise http_error(503)
        with self.assertRaises(urllib.error.HTTPError):
            call_with_retry(send,sleep=lambda _:None)
        self.assertEqual(len(calls),3)
        self.assertEqual(classify_error(http_error(503)),"REVIEW_API_UNAVAILABLE")

if __name__=="__main__": unittest.main()
