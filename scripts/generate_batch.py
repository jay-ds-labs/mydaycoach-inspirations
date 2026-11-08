#!/usr/bin/env python3
"""Generate exactly five candidates per category, saving progress after each item.
Requires OPENAI_API_KEY; candidates are DRAFT until editorial verification.
Run from the content repository root. Does not silently publish unverified claims.
"""
import datetime as dt
import json
import os
import pathlib
import re
import time
import urllib.request
import uuid

ROOT = pathlib.Path(__file__).resolve().parents[1]
FEED = ROOT / "library.json"
PROGRESS = ROOT / "refresh-status.json"
CATEGORIES = ("Quotes", "Stories", "Philosophy")
TARGET = 15

def save(path, data):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)

def now():
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")

def generate(category, existing):
    api_key = os.environ["OPENAI_API_KEY"]
    prompt = (
        f"Create ONE original, historically accurate, distinct {category} inspiration. "
        "Avoid these titles and subjects: " + ", ".join(existing[-100:]) +
        ". Return ONLY a JSON object with title, body (35-75 word synopsis), "
        "detail (650-950 words, richly written, engaging, contextual, accurate), "
        "attribution, source (specific credible HTTPS source URL), takeaway (one actionable sentence), "
        "image (a verified, reusable HTTPS image URL, or empty string), and category. "
        "For Quotes, include an accurately attributed quotation and its original context. "
        "For Stories, narrate a documented real event. For Philosophy, explain an actual school or thinker. "
        "Do not fabricate citations, quotations, URLs or image licensing; if unsure, return empty source. "
        "Do not output markdown. Category must be " + category + "."
    )
    payload = {"model": os.environ.get("OPENAI_CONTENT_MODEL", "gpt-4.1"),
               "input": [{"role": "user", "content": prompt}],
               "text": {"format": {"type": "json_object"}}}
    req = urllib.request.Request("https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode(), headers={
            "Authorization": "Bearer " + api_key, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as response:
        result = json.load(response)
    chunks = [part.get("text", "") for output in result.get("output", [])
              for part in output.get("content", []) if part.get("type") == "output_text"]
    if not chunks:
        raise ValueError("No text returned")
    entry = json.loads("".join(chunks))
    if entry.get("category") != category:
        raise ValueError("Category mismatch")
    if len(entry.get("detail", "").split()) < 500:
        raise ValueError("Article too short")
    if not entry.get("source", "").startswith("https://"):
        raise ValueError("Missing credible source URL")
    if not all(entry.get(k, "").strip() for k in ("title","body","detail","attribution","takeaway")):
        raise ValueError("Missing content")
    entry["id"] = "generated-" + uuid.uuid4().hex[:20]
    entry["status"] = "draft"
    entry["publishedAt"] = ""
    entry["image"] = ""  # Images require separate rights and URL verification.
    return entry

def main():
    library = json.loads(FEED.read_text(encoding="utf-8"))
    status = {"state": "running", "completed": 0, "total": TARGET,
              "quotes": 0, "stories": 0, "philosophy": 0,
              "startedAt": now(), "completedAt": None, "error": None}
    save(PROGRESS, status)
    existing = [item["title"] for item in library["items"]]
    try:
        for category in CATEGORIES:
            for index in range(5):
                for attempt in range(3):
                    try:
                        entry = generate(category, existing)
                        if entry["title"].casefold() in {x.casefold() for x in existing}:
                            raise ValueError("Duplicate title")
                        break
                    except Exception:
                        if attempt == 2: raise
                        time.sleep(2 ** attempt)
                library["items"].append(entry)
                existing.append(entry["title"])
                save(FEED, library)
                status["completed"] += 1
                status[category.lower()] += 1
                save(PROGRESS, status)
        status["state"] = "awaiting_review"
        status["completedAt"] = now()
    except Exception as error:
        status["state"] = "failed"
        status["error"] = str(error)[:300]
        status["completedAt"] = now()
        raise
    finally:
        save(PROGRESS, status)

if __name__ == "__main__":
    main()
