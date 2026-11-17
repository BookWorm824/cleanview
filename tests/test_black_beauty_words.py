"""Words from the owner's Black Beauty report (CleanRead, 2026-11-16, in the CleanListen chat; the
same words in every app): "leave all words except pussy. take that word out", "i guess if jerk is
used directed towards a person it should come out", "but if its a motion should stay. like he
jerked the rope", "and dumb if its aninsult"."""
import unittest

import support  # noqa: F401  (must come first)

import cvcore as cl

CATS = ["strong", "moderate", "mild", "deity", "minced", "samesex", "rude"]


def found(text):
    ws = [w for w in (cl.norm(w) for w in text.split()) if w]
    return [" ".join(ws[i:j]) for i, j, _ in cl.find_language(ws, CATS)]


class Pussy(unittest.TestCase):
    # out every time at first ("take that word out"), then, later that day, left when it's a cat
    # ("if pussy is used as a cat only", "it can stay", "but keep it limited"; CleanListen 1.17.54)
    def test_out(self):
        for t in ("Pussy willow", "Here, pussy, pussy", "Don't be a pussy",
                  "He's such a pussy, my cat is braver"):
            self.assertIn("pussy", found(t), t)

    def test_a_cat(self):
        for t in ("The pussy cat purred.", "She held the little pussy kitten.",
                  "The kitten mewed, and the old pussy licked its ears."):
            self.assertEqual(found(t), [], t)


class Jerk(unittest.TestCase):
    def test_at_a_person(self):
        for t in ("you jerk", "what a jerk", "don't be a jerk at the party", "you little jerk",
                  "out with a jerk like him", "a jerk of a husband", "he's such a jerk on the phone"):
            self.assertIn("jerk", found(t), t)

    def test_a_movement(self):
        for t in ("a jerk of his head", "with a sudden jerk", "gave the rein a jerk",
                  "he jerked the rope", "a jerk at the reins", "with a jerk the cart moved",
                  "moved in short jerks"):
            self.assertEqual(found(t), [], t)


class Dumb(unittest.TestCase):
    def test_an_insult(self):
        for t in ("you dumb animal", "that's dumb", "a dumb idea", "you're so dumb"):
            self.assertIn("dumb", found(t), t)

    def test_unable_to_speak(self):
        for t in ("our dumb beasts", "a poor dumb creature", "struck dumb", "she stood dumb",
                  "deaf and dumb", "in dumb amazement", "play dumb"):
            self.assertEqual(found(t), [], t)


if __name__ == "__main__":
    unittest.main()
