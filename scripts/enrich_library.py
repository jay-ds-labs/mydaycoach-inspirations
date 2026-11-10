#!/usr/bin/env python3
"""Resumable, evidence-aware enrichment of existing inspiration entries.

Preserves title, body, category, ID, favourites compatibility, and the existing
three published examples. Writes full detail into library.json and review
records into enrichment-review.json. Moves complete content to ready_for_publish; review failures remain visible.
"""
import datetime as dt
import html
import json
import os
from pathlib import Path
import re
import subprocess
import time
from api_resilience import call_with_retry, classify_error
import urllib.error
import urllib.request
from audit_images import candidates as image_candidates
from research import discover as discover_sources, evidence_bundle

ROOT=Path(__file__).resolve().parents[1]
FEED=ROOT/"library.json"
PROGRESS=ROOT/"enrichment-status.json"
REVIEWS=ROOT/"enrichment-review.json"
IMAGES=ROOT/"enrichment-images.json"
MODEL=os.getenv("OPENAI_CONTENT_MODEL","gpt-4.1")
REVIEW_MODEL=os.getenv("OPENAI_REVIEW_MODEL",MODEL)
BATCH_SIZE=max(1,min(20,int(os.getenv("ENRICH_BATCH_SIZE","10"))))
RETRY_REVIEW=os.getenv("ENRICH_RETRY_REVIEW","false").lower()=="true"
MAX_ATTEMPTS=max(1,min(3,int(os.getenv("ENRICH_MAX_ATTEMPTS","3"))))

# Targeted primary or institutional sources for the five pilot articles.
# Generic homepages are inadequate evidence for a 750-word historical article.
TARGETED_SOURCES={
 "apollo-11":"https://www.nasa.gov/missions/apollo/apollo-11-mission-overview/",
 "curie-nobel":"https://www.nobelprize.org/prizes/physics/1903/marie-curie/facts/",
 "mandela-release":"https://www.nelsonmandela.org/trials-and-prison-chronology",
 "everest-summit":"https://nzhistory.govt.nz/edmund-hillary-and-tensing-norgay-reach-summit-of-everest",
 "wright-flight":"https://www.si.edu/object/nasm_A19610048000",
}

MIN_WORDS=600
MAX_WORDS=1100

def now():
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00","Z")

def write(path,data):
    tmp=path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    tmp.replace(path)

def persist(message):
    subprocess.run(["git","add",FEED.name,PROGRESS.name,REVIEWS.name,IMAGES.name],check=True)
    if subprocess.run(["git","diff","--cached","--quiet"]).returncode == 0:
        return
    subprocess.run(["git","commit","-m",message],check=True)
    push = ["git", "push", "origin", "HEAD:" + os.getenv("CONTENT_TARGET_BRANCH", "main")]
    for attempt in range(3):
        result = subprocess.run(push, text=True, stderr=subprocess.PIPE)
        if result.returncode == 0:
            return
        print(result.stderr, end="", flush=True)
        if attempt == 2 or "missing necessary objects" not in result.stderr:
            result.check_returncode()
        time.sleep(2 ** attempt)

def model_json(prompt,model):
    payload={"model":model,"input":[{"role":"user","content":prompt}],
             "text":{"format":{"type":"json_object"}}}
    request=urllib.request.Request("https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization":"Bearer "+os.environ["OPENAI_API_KEY"],
                 "Content-Type":"application/json"})
    def send():
        with urllib.request.urlopen(request,timeout=180) as response:
            return json.load(response)
    raw=call_with_retry(send)
    parts=[p.get("text","") for o in raw.get("output",[])
           for p in o.get("content",[]) if p.get("type")=="output_text"]
    if not parts:
        raise ValueError("Model returned no text")
    return json.loads("".join(parts))

def evidence(url):
    if not url.startswith("https://"):
        return "", "No HTTPS source"
    try:
        req=urllib.request.Request(url,headers={"User-Agent":"MyDayCoachEditorial/1.0"})
        with urllib.request.urlopen(req,timeout=18) as resp:
            typ=resp.headers.get("Content-Type","").lower()
            if "text/html" not in typ and "text/plain" not in typ:
                return "", "Source not accessible as text"
            raw=resp.read(350000).decode("utf-8","replace")
        raw=re.sub(r"(?is)<(script|style|nav|footer|header)[^>]*>.*?</\1>"," ",raw)
        raw=re.sub(r"(?s)<[^>]+>"," ",raw)
        clean=html.unescape(re.sub(r"\s+"," ",raw)).strip()
        if len(clean)<350:
            return "", "Source has insufficient readable evidence"
        return clean[:14000], ""
    except urllib.error.HTTPError as error:
        return "", ("SOURCE_ACCESS_DENIED: HTTP 403" if error.code==403 else
                    "Source retrieval failed: HTTP "+str(error.code))
    except Exception as error:
        return "", "Source retrieval failed: "+str(error)[:140]

