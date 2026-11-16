#!/usr/bin/env python3
"""Offline link importer. No network calls, cookies, or scraping."""
import argparse
import csv
import hashlib
import json
from datetime import date, datetime, time
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Shanghai")
KINDS = {"note", "reply", "restack", "post", "unknown"}
DROP_PARAMS = {"fbclid", "gclid", "mc_cid", "mc_eid", "r", "token", "inbox"}


def normalize_url(value):
    u = urlsplit((value or "").strip())
    host = (u.hostname or "").lower()
    if u.scheme not in ("https", "http") or not (host == "substack.com" or host.endswith(".substack.com")):
        raise ValueError("Substack URL required")
    if u.username or u.password or u.port not in (None, 80, 443):
        raise ValueError("URL credentials and unusual ports forbidden")
    path = (u.path or "/").rstrip("/") or "/"
    query = [(k, v) for k, v in parse_qsl(u.query, keep_blank_values=True)
             if not k.lower().startswith("utm_") and k.lower() not in DROP_PARAMS]
    return urlunsplit(("https", host, path, urlencode(query), ""))


def convert_date(value):
    raw = (value or "").strip()
    if len(raw) == 10:
        dt = datetime.combine(date.fromisoformat(raw), time.min, tzinfo=TZ)
    else:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            raise ValueError("published_at must include Z or a timezone offset")
        dt = dt.astimezone(TZ)
    return dt.isoformat()


def normalize(row):
    author = (row.get("author_handle") or "").strip().lower().lstrip("@")
    if author != "mistery0789":
        raise ValueError("Unexpected author_handle; attribution still needs verification")
    url = normalize_url(row.get("url"))
    kind = (row.get("kind") or "unknown").strip().lower()
    if kind not in KINDS:
        raise ValueError("Unsupported kind")
    summary = (row.get("reader_summary") or "").strip()
    if len(summary) > 500:
        raise ValueError("reader_summary too long")
    return {
        "id": hashlib.sha256(url.encode("utf-8")).hexdigest()[:20],
        "author_handle": author,
        "url": url,
        "published_at_beijing": convert_date(row.get("published_at")),
        "kind": kind,
        "reader_summary": summary,
        "attribution_verified": False,
        "source": "user_provided_link"
    }


def import_csv(input_path, output_path):
    previous = {}
    if output_path.is_file():
        for item in json.loads(output_path.read_text(encoding="utf-8")).get("items", []):
            previous[item["url"]] = item
    count = 0
    with input_path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            item = normalize(row)
            previous[item["url"]] = item
            count += 1
    records = sorted(previous.values(), key=lambda x: (x["published_at_beijing"], x["url"]))
    result = {
        "schema_version": 1,
        "subject": "mistery0789",
        "status": "manual_partial",
        "complete": False,
        "network_scraping": False,
        "coverage_note": "Manually supplied links. No completeness or attribution guarantee.",
        "items": records
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return count, len(records)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    count, total = import_csv(args.input, args.output)
    print(f"Imported {count} rows; retained {total} unique links; coverage remains partial.")
