"""Conservative Wikimedia Commons image discovery and license metadata verification.

Never equate image availability with permission. Only accept explicit, machine-readable
CC0/Public Domain/CC BY/CC BY-SA metadata and store provenance for editorial audit.
"""
import html
import json
import re
import urllib.parse
import urllib.request

API="https://commons.wikimedia.org/w/api.php"
ALLOWED={"cc0","public domain","pd","cc-by-4.0","cc-by-sa-4.0",
         "cc-by-3.0","cc-by-sa-3.0","cc-by-2.0","cc-by-sa-2.0"}

def request(params):
    url=API+"?"+urllib.parse.urlencode({"format":"json",**params})
    req=urllib.request.Request(url,headers={"User-Agent":"MyDayCoachEditorial/1.0 (image metadata audit)"})
    with urllib.request.urlopen(req,timeout=20) as response:
        return json.load(response)

def plain(text):
    return re.sub(r"<[^>]+>"," ",html.unescape(str(text or ""))).strip()

def discover(title,limit=8):
    search=request({"action":"query","generator":"search","gsrsearch":title,
        "gsrnamespace":6,"gsrlimit":limit,"prop":"imageinfo",
        "iiprop":"url|mime|extmetadata","iiurlwidth":1200})
    pages=search.get("query",{}).get("pages",{})
    return [pages[k] for k in pages]

def verify(candidate):
    info=(candidate.get("imageinfo") or [{}])[0]
    meta=info.get("extmetadata",{})
    def m(key):
        return plain(meta.get(key,{}).get("value",""))
    license_code=m("LicenseShortName").lower().replace(" ","-")
    license_url=m("LicenseUrl")
    usage=m("UsageTerms").lower()
    creator=m("Artist")
    attribution=m("Attribution") or creator
    source=info.get("descriptionurl","")
    image_url=info.get("thumburl") or info.get("url","")
    mime=info.get("mime","")
    permitted=license_code in ALLOWED and source.startswith("https://") and image_url.startswith("https://") and mime in ("image/jpeg","image/png","image/webp")
    # Ambiguous copyright statements must always be escalated.
    if "non-commercial" in usage or "permission" in usage or "fair use" in usage:
        permitted=False
    return {"state":"license_metadata_pass" if permitted else "needs_manual_license_review",
        "fileTitle":candidate.get("title",""),"imageUrl":image_url,
        "descriptionUrl":source,"creator":creator,"attribution":attribution,
        "license":license_code,"licenseUrl":license_url,"usageTerms":m("UsageTerms"),
        "mime":mime,"requiresVisualReview":True,
        "note":"Metadata check is not legal clearance or visual relevance verification."}

def candidates(title):
    try:
        return [verify(p) for p in discover(title)]
    except Exception as error:
        return [{"state":"image_search_failed","reason":str(error)[:250]}]