def compose(item,source,feedback=""):
    return model_json(
        "Write one original, accurate, publication-quality inspiration as a JSON object "
        "with keys detail and takeaway. The existing card fields must NOT be rewritten. "
        "Keep the subject and exact historical setting of this card: "+
        json.dumps({k:item.get(k,"") for k in ("category","title","body","attribution","source","takeaway")},ensure_ascii=False)+
        "\nEvidence from the source (may be truncated):\n"+source+
        "\nWrite 750-950 words in detail, narrative paragraphs, a strong opening, "
        "specific context, and an actionable closing. Do not add unsupported direct quotes, "
        "dates, dramatic dialogue, motives, or fabricated events. "
        "For philosophy distinguish interpretation from historical fact. "
        "For quotes use verbatim quotation only if the evidence supports it. "
        "Prefer directly evidenced chronology to invented inner thoughts, motivations, or dialogue. "
        "If earlier review identified unsupported assertions, remove them rather than paraphrasing them. "
        "Do not mention editorial process. Return JSON only. "+
        ("Revise to address: "+feedback if feedback else ""),MODEL)

def review(item,detail,source):
    return model_json(
        "You are an independent, skeptical editorial reviewer. Return JSON ONLY with "
        "approved (boolean), issues (array of short strings), factual_risk (low/medium/high), "
        "summary (string). Do not rubber-stamp. APPROVE only if every concrete factual claim "
        "and quotation in the article is supported by the supplied evidence, the article "
        "faithfully matches the original card, has no invented speech or unsupported motives, "
        "is engaging and coherent. Do not assess or mention article word count: Python validates length. If evidence is partial or inaccessible "
        "set approved=false. You cannot verify image licensing, so do not claim to have done so. "
        "Card: "+json.dumps({k:item.get(k,"") for k in ("category","title","body","source","attribution")})+
        "\nSource evidence:\n"+source+"\nArticle:\n"+detail,REVIEW_MODEL)

