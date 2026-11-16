#!/usr/bin/env python3
"""Offline parser for an API Direct User Activity JSON response.

The API is NOT called by this tool. It does not handle credentials, request
content from third parties, or save full original bodies. Schema is based on
API Direct's public docs and must be validated against real authorized data.
"""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from substack_notes_import import normalize_url

TARGET = "mistery0789"
BJ = ZoneInfo("Asia/Shanghai")
ACTIVITY = {"note", "post", "reply", "restack", "like"}


def _date_utc(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("date missing")
    value = value.strip()
    # API Direct documents this naive date form as UTC.
    d = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(BJ).isoformat()


def normalize_activity_response(data):
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        raise ValueError("API Direct response must have items list")
    profile = str(data.get("username") or "").strip().lower().lstrip("@")
    if profile and profile != TARGET:
        raise ValueError("Response username did not match target")
    seen, errors = {}, []
    for i, item in enumerate(data["items"], 1):
        if not isinstance(item, dict):
            errors.append({"position": i, "reason": "invalid_item"})
            continue
        author = str(item.get("author") or "").strip().lower().lstrip("@")
        if author != TARGET:
            errors.append({"position": i, "reason": "author_mismatch"})
            continue
        activity = str(item.get("activity") or "").lower()
        if activity not in ACTIVITY:
            errors.append({"position": i, "reason": "unsupported_activity"})
            continue
        try:
            link = normalize_url(item.get("url"))
            dt = _date_utc(item.get("date"))
        except (ValueError, TypeError):
            errors.append({"position": i, "reason": "missing_or_invalid_url_date"})
            continue
        uid = str(item.get("note_id") or "").strip()
        key = hashlib.sha256((f"{activity}:{uid}" if uid else f"{activity}:{link}").encode()).hexdigest()[:24]
        seen[key] = {
            "id": key,
            "url": link,
            "author_handle": TARGET,
            "published_at_beijing": dt,
            "activity": activity,
            "author_verified_by_platform": False,
            "body_saved": False,
            "source": "apidirect_user_activity_response",
        }
    return {
        "schema_version": 1,
        "subject": TARGET,
        "status": "offline_partial",
        "complete": False,
        "records": sorted(seen.values(), key=lambda x: (x["published_at_beijing"], x["id"])),
        "rejected": errors,
        "coverage_note": "Offline parsing of supplied JSON. Full API coverage and licensing not independently verified.",
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    result = normalize_activity_response(json.loads(a.input.read_text(encoding="utf-8")))
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(f"Parsed {len(result['records'])} activities; rejected {len(result['rejected'])}; coverage remains partial.")


if __name__ == "__main__":
    main()
