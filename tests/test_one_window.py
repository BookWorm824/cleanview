"""One CleanView at a time, and a window straight away (1.18.64; the owner, 2026-11-12: "it can
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
        with mock.patch.object(self.lm, "exists", lambda n: n == self.lm.ONE_NAME),                 mock.patch.object(self.lm, "still_opening", lambda: None):
            self.assertTrue(self.lm.clicked())
        self.assertEqual(self.calls, ["bring_forward"])

    def test_still_updating_shows_the_box_again(self):
        # 1.18.128 (the owner, 2026-11-17: closed the box during an update, clicked again and
        # got only "a blue spinner"): no window yet, so the box comes back for that one
        proc = self.lm.Running(os.getpid())
        with mock.patch.object(self.lm, "exists", lambda n: n == self.lm.ONE_NAME),                 mock.patch.object(self.lm, "still_opening", lambda: proc):
            self.assertTrue(self.lm.clicked())
        self.assertEqual(self.calls, ["bring_forward", "splash"])

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

    def test_waits_while_updating(self):
        lm = load_launcher()
        lm.opening("Updating CleanView to 9.9.9… (3 of 21)")
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(2.5)"])
        t = time.time()
        lm.splash(child, most=0.5)              # not gone at `most` while it's updating
        self.assertGreater(time.time() - t, 2.0)
        child.wait()

    def test_opening_still_goes_at_most(self):
        lm = load_launcher()
        lm.opening("Opening CleanView…")
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(6)"])
        t = time.time()
        lm.splash(child, most=0.5)
        self.assertLess(time.time() - t, 3)
        child.kill()
        child.wait()

    def test_says_whats_happening(self):
        lm = load_launcher()
        lm.opening("Getting CleanView 9.9.9…")
        self.assertEqual(lm.OPENING_NOTE.read_text(encoding="utf8"),
                         "Getting CleanView 9.9.9…")


class StillRunning(unittest.TestCase):
    def test_running_and_ended(self):
        lm = load_launcher()
        self.assertIsNone(lm.Running(os.getpid()).poll())
        p = subprocess.Popen([sys.executable, "-c", "pass"])
        p.wait()
        self.assertIsNotNone(lm.Running(p.pid).poll())

    def test_still_opening_reads_the_pid(self):
        lm = load_launcher()
        p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(5)"])
        try:
            lm.PID_FILE.parent.mkdir(parents=True, exist_ok=True)
            lm.PID_FILE.write_text(str(p.pid), encoding="utf8")
            self.assertEqual(lm.still_opening().pid, p.pid)
        finally:
            p.kill()
            p.wait()
        self.assertIsNone(lm.still_opening())


class TheUpdate(unittest.TestCase):
    """1.18.128: the files several at a time, each tried twice, within UPDATE_MOST, and the
    opening box told how far it's got. Nothing goes online: urlopen is a stand-in."""

    def setUp(self):
        import json
        import tempfile
        from pathlib import Path
        self.lm = load_launcher()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.here = Path(self.tmp.name)
        (self.here / "version.json").write_text(json.dumps({"version": "1.0.0", "files": []}))
        self.files = {"a.py": b"x = 1\n", "b.txt": b"hello", "CleanView.pyw": b"y = 2\n"}
        self.remote = {"version": "1.0.1", "files": list(self.files)}
        self.slow, self.fail_once, self.asked = set(), set(), []
        p = mock.patch.object(self.lm, "HERE", self.here)
        p.start()
        self.addCleanup(p.stop)

    def urlopen(self, url, timeout=None):
        import io
        import json
        name = url.rsplit("/", 1)[-1]
        self.asked.append(name)
        if name == "version.json":
            body = json.dumps(self.remote).encode()
        else:
            if name in self.slow:
                time.sleep(3)
            if name in self.fail_once:
                self.fail_once.discard(name)
                raise OSError("handshake timed out")
            body = self.files[name]
        r = io.BytesIO(body)
        r.__enter__ = lambda *a: r
        r.__exit__ = lambda *a: None
        return mock.MagicMock(__enter__=lambda s: r, __exit__=lambda s, *a: None)

    def run_update(self):
        with mock.patch.object(self.lm.urllib.request, "urlopen", self.urlopen):
            return self.lm.update()

    def test_every_file_and_how_far(self):
        self.assertEqual(self.run_update(), "1.0.1")
        for name, body in self.files.items():
            self.assertEqual((self.here / name).read_bytes(), body)
        self.assertIn("(3 of 3)", self.lm.OPENING_NOTE.read_text(encoding="utf8"))
        self.assertTrue(self.lm.OPENING_NOTE.read_text(encoding="utf8").startswith("Updating"))

    def test_a_file_that_fails_once_is_tried_again(self):
        self.fail_once.add("b.txt")
        self.assertEqual(self.run_update(), "1.0.1")
        self.assertEqual(self.asked.count("b.txt"), 2)

    def test_too_slow_waits_for_next_time(self):
        self.slow.add("CleanView.pyw")
        self.lm.UPDATE_MOST = 1
        t = time.time()
        with self.assertRaises(TimeoutError):
            self.run_update()
        self.assertLess(time.time() - t, 2.5)
        self.assertFalse((self.here / "a.py").exists())      # nothing swapped in
        import json
        self.assertEqual(json.loads((self.here / "version.json").read_text())["version"],
                         "1.0.0")

    def test_at_once(self):
        for n in self.files:
            self.slow.add(n)
        t = time.time()
        self.run_update()
        self.assertLess(time.time() - t, 5)       # three 3-second files: about 3, not 9


if __name__ == "__main__":
    unittest.main()
