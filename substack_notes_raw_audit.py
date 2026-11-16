#!/usr/bin/env python3
"""Offline analysis of raw Gateway/Substack profile-feed JSON from an allowed source.

No requests, cookies, full bodies, or paid content. Unlike Gateway's simplified
NotesPageResponse, raw feed items MAY have type and parentComments fields.
Those fields are preserved only as diagnostic signals: their presence alone
does not establish that a Note is an original, reply or restack.
"""
import argparse
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TARGET_HANDLE = "mistery0789"
BEIJING = ZoneInfo("Asia/Shanghai")
ENTITY_KEY = re.compile(r"^comment-(\d+)$")


def _beijing(value):
    if not isinstance(value, str):
        raise ValueError("missing context.timestamp")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid context.timestamp") from exc
    if dt.tzinfo is None:
        raise ValueError("context.timestamp has no timezone")
    return dt.astimezone(BEIJING).isoformat()


def _record(item):
    """Extract metadata only; return (record, error), never copy body."""
    if not isinstance(item, dict):
        return None, "not_an_object"
    comment = item.get("comment")
    context = item.get("context")
    if not isinstance(comment, dict) or not isinstance(context, dict):
        return None, "missing_comment_or_context"
    comment_id = comment.get("id")
    if isinstance(comment_id, bool) or not isinstance(comment_id, int) or comment_id <= 0:
        return None, "invalid_comment_id"

    key = item.get("entity_key")
    if not isinstance(key, str):
        return None, "missing_entity_key"
    match = ENTITY_KEY.fullmatch(key)
    if match is None or int(match.group(1)) != comment_id:
        return None, "entity_key_id_mismatch"

    users = context.get("users")
    if not isinstance(users, list):
        return None, "missing_context_users"
    context_handles = [
        str(u.get("handle", "")).strip().lower().lstrip("@")
        for u in users if isinstance(u, dict)
    ]
    comment_handle = str(comment.get("handle") or "").strip().lower().lstrip("@")

    if comment_handle:
        if comment_handle != TARGET_HANDLE:
            return None, "comment_author_mismatch"
        attribution_basis = "comment.handle"
    elif len(context_handles) == 1 and context_handles[0] == TARGET_HANDLE:
        # A feed context user is not guaranteed to be the comment author.
        attribution_basis = "single_context_user_provisional"
    else:
        return None, "ambiguous_author"
    try:
        published = _beijing(context.get("timestamp"))
    except ValueError:
        return None, "invalid_timestamp"

    parents = item.get("parentComments")
    if parents is not None and not isinstance(parents, list):
        return None, "malformed_parent_comments"
    upstream_type = item.get("type")
    if upstream_type is not None and not isinstance(upstream_type, str):
        return None, "malformed_upstream_type"

    # Prove no more than the data says: a parent context is a signal, not a
    # verified relationship; a referenced post is not automatically a restack.
    evidence = {
        "upstream_type": upstream_type,
        "has_parent_context": bool(parents),
        "has_post_reference": isinstance(item.get("post"), dict),
    }
    return {
        "note_id": comment_id,
        "author_handle": TARGET_HANDLE,
        "attribution_basis": attribution_basis,
        "attribution_verified_externally": False,
        "published_at_beijing": published,
        "content_kind": "unverified",
        "canonical_url": None,
        "evidence": evidence,
        "full_body_saved": False,
    }, None


def audit_raw_pages(pages):
    if not isinstance(pages, list) or not pages:
        raise ValueError("At least one page required")
    accepted = {}
    rejected = []
    repeats = 0
    cursor_outputs = []
    page_sizes = []
    for pidx, page in enumerate(pages, 1):
        if not isinstance(page, dict) or not isinstance(page.get("items"), list):
            raise ValueError(f"Page {pidx} must contain items list")
        nxt = page.get("nextCursor")
        if nxt is not None and (not isinstance(nxt, str) or not nxt):
            raise ValueError(f"Page {pidx} has malformed nextCursor")
        cursor_outputs.append(nxt)
        page_sizes.append(len(page["items"]))
        for pos, item in enumerate(page["items"], 1):
            record, reason = _record(item)
            if reason:
                rejected.append({"page": pidx, "item": pos, "reason": reason})
                continue
            key = record["note_id"]
            if key in accepted:
                repeats += 1
                if accepted[key]["evidence"] != record["evidence"] or accepted[key]["published_at_beijing"] != record["published_at_beijing"]:
                    rejected.append({"page": pidx, "item": pos, "reason": "duplicate_id_conflicting_metadata"})
                continue
            accepted[key] = record

    # Same nextCursor emitted twice indicates a broken/unstable page walk.
    nonempty_cursors = [c for c in cursor_outputs if c]
    repeated_cursor = len(set(nonempty_cursors)) != len(nonempty_cursors)
    truncated = bool(cursor_outputs[-1])
    premature_end = any(c is None for c in cursor_outputs[:-1])
    records = sorted(accepted.values(), key=lambda r: (r["published_at_beijing"], r["note_id"]))
    day_counts = dict(sorted(Counter(r["published_at_beijing"][:10] for r in records).items()))
    warnings = [
        "Offline input only; no live Substack access or completeness guarantee.",
        "Gateway profile endpoint applies types=note; replies/restacks may be absent.",
        "Raw parentComments, type and post references are evidence only, not validated classifications.",
        "A context.users entry does not independently prove comment authorship.",
        "Never infer a canonical Note URL from its numeric ID.",
        "Page exhaustion does not prove all deleted, historical, replied-to, or restacked content was captured.",
    ]
    if truncated:
        warnings.append("Last page exposes nextCursor: provided pages are incomplete.")
    if repeated_cursor:
        warnings.append("Repeated nextCursor detected: pagination may be looping.")
    if premature_end:
        warnings.append("A nonfinal page has no nextCursor: page order/continuity is suspect.")
    if rejected:
        warnings.append("Some records were rejected; inspect rejected reasons.")
    return {
        "schema_version": 1,
        "subject": TARGET_HANDLE,
        "status": "offline_partial",
        "complete": False,
        "network_scraping": False,
        "pages_supplied": len(pages),
        "page_sizes": page_sizes,
        "last_cursor_present": truncated,
        "repeated_next_cursor": repeated_cursor,
        "premature_cursor_end": premature_end,
        "provisional_records": len(records),
        "duplicates": repeats,
        "records_by_beijing_day": day_counts,
        "rejected": rejected,
        "records": records,
        "warnings": warnings,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, nargs="+", required=True, help="Permitted raw JSON pages in chronological retrieval order")
    p.add_argument("--output", type=Path, required=True, help="Private local JSON report")
    a = p.parse_args()
    pages = []
    for path in a.input:
        pages.append(json.loads(path.read_text(encoding="utf-8")))
    report = audit_raw_pages(pages)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Offline-only: {report['provisional_records']} IDs; {report['duplicates']} duplicates; "
          f"{len(report['rejected'])} rejected; coverage=partial")


if __name__ == "__main__":
    main()
