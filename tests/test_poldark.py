"""Lauren's Poldark S1E1 report (1.18.92, 2026-11-14, kids, the AI helper, made on 1.18.89).

"Poldark S1 Ep. 1.mp4" said "No subtitles: couldn't tell which episode this is from its name",
so nothing checked what was heard: "he's very full of himself" was heard as "very fool of
himself" and "fool" was muted. Names like "<show> S1 Ep. 1" are read as season 1 episode 1
now."""
import unittest

import support  # noqa: F401  (sets up the sandbox first)
import cleanview as engine


class EpisodeNames(unittest.TestCase):
    def test_s_and_ep(self):
        for name, want in (("Poldark S1 Ep. 1.mp4", ("Poldark", 1, 1)),
                           ("Poldark S1 Ep 1.mp4", ("Poldark", 1, 1)),
                           ("Poldark S1 Ep. 10.mp4", ("Poldark", 1, 10)),
                           ("Poldark S2 - Ep. 4.mkv", ("Poldark", 2, 4)),
                           ("Poldark s3 episode 7.mkv", ("Poldark", 3, 7)),
                           ("Poldark_S1_Ep_2.mp4", ("Poldark", 1, 2))):
            self.assertEqual(engine.guess_title(name), want, name)

    def test_the_names_that_worked_still_do(self):
        for name, want in (("Poldark S01E01.mp4", ("Poldark", 1, 1)),
                           ("I Love Lucy 1 - Ep. 1.m4v", ("I Love Lucy", 1, 1)),
                           ("Castle Season 1 - Ep. 3.mp4", ("Castle", 1, 3)),
                           ("Monster's University.m4v", ("Monster's University", None, None)),
                           ("50 First Dates.m4v", ("50 First Dates", None, None))):
            self.assertEqual(engine.guess_title(name), want, name)

    def test_disc_names_still_cant_be_told(self):
        for name in ("Poldark S1 D2.mkv", "Poldark S1 Disc 1 Title 3.mkv"):
            self.assertIsNone(engine.guess_title(name), name)

    def test_learned_under_the_show(self):
        self.assertTrue(engine.learned_key("Poldark S1 Ep. 1.mp4", {"profile": "kids"})
                        .startswith("poldark"))


if __name__ == "__main__":
    unittest.main()
