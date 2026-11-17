"""The sexual words research (1.18.127; the owner, 2026-11-17: "do research on words that world
uses as innuendo/sexual terms - do nitty gritty research - make sure all are on our list").
`SEXUAL_TERMS`, `CASUAL_TERMS`, `FORENSIC_TERMS` and the same-sex additions, each caught in a
sentence, and the everyday meanings next to them left alone."""
import time
import unittest

import support  # noqa: F401  (must come first)
import cleanview as engine

L = engine.LINE_WORDS


def found(line):
    return {k for k, rx in L.items() if rx.search(line)}


class Caught(unittest.TestCase):
    def check(self, filt, lines):
        for line in lines:
            self.assertIn(filt, found(line), line)

    def test_sexual_references(self):
        self.check("sexref", (
            "She gave him a handjob.", "He went down on her.", "I'd tap that.",
            "Did you get laid?", "Get your freak on!", "They were knocking boots all night.",
            "Netflix and chill?", "He got a hard-on.", "He was rubbing one out.",
            "He wanted to jump her bones.", "Stop flogging the dolphin.", "I want to shag you.",
            "She's a call girl.", "They met at a brothel.", "Is that porno?",
            "I was watching pornography.", "No more schtupping my wife.", "What a schlong.",
            "You're a gigolo?", "I'm dying to cop a feel.", "Which makes you sloppy seconds.",
            "They cross-stitch pillows with risqué phrases.", "He's running an escort service.",
            "We tried the reverse cowgirl.", "Masturbation and wet dreams.", "Your place or mine?",
            "That was orgasmic.", "He has a foot fetish.", "Death by coitus.", "Smash or pass?",
            "Thirst trap.", "They found a vibrator.", "Shagging in the shed.",
            "He couldn't get it up.", "Summa cum laude? No, cum on the sheets.",
            "after you get into their pants", "a peeping Tom", "You have an atrophied testicle.",
            # the owner in the CleanStream chat: "and the term gang bang"
            "It was a gang bang.", "a gangbang video", "They gang-banged her."))

    def test_sleeping_around(self):
        self.check("casual", ("He is a womanizer.", "It appears our boy's a ladies' man.",
                              "Accused of adultery.", "She's his side chick.",
                              "He's sowing his wild oats.", "They have an open marriage."))

    def test_case_talk(self):
        self.check("forensic", ("He was a pedophile.", "a convicted child molester",
                                "Charged with indecent exposure.", "bestiality and incest"))

    def test_same_sex(self):
        self.check("samesex", ("She is bi-curious.", "He's a twink."))


class LeftAlone(unittest.TestCase):
    def test_everyday_meanings(self):
        for line in ("He has a shag carpet.", "She graduated summa cum laude.",
                     "We beat off the attackers.", "Don't be so hard on yourself.",
                     "He'll eat her out of house and home.", "Let's get a head start.",
                     "Get head lice treatment.", "He tried to pervert the course of justice.",
                     "Twinkies for lunch.", "We need to reach around the back.",
                     "They become pret yoni, a ghost.", "That's what she said, right?",
                     "Hand me the testing kit.", "She wore a shaggy coat.",
                     "I'll whack off the dead branches.", "They live in South Carolina.",
                     "Hello, Carol.", "The cumin is in the cupboard.",
                     "He was a gangbanger in LA.", "He quit gangbanging at 16.",
                     # CleanListen 516fff6's guards, from its classics (1.18.128)
                     "She went down on her knees.", "going down on her hands and knees",
                     "the sun went down on them", "She tidies the room.",
                     "face to face, sitting in the heather", "a topless automobile",
                     "an orgy of eating", "male members of the family",
                     "a key party to the deal", "the girl on top of the wall",
                     "a bit on the side of the road", "a good lay of the land",
                     "the car jerked off the road", "rimming the glass with salt",
                     "the purple-headed mountain", "He got into his pants and shirt."):
            hit = found(line) & {"sexref", "casual", "forensic", "samesex"}
            self.assertFalse(hit, f"{line} -> {hit}")

    def test_still_quick(self):
        lines = ["What did you say to the man at the door last night?"] * 2000
        t = time.perf_counter()
        for line in lines:
            L["sexref"].search(line)
            L["casual"].search(line)
        self.assertLess(time.perf_counter() - t, 2.0)


if __name__ == "__main__":
    unittest.main()
