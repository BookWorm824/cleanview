"""Words from CleanListen 1.17.44 (2026-11-15, the owner's Camp Club Girls report; the same words in
every app): "fool" as fooling someone, "play dumb", "shut it softly" closing a door. And kept
here: "What a fool you are!" is still calling someone a fool (FOOL_NOUN_PREV)."""
import unittest

import support  # noqa: F401  (sets up the sandbox first)
import cvcore as cv


def found(text):
    w = [x for x in (cv.norm(t) for t in text.split()) if x]
    return [" ".join(w[i:j]) for i, j, _ in cv.find_language(w, list(cv.CATS))]


class Fool(unittest.TestCase):
    def test_fooling_someone_left_alone(self):
        for text in ("You are too honest to try to fool yourself.", "You can't fool me.",
                     "I mooned around her for months, making a complete fool of myself.",
                     "It won't fool anybody."):
            self.assertEqual(found(text), [], text)

    def test_calling_someone_a_fool_still_muted(self):
        for text in ("Don't be a fool.", "You fool!", "What a fool you are!",
                     "Such a fool you are.", "You're a fool to trust him."):
            self.assertEqual(found(text), ["fool"], text)


class PlayDumb(unittest.TestCase):
    def test(self):
        for text in ("He played dumb when they asked.", "Play dumb?", "best just to play dumb"):
            self.assertEqual(found(text), [], text)
        self.assertEqual(found("That's dumb."), ["dumb"])


class ShutIt(unittest.TestCase):
    def test(self):
        for text in ("Elizabeth tiptoed to the door, shut it softly, and turned the lock.",
                     "He shut it behind him.", "She shut it quietly."):
            self.assertEqual(found(text), [], text)
        for text in ("Shut it!", "Shut it, Harold."):
            self.assertEqual(found(text), ["shut it"], text)


if __name__ == "__main__":
    unittest.main()
