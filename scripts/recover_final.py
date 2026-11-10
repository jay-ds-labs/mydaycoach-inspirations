"""Run the shared editorial review once for each of the 27 audited items."""

import json
import subprocess
from pathlib import Path

from enrich_library import now, write
from final_review import finalize

ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "recovery/final-27-results.json"

def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))

def checkpoint(result):
    write(RESULT, result)
    subprocess.run(["git", "add", str(RESULT)], check=True, cwd=ROOT)
    if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT).returncode:
        subprocess.run(["git", "commit", "-m", "Record final Inspire recovery progress"], check=True, cwd=ROOT)
        subprocess.run(["git", "push", "origin", "HEAD:main"], check=True, cwd=ROOT)

def main():
    manifest = load("recovery/final-27.json")
    ids = [row["id"] for row in manifest]
    if len(ids) != 27 or len(set(ids)) != 27:
        raise ValueError("Expected exactly the 27 distinct audited IDs")
    archived = load("recovery/unpublished-21-2026-11-09.json")["items"]
    feed = load("library.json")["items"]
    cards = {x["id"]: x for x in archived + feed}
    if not set(ids) <= cards.keys():
        raise ValueError("Recovery source cards are missing")
    result = load("recovery/final-27-results.json") if RESULT.exists() else {
        "state": "running", "total": 27, "completed": 0, "generated": 0,
        "reviewed": 0, "approved": 0, "reviewFailed": 0, "eligible": 0,
        "startedAt": now(), "items": {},
    }
    checkpoint(result)
    for row in manifest:
        item_id = row["id"]
        if item_id in result["items"]:
            continue
        print(f"{result['completed'] + 1}/27 {item_id}: research", flush=True)
        item, audit = finalize(cards[item_id], row["sources"], row["correctCard"],
                               lambda stage: print(f"{item_id}: {stage}", flush=True))
        result["items"][item_id] = {"item": item, "audit": audit}
        result["completed"] += 1
        result["generated"] += int(audit["generated"])
        result["reviewed"] += int(audit["completedReviews"] > 0)
        result["approved"] += int(audit["state"] == "approved")
        result["reviewFailed"] += int(audit["state"] == "review_failed")
        result["eligible"] += int(audit["eligible"])
        checkpoint(result)
    result.update(state="completed", completedAt=now())
    checkpoint(result)

if __name__ == "__main__":
    main()
