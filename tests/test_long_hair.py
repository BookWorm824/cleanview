"""Men with long hair taken for women (1.18.96; the owner, 2026-11-14: "one thing clean view
struggles with is men with long hair. it says same sex when they are with women", "i mean long
hair in general", "if a guy with long hair says i love you it flags same sex"; Selena's two
kisses with Chris were labelled "two women").

1. Every picture check that says who (the AI on this PC's kiss and intimate-scene looks, and
   Claude, ChatGPT and Gemini's picture rules) is told long hair alone isn't a woman.
2. A scene the AI on this PC calls two women or two men, with a man's and a woman's voice heard
   there, is offered unticked (as the dialogue's flirting finds already were)."""
import inspect
import unittest

import support  # noqa: F401  (sets up the sandbox first)
import cleanview as engine
import cleanview_ai as ai
import cleanview_claude as cc


def scene(kind, s=100.0, e=106.0, **more):
    return {"s": s, "e": e, "kind": [kind], "why": "kissing seen", "sure": True, **more}


LINES = [{"s": 98.0, "e": 99.5, "text": "I love you."}, {"s": 100.5, "e": 101.5, "text": "I love you too."},
         {"s": 140.0, "e": 141.0, "text": "Later."}]


class Told(unittest.TestCase):
    def test_the_ai_on_this_pc(self):
        for k in ("kiss", "bed"):
            self.assertIn("Long hair alone does not make someone a woman", ai.LOOK[k][0], k)
            self.assertIn("answer unclear", ai.LOOK[k][0], k)

    def test_claude_chatgpt_gemini(self):
        self.assertIn("long hair alone does not make someone a woman", cc.PIC_RULES)
        self.assertIn("a beard, stubble", cc.PIC_RULES)


class Voices(unittest.TestCase):
    def test_a_man_and_a_woman_heard(self):
        scenes = [scene("Kiss · two women · passionate")]
        n = engine.picture_voices(scenes, LINES, ["man", "woman", "woman"])
        self.assertEqual(n, 1)
        self.assertFalse(scenes[0]["sure"])
        self.assertIn("a man's and a woman's voice are heard there", scenes[0]["why"])
        self.assertIn("only cut if you tick it", scenes[0]["why"])

    def test_cut_flag_too(self):
        scenes = [scene("Intimate scene · two men", cut=True)]
        engine.picture_voices(scenes, LINES, [{"g": "woman"}, {"g": "man"}, {}])
        self.assertFalse(scenes[0]["cut"])

    def test_left_alone(self):
        cases = (([scene("Kiss · two women")], ["woman", "woman", "man"]),   # the man is later
                 ([scene("Kiss · man & woman")], ["man", "woman", "man"]),
                 ([scene("Kiss · two women", by_you=True)], ["man", "woman", "man"]),
                 ([scene("Violence")], ["man", "woman", "man"]),
                 ([scene("Kiss · two women")], None))
        for scenes, voices in cases:
            self.assertEqual(engine.picture_voices(scenes, LINES, voices), 0, scenes[0]["kind"])
            self.assertTrue(scenes[0]["sure"])

    def test_not_said_twice(self):
        scenes = [scene("Same-sex romance · two women")]
        scenes[0]["why"] += engine.VOICES_MIXED
        self.assertEqual(engine.picture_voices(scenes, LINES, ["man", "woman", "man"]), 0)
        self.assertEqual(scenes[0]["why"].count("a man's and a woman's voice"), 1)

    def test_only_the_ai_on_this_pc(self):
        src = inspect.getsource(engine.analyze)
        self.assertIn("picture_voices(pictured, lines, genders)", src)
        self.assertEqual(src.count("picture_voices("), 1)
        a = src.index("pictured = decide_picture_scenes(")
        self.assertLess(a, src.index("picture_voices(pictured"))
        self.assertLess(src.index("scenes += pictured"), src.index("look_at_picture("))


if __name__ == "__main__":
    unittest.main()
