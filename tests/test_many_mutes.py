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


def plain(f):
    """At most 50 between() terms, plainly added up (1.18.55, from CleanListen 1.17.20)."""
    return f.count("between(") <= 50 and ")+(" not in f and "((" not in f


class Expressions(unittest.TestCase):
    def test_sums_never_run_over_100(self):
        # (the time the cuts take out, which can't be chained, is still bracketed past 50)
        expr = engine._sum(f"gte(T,{i}.0)*0.5" for i in range(3000))
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

    def test_a_filter_for_each_50_with_no_brackets(self):
        # Scarlet (Unabridged) didn't save in CleanListen with 500 to a filter bracketed in
        # 50s (2026-11-11); 50 plain terms to a filter reads in any ffmpeg
        rs = [(i, i + 0.5) for i in range(1201)]
        fs = engine._mute_filters(rs, 0.0)
        self.assertEqual(len(fs), 25)
        self.assertEqual(sum(f.count("between(") for f in fs), 1201)
        self.assertTrue(all(plain(f) for f in fs))
        cuts = engine._cut_filters(rs[:120], 0.0)
        self.assertEqual([f.split("=")[0] for f in cuts], ["aselect"] * 3 + ["asetpts"])
        self.assertTrue(all(plain(f) for f in cuts[:-1]))
        vcuts = engine._cut_filters(rs[:120], 0.0, video=True)
        self.assertEqual([f.split("=")[0] for f in vcuts], ["select"] * 3 + ["setpts"])

    def test_a_few_are_as_before(self):
        self.assertEqual(engine._ranges([(1, 2), (3, 4)], 0.0),
                         "between(t,1.000,2.000)+between(t,3.000,4.000)")
        self.assertEqual(engine._cut_filters([(1, 2)], 0.0),
                         ["aselect='not(between(t,1.000,2.000))'",
                          "asetpts='PTS-(gte(T,2.000)*1.000)/TB'"])

    def test_audiobook_ranges_too(self):
        rs = [(i, i + 0.5) for i in range(500)]
        self.assertEqual(cl._ranges(rs).count("between("), 500)
        f = cl._range_filters(rs, rs[:120])
        self.assertEqual(sum(x.startswith("volume=") for x in f), 10)
        self.assertEqual(sum(x.startswith("aselect=") for x in f), 3)
        self.assertEqual(f[-1], "asetpts=N/SR/TB")
        self.assertTrue(all(plain(x) for x in f))
        self.assertEqual(cl._range_filters([], []), [])

    def test_the_error_shows_what_went_wrong_not_just_times(self):
        err = ("[Parsed_volume_3 @ 0000] Error when evaluating the expression '" +
               "+".join(f"between(t,{i}.320,{i}.510)" for i in range(23000, 23050)) +
               "' for enable\n[AVFilterGraph @ 0000] Error initializing filters\n"
               "Error opening output file D:\\Movies\\Clean\\Scarlet (Clean).partial.mp4.")
        short = engine._short_error(err)
        self.assertIn("Error when evaluating the expression", short[-700:])
        self.assertIn("for enable", short[-700:])
        self.assertIn("Error opening output file D:", short)
        self.assertLess(len(short), 500)
        self.assertEqual(engine._short_error("x.mp4: Permission denied"),
                         "x.mp4: Permission denied")

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
        work = Path(res["out"]).parent.parent           # the filters it was given
        for name in ("afilter.txt", "vfilter.txt"):
            fs = (work / name).read_text().split(",")
            self.assertTrue(all(plain(f) for f in fs if "between(" in f), name)

    def test_1600_mutes_and_60_cuts(self):
        mutes = [{"s": i * 0.08, "e": i * 0.08 + 0.04, "word": "darn"} for i in range(1600)]
        cuts = [{"s": i * 2 + 0.5, "e": i * 2 + 0.7, "kind": ["Violence"], "why": "made up",
                 "cut": True} for i in range(60)]
        res = self.render(mutes, cuts)
        self.assertTrue(Path(res["out"]).exists())
        self.assertAlmostEqual(engine.probe(res["out"])["duration"], 130 - 12, delta=1.5)


if __name__ == "__main__":
    unittest.main()
