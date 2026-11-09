#!/usr/bin/env python3
"""Resumable, evidence-aware enrichment of existing inspiration entries.

Preserves title, body, category, ID, favourites compatibility, and the existing
three published examples. Writes full detail into library.json and review
records into enrichment-review.json. Does not auto-publish uncertain content.
"""
import datetime as dt
import html
import json
import os
from pathlib import Path
import re
import subprocess
import time
import urllib.error
import urllib.request
from image_audit import candidates as image_candidates

ROOT=Path(__file__).resolve().parents[1]
FEED=ROOT/"library.json"
PROGRESS=ROOT/"enrichment-status.json"
REVIEWS=ROOT/"enrichment-review.json"
IMAGES=ROOT/"enrichment-images.json"
MODEL=os.getenv("OPENAI_CONTENT_MODEL","gpt-4.1")
REVIEW_MODEL=os.getenv("OPENAI_REVIEW_MODEL",MODEL)
BATCH_SIZE=max(1,min(20,int(os.getenv("ENRICH_BATCH_SIZE","10"))))
RETRY_REVIEW=os.getenv("ENRICH_RETRY_REVIEW","false").lower()=="true"

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
    if subprocess.run(["git","diff","--cached","--quiet"]).returncode:
        subprocess.run(["git","commit","-m",message],check=True)
        subprocess.run(["git","push","origin","HEAD:main"],check=True)

def model_json(prompt,model):
    payload={"model":model,"input":[{"role":"user","content":prompt}],
             "text":{"format":{"type":"json_object"}}}
    request=urllib.request.Request("https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization":"Bearer "+os.environ["OPENAI_API_KEY"],
                 "Content-Type":"application/json"})
    with urllib.request.urlopen(request,timeout=180) as response:
        raw=json.load(response)
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
        "Do not mention editorial process. Return JSON only. "+
        ("Revise to address: "+feedback if feedback else ""),MODEL)

def review(item,detail,source):
    return model_json(
        "You are an independent, skeptical editorial reviewer. Return JSON ONLY with "
        "approved (boolean), issues (array of short strings), factual_risk (low/medium/high), "
        "summary (string). Do not rubber-stamp. APPROVE only if every concrete factual claim "
        "and quotation in the article is supported by the supplied evidence, the article "
        "faithfully matches the original card, has no invented speech or unsupported motives, "
        "is engaging, coherent, and is 600-1100 words. If evidence is partial or inaccessible "
        "set approved=false. You cannot verify image licensing, so do not claim to have done so. "
        "Card: "+json.dumps({k:item.get(k,"") for k in ("category","title","body","source","attribution")})+
        "\nSource evidence:\n"+source+"\nArticle:\n"+detail,REVIEW_MODEL)

