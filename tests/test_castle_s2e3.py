"""Lauren's Castle S2E3 report (2026-11-12, adults, the AI helper, 1.18.67): the AI helper missed
the episode's sexual talk. The owner: "do both but leave coroners talk". Its lines are built in
for Castle (not the coroner's "Any signs of sexual assault?"), and "skinny dip", "chastity
belt" and "naked photos/pictures" are on the short list that works without an AI."""
import json
import unittest

import support
import cleanview as engine
import cleanview_learn as learn

TAUGHT = ["If you catch me, you can have me.", "They're coming off right now. Take your pants off!",
          "she might as well be wearing a chastity belt.", "Look at naked pictures? If you insist.",
          "Because Jenna wouldn't sleep with him.", "And you assumed that was code for \"do me.\"",
          "It looks like Teddy Farrow isn't the only guy that Sierra was modeling for."]


class BuiltIn(unittest.TestCase):
    def setUp(self):
        shared = json.loads((support.ROOT / "shared_learned.json").read_text(encoding="utf8"))
        self.castle = shared["shows"]["castle"]
        self.find = learn.LearnedLines(self.castle["muted"])

    def test_the_lines_and_what_for(self):
        for t in TAUGHT:
            with self.subTest(t):
                self.assertIsNotNone(self.find.match(learn.norm(t)))
                self.assertEqual(self.castle["muted_for"].get(self.find.match(learn.norm(t))),
                                 "sexref")

    def test_not_the_coroner_or_everyday_lines(self):
        for t in ("Any signs of sexual assault?", "It's not the worst thing in the world.",
                  "You can have me.", "Give us the stats.", "I was ready to get down to business."):
            with self.subTest(t):
                self.assertIsNone(self.find.match(learn.norm(t)))

    def test_the_insult_isnt_taught_as_fine_any_more(self):
        # taught as a false alarm in 1.18.69; "fart" is always removed since the owner's hard
        # rule of 2026-11-13 (test_hard_rule.py), so no lesson keeps it
        self.assertNotIn(learn.norm("and called Calvin Klein a boring old fart, to his face."),
                         self.castle["kept"])


class ShortList(unittest.TestCase):
    def test_found(self):
        r = engine.LINE_WORDS["sexref"]
        for t, word in (("Oh, a fountain! Let's skinny dip!", "skinny dip"),
                        ("We went skinny-dipping at the lake.", "skinny-dipping"),
                        ("she might as well be wearing a chastity belt.", "chastity belt"),
                        ("Mmm. Naked photos.", "Naked photos"),
                        ("Look at naked pictures? If you insist.", "naked pictures"),
                        ("He sent her naked selfies.", "naked selfies")):
            with self.subTest(t):
                self.assertEqual(r.search(t).group(0), word)

    def test_left_alone(self):
        r = engine.LINE_WORDS["sexref"]
        for t in ("A couple of skinny dippers found her this morning.",   # police talk
                  "Can you see it with the naked eye?", "That's the naked truth.",
                  "a skinny guy dipped his fries"):
            with self.subTest(t):
                self.assertIsNone(r.search(t))


class ScanRecord(unittest.TestCase):
    def test_says_which_picture_runtime(self):
        src = (support.ROOT / "cleanview.py").read_text(encoding="utf8")
        self.assertIn('"picture_runtime": _ort_installed()', src)


if __name__ == "__main__":
    unittest.main()
