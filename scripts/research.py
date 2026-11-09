"""Discover subject-specific sources and retain URLs for an evidence audit."""
import json
import urllib.parse
import urllib.request

API="https://en.wikipedia.org/w/api.php"
HEADERS={"User-Agent":"MyDayCoachEditorial/1.1 (research; github.com/jay-ds-labs/mydaycoach-inspirations)"}

def get_json(url):
    req=urllib.request.Request(url,headers=HEADERS)
    with urllib.request.urlopen(req,timeout=20) as response:
        return json.load(response)

def specific(url):
    if not url.startswith("https://"):
        return False
    p=urllib.parse.urlsplit(url)
    return bool(p.path.strip("/") and p.path.strip("/") not in ("wiki","home","index.html"))

def wikipedia(query,limit=3):
    search=get_json(API+"?"+urllib.parse.urlencode({"action":"query","list":"search",
        "srsearch":query,"srlimit":limit,"format":"json"}))
    hits=search.get("query",{}).get("search",[])
    if not hits:
        return []
    ids="|".join(str(h["pageid"]) for h in hits)
    pages=get_json(API+"?"+urllib.parse.urlencode({"action":"query","pageids":ids,
        "prop":"extracts","explaintext":1,"exsectionformat":"plain","format":"json",
        "exchars":10000})).get("query",{}).get("pages",{})
    results=[]
    for hit in hits:
        p=pages.get(str(hit["pageid"]),{})
        content=p.get("extract","")
        if len(content)>450:
            results.append({"url":"https://en.wikipedia.org/wiki/"+
                urllib.parse.quote(hit["title"].replace(" ","_")),
                "title":hit["title"],"text":content[:11000],"origin":"wikipedia"})
    return results

def discover(item,existing_source="",fetch=None):
    fetch=fetch or (lambda url: ("","No fetcher configured"))
    records=[];errors=[]
    if specific(existing_source):
        content,error=fetch(existing_source)
        if content and len(content)>450:
            records.append({"url":existing_source,"title":"Provided source",
                            "text":content[:11000],"origin":"institutional"})
        elif error:
            errors.append(error)
    title=item.get("title","")
    attribution=item.get("attribution","")
    query=" ".join(x for x in (attribution,title) if x).strip() or item.get("body","")[:100]
    try:
        matches=wikipedia(query)
        if not matches and attribution:
            matches=wikipedia(attribution)
        if not matches:
            matches=wikipedia(title)
        seen={r["url"] for r in records}
        records.extend(x for x in matches if x["url"] not in seen)
    except Exception as exc:
        errors.append("Wikipedia lookup failed: "+str(exc)[:160])
    return records[:4],errors

def evidence_bundle(records):
    return "\n\n".join("[SOURCE "+str(i+1)+"] "+r["title"]+" "+r["url"]+
        "\n"+r["text"][:10000] for i,r in enumerate(records))[:30000]
