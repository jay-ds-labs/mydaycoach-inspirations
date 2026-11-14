"""Haiku-only client. The Anthropic key lives only in the Cloudflare Inspire Worker."""
import json
import os
import urllib.request
from urllib.parse import urlsplit

MODEL = "claude-haiku-5-5"

class ModelError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code

def configured():
    return bool(os.getenv("INSPIRE_WORKER_URL") and os.getenv("INSPIRE_WORKER_TOKEN"))

def parse_json(text):
    text = text.strip()
    try:
        value = json.loads(text)
        if isinstance(value, dict):
            return value
    except ValueError:
        pass
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text[index:])
            if isinstance(value, dict):
                return value
        except ValueError:
            continue
    raise ModelError("INVALID_MODEL_OUTPUT", "Haiku returned an unusable JSON object")

def request_json(prompt, model=MODEL, image_url=None):
    if model != MODEL:
        raise ModelError("WRONG_MODEL", "Only claude-haiku-5-5 is permitted")
    base = os.getenv("INSPIRE_WORKER_URL", "").rstrip("/")
    token = os.getenv("INSPIRE_WORKER_TOKEN", "")
    url = urlsplit(base)
    if url.scheme != "https" or not url.hostname or url.username or url.password or url.query or url.fragment:
        raise ModelError("PROVIDER_NOT_CONFIGURED", "Configure the HTTPS INSPIRE_WORKER_URL variable")
    if len(token) < 16:
        raise ModelError("PROVIDER_NOT_CONFIGURED", "Configure INSPIRE_WORKER_TOKEN to match the Inspire Worker access code")
    payload = {"prompt": prompt}
    if image_url:
        payload["imageUrl"] = image_url
    req = urllib.request.Request(base + "/ai/messages", data=json.dumps(payload).encode(),
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json",
                 "Accept": "application/json", "User-Agent": "MyDayCoach-Inspiration/2.0"})
    # Never forward the private access code through HTTP redirects.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None
    with urllib.request.build_opener(NoRedirect).open(req, timeout=180) as response:
        result = json.load(response)
    if result.get("model") != MODEL:
        raise ModelError("WRONG_MODEL", "The Worker returned an unexpected model")
    return parse_json(result.get("text", ""))
