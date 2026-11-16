"""Offline tests for the third-party feed compatibility probe. No network."""
import unittest
from probe_mi_openrss import inspect_feed


class OpenRSSProbeTests(unittest.TestCase):
    def test_rss_notes_replies_restacks(self):
        raw = b"""<?xml version="1.0"?>
        <rss version="2.0"><channel><title>Demo</title>
          <item><title>Restacked author X</title><link>https://substack.com/@mistery0789/note/c-1</link><guid>1</guid><pubDate>Mon, 16 Nov 2026 03:00:00 GMT</pubDate></item>
          <item><title>Commented on another Note</title><link>https://substack.com/@mistery0789/note/c-2</link><guid>2</guid></item>
          <item><title>New analysis</title><link>https://substack.com/@mistery0789/note/c-3</link><guid>3</guid></item>
        </channel></rss>"""
        r = inspect_feed(raw)
        self.assertEqual(r["items_in_current_snapshot"], 3)
        self.assertEqual(r["labels_provisional"]["maybe_restack"], 1)
        self.assertEqual(r["labels_provisional"]["maybe_reply"], 1)
        self.assertEqual(r["labels_provisional"]["other_unverified"], 1)
        self.assertEqual(r["substack_hosted_links"], 3)
        self.assertEqual(r["coverage"], "unverified_partial")

    def test_atom_feed(self):
        raw = b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>test</title><link rel="alternate" href="https://substack.com/@mistery0789/note/c-11"/><id>11</id><updated>2026-11-16T01:00:00Z</updated></entry></feed>'
        r = inspect_feed(raw)
        self.assertEqual(r["feed_type"], "atom")
        self.assertEqual(r["items_in_current_snapshot"], 1)

    def test_html_rejected(self):
        with self.assertRaises(ValueError):
            inspect_feed(b'<html><body>Blocked</body></html>')

    def test_dtd_rejected(self):
        with self.assertRaises(ValueError):
            inspect_feed(b'<!DOCTYPE rss><rss><channel/></rss>')

    def test_oversized_rejected(self):
        with self.assertRaises(ValueError):
            inspect_feed(b'a' * 1_000_001)

    def test_empty_rss_is_not_proof_of_no_notes(self):
        r = inspect_feed(b'<rss><channel><title>empty</title></channel></rss>')
        self.assertEqual(r["items_in_current_snapshot"], 0)
        self.assertEqual(r["coverage"], "unverified_partial")


if __name__ == "__main__":
    unittest.main()
