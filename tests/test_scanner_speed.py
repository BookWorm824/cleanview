"""The picture scanner, faster with the same scores (the owner, 2026-11-09: "is it optimized
fully?", then "1, 2 and 3"): frames too dark to judge are skipped (their scores were never
used), and the picture AI runs beside the nudity check. Faster frame preparation (3) was
tried and dropped: the same math was no faster, and faster math changes the numbers."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

import support
import test_timing as T
import cleanview as engine
import cleanview_ai as ai


class Rules(unittest.TestCase):

    def test_too_dark_is_what_the_scenes_leave_out(self):
        self.assertEqual((engine.DARK_MEAN, engine.FLAT_STD), (40, 18))    # clip_candidates too
        self.assertTrue(engine.too_dark([12.0, 30.0]))
        self.assertTrue(engine.too_dark([90.0, 10.0]))
        self.assertFalse(engine.too_dark([40.0, 18.0]))

    def test_threads_shared_not_crowded(self):
        self.assertEqual(engine.scan_threads(16, True), (4, 8))
        self.assertEqual(engine.scan_threads(8, True), (2, 4))
        self.assertEqual(engine.scan_threads(4, True), (1, 2))
        self.assertEqual(engine.scan_threads(None, True), (1, 1))
        self.assertEqual(engine.scan_threads(16, False), (6, 0))


class FakeClip:
    """Scores from the frame itself, so the right frame must reach the right slot."""
    seen = []

    def __init__(self, ort, threads=4, spin=True):
        self.spin = spin

    def scores(self, rgb):
        FakeClip.seen.append(float(rgb.mean()))
        return {"kiss": round(float(rgb.mean()) / 255, 3), "fight": 0.0}


@T.needs_ffmpeg
@unittest.skipUnless(engine.nudity_model(), "the nudity checker isn't installed")
class RealScan(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.video = support.SANDBOX / "Light and dark.mp4"
        if not cls.video.exists():
            T.ffmpeg("-f", "lavfi", "-i", "testsrc=size=320x180:rate=10:duration=4",
                     "-f", "lavfi", "-i", "color=c=black:size=320x180:rate=10:duration=3",
                     "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=10:duration=4",
                     "-f", "lavfi", "-i", "sine=frequency=300:duration=11",
                     "-filter_complex", "[0:v][1:v][2:v]concat=n=3:v=1:a=0[v]",
                     "-map", "[v]", "-map", "3:a", "-c:v", "libx264", "-c:a", "aac", cls.video)

    def scan(self, use_clip=True, clip=FakeClip):
        out = Path(tempfile.mkdtemp(dir=support.SANDBOX)) / "pictures.json"
        FakeClip.seen = []
        said = io.StringIO()
        with mock.patch.object(ai, "Clip", clip), contextlib.redirect_stdout(said):
            engine._visual_scan_here(str(self.video), out, use_clip)
        return json.loads(out.read_text()), said.getvalue()

    def test_dark_frames_skipped_the_rest_scored(self):
        vis, said = self.scan()
        n = len(vis["lum"])
        self.assertEqual(len(vis["scores"]), n)
        dark = [k for k, l in enumerate(vis["lum"]) if engine.too_dark(l)]
        self.assertTrue(4 <= len(dark) <= 8, dark)               # the 3 s of black
        self.assertTrue(all(vis["scores"][k] == [0.0] * len(engine.KEEP) for k in dark))
        t_clip = [int(round(t * vis["fps"])) for t in vis["clip"]["t"]]
        self.assertEqual(t_clip, [k for k in range(0, n, 2) if k not in dark])
        self.assertIn("P ", said)

    def test_each_picture_ai_score_is_its_own_frames(self):
        vis, _ = self.scan()
        kisses = [s["kiss"] for s in vis["clip"]["scores"]]
        self.assertEqual(kisses, [round(m / 255, 3) for m in FakeClip.seen])
        self.assertGreater(len(set(kisses)), 1)          # different frames, different scores

    def test_same_nudity_scores_as_one_frame_at_a_time(self):
        import onnxruntime as ort
        vis, _ = self.scan(use_clip=False)
        sess = ort.InferenceSession(str(engine.nudity_model()), providers=["CPUExecutionProvider"])
        name = sess.get_inputs()[0].name
        info = engine.probe(self.video)
        H = 256
        W = max(64, int(round(H * (info["video"].get("dar") or 16 / 9) / 2)) * 2)
        import subprocess
        import cvcore as cl
        raw = subprocess.run([cl._tool("ffmpeg"), "-v", "error", "-i", str(self.video), "-map",
                              "0:v:0", "-vf", f"fps=2,scale={W}:{H},setsar=1,format=rgb24",
                              "-f", "rawvideo", "-"], capture_output=True).stdout
        cols = [engine.NUDE_CLASSES.index(k) for k in engine.KEEP]
        size = W * H * 3
        for k in range(len(raw) // size):
            if engine.too_dark(vis["lum"][k]):
                continue
            f = np.frombuffer(raw[k * size:(k + 1) * size], dtype=np.uint8).reshape(H, W, 3)
            y = sess.run(None, {name: ai.nudenet_input(f)[None].astype(np.float32)})[0]
            best = y[:, 4:, :].max(axis=2)[0]
            for a, b in zip(vis["scores"][k], [round(float(best[c]), 3) for c in cols]):
                self.assertAlmostEqual(a, b, delta=0.0015)

    def test_a_picture_ai_problem_stops_the_scan(self):
        class Broken(FakeClip):
            def scores(self, rgb):
                raise RuntimeError("picture AI broke")
        with self.assertRaises(RuntimeError):
            self.scan(clip=Broken)

    def test_without_the_picture_ai(self):
        vis, _ = self.scan(use_clip=False)
        self.assertIsNone(vis["clip"])
        self.assertEqual(FakeClip.seen, [])


if __name__ == "__main__":
    unittest.main()
