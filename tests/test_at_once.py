"""Several videos at once (Lauren, 2026-11-04: "have it where it can run multiple"): each
video is watched and listened to in its own worker (videoqueue.py), "Videos at once" at a
time. The workers run a stand-in engine (fake_engine.py)."""
import json
import os
import queue
import threading
import time
import types
import unittest
from pathlib import Path
from unittest import mock

import support

import videoqueue as VQ

TESTS = Path(__file__).resolve().parent
FAKE_ENV = {"CLEANVIEW_ENGINE": "fake_engine",
            "PYTHONPATH": str(TESTS) + os.pathsep + os.environ.get("PYTHONPATH", "")}


def run_workers(names, at_once=2, opts=None, stop_after_first=False, cancel_after=None):
    """The window's _run_workers on a stand-in for the window. Returns (jobs, messages)."""
    import importlib.machinery
    import importlib.util
    loader = importlib.machinery.SourceFileLoader("cleanview_ui_at_once",
                                                  str(support.ROOT / "CleanView.pyw"))
    ui = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
    loader.exec_module(ui)
    win = types.SimpleNamespace(
        jobs=[{"video": str(support.SANDBOX / n), "work": support.SANDBOX / "w" / n,
               "analysis": None, "error": None} for n in names],
        q=queue.Queue(), groups=["swearing"], scan_opts=dict(opts or {}, ai=False),
        cancel_flag=False, stop_after=False, at_once=at_once)
    for j in win.jobs:
        Path(j["work"]).mkdir(parents=True, exist_ok=True)
        for f in ("times.json", "analysis.json"):
            (Path(j["work"]) / f).unlink(missing_ok=True)
    seen = []
    real_put = win.q.put

    def put(msg):
        seen.append(msg)
        if stop_after_first and msg[:3] == ("job", 0, "now"):
            win.stop_after = True
        real_put(msg)
    win.q.put = put
    if cancel_after:
        threading.Timer(cancel_after, lambda: setattr(win, "cancel_flag", True)).start()
    with mock.patch.dict(os.environ, FAKE_ENV):
        ui.App._run_workers(win)
    return win.jobs, seen


def times(job):
    return json.loads((Path(job["work"]) / "times.json").read_text())


class TwoAtOnce(unittest.TestCase):
    def test_two_videos_are_worked_on_at_the_same_time(self):
        jobs, msgs = run_workers(["Ep 1.mp4", "Ep 2.mp4", "Ep 3.mp4"], at_once=2)
        self.assertTrue(all(j["analysis"] for j in jobs))
        self.assertEqual([j["analysis"]["video"] for j in jobs],
                         ["Ep 1.mp4", "Ep 2.mp4", "Ep 3.mp4"])
        a, b, c = (times(j) for j in jobs)
        self.assertLess(b["start"], a["end"])           # 1 and 2 together
        self.assertGreaterEqual(c["start"], min(a["end"], b["end"]) - 0.05)   # 3 waits
        self.assertIn(("which", "2 videos at once  ·  0 of 3 done"), msgs)
        self.assertTrue(any(m[0] == "jobmsg" and m[1] == 1 for m in msgs))
        done = [m[1] for m in msgs if m[0] == "job" and m[2] == "done"]
        self.assertEqual(sorted(done), [0, 1, 2])
        overall = [m[1] for m in msgs if m[0] == "progress"]
        self.assertTrue(all(0 <= f <= 1 for f in overall))

    def test_one_at_a_time(self):
        jobs, _ = run_workers(["One 1.mp4", "One 2.mp4"], at_once=1)
        a, b = (times(j) for j in jobs)
        self.assertGreaterEqual(b["start"], a["end"] - 0.05)

    def test_the_cores_are_shared(self):
        jobs, _ = run_workers(["Cores 1.mp4", "Cores 2.mp4"], at_once=2)
        self.assertEqual(times(jobs[0])["threads"], VQ.threads_each(2))
        self.assertEqual(VQ.threads_each(2, cpus=16), 8)
        self.assertEqual(VQ.threads_each(4, cpus=8), 2)
        self.assertEqual(VQ.threads_each(1, cpus=32), 8)

    def test_less_memory_one_at_a_time(self):
        self.assertEqual(VQ.default_at_once(8), 1)
        self.assertEqual(VQ.default_at_once(16), 2)
        self.assertEqual(VQ.default_at_once(0), 2)        # couldn't tell


class WhenOneGoesWrong(unittest.TestCase):
    def test_a_problem_is_said_plainly_and_the_rest_carry_on(self):
        jobs, msgs = run_workers(["Good 1.mp4", "bad 2.mp4", "unreadable 3.mp4"])
        self.assertTrue(jobs[0]["analysis"])
        self.assertEqual(jobs[1]["error"],
                         "bad 2.mp4: Couldn't read the sound in this video.")
        self.assertIn("ffmpeg said", jobs[1]["details"])
        self.assertEqual(jobs[2]["error"], "This file isn't a video CleanView can read.")
        failed = [m[1] for m in msgs if m[0] == "job" and m[2] == "failed"]
        self.assertEqual(sorted(failed), [1, 2])

    def test_a_crash_only_loses_that_video(self):
        jobs, _ = run_workers(["crash 1.mp4", "Fine 2.mp4"])
        self.assertIn("stopped working on this video unexpectedly", jobs[0]["error"])
        self.assertTrue(jobs[1]["analysis"])

    def test_stop_after_the_ones_being_done(self):
        jobs, msgs = run_workers(["Stop 1.mp4", "Stop 2.mp4", "Stop 3.mp4", "Stop 4.mp4"],
                                 at_once=2, stop_after_first=True)
        self.assertEqual([bool(j["analysis"]) for j in jobs], [True, True, False, False])
        self.assertEqual([j.get("skipped", False) for j in jobs], [False, False, True, True])

    def test_cancel_stops_the_workers(self):
        t0 = time.time()
        with self.assertRaises(KeyboardInterrupt):
            run_workers(["slow 1.mp4", "slow 2.mp4"], cancel_after=1.0)
        self.assertLess(time.time() - t0, 20)


class PlainWords(unittest.TestCase):
    def test_same_as_the_window(self):
        self.assertEqual(VQ.plain_error(RuntimeError("couldn't read the sound\nmore")),
                         "Couldn't read the sound.")
        self.assertEqual(VQ.plain_error(KeyError("x")), "Something unexpected went wrong.")


if __name__ == "__main__":
    unittest.main()
