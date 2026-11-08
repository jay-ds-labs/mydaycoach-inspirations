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

ROOT=Path(__file__).resolve().parents[1]
FEED=ROOT/"library.json"
PROGRESS=ROOT/"enrichment-status.json"
REVIEWS=ROOT/"enrichment-review.json"
MODEL=os.getenv("OPENAI_CONTENT_MODEL","gpt-4.1")
REVIEW_MODEL=os.getenv("OPENAI_REVIEW_MODEL",MODEL)
BATCH_SIZE=max(1,min(20,int(os.getenv("ENRICH_BATCH_SIZE","10"))))
MIN_WORDS=600
MAX_WORDS=1100

def now():
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00","Z")

def write(path,data):
    tmp=path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    tmp.replace(path)

def persist(message):
    subprocess.run(["git","add",FEED.name,PROGRESS.name,REVIEWS.name],check=True)
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
    done={k for k,v in reviews["items"].items() if v.get("state") in ("approved","needs_review")}
    remaining=[x for x in original if x["id"] not in done]
    selected=remaining[:BATCH_SIZE]
    status={"state":"running","stage":"generation","completed":len(done),
            "total":len(original),"batchTotal":len(selected),"batchCompleted":0,
            "generated":0,"reviewed":0,"approved":0,"needsReview":0,
            "startedAt":now(),"completedAt":None,"currentId":None,"error":None}
    write(PROGRESS,status);write(REVIEWS,reviews);persist("Start resumable editorial enrichment batch")
    try:
        for item in selected:
            status["currentId"]=item["id"]
            status["stage"]="research"
            write(PROGRESS,status);persist("Research inspiration "+item["id"])
            source,source_error=evidence(item.get("source",""))
            status["stage"]="generation"
            draft=None;result=None;issues=[]
            for attempt in range(3):
                try:
                    draft=compose(item,source,("; ".join(issues)) if issues else "")
                    detail=draft.get("detail","")
                    words=len(detail.split())
                    if not MIN_WORDS<=words<=MAX_WORDS:
                        raise ValueError("Article length "+str(words)+" outside 600-1100 words")
                    status["generated"]+=1
                    status["stage"]="review"
                    write(PROGRESS,status);persist("Review inspiration "+item["id"])
                    result=review(item,detail,source) if source else {
                        "approved":False,"issues":[source_error],"factual_risk":"high"}
                    issues=[str(x)[:300] for x in result.get("issues",[])]
                    if result.get("approved") is True and source:
                        break
                    issues=issues or ["Reviewer did not approve factual grounding"]
                except Exception as error:
                    issues=[str(error)[:250]]
                time.sleep(1)
            if draft and MIN_WORDS<=len(draft.get("detail","").split())<=MAX_WORDS:
                item["detail"]=draft["detail"]
                # Keep the short library summary, title, category and existing ID unchanged.
                item["status"]="draft"
                item["publishedAt"]=""
            state="approved" if result and result.get("approved") is True and source else "needs_review"
            reviews["items"][item["id"]]={
                "state":state,"checkedAt":now(),"source":item.get("source",""),
                "sourceAccessible":bool(source),"wordCount":len(item.get("detail","").split()),
                "issues":issues,"factualRisk":(result or {}).get("factual_risk","high"),
                "imageStatus":"requires_license_verification",
                "publication":"held_for_editorial_approval"
            }
            status["reviewed"]+=1
            status["approved"]+=int(state=="approved")
            status["needsReview"]+=int(state=="needs_review")
            status["completed"]+=1
            status["batchCompleted"]+=1
            write(FEED,feed);write(REVIEWS,reviews);write(PROGRESS,status)
            persist("Enrich and review inspiration "+item["id"])
        status["state"]="batch_complete" if len(remaining)>len(selected) else "awaiting_editorial_approval"
        status["stage"]="done";status["currentId"]=None;status["completedAt"]=now()
    except Exception as error:
        status["state"]="failed";status["error"]=str(error)[:400];status["completedAt"]=now()
        raise
    finally:
        write(PROGRESS,status);write(REVIEWS,reviews);persist("Finalize editorial enrichment batch status")

if __name__=="__main__":
    main()
