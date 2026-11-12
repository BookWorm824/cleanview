"""Lauren's Castle S2E1 report (2026-11-11, 1.18.60, adults, the AI helper). "That's a long
way to go for a robbery." was muted as the lesson "That's a long way to go for a lube job" (8
words the same, the joke in the rest), and "Now, that's kind of hot." (Castle to Beckett) was
cut as same-sex flirting between "two men"."""
import unittest
from unittest import mock

import support  # noqa: F401
import cleanview as engine
import cleanview_ai as ai
import cleanview_learn as learn

LESSONS = ["that's a long way to go for a lube job",
           "instead of getting your freak on with writer boy",
           "i'm not ready to buy our attacker as a sexual predator"]


class EndsDiffer(unittest.TestCase):
    def setUp(self):
        self.find = learn.LearnedLines(LESSONS)

    def match(self, text):
        return self.find.match(learn.norm(text))

    def test_another_ending_isnt_the_lesson(self):
        self.assertIsNone(self.match("That's a long way to go for a robbery."))
        self.assertIsNone(self.match("That's a long way to go for a sandwich at midnight."))

    def test_the_lesson_still_matches(self):
        self.assertEqual(self.match("That's a long way to go for a lube job, isn't it?"),
                         LESSONS[0])
        self.assertEqual(self.match("So that's a long way to go for a lube job"), LESSONS[0])

    def test_a_word_heard_differently(self):
        self.assertEqual(self.match("Getting a drink with me after work instead of getting your "
                                    "freak on with Ryder Boy?"), LESSONS[1])
        self.assertEqual(self.match("That's a long way to go for a lube jab"), LESSONS[0])

    def test_split_across_heard_lines(self):
        self.assertEqual(self.match("Look, I'm not ready to buy our attacker as a sexual"),
                         LESSONS[2])


class VoicesSayManAndWoman(unittest.TestCase):
    def setUp(self):
        def chat(prompt, *a, schema=None, **k):
            if "quote" in (schema or {}).get("properties", {}):
                return {"romance": True, "between": "two men", "lines": [2],
                        "quote": "kind of hot",
                        "what": "Ryan comments on Beckett's behavior in a flirtatious manner"}
            return {"romance": True, "between": "two men"}
        p = mock.patch.object(ai, "chat", chat)
        p.start()
        self.addCleanup(p.stop)
        self.lines = [{"s": 1818.2, "e": 1822.9, "text": "and pretend to be Muscovite."},
                      {"s": 1823.2, "e": 1824.9, "text": "Now, that's kind of hot."},
                      {"s": 1827.0, "e": 1827.6, "text": "Raise."}]

    def test_a_man_and_a_woman_heard(self):
        genders = [{"spk": "Speaker 1", "g": "woman"}, {"spk": "Speaker 2", "g": "man"},
                   {"spk": "Speaker 3", "g": "man"}]
        (f,) = ai.romance_scenes(self.lines, genders)
        self.assertEqual(f["between"], "mm")
        self.assertTrue(f["mixed"])
        (sc,) = engine.flirt_scenes([f])
        self.assertFalse(sc["sure"])
        self.assertIn("a man's and a woman's voice", sc["why"])
        self.assertEqual(sc["kind"], ["Same-sex romance · two men"])

    def test_only_men_heard(self):
        genders = ["man", "man", "man"]
        (f,) = ai.romance_scenes(self.lines, genders)
        self.assertFalse(f["mixed"])
        (sc,) = engine.flirt_scenes([f])
        self.assertTrue(sc["sure"])
        self.assertNotIn("voice", sc["why"])

    def test_voices_not_known(self):
        (f,) = ai.romance_scenes(self.lines, None)
        self.assertFalse(f["mixed"])
        self.assertTrue(engine.flirt_scenes([f])[0]["sure"])

    def test_claude_and_man_and_woman_flirts(self):
        self.assertTrue(engine.flirt_scenes([{"s": 5, "e": 6, "between": "ss",
                                              "what": "two women"}])[0]["sure"])
        self.assertEqual(engine.flirt_scenes([{"s": 5, "e": 6, "between": "mf", "what": "",
                                               "mixed": False}]), [])


if __name__ == "__main__":
    unittest.main()
