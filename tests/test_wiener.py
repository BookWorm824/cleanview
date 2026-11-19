""""little wiener" is a sexual reference, not when it's a dog or food (1.18.137; the owner,
2026-11-18: "little wiener when it doesn't mean a dog")."""
import unittest

import support  # noqa: F401  (must come first)
import cleanview as engine

SEXREF = engine.LINE_WORDS["sexref"]


class LittleWiener(unittest.TestCase):
    def test_sexual(self):
        for line in ("Nice try, little wiener.", "He has a little weiner.",
                     "Don't flatter yourself, little weenie."):
            self.assertIsNotNone(SEXREF.search(line), line)

    def test_a_dog_or_food(self):
        for line in ("Look at that cute little wiener dog!",
                     "Our dachshund is such a little wiener.",
                     "We had little wieners in a blanket.",
                     "Pass me a little weenie and some mustard."):
            self.assertIsNone(SEXREF.search(line), line)

    def test_the_stripper_guard_still_works(self):
        self.assertIsNone(SEXREF.search("Thanks for the paint stripper."))
        self.assertIsNotNone(SEXREF.search("She was a stripper."))


class RubbingHisBall(unittest.TestCase):
    """1.18.137 (the owner: "can we add the line 'rubbing his ball'", then "balls")."""

    def test_sexual(self):
        for line in ("He was rubbing his ball.", "He sat there rubbing his balls.",
                     "Stop rubbing your balls!", "He rubbed his balls and grinned."):
            self.assertIsNotNone(SEXREF.search(line), line)

    def test_a_game_or_a_thing(self):
        for line in ("The pitcher was rubbing his ball on the mound.",
                     "She kept rubbing her crystal ball.",
                     "He rubbed his ball for luck before the throw.",
                     "He was rubbing his bowling ball dry."):
            self.assertIsNone(SEXREF.search(line), line)


if __name__ == "__main__":
    unittest.main()
