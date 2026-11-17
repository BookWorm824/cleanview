"""A face screwed up isn't rude (1.18.117; CleanListen's The Railway Children lessons, the owner,
2026-11-16: "i think too much was flagged here"; the same words in every app)."""
import unittest

import support  # noqa: F401  (must come first)
import cvcore as c

CATS = [x for g in ("swearing", "mild", "deity", "minced") for x in c.GROUPS[g]]


def found(text):
    w = [x for x in (c.norm(t) for t in text.split()) if x]
    return [" ".join(w[i:j]) for i, j, _ in c.find_language(w, CATS)]


class ScrewedFace(unittest.TestCase):
    def test_left_alone(self):
        for t in ("asked Phyllis, screwing her eyelids more tightly together",
                  "He screwed his eyes shut.", "She would screw her face up at him.",
                  "screwing up her face", "he screwed her eyes tight against the wind"):
            self.assertEqual(found(t), [], t)

    def test_still_rude(self):
        self.assertEqual(found("He screwed her over."), ["screwed her over"])
        self.assertEqual(found("Screw her, she left me"), ["screw her"])
        self.assertEqual(found("Latimer screwed us."), ["screwed us"])


if __name__ == "__main__":
    unittest.main()
