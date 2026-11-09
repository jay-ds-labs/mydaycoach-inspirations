"""Fail-closed publication eligibility assessment; never changes library.json."""
import datetime as dt
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MIN_WORDS=600
MAX_WORDS=1100

def eligible(item,review,image_record):
    """Review failures are advisory; a complete article is publishable without an image."""
    reasons=[]
    words=len(str(item.get("detail") or "").split())
    if not MIN_WORDS<=words<=MAX_WORDS:
        reasons.append("full_article_missing_or_wrong_length")
    if item.get("reviewStatus",review.get("state")) not in ("approved","review_failed"):
        reasons.append("review_cycle_not_completed")
    if review.get("state") not in ("approved","review_failed"):
        reasons.append("review_record_missing")
    # Images are optional. An image may only be displayed when separately cleared.
    selected=image_record.get("selected")
    image_ready=False
    if isinstance(selected,dict):
        matched=next((x for x in image_record.get("candidates",[]) if
            x.get("fileTitle")==selected.get("fileTitle") and
            x.get("descriptionUrl")==selected.get("descriptionUrl")),None)
        image_ready=bool(matched and matched.get("state")=="license_metadata_pass" and
            selected.get("rightsApproved") is True and selected.get("editorialApproved") is True and
            matched.get("attribution") and matched.get("descriptionUrl") and matched.get("license"))
    return {"id":item["id"],"eligible":not reasons,"reasons":reasons,
            "reviewStatus":review.get("state","not_reviewed"),
            "reviewFailureSummary":review.get("reviewFailureSummary",""),
            "imageReady":image_ready,"publishWithoutImage":not image_ready}

def assess(feed,reviews,images):
    results=[eligible(item,reviews.get("items",{}).get(item["id"],{}),
        images.get("items",{}).get(item["id"],{}))
        for item in feed.get("items",[]) if item.get("status")!="published"]
    return {"checkedAt":dt.datetime.now(dt.timezone.utc).isoformat(),
        "ready":sum(r["eligible"] for r in results),"blocked":sum(not r["eligible"] for r in results),
        "items":results,"note":"Assessment only; never publishes or changes short cards."}

def main():
    feed=json.loads((ROOT/"library.json").read_text(encoding="utf-8"))
    reviews=json.loads((ROOT/"enrichment-review.json").read_text(encoding="utf-8"))
    images=json.loads((ROOT/"enrichment-images.json").read_text(encoding="utf-8"))
    result=assess(feed,reviews,images)
    (ROOT/"publication-gate.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"ready":result["ready"],"blocked":result["blocked"]},indent=2))

if __name__=="__main__":
    main()
