"""Rude and sexual gestures (the middle finger, crude motions): found in the picture,
by the AI on this PC and by Claude/ChatGPT, and cut."""
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
        self.assertEqual([(s["kind"], s["sure"]) for s in scenes],
                         [(["Rude or sexual gesture"], True)])

    def test_sexual_gestures_too(self):
        self.assertTrue(any("sexual" in t for t in ai.CLIP_CATS["gestures"]))
        self.assertIn("sexual", ai.LOOK["gestures"][0])
        self.assertIn("sexual", engine.picture_wanted(ON))
        self.assertIn("sexual", cc.PIC_RULES)
        cands = [{"cat": "gestures", "s": 10, "e": 12}, {"cat": "gestures", "s": 30, "e": 32}]
        answers = iter([{"see": "A man makes a crude sexual motion with his hands", "yes": True,
                         "clear": True},
                        {"see": "People dancing at a party", "yes": False, "clear": True}])
        saved, ai.chat = ai.chat, lambda *a, **k: next(answers)
        try:
            ai.second_look(cands, lambda c: ["a frame"])
        finally:
            ai.chat = saved
        scenes = engine.decide_picture_scenes(cands, ON, True)
        self.assertEqual([s["s"] for s in scenes], [10])

    def test_old_picture_scans_done_again_when_descriptions_change(self):
        before = ai.clip_signature()
        ai.CLIP_CATS["gestures"].append("a made-up new description")
        try:
            self.assertNotEqual(ai.clip_signature(), before)
        finally:
            ai.CLIP_CATS["gestures"].pop()
        self.assertEqual(ai.clip_signature(), before)

    def test_claude_looks_for_them_when_ticked(self):
        self.assertIn("rude gesture", cc.PIC_KINDS)
        self.assertIn("middle finger", engine.picture_wanted(ON))
        self.assertNotIn("middle finger", engine.picture_wanted(engine.full_opts()))
        self.assertEqual(engine._pic_wanted({"what": "rude gesture"}, ON),
                         "Rude or sexual gesture")
        self.assertIsNone(engine._pic_wanted({"what": "rude gesture"}, engine.full_opts()))
        self.assertIn("middle finger", engine.wanted_text(ON, []))


if __name__ == "__main__":
    unittest.main()
