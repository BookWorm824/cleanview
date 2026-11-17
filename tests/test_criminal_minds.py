"""Lauren's Criminal Minds S1E1 report (1.18.125, 2026-11-17, adults, the AI helper, made on
1.18.122; the owner: "yes fi them", "and the subtitle look up also"). "Criminal Minds - 1-1 --
Extreme Aggressor.m4v" was looked up as a movie (the wrong subtitles, 3% lined up) and learned
under movies; its rape case talk went through with coroner and detective talk ticked; and the
taunt's first line went through while the two after it were muted."""
import json
import unittest

import support  # noqa: F401  (must come first)
import cleanview as engine
import cleanview_learn as learn

FORENSIC = engine.LINE_WORDS["forensic"]


class TheName(unittest.TestCase):
    def test_season_dash_episode(self):
        self.assertEqual(engine.guess_title("Criminal Minds - 1-1 -- Extreme Aggressor.m4v"),
                         ("Criminal Minds", 1, 1))
        self.assertEqual(engine.guess_title("Criminal Minds - 2-14 - Sex, Birth, Death.m4v"),
                         ("Criminal Minds", 2, 14))
        self.assertEqual(engine.guess_title("Criminal Minds - 1-1.m4v"), ("Criminal Minds", 1, 1))
        self.assertEqual(learn.show_key(engine.guess_title(
            "Criminal Minds - 1-1 -- Extreme Aggressor.m4v")), "criminal-minds")

    def test_still_movies(self):
        for name in ("Apollo 13 - 1-1 Draft.mp4", "Ocean 11 - 2-3.mp4",
                     "Star Wars - 4-6 Collection.mkv"):
            self.assertIsNone(engine.guess_title(name)[1], name)


class RapeCaseTalk(unittest.TestCase):
    def test_coroner_and_detective_talk(self):
        for line in ("Murders have all involved rapes.",
                     "But rape without penetration is a form of voyeurism.",
                     "The last four murderers show he's an anger excitation rapist.",
                     "In 1979, they outfitted a van to rape and murder girls in California.",
                     "She was raped.", "slips them a sedative, then rapes them."):
            self.assertTrue(FORENSIC.search(line), line)

    def test_not_rape(self):
        for line in ("My therapist says hi.", "Grape juice, please.", "The rapeseed fields.",
                     "Hand me the rapier."):
            self.assertFalse(FORENSIC.search(line), line)

    def test_without_penetration_is_explicit(self):
        self.assertTrue(engine.EXPLICIT_FINDING.search(
            "But rape without penetration is a form of voyeurism"))


class TheTaunt(unittest.TestCase):
    def test_taught_for_the_show(self):
        with open(support.ROOT / "shared_learned.json", encoding="utf-8") as f:
            show = json.load(f)["shows"]["criminal-minds"]
        line = learn.norm("What'd they come up with when you fumbled your way into some girl's "
                          "pants and she started laughing when she got a good look at just")
        self.assertIn(line, show["muted"])
        self.assertEqual(show["muted_for"][line], "sexref")


if __name__ == "__main__":
    unittest.main()
