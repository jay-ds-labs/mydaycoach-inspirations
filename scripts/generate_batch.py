#!/usr/bin/env python3
"""Generate five cards per category and run the shared final editorial pipeline."""

import json
import subprocess
import uuid
from pathlib import Path

from enrich_library import now, write as save
from final_review import ReviewError, finalize, request_json

ROOT = Path(__file__).resolve().parents[1]
FEED = ROOT / "library.json"
PROGRESS = ROOT / "refresh-status.json"
REVIEWS = ROOT / "enrichment-review.json"
CATEGORIES = ("Quotes", "Stories", "Philosophy")
TARGET = 15
ART_ROOT = "https://raw.githubusercontent.com/jay-ds-labs/mydaycoach-inspirations/main/images/inspire/"
CATEGORY_ART = {
    "Quotes": "reflection-030.webp",
    "Stories": "reflection-013.webp",
    "Philosophy": "reflection-001.webp",
}

def persist():
    subprocess.run(["git", "add", FEED.name, PROGRESS.name, REVIEWS.name], check=True, cwd=ROOT)
    if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT).returncode:
        subprocess.run(["git", "commit", "-m", "Record reviewed inspiration refresh progress"], check=True, cwd=ROOT)
        subprocess.run(["git", "push", "origin", "HEAD:main"], check=True, cwd=ROOT)

def generate(category, existing):
    entry = request_json(
        f"Return JSON for one distinct {category} inspiration with title, body, attribution, "
        "source, takeaway, and detail. Body is a short summary; detail is an initial draft. "
        "Choose a well-documented subject and a specific credible HTTPS source page. "
        "Use an exact quotation only with reliable attribution, or choose a different subject. "
        "Do not invent events, quotes or links. Avoid repeating these titles: "
        + json.dumps(existing[-150:], ensure_ascii=False)
    )
    required = ("title", "body", "attribution", "source", "takeaway")
    if any(not isinstance(entry.get(k), str) or not 0 < len(entry[k].strip()) <= 4000 for k in required):
        raise ReviewError("INVALID_CARD", "Generated card is missing required content")
    if not entry["source"].startswith("https://"):
        raise ReviewError("INSUFFICIENT_EVIDENCE", "Generated card lacks a credible HTTPS source")
    if entry["title"].strip().casefold() in {x.strip().casefold() for x in existing}:
        raise ReviewError("DUPLICATE_CARD", "Generated title already exists")
    return {**{k: entry[k].strip() for k in required},
            "detail": str(entry.get("detail") or "")[:11500],
            "id": "generated-" + uuid.uuid4().hex[:20], "category": category,
            "status": "draft", "publishedAt": "", "image": ART_ROOT + CATEGORY_ART[category]}

def main():
    library = json.loads(FEED.read_text(encoding="utf-8"))
    reviews = json.loads(REVIEWS.read_text(encoding="utf-8"))
    status = {"state": "running", "stage": "generation", "completed": 0, "total": TARGET,
              "quotes": 0, "stories": 0, "philosophy": 0, "generated": 0,
              "reviewed": 0, "approved": 0, "needsReview": 0, "reviewFailed": 0,
              "startedAt": now(), "completedAt": None, "error": None, "outcomes": []}
    save(PROGRESS, status)
    persist()
    existing = [item["title"] for item in library["items"]]
    try:
        for category in CATEGORIES:
            for index in range(5):
                print(f"{category} {index + 1}/5: generation", flush=True)
                try:
                    card = generate(category, existing)
                    existing.append(card["title"])
                    status["generated"] += 1
                    status["stage"] = "review"
                    save(PROGRESS, status)
                    persist()
                    item, audit = finalize(card, allow_card_correction=True,
                                           progress=lambda stage: print(stage, flush=True))
                    if audit["eligible"]:
                        library["items"].append(item)
                    else:
                        audit["finalVersion"] = item
                    reviews["items"][card["id"]] = audit
                    status["reviewed"] += int(audit["completedReviews"] > 0)
                    status["approved"] += int(audit["state"] == "approved")
                    outcome = {"id": card["id"], "category": category, "state": audit["state"],
                               "reasonCode": audit["reasonCode"], "eligible": audit["eligible"]}
                except ReviewError as error:
                    outcome = {"category": category, "state": "review_failed",
                               "reasonCode": error.code, "reason": str(error), "eligible": False}
                status["reviewFailed"] += int(outcome["state"] == "review_failed")
                status["outcomes"].append(outcome)
                status["completed"] += 1
                status[category.lower()] += 1
                status["stage"] = "generation"
                save(FEED, library)
                save(REVIEWS, reviews)
                save(PROGRESS, status)
                persist()
        status["state"] = "review_incomplete" if status["reviewFailed"] else "awaiting_editorial_approval"
        status["stage"] = "done"
    except Exception as error:
        status["state"] = "failed"
        status["error"] = str(error)[:300]
        raise
    finally:
        status["completedAt"] = now()
        save(PROGRESS, status)
        persist()

if __name__ == "__main__":
    main()
