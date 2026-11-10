#!/usr/bin/env python3
"""Mark app refresh failed if generation or editorial processing exits early."""
import datetime as dt
import json
from pathlib import Path
p=Path(__file__).resolve().parents[1]/"refresh-status.json"
if p.exists():
    data=json.loads(p.read_text(encoding="utf-8"))
    if data.get("state")=="running":
        data["state"]="failed"
        data["error"]="Generation or editorial review workflow failed; retry to resume this batch"
        data["completedAt"]=dt.datetime.now(dt.timezone.utc).isoformat()
        p.write_text(json.dumps(data,indent=2)+"\n",encoding="utf-8")
