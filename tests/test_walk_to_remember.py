"""Lauren's A Walk to Remember report (2026-11-08, adults, word lists only): every listed word
muted, prayers and hymns left alone; three crude lines only an AI would catch are taught."""
import json
import unittest

import support
import cvcore as cl


class LessonsBuiltIn(unittest.TestCase):

    def test_lines_taught(self):
        d = json.loads((support.ROOT / "shared_learned.json").read_text(encoding="utf8"))
        movies = d["shows"]["_movies"]
        for line in ("any excuse for you to pull that thing out", "ready to get his freak on",
                     "she might put it on a brother"):
            with self.subTest(line):
                key = next(k for k in movies["muted"] if line in k)
                self.assertEqual(movies["muted_for"][key], "sexref")

    def test_prayers_and_hymns_left_alone(self):
        for text in ("LORD, LET YOUR HOLY LIGHT", "THAT A YOUNG LIFE WAS SAVED BY OUR LORD.",
                     "BUT YOU SHOULD CARE ABOUT GOD'S OPINION.", "GOD IS NOT MOCKED."):
            with self.subTest(text):
                words = [w for w in (cl.norm(t) for t in text.split()) if w]
                self.assertEqual(cl.find_language(words, ["deity"]), [])


if __name__ == "__main__":
    unittest.main()
