"""The Resident S2E12 (1.18.167; the owner: "missed a reference to a woman having a girlfriend",
"she was referenced earlier as a she", "Yes, both"). The former prison guard is a woman (the
dialogue says "she" and "her", and names her Meg) but the voice check tagged her lines as a
man's voice, so Claude read her girlfriend lines as a man's."""
import json
import unittest
from pathlib import Path

import support  # noqa: F401  (must come first)
import cleanview as engine
import cleanview_claude as cc
import cleanview_learn as learn

SHARED = json.loads((Path(engine.__file__).parent / "shared_learned.json").read_text("utf8"))

LINES = ["I heard a rumor you were her favorite guard during her stint in prison.",
         "Yeah, and she was one of my favorite inmates, too.",
         "Mm. Sorry to say, I have no plans on going back there.",
         "How's your girlfriend?", "Oh, in Tampa. We broke up.", "Oh. No, we'll stay friends.",
         "No, scratch that. No, we won't.", "So how are you lovebirds?", "Yeah. Good."]
DIALOGUE = [{"s": 524.8 + 2.2 * i, "e": 526.6 + 2.2 * i, "text": t} for i, t in enumerate(LINES)]


class Episode12(unittest.TestCase):
    def scenes(self, ticked, episode=(2, 12)):
        return learn.title_scenes("the-resident@adults", "The Resident", DIALOGUE, ticked,
                                  episode=episode)

    def test_girlfriend_talk_muted(self):
        (sc,) = self.scenes(["samesex"])
        self.assertTrue(sc["mute_only"])
        self.assertEqual(sc["kind"], ["Same-sex relationship"])
        self.assertAlmostEqual(sc["s"], DIALOGUE[3]["s"] - 0.3, places=2)   # from "How's your
        self.assertAlmostEqual(sc["e"], DIALOGUE[7]["s"] - 0.2, places=2)   # ...to "lovebirds"

    def test_only_with_same_sex_ticked_and_only_this_episode(self):
        self.assertEqual(self.scenes(["sexref", "casual"]), [])
        self.assertEqual(self.scenes(["samesex"], episode=(2, 11)), [])

    def test_ex_girlfriend_line_taught(self):
        line = learn.norm("I'd like to call my ex-girlfriend, but I really blew that one.")
        sh = SHARED["shows"]["the-resident"]
        self.assertIn(line, sh["muted"])
        self.assertEqual(sh["muted_for"][line], "samesex")


class VoiceGuessYieldsToShe(unittest.TestCase):
    def test_claude_told_she_and_her_win(self):
        t = cc.TYPE_TEXT["samesex"]
        for words in ("'she' or 'her'", "tagged as a man's voice", "girlfriend",
                      "a man and a woman together"):
            self.assertIn(words, t)


if __name__ == "__main__":
    unittest.main()
