"""Swearing sorted by type (1.18.150; the owner, in the CleanStream chat: "when i had the hard
language filter on it took out some words that should be in other categories", "organize
better by type", "Yes, all of it"). Slurs are a box of their own, ticked for every age; sexual
words go with "Sexual references and innuendo", crude words with "Crude humor", "skeevy" with
the rude words."""
import unittest

import support  # noqa: F401  (must come first)
import cvcore as cl
import cleanview as engine
import test_ui

ui = test_ui.ui


def found(text, groups, opts=None):
    words = [cl.norm(w) for w in text.split()]
    return [(" ".join(words[a:b]), cat)
            for a, b, cat in cl.find_language(words, cl.cats_for(groups, opts))]


EVERY_GROUP = list(cl.GROUPS)
SLURS = ["you lazy wop", "dumb polack", "you retard", "a faggot", "what a dyke", "you homo"]
SEX = ["shes a hussy", "nice pair of melons", "he is horny", "what a slut",
       "pop her cherry", "is that a banana in your pocket"]
CRUDE = ["that took some balls", "grow a pair", "what a turd", "kicked him in the nuts",
         "he is ballsy"]
SWEARING = ["shit", "what the eff", "you bastard", "eff you", "s o b"]


class TheBoxes(unittest.TestCase):
    def test_slurs_have_their_own_box(self):
        for t in SLURS:
            self.assertEqual(found(t, ["swearing", "samesexwords"]), [], t)
            self.assertEqual([c for _, c in found(t, ["slurs"])], ["slurs"], t)

    def test_sexual_words_go_with_sexual_references(self):
        for t in SEX:
            self.assertEqual(found(t, EVERY_GROUP, {"crude": True}), [], t)
            self.assertEqual([c for _, c in found(t, [], {"sexref": True})], ["sexwords"], t)

    def test_crude_words_go_with_crude_humor(self):
        for t in CRUDE:
            self.assertEqual(found(t, EVERY_GROUP, {"sexref": True}), [], t)
            self.assertEqual([c for _, c in found(t, [], {"crude": True})], ["crudewords"], t)

    def test_swearing_keeps_the_swears(self):
        for t in SWEARING:
            self.assertEqual([c for _, c in found(t, ["swearing"])], ["moderate"], t)

    def test_skeevy_is_a_rude_word(self):
        self.assertEqual(found("you skeevy guy", ["swearing"]), [])
        self.assertEqual(found("you skeevy guy", ["rude"]), [("skeevy", "rude")])

    def test_gay_is_still_a_same_sex_word(self):
        self.assertEqual(found("he is gay", ["samesexwords"]), [("gay", "samesex")])
        self.assertEqual(found("he is gay", ["slurs"]), [])

    def test_slurs_still_never_fine(self):
        for w in ("wop", "retarded", "spic"):
            self.assertTrue(cl.never_fine(w), w)

    def test_every_word_kept(self):
        # the same 161 words as before, only sorted ("skeevy" with the rude words); 1.18.172
        # added "pansy" and "pansy-ass" to the slurs
        self.assertEqual(sum(map(len, (cl.STRONG, cl.SLURS, cl.MODERATE, cl.SEX_WORDS,
                                       cl.CRUDE_WORDS, cl.MILD, cl.SAMESEX_WORDS))), 162)
        self.assertIn("skeevy", cl.RUDE)
        self.assertEqual(len(cl.SLANG_CAT), len(cl.BODY_SLANG))

    def test_an_ai_mutes_a_word_only_with_its_box(self):
        self.assertFalse(engine._words_listed("hussy", (), ["swearing", "mild"], {}))
        self.assertTrue(engine._words_listed("hussy", (), [], {"sexref": True}))
        self.assertTrue(engine._words_listed("wop", (), ["slurs"], {}))
        self.assertFalse(engine._words_listed("wop", (), ["swearing"], {}))


class EveryAge(unittest.TestCase):
    def test_slurs_ticked_for_every_age(self):
        self.assertIn("slurs", ui.FILTER_KEYS)
        for p, ticks in ui.PRESETS.items():
            self.assertTrue(ticks["slurs"], p)

    def test_what_each_age_mutes(self):
        for p, ticks in ui.PRESETS.items():
            groups = [g for g in cl.GROUPS if ticks.get(g)]
            for t in SLURS + SWEARING + SEX:
                self.assertTrue(found(t, groups, ticks), (p, t))
            # Crude humor is off for Teens and Adults: "balls" meaning nerve plays there
            self.assertEqual(bool(found("that took some balls", groups, ticks)),
                             bool(ticks["crude"]), p)

    def test_review_page_names(self):
        names = _word_group()
        self.assertEqual(names["slurs"], "Slurs")
        self.assertEqual(names["sexwords"], engine.LINE_LABEL["sexref"])
        self.assertEqual(names["crudewords"], engine.LINE_LABEL["crude"])


def _word_group():
    for v in vars(ui).values():
        if isinstance(v, type) and "WORD_GROUP" in vars(v):
            return v.WORD_GROUP
    raise AssertionError("no WORD_GROUP")


if __name__ == "__main__":
    unittest.main()
