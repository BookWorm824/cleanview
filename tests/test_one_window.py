"""One CleanView at a time, and a window straight away (1.18.64; Lauren, 2026-11-12: "it can
take several second and gives no indication it is opening. so i click again and get multiple
windows open. I only want there to be a single instance", "The program can take time to open
if it needs, but give an indicator box it is opening")."""
import os
import subprocess
import sys
import textwrap
import time
import unittest
import uuid
from unittest import mock

import support  # noqa: F401  (sets up the sandbox first)
from test_own_exe import load_launcher

WINDOWS = os.name == "nt"


def holder(name, secs):
    """Another process holding the lock `name` for `secs` seconds."""
    code = textwrap.dedent(f"""
        import ctypes, time
        k = ctypes.WinDLL("kernel32")
        k.CreateMutexW.restype = ctypes.c_void_p
        h = k.CreateMutexW(None, True, {name!r})
        print("held", flush=True)
        time.sleep({secs})
    """)
    p = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True)
    p.stdout.readline()
    return p


@unittest.skipUnless(WINDOWS, "Windows locks")
class Lock(unittest.TestCase):
    def setUp(self):
        self.lm = load_launcher()
        self.name = f"Local\\CleanView-test-{uuid.uuid4().hex}"

    def test_one_holder(self):
        self.assertFalse(self.lm.exists(self.name))
        p = holder(self.name, 30)
        try:
            self.assertTrue(self.lm.exists(self.name))
            self.assertFalse(self.lm.hold(self.name))
        finally:
            p.kill()
            p.wait()

    def test_waits_for_the_old_one(self):
        p = holder(self.name, 1.5)
        t = time.time()
        self.assertTrue(self.lm.hold(self.name, wait=20))
        self.assertGreater(time.time() - t, 0.5)
        p.wait()

    def test_free(self):
        self.assertTrue(self.lm.hold(self.name))
        self.assertTrue(self.lm.hold(self.name))      # the same process again


@unittest.skipUnless(WINDOWS, "Windows windows")
class FindsTheWindow(unittest.TestCase):
    def test_a_window_one_process_down(self):
        lm = load_launcher()
        # a venv's python.exe starts the real Python, which owns the window
        code = (support.HIDE + "import tkinter as tk, time; r = tk.Tk(); "
                "r.title('CleanView test window'); r.after(8000, r.destroy); r.mainloop()")
        outer = subprocess.Popen([sys.executable, "-c",
                                  f"import subprocess, sys; subprocess.run([sys.executable, "
                                  f"'-c', {code!r}])"])
        try:
            t = time.time()
            while not lm.windows_of(outer.pid) and time.time() - t < 15:
                time.sleep(0.1)
            self.assertTrue(lm.windows_of(outer.pid))
            self.assertTrue(lm.windows_of(title="CleanView test window"))
        finally:
            for p in lm.family(outer.pid):
                subprocess.run(["taskkill", "/PID", str(p), "/F"], capture_output=True)


class WhatAClickDoes(unittest.TestCase):
    def setUp(self):
        self.lm = load_launcher()
        self.calls = []
        for name in ("bring_forward", "start_app", "splash"):
            p = mock.patch.object(self.lm, name,
                                  lambda *a, n=name: self.calls.append(n) or
                                  (mock.Mock() if n == "start_app" else None))
            p.start()
            self.addCleanup(p.stop)
        env = mock.patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("CLEANVIEW_UPDATED", None)
        os.environ.pop("CLEANVIEW_RESTART", None)

    def test_already_open(self):
        with mock.patch.object(self.lm, "exists", lambda n: n == self.lm.ONE_NAME):
            self.assertTrue(self.lm.clicked())
        self.assertEqual(self.calls, ["bring_forward"])

    def test_already_opening(self):
        with mock.patch.object(self.lm, "exists", lambda n: False), \
                mock.patch.object(self.lm, "hold", lambda n, wait=0: False):
            self.assertTrue(self.lm.clicked())
        self.assertEqual(self.calls, ["bring_forward"])

    def test_not_open(self):
        with mock.patch.object(self.lm, "exists", lambda n: False), \
                mock.patch.object(self.lm, "hold", lambda n, wait=0: True):
            self.assertTrue(self.lm.clicked())
        self.assertEqual(self.calls, ["start_app", "splash"])

    def test_update_now_starts_again(self):
        os.environ["CLEANVIEW_UPDATED"] = "CleanView was updated to version 9.9.9."
        with mock.patch.object(self.lm, "exists", lambda n: True):
            self.assertTrue(self.lm.clicked())
        self.assertEqual(self.calls, ["start_app", "splash"])

    def test_couldnt_start_apart(self):
        with mock.patch.object(self.lm, "exists", lambda n: False), \
                mock.patch.object(self.lm, "hold", lambda n, wait=0: True), \
                mock.patch.object(self.lm, "start_app", lambda: None):
            self.assertFalse(self.lm.clicked())


class TheAppPart(unittest.TestCase):
    def setUp(self):
        self.lm = load_launcher()
        env = mock.patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("CLEANVIEW_UPDATED", None)

    def test_another_won(self):
        waits = []
        with mock.patch.object(self.lm, "hold", lambda n, wait=0: waits.append(wait)), \
                mock.patch.object(self.lm, "bring_forward") as fwd, \
                mock.patch.object(self.lm, "update", side_effect=AssertionError("no update")), \
                mock.patch.object(self.lm.runpy, "run_path") as run:
            self.lm.run_app()
        fwd.assert_called_once()
        run.assert_not_called()
        self.assertEqual(waits, [3])

    def test_update_now_waits_longer(self):
        os.environ["CLEANVIEW_UPDATED"] = "x"
        waits = []
        with mock.patch.object(self.lm, "hold", lambda n, wait=0: waits.append(wait) or True), \
                mock.patch.object(self.lm, "update", lambda: None), \
                mock.patch.object(self.lm.runpy, "run_path") as run:
            self.lm.run_app()
        self.assertEqual(waits, [self.lm.RESTART_WAIT])
        run.assert_called_once()
        self.assertEqual(self.lm.PID_FILE.read_text(encoding="utf8"), str(os.getpid()))
        self.assertIn("Opening", self.lm.OPENING_NOTE.read_text(encoding="utf8"))


@unittest.skipUnless(WINDOWS, "a real window")
class OpeningBox(unittest.TestCase):
    def test_closes_when_the_window_is_up(self):
        lm = load_launcher()
        child = subprocess.Popen([sys.executable, "-c", support.HIDE +
                                  "import time, tkinter as tk; time.sleep(2); r = tk.Tk(); "
                                  "r.after(4000, r.destroy); r.mainloop()"])
        t = time.time()
        lm.splash(child)
        took = time.time() - t
        self.assertGreater(took, 1.5)
        self.assertLess(took, 5.5)          # not when the window closes at 6 s
        child.wait()

    def test_closes_when_it_stops(self):
        lm = load_launcher()
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(1)"])
        t = time.time()
        lm.splash(child)
        self.assertLess(time.time() - t, 4)

    def test_says_whats_happening(self):
        lm = load_launcher()
        lm.opening("Getting CleanView 9.9.9…")
        self.assertEqual(lm.OPENING_NOTE.read_text(encoding="utf8"),
                         "Getting CleanView 9.9.9…")


if __name__ == "__main__":
    unittest.main()
