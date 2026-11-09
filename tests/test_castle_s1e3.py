"""Lauren's Castle S1E3 report (2026-11-09, teens, the local AI helper, no Claude). The show's
built-in lessons had this episode's lines ("And that is not his wife", "I gotta hand it to
Councilman Horny"...), learned from adults' reports under "castle", but a teens run only looked
under "castle@teens", so none of the 191 were used. What's muted for an older age is now muted
for the younger ones too; what an older age keeps isn't. And two lines heard split or worded
differently from the lesson now match."""
import unittest

import support  # noqa: F401  (sets up the sandbox first)
import cleanview_learn as learn

HEARD = [(897.9, "And that is not his wife."),
         (911.5, "I gotta hand it to Councilman Horney."),
         (913.4, "He is incredibly flexible for a guy his age."),
         (1037.8, "You don't think with a body like that she's gonna swoon over his stump "
                  "speeches, do you?"),
         (1291.1, "Getting a drink with me after work instead of getting your freak on with "
                  "Ryder Boy?"),
         (1300.0, "Let's go get some coffee before the press conference.")]


def dialogue(rows):
    return [{"s": s, "e": s + 2.0, "text": t} for s, t in rows]


class OlderAgesMutedToo(unittest.TestCase):

    def setUp(self):
        self.saved = learn._shared
        learn._shared = {"general": {}, "shows": {
            "agesshow": {"muted": ["he is incredibly flexible for a guy his age",
                                   "she's not in my little black book"],
                         "kept": ["and what was that girl thinking"],
                         "muted_for": {"she's not in my little black book": "casual"}},
            "agesshow@teens": {"muted": ["i'm gonna kick your butt at chess"]}}}

    def tearDown(self):
        learn._shared = self.saved

    def added(self, key, rows, on=None):
        got, _ = learn.apply(key, dialogue(rows), [], [], [], on=on)
        return [l["text"] for l in got]

    def test_adults_lines_muted_for_teens_and_kids(self):
        rows = [(1.0, "He is incredibly flexible for a guy his age.")]
        for key in ("agesshow", "agesshow@teens", "agesshow@kids", "agesshow@young"):
            with self.subTest(key):
                self.assertEqual(self.added(key, rows), [rows[0][1]])

    def test_teens_lines_for_kids_not_adults(self):
        rows = [(1.0, "I'm gonna kick your butt at chess.")]
        self.assertEqual(self.added("agesshow@kids", rows), [rows[0][1]])
        self.assertEqual(self.added("agesshow", rows), [])

    def test_what_adults_keep_isnt_kept_for_teens(self):
        self.assertEqual(learn._sh("agesshow", "kept"), ["and what was that girl thinking"])
        self.assertEqual(learn._sh("agesshow@teens", "kept"), [])

    def test_a_filter_thats_off_still_counts(self):
        rows = [(1.0, "She's not in my little black book.")]
        self.assertEqual(self.added("agesshow@teens", rows, on={"sexref"}), [])
        self.assertEqual(self.added("agesshow@teens", rows, on={"casual"}), [rows[0][1]])

    def test_the_age_keys(self):
        self.assertEqual(learn._age_keys("castle@teens", older=True),
                         ["castle@teens", "castle", "castle@adults"])
        self.assertEqual(learn._age_keys("castle@teens"), ["castle@teens"])
        self.assertEqual(learn._age_keys("castle"), ["castle", "castle@adults"])
        self.assertEqual(learn._age_keys("_movies@kids", older=True),
                         ["_movies@kids", "_movies@teens", "_movies", "_movies@adults"])


class TheRealLessons(unittest.TestCase):

    def test_castle_s1e3_for_teens(self):
        got, _ = learn.apply("castle@teens", dialogue(HEARD), [], [], [],
                             on={"sexref", "casual", "oppsex"})
        self.assertEqual([round(l["s"], 1) for l in got], [897.9, 911.5, 913.4, 1037.8, 1291.1])
        self.assertEqual({l["learned_from"] for l in got}, {"shared"})


class SplitDifferently(unittest.TestCase):

    def setUp(self):
        self.find = learn.LearnedLines([
            "instead of getting your freak on with writer boy",
            "she was a pro you don't think with a body like that",
            "i'm not ready to buy our attacker as a sexual predator",
            "a little cops gone wild you do know i'm wearing a gun"])

    def match(self, text):
        return self.find.match(learn.norm(text))

    def test_a_word_heard_differently_in_a_longer_line(self):
        self.assertEqual(self.match(HEARD[4][1]), "instead of getting your freak on with writer boy")

    def test_running_across_two_lessons(self):
        self.assertEqual(self.match(HEARD[3][1]), "she was a pro you don't think with a body like that")

    def test_a_harmless_piece_still_isnt(self):
        for text in ("Without evidence of trauma, I'm not ready to buy our attacker",
                     "You do know I'm wearing a gun?",
                     "Getting a drink with me after work instead?"):
            with self.subTest(text):
                self.assertIsNone(self.match(text))


if __name__ == "__main__":
    unittest.main()
