"""Offline contract tests; no API access and no stored original text."""
import unittest

from apidirect_mi_activity_adapter import normalize_activity_response


class APIDirectAdapterTests(unittest.TestCase):
    def row(self, activity, note_id, author="mistery0789", date="2026-11-16 08:00:00"):
        return {
            "activity": activity, "note_id": str(note_id), "author": author,
            "date": date,
            "url": f"https://substack.com/@mistery0789/note/c-{note_id}",
            "body": "Synthetic private long text NEVER to retain"
        }

    def test_all_activity_types_and_no_body(self):
        d = {"username": "mistery0789", "items": [
            self.row("note", 1), self.row("reply", 2),
            self.row("restack", 3), self.row("post", 4)
        ]}
        result = normalize_activity_response(d)
        self.assertEqual(len(result["records"]), 4)
        self.assertEqual(set(i["activity"] for i in result["records"]), {"note", "reply", "restack", "post"})
        self.assertTrue(all(i["published_at_beijing"].startswith("2026-11-16T16:00:00") for i in result["records"]))
        self.assertNotIn("Synthetic private long text", str(result))
        self.assertFalse(result["complete"])

    def test_wrong_author_is_rejected(self):
        d = {"username": "mistery0789", "items": [self.row("reply", 1, author="other")]}
        result = normalize_activity_response(d)
        self.assertFalse(result["records"])
        self.assertEqual(result["rejected"][0]["reason"], "author_mismatch")

    def test_wrong_profile_raises(self):
        with self.assertRaises(ValueError):
            normalize_activity_response({"username": "wrong", "items": []})

    def test_missing_activity_and_url_rejected(self):
        row = self.row("note", 1)
        row["url"] = "https://bad.example.com/"
        d = {"username": "mistery0789", "items": [row, self.row("unknown", 2)]}
        result = normalize_activity_response(d)
        self.assertEqual(len(result["rejected"]), 2)

    def test_dedupe(self):
        row = self.row("note", 1)
        result = normalize_activity_response({"username": "mistery0789", "items": [row, dict(row)]})
        self.assertEqual(len(result["records"]), 1)


if __name__ == "__main__":
    unittest.main()
