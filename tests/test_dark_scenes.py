"""Dark scenes are brightened and checked instead of skipped (the owner, 2026-11-09: "the
picture scanner skips dark frames, is that going to allow intimate scenes through?", then
"Yes, build and test"). In 148 saved reviews, 42% of the intimate scenes cut were mostly too
dark to judge and only Claude saw them; brightened, the PC's own checks saw 9 of 11 in 10
episodes, with no false alarms. Frames still featureless when brightened stay skipped."""
import base64
import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

import support
import test_timing as T
import cleanview as engine
import cleanview_ai as ai
import cvcore as cl


class Brighten(unittest.TestCase):

    def test_a_dim_picture_gets_its_full_range(self):
        dim = np.tile(np.linspace(4, 70, 64, dtype=np.uint8), (32, 1))[:, :, None].repeat(3, 2)
        self.assertTrue(engine.too_dark([dim.mean(), dim.mean(axis=2).std()]))
        out = ai.brighten(dim)
        self.assertGreater(out.max(), 200)
        self.assertLess(out.min(), 20)
        self.assertGreaterEqual(out.mean(axis=2).std(), engine.FLAT_STD)

    def test_noise_is_never_multiplied_more_than_four_times(self):
        rng = np.random.default_rng(1)
        murk = (20 + rng.integers(-2, 3, (32, 64, 3))).astype(np.uint8)
        lo, hi = ai.lift_levels(murk)
        self.assertGreaterEqual(hi - lo, 255 / ai.LIFT_MOST)
        self.assertLess(ai.brighten(murk).mean(axis=2).std(), engine.FLAT_STD)  # still murk

    def test_black_stays_black(self):
        black = np.zeros((32, 64, 3), np.uint8)
        self.assertEqual(int(ai.brighten(black).max()), 0)


class Scenes(unittest.TestCase):

    def vis(self, lifted):
        dark = [10.0, 30.0]
        row = [0.9] + [0.0] * (len(engine.KEEP) - 1)          # breasts exposed, strongly
        return {"fps": 2.0, "classes": engine.KEEP, "scores": [row] * 12, "lum": [dark] * 12,
                "lifted": lifted}

    def test_brightened_nudity_counts(self):
        nude, _ = engine.nudity_scenes(self.vis(list(range(12))))
        self.assertEqual(len(nude), 1)
        self.assertTrue(nude[0]["lifted"])
        self.assertIn("in a dark scene, brightened", nude[0]["why"])
        self.assertTrue(engine.nudity_checks(nude)[0]["lifted"])

    def test_brightened_nudity_unticked_until_the_ai_helper_confirms(self):
        nude, _ = engine.nudity_scenes(self.vis(list(range(12))))
        self.assertFalse(nude[0]["sure"])               # word lists only: offered, not cut
        self.assertIn("only cut if you tick it", nude[0]["why"])
        o = {"nudity": True, "implied": True}
        checks = engine.nudity_checks(nude)
        checks[0]["verdict"] = {"level": "shown", "what": "a bare chest in bed"}
        (kept,) = engine.check_nudity(nude, o, None, [], checks=checks)
        self.assertTrue(kept["sure"])                   # confirmed: ticked
        self.assertNotIn("only cut if you tick it", kept["why"])
        self.assertIn("in a dark scene, brightened", kept["why"])
        checks[0]["verdict"] = {"level": "none"}
        self.assertEqual(engine.check_nudity(nude, o, None, [], checks=checks), [])
        checks[0]["verdict"] = {"error": "timed out"}
        (kept,) = engine.check_nudity(nude, o, None, [], checks=checks)
        self.assertFalse(kept["sure"])                  # the check failed: still unticked

    def test_bright_nudity_still_ticked_as_before(self):
        v = self.vis([])
        v["lum"] = [[120.0, 50.0]] * 12
        (sc,) = engine.nudity_scenes(v)[0]
        self.assertTrue(sc["sure"])
        self.assertFalse(sc["lifted"])
        self.assertNotIn("brightened", sc["why"])

    def test_dark_and_not_brightened_still_skipped(self):
        self.assertEqual(engine.nudity_scenes(self.vis([]))[0], [])

    def test_brightened_picture_ai_frames_count(self):
        clip = {"t": [k / 2 for k in range(0, 12, 2)],
                "scores": [dict({"kiss": 0.95, "fight": 0.0}, **{w: 0.3 for w in ai.WHO})] * 6}
        lum = [[10.0, 30.0]] * 12
        self.assertEqual(ai.clip_candidates(clip, ["kiss"], lum=lum, fps=2.0), [])
        (c,) = ai.clip_candidates(clip, ["kiss"], lum=lum, fps=2.0, lifted=range(12))
        self.assertTrue(c["lifted"])

    def test_old_scans_are_done_again(self):
        self.assertEqual(engine.PICTURE_VERSION, 4)
        self.assertIn('vis.get("version", 1) < PICTURE_VERSION', inspect_analyze())


