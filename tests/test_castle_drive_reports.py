"""The Castle reports in the Drive folder, gone over 2026-11-12 (S1E3, S1E4, S1E6-E9, S1E2
"(Clean)", S2E4; the owner: "do 1"): missed lines built in, her unticks of lines that fit no
filter taught as fine, and two older lessons that joined a harmless line to the next taken out
(she unticked the harmless half: "Someone who was slipping her a little cash", "What are we
playing for?")."""
import json
import unittest

import support
import cleanview_learn as learn


class CastleLessons(unittest.TestCase):
    def setUp(self):
        shared = json.loads((support.ROOT / "shared_learned.json").read_text(encoding="utf8"))
        self.castle = shared["shows"]["castle"]
        self.find = learn.LearnedLines(self.castle["muted"])

    def test_missed_lines_built_in(self):
        for t, kind in (("You're a married man sleeping with her in your own bed.", "casual"),
                        ("Only the whole time, he was sleeping with me.", "casual"),
                        ("We could always make it strip poker.", "sexref"),
                        ("No time for dirty talk, go get changed.", "sexref"),
                        ("That better not be porn, and if it is, I want in.", "sexref"),
                        ("I'm a very generous man looking to arrange a very special date "
                         "with Tiffany.", "sexref")):
            with self.subTest(t):
                m = self.find.match(learn.norm(t))
                self.assertIsNotNone(m)
                self.assertEqual(self.castle["muted_for"].get(m), kind)

    def test_her_unticks_not_muted(self):
        for t in ("Someone who was slipping her a little cash", "What are we playing for?",
                  "Oh, do us a favor, Detective. Beat his pants off.",
                  "Lord I can't stop myself"):
            with self.subTest(t):
                self.assertIsNone(self.find.match(learn.norm(t)))
                self.assertIn(learn.norm(t), self.castle["kept"])

    def test_the_innuendo_after_them_still_muted(self):
        self.assertIsNotNone(self.find.match(learn.norm("while he was slipping her something "
                                                        "else.")))
        self.assertIsNotNone(self.find.match(learn.norm("Yes, please. Beat my pants off, if "
                                                        "you dare.")))

    def test_s2e5_lines(self):
        # Castle S2E5 (2026-11-12, 1.18.70): "Yes, teach them"
        for t, kind in (("Oh, Rick. You sleeping with her? No.", "sexref"),
                        ("Geez, one night in Ibiza and what do I get, a chapter in Storm Fall?",
                         "casual")):
            with self.subTest(t):
                m = self.find.match(learn.norm(t))
                self.assertEqual(self.castle["muted_for"].get(m), kind)
        self.assertIsNone(self.find.match(learn.norm("You sleeping with her?")))

    def test_coroner_talk_not_taught(self):
        self.assertIsNone(self.find.match(learn.norm("Any signs of sexual assault?")))


if __name__ == "__main__":
    unittest.main()
