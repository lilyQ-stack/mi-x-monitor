"""Offline regression tests; fake samples only, no HTTP requests."""
import unittest

from substack_notes_gateway_audit import audit, parse_beijing


class GatewayAuditTests(unittest.TestCase):
    @staticmethod
    def item(note_id, handle="mistery0789", ts="2026-11-15T23:00:00Z", body="A fake private note that MUST NOT be copied"):
        return {
            "id": note_id,
            "author": {"handle": handle, "name": "Synthetic Test User"},
            "published_at": ts,
            "body": body,
            "likes_count": 9,
        }

    def test_timestamp(self):
        self.assertEqual(parse_beijing("2026-11-15T23:00:00Z"), "2026-11-16T07:00:00+08:00")

    def test_reject_naive_time(self):
        with self.assertRaises(ValueError):
            parse_beijing("2026-11-15T15:00:00")

    def test_multi_page_dedupe_filter_and_no_body_copy(self):
        pages = [
            {"items": [self.item(100), self.item(101, handle="different")], "next": "cursor-2"},
            {"items": [self.item(100), self.item(102, ts="2026-11-16T02:00:00Z")], "next": None},
        ]
        result = audit(pages)
        self.assertEqual(result["pages_supplied"], 2)
        self.assertEqual(result["distinct_provisional_items"], 2)
        self.assertEqual(result["duplicates"], 1)
        self.assertEqual(len(result["rejected_items"]), 1)
        self.assertFalse(result["complete"])
        self.assertFalse(result["live_scraping"])
        self.assertIsNone(result["records"][0]["canonical_url"])
        self.assertEqual(result["records"][0]["classification"], "unknown")
        self.assertNotIn("A fake private note", str(result))
        self.assertFalse(result["last_cursor_present"])

    def test_pagination_incomplete(self):
        result = audit([{"items": [self.item(15)], "next": "cursor-missing"}])
        self.assertTrue(result["last_cursor_present"])
        self.assertTrue(any("NOT exhausted" in warning for warning in result["warnings"]))

    def test_empty_is_partial_not_no_activity(self):
        result = audit([{"items": [], "next": None}])
        self.assertEqual(result["distinct_provisional_items"], 0)
        self.assertEqual(result["status"], "offline_partial")
        self.assertFalse(result["complete"])

    def test_invalid_shape(self):
        with self.assertRaises(ValueError):
            audit([])
        with self.assertRaises(ValueError):
            audit([{"items": None}])

    def test_invalid_id_and_timestamp(self):
        result = audit([{"items": [self.item(0), self.item(True), self.item(44, ts="2026-11-16T08:00:00")], "next": None}])
        self.assertEqual(result["distinct_provisional_items"], 0)
        self.assertEqual(len(result["rejected_items"]), 3)


if __name__ == "__main__":
    unittest.main()
