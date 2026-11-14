""""Blasted" and "blast it" are mild oaths (1.18.93, 2026-11-14). From Lauren's Poldark S1E1
report: "lather and blasted brat" muted "brat" but not "blasted"; asked whether to add it to
all three apps, she said "Yes, add it". Muted with the minced oaths ("darn", "heck"); blown
up, a loud noise or drunk is left alone."""
import unittest

import support  # noqa: F401  (sets up the sandbox first)
import cvcore as cl

CATS = [c for g in ("swearing", "mild", "deity", "minced", "rude") for c in cl.GROUPS[g]]


def muted(text):
    words = [w for w in (cl.norm(t) for t in text.split()) if w]
    return [" ".join(words[i:j]) for i, j, _ in cl.find_language(words, CATS)]


class Oath(unittest.TestCase):
    def test_the_oath(self):
        for text, want in (("lather and blasted brat", ["blasted", "brat"]),
                           ("Get that blasted dog out of my kitchen", ["blasted"]),
                           ("You blasted fool", ["blasted", "fool"]),
                           ("this blasted rain will not stop", ["blasted"]),
                           ("Turn off that blasted music", ["blasted"]),
                           ("Blast it, the horse has thrown a shoe", ["blast it"]),
                           ("Oh blast it all", ["oh blast it"]),
                           ("Blast you, Judd", ["blast you"]),
                           ("Blast and damnation", ["blast and damnation"]),
                           ("Oh blast, I forgot the key", ["oh blast"])):
            self.assertEqual(muted(text), want, text)

    def test_only_with_the_minced_oaths(self):
        words = ["that", "blasted", "dog"]
        self.assertEqual(cl.find_language(words, ["mild", "deity"]), [])
        self.assertTrue(cl.listed_word("blasted"))

    def test_blown_up_loud_or_drunk_left_alone(self):
        for text in ("The rocket blasted off at dawn",
                     "They blasted through the rock",
                     "He blasted the door open",
                     "The cannon blasted the wall",
                     "the music blasted from the speakers",
                     "He got blasted at the party",
                     "the town was blasted by the storm",
                     "a blasted heath under the moon",
                     "We had a blast at the fair",
                     "Turn the radio up full blast",
                     "The blast shook the windows",
                     "a blast from the past",
                     "Blast it open with the charge",
                     "blast them out of the water",
                     "Oh, what a blast"):
            self.assertEqual(muted(text), [], text)


if __name__ == "__main__":
    unittest.main()
