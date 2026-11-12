"""A muted stretch of 4 seconds or more is cut instead (1.18.60, the owner: "if something that is
muted, is longer then 4 seconds, go ahead and cut the scene so its not a long gap of silence").
Mutes under a second apart count as one stretch; shorter ones stay muted; the report says so."""
import json
import tempfile
import unittest
from pathlib import Path

import support
import test_timing as T

import cleanview as engine


class Stretches(unittest.TestCase):
    def test_four_seconds_or_more(self):
        L = engine.long_mutes
        self.assertEqual(L([(10.0, 14.0)]), [(10.0, 14.0)])
        self.assertEqual(L([(10.0, 13.9)]), [])
        self.assertEqual(L([(10.0, 12.0), (12.5, 15.0)]), [(10.0, 15.0)])   # joined over a pause
        self.assertEqual(L([(1.0, 3.0), (4.2, 6.0)]), [])                    # a real gap: two
        self.assertEqual(L([(1.0, 3.0), (3.4, 5.6), (30.0, 31.0)]), [(1.0, 5.6)])  # two lines
        self.assertEqual(L([]), [])

    def test_words_muted_one_by_one_stay_words(self):
        # a word every 0.8 s with talking between (Shawshank-like): not a long silence
        words = [(i * 0.8, i * 0.8 + 0.4) for i in range(150)]
        self.assertEqual(engine.long_mutes(words), [])
        # unless one of them is itself long
        self.assertEqual(engine.long_mutes(words[:5] + [(4.1, 9.0)]), [(4.1, 9.0)])


@T.needs_ffmpeg
class Saved(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.video = support.SANDBOX / "Long Mutes Show S01E01.mp4"
        if not cls.video.exists():
            T.ffmpeg("-f", "lavfi", "-i", "testsrc=size=64x48:rate=10:duration=30", "-f", "lavfi",
                     "-i", "sine=frequency=440:duration=30", "-c:v", "libx264", "-c:a", "aac",
                     "-shortest", cls.video)

    def render(self, lines, words):
        work = Path(tempfile.mkdtemp(dir=support.SANDBOX))
        info = engine.probe(self.video)
        st = {"path": str(self.video), "info": info, "duration": info["duration"],
              "groups": [], "mutes": [], "scenes": [], "lines": [], "notes": [], "cues": []}
        (work / "analysis.json").write_text(json.dumps(st))
        res = engine.render(work, work / "Clean", [], lines=lines, words=words,
                            encoders=[engine.ENCODERS[-1]], log=lambda m: None)
        rep = (Path(res["folder"]) / "Reports" /
               "Long Mutes Show S01E01 - CleanView report.txt").read_text("utf8")
        return engine.probe(res["out"])["duration"], rep

    def test_a_long_stretch_is_cut(self):
        lines = [{"s": 10.0, "e": 12.5, "text": "first line", "types": ["sexref"]},
                 {"s": 13.0, "e": 15.0, "text": "second line", "types": ["sexref"]}]
        dur, rep = self.render(lines, [])
        self.assertAlmostEqual(dur, 30 - 5.0, delta=0.6)
        self.assertIn("cut instead, so there's no long silence", rep)
        self.assertIn("CUT 5 seconds  instead of a long silence", rep)

    def test_a_short_one_stays_muted(self):
        words = [{"s": 10.0, "e": 11.0, "word": "darn", "cat": "mild"}]
        lines = [{"s": 20.0, "e": 23.0, "text": "a line", "types": ["crude"]}]
        dur, rep = self.render(lines, words)
        self.assertAlmostEqual(dur, 30.0, delta=0.6)
        self.assertNotIn("instead of a long silence", rep)


if __name__ == "__main__":
    unittest.main()