def main():
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("Missing OPENAI_API_KEY")
    feed=json.loads(FEED.read_text(encoding="utf-8"))
    original=[x for x in feed["items"] if x.get("status")!="published"]
    reviews=json.loads(REVIEWS.read_text(encoding="utf-8")) if REVIEWS.exists() else {"items":{}}
    done={k for k,v in reviews["items"].items() if v.get("state")=="approved" or (v.get("state")=="needs_review" and not RETRY_REVIEW)}
    remaining=[x for x in original if x["id"] not in done]
    if RETRY_REVIEW:
        remaining=[x for x in remaining if reviews["items"].get(x["id"],{}).get("state")=="needs_review"]
    selected=remaining[:BATCH_SIZE]
    images=json.loads(IMAGES.read_text(encoding="utf-8")) if IMAGES.exists() else {"items":{}}
    status={"state":"running","stage":"generation","completed":len(done),
            "total":len(original),"batchTotal":len(selected),"batchCompleted":0,
            "generated":0,"reviewed":0,"approved":0,"needsReview":0,
            "startedAt":now(),"completedAt":None,"currentId":None,"error":None}
    write(PROGRESS,status);write(REVIEWS,reviews);write(IMAGES,images);persist("Start resumable editorial enrichment batch")
    try:
        for item in selected:
            status["currentId"]=item["id"]
            status["stage"]="research"
            write(PROGRESS,status);persist("Research inspiration "+item["id"])
            original_source=item.get("source","")
            candidate_source=TARGETED_SOURCES.get(item["id"],original_source)
            source,source_error=evidence(candidate_source)
            if not source and candidate_source!=original_source:
                source,source_error=evidence(original_source)
                candidate_source=original_source
            # A generic homepage is not adequate historical evidence even if accessible.
            if candidate_source.rstrip("/").count("/")==2:
                source="";source_error="Source is a generic homepage, not evidence for this subject"
            status["stage"]="generation"
            draft=None;result=None;issues=[];best_detail=""
            last_reviewed_detail="";last_reviewed_result=None
            if not source:
                issues=[source_error or "No accessible supporting evidence"]
                # Do not burn API credits generating ungrounded historical stories.
                reviews["items"][item["id"]]={"state":"needs_review","checkedAt":now(),
                  "source":candidate_source,"sourceAccessible":False,"wordCount":len(item.get("detail","").split()),
                  "issues":issues,"factualRisk":"high","publication":"held_for_editorial_approval",
                  "imageStatus":"not_checked"}
                status["reviewed"]+=1;status["needsReview"]+=1
                status["completed"]+=1;status["batchCompleted"]+=1
                write(PROGRESS,status);write(REVIEWS,reviews);persist("Flag missing evidence "+item["id"])
                continue
            for attempt in range(5):
                try:
                    draft=compose(item,source,("; ".join(issues)) if issues else "")
                    detail=draft.get("detail","")
                    words=len(detail.split())
                    if MIN_WORDS<=words<=MAX_WORDS:
                        best_detail=detail
                    if not MIN_WORDS<=words<=MAX_WORDS:
                        raise ValueError("Article length "+str(words)+" outside 600-1100 words")
                    status["generated"]+=1
                    status["stage"]="review"
                    write(PROGRESS,status);persist("Review inspiration "+item["id"])
                    result=review(item,detail,source)
                    last_reviewed_detail=detail
                    last_reviewed_result=result
                    issues=[str(x)[:300] for x in result.get("issues",[])]
                    # Numeric claims from a language model are not a reliable word-count test.
                    issues=[x for x in issues if not re.search(r"(word count|article length|\bwords?\b.*\b(600|1100)\b|\b(600|1100)\b.*\bwords?\b)",x,re.I)]
                    if result.get("approved") is True and source:
                        best_detail=detail
                    if result.get("approved") is True and source:
                        break
                    issues=issues or ["Reviewer did not approve factual grounding"]
                except Exception as error:
                    issues=[str(error)[:250]]
                time.sleep(1)
            # Never retain an unreviewed candidate as though the last reviewer checked it.
            if last_reviewed_detail and MIN_WORDS<=len(last_reviewed_detail.split())<=MAX_WORDS:
                item["detail"]=last_reviewed_detail
            elif best_detail:
                item["detail"]=best_detail
                # Keep the short library summary, title, category and existing ID unchanged.
                item["status"]="draft"
                item["publishedAt"]=""
            saved_detail=item.get("detail","")
            review_matches_saved=bool(last_reviewed_detail) and saved_detail==last_reviewed_detail
            saved_words=len(saved_detail.split())
            state="approved" if (last_reviewed_result and last_reviewed_result.get("approved") is True
                and source and review_matches_saved and MIN_WORDS<=saved_words<=MAX_WORDS) else "needs_review"
            if not review_matches_saved:
                issues.append("Saved article was not the exact text evaluated by the final reviewer")
            if not MIN_WORDS<=saved_words<=MAX_WORDS:
                issues.append("Saved article length outside 600-1100 words")
            if state=="approved":
                issues=[]
            if state=="approved" and candidate_source!=original_source:
                item["source"]=candidate_source
            status["stage"]="image_audit"
            write(PROGRESS,status)
            image_results=image_candidates(item.get("attribution") or item["title"])
            images["items"][item["id"]]={"checkedAt":now(),"candidates":image_results[:5],
                "selected":None,"state":"awaiting_visual_and_license_review"}
            reviews["items"][item["id"]]={
                "state":state,"checkedAt":now(),"source":candidate_source,
                "sourceAccessible":bool(source),"wordCount":saved_words,
                "reviewedTextMatchesSaved":review_matches_saved,
                "originalSource":original_source,"evidenceSource":candidate_source,
                "issues":issues,"factualRisk":(result or {}).get("factual_risk","high"),
                "imageStatus":"awaiting_visual_and_license_review",
                "publication":"held_for_editorial_approval"
            }
            status["reviewed"]+=1
            status["approved"]+=int(state=="approved")
            status["needsReview"]+=int(state=="needs_review")
            status["completed"]+=1
            status["batchCompleted"]+=1
            write(FEED,feed);write(REVIEWS,reviews);write(IMAGES,images);write(PROGRESS,status)
            persist("Enrich and review inspiration "+item["id"])
        status["state"]="batch_complete" if len(remaining)>len(selected) else "awaiting_editorial_approval"
        status["stage"]="done";status["currentId"]=None;status["completedAt"]=now()
    except Exception as error:
        status["state"]="failed";status["error"]=str(error)[:400];status["completedAt"]=now()
        raise
    finally:
        write(PROGRESS,status);write(REVIEWS,reviews);write(IMAGES,images);persist("Finalize editorial enrichment batch status")

if __name__=="__main__":
    main()
