"""Independent, conservative image audit; does not regenerate or publish text."""
import datetime as dt
import html
import json
import os
from pathlib import Path
import re
import subprocess
import urllib.parse
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
FEED=ROOT/"library.json"
IMAGES=ROOT/"enrichment-images.json"
REVIEWS=ROOT/"enrichment-review.json"
STATUS=ROOT/"image-audit-status.json"
API="https://commons.wikimedia.org/w/api.php"
HEADERS={"User-Agent":"MyDayCoachEditorial/1.2 (https://github.com/jay-ds-labs/mydaycoach-inspirations)"}
ALLOWED={"cc0","public-domain","public domain","pd","cc-by-4.0","cc-by-sa-4.0",
         "cc-by-3.0","cc-by-sa-3.0","cc-by-2.0","cc-by-sa-2.0"}
QUERIES={
    "apollo-11":["Apollo 11 Buzz Aldrin lunar surface NASA","Apollo 11 moon landing NASA"],
    "curie-nobel":["Marie Curie portrait photograph","Marie Skłodowska Curie"],
    "mandela-release":["Nelson Mandela released prison 1990 photograph","Nelson Mandela portrait"],
    "everest-summit":["Edmund Hillary Tenzing Norgay Everest 1953","Tenzing Norgay Hillary summit"],
    "wright-flight":["Wright brothers first flight 1903 Kitty Hawk photograph","Wright Flyer 1903"],
}

def now():
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00","Z")

def plain(value):
    return re.sub(r"<[^>]+>"," ",html.unescape(str(value or ""))).strip()

def query_api(params):
    url=API+"?"+urllib.parse.urlencode({"format":"json","formatversion":"2",**params})
    with urllib.request.urlopen(urllib.request.Request(url,headers=HEADERS),timeout=25) as resp:
        return json.load(resp)

def search(query,limit=8):
    data=query_api({"action":"query","generator":"search","gsrsearch":query,
                    "gsrnamespace":6,"gsrlimit":limit,"prop":"imageinfo",
                    "iiprop":"url|mime|extmetadata","iiurlwidth":1200})
    return data.get("query",{}).get("pages",[])

def verify(page):
    info=(page.get("imageinfo") or [{}])[0]
    meta=info.get("extmetadata") or {}
    def m(k):
        return plain((meta.get(k) or {}).get("value",""))
    license_name=m("LicenseShortName").lower().replace(" ","-")
    license_url=m("LicenseUrl")
    terms=m("UsageTerms")
    creator=m("Artist")
    attribution=m("Attribution") or creator
    url=info.get("thumburl") or info.get("url") or ""
    description=info.get("descriptionurl") or ""
    mime=info.get("mime","")
    metadata_ok=license_name in ALLOWED and url.startswith("https://") and description.startswith("https://") and mime in ("image/jpeg","image/png","image/webp")
    if any(x in (terms+" "+m("Permission")).lower() for x in ("non-commercial","fair use","permission required","all rights reserved")):
        metadata_ok=False
    return {"state":"license_metadata_pass" if metadata_ok else "needs_manual_license_review",
            "fileTitle":page.get("title",""),"imageUrl":url,"descriptionUrl":description,
            "creator":creator,"attribution":attribution,"license":license_name,
            "licenseUrl":license_url,"usageTerms":terms,"mime":mime,
            "description":m("ImageDescription")[:500],
            "requiresVisualReview":True,
            "note":"Metadata only; authenticity, relevance, and legal suitability not yet verified."}

def visual_check(item,candidate):
    """Vision-assisted relevance screening; not proof of historical authenticity."""
    key=os.getenv("OPENAI_API_KEY","")
    if not key or candidate.get("state")!="license_metadata_pass":
        return {"state":"not_checked","reason":"No API key or license metadata not approved"}
    prompt=("Assess whether this Wikimedia Commons image is visibly relevant to the "
        "following inspiration. Do not identify people from their faces. Use the file "
        "title and image description as context, but flag uncertain provenance. "
        "Return JSON with relevant (boolean), confidence (low/medium/high), "
        "issues (array), explanation (string). "
        "Inspiration: "+json.dumps({"title":item.get("title"),"body":item.get("body"),
            "category":item.get("category")})+
        "\nFile title: "+candidate.get("fileTitle","")+
        "\nDescription: "+candidate.get("description",""))
    payload={"model":os.getenv("OPENAI_IMAGE_REVIEW_MODEL","gpt-4.1-mini"),
        "input":[{"role":"user","content":[{"type":"input_text","text":prompt},
            {"type":"input_image","image_url":candidate["imageUrl"]}]}],
        "text":{"format":{"type":"json_object"}}}
    try:
        req=urllib.request.Request("https://api.openai.com/v1/responses",
            data=json.dumps(payload).encode(),headers={"Authorization":"Bearer "+key,
                "Content-Type":"application/json"})
        with urllib.request.urlopen(req,timeout=90) as resp:
            response=json.load(resp)
        output="".join(p.get("text","") for o in response.get("output",[])
            for p in o.get("content",[]) if p.get("type")=="output_text")
        verdict=json.loads(output)
        return {"state":"relevant_candidate" if verdict.get("relevant") and
            verdict.get("confidence")=="high" else "needs_visual_review",
            "confidence":verdict.get("confidence","low"),
            "issues":verdict.get("issues",[]),"explanation":verdict.get("explanation","")}
    except Exception as exc:
        return {"state":"visual_review_failed","reason":str(exc)[:250]}

