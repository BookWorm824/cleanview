"""Lauren's West Side Story report (2026-11-08). "West Side Story.m4v" has no year, so the
subtitle search matched every movie of that name with the same score, and the 2021 remake's
came first: only 22% of the words lined up, so no subtitles were used, and with them went the
right words ("every last buggin' gang" was heard as a swear) and the slurs. Now the best
subtitles of each movie are tried in turn until some line up (the 1961 film's: 89%)."""
import unittest
from types import SimpleNamespace as NS

import support  # noqa: F401  (sets up the sandbox first)
import cleanview as engine


def srt(lines, start=0.0, gap=3.0):
    out = []
    for k, text in enumerate(lines):
        s, e = start + k * gap, start + k * gap + 2.5
        f = lambda t: f"00:{int(t // 60):02}:{int(t % 60):02},{int(t * 1000) % 1000:03}"
        out.append(f"{k + 1}\n{f(s)} --> {f(e)}\n{text}\n")
    return "\n".join(out)


FILM_1961 = ["When you're a Jet you're a Jet all the way", "From your first cigarette to your last dying day",
             "Here come the Jets like a bat out of hell", "Someone gets in our way someone don't feel so well",
             "Every last buggin gang on the whole buggin street", "Cause your ma's hot for me",
             "I just met a girl named Maria", "And suddenly that name will never be the same to me",
             "Tonight tonight it all began tonight", "I feel pretty oh so pretty",
             "There's a place for us somewhere a place for us", "Boy boy crazy boy get cool boy"]
REMAKE = ["Completely different words from another script", "Nothing here was said in this film",
          "The lines were all written again for a new movie", "So hardly any of them line up at all",
          "Different scenes and different songs entirely", "Not one of these is what anyone heard"] * 2


def heard(lines, gap=3.0):
    """What the speech recognition heard: the 1961 words, 0.8 s later than the subtitles say."""
    asr = []
    for k, line in enumerate(lines):
        ws = line.split()
        for j, w in enumerate(ws):
            s = 0.8 + k * gap + 2.5 * j / len(ws)
            asr.append({"t": w, "s": s, "e": s + 0.2})
    return asr


class TryOtherSubtitles(unittest.TestCase):
    def test_each_movie_of_the_name_gets_a_turn(self):
        subs = [NS(id=1, movie_name="West Side Story", movie_year=2021, hearing_impaired=False),
                NS(id=2, movie_name="West Side Story", movie_year=2021, hearing_impaired=True),
                NS(id=3, movie_name="West Side Story", movie_year=2021, hearing_impaired=False),
                NS(id=4, movie_name="West Side Story", movie_year=1961, hearing_impaired=False),
                NS(id=5, movie_name="West Side Story", movie_year=1961, hearing_impaired=True)]
        order = [s.id for s in engine.subtitle_order(subs, lambda s: 216)]   # all scored the same
        self.assertEqual(order[:2], [2, 5])          # the best of each, hearing-impaired first
        self.assertEqual(sorted(order), [1, 2, 3, 4, 5])

    def test_a_better_score_still_comes_first(self):
        subs = [NS(id=1, movie_year=2021, hearing_impaired=True), NS(id=2, movie_year=1961)]
        order = engine.subtitle_order(subs, lambda s: 300 if s.id == 2 else 200)
        self.assertEqual([s.id for s in order], [2, 1])

    def test_the_ones_that_line_up_are_used(self):
        asr = heard(FILM_1961)
        asked = []

        def others():
            for text, why in ((srt(REMAKE), "subtitles (2021) again"), (srt(FILM_1961), "subtitles (1961)"),
                              (srt(FILM_1961), "never needed")):
                asked.append(why)
                yield text, why
        cues, frac, text, why = engine.pick_subtitles(srt(REMAKE), "subtitles (2021)", asr, others())
        self.assertTrue(cues)
        self.assertEqual(why, "subtitles (1961)")
        self.assertGreater(frac, 0.8)
        self.assertNotIn("never needed", asked)       # downloads stop once some line up
        self.assertAlmostEqual(cues[0]["s"], 0.8, delta=0.5)   # and they're re-timed

    def test_none_line_up(self):
        cues, frac, text, why = engine.pick_subtitles(srt(REMAKE), "subtitles (2021)",
                                                      heard(FILM_1961), iter([]))
        self.assertEqual(cues, [])
        self.assertEqual(why, "subtitles (2021)")
        self.assertLess(frac, 0.25)

    def test_first_ones_fine_nothing_else_fetched(self):
        def others():
            raise AssertionError("shouldn't look for others")
            yield
        cues, frac, text, why = engine.pick_subtitles(srt(FILM_1961), "first", heard(FILM_1961), others())
        self.assertTrue(cues)
        self.assertEqual(why, "first")

    def test_where_from_says_the_year(self):
        self.assertEqual(engine._sub_where(NS(hearing_impaired=True, movie_year=1961,
                                              provider_name="opensubtitles")),
                         "hearing-impaired subtitles (1961) downloaded from opensubtitles")


class NoAIPhraseList(unittest.TestCase):
    """The short list that works without an AI (LINE_WORDS) agrees with the word lists."""

    def test_gay_meaning_happy_isnt_a_same_sex_line(self):
        r = engine.LINE_WORDS["samesex"]
        for text in ("I feel pretty and witty and gay, and I pity any girl who isn't me tonight",
                     "Pretty and Witty and Gay", "so gay and carefree"):
            with self.subTest(text=text):
                self.assertIsNone(r.search(text))
        for text in ("He's gay and proud", "a gay couple", "Her brother is gay."):
            with self.subTest(text=text):
                self.assertIsNotNone(r.search(text))

    def test_thanks_for_the_quickie(self):
        # Red Eye (2026-11-08), after the airplane bathroom
        self.assertIsNotNone(engine.LINE_WORDS["sexref"].search("Well, thanks for the quickie."))
        self.assertIsNone(engine.LINE_WORDS["sexref"].search(
            "I thought he came down here for a quickie divorce"))


class LessonsBuiltIn(unittest.TestCase):
    def test_lines_taught(self):
        import json
        d = json.loads((support.ROOT / "shared_learned.json").read_text(encoding="utf8"))
        movies = d["shows"]["_movies@teens"]
        for line in ("cause your ma's hot for me", "go walk the streets like your sister",
                     "on your mother's side of the street"):
            with self.subTest(line):
                key = next(k for k in movies["muted"] if line in k)
                self.assertEqual(movies["muted_for"].get(key), "sexref")

    def test_note_for_the_movie(self):
        import cleanview_learn as learn
        notes = learn.notes("_movies@teens", "West Side Story")
        self.assertTrue(any("rumble" in n and "Riff" in n for n in notes))
        self.assertFalse(any("rumble" in n for n in learn.notes("_movies@teens", "Toy Story 4")))


if __name__ == "__main__":
    unittest.main()