def inspect_analyze():
    import inspect
    return inspect.getsource(engine.analyze)


class FakeClip:
    def __init__(self, ort, threads=4, spin=True):
        pass

    def scores(self, rgb):
        return {"kiss": round(float(rgb.mean()) / 255, 3), "fight": 0.0}


@T.needs_ffmpeg
@unittest.skipUnless(engine.nudity_model(), "the nudity checker isn't installed")
class RealScan(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.video = support.SANDBOX / "Bright dim black.mp4"
        if not cls.video.exists():
            T.ffmpeg("-f", "lavfi", "-i", "testsrc=size=320x180:rate=10:duration=3",
                     "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=10:duration=3",
                     "-f", "lavfi", "-i", "color=c=black:size=320x180:rate=10:duration=3",
                     "-f", "lavfi", "-i", "sine=frequency=300:duration=9",
                     "-filter_complex", "[1:v]colorlevels=romax=0.12:gomax=0.12:bomax=0.12[dim];"
                     "[0:v][dim][2:v]concat=n=3:v=1:a=0[v]",
                     "-map", "[v]", "-map", "3:a", "-c:v", "libx264", "-c:a", "aac", cls.video)

    def scan(self):
        out = Path(tempfile.mkdtemp(dir=support.SANDBOX)) / "pictures.json"
        with mock.patch.object(ai, "Clip", FakeClip), contextlib.redirect_stdout(io.StringIO()):
            engine._visual_scan_here(str(self.video), out, True)
        return json.loads(out.read_text())

    def test_dim_frames_brightened_black_skipped(self):
        vis = self.scan()
        dark = [k for k, l in enumerate(vis["lum"]) if engine.too_dark(l)]
        lifted = set(vis["lifted"])
        self.assertTrue(lifted)
        self.assertTrue(lifted <= set(dark))
        dim = [k for k in range(6, 12) if k in dark]            # the dimmed testsrc2 (3-6 s)
        self.assertTrue(dim and all(k in lifted for k in dim), (dim, sorted(lifted)))
        black = [k for k in range(13, 18) if k in dark]         # the black (6-9 s)
        self.assertTrue(black and not any(k in lifted for k in black))
        self.assertTrue(all(vis["scores"][k] == [0.0] * len(engine.KEEP) for k in black))
        clip_frames = {int(round(t * vis["fps"])) for t in vis["clip"]["t"]}
        self.assertTrue(clip_frames & lifted)
        self.assertFalse(clip_frames & set(black))
        self.assertEqual(vis["version"], 4)

    def test_the_ai_helper_gets_brightened_stills(self):
        ff = cl._tool("ffmpeg")

        def mean_of(b64):
            raw = subprocess.run([ff, "-v", "error", "-i", "-", "-f", "rawvideo", "-pix_fmt",
                                  "gray", "-"], input=base64.b64decode(b64),
                                 capture_output=True).stdout
            return np.frombuffer(raw, dtype=np.uint8).mean()
        (plain,) = ai.grab_frames(ff, self.video, [4.5], cl.run)
        (lifted,) = ai.grab_frames(ff, self.video, [4.5], cl.run, lift=True)
        self.assertGreater(mean_of(lifted), 2 * mean_of(plain))


if __name__ == "__main__":
    unittest.main()