def subject_queries(item):
    if item.get("id") in QUERIES:
        return QUERIES[item["id"]]
    title=item.get("title","").strip()
    body=item.get("body","")
    # Do not use institution/source attribution as a search term.
    return [title+" "+body[:85],title]

def candidates(item):
    found={};errors=[]
    for query in subject_queries(item):
        try:
            for page in search(query):
                result=verify(page)
                if result["fileTitle"]:
                    found[result["fileTitle"]]=result
        except Exception as exc:
            errors.append(query+": "+str(exc)[:180])
    def relevance_priority(candidate):
        title=candidate["fileTitle"].lower()
        item_id=item.get("id","")
        penalize=any(word in title for word in ("sculpture","statue","bust","plaque","museum","replica","model"))
        if item_id=="curie-nobel":
            priority=("curie" in title and ("portrait" in title or "1903" in title))
        elif item_id=="apollo-11":
            priority=("aldrin" in title or "apollo 11" in title)
        elif item_id=="wright-flight":
            priority=("first flight" in title or "1903" in title)
        elif item_id=="everest-summit":
            priority=("hillary" in title and "tenzing" in title)
        elif item_id=="mandela-release":
            priority=("mandela" in title and ("1990" in title or "release" in title))
        else:
            priority=False
        return (candidate["state"]!="license_metadata_pass",penalize,not priority,title)
    ranked=sorted(found.values(),key=relevance_priority)
    for candidate in ranked[:3]:
        candidate["visualCheck"]=visual_check(item,candidate)
    return ranked[:10],errors

def write(path,data):
    path.write_text(json.dumps(data,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")

def persist():
    subprocess.run(["git","add",IMAGES.name,STATUS.name,REVIEWS.name],check=True)
    if subprocess.run(["git","diff","--cached","--quiet"]).returncode:
        subprocess.run(["git","commit","-m","Audit image candidates without changing article content"],check=True)
        subprocess.run(["git","push","origin","HEAD:main"],check=True)

def audit(items,existing=None):
    result=existing or {"items":{}}
    report={"checkedAt":now(),"processed":0,"withCandidates":0,"withLicenseMetadataPass":0,
            "errors":0,"publicationReady":0,"state":"completed_pending_visual_review"}
    for item in items:
        choices,errors=candidates(item)
        result["items"][item["id"]]={"checkedAt":now(),"queries":subject_queries(item),
            "candidates":choices,"errors":errors,"selected":None,
            "state":"awaiting_visual_and_license_review"}
        report["processed"]+=1
        report["withCandidates"]+=bool(choices)
        report["withLicenseMetadataPass"]+=any(x["state"]=="license_metadata_pass" for x in choices)
        report["errors"]+=len(errors)
    return result,report

def main():
    feed=json.loads(FEED.read_text(encoding="utf-8"))
    reviews=json.loads(REVIEWS.read_text(encoding="utf-8"))
    images=json.loads(IMAGES.read_text(encoding="utf-8")) if IMAGES.exists() else {"items":{}}
    batch=max(1,min(100,int(os.getenv("IMAGE_AUDIT_BATCH_SIZE","10"))))
    only_missing=os.getenv("IMAGE_AUDIT_ONLY_MISSING","false").lower()=="true"
    items=[i for i in feed["items"] if i.get("status")!="published" and i["id"] in reviews.get("items",{})]
    if only_missing:
        items=[i for i in items if i["id"] not in images["items"]]
    items=items[:batch]
    images,report=audit(items,images)
    for item in items:
        reviews["items"][item["id"]]["imageStatus"]="awaiting_visual_and_license_review"
        reviews["items"][item["id"]]["publication"]="held_for_editorial_and_image_approval"
    write(IMAGES,images);write(REVIEWS,reviews);write(STATUS,report)
    persist()
    print(json.dumps(report,indent=2))

if __name__=="__main__":
    main()
