"""The owner, 2026-11-13 (in the CleanListen session, for every app): "any explicit talk should
be removed from coroner talk regardless of medical /coroner - tearing, vaginal bruising etc",
and how: "whole line on sexual reference". Explicit detail in a coroner's, doctor's or
detective's findings is muted as a whole line whenever sexual references is ticked, with the
coroner box on or off; plain case talk ("any signs of sexual assault?") still follows that box.
An AI can't untick it; her own choice still can."""
import unittest

import support  # noqa: F401  (the sandbox, before any app module)
import cleanview as engine
import cleanview_ai as ai
import cleanview_claude as cc
from test_learning import review

EXPLICIT = ["The coroner found vaginal bruising and tearing.",
            "Tearing consistent with forced penetration.",
            "Anal tearing, the doctor said.",
            "Bruising of the labia.",
            "She was raped; there was tearing.",
            "There were signs of penetration."]
NOT_EXPLICIT = ["She was tearing up the letter.",
                "The bullet penetrated his lung.",
                "Bruising on her arms and neck.",
                "Any signs of sexual assault?",
                "He came tearing down the road.",
                "An analysis of the canal.",
                "The paper was tearing at the edges."]


def dialogue(*texts):
    return [{"s": 10.0 * i, "e": 10.0 * i + 4, "text": t} for i, t in enumerate(texts)]


def found(texts, **opts):
    o = engine.full_opts(dict({"sexref": True, "forensic": False}, **opts))
    lines, _ = engine.find_lines(dialogue(*texts), o, False)
    return {l["plain"]: l for l in lines}


class WhatCounts(unittest.TestCase):

    def test_explicit_detail(self):
        for t in EXPLICIT:
            with self.subTest(t):
                self.assertEqual(engine.explicit_findings(dialogue(t)), [0])

    def test_everyday_and_plain_case_talk(self):
        for t in NOT_EXPLICIT:
            with self.subTest(t):
                self.assertEqual(engine.explicit_findings(dialogue(t)), [])

    def test_tearing_after_the_question(self):
        d = dialogue("Any signs of sexual assault?", "There was tearing.")
        self.assertEqual(engine.explicit_findings(d), [1])
        d = dialogue("The curtains were old.", "There was tearing.")
        self.assertEqual(engine.explicit_findings(d), [])


class WholeLine(unittest.TestCase):

    def test_muted_whole_with_the_coroner_box_off_or_on(self):
        for forensic in (False, True):
            with self.subTest(coroner_box=forensic):
                got = found(EXPLICIT + NOT_EXPLICIT, forensic=forensic)
                for t in EXPLICIT:
                    l = got[t]
                    self.assertIn("sexref", l["types"])
                    self.assertTrue(l["mute"] and l["explicit"])
                    self.assertNotIn("words", l, "the whole line, not just a word")
                for t in ("She was tearing up the letter.", "Bruising on her arms and neck.",
                          "He came tearing down the road."):
                    self.assertNotIn(t, got)

    def test_plain_case_talk_follows_the_coroner_box(self):
        self.assertNotIn("Any signs of sexual assault?",
                         found(["Any signs of sexual assault?"], forensic=False))
        self.assertIn("Any signs of sexual assault?",
                      found(["Any signs of sexual assault?"], forensic=True))

    def test_only_with_sexual_references_ticked(self):
        self.assertEqual(found(EXPLICIT, sexref=False, forensic=False), {})

    def test_stays_whole_through_the_word_list_step(self):
        o = engine.full_opts({"sexref": True, "forensic": False})
        d = dialogue("They had sex in the car.", "The coroner found vaginal bruising and tearing.")
        lines, _ = engine.find_lines(d, o, False)
        st = {"path": "nowhere.mp4", "dialogue": d, "asr": [], "mutes": [], "lines": lines,
              "scenes": [], "opts": o}
        engine.list_words_only(st)
        by = {l["plain"]: l for l in st["lines"]}
        self.assertFalse(by["They had sex in the car."]["mute"], "the short list: just the word")
        self.assertTrue(by["The coroner found vaginal bruising and tearing."]["mute"])


class NothingUnticksItButHer(unittest.TestCase):

    def line(self, **more):
        return dict({"s": 5.0, "e": 9.0, "text": "The coroner found vaginal bruising.",
                     "plain": "The coroner found vaginal bruising.", "types": ["sexref"],
                     "mute": True, "explicit": True, "idx": 0}, **more)

    def test_a_hint_that_it_was_fine_before(self):
        l = self.line(mute=False, hint="CleanView learned this is fine")
        self.assertEqual(engine.explicit_stay({"lines": [l]}), 1)
        self.assertTrue(l["mute"])
        self.assertNotIn("hint", l)

    def test_her_own_choice_stays(self):
        for mine in ({"learned": "you left this unmuted before"}, {"by_you": True}):
            l = self.line(mute=False, **mine)
            self.assertEqual(engine.explicit_stay({"lines": [l]}), 0)
            self.assertFalse(l["mute"])

    def test_a_review_cant_untick_it(self):
        from test_learning import Item
        for said in ("not an issue", "just the word", "can't tell"):
            with self.subTest(said=said):
                l = Item(**self.line())
                review({"dialogue": [], "lines": [l], "scenes": [], "mutes": []},
                       {l: (said, "it's only evidence talk")})
                self.assertTrue(l["mute"])
                self.assertEqual(l["claude"]["decision"], "remove")
                self.assertIn("explicit", l["claude"]["why"])

    def test_the_readers_are_told(self):
        for text in (ai.NOT_CASE, cc.NOT_CASE):
            self.assertIn("explicit detail", text)
            self.assertIn("always counts", text)


if __name__ == "__main__":
    unittest.main()
