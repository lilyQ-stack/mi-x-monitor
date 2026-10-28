#!/usr/bin/env python3
"""Experimental public-activity collector. Publishes metadata, never authentication material."""
import asyncio
import base64
import json
import os
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from tempfile import TemporaryDirectory

TARGET = "wr0789"
TZ = ZoneInfo("Asia/Shanghai")
ROOT = Path(__file__).resolve().parent

def stamp():
    return datetime.now(TZ).isoformat(timespec="seconds")

def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def info(tweet, source):
    tid = str(getattr(tweet, "id", "") or "")
    created = str(getattr(tweet, "created_at_datetime", "") or getattr(tweet, "created_at", ""))
    raw = str(getattr(tweet, "text", "") or "").replace("\n", " ")
    kind = "reply" if getattr(tweet, "in_reply_to_status_id", None) else ("repost" if raw.startswith("RT @") else "post_or_quote")
    return {"id": tid, "url": f"https://x.com/{TARGET}/status/{tid}" if tid else None,
            "created_at": created, "kind": kind, "source": source,
            "excerpt": raw[:120]}

async def collect(cookies_file):
    from twikit import Client
    client = Client("en-US")
    client.load_cookies(cookies_file)
    user = await client.get_user_by_screen_name(TARGET)
    uid = str(user.id)
    posts, failures = {}, {}
    for timeline in ("Tweets", "Replies"):
        try:
            page = await client.get_user_tweets(uid, timeline, count=40)
            seen = 0
            for item in page:
                row = info(item, timeline)
                if row["id"]:
                    posts[row["id"]] = row
                    seen += 1
            # First page only: incomplete historical coverage explicitly flagged.
            failures[timeline] = {"state": "first_page_only", "items_received": seen}
        except Exception as exc:
            failures[timeline] = {"state": "error", "reason": type(exc).__name__, "detail": str(exc)[:180]}
    return list(posts.values()), failures

def parse_day(created):
    from email.utils import parsedate_to_datetime
    try:
        t = datetime.fromisoformat(created.replace("Z", "+00:00"))
    except ValueError:
        try: t = parsedate_to_datetime(created)
        except (ValueError, TypeError): return None
    if t.tzinfo is None: return None
    return t.astimezone(TZ).date().isoformat()

async def main():
    now = datetime.now(TZ)
    state = {"checked_at": stamp(), "account": TARGET, "status": "needs_auth", "complete": False,
             "message": "No X session supplied. Collection not attempted; no conclusions about posts."}
    b64 = os.getenv("X_COOKIES_BASE64", "").strip()
    if not b64:
        write_json(ROOT / "state/latest.json", state)
        print("NEEDS_AUTH: No X_COOKIES_BASE64 secret. Connectivity test completed.")
        return
    try:
        with TemporaryDirectory() as folder:
            cookie_path = Path(folder) / "cookies.json"
            cookie_path.write_bytes(base64.b64decode(b64, validate=True))
            posts, coverage = await collect(str(cookie_path))
        state.update(status="partial" if any(v["state"]=="error" for v in coverage.values()) else "unverified",
                     message="First-page collection only. Not proof of completeness.",
                     coverage=coverage, count=len(posts))
        for d in ((now - timedelta(days=1)).date(), now.date()):
            ds = d.isoformat()
            subset = [p for p in posts if parse_day(p["created_at"]) == ds]
            write_json(ROOT / f"data/{ds}.json", {"date":ds, "account":TARGET,
                "status":state["status"], "complete":False, "post_count":len(subset), "posts":subset,
                "note":"First-page snapshot only. 0 posts does NOT mean no activity."})
    except Exception as exc:
        state.update(status="error", message=f"{type(exc).__name__}: {str(exc)[:240]}")
        print("COLLECT_ERROR", type(exc).__name__)
    write_json(ROOT / "state/latest.json", state)
    print("STATUS", state["status"], "COUNT", state.get("count", 0))

if __name__ == "__main__":
    asyncio.run(main())
