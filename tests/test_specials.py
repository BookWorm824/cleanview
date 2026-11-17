"""A season's special gets subtitles too (1.18.124; the owner, 2026-11-17, of "Call the Midwife -
Christmas Special S2.mp4", which got "No subtitles: couldn't tell which episode this is from its
name": "is it possobe if a video just says a season number and say a special that it still gets
searched for subitles", "search the seaon ad look uner christtmas and see which agrees"). The
subtitle site files a season's Christmas special as its episode 0, and lists a show's whole run
under any of its episodes; the specials are tried, nearest season first, and the first that
lines up with what was heard is used. Tried for real on her report's dialogue: the 2013
special's lined up 92%. The subtitle site here is a stand-in: nothing goes online."""
import importlib.util
import unittest
from types import SimpleNamespace
from unittest import mock

import support  # noqa: F401  (sets up the sandbox first)
import cleanview as engine

HAVE_FINDER = importlib.util.find_spec("subliminal") is not None


class TheName(unittest.TestCase):
    def test_a_special_and_its_season(self):
        for name, want in (
                ("Call the Midwife - Christmas Special S2.mp4", ("Call the Midwife", 2, 0)),
                ("Call the Midwife - Christmas Special S1.avi", ("Call the Midwife", 1, 0)),
                ("Call the Midwife Season 3 Christmas Special.mkv", ("Call the Midwife", 3, 0)),
                ("Downton Abbey Series 4 Christmas Special.mp4", ("Downton Abbey", 4, 0)),
                ("Doctor Who S5 Special.mkv", ("Doctor Who", 5, 0)),
                ("E:/TV/Call the Midwife/Season 2/Christmas Special.mkv",
                 ("Call the Midwife", 2, 0))):
            self.assertEqual(engine.guess_title(name), want, name)

    def test_not_a_special(self):
        self.assertEqual(engine.guess_title("Special Agent Oso S1E2.mkv"),
                         ("Special Agent Oso", 1, 2))
        self.assertEqual(engine.guess_title("Castle S01E04.mp4"), ("Castle", 1, 4))
        self.assertEqual(engine.guess_title("My Special Day.mp4"), ("My Special Day", None, None))
        self.assertEqual(engine.guess_title("The Office - Christmas Special.mkv"),   # no season
                         ("The Office - Christmas Special", None, None))

    def test_the_other_seasons_specials_next(self):
        self.assertEqual(list(engine.neighbour_episodes(2, 0)), [(3, 0), (1, 0), (4, 0)])
        self.assertEqual(list(engine.neighbour_episodes(1, 0)), [(2, 0), (3, 0)])
        self.assertIn("for season 3's special, so this file's season number may be off",
                      engine.neighbour_note(2, 0, 3, 0))

    def test_the_sites_names(self):
        a = SimpleNamespace(movie_name='"Call the Midwife" Christmas Special 2013',
                            series_season=3, series_episode=0, movie_year=2013)
        b = SimpleNamespace(movie_full_name="Call the Midwife - S02E00  Christmas Special - 2012",
                            movie_title="Christmas Special - 2012", series_season=2,
                            series_episode=None, movie_year=2012)
        c = SimpleNamespace(movie_name='"Call the Midwife" Episode #2.4', series_season=2,
                            series_episode=4, movie_year=2013)
        self.assertEqual(engine._special_key(a)[1:], (3, 0, 2013))
        self.assertEqual(engine._special_key(b)[1:], (2, 0, 2012))
        self.assertTrue(engine._is_special(a) and engine._is_special(b))
        self.assertFalse(engine._is_special(c))


@unittest.skipUnless(HAVE_FINDER, "the subtitle finder isn't installed")
class FromTheSite(unittest.TestCase):
    """The site lists the show's whole run (episodes and specials) whatever is asked."""
    RUN = [("Episode #2.4", 2, 4, 2013), ("Christmas Special 2017", 7, 0, 2017),
           ("Christmas Special 2025 Part 1", 0, 0, 2025), ("Christmas Special 2013", 3, 0, 2013),
           ("Episode #3.5", 3, 5, 2014), ("Christmas Special 2018", 8, 0, 2018),
           ("Christmas Special 2013", 3, 0, 2013)]

    def site(self):
        import subliminal
        asked, fetched = [], []

        def list_subtitles(videos, languages):
            v = next(iter(videos))
            asked.append((v.season, v.episode))
            return {v: [SimpleNamespace(provider_name="site", hearing_impaired=False, text=None,
                                        movie_name=f'"Call the Midwife" {n}', series_season=s,
                                        series_episode=e, movie_year=y)
                        for n, s, e, y in self.RUN]}

        def download(subs):
            for s in subs:
                fetched.append(s.movie_name.split('" ')[1])
                s.text = f"1\n00:00:01,000 --> 00:00:02,000\n{fetched[-1]}\n"
        return asked, fetched, [
            mock.patch.object(engine, "_load_subtitle_finder", lambda log=None: None),
            mock.patch.object(subliminal, "list_subtitles", list_subtitles),
            mock.patch.object(subliminal, "download_subtitles", download),
            mock.patch.object(subliminal, "compute_score", lambda s, v: 1)]

    def run_it(self, lines_up):
        asked, fetched, patches = self.site()

        def sync(cues, asr):
            return (cues, 0.92) if cues and cues[0]["text"] == lines_up else ([], 0.03)
        for p in patches + [mock.patch.object(engine, "sync_cues", sync)]:
            p.start()
        try:
            got = engine.pick_subtitles(
                "1\n00:00:01,000 --> 00:00:02,000\nnothing\n", "first", [{"t": "x"}],
                engine.other_subtitles("Call the Midwife - Christmas Special S2.mp4",
                                       log=lambda m: None))
        finally:
            mock.patch.stopall()
        return asked, fetched, got

    def test_every_special_is_tried_nearest_season_first(self):
        asked, fetched, (cues, frac, text, why) = self.run_it("Christmas Special 2018")
        self.assertEqual(asked[0], (2, 0))                     # season 2's special first
        self.assertEqual(fetched[:3], ["Episode #2.4", "Christmas Special 2017",
                                       "Christmas Special 2025 Part 1"])    # its own best three
        self.assertEqual(fetched[3:], ["Christmas Special 2013", "Christmas Special 2018"])
        self.assertNotIn("Episode #3.5", fetched)              # not an episode
        self.assertEqual(fetched.count("Christmas Special 2013"), 1)   # each special once
        self.assertEqual(text.splitlines()[2], "Christmas Special 2018")
        self.assertIn("season 8's special", why)

    def test_stops_at_the_one_that_lines_up(self):
        asked, fetched, (cues, frac, text, why) = self.run_it("Christmas Special 2017")
        self.assertEqual(fetched, ["Episode #2.4", "Christmas Special 2017"])
        self.assertEqual(asked, [(2, 0)])


if __name__ == "__main__":
    unittest.main()
