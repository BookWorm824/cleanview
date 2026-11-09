"""Cancel goes back to the start page at once (the owner, 2026-11-09, in CleanRead: "when
clicking cancel on a book that just stated, it seems like it taking a while to actually cancel
and go back to home screen, why is that?", then "send this fix to clean view and read aloud
alos"). The work stops by itself at its next check; what it still sends is dropped by its
number; new work waits for the old to finish stopping; a cancelled save leaves no half copy."""
import json
import tempfile
import threading
import time
import types
import unittest
from pathlib import Path
from unittest import mock

import support
import test_timing as T
import test_ui

import cleanview as engine

ui = test_ui.ui


def stand_in(**kw):
    win = types.SimpleNamespace(q=__import__("queue").Queue(), run=0, cancel_flag=False,
                                jobs=[], shown=[], **kw)
    win.show_setup = lambda: win.shown.append("setup")
    for name in ("_start_work", "_render_now", "_render_thread", "_handle"):
        setattr(win, name, getattr(ui.App, name).__get__(win))
    return win


def drain(win):
    out = []
    while not win.q.empty():
        out.append(win.q.get())
    return out


class CancelAtOnce(unittest.TestCase):

    def test_home_before_the_work_stops(self):
        win = stand_in()
        go, stopped = threading.Event(), threading.Event()

        def work(run):
            go.wait(5)                      # busy in a step that can't be interrupted
            win.q.put(("for_run", run, ("analyzed",)))
            stopped.set()
        win._start_work(work)
        ui.App.cancel(win)
        self.assertEqual(win.shown, ["setup"])          # straight away
        self.assertFalse(stopped.is_set())
        go.set()
        stopped.wait(5)
        handled = []
        win.after_analyze = lambda: handled.append("review")
        for m in drain(win):
            win._handle(m)
        self.assertEqual(handled, [])                   # its late "done" is dropped

    def test_current_work_still_heard(self):
        win = stand_in()
        seen = []
        win._start_work(lambda run: win.q.put(("for_run", run, ("call", lambda: seen.append(1)))))
        win.work_thread.join(5)
        for m in drain(win):
            win._handle(m)
        self.assertEqual(seen, [1])

    def test_new_work_waits_for_the_old_to_stop(self):
        win = stand_in()
        order, release = [], threading.Event()

        def old(run):
            while win.run == run:
                time.sleep(0.01)
            release.wait(5)                 # still tidying up after Cancel
            order.append("old stopped")

        def new(run):
            order.append("new started")
        win._start_work(old)
        ui.App.cancel(win)
        win._start_work(new)
        time.sleep(0.2)
        self.assertEqual(order, [])
        release.set()
        win.work_thread.join(5)
        self.assertEqual(order, ["old stopped", "new started"])
        msgs = [m[2] for m in drain(win) if m[1] == win.run]
        self.assertIn(("progress", 0.0, "Finishing stopping the last one…", ""), msgs)

    def test_cancelled_work_never_starts_late(self):
        win = stand_in()
        started, release = [], threading.Event()
        win._start_work(lambda run: release.wait(5))
        win._start_work(lambda run: started.append("second"))
        win._start_work(lambda run: started.append("third"))
        release.set()
        win.work_thread.join(5)
        time.sleep(0.1)
        self.assertEqual(started, ["third"])

    def test_a_cancelled_save_is_told_to_stop(self):
        win = stand_in(outdir="out", _save_failures=[])
        win.jobs = [{"video": "a.mp4", "work": "w", "analysis": {"x": 1}, "cuts": []}]
        asked = []

        def render(*a, cancel=None, **k):
            ui.App.cancel(win)
            asked.append(cancel())
            raise KeyboardInterrupt
        with mock.patch.object(ui.engine, "render", render):
            ui.App._render_now(win, win.run)
        self.assertEqual(asked, [True])
        self.assertEqual(win.shown, ["setup"])
        msgs = drain(win)
        self.assertEqual(msgs[-1][2], ("cancelled",))
        for m in msgs:
            win._handle(m)                  # all of them dropped: nothing else shown
        self.assertEqual(win.shown, ["setup"])

    def test_closing_the_window_still_stops_it(self):
        win = stand_in()
        stop = []
        win._start_work(lambda run: None)
        win.work_thread.join(5)
        win.cancel_flag = True
        with mock.patch.object(ui.engine, "render",
                               lambda *a, cancel=None, **k: stop.append(cancel())):
            win.jobs = [{"video": "a.mp4", "work": "w", "analysis": {"x": 1}, "cuts": []}]
            win.outdir, win._save_failures = "out", []
            ui.App._render_now(win, win.run)
        self.assertEqual(stop, [True])


@T.needs_ffmpeg
class NoHalfCopy(unittest.TestCase):

    def test_cancelled_partway_leaves_nothing(self):
        video = support.SANDBOX / "Cancel me.mp4"
        if not video.exists():
            T.ffmpeg("-f", "lavfi", "-i", "testsrc=size=320x240:rate=25:duration=30", "-f",
                     "lavfi", "-i", "sine=frequency=440:duration=30", "-c:v", "libx264",
                     "-c:a", "aac", "-shortest", video)
        work = Path(tempfile.mkdtemp(dir=support.SANDBOX))
        info = engine.probe(video)
        (work / "analysis.json").write_text(json.dumps(
            {"path": str(video), "info": info, "duration": info["duration"], "groups": [],
             "mutes": [], "scenes": [], "lines": [], "notes": [], "cues": []}))
        out = work / "Clean"
        checks = []

        def cancel():                       # pressed once some of it is written
            checks.append(1)
            return len(checks) > 4
        with self.assertRaises(KeyboardInterrupt):
            engine.render(work, out, [{"s": 3.0, "e": 4.0, "kind": ["Violence"], "cut": True}],
                          lines=[], words=[], encoders=[engine.ENCODERS[-1]], log=lambda m: None,
                          cancel=cancel)
        left = [p.name for p in out.glob("*")] if out.exists() else []
        self.assertFalse([n for n in left if n.lower().endswith((".mp4", ".mkv", ".tmp"))], left)


if __name__ == "__main__":
    unittest.main()
