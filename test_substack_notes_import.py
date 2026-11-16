"""Tests are offline; no Substack access, credentials or network."""
import csv
import json
import tempfile
import unittest
from pathlib import Path

from substack_notes_import import convert_date, normalize, normalize_url, import_csv


class NotesImportTests(unittest.TestCase):
    def test_url_tracking_removed(self):
        a = "https://substack.com/@mistery0789/note/c-123?utm_source=share&r=abc#comment"
        self.assertEqual(normalize_url(a), "https://substack.com/@mistery0789/note/c-123")

    def test_host_rejected(self):
        for u in ("https://substack.com.evil.test/note/a", "file:///etc/passwd", "https://x.com/a"):
            with self.assertRaises(ValueError):
                normalize_url(u)

    def test_beijing_timezone(self):
        self.assertEqual(convert_date("2026-11-15T23:00:00Z"), "2026-11-16T07:00:00+08:00")

    def test_naive_time_rejected(self):
        with self.assertRaises(ValueError):
            convert_date("2026-11-15T08:00:00")

    def test_wrong_author_rejected(self):
        with self.assertRaises(ValueError):
            normalize({"author_handle": "other", "url": "https://substack.com/note/c-1", "published_at": "2026-11-15"})

    def test_unverified_even_with_expected_author(self):
        row = {"author_handle": "@mistery0789", "url": "https://substack.com/@mistery0789/note/c-1", "published_at": "2026-11-15", "kind": "note"}
        self.assertFalse(normalize(row)["attribution_verified"])

    def test_dedupe_and_partial_state(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "source.csv"
            output = Path(temp) / "output.json"
            rows = [
                {"author_handle": "mistery0789", "url": "https://substack.com/@mistery0789/note/c-1?utm_source=a", "published_at": "2026-11-15", "kind": "note", "reader_summary": "my summary"},
                {"author_handle": "mistery0789", "url": "https://substack.com/@mistery0789/note/c-1?utm_source=b", "published_at": "2026-11-15", "kind": "note", "reader_summary": "my summary"}
            ]
            with path.open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
            self.assertEqual(import_csv(path, output), (2, 1))
            self.assertEqual(import_csv(path, output), (2, 1))
            data = json.loads(output.read_text(encoding="utf-8"))
            self.assertFalse(data["complete"])
            self.assertFalse(data["network_scraping"])
            self.assertEqual(len(data["items"]), 1)


if __name__ == "__main__":
    unittest.main()
