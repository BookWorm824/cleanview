"""Rude hand gestures (the middle finger...): found in the picture, by the AI on this
PC and by Claude/ChatGPT, and cut."""
import unittest

import support  # noqa: F401  (sets up the sandbox first)
import cleanview as engine
import cleanview_ai as ai
import cleanview_claude as cc

ON = engine.full_opts({"gestures": True})


class Gestures(unittest.TestCase):

    def test_looked_for_when_ticked(self):
        self.assertFalse(engine.DEFAULTS["gestures"])
        self.assertIn("gestures", engine.needs(ON)["clip"])
        self.assertNotIn("gestures", engine.needs({})["clip"])
        for table in (ai.CLIP_CATS, ai.THRESH, ai.MIN_FRAMES, ai.LOOK):
            self.assertIn("gestures", table)

    def test_one_second_is_enough(self):
        """A rude gesture is often over in a second: one strong frame makes a scene."""
        clip = {"t": [20.0], "scores": [{"gestures": 0.8}]}
        cands = ai.clip_candidates(clip, ["gestures"])
        self.assertEqual([(c["cat"], c["s"], c["e"]) for c in cands], [("gestures", 19.0, 21.0)])

    def test_double_checked_by_the_ai_on_this_pc(self):
        cands = [{"cat": "gestures", "s": 10, "e": 12}, {"cat": "gestures", "s": 30, "e": 32}]
        answers = iter([{"see": "A man raises his middle finger at the driver", "yes": True,
                         "clear": True},
                        {"see": "A girl waves goodbye", "yes": False, "clear": True}])
        saved, ai.chat = ai.chat, lambda *a, **k: next(answers)
        try:
            ai.second_look(cands, lambda c: ["a frame"])
        finally:
            ai.chat = saved
        scenes = engine.decide_picture_scenes(cands, ON, True)
        self.assertEqual([(s["kind"], s["sure"]) for s in scenes], [(["Rude gesture"], True)])

    def test_claude_looks_for_them_when_ticked(self):
        self.assertIn("rude gesture", cc.PIC_KINDS)
        self.assertIn("middle finger", engine.picture_wanted(ON))
        self.assertNotIn("middle finger", engine.picture_wanted(engine.full_opts()))
        self.assertEqual(engine._pic_wanted({"what": "rude gesture"}, ON), "Rude gesture")
        self.assertIsNone(engine._pic_wanted({"what": "rude gesture"}, engine.full_opts()))
        self.assertIn("middle finger", engine.wanted_text(ON, []))


if __name__ == "__main__":
    unittest.main()
