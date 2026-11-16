"""Synthetic, offline-only tests for raw Gateway Notes diagnostic extraction."""
import unittest
from substack_notes_raw_audit import audit_raw_pages


def raw_item(note_id, *, handle="mistery0789", context_handles=None,
             ts="2026-11-15T23:05:00Z", parents=None, upstream_type=None,
             post=None, comment_handle=None, body="Fake author text NOT to retain"):
    if context_handles is None:
        context_handles = [handle]
    return {
        "entity_key": f"comment-{note_id}",
        "type": upstream_type,
        "context": {
            "timestamp": ts,
            "users": [{"id": idx + 10, "name": "Synthetic", "handle": h} for idx, h in enumerate(context_handles)]
        },
        "comment": {
            "id": note_id,
            "body": body,
            "handle": comment_handle,
            "reaction_count": 4,
        },
        "parentComments": [] if parents is None else parents,
        "post": post,
    }


class RawAuditTests(unittest.TestCase):
    def test_basic_metadata_without_body(self):
        result = audit_raw_pages([{"items": [raw_item(42)], "nextCursor": None}])
        self.assertEqual(result["provisional_records"], 1)
        self.assertEqual(result["records_by_beijing_day"], {"2026-11-16": 1})
        rec = result["records"][0]
        self.assertEqual(rec["content_kind"], "unverified")
        self.assertIsNone(rec["canonical_url"])
        self.assertFalse(rec["attribution_verified_externally"])
        self.assertEqual(rec["attribution_basis"], "single_context_user_provisional")
        self.assertNotIn("Fake author text", str(result))

    def test_parent_context_and_post_reference_not_guaranteed_classification(self):
        result = audit_raw_pages([{"items": [
            raw_item(100, parents=[{"id": 99, "body": "Parent from another author"}]),
            raw_item(101, upstream_type="restack", post={"id": 77, "title": "sample"}),
        ], "nextCursor": None}])
        self.assertEqual(result["provisional_records"], 2)
        self.assertTrue(result["records"][0]["evidence"]["has_parent_context"])
        self.assertEqual(result["records"][1]["evidence"]["upstream_type"], "restack")
        self.assertTrue(result["records"][1]["evidence"]["has_post_reference"])
        self.assertTrue(all(r["content_kind"] == "unverified" for r in result["records"]))
        self.assertNotIn("Parent from another author", str(result))

    def test_reject_ambiguous_and_wrong_author(self):
        result = audit_raw_pages([{"items": [
            raw_item(10, context_handles=["mistery0789", "other"]),
            raw_item(11, context_handles=["other"]),
            raw_item(12, comment_handle="other"),
        ], "nextCursor": None}])
        self.assertEqual(result["provisional_records"], 0)
        self.assertEqual([e["reason"] for e in result["rejected"]],
                         ["ambiguous_author", "ambiguous_author", "comment_author_mismatch"])

    def test_comment_handle_as_stronger_evidence(self):
        result = audit_raw_pages([{"items": [
            raw_item(10, context_handles=["other", "mistery0789"], comment_handle="mistery0789"),
        ], "nextCursor": None}])
        self.assertEqual(result["records"][0]["attribution_basis"], "comment.handle")
        self.assertFalse(result["records"][0]["attribution_verified_externally"])

    def test_reject_malformed_timestamp_and_mismatched_id(self):
        broken = raw_item(42)
        broken["entity_key"] = "comment-41"
        bad_time = raw_item(43, ts="2026-11-16T07:00:00")
        result = audit_raw_pages([{"items": [broken, bad_time], "nextCursor": None}])
        self.assertEqual(result["provisional_records"], 0)
        self.assertEqual([e["reason"] for e in result["rejected"]],
                         ["entity_key_id_mismatch", "invalid_timestamp"])

    def test_overlap_and_cursor_loop(self):
        pages = [
            {"items": [raw_item(1)], "nextCursor": "same"},
            {"items": [raw_item(1), raw_item(2)], "nextCursor": "same"},
        ]
        result = audit_raw_pages(pages)
        self.assertEqual(result["duplicates"], 1)
        self.assertTrue(result["repeated_next_cursor"])
        self.assertTrue(result["last_cursor_present"])
        self.assertFalse(result["complete"])

    def test_id_conflict_is_not_silently_merged(self):
        pages = [
            {"items": [raw_item(1)], "nextCursor": "after"},
            {"items": [raw_item(1, ts="2026-11-15T23:06:00Z")], "nextCursor": None}
        ]
        result = audit_raw_pages(pages)
        self.assertEqual(result["duplicates"], 1)
        self.assertEqual(result["rejected"][0]["reason"], "duplicate_id_conflicting_metadata")

    def test_empty_still_partial(self):
        result = audit_raw_pages([{"items": [], "nextCursor": None}])
        self.assertEqual(result["provisional_records"], 0)
        self.assertEqual(result["status"], "offline_partial")
        self.assertFalse(result["complete"])

    def test_invalid_pages(self):
        for pages in ([], [1], [{"items": None}], [{"items": [], "nextCursor": 3}]):
            with self.assertRaises(ValueError):
                audit_raw_pages(pages)


if __name__ == "__main__":
    unittest.main()
