"""Lauren's 50 First Dates report (2026-11-08, teens, word lists only): no subtitles were found
online, so only listed words were muted and the film's crude jokes went through. The name
"50 First Dates" was read as episode 50 of a show called "First Dates", and the subtitle
site's search finds nothing for a title starting with a number ("50 First Dates", "13 Going
on 30") but does for "Fifty First Dates". Movies are now looked up as movies, numbers are
spelled out when the first search finds nothing, and an older "none online" is looked up
again."""
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

import support
import cleanview as engine
import cvcore as cl
import cleanview_learn as learn

try:
    import subliminal
except Exception:                   # pragma: no cover
    subliminal = None


def found(text):
    words = [w for w in (cl.norm(t) for t in text.split()) if w]
    return [" ".join(words[i:j]) for i, j, _ in cl.find_language(words, list(cl.CATS))]


@unittest.skipUnless(subliminal, "no subtitle finder here")
class LookedUpAsAMovie(unittest.TestCase):

    def test_a_number_first_is_still_a_movie(self):
        for name, title, year in (("50 First Dates.m4v", "50 First Dates", None),
                                  ("50 First Dates (2004).m4v", "50 First Dates", 2004),
                                  ("13 Going on 30.mkv", "13 Going on 30", None),
                                  ("Toy Story 4.mkv", "Toy Story 4", None),
                                  ("Blade Runner 2049.mkv", "Blade Runner 2049", None)):
            with self.subTest(name):
                v = engine.sub_video(engine.guess_title(name), Path(name).suffix)
                self.assertIsInstance(v, subliminal.Movie)
                self.assertEqual((v.title, v.year), (title, year))

    def test_episodes_as_before(self):
        v = engine.sub_video(("Castle", 1, 7), ".mkv")
        self.assertIsInstance(v, subliminal.Episode)
        self.assertEqual((v.series, v.season, v.episode), ("Castle", 1, 7))

    def test_numbers_spelled_out_when_nothing_is_found(self):
        asked = []

        def list_subtitles(videos, langs):
            v = next(iter(videos))
            asked.append(v.title)
            if v.title == "Fifty First Dates":
                return {v: [NS(movie_name="50 First Dates", movie_year=2004, hearing_impaired=True,
                               provider_name="opensubtitles", text=None, id=1),
                            NS(movie_name="Fifty Shades of Grey", movie_year=2015,
                               hearing_impaired=False, provider_name="opensubtitles", text=None, id=2)]}
            return {v: []}

        def download(subs):
            for s in subs:
                s.text = "1\n00:00:01,000 --> 00:00:02,000\nAloha.\n"
        real = (subliminal.list_subtitles, subliminal.download_subtitles, subliminal.compute_score)
        self.addCleanup(lambda: (setattr(subliminal, "list_subtitles", real[0]),
                                 setattr(subliminal, "download_subtitles", real[1]),
                                 setattr(subliminal, "compute_score", real[2])))
        subliminal.list_subtitles, subliminal.download_subtitles = list_subtitles, download
        subliminal.compute_score = lambda s, v: 10
        got = list(engine.other_subtitles("50 First Dates.m4v", log=lambda m: None, tries=3))
        self.assertEqual(asked, ["50 First Dates", "Fifty First Dates"])
        self.assertEqual([w for _, w in got],                  # not Fifty Shades
                         ["hearing-impaired subtitles (2004) downloaded from opensubtitles"])

    def test_spelling_out(self):
        self.assertEqual(engine.number_titles("50 First Dates"), ["Fifty First Dates"])
        self.assertEqual(engine.number_titles("13 Going on 30"), ["Thirteen Going On Thirty"])
        self.assertEqual(engine.number_titles("21 Jump Street"),
                         ["Twenty-one Jump Street", "Twenty One Jump Street"])
        self.assertEqual(engine.number_titles("101 Dalmatians")[0], "One Hundred And One Dalmatians")
        self.assertEqual(engine.number_titles("Toy Story"), [])
        self.assertTrue(engine._same_title("50 First Dates", "Fifty First Dates"))
        self.assertTrue(engine._same_title("Twenty-One Jump Street", "21 Jump Street"))
        self.assertFalse(engine._same_title('"Big Mouth" Twenty Two and You', "21 Jump Street"))
        self.assertFalse(engine._same_title(None, "21 Jump Street"))


class LookedUpAgain(unittest.TestCase):

    def test_an_older_none_online_is_asked_again(self):
        miss = Path(tempfile.mkdtemp()) / "no_subtitles_online.txt"
        self.assertFalse(engine.remembered_miss(miss))
        miss.write_text(engine.MISS_REMEMBER, encoding="utf8")            # 1.18.33 and before
        self.assertFalse(engine.remembered_miss(miss))
        miss.write_text(engine.MISS_REMEMBER + "\n" + engine.SUB_LOOKUP, encoding="utf8")
        self.assertTrue(engine.remembered_miss(miss))
        old = time.time() - 4 * 86400
        os.utime(miss, (old, old))
        self.assertFalse(engine.remembered_miss(miss))


class WordsWithoutAnAI(unittest.TestCase):

    def test_nympho(self):
        self.assertEqual(found("How's that hot wahini nympho from Ohio, huh?"), ["nympho"])
        self.assertEqual(found("Daddy, what's a nympho?"), ["nympho"])
        self.assertEqual(found("She is a nymphomaniac."), ["nymphomaniac"])
        self.assertEqual(found("a water nymph in the pond"), [])

    def test_body_jokes(self):
        r = engine.LINE_WORDS["sexref"]
        for t in ("They only bite when you touch the private parts.",
                  "out of all mammals, they have the second largest penis"):
            self.assertIsNotNone(r.search(t), t)
        for t in ("It's a private party.", "We spoke privately.", "keep your parts private"):
            self.assertIsNone(r.search(t), t)

    def test_lines_taught(self):
        d = json.loads((support.ROOT / "shared_learned.json").read_text(encoding="utf8"))
        movies = d["shows"]["_movies@teens"]
        for line in ("lack of recent physical intimacy", "willingness to experiment",
                     "male parts can get pretty gigantic", "with their big winkies",
                     "unlimited boob access"):
            with self.subTest(line):
                key = next(k for k in movies["muted"] if line in k)
                self.assertEqual(movies["muted_for"][key], "sexref")


if __name__ == "__main__":
    unittest.main()
