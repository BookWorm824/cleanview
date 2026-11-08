"""Jason, 2026-11-07: The Shawshank Redemption wouldn't save, every way failing with
"Cannot allocate memory", and CleanView told him the PC ran out of memory (Task Manager
said 33%). It was ffmpeg: it won't read more than 100 times added up in a row, and the
movie had more mutes than that. Now they're bracketed in groups (and each 500 get their own
filter), so any number saves; and that ffmpeg error isn't called running out of memory."""
import json
import tempfile
import unittest
import array
from pathlib import Path

import support
import test_timing as T

import cleanview as engine
import cvcore as cl
import videoqueue as VQ


class Expressions(unittest.TestCase):
    def test_grouped_so_no_run_is_over_100(self):
        expr = engine._ranges([(i, i + 0.5) for i in range(3000)], 0.0)
        self.assertEqual(expr.count("between("), 3000)
        depth, runs = 0, [0]
        for ch in expr:                       # terms added up side by side at each level
            if ch == "(":
                depth += 1
                runs.append(0)
            elif ch == ")":
                depth -= 1
                runs.pop()
            elif ch == "+":
                runs[-1] += 1
                self.assertLess(runs[-1], 100)

    def test_mutes_get_a_filter_for_each_500(self):
        fs = engine._mute_filters([(i, i + 0.5) for i in range(1200)], 0.0)
        self.assertEqual(len(fs), 3)
        self.assertEqual(sum(f.count("between(") for f in fs), 1200)

    def test_a_few_are_as_before(self):
        self.assertEqual(engine._ranges([(1, 2), (3, 4)], 0.0),
                         "between(t,1.000,2.000)+between(t,3.000,4.000)")

    def test_audiobook_ranges_too(self):
        self.assertEqual(cl._ranges([(i, i + 0.5) for i in range(500)]).count("between("), 500)

    def test_ffmpegs_error_isnt_running_out_of_memory(self):
        err = RuntimeError(
            "Couldn't save the clean copy of Shawshank Redemption, The.m4v:\n"
            "...between(t,8189.770,8191.030)' for enable\n"
            "[AVFilterGraph @ 000002c21f700900] Error initializing filters\n"
            "Error opening output files: Cannot allocate memory")
        self.assertEqual(VQ.plain_error(err),
                         "Couldn't save the clean copy of Shawshank Redemption, The.m4v.")
        self.assertEqual(VQ.plain_error(RuntimeError("bad allocation")), VQ.OUT_OF_MEMORY)


@T.needs_ffmpeg
class SavesWithHundredsOfMutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.video = support.SANDBOX / "Shawshank Redemption, The.m4v"
        if not cls.video.exists():
            T.ffmpeg("-f", "lavfi", "-i", "testsrc=size=64x48:rate=10:duration=130", "-f",
                     "lavfi", "-i", "sine=frequency=440:duration=130:sample_rate=8000",
                     "-c:v", "libx264", "-c:a", "aac", "-shortest", "-f", "mp4", cls.video)

    def render(self, mutes, cuts):
        work = Path(tempfile.mkdtemp(dir=support.SANDBOX))
        info = engine.probe(self.video)
        st = {"path": str(self.video), "info": info, "duration": info["duration"],
              "groups": [], "mutes": [], "scenes": [], "lines": [], "notes": [], "cues": []}
        (work / "analysis.json").write_text(json.dumps(st))
        return engine.render(work, work / "Clean", cuts, lines=[], words=mutes,
                             encoders=[engine.ENCODERS[-1]], log=lambda m: None)

    def loudness(self, path, s, e):
        raw = Path(tempfile.mkdtemp(dir=support.SANDBOX)) / "a.raw"
        T.ffmpeg("-i", path, "-vn", "-ac", "1", "-ar", "8000", "-f", "s16le", raw)
        a = array.array("h", raw.read_bytes())
        x = a[int(s * 8000):int(e * 8000)]
        return (sum(v * v for v in x) / max(1, len(x))) ** 0.5

    def test_150_mutes_copied(self):
        # every other half second for 150 s... (no cuts: the sound is made again, the video copied)
        mutes = [{"s": i * 0.8, "e": i * 0.8 + 0.4, "word": "darn"} for i in range(150)]
        res = self.render(mutes, [])
        self.assertTrue(Path(res["out"]).exists())
        self.assertLess(self.loudness(res["out"], 100 * 0.8 + 0.1, 100 * 0.8 + 0.3), 50)
        self.assertGreater(self.loudness(res["out"], 100 * 0.8 + 0.5, 100 * 0.8 + 0.7), 500)

    def test_150_mutes_and_120_cuts(self):
        mutes = [{"s": i * 0.8, "e": i * 0.8 + 0.4, "word": "darn"} for i in range(150)]
        cuts = [{"s": i + 0.6, "e": i + 0.7, "kind": ["Violence"], "why": "made up", "cut": True}
                for i in range(120)]
        res = self.render(mutes, cuts)
        self.assertTrue(Path(res["out"]).exists())
        info = engine.probe(res["out"])
        self.assertAlmostEqual(info["duration"], 130 - 12, delta=1.5)


if __name__ == "__main__":
    unittest.main()
