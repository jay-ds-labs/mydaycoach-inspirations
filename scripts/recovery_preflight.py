"""Preflight safety checks for the historical 36-item recovery."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def validate(manifest, reviews, library):
    ids=manifest.get("generatedIds",[])
    if len(ids)!=36 or len(set(ids))!=36:
        raise ValueError("Recovery manifest must contain exactly 36 distinct IDs")
    by_id={x["id"]:x for x in library.get("items",[])}
    records=reviews.get("items",{})
    missing=[id for id in ids if id not in by_id or id not in records]
    if missing:
        raise ValueError("Recovery IDs missing from library/reviews: "+", ".join(missing))
    published=[id for id in ids if by_id[id].get("status")=="published"]
    if published:
        raise ValueError("Refusing to reprocess published IDs: "+", ".join(published))
    unexpected=[id for id in ids if records[id].get("state") not in
                ("review_failed","review_pending_retry","needs_manual_review","approved")]
    if unexpected:
        raise ValueError("Unexpected review state: "+", ".join(unexpected))
    return {"targetCount":len(ids),"alreadyApproved":sum(records[id].get("state")=="approved" for id in ids),
            "remaining":sum(records[id].get("recoveryBatchId")!="historical-36-v1" for id in ids)}

if __name__=="__main__":
    manifest=json.loads((ROOT/"recovery/failed-review-36.json").read_text())
    reviews=json.loads((ROOT/"enrichment-review.json").read_text())
    library=json.loads((ROOT/"library.json").read_text())
    print(json.dumps(validate(manifest,reviews,library),indent=2))
