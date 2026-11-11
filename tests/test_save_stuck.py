"""Lauren, 2026-11-10 (her MSI laptop): Castle S1E2 got stuck saving, several times, and
nothing said why. A save whose ffmpeg stops moving is now stopped after SAVE_STUCK_SECS and
tried the next way (another encoder, then the careful way); if every way gets stuck, the
error says where, so it can be sent in. Slow but moving saves, and the quiet stretch after
the last progress (moving the index to the front), are left alone; Cancel still works while
ffmpeg is silent; the progress line says how long it hasn't moved."""
import json
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import support
import test_timing as T

import cleanview as engine
import cvcore as cl
import videoqueue as VQ

real_popen = cl.popen

FAKE = r'''
import sys, time
out, mode = sys.argv[1], sys.argv[2]
def p(**kw):
    for k, v in kw.items():
        print(f"{k}={v}", flush=True)
if mode == "stuck":                     # gets to 2 s, then hangs silently
    for k in range(3):
        p(out_time_us=k * 1000000, total_size=1000 * (k + 1), progress="continue")
    time.sleep(60)
elif mode == "slow":                    # slow, but keeps moving
    for k in range(12):
        p(out_time_us=k * 500000, total_size=1000 * (k + 1), progress="continue")
        time.sleep(0.25)
    open(out, "wb").write(b"x")
    p(progress="end")
elif mode == "quiet_end":               # last progress, then a quiet stretch, then done
    p(out_time_us=8000000, total_size=5000, progress="end")
    time.sleep(1.5)
    open(out, "wb").write(b"x")
elif mode == "silent":                  # never says anything
    time.sleep(60)
'''


def fake_popen(mode, careful_works=False):
    script = support.SANDBOX / "fake_ffmpeg.py"
    script.write_text(FAKE, encoding="utf8")

    def popen(cmd, **kw):
        if careful_works and "-err_detect" in cmd:
            return real_popen(cmd, **kw)
        return subprocess.Popen([sys.executable, str(script), cmd[-1], mode], **kw)
    return popen


@T.needs_ffmpeg
class StuckSave(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.video = support.SANDBOX / "Castle Season 1 - Ep.  2 (Clean).mp4"
        if not cls.video.exists():
            T.ffmpeg("-f", "lavfi", "-i", "testsrc=size=64x48:rate=10:duration=8", "-f", "lavfi",
                     "-i", "sine=frequency=440:duration=8", "-c:v", "libx264", "-c:a", "aac",
                     "-shortest", cls.video)

    def render(self, popen, stuck=1.0, cancel=None, said=None, encoders=None):
        work = Path(tempfile.mkdtemp(dir=support.SANDBOX))
        info = engine.probe(self.video)
        st = {"path": str(self.video), "info": info, "duration": info["duration"],
              "groups": [], "scenes": [], "lines": [], "notes": [],
              "mutes": [{"s": 2.0, "e": 2.5, "word": "porn", "src": "audio"}],
              "cues": [{"s": 1.0, "e": 2.0, "text": "Hello there."}]}
        (work / "analysis.json").write_text(json.dumps(st))
        self.out_dir = work / "Clean"
        with mock.patch.object(cl, "popen", popen), \
                mock.patch.object(engine, "SAVE_STUCK_SECS", stuck), \
                mock.patch.object(engine, "SAVE_STILL_SAY", 0.4):
            return engine.render(work, self.out_dir, [], lines=[], words=None,
                                 encoders=encoders, cancel=cancel, log=lambda m: None,
                                 progress=(lambda f, m: said.append(m)) if said is not None
                                 else None)

    def leftovers(self):
        return [p.name for p in self.out_dir.glob("*.partial*")]

    def test_stuck_save_is_stopped_and_the_careful_way_saves_it(self):
        t = time.time()
        res = self.render(fake_popen("stuck", careful_works=True))
        self.assertLess(time.time() - t, 30)                  # not the fake's 60 s
        self.assertTrue(Path(res["out"]).exists())
        rep = Path(res["folder"]) / "Reports" / \
            "Castle Season 1 - Ep.  2 (Clean) - CleanView report.txt"
        self.assertIn("careful way", rep.read_text("utf8"))
        self.assertEqual(self.leftovers(), [])

    def test_every_way_stuck_says_where(self):
        with self.assertRaises(RuntimeError) as cm:
            self.render(fake_popen("stuck"))
        msg = str(cm.exception)
        self.assertIn(engine.STUCK_SAID + " at 0:02 of 0:0", msg)
        self.assertIn("careful copy:", msg)
        self.assertTrue(VQ.plain_error(cm.exception).startswith(
            "Saving the clean copy of Castle Season 1 - Ep.  2 (Clean).mp4 stopped moving "
            "at 0:02 of 0:0"))
        self.assertIsNone(engine.save_trouble(msg))
        self.assertEqual(self.leftovers(), [])

    def test_stuck_with_cuts_tries_the_next_encoder(self):
        with self.assertRaises(RuntimeError) as cm:
            work = Path(tempfile.mkdtemp(dir=support.SANDBOX))
            info = engine.probe(self.video)
            st = {"path": str(self.video), "info": info, "duration": info["duration"],
                  "groups": [], "scenes": [], "lines": [], "notes": [], "mutes": [],
                  "cues": []}
            (work / "analysis.json").write_text(json.dumps(st))
            with mock.patch.object(cl, "popen", fake_popen("stuck")), \
                    mock.patch.object(engine, "SAVE_STUCK_SECS", 1.0):
                engine.render(work, work / "Clean", [{"s": 3.0, "e": 4.0, "cut": True}],
                              lines=[], words=[], log=lambda m: None,
                              encoders=[("h264_nvenc", []), engine.ENCODERS[-1]])
        msg = str(cm.exception)
        self.assertIn("h264_nvenc: " + engine.STUCK_SAID, msg)
        self.assertIn("libx264: " + engine.STUCK_SAID, msg)

    def test_slow_but_moving_isnt_stopped(self):
        res = self.render(fake_popen("slow"), stuck=1.0)     # 3 s in all, a step every 0.25
        self.assertTrue(Path(res["out"]).exists())

    def test_quiet_after_the_last_progress_isnt_stuck(self):
        res = self.render(fake_popen("quiet_end"), stuck=0.5)
        self.assertTrue(Path(res["out"]).exists())

    def test_cancel_works_while_ffmpeg_says_nothing(self):
        start = time.time()
        with self.assertRaises(KeyboardInterrupt):
            self.render(fake_popen("silent"), stuck=30,
                        cancel=lambda: time.time() - start > 1)
        self.assertLess(time.time() - start, 15)
        self.assertEqual(self.leftovers(), [])

    def test_progress_says_it_hasnt_moved(self):
        said = []
        with self.assertRaises(RuntimeError):
            self.render(fake_popen("stuck"), stuck=1.5, said=said)
        self.assertTrue(any("no progress for" in m and "tries another way" in m for m in said),
                        said)

    def test_a_normal_save_still_works(self):
        res = self.render(real_popen)
        self.assertTrue(Path(res["out"]).exists())


class Clock(unittest.TestCase):
    def test_clock(self):
        self.assertEqual(engine._clock(5), "0:05")
        self.assertEqual(engine._clock(754.6), "12:34")
        self.assertEqual(engine._clock(3725), "1:02:05")


if __name__ == "__main__":
    unittest.main()
