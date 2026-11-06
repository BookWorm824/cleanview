"""Jason's That Thing You Do runs (2026-11-05). Without an AI his chat notes reach nothing, so
he had to correct the same things on every scan. Now:
1. her own choices on a video's scenes come back when the same video is scanned again;
2. "just the word" is learned as that (not as a line that's fine);
3. "Santa Anita" and "Santa Monica" aren't Christmas;
4. subtitles that only say someone screams are offered unticked, not cut;
5. the AI helper's flirting check follows the notes, and its "two men" yields to its own
   sentence about a man and a woman."""
import unittest
from unittest import mock

import support  # noqa: F401

import cleanview as engine
import cleanview_ai as ai
import cleanview_learn as learn

MOVIE = r"D:\Movies\That Thing You Do.m4v"


def scene(s, e, kind, cut=True, **k):
    return dict({"s": s, "e": e, "kind": [kind], "cut": cut}, **k)


class SameMovieAgain(unittest.TestCase):
    def setUp(self):
        self.key = "ttyd@teens"
        slam = scene(1044.0, 1057.0, "Violence", cut=False, by_you=True)      # the phone slam
        shirt = scene(149.0, 153.0, "Nudity", cut=False, _shown=True)         # unticked by him
        left = scene(1836.0, 1851.0, "Violence", cut=True, _shown=True)       # left as it was
        learn.record(self.key, [], [], [], [slam, shirt, left], [False, False, True], [], [], [],
                     video=MOVIE)

    def test_his_choices_come_back_on_the_next_scan(self):
        again = [scene(1044.5, 1057.4, "Violence"), scene(148.6, 153.2, "Nudity"),
                 scene(1836.0, 1851.0, "Violence"), scene(3000.0, 3010.0, "Violence")]
        learn.apply(self.key, [], [], again, [], video=MOVIE)
        self.assertFalse(again[0]["cut"])
        self.assertEqual(again[0]["learned"], "you kept this scene before")
        self.assertFalse(again[1]["cut"])
        self.assertTrue(again[2]["cut"], "left as the scan had it: not his choice")
        self.assertNotIn("learned", again[2])
        self.assertTrue(again[3]["cut"], "a scene he never saw")

    def test_only_for_that_movie_and_that_kind(self):
        other = [scene(1044.5, 1057.4, "Violence")]
        learn.apply(self.key, [], [], other, [], video=r"D:\Movies\Another Movie.m4v")
        self.assertTrue(other[0]["cut"])
        kiss = [scene(1044.5, 1057.4, "Kiss")]
        learn.apply(self.key, [], [], kiss, [], video=MOVIE)
        self.assertNotIn("learned", kiss[0])

    def test_changing_his_mind_wins(self):
        again = scene(1044.5, 1057.4, "Violence", cut=True, by_you=True)
        learn.record(self.key, [], [], [], [again], [True], [], [], [], video=MOVIE)
        later = [scene(1044.0, 1057.0, "Violence", cut=False)]
        learn.apply(self.key, [], [], later, [], video=MOVIE)
        self.assertTrue(later[0]["cut"])
        self.assertEqual(later[0]["learned"], "you cut this scene before")


