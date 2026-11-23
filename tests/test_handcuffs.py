"""Handcuffs as innuendo (1.18.163; the owner: "add handcuffs to the list when used as
inuendo"): only the unmistakable ones on the list; police cuffing someone left alone."""
import unittest

import support  # noqa: F401  (must come first)
import cleanview as engine


def found(t):
    return [m.group(0) for m in engine.LINE_WORDS["sexref"].finditer(t)]


class Handcuffs(unittest.TestCase):
    def test_innuendo(self):
        for t in ("Bring the furry handcuffs.", "Handcuff me to the bed.",
                  "You can cuff me to the bedpost later.", "I keep handcuffs in the bedroom.",
                  "The handcuffs are kinky.", "Ooh, naughty handcuffs."):
            self.assertTrue(found(t), t)

    def test_police_and_patients_left_alone(self):
        for t in ("Cuff him.", "75 cops in cuffs, that's news.",
                  "You cuff her to the bed if need be.", "Get these cuffs off.",
                  "Someone paid her to handcuff you to a bed, so they could murder you.",
                  "You just found real handcuffs?", "I'm not the one handcuffed to a chair."):
            self.assertEqual(found(t), [], t)

    def test_readers_told(self):
        self.assertIn("handcuffs", engine.OPT_TEXT["sexref"])
        self.assertIn("handcuffs", engine.ai.LINE_TYPES["sexref"])
        self.assertIn("handcuffs", engine.cc.TYPE_TEXT["sexref"])


if __name__ == "__main__":
    unittest.main()
