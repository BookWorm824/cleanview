"""Lessons from Lauren's first CleanView Play scan (1.18.94; I Love Lucy 1 - Ep. 2, young, the
AI helper, 2026-11-14), passed on by the play-only chat with her "yes send":
1. the show's heart-on-satin title cards were cut four times as Valentine's Day ("teach that a
   heart doesn't mean valentine by itself");
2. "Your life should be just one gay round of nightclubs" was muted as a same-sex word ("this
   is an old show so gay means happy");
3. "...keep our eye on our wives, who've seen fit to go out with other men!" was flagged as a
   sexual reference (she unticked it);
4. her chat note on "gay" in old shows, built in for everyone."""
import unittest

import support  # noqa: F401  (sets up the sandbox first)
import cvcore as cl
import cleanview as engine
import cleanview_ai as ai
import cleanview_claude as cc
import cleanview_learn as learn

CATS = list(cl.CATS)


def muted(text):
    words = [w for w in (cl.norm(t) for t in text.split()) if w]
    return [" ".join(words[i:j]) for i, j, _ in cl.find_language(words, CATS)]


class GayMeaningHappy(unittest.TestCase):
    def test_old_uses_left_alone(self):
        for text in ("Your life should be just one gay round of nightclubs.",
                     "We had a gay old time at the fair",
                     "everyone was in gay spirits",
                     "a gay whirl of parties", "they sang a gay tune",
                     "the gay nineties", "I feel pretty and witty and gay"):
            self.assertEqual(muted(text), [], text)
            self.assertIsNone(engine.LINE_WORDS["samesex"].search(text), text)

    def test_still_a_same_sex_word(self):
        for text in ("he is gay", "a gay couple moved in", "gay marriage is legal there",
                     "I think she's gay", "they met at a gay bar"):
            self.assertEqual(muted(text), ["gay"], text)
            self.assertIsNotNone(engine.LINE_WORDS["samesex"].search(text), text)

    def test_her_note_for_everything(self):
        notes = " ".join(learn.notes("_movies@adults", "Some Movie"))
        self.assertIn("'gay' meaning happy, cheerful or merry", notes)


class HeartTitleCards(unittest.TestCase):
    def test_a_heart_alone_isnt_valentines(self):
        q = ai.LOOK["valentine"][0]
        self.assertIn("A heart shape on its own", q)
        self.assertIn("title card", q)
        self.assertIn("a heart used as a show's logo or title card", cc.PIC_RULES)

    def test_the_shows_note(self):
        for key in ("i-love-lucy@young", "i-love-lucy@kids", "i-love-lucy"):
            self.assertTrue(any("heart on satin" in n for n in learn.notes(key)), key)


class TheFalseAlarm(unittest.TestCase):
    def test_taught_as_fine_for_the_show(self):
        kept = learn._sh("i-love-lucy@young", "kept")
        self.assertIn("on our wives who've seen fit", kept)
        self.assertIn("we can get a couple of blondes just to help us keep our eye on our wives "
                      "who've seen fit to go out with other men", kept)


if __name__ == "__main__":
    unittest.main()
