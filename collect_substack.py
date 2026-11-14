#!/usr/bin/env python3
"""Monitor public Substack RSS metadata; never access Gmail or paid content."""
from __future__ import annotations

import hashlib
import html
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from zoneinfo import ZoneInfo

FEED = "https://mistery0789.substack.com/feed"
BEIJING = ZoneInfo("Asia/Shanghai")
ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "substack"
STATE = ROOT / "state" / "substack-latest.json"


def clean_text(value: str | None, limit: int = 240) -> str:
    value = re.sub(r"<[^>]*>", " ", value or "")
    value = " ".join(html.unescape(value).split())
    return value[:limit]


def normalize_link(value: str) -> str:
    p = urlsplit(value.strip())
    if p.scheme not in ("http", "https") or not p.netloc:
        return ""
    return urlunsplit(("https", p.netloc.lower(), p.path.rstrip("/") or "/", "", ""))


def read_feed(xml_bytes: bytes) -> list[dict]:
    root = ET.fromstring(xml_bytes)
    channel = root.find("channel")
    if root.tag != "rss" or channel is None:
        raise ValueError("Unexpected RSS format; do not assume zero posts")
    items = []
    for node in channel.findall("item"):
        title = clean_text(node.findtext("title"), 300)
        link = normalize_link(node.findtext("link") or "")
        pub = (node.findtext("pubDate") or "").strip()
        if not title or not link or not pub:
            continue
        try:
            published = parsedate_to_datetime(pub)
            if published.tzinfo is None:
                published = published.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError, IndexError):
            continue
        local = published.astimezone(BEIJING)
        unique = hashlib.sha256(link.encode("utf-8")).hexdigest()[:20]
        items.append({
            "id": unique,
            "title": title,
            "url": link,
            "published_utc": published.astimezone(timezone.utc).isoformat(),
            "published_beijing": local.isoformat(),
            "date_beijing": local.date().isoformat(),
            "excerpt": clean_text(node.findtext("description")),
            "source": "substack_public_rss",
        })
    return items


def save_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def merge_day(day: str, additions: list[dict]) -> int:
    path = DATA / f"{day}.json"
    old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    by_id = {p["id"]: p for p in old.get("items", []) if "id" in p}
    for p in additions:
        by_id[p["id"]] = p
    items = sorted(by_id.values(), key=lambda x: x["published_utc"])
    save_json(path, {
        "date_beijing": day,
        "source": "https://mistery0789.substack.com/feed",
        "scope": "public RSS titles, links and short descriptions only; excludes Notes, live events, and subscriber-only emails",
        "complete": False,
        "items": items,
    })
    return len(items)


def main() -> int:
    checked = datetime.now(timezone.utc).isoformat()
    try:
        request = urllib.request.Request(
            FEED, headers={"User-Agent": "MI-public-feed-monitor/1.0 (RSS metadata only)", "Accept": "application/rss+xml,application/xml,text/xml"}
        )
        with urllib.request.urlopen(request, timeout=25) as response:
            data = response.read(3_000_000)
        found = read_feed(data)
        days = {}
        for item in found:
            days.setdefault(item["date_beijing"], []).append(item)
        counts = {day: merge_day(day, posts) for day, posts in days.items()}
        save_json(STATE, {
            "status": "ok",
            "checked_utc": checked,
            "rss_items_seen": len(found),
            "days_updated": counts,
            "newest_article_beijing": max((x["published_beijing"] for x in found), default=None),
            "coverage_note": "RSS is a limited public feed; no items is not evidence the author has been inactive.",
        })
        print(f"RSS success: {len(found)} feed items across {len(days)} Beijing dates")
        return 0
    except Exception as exc:
        save_json(STATE, {"status": "error", "checked_utc": checked, "error_type": type(exc).__name__,
                          "error_summary": str(exc)[:220], "coverage_note": "Fetch/parse failure: cannot infer author activity."})
        print(f"RSS failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
