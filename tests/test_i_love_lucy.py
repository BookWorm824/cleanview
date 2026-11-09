"""Lauren's I Love Lucy report (2026-11-08, teens, word lists only). "I Love Lucy 1 - Ep. 1.m4v"
wasn't read as season 1 episode 1: it was looked up online as a movie of that name, the
subtitles found lined up 4%, and what she chooses was learned under "movies". And "Let's get
Valentine." was muted as Valentine's Day: a lone "Valentine" is a name."""
import unittest

import support  # noqa: F401  (sets up the sandbox first)
import cleanview as engine


class EpisodeNames(unittest.TestCase):

    def test_season_dash_ep(self):
        for name, want in (("I Love Lucy 1 - Ep. 1.m4v", ("I Love Lucy", 1, 1)),
                           ("I Love Lucy 2 - Ep. 14.m4v", ("I Love Lucy", 2, 14)),
                           ("Castle 1 - Episode 7.mkv", ("Castle", 1, 7)),
                           (r"E:\TV\I Love Lucy\I Love Lucy 1 - Ep. 1.m4v", ("I Love Lucy", 1, 1))):
            with self.subTest(name):
                self.assertEqual(engine.guess_title(name), want)

    def test_others_as_before(self):
        self.assertEqual(engine.guess_title("Castle S01E07.mkv"), ("Castle", 1, 7))
        self.assertEqual(engine.guess_title("Toy Story 4.mkv"), ("Toy Story 4", None, None))
        self.assertEqual(engine.guess_title("50 First Dates.m4v"), ("50 First Dates", None, None))

    def test_learned_under_the_show(self):
        self.assertEqual(engine.learned_key("I Love Lucy 1 - Ep. 1.m4v", {"profile": "teens"}),
                         engine.learned_key("I Love Lucy S01E02.m4v", {"profile": "teens"}))


class ValentineIsAName(unittest.TestCase):

    def test_a_lone_valentine_is_a_name(self):
        r = engine.LINE_WORDS["valentine"]
        for t in ("Let's get Valentine.", "Mrs. Valentine called.", "Valentine, come here."):
            with self.subTest(t):
                self.assertIsNone(r.search(t))

    def test_the_day_still_counts(self):
        r = engine.LINE_WORDS["valentine"]
        for t in ("Happy Valentine's Day!", "Will you be my valentine?",
                  "I made valentines for the class.", "a Valentine card",
                  "I got a valentine from Tommy", "Valentine Day is coming", "Cupid shot his arrow"):
            with self.subTest(t):
                self.assertIsNotNone(r.search(t))


if __name__ == "__main__":
    unittest.main()
