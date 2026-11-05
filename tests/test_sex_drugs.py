"""Sex drugs are sexual references (Lauren, 2026-11-04: "add sexual drugs to sexual reference
filter"): Viagra and the like, aphrodisiacs, drugging someone for sex."""
import unittest

import support  # noqa: F401

import cleanview as engine
import cleanview_ai as ai
import cleanview_claude as cc


class SexDrugs(unittest.TestCase):
    def test_word_list(self):
        for text in ("Did you take a Viagra?", "He's on Cialis now", "a little blue pill",
                     "Grandpa's little blue pills", "erectile dysfunction", "boner pills",
                     "It's an aphrodisiac", "a dash of Spanish fly", "Levitra"):
            self.assertIsNotNone(engine.LINE_WORDS["sexref"].search(text), text)

    def test_not_mistaken(self):
        for text in ("You take the blue pill, the story ends", "Take two pills with water",
                     "a little blue bird", "He sold Spanish flies to fishermen"):
            self.assertIsNone(engine.LINE_WORDS["sexref"].search(text), text)

    def test_both_readers_are_told(self):
        for text in (cc.TYPE_TEXT["sexref"], ai.LINE_TYPES["sexref"]):
            self.assertIn("Viagra", text)
            self.assertIn("aphrodisiac", text)
            self.assertIn("drugging someone to have sex", text)
        # the local reader still leaves other drug talk alone
        self.assertIn("other drugs", ai.LINE_TYPES["sexref"])


if __name__ == "__main__":
    unittest.main()
