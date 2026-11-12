"""A badly numbered episode (1.18.59, Lauren 2026-11-11: "Castle Season 1 - Ep. 3.mp4" was
really episode 4, so episode 3's subtitles lined up 4% and none were used; the owner: "also
build in if it is say season 2 episode 5 but says season 3 episode 5"): after the episode's own
other subtitles, the neighbouring episodes' and then the neighbouring seasons' are tried, and the
note says which they were. The subtitle site is a stand-in: nothing goes online."""
import importlib.util
import inspect
import unittest
from types import SimpleNamespace
from unittest import mock

import support  # noqa: F401  (sets up the sandbox first)
import cleanview as engine

HAVE_FINDER = importlib.util.find_spec("subliminal") is not None


class Order(unittest.TestCase):
    def test_nearest_first_then_the_other_seasons(self):
        self.assertEqual(list(engine.neighbour_episodes(1, 3)),
                         [(1, 4), (1, 2), (1, 5), (1, 1), (2, 3)])
        self.assertEqual(list(engine.neighbour_episodes(3, 5)),
                         [(3, 6), (3, 4), (3, 7), (3, 3), (2, 5), (4, 5)])
        self.assertEqual(list(engine.neighbour_episodes(1, 1)), [(1, 2), (1, 3), (2, 1)])

    def test_notes(self):
        self.assertIn("for episode 4, so this file's episode number may be off",
                      engine.neighbour_note(1, 3, 1, 4))
        self.assertIn("for season 2, so this file's season number may be off",
                      engine.neighbour_note(3, 5, 2, 5))

    def test_tried_again_once_for_videos_tried_before(self):
        src = inspect.getsource(engine.analyze)
        self.assertIn("NEIGHBOUR_LOOKUP in tried.read_text", src)


@unittest.skipUnless(HAVE_FINDER, "the subtitle finder isn't installed")
class FromTheSite(unittest.TestCase):
    def site(self):
        """list_subtitles/download_subtitles stand-ins: two subtitles for every episode asked."""
        import subliminal
        asked = []

        def list_subtitles(videos, languages):
            v = next(iter(videos))
            asked.append((getattr(v, "season", None), getattr(v, "episode", None)))
            return {v: [SimpleNamespace(provider_name="site", hearing_impaired=k == 0,
                                        text=None, ep=asked[-1], k=k) for k in range(2)]}

        def download(subs):
            for s in subs:
                s.text = f"1\n00:00:01,000 --> 00:00:02,000\nS{s.ep[0]}E{s.ep[1]} #{s.k}\n"
        return asked, [mock.patch.object(engine, "_load_subtitle_finder", lambda log=None: None),
                       mock.patch.object(subliminal, "list_subtitles", list_subtitles),
                       mock.patch.object(subliminal, "download_subtitles", download),
                       mock.patch.object(subliminal, "compute_score", lambda s, v: 1)]

    def got(self, name):
        asked, patches = self.site()
        for p in patches:
            p.start()
        try:
            return asked, list(engine.other_subtitles(name, log=lambda m: None))
        finally:
            for p in patches:
                p.stop()

    def test_an_episode_tries_its_own_then_the_neighbours(self):
        asked, got = self.got("Castle Season 1 - Ep. 3.mp4")
        self.assertEqual(asked, [(1, 3), (1, 4), (1, 2), (1, 5), (1, 1), (2, 3)])
        texts = [t.splitlines()[2] for t, _ in got]
        self.assertEqual(texts[:2], ["S1E3 #0", "S1E3 #1"])            # its own first
        self.assertEqual(texts[2:], ["S1E4 #0", "S1E2 #0", "S1E5 #0", "S1E1 #0", "S2E3 #0"])
        whys = [w for _, w in got]
        self.assertNotIn("may be off", whys[0])
        self.assertIn("episode 4, so this file's episode number may be off", whys[2])
        self.assertIn("season 2, so this file's season number may be off", whys[-1])

    def test_the_first_that_lines_up_is_used_and_no_more_are_fetched(self):
        asked, patches = self.site()
        lined = []

        def sync(cues, asr):
            lined.append(cues[0]["text"] if cues else "")
            return (cues, 0.9) if cues and cues[0]["text"] == "S1E4 #0" else ([], 0.04)
        patches = patches + [mock.patch.object(engine, "sync_cues", sync)]
        for p in patches:
            p.start()
        try:
            first = "1\n00:00:01,000 --> 00:00:02,000\nS1E3 #0\n"
            cues, frac, text, why = engine.pick_subtitles(
                first, "subtitles downloaded from site", [{"t": "x"}],
                engine.other_subtitles("Castle Season 1 - Ep. 3.mp4", log=lambda m: None))
        finally:
            for p in patches:
                p.stop()
        self.assertEqual(text.splitlines()[2], "S1E4 #0")
        self.assertIn("episode 4", why)
        self.assertEqual(asked, [(1, 3), (1, 4)])          # stopped once episode 4 lined up

    def test_a_movie_has_no_neighbours(self):
        asked, got = self.got("West Side Story.m4v")
        self.assertEqual(len(asked), 1)
        self.assertTrue(all("may be off" not in w for _, w in got))


if __name__ == "__main__":
    unittest.main()
