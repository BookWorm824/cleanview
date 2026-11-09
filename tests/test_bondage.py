"""Lauren (2026-11-08): "bondage" and "safe word" are sexual references (Castle S1E1: "Bondage.
My safe word is 'apples.'"). The whole line goes, with no AI (LINE_WORDS["sexref"]); "bondage"
meaning slavery doesn't count, nor a safe word for something."""
import unittest

import support  # noqa: F401  (sets up the sandbox first)
import cleanview as engine


class BondageAndSafeWord(unittest.TestCase):

    def test_sexual(self):
        r = engine.LINE_WORDS["sexref"]
        for t in ('Bondage. My safe word is "apples."', "Are you into bondage?",
                  "What's your safe word?", "We need a safeword.",
                  "Pick safe words with your partner."):
            with self.subTest(t):
                self.assertIsNotNone(r.search(t))

    def test_slavery_and_everyday(self):
        r = engine.LINE_WORDS["sexref"]
        for t in ("out of the house of bondage", "He freed them from bondage.",
                  "the bondage of sin", "Israel was in bondage in Egypt", "sold into bondage",
                  "Is there a safe word to use?", "That's a safe word for kids to say",
                  "The house is safe.", "Keep your word."):
            with self.subTest(t):
                self.assertIsNone(r.search(t))


if __name__ == "__main__":
    unittest.main()
