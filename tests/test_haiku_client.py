import io
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import haiku_client as client
import audit_images

class HaikuClientTests(unittest.TestCase):
    def test_no_model_override_or_fallback(self):
        with self.assertRaisesRegex(client.ModelError,'Only claude-haiku-5-5'):
            client.request_json('Hello',model='different-model')
    def test_missing_connection_is_explicit(self):
        with patch.dict(os.environ,{},clear=True),self.assertRaises(client.ModelError):
            client.request_json('Hello')
    def test_json_fences_and_prose_are_accepted_without_fabrication(self):
        self.assertEqual(client.parse_json('Here:\n```json\n{"detail":"A {valid} response"}\n```'),{'detail':'A {valid} response'})
        with self.assertRaises(client.ModelError):client.parse_json('{"detail":')
    def test_workflow_uses_access_code_and_worker_not_private_model_key(self):
        class Opener:
            def open(self,req,timeout):
                self.req=req
                return io.BytesIO(json.dumps({'model':client.MODEL,'text':'{"approved":true}'}).encode())
        opener=Opener()
        with patch.dict(os.environ,{'INSPIRE_WORKER_URL':'https://inspire.example','INSPIRE_WORKER_TOKEN':'private-access-token-1234'},clear=True),patch('urllib.request.build_opener',return_value=opener):
            self.assertEqual(client.request_json('Review'),{'approved':True})
        self.assertEqual(opener.req.full_url,'https://inspire.example/ai/messages')
        self.assertEqual(opener.req.get_header('Authorization'),'Bearer private-access-token-1234')
        self.assertEqual(json.loads(opener.req.data),{'prompt':'Review'})
        self.assertEqual(opener.req.get_header('User-agent'),'MyDayCoach-Inspiration/2.0')
        self.assertEqual(opener.req.get_header('Accept'),'application/json')
    def test_visual_check_uses_same_haiku_client(self):
        with patch('audit_images.haiku_configured',return_value=True),patch('audit_images.haiku_json',return_value={'relevant':True,'confidence':'high'}) as call:
            result=audit_images.visual_check({'title':'A lesson'},{'state':'license_metadata_pass','imageUrl':'https://upload.wikimedia.org/a.jpg'})
            self.assertEqual(result['state'],'relevant_candidate')
            self.assertEqual(call.call_args.kwargs['image_url'],'https://upload.wikimedia.org/a.jpg')
