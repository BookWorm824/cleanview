"""Pause and Resume while videos are worked on or saved (1.18.66; the owner: "should we have a
pause buton next to the cancel button when a check is happening", then "yes build it"). The
helper processes freeze where they are and carry on from there; while paused the PC may sleep,
the stuck-save watch and the time left don't count, nothing new starts, and Cancel or closing
still stop everything."""
import gc
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

import support
import test_save_stuck as SS
import test_timing as T

import cleanview as engine
import cvcore as cl

WINDOWS = os.name == "nt"


class FakeProc:
    def __init__(self, pid, alive=True):
        self.pid, self.alive = pid, alive

    def poll(self):
        return None if self.alive else 0


class WhatPausingDoes(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.p = engine.Pausing(freeze=lambda pid, on: self.calls.append((pid, on)) or True,
                                family=lambda pid: [pid, pid * 10])

    def test_freezes_and_unfreezes_each_family(self):
        self.p.track(FakeProc(1))
        self.p.track(FakeProc(2))
        self.p.pause()
        self.assertTrue(self.p.on)
        self.assertEqual(self.calls, [(1, True), (10, True), (2, True), (20, True)])
        self.calls.clear()
        self.p.resume()
        self.assertFalse(self.p.on)
        self.assertEqual(self.calls, [(20, False), (2, False), (10, False), (1, False)])

    def test_started_while_paused_freezes_at_once(self):
        self.p.pause()
        self.p.track(FakeProc(3))
        self.assertEqual(self.calls, [(3, True), (30, True)])

    def test_finished_and_untracked_left_alone(self):
        done, gone = FakeProc(4, alive=False), FakeProc(5)
        self.p.track(done)
        self.p.track(gone)
        self.p.untrack(gone)
        self.p.pause()
        self.assertEqual(self.calls, [])

    def test_twice_is_once(self):
        self.p.track(FakeProc(1))
        self.p.pause()
        self.p.pause()
        self.p.resume()
        self.p.resume()
        self.assertEqual(len(self.calls), 4)

    def test_paused_time_counted(self):
        self.p.pause()
        time.sleep(0.3)
        self.p.resume()
        self.assertGreater(self.p.paused_for(), 0.25)
        self.assertLess(self.p.paused_for(), 2)

    def test_listeners_told(self):
        heard = []
        self.p.listen(heard.append)
        self.p.pause()
        self.p.resume()
        self.p.unlisten(heard.append)
        self.p.pause()
        self.assertEqual(heard, [True, False])


@unittest.skipUnless(WINDOWS, "Windows suspends processes")
class RealProcess(unittest.TestCase):
    def test_a_counter_stops_and_goes_on(self):
        f = Path(tempfile.mkdtemp(dir=support.SANDBOX)) / "count.txt"
        code = ("import sys, time\nn = 0\nwhile n < 400:\n    n += 1\n"
                "    open(sys.argv[1], 'w').write(str(n))\n    time.sleep(0.05)\n")
        proc = subprocess.Popen([sys.executable, "-c", code, str(f)])
        p = engine.Pausing()
        try:
            p.track(proc)
            while not f.exists():
                time.sleep(0.05)
            time.sleep(0.4)
            p.pause()
            time.sleep(0.3)
            a = int(f.read_text() or 0)
            time.sleep(0.8)
            self.assertEqual(int(f.read_text() or 0), a, "it stood still while paused")
            p.resume()
            time.sleep(0.8)
            self.assertGreater(int(f.read_text() or 0), a + 3, "it went on after Resume")
        finally:
            p.resume()
            proc.kill()
            proc.wait()


class KeepAwakeLetsGo(unittest.TestCase):
    def setUp(self):
        gc.collect()        # as in SavingPaused: keep_awake has a thread of its own

    def test_paused_and_resumed(self):
        calls = []
        try:
            with engine.keep_awake(calls.append):
                engine.PAUSE.pause()
                engine.PAUSE.resume()
                time.sleep(0.3)
        finally:
            engine.PAUSE.resume()
        on, off = 0x80000001, 0x80000000
        self.assertEqual(calls, [on, off, on, off])

    def test_already_paused(self):
        calls = []
        engine.PAUSE.pause()
        try:
            with engine.keep_awake(calls.append):
                time.sleep(0.2)
        finally:
            engine.PAUSE.resume()
        self.assertEqual(calls, [0x80000001, 0x80000000, 0x80000000])


@T.needs_ffmpeg
@unittest.skipUnless(WINDOWS, "Windows suspends processes")
class SavingPaused(unittest.TestCase):
    """A save paused for longer than the stuck-save limit isn't taken as stuck."""

    @classmethod
    def setUpClass(cls):
        SS.StuckSave.setUpClass.__func__(cls)

    def setUp(self):
        # window bits left by earlier tests are tidied here, on the main thread: Tk can't
        # have them tidied by this test's other thread ("Tcl_AsyncDelete ... wrong thread")
        gc.collect()

    def test_paused_longer_than_the_limit(self):
        def pause_a_while():
            time.sleep(1.0)
            engine.PAUSE.pause()
            time.sleep(2.5)
            engine.PAUSE.resume()
        th = threading.Thread(target=pause_a_while)
        t = time.time()
        th.start()
        try:
            res = SS.StuckSave.render(self, SS.fake_popen("slow"), stuck=1.0)
        finally:
            th.join()
            engine.PAUSE.resume()
        self.assertGreater(time.time() - t, 4.5)          # 3 s of saving + 2.5 s paused
        self.assertTrue(Path(res["out"]).exists())
        rep = next((Path(res["folder"]) / "Reports").glob("*.txt")).read_text("utf8")
        self.assertNotIn("careful way", rep)               # the first way finished it


class TheWindow(unittest.TestCase):
    def test_button_and_resume_before_stopping(self):
        from test_ui import ui
        import inspect
        src = inspect.getsource(ui.App.show_working)
        self.assertIn('text="Pause"', src)
        self.assertIn("toggle_pause", src)
        for name in ("cancel", "_on_close", "_run_workers"):
            self.assertIn("engine.PAUSE.resume()", inspect.getsource(getattr(ui.App, name)),
                          name)
        run = inspect.getsource(ui.App._run_workers)
        self.assertIn("engine.PAUSE.track(", run)
        self.assertIn("not engine.PAUSE.on", run)        # nothing new starts while paused

    def test_pressing_it(self):
        from test_ui import ui
        import tkinter as tk
        try:
            root = tk.Tk()
        except tk.TclError as ex:
            raise unittest.SkipTest(f"no screen ({ex})")
        try:
            app = mock.Mock()
            app._work_t0 = time.time() - 100
            app.PAUSED_SAID = ui.App.PAUSED_SAID
            app.pause_btn = tk.Button(root, text="Pause")
            app.status = tk.Label(root, text="Listening…")
            app._doing = {"status": "Listening… 40%"}
            ui.App.toggle_pause(app)
            self.assertTrue(engine.PAUSE.on)
            self.assertEqual(app.pause_btn.cget("text"), "Resume")
            self.assertIn("Paused", app.status.cget("text"))
            t0 = app._work_t0
            time.sleep(0.3)
            ui.App.toggle_pause(app)
            self.assertFalse(engine.PAUSE.on)
            self.assertEqual(app.pause_btn.cget("text"), "Pause")
            self.assertEqual(app.status.cget("text"), "Listening… 40%")
            self.assertGreater(app._work_t0 - t0, 0.25)  # time left leaves the pause out
        finally:
            engine.PAUSE.resume()
            root.destroy()


if __name__ == "__main__":
    unittest.main()