def main():
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("Missing OPENAI_API_KEY")
    feed=json.loads(FEED.read_text(encoding="utf-8"))
    original=[x for x in feed["items"] if x.get("status")!="published"]
    reviews=json.loads(REVIEWS.read_text(encoding="utf-8")) if REVIEWS.exists() else {"items":{}}
    done={k for k,v in reviews["items"].items() if v.get("state") in ("approved","review_failed","needs_manual_review")}
    if RETRY_REVIEW:
        remaining=[x for x in original if reviews["items"].get(x["id"],{}).get("state") in ("review_failed","needs_review","review_pending_retry","needs_manual_review") or (x["id"] not in done and x["id"] in reviews["items"])]
    else:
        remaining=[x for x in original if x["id"] not in done]
    batch_ids=os.getenv("ENRICH_TARGET_IDS_FILE","")
    recovery_id=os.getenv("ENRICH_RECOVERY_BATCH_ID","")
    if batch_ids:
        requested=json.loads(Path(batch_ids).read_text(encoding="utf-8")).get("generatedIds",[])
        requested_set=set(requested)
        selected=[x for x in original if x["id"] in requested_set and
                  (not recovery_id or reviews["items"].get(x["id"],{}).get("recoveryBatchId")!=recovery_id)][:BATCH_SIZE]
    else:
        selected=remaining[:BATCH_SIZE]
    images=json.loads(IMAGES.read_text(encoding="utf-8")) if IMAGES.exists() else {"items":{}}
    completed = len(done)
    total = len(original)
    if batch_ids and recovery_id:
        completed = sum(reviews["items"].get(item_id, {}).get("recoveryBatchId") == recovery_id
                        for item_id in requested_set)
        total = len(requested_set)
    status={"state":"running","stage":"generation","completed":completed,
            "total":total,"batchTotal":len(selected),"batchCompleted":0,
            "generated":0,"reviewed":0,"approved":0,"needsReview":0,
            "startedAt":now(),"completedAt":None,"currentId":None,"error":None}
    write(PROGRESS,status);write(REVIEWS,reviews);write(IMAGES,images);persist("Start resumable editorial enrichment batch")
    try:
        for item in selected:
            status["currentId"]=item["id"]
            status["stage"]="research"
            write(PROGRESS,status);persist("Research inspiration "+item["id"])
            original_source=item.get("source","")
            preferred_source=TARGETED_SOURCES.get(item["id"],original_source)
            records,source_errors=discover_sources(item,preferred_source,fetch=evidence)
            source=evidence_bundle(records)
            source_urls=[r["url"] for r in records]
            issues=[];best_detail="";best_result=None;best_issues=[];attempts=[]
            completed_reviews=0
            length_failures=0
            approved=False
            infrastructure_error=None
            if not records:
                issues=["No subject-specific evidence found"]+source_errors
            status["stage"]="generation"
            if records:
                for attempt in range(MAX_ATTEMPTS+3):
                    if completed_reviews>=MAX_ATTEMPTS or length_failures>=3:
                        break
                    attempt_record={"attempt":attempt+1,"approved":False,"issues":[]}
                    try:
                        draft=compose(item,source or "No independent source was retrieved. Avoid unverifiable specifics; explain uncertainty.", "; ".join(issues))
                        detail=str(draft.get("detail",""))
                        words=len(detail.split())
                        if MIN_WORDS<=words<=MAX_WORDS and not best_detail:
                            best_detail=detail;best_issues=["Article not yet approved by reviewer"]
                        if not MIN_WORDS<=words<=MAX_WORDS:
                            issues=["Generated article length "+str(words)+" outside 600-1100 words"]
                            attempt_record["issues"]=issues[:3]
                            attempt_record["failureCode"]="EDITORIAL_QUALITY_FAILED"
                            length_failures+=1
                            attempts.append(attempt_record)
                            continue
                        status["generated"]+=1
                        status["stage"]="review"
                        write(PROGRESS,status);persist("Review inspiration "+item["id"])
                        result=review(item,detail,source)
                        # Python owns deterministic length checks; ignore numerical model errors.
                        editorial_issues=[str(x)[:300] for x in result.get("issues",[])
                            if not re.search(r"(word count|article length|\\bwords?\\b.*\\b(600|1100)\\b|\\b(600|1100)\\b.*\\bwords?\\b)",str(x),re.I)]
                        completed_reviews+=1
                        attempt_record["completedEditorialReview"]=True
                        editorial_pass=result.get("approved") is True and not editorial_issues
                        attempt_record["approved"]=editorial_pass
                        attempt_record["issues"]=editorial_issues[:3]
                        if editorial_pass:
                            best_detail=detail;best_result=result;best_issues=[]
                            attempts.append(attempt_record)
                            break
                        if not best_detail or len(editorial_issues)<len(best_issues):
                            best_detail=detail;best_result=result;best_issues=editorial_issues or ["Reviewer did not approve"]
                        attempts.append(attempt_record)
                        issues=editorial_issues or ["Factual or editorial review did not approve"]
                    except Exception as error:
                        code=classify_error(error)
                        issues=["Generation/review error: "+str(error)[:250]]
                        attempt_record["issues"]=issues[:3]
                        attempt_record["failureCode"]=code
                        if code in ("REVIEW_API_UNAVAILABLE","REVIEW_API_FORBIDDEN"):
                            infrastructure_error=code
                            break
                        attempts.append(attempt_record)
                    time.sleep(1)
            # Preserve existing valid text if all new attempts fail; never claim it passed.
            if best_detail:
                item["detail"]=best_detail
            complete=MIN_WORDS<=len(str(item.get("detail") or "").split())<=MAX_WORDS
            item["status"]="draft"  # Fail closed until evidence and editorial review approve.
            if item["status"]=="draft":
                item["publishedAt"]=""
            saved_detail=item.get("detail","")
            saved_words=len(saved_detail.split())
            exact_review=bool(best_detail and best_result) and saved_detail==best_detail
            approved=bool(best_result) and exact_review and not best_issues and best_result.get("approved") is True and infrastructure_error is None
            state=("review_pending_retry" if infrastructure_error=="REVIEW_API_UNAVAILABLE"
                   else "needs_manual_review" if infrastructure_error=="REVIEW_API_FORBIDDEN" or not records
                   else "approved" if approved and records and MIN_WORDS<=saved_words<=MAX_WORDS
                   else "needs_manual_review" if completed_reviews==0 and length_failures>=3
                   else "review_pending_retry" if completed_reviews==0
                   else "review_failed")
            if state=="approved":
                item["status"]="ready_for_publish"
            if state!="approved":
                issues=list(best_issues or issues or ["No approved review of the saved article"])
                if not exact_review:
                    issues.append("Saved text has not passed a matching editorial review")
                if not MIN_WORDS<=saved_words<=MAX_WORDS:
                    issues.append("Saved article length outside 600-1100 words")
            else:
                issues=[]
            item["reviewStatus"]=state
            item["reviewFailureSummary"]="; ".join(issues[:2])[:350] if state!="approved" else ""
            status["stage"]="image_audit"
            write(PROGRESS,status)
            try:
                image_results,image_errors=image_candidates(item)
            except Exception as image_error:
                image_results,image_errors=[],["Image discovery unavailable: "+str(image_error)[:180]]
            images["items"][item["id"]]={"checkedAt":now(),
                "queries":[item.get("title","")],"candidates":image_results,
                "errors":image_errors,"selected":None,
                "state":"awaiting_visual_and_license_review"}
            previous_review=reviews["items"].get(item["id"],{})
            reviews["items"][item["id"]]={
                "previousReview":previous_review if previous_review else None,
                "recoveryBatchId":recovery_id if batch_ids else "",
                "state":state,"checkedAt":now(),"source":preferred_source,
                "failureCodes":([infrastructure_error] if infrastructure_error else
                    (["SOURCE_ACCESS_DENIED","INSUFFICIENT_EVIDENCE"] if any("SOURCE_ACCESS_DENIED" in x for x in source_errors) else ["INSUFFICIENT_EVIDENCE"]) if not records else
                    ["EDITORIAL_QUALITY_FAILED"] if not complete else
                    ["FACTUAL_CONTRADICTION"] if any("unsupported" in str(x).lower() or "factual" in str(x).lower() for x in issues) else
                    ["EDITORIAL_QUALITY_FAILED"] if state!="approved" else []),
                "reviewAttempts":attempts,"attemptCount":len(attempts),
                "completedEditorialReviews":completed_reviews,
                "reviewFailureSummary":"; ".join(issues[:2])[:350] if state!="approved" else "",
                "sourceAccessible":bool(records),"sourceUrls":source_urls,
                "sourceCount":len(records),"wordCount":saved_words,
                "reviewedTextMatchesSaved":exact_review,
                "originalSource":original_source,"evidenceSource":source_urls[0] if source_urls else "",
                "issues":issues,"factualRisk":(best_result or {}).get("factual_risk","high"),
                "imageStatus":"awaiting_visual_and_license_review",
                "publication":"ready_for_publish" if state=="approved" else "blocked_unapproved_review"
            }
            status["reviewed"]+=1
            status["approved"]+=int(state=="approved")
            status["needsReview"]+=int(state!="approved")
            status["completed"]+=1
            status["batchCompleted"]+=1
            write(FEED,feed);write(REVIEWS,reviews);write(IMAGES,images);write(PROGRESS,status)
            persist("Enrich and review inspiration "+item["id"])
        status["state"]="batch_complete" if len(remaining)>len(selected) else "awaiting_editorial_approval"
        status["contentReady"]=sum(v.get("state")=="approved" for v in reviews["items"].values())
        status["contentNeedsReview"]=sum(v.get("state") in ("needs_review","review_failed","review_pending_retry","needs_manual_review") for v in reviews["items"].values())
        status["reviewFailed"]=sum(v.get("state")=="review_failed" for v in reviews["items"].values())
        status["publicationReady"]=sum(x.get("status")=="ready_for_publish" for x in original)
        status["publicationBlocked"]=sum(x.get("status")=="draft" for x in original)
        status["qualityGate"]="full_article_and_approved_review_required"
        status["stage"]="done";status["currentId"]=None;status["completedAt"]=now()
    except Exception as error:
        status["state"]="failed";status["error"]=str(error)[:400];status["completedAt"]=now()
        raise
    finally:
        write(PROGRESS,status);write(REVIEWS,reviews);write(IMAGES,images);persist("Finalize editorial enrichment batch status")

if __name__=="__main__":
    main()
