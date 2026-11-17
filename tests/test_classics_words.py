"""Old meanings from CleanListen 1.17.57's ten classics (2026-11-17; passed on by the CleanView Play
chat): the family's donkey, sewing, "shut up" meaning closed, seabirds, a lamb at its bottle...
And here: "kick your ass" is still muted (CleanListen's donkey check took "kick" as a sign of
the animal, which would have let nine lines of past reviews through)."""
import unittest

import support  # noqa: F401  (must come first)
import cvcore as cl


def muted(text):
    words = [cl.norm(t) for t in text.split()]
    words = [w for w in words if w]
    return [" ".join(words[a:b]) for a, b, _ in cl.find_language(words, list(cl.CATS), [])]


class OldMeanings(unittest.TestCase):
    def test_left_alone(self):
        for line in ("The ass carried the load.",
                     "We brought the cow and the ass ashore.",
                     "I have found on board the ship, a cow and an ass, two goats, six sheep",
                     "Camels and asses are very fond of thistles",
                     # CleanListen 13669bf: a farm animal close by, after "my"/"our"
                     "both my cow and my ass", "even our ass came to the cart",
                     "our ass instantly ran up to take its favourite oats",
                     "He darned his own socks.", "darning hose by the fire",
                     "I like his neat darns.", "She sat with her darning-needle.",
                     "the garden which was shut up", "since it was shut up ten year'",
                     "that poor lad lyin' shut up", "most of them's shut up and locked",
                     "a stir of hidden pulses under the gray sod",
                     "quieted all pricks of conscience",
                     "the lamb began to suck it with ravenous ecstasy",
                     "each of the boys seized one of the sugarcanes and began to suck it",
                     "when I have sucked this part dry",
                     "she eats one before her face, and don't offer even a suck",
                     "all clipped an' spick an' span",
                     "you ain't dumb, I reckon",
                     "gulls, man of war birds, boobies, albatrosses, and a crowd of others",
                     "We all cast our eyes upon the pot with a sort of silent and stupid "
                     "perplexity",
                     "and then a second jerk, accompanied by a rapid motion of the boat",
                     "nuzzle into its folds and butt its tight-curled head",
                     "something of a butt with the country boys",
                     "if people wouldn't twit me about my looks",
                     "a chromo entitled, Christ Blessing Little Children"):
            self.assertEqual(muted(line), [], line)

    def test_still_muted(self):
        for line, want in (("Shut up and sit down.", "shut up"),
                           ("You ass, look what you did.", "ass"),
                           ("Don't be such an ass.", "ass"),
                           ("Prepare to get your ass kicked.", "ass"),
                           ("Track him down, catch up to him this time, kick his ass?", "ass"),
                           ("who got their asses kicked at Club 225 tonight.", "asses"),
                           ("and kick cancer's ass all in the same year.", "ass"),
                           ("Go kick some Red Rock ass.", "ass"),
                           ("That really sucks.", "sucks"),
                           ("Well, darn it.", "darn"),
                           ("You're so stupid.", "stupid"),
                           ("That was a dumb idea.", "dumb")):
            got = muted(line)
            self.assertTrue(any(want in g for g in got), (line, got))


if __name__ == "__main__":
    unittest.main()