class JustTheWord(unittest.TestCase):
    LINE = "Movie cameras. Jiminy Christmas."

    def test_learned_as_just_the_word(self):
        line = {"s": 1655.6, "e": 1658.9, "text": self.LINE, "by_you": True, "mute": False}
        word = {"s": 1657.9, "e": 1658.5, "raw": "christmas", "word": "christmas", "cat": "claude",
                "by_you": True}
        learn.record("wordonly", [line], [False], [], [], [], [], [word], [True])
        d = learn.load("wordonly")
        self.assertEqual(d["word_only"][learn.norm(self.LINE)], ["christmas"])
        self.assertNotIn(learn.norm(self.LINE), d["kept"], "not a line that's fine")

    def test_starts_that_way_next_time(self):
        d = learn.load("wordonly2")
        d["word_only"][learn.norm(self.LINE)] = ["christmas"]
        learn.save("wordonly2", d)
        st = {"path": MOVIE, "info": {}, "mutes": [],
              "lines": [{"s": 1655.6, "e": 1658.9, "text": self.LINE, "mute": True}],
              "asr": [["movie", 1655.6, 1656.0], ["cameras", 1656.0, 1656.6],
                      ["jiminy", 1656.9, 1657.6], ["christmas", 1657.7, 1658.4]]}
        self.assertEqual(engine.learned_word_only(st, "wordonly2"), 1)
        line = st["lines"][0]
        self.assertFalse(line["mute"])
        self.assertIn("christmas", line["learned"])
        (m,) = st["mutes"]
        self.assertEqual(m["raw"], "christmas")
        self.assertFalse(m["keep"])
        self.assertTrue(m["learned"])

    def test_the_whole_line_again_if_she_ticks_it(self):
        line = {"s": 1.0, "e": 3.0, "text": self.LINE, "by_you": True, "mute": False}
        word = {"s": 2.0, "e": 2.5, "raw": "christmas", "by_you": True}
        learn.record("wordonly3", [line], [False], [], [], [], [], [word], [True])
        learn.record("wordonly3", [dict(line, mute=True)], [True], [], [], [], [], [], [])
        self.assertNotIn(learn.norm(self.LINE), learn.load("wordonly3")["word_only"])


class SantaThePlace(unittest.TestCase):
    def test_place_names_are_not_christmas(self):
        r = engine.LINE_WORDS["christmas"]
        for text in ("So, Solly, how much did you lose at Santa Anita last year?",
                     "From the brand-new City of Broadcasting in Santa Monica, California...",
                     "We drove to Santa Fe.", "A cruise to Christmas Island."):
            with self.subTest(text=text):
                self.assertIsNone(r.search(text))
        for text in ("Here comes Santa Claus!", "Santa and his elves", "Movie cameras. "
                     "Jiminy Christmas.", "Christmas in July.", "Santa!"):
            with self.subTest(text=text):
                self.assertIsNotNone(r.search(text))


class ScreamingAlone(unittest.TestCase):
    def snd(self):
        return {"t": [5000.0], "labels": engine.TRACKED, "p": [[0.0] * len(engine.TRACKED)]}

    def test_offered_not_cut(self):
        (sc,) = engine.violence_scenes(self.snd(), [{"s": 1836.0, "e": 1851.0,
                                                     "text": "[screaming continues]"}])
        self.assertFalse(sc["sure"])

    def test_gunfire_in_the_subtitles_still_cuts(self):
        (sc,) = engine.violence_scenes(self.snd(), [{"s": 100.0, "e": 110.0,
                                                     "text": "[gunshot] [screaming]"}])
        self.assertTrue(sc["sure"])


class FlirtingCheck(unittest.TestCase):
    def setUp(self):
        self.prompts = []

        def chat(prompt, *a, schema=None, **k):
            self.prompts.append(prompt)
            if "quote" in (schema or {}).get("properties", {}):
                return {"romance": True, "between": "two men", "lines": [1],
                        "quote": "pretty baby", "what": "A man flirts with a woman, calling her "
                                                        "pretty baby"}
            return {"romance": True, "between": "two men"}
        p = mock.patch.object(ai, "chat", chat)
        p.start()
        self.addCleanup(p.stop)
        self.lines = [{"s": 2942.0, "e": 2944.0, "text": "Hey, pretty baby, wanna dance?"},
                      {"s": 2944.5, "e": 2946.0, "text": "Sure."}]

    def test_a_man_and_a_woman_isnt_two_men(self):
        (f,) = ai.romance_scenes(self.lines, None)
        self.assertEqual(f["between"], "mf")

    def test_two_men_stays_two_men(self):
        self.assertEqual(ai._between_checked("mm", "Two men flirt; he asks him out"), "mm")
        self.assertEqual(ai._between_checked("ff", "Two women; she asks her out"), "ff")

    def test_follows_the_notes(self):
        note = "Men talking or joking together isn't same-sex romance."
        ai.romance_scenes(self.lines, None, notes=[note])
        self.assertTrue(self.prompts and all(note in p for p in self.prompts))

    def test_analyze_passes_the_notes(self):
        src = (support.ROOT / "cleanview.py").read_text(encoding="utf8")
        call = src[src.index("flirts = ai.romance_scenes("):]
        self.assertIn("notes=told", call[:400])


if __name__ == "__main__":
    unittest.main()
