"""Offline regression tests for Substack RSS parsing and merge behavior."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import collect_substack as c

SAMPLE = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<item><title>Public note A</title><link>https://mistery0789.substack.com/p/test-a?utm_source=rss</link>
<pubDate>Sat, 14 Nov 2026 01:00:00 GMT</pubDate><description>&lt;p&gt;Public excerpt&lt;/p&gt;</description></item>
<item><title>Public note B</title><link>https://mistery0789.substack.com/p/test-b</link>
<pubDate>Fri, 13 Nov 2026 18:00:00 GMT</pubDate></item>
</channel></rss>"""


class FeedTest(unittest.TestCase):
    def test_beijing_date_and_strip_tracking(self):
        records = c.read_feed(SAMPLE)
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["date_beijing"], "2026-11-14")
        self.assertEqual(records[1]["date_beijing"], "2026-11-14")
        self.assertEqual(records[0]["url"], "https://mistery0789.substack.com/p/test-a")
        self.assertEqual(records[0]["excerpt"], "Public excerpt")

    def test_bad_xml_is_error_not_no_posts(self):
        with self.assertRaises(Exception):
            c.read_feed(b"bad")

    def test_merge_preserves_old_items(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(c, "DATA", Path(folder)):
                original = c.read_feed(SAMPLE)
                self.assertEqual(c.merge_day("2026-11-14", original[:1]), 1)
                self.assertEqual(c.merge_day("2026-11-14", original), 2)
                self.assertEqual(c.merge_day("2026-11-14", original[:1]), 2)
                saved = json.loads((Path(folder) / "2026-11-14.json").read_text())
                self.assertEqual(len(saved["items"]), 2)
                self.assertFalse(saved["complete"])


if __name__ == "__main__":
    unittest.main()
