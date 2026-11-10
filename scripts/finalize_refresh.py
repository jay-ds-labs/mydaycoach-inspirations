#!/usr/bin/env python3
"""Synchronize app-visible refresh status after editorial verification."""
import datetime as dt
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
STATUS=ROOT/"refresh-status.json"
REVIEWS=ROOT/"enrichment-review.json"
LIBRARY=ROOT/"library.json"

def summarize(refresh, reviews, library):
    ids=refresh.get("generatedIds",[])
    records=reviews.get("items",{})
    existing={item["id"] for item in library.get("items",[])}
    counts={state:0 for state in ("approved","review_failed","review_pending_retry","needs_manual_review")}
    for id in ids:
        if id not in existing:
            raise ValueError("Generated inspiration missing from library: "+id)
        state=records.get(id,{}).get("state","review_pending_retry")
        counts[state]=counts.get(state,0)+1
    refresh["reviewOutcomes"]=counts
    refresh["reviewed"]=sum(v for k,v in counts.items() if k!="review_pending_retry")
    refresh["approved"]=counts["approved"]
    refresh["state"]="awaiting_editorial_approval" if counts["approved"]==len(ids) and len(ids)==15 else "review_incomplete"
    refresh["completedAt"]=dt.datetime.now(dt.timezone.utc).isoformat()
    return refresh

if __name__=="__main__":
    refresh=json.loads(STATUS.read_text(encoding="utf-8"))
    reviews=json.loads(REVIEWS.read_text(encoding="utf-8"))
    library=json.loads(LIBRARY.read_text(encoding="utf-8"))
    STATUS.write_text(json.dumps(summarize(refresh,reviews,library),indent=2)+"\n",encoding="utf-8")
