"""Discover subject-specific sources and retain URLs for an evidence audit."""
import json
import urllib.parse
import urllib.request
import re
import unicodedata

API="https://en.wikipedia.org/w/api.php"
PILOT_QUERIES={"curie-nobel":"Marie Curie Nobel Prize",
    "everest-summit":"1953 British Mount Everest expedition Hillary Tenzing",
    "wright-flight":"Wright brothers first powered flight 1903",
    "mandela-release":"Release of Nelson Mandela 1990",
    "apollo-11":"Apollo 11 mission 1969"}
HEADERS={"User-Agent":"MyDayCoachEditorial/1.1 (research; github.com/jay-ds-labs/mydaycoach-inspirations)"}

def words(value):
    value=unicodedata.normalize("NFKD",str(value)).encode("ascii","ignore").decode().lower()
    return {w for w in re.findall(r"[a-z]{3,}",value) if w not in {
        "the","and","with","from","that","this","for","how","what","why","into","was",
        "his","her","their","life","lesson","inspiration","discipline","mindset","american",
        "english","philosopher","historian","author","scientist","born","century"}}

def subject_query(item):
    attribution=re.split(r"[,;(–—]|\d",item.get("attribution", ""))[0].strip()
    if attribution.lower() in ("mydaycoach","unknown","anonymous"):
        attribution=""
    return attribution or item.get("title", "").split(":")[0]

def relevant(record,item):
    subject=words(subject_query(item))
    if not subject:
        return True
    identity=words(record.get("title", "")+" "+record.get("url", "").replace("_"," "))
    text=words(record.get("text", ""))
    # A country or broad topic is not a substitute for the requested person's account.
    return len(subject & identity)>=min(2,len(subject)) or len(subject & text)>=min(2,len(subject))

def select_passages(text,query,budget=14000):
    """Keep context plus matching passages throughout the document, not only its lead."""
    if len(text)<=budget:
        return text
    terms=words(query)
    chunks=[text[i:i+1600] for i in range(0,len(text),1400)]
    ranked=sorted(range(len(chunks)),key=lambda i:len(words(chunks[i]) & terms),reverse=True)
    chosen={0};used=len(chunks[0])
    for i in ranked:
        if i in chosen or not terms & words(chunks[i]):continue
        if used+len(chunks[i])>budget:continue
        chosen.add(i);used+=len(chunks[i])
    return "\n[excerpt]\n".join(chunks[i] for i in sorted(chosen))

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
        "exlimit":limit})).get("query",{}).get("pages",{})
    results=[]
    for hit in hits:
        p=pages.get(str(hit["pageid"]),{})
        content=p.get("extract","")
        if len(content)>450:
            results.append({"url":"https://en.wikipedia.org/wiki/"+
                urllib.parse.quote(hit["title"].replace(" ","_")),
                "title":hit["title"],"text":select_passages(content,query),"origin":"wikipedia"})
    return results

def wikipedia_exact(title):
    pages=get_json(API+"?"+urllib.parse.urlencode({"action":"query","titles":title,"redirects":1,
        "prop":"extracts","explaintext":1,"exlimit":1,"format":"json"})).get("query",{}).get("pages",{})
    results=[]
    for page in pages.values():
        content=page.get("extract","")
        if len(content)>450:
            results.append({"url":"https://en.wikipedia.org/wiki/"+
                urllib.parse.quote(page["title"].replace(" ","_")),
                "title":page["title"],"text":select_passages(content,title),"origin":"wikipedia"})
    return results

def discover(item,existing_source="",fetch=None):
    fetch=fetch or (lambda url: ("","No fetcher configured"))
    records=[];errors=[]
    if specific(existing_source):
        content,error=fetch(existing_source)
        if content and len(content)>450:
            records.append({"url":existing_source,"title":"Provided source",
                            "text":select_passages(content,item.get("body","")+" "+item.get("title","")),"origin":"institutional"})
        elif error:
            errors.append(error)
    title=item.get("title","")
    attribution=item.get("attribution","")
    query=PILOT_QUERIES.get(item.get("id")," ".join(x for x in (attribution,title) if x).strip() or item.get("body","")[:100])
    try:
        queries=list(dict.fromkeys([PILOT_QUERIES.get(item.get("id"),""),subject_query(item),title]))
        for candidate in filter(None,queries):
            matches=wikipedia_exact(candidate)
            if not matches:matches=wikipedia(candidate,limit=2)
            seen={r["url"] for r in records}
            records.extend(x for x in matches if x["url"] not in seen and relevant(x,item))
            if len(records)>=2:break
    except Exception as exc:
        errors.append("Wikipedia lookup failed: "+str(exc)[:160])
    return records[:4],errors

def evidence_bundle(records):
    return "\n\n".join("[SOURCE "+str(i+1)+"] "+r["title"]+" "+r["url"]+
        "\n"+r["text"][:14000] for i,r in enumerate(records))[:30000]

