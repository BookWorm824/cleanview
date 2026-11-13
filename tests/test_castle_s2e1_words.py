"""Two things from Lauren's Castle S2E1 tests of 2026-11-13 (the AI helper, then asking Claude):

- "using him as a stripper pole": only "stripper" was muted, so "pole" played. In the chat she
  said "if pole ever comes after stripper it should be muted, keep pole other instances".
- "Ladies, I love it. Sexy. Sexy's not a crime.": the word is said twice, but the second mute
  was put on top of the first (both at 0:45.3), so "Sexy's" played."""
import json
import unittest

import support
import cleanview as engine
import cleanview_learn as learn
from test_code_check import state

SEXREF = engine.LINE_WORDS["sexref"]


def found(text):
    return [m.group(0).lower() for m in SEXREF.finditer(text)]


class StripperPole(unittest.TestCase):
    def test_the_two_words_together(self):
        self.assertEqual(found("using him as a stripper pole while I make nicey-nice"),
                         ["stripper pole"])
        self.assertEqual(found("They put in two stripper poles."), ["stripper poles"])

    def test_stripper_alone_as_before(self):
        self.assertEqual(found("She used to be a stripper."), ["stripper"])
        self.assertEqual(found("The strippers left at nine."), ["strippers"])

    def test_a_person_not_a_tool(self):
        # (the owner, 2026-11-13: "read the context. like a paint stripper would be ok. but a
        # person stripper isnt. a pole by itself is fine but with stripper it isn't")
        for text in ("He hired a stripper for the bachelor party.",
                     "The stripper's name was Candy.",
                     "Two strippers walked into the precinct.",
                     "She worked as a stripper to pay for college."):
            self.assertTrue(found(text), text)
        for text in ("Hand me the paint stripper.",
                     "Use the wire strippers to bare the ends.",
                     "The stripper took the varnish off the floor.",
                     "He brushed the stripper onto the old paintwork.",
                     "A good wallpaper stripper saves hours.",
                     "He made his money as an asset stripper.",
                     "Load the rifle with a stripper clip.",
                     "It came from a stripper well in Texas.",
                     "Get the weed stripper out of the shed."):
            self.assertEqual(found(text), [], text)
            self.assertIsNone(SEXREF.search(text), text)

    def test_with_a_pole_its_never_the_tool(self):
        self.assertEqual(found("They painted the stripper pole gold."), ["stripper pole"])

    def test_the_tool_isnt_muted_in_a_line(self):
        st = state(["Hand me the paint stripper and a brush."], sexref=True)
        st["lines"] = []
        self.assertEqual(engine.list_words_only(st), 0)
        self.assertEqual(st["mutes"], [])

    def test_the_rest_of_the_list_as_before(self):
        self.assertEqual(found("It kind of reminds me of porn."), ["porn"])
        self.assertEqual(found("Sexy. Sexy's not a crime."), ["sexy", "sexy"])
        self.assertTrue(SEXREF.search("They were having sex."))
        self.assertIsNone(SEXREF.search("The fair sex was well represented."))
        self.assertTrue(SEXREF.pattern)                 # still usable as the pattern it is

    def test_a_pole_anywhere_else_is_fine(self):
        for text in ("He flew to the North Pole.", "Hand me that fishing pole.",
                     "The flag pole fell on the stripper's car."[:23]):
            self.assertEqual(found(text), [], text)

    def test_muted_from_stripper_to_pole(self):
        st = state(["They were using him as a stripper pole today."], sexref=True)
        st["lines"] = [dict(st["dialogue"][0], types=["sexref"], mute=True,
                            words=["stripper pole"], idx=0)]
        self.assertEqual(engine.list_words_only(st), 1)
        self.assertEqual(len(st["mutes"]), 1)
        m = st["mutes"][0]
        self.assertEqual(m["raw"], "stripper pole")
        heard = {w[0]: w for w in st["asr"]}
        self.assertLessEqual(m["s"], heard["stripper"][1] + 0.05)
        self.assertGreaterEqual(m["e"], heard["pole"][2] - 0.05)       # "pole" too
        self.assertLessEqual(m["e"], heard["today."][1] + 0.3)         # and no further


class SaidTwiceWithAnS(unittest.TestCase):
    LINE = "Ladies, I love it. Sexy. Sexy's not a crime."

    def lines(self, st):
        st["lines"] = [dict(st["dialogue"][0], types=["sexref"], mute=True,
                            words=["Sexy", "Sexy"], idx=0)]

    def test_each_gets_its_own_mute_when_it_wasnt_heard(self):
        st = state([self.LINE], sexref=True)
        st["asr"] = []                               # only the subtitles have the words
        self.lines(st)
        engine.list_words_only(st)
        self.assertEqual(len(st["mutes"]), 2)
        first, second = st["mutes"]
        self.assertGreater(second["s"], first["s"] + 0.2)          # not on top of each other

    def test_each_gets_its_own_mute_when_it_was_heard(self):
        st = state([self.LINE], sexref=True)
        self.lines(st)
        engine.list_words_only(st)
        self.assertEqual(len(st["mutes"]), 2)
        heard = [w for w in st["asr"] if w[0].lower().startswith("sexy")]
        self.assertAlmostEqual(st["mutes"][0]["s"], heard[0][1], delta=0.35)
        self.assertAlmostEqual(st["mutes"][1]["s"], heard[1][1], delta=0.35)

    def test_asked_for_more_often_than_its_said(self):
        st = state(["That is so sexy of you."], sexref=True)
        st["asr"] = []
        st["lines"] = [dict(st["dialogue"][0], types=["sexref"], mute=True,
                            words=["sexy", "sexy"], idx=0)]
        engine.list_words_only(st)
        self.assertEqual(len(st["mutes"]), 1)                       # no second one on top


class Lessons(unittest.TestCase):
    """Her "Yes, teach them" (2026-11-13): two lines the AI helper flagged that fit no filter."""

    def setUp(self):
        shared = json.loads((support.ROOT / "shared_learned.json").read_text(encoding="utf8"))
        self.castle = shared["shows"]["castle"]
        self.find = learn.LearnedLines(self.castle["muted"])

    def test_the_false_alarms_are_fine(self):
        for t in ("You do remind me a little of Hooch.",                  # a dog, not innuendo
                  "Try unbuttoning his shirt. Just, just the first one right there."):  # a photo shoot
            with self.subTest(t):
                self.assertIn(learn.norm(t), self.castle["kept"])
                self.assertIsNone(self.find.match(learn.norm(t)))

    def test_the_same_joke_at_the_end_isnt_muted_either(self):
        self.assertIsNone(self.find.match(learn.norm(
            "You know, now that you mention it, you do remind me a little of Hooch.")))


if __name__ == "__main__":
    unittest.main()
