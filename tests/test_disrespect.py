"""Disrespect (Lauren, 2026-10-30): kids being bratty, talking back to or disobeying their
parents and other grown-ups. A dialogue filter, whole lines, ticked for Young kids, Kids and
Teens. The AI still flags it when the child learns their lesson, but says so (or that they
get away with it)."""
import inspect
import unittest

import support  # noqa: F401  (sets up the sandbox first)
import cleanview as engine
import cleanview_ai as ai
import cleanview_claude as cc

ON = engine.full_opts({"disrespect": True})


def dialogue(*texts, gap=3.0):
    return [{"s": k * gap, "e": k * gap + 2.0, "text": t} for k, t in enumerate(texts)]


def flagged(lines, opts=ON):
    out, _ = engine.find_lines(lines, opts, have_ai=False)
    return {l["idx"]: [t for t in l["types"] if t == "disrespect"] for l in out}


class Heard(unittest.TestCase):

    def test_off_unless_ticked(self):
        self.assertFalse(engine.DEFAULTS["disrespect"])
        self.assertEqual(flagged(dialogue("You can't tell me what to do!"), engine.full_opts()),
                         {})

    def test_found_without_any_ai(self):
        for text in ("You can't tell me what to do!", "You're not the boss of me.",
                     "You're not my real mom!", "I don't have to listen to you.",
                     "You can't make me!", "I hate you, Dad!",
                     "I don't care what you say."):
            with self.subTest(text=text):
                self.assertEqual(flagged(dialogue(text)), {0: ["disrespect"]})

    def test_everyday_talk_left_alone(self):
        for text in ("Whatever you want for dinner.", "Make me a sandwich, please.",
                     "Leave the light on.", "I don't care which one, they're both nice.",
                     "Can you tell me what to do next?"):
            with self.subTest(text=text):
                self.assertEqual(flagged(dialogue(text)), {})

    def test_every_reader_knows_it(self):
        self.assertIn("disrespect", engine.LINE_KINDS)
        self.assertIn("disrespect", ai.LINE_TYPES)
        self.assertIn("disrespect", ai.LINE_NAMES)
        self.assertIn("disrespect", cc.TYPE_TEXT)
        self.assertIn("disrespect", engine.LINE_LABEL)
        self.assertNotIn("disrespect", engine.WHOLE_CONVERSATIONS)    # just the lines
        self.assertIn("talking back", engine.wanted_text(ON, []))
        self.assertTrue(cc.MORE_THAN_WORD.search("talking back to his mom"))

    def test_says_whether_they_learn_their_lesson(self):
        self.assertIn("learn their lesson", cc.TYPE_TEXT["disrespect"])
        self.assertIn("get away with it", cc.TYPE_TEXT["disrespect"])
        self.assertIn("learn their lesson", inspect.getsource(cc.review))


class StartPage(unittest.TestCase):

    def test_ticked_for_kids_and_teens_not_adults(self):
        from test_ui import ui
        self.assertIn("disrespect", ui.FILTER_KEYS)
        for p in ("young", "kids", "teens"):
            self.assertTrue(ui.PRESETS[p]["disrespect"], p)
        self.assertFalse(ui.PRESETS["adults"]["disrespect"])
        self.assertIn("Disrespect", ui.CHIP)


if __name__ == "__main__":
    unittest.main()
