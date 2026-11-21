""""jerk me off" and its forms are sexual words, for every age (1.18.157; the owner in the
CleanStream chat: "jerk me off should go in the sex catogory for all"). Each word alone stays as
it was: "jerk" is a rude word, "off" nothing."""
import unittest

import support  # noqa: F401  (must come first)
import cvcore as cl
import cleanview as engine

CATS = list(cl.CATS)


def found(text):
    w = [cl.norm(x) for x in text.split()]
    return [(" ".join(w[a:b]), c) for a, b, c in cl.find_language(w, CATS)]


class JerkMeOff(unittest.TestCase):
    def test_caught(self):
        for t, said in (("jerk me off", "jerk me off"), ("She jerked him off.", "jerked him off"),
                        ("I'll jerk you off", "jerk you off"), ("jerk her off", "jerk her off"),
                        ("jack them off", "jack them off"), ("jerking each other off",
                                                             "jerking each other off")):
            self.assertIn((said, "sexwords"), found(t), t)
            self.assertTrue(engine.LINE_WORDS["sexref"].search(t), t)

    def test_already_caught_forms(self):
        for t in ("he was jerking off", "jerked off", "he jerks off"):
            self.assertEqual([c for _, c in found(t)], ["sexwords"], t)

    def test_pulled_off_something_left_alone(self):
        for t in ("He jerked him off his feet", "She jerked her off the ledge",
                  "it jerked me off balance", "the car jerked off the road"):
            self.assertEqual(found(t), [], t)
            self.assertIsNone(engine.LINE_WORDS["sexref"].search(t), t)

    def test_each_word_alone_as_before(self):
        self.assertEqual(found("you jerk"), [("jerk", "rude")])
        self.assertEqual(found("he took the day off"), [])

    def test_with_sexual_references_ticked(self):
        w = [cl.norm(x) for x in "jerk me off".split()]
        self.assertEqual(cl.find_language(w, cl.cats_for(["swearing"], {})), [])
        self.assertTrue(cl.find_language(w, cl.cats_for([], {"sexref": True})))


if __name__ == "__main__":
    unittest.main()
