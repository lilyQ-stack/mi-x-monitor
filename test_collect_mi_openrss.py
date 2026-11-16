"""Offline tests for accumulating public RSS metadata; no network."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from collect_mi_openrss import parse_feed, merge, run, _entry

EXAMPLE = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>Test</title>
<item><guid>entry-A</guid><link>https://substack.com/@mistery0789/note/c-1</link>
<title>Commented on a Note</title><pubDate>Mon, 16 Nov 2026 08:00:00 GMT</pubDate><description>Private synthetic body never persisted</description></item>
<item><guid>entry-B</guid><link>https://substack.com/@mistery0789/note/c-2?utm_source=test</link>
<title>Restacked a Note</title><pubDate>Mon, 16 Nov 2026 08:01:00 GMT</pubDate></item>
</channel></rss>"""


class RSSCollectionTests(unittest.TestCase):
    def test_parse_and_types_provisional(self):
        rows, errs = parse_feed(EXAMPLE)
        self.assertEqual(len(rows), 2)
        self.assertFalse(errs)
        self.assertEqual(rows[0]["kind_hint"], "maybe_reply")
        self.assertEqual(rows[1]["kind_hint"], "maybe_restack")
        self.assertTrue(all(x["complete_text_saved"] is False for x in rows))
        self.assertEqual(rows[0]["published_at_beijing"], "2026-11-16T16:00:00+08:00")
        self.assertNotIn("Private synthetic body", str(rows))
        self.assertNotIn("utm_source", rows[1]["url"])

    def test_missing_timestamp_rejected_without_claiming_completeness(self):
        bad = b'<rss><channel><item><link>https://substack.com/@mistery0789/note/c-1</link><title>test</title></item></channel></rss>'
        rows, errors = parse_feed(bad)
        self.assertFalse(rows)
        self.assertEqual(len(errors), 1)

    def test_merge_dedup(self):
        rows, _ = parse_feed(EXAMPLE)
        combined, new = merge(rows, [])
        self.assertEqual(new, 2)
        combined_again, new2 = merge(rows, combined)
        self.assertEqual(new2, 0)
        self.assertEqual(len(combined_again), 2)

    def test_persist_metadata_and_not_text(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch("collect_mi_openrss.get_feed", return_value=EXAMPLE):
                self.assertEqual(run(Path(temp)), 0)
                self.assertEqual(run(Path(temp)), 0)
            raw = (Path(temp) / "data/substack_notes/observed.json").read_text(encoding="utf-8")
            db = json.loads(raw)
            self.assertEqual(len(db["items"]), 2)
            self.assertFalse(db["complete"])
            self.assertNotIn("Private synthetic body", raw)
            health = json.loads((Path(temp) / "state/substack-openrss-latest.json").read_text(encoding="utf-8"))
            self.assertEqual(health["new_items"], 0)
            self.assertEqual(health["status"], "partial")

    def test_fetch_error_doesnt_overwrite_previous(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch("collect_mi_openrss.get_feed", return_value=EXAMPLE):
                self.assertEqual(run(Path(temp)), 0)
            stored = (Path(temp) / "data/substack_notes/observed.json")
            previous = stored.read_text(encoding="utf-8")
            with patch("collect_mi_openrss.get_feed", side_effect=OSError("network unavailable")):
                self.assertEqual(run(Path(temp)), 2)
            self.assertEqual(stored.read_text(encoding="utf-8"), previous)
            health = json.loads((Path(temp) / "state/substack-openrss-latest.json").read_text(encoding="utf-8"))
            self.assertEqual(health["status"], "error")
            self.assertFalse(health["complete"])

    def test_no_fake_author_link_claim(self):
        item = _entry("https://substack.com/@other/note/c-999", "x", "Mon, 16 Nov 2026 08:00:00 GMT", "random")
        self.assertEqual(item["author_attribution"], "requires_manual_check")


if __name__ == "__main__":
    unittest.main()
