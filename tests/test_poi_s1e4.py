"""The owner's Person of Interest S1E4 report (1.18.105, 2026-11-15, adults, the AI helper, made on
1.18.104; the owner: "yes 1 and 2"). "I'm going home and hitting the hay" was heard as "hit in
the heck" and "heck" muted, though the subtitles say "hay" right there; "Benton's conquests?"
and "I do know a place right around the corner -- full bar, comfy bed." went through."""
import unittest

import support  # noqa: F401  (sets up the sandbox first)
import cvcore as cl
import cleanview as engine


class Hay(unittest.TestCase):
    def test_short_words_alike(self):
        self.assertTrue(engine.sounds_alike("heck", "hay"))
        for heard, written in (("bitch", "Finch"), ("dick", "Nic"), ("fucking", "bugging"),
                               ("hell", "Al")):
            self.assertEqual(engine.sounds_alike(heard, written),
                             heard != "hell", (heard, written))   # "Al" is the name rule's

    def test_still_not_alike(self):
        for heard, written in (("ass", "eye"), ("hell", "no"), ("fuck", "oh"),
                               ("son of a bitch", "sop"), ("pissed", "pay")):
            self.assertFalse(engine.sounds_alike(heard, written), (heard, written))

    def test_offered_unticked(self):
        sw = "Workaholics need rest. I'm going home and hitting the hay. Okay.".split()
        sn = [cl.norm(w) for w in sw]
        asr_n = [cl.norm(w) for w in
                 "workaholics need rest i'm going home and hit in the heck okay".split()]
        mapping = cl.align(sn, asr_n)
        m = {"at": asr_n.index("heck"), "src": "audio", "cat": "minced", "word": "heck"}
        engine.subtitle_word_there([m], mapping, sw, sn, asr_n)
        self.assertEqual(m.get("sub"), "hay.")
        self.assertTrue(m.get("keep"), "misheard: offered unticked")


class Conquests(unittest.TestCase):
    CASUAL = engine.LINE_WORDS["casual"]

    def test_found_and_just_the_word(self):
        for text in ("Benton's conquests?", "So I could be another one of your conquests?",
                     "He bragged about his conquests."):
            m = self.CASUAL.search(text)
            self.assertTrue(m, text)
            self.assertEqual(engine.LIST_WORD_TRIM.sub("", m.group(0)).lower(), "conquests")

    def test_other_conquests_left_alone(self):
        for text in ("the Norman Conquest", "the conquest of Mexico", "Conquest is a game."):
            self.assertIsNone(self.CASUAL.search(text), text)


class Taught(unittest.TestCase):
    def test_comfy_bed_for_person_of_interest(self):
        import cleanview_learn as learn
        line = learn.norm("I do know a place right around the corner -- full bar, comfy bed.")
        muted = learn._sh("person-of-interest", "muted")
        self.assertIn(line, muted)
        self.assertIn(line, learn._for_filters("person-of-interest", muted, {"casual"}))
        self.assertNotIn(line, learn._for_filters("person-of-interest", muted, {"sexref"}))


if __name__ == "__main__":
    unittest.main()
