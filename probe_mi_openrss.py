#!/usr/bin/env python3
"""One-time Open RSS compatibility probe; no direct Substack requests.

Only visits the Open RSS feed explicitly published for readers. Prints
non-sensitive source-health metadata, no bodies or account credentials.
NO automatic collection, scheduling, saving, or reposting.
"""
import json
import sys
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

FEED_URL = "https://openrss.org/substack.com/@mistery0789"
MAX_BYTES = 1_000_000
ATOM = "{http://www.w3.org/2005/Atom}"


def inspect_feed(raw):
    if len(raw) > MAX_BYTES:
        raise ValueError("feed too large")
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise ValueError("DTD or entity definitions prohibited")
    root = ET.fromstring(raw)
    tags = []
    entries = []
    if root.tag == "rss":
        channel = root.find("channel")
        if channel is None:
            raise ValueError("RSS without channel")
        for item in channel.findall("item"):
            entries.append({
                "link": (item.findtext("link") or "").strip(),
                "date": (item.findtext("pubDate") or "").strip(),
                "title": (item.findtext("title") or "").strip(),
                "guid": (item.findtext("guid") or "").strip(),
            })
        tags = ["rss"]
    elif root.tag == ATOM + "feed":
        for entry in root.findall(ATOM + "entry"):
            link = ""
            for node in entry.findall(ATOM + "link"):
                if node.get("rel") in (None, "alternate"):
                    link = node.get("href") or ""
                    break
            entries.append({
                "link": link,
                "date": (entry.findtext(ATOM + "published") or entry.findtext(ATOM + "updated") or "").strip(),
                "title": (entry.findtext(ATOM + "title") or "").strip(),
                "guid": (entry.findtext(ATOM + "id") or "").strip(),
            })
        tags = ["atom"]
    else:
        raise ValueError("not a recognized RSS or Atom feed")

    # Titles can be localized, shortened, or modified. Treat labels as hints only.
    labels = {"maybe_restack": 0, "maybe_reply": 0, "other_unverified": 0}
    for entry in entries:
        t = entry["title"].lower()
        if t.startswith("restacked"):
            labels["maybe_restack"] += 1
        elif t.startswith("commented on"):
            labels["maybe_reply"] += 1
        else:
            labels["other_unverified"] += 1
    from urllib.parse import urlsplit
    links = [x["link"] for x in entries]
    supported_links = sum(
        1 for link in links
        if (urlsplit(link).hostname or "").lower() == "substack.com"
        or (urlsplit(link).hostname or "").lower().endswith(".substack.com")
    )
    # No single page can prove historical completeness.
    return {
        "feed_type": tags[0],
        "items_in_current_snapshot": len(entries),
        "labels_provisional": labels,
        "substack_hosted_links": supported_links,
        "has_nonempty_guid": sum(bool(x["guid"]) for x in entries),
        "has_date_field": sum(bool(x["date"]) for x in entries),
        "sample_source_links": [x["link"] for x in entries[:3]],
        "coverage": "unverified_partial",
    }


def run():
    # Even if redirect occurs, only allow the same Open RSS host.
    class SameHostRedirectHandler(__import__("urllib.request", fromlist=["HTTPRedirectHandler"]).HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            from urllib.parse import urlsplit
            if urlsplit(newurl).hostname != "openrss.org":
                raise ValueError("redirect outside Open RSS denied")
            return super().redirect_request(req, fp, code, msg, headers, newurl)
    from urllib.request import build_opener
    opener = build_opener(SameHostRedirectHandler())
    req = Request(FEED_URL, headers={"User-Agent": "MI-Notes-RSS-probe/0.1 (+compatible RSS reader)", "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml"})
    try:
        with opener.open(req, timeout=16) as response:
            status = response.status
            content_type = response.headers.get("Content-Type", "")
            raw = response.read(MAX_BYTES + 1)
    except (HTTPError, URLError, TimeoutError, ValueError) as error:
        print(json.dumps({"status": "not_verified", "error_kind": type(error).__name__, "note": "Open RSS feed unavailable; no content claimed"}))
        return 2
    try:
        report = inspect_feed(raw)
    except (ET.ParseError, ValueError) as error:
        print(json.dumps({"status": "not_verified", "http_status": status, "content_type": content_type, "error_kind": type(error).__name__, "note": "Response not validated as a feed"}))
        return 3
    report.update({"status": "rss_parsed", "http_status": status, "content_type": content_type, "target": "mistery0789", "timestamp_utc": datetime.now(timezone.utc).isoformat()})
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(run())
