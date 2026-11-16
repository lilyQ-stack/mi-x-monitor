#!/usr/bin/env python3
"""Read Open RSS's public MI Notes feed and retain links/metadata, not text.

This is an RSS client for an opt-in public feed distributed by Open RSS.
No direct Substack network calls, login cookies, paid content, or full text.
A snapshot is inherently partial and NEVER establishes total author activity.
"""
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
import xml.etree.ElementTree as ET

OPENRSS_FEED = "https://openrss.org/substack.com/@mistery0789"
MAX_BYTES = 1_000_000
ATOM = "{http://www.w3.org/2005/Atom}"
BEIJING = __import__("zoneinfo", fromlist=["ZoneInfo"]).ZoneInfo("Asia/Shanghai")


class OpenRSSRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urlsplit(newurl).hostname != "openrss.org":
            raise ValueError("Refusing redirect outside Open RSS")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def get_feed():
    req = Request(OPENRSS_FEED, headers={
        "User-Agent": "MI-Notes-Reader/0.1 (+public RSS reader)",
        "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml"
    })
    with build_opener(OpenRSSRedirects()).open(req, timeout=16) as resp:
        raw = resp.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError("Feed exceeds safe size")
        return raw


def _time(value):
    try:
        parsed = parsedate_to_datetime(value)
    except (ValueError, TypeError, IndexError):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp missing timezone")
    return parsed.astimezone(BEIJING).isoformat()


def _kind_hint(title):
    t = (title or "").strip().lower()
    if t.startswith("commented on"):
        return "maybe_reply"
    if t.startswith("restacked"):
        return "maybe_restack"
    return "unverified"


def _entry(link, guid, pub_date, title):
    from substack_notes_import import normalize_url
    link = normalize_url(link)
    if not link or not pub_date:
        raise ValueError("Missing entry link or date")
    # Feed is authored by a third party: target ownership needs spot-checking.
    host = urlsplit(link).hostname
    path = urlsplit(link).path
    attributed = (host == "substack.com" and path.lower().startswith("/@mistery0789/")) or host == "mistery0789.substack.com"
    key = hashlib.sha256((guid or link).encode("utf-8")).hexdigest()[:24]
    return {
        "id": key,
        "source_guid_hash": hashlib.sha256((guid or "").encode("utf-8")).hexdigest()[:12] if guid else None,
        "url": link,
        "published_at_beijing": _time(pub_date),
        "kind_hint": _kind_hint(title),
        "author_attribution": "link_target_matches" if attributed else "requires_manual_check",
        "complete_text_saved": False,
        "source": "openrss_mistery0789_user_feed",
    }


def parse_feed(raw):
    if len(raw) > MAX_BYTES or b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise ValueError("Unsafe or oversized XML")
    root = ET.fromstring(raw)
    source = []
    if root.tag == "rss":
        channel = root.find("channel")
        if channel is None:
            raise ValueError("RSS channel missing")
        for it in channel.findall("item"):
            source.append((
                it.findtext("link"), it.findtext("guid"),
                it.findtext("pubDate"), it.findtext("title")
            ))
    elif root.tag == ATOM + "feed":
        for it in root.findall(ATOM + "entry"):
            link = ""
            for l in it.findall(ATOM + "link"):
                if l.get("rel") in (None, "alternate"):
                    link = l.get("href", "")
                    break
            source.append((link, it.findtext(ATOM + "id"),
                           it.findtext(ATOM + "published") or it.findtext(ATOM + "updated"),
                           it.findtext(ATOM + "title")))
    else:
        raise ValueError("Unexpected content: not RSS/Atom")

    result, rejected = [], []
    for i, (link, guid, stamp, title) in enumerate(source, 1):
        try:
            result.append(_entry(link or "", guid or "", stamp or "", title or ""))
        except (ValueError, TypeError) as exc:
            rejected.append({"position": i, "reason": type(exc).__name__})
    return result, rejected


def merge(records, known):
    by_key = {r["id"]: r for r in known if isinstance(r, dict) and "id" in r}
    nnew = 0
    for record in records:
        if record["id"] not in by_key:
            by_key[record["id"]] = record
            nnew += 1
        elif by_key[record["id"]]["kind_hint"] == "unverified" and record["kind_hint"] != "unverified":
            by_key[record["id"]]["kind_hint"] = record["kind_hint"]
    return sorted(by_key.values(), key=lambda x: (x["published_at_beijing"], x["id"])), nnew


def run(store):
    now = datetime.now(timezone.utc).isoformat()
    path = store / "data" / "substack_notes" / "observed.json"
    health_path = store / "state" / "substack-openrss-latest.json"
    old = []
    if path.exists():
        prior = json.loads(path.read_text(encoding="utf-8"))
        old = prior.get("items", [])
    try:
        raw = get_feed()
        records, rejected = parse_feed(raw)
        updated, nnew = merge(records, old)
        by_day = {}
        for item in updated:
            day = item["published_at_beijing"][:10]
            by_day[day] = by_day.get(day, 0) + 1
        payload = {
            "schema_version": 1, "subject": "mistery0789",
            "status": "partial", "complete": False, "source": OPENRSS_FEED,
            "items": updated,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        status = {
            "checked_utc": now, "source": OPENRSS_FEED,
            "status": "partial", "complete": False,
            "snapshot_count": len(records),
            "new_items": nnew, "cumulative_items": len(updated),
            "by_beijing_day_observed": dict(sorted(by_day.items())),
            "rejected_count": len(rejected),
            "coverage_warning": "RSS snapshot is not a complete or official list of author activity; link attribution and coverage unverified.",
        }
    except Exception as exc:
        status = {
            "checked_utc": now, "source": OPENRSS_FEED,
            "status": "error", "complete": False,
            "error_type": type(exc).__name__,
            "coverage_warning": "Fetch/parse error: do not infer zero posts. Previously observed data is unchanged.",
        }
    health_path.parent.mkdir(parents=True, exist_ok=True)
    health_path.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(status, ensure_ascii=False))
    return 0 if status["status"] == "partial" else 2


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--store", type=Path, default=Path("."))
    args = p.parse_args()
    sys.exit(run(args.store))
