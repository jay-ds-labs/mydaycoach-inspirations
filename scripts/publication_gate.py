"""Fail-closed publication eligibility assessment; never changes library.json."""
import datetime as dt
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MIN_WORDS=600
MAX_WORDS=1100

def eligible(item,review,image_record):
    reasons=[]
    if not item.get("detail") or not MIN_WORDS<=len(item["detail"].split())<=MAX_WORDS:
        reasons.append("article_missing_or_wrong_length")
    if review.get("state")!="approved" or review.get("reviewedTextMatchesSaved") is not True:
        reasons.append("editorial_review_not_approved_for_saved_text")
    if not review.get("sourceAccessible") or not review.get("sourceUrls"):
        reasons.append("evidence_not_verified")
    selected=image_record.get("selected")
    if not isinstance(selected,dict):
        reasons.append("image_not_selected")
    else:
        candidates=image_record.get("candidates",[])
        matched=next((x for x in candidates if x.get("fileTitle")==selected.get("fileTitle") and
            x.get("descriptionUrl")==selected.get("descriptionUrl")),None)
        if not matched:
            reasons.append("selected_image_not_in_audit")
        else:
            if matched.get("state")!="license_metadata_pass":
                reasons.append("image_license_metadata_not_passed")
            if matched.get("visualCheck",{}).get("state")!="relevant_candidate":
                reasons.append("image_visual_review_not_passed")
            if not matched.get("attribution") or not matched.get("descriptionUrl") or not matched.get("license"):
                reasons.append("image_attribution_incomplete")
        if selected.get("editorialApproved") is not True:
            reasons.append("image_editorial_approval_missing")
        if selected.get("rightsApproved") is not True:
            reasons.append("image_rights_approval_missing")
    if review.get("editorialSignoff") is not True:
        reasons.append("final_editorial_signoff_missing")
    return {"id":item["id"],"eligible":not reasons,"reasons":reasons}

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
