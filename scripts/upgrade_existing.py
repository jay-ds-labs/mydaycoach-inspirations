#!/usr/bin/env python3
"""Expand existing draft entries into long-form editorial candidates.
Requires OPENAI_API_KEY. Generated content remains draft pending source and image review.
"""
import json
import os
import pathlib
import subprocess
import sys
from generate_batch import generate, now, save

ROOT=pathlib.Path(__file__).resolve().parents[1]
FEED=ROOT/"library.json"
STATUS=ROOT/"upgrade-status.json"

def commit():
    subprocess.run(["git","add","library.json","upgrade-status.json"],check=True)
    subprocess.run(["git","commit","-m","Expand next draft inspiration"],check=True)
    subprocess.run(["git","push","origin","HEAD:main"],check=True)

def main():
    feed=json.loads(FEED.read_text())
    drafts=[x for x in feed["items"] if x.get("status")!="published"]
    status={"state":"running","completed":0,"total":len(drafts),"startedAt":now(),"completedAt":None,"error":None}
    save(STATUS,status);commit()
    try:
        for item in drafts:
            # Preserve the subject, rather than replacing it with a new unrelated article.
            category=item["category"]
            subject=item["title"]+" — "+item.get("body","")
            result=generate(category,["The new article MUST cover this exact subject: "+subject])
            item["detail"]=result["detail"]
            item["image"]=""  # Requires verified licensed image, added during review.
            item["source"]=result["source"]
            item["attribution"]=result["attribution"]
            item["takeaway"]=result["takeaway"]
            item["status"]="draft"
            item["publishedAt"]=""
            save(FEED,feed)
            status["completed"]+=1
            save(STATUS,status);commit()
        status["state"]="awaiting_review"
        status["completedAt"]=now()
    except Exception as exc:
        status["state"]="failed";status["error"]=str(exc)[:300];status["completedAt"]=now()
        raise
    finally:
        save(STATUS,status);commit()

if __name__=="__main__":
    main()
