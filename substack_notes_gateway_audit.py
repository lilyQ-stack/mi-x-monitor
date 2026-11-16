#!/usr/bin/env python3
"""Offline audit of PRE-OBTAINED, PERMITTED Gateway profile Notes JSON pages.

Never makes a network request. Does not save Note text, cookies or paid content.
The Gateway's simplified profile-notes schema lacks reliable type, parent and
canonical URL fields, so these are deliberately NOT fabricated.
"""
import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TARGET = "mistery0789"
TZ = ZoneInfo("Asia/Shanghai")


def parse_beijing(value):
    if not isinstance(value, str):
        raise ValueError("published_at missing")
    d = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if d.tzinfo is None:
        raise ValueError("published_at must include timezone")
    return d.astimezone(TZ).isoformat()


def audit(pages):
    """Return safety-first audit of a sequence of provided Gateway pages.

    Input: each page is {'items': [Gateway NoteResponse, ...], 'next': cursor|null}.
    Never treat an empty result as proof that the author made zero Notes.
    """
    if not pages:
        raise ValueError("At least one page is required")
    by_id = {}
    rejected = []
    repeated = 0
    cursors = []
    page_sizes = []

    for page_num, page in enumerate(pages, 1):
        if not isinstance(page, dict) or not isinstance(page.get("items"), list):
            raise ValueError(f"Page {page_num}: expected Gateway items list")
        nxt = page.get("next")
        if nxt is not None and not isinstance(nxt, str):
            raise ValueError(f"Page {page_num}: cursor must be a string or null")
        cursors.append(nxt)
        page_sizes.append(len(page["items"]))
        for position, item in enumerate(page["items"], 1):
            if not isinstance(item, dict):
                rejected.append({"page": page_num, "position": position, "reason": "invalid_item"})
                continue
            author = item.get("author")
            handle = (author.get("handle") if isinstance(author, dict) else None)
            handle = (handle or "").strip().lower().lstrip("@")
            if handle != TARGET:
                rejected.append({"page": page_num, "position": position, "reason": "author_not_verified"})
                continue
            note_id = item.get("id")
            if isinstance(note_id, bool) or not isinstance(note_id, int) or note_id <= 0:
                rejected.append({"page": page_num, "position": position, "reason": "invalid_id"})
                continue
            try:
                stamp = parse_beijing(item.get("published_at"))
            except (ValueError, TypeError):
                rejected.append({"page": page_num, "position": position, "reason": "invalid_timestamp"})
                continue
            if note_id in by_id:
                repeated += 1
                continue
            by_id[note_id] = {
                "note_id": note_id,
                "author_handle": TARGET,
                "published_at_beijing": stamp,
                "classification": "unknown",
                "canonical_url": None,
                "attribution": "provisional_gateway_author_field",
                "body_stored": False,
            }

    warnings = [
        "No live access performed. Data provenance and author identity must be verified separately.",
        "Gateway profile-notes response cannot reliably distinguish Notes, replies and restacks.",
        "No canonical URL returned; do not invent URLs from IDs.",
        "Even an exhausted cursor does not prove total historical or deleted-content coverage.",
    ]
    if cursors[-1]:
        warnings.append("Last supplied page has a next cursor: pagination NOT exhausted.")
    if len(pages) > 1 and any(cursor is None for cursor in cursors[:-1]):
        warnings.append("A non-final page has no next cursor: page continuity is uncertain.")
    if rejected:
        warnings.append("Some records were rejected for missing or mismatched attribution/fields.")

    return {
        "schema_version": 1,
        "subject": TARGET,
        "status": "offline_partial",
        "complete": False,
        "live_scraping": False,
        "pages_supplied": len(pages),
        "page_sizes": page_sizes,
        "distinct_provisional_items": len(by_id),
        "duplicates": repeated,
        "rejected_items": rejected,
        "last_cursor_present": bool(cursors[-1]),
        "records": sorted(by_id.values(), key=lambda x: (x["published_at_beijing"], x["note_id"])),
        "warnings": warnings,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, nargs="+", required=True, help="Locally supplied authorized JSON pages in traversal order")
    parser.add_argument("--output", type=Path, required=True, help="Private JSON file, not a public GitHub commit")
    args = parser.parse_args()
    pages = []
    for path in args.input:
        with path.open(encoding="utf-8") as f:
            pages.append(json.load(f))
    result = audit(pages)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Offline audit: {result['distinct_provisional_items']} provisional IDs, "
          f"{result['duplicates']} duplicates, {len(result['rejected_items'])} rejected; status=partial")


if __name__ == "__main__":
    main()
