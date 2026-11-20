"""The owner's Person of Interest S1 report (1.18.101, 2026-11-14, adults, the AI helper, made on
1.18.100; passed on by the CleanListen chat). "Person of Interest S1 - (1).wmv" said "No
subtitles: couldn't tell which episode this is from its name" and was learned under movies.
The season, then the episode in brackets, is read as season and episode now."""
import unittest

import support  # noqa: F401  (sets up the sandbox first)
import cleanview as engine


class BracketedEpisode(unittest.TestCase):
    def test_season_then_episode_in_brackets(self):
        for name, want in (("Person of Interest S1 - (1).wmv", ("Person of Interest", 1, 1)),
                           ("Person of Interest S1 - (12).wmv", ("Person of Interest", 1, 12)),
                           ("Person of Interest S2 (3).mp4", ("Person of Interest", 2, 3)),
                           ("Person of Interest S1-(4).mkv", ("Person of Interest", 1, 4)),
                           ("Person of Interest S1 - [5].mkv", ("Person of Interest", 1, 5)),
                           ("Castle Season 2 - (6).mp4", ("Castle", 2, 6))):
            self.assertEqual(engine.guess_title(name), want, name)

    def test_learned_under_the_show(self):
        self.assertEqual(engine.learned_key("Person of Interest S1 - (1).wmv", {"profile": "adults"}),
                         "person-of-interest")

    def test_years_and_sizes_arent_episodes(self):
        got = engine.guess_title("Castle Season 2 (2009).mp4")
        self.assertTrue(got is None or got[1] is None, got)          # not episode 2009
        self.assertEqual(engine.guess_title("Person of Interest S1 [720p].mkv"), None)
        self.assertEqual(engine.guess_title("Selena (1997).m4v"), ("Selena (1997)", None, None))

    def test_the_names_that_worked_still_do(self):
        for name, want in (("Person of Interest S02E07.mkv", ("Person of Interest", 2, 7)),
                           ("Poldark S1 Ep. 1.mp4", ("Poldark", 1, 1)),
                           ("I Love Lucy 1 - Ep. 1.m4v", ("I Love Lucy", 1, 1)),
                           ("Castle Season 1 - Ep. 3.mp4", ("Castle", 1, 3))):
            self.assertEqual(engine.guess_title(name), want, name)
        self.assertIsNone(engine.guess_title("Poldark S1 D2.mkv"))


if __name__ == "__main__":
    unittest.main()
