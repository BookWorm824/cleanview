"""Ollama only while CleanView, CleanListen or CleanRead are open (Lauren, 2026-11-05; the same
ollama_care.py as CleanListen 1.15.2, plus CleanView's video workers), and the window staying
quick to answer while videos are worked on (CleanListen 1.15.1: one core left free, the work
below normal priority). The real Ollama on this PC is never stopped here: stop() is a stand-in."""
import os
import re
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import support  # noqa: F401

import cvcore as cl
import ollama_care as O
import videoqueue as VQ

HERE = Path(__file__).resolve().parent.parent


class TakenOutOfStartup(unittest.TestCase):
    def test_taken_out_of_windows_startup(self):
        with tempfile.TemporaryDirectory() as d:
            link = Path(d) / "Ollama.lnk"
            link.write_bytes(b"x")
            self.assertTrue(O.autostart_off(link))
            self.assertFalse(link.exists())
            self.assertFalse(O.autostart_off(link), "already gone: nothing to do")


class StopWhenIdle(unittest.TestCase):
    def setUp(self):
        self.state = s = {"running": True, "others": set(), "models": [[]], "stopped": 0,
                          "slept": 0}

        def models():
            return s["models"].pop(0) if len(s["models"]) > 1 else s["models"][0]

        def sleep(sec):
            s["slept"] += sec
        for p in (mock.patch.object(O, "running", lambda: s["running"]),
                  mock.patch.object(O, "other_apps", lambda skip=(): s["others"]),
                  mock.patch.object(O, "loaded_models", models),
                  mock.patch.object(O, "stop", lambda: s.__setitem__("stopped", s["stopped"] + 1)),
                  mock.patch.object(O.time, "sleep", sleep)):
            p.start()
            self.addCleanup(p.stop)

    def test_stopped_when_nothing_uses_it(self):
        self.assertEqual(O.stop_when_idle(), "stopped")
        self.assertEqual(self.state["stopped"], 1)

    def test_left_running_while_another_app_is_open(self):
        self.state["others"] = {1234}
        self.assertEqual(O.stop_when_idle(), "in use")
        self.state["others"] = None                      # Windows couldn't say: leave it
        self.assertEqual(O.stop_when_idle(), "in use")
        self.assertEqual(self.state["stopped"], 0)

    def test_waits_for_the_model_to_be_let_go_of(self):
        self.state["models"] = [[{"name": "qwen3-vl:8b"}], [{"name": "qwen3-vl:8b"}], []]
        self.assertEqual(O.stop_when_idle(every=15), "stopped")
        self.assertGreaterEqual(self.state["slept"], 30)

    def test_a_model_kept_loaded_by_something_else_is_left_alone(self):
        self.state["models"] = [[{"name": "llama3"}]]
        clock = iter(range(0, 10_000, 60))
        with mock.patch.object(O.time, "time", lambda: next(clock)):
            self.assertEqual(O.stop_when_idle(most=420), "busy")
        self.assertEqual(self.state["stopped"], 0)

    def test_not_running_is_nothing_to_do(self):
        self.state["running"] = False
        self.assertEqual(O.stop_when_idle(), "not running")
        self.assertEqual(self.state["stopped"], 0)


class WhatCountsAsOpen(unittest.TestCase):
    def test_cleanview_window_and_video_workers_count(self):
        for line in (r'pythonw.exe "C:\Users\x\AppData\Local\CleanView\app\CleanView.pyw"',
                     r'python.exe "C:\Users\x\AppData\Local\CleanView\app\videoqueue.py" '
                     r'"D:\work\queue_task.json"',
                     r'pythonw.exe C:\x\CleanListen.pyw', r'python.exe C:\x\bookrunner.py'):
            self.assertTrue(re.search(O.CLEAN_APPS, line), line)
        self.assertFalse(re.search(O.CLEAN_APPS, r"ollama.exe serve"))

    @unittest.skipUnless(os.name == "nt", "Windows processes")
    def test_finds_a_running_video_worker(self):
        p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)",
                              r"C:\x\videoqueue.py"], creationflags=0x08000000)
        try:
            time.sleep(0.5)
            found = O.other_apps()
            self.assertIsNotNone(found)
            self.assertIn(p.pid, found)
            self.assertNotIn(p.pid, O.other_apps(skip=[p.pid]))
        finally:
            p.kill()

    def test_closing_hands_it_to_a_small_program(self):
        got = []
        with mock.patch.object(O, "installed", lambda: True), \
                mock.patch.object(O.os, "name", "nt"), \
                mock.patch.object(O.subprocess, "Popen", lambda cmd, **kw: got.append(cmd)):
            O.stop_later()
        (cmd,) = got
        self.assertEqual(cmd[:2], [sys.executable, "-c"])
        compile(cmd[2], "helper", "exec")
        self.assertIn("stop_when_idle(skip=[%d])" % os.getpid(), cmd[2])
        self.assertFalse(re.search(O.CLEAN_APPS, " ".join(cmd)),
                         "its own command line isn't taken for one of the apps")


class TheWindowUsesIt(unittest.TestCase):
    def test_called_on_opening_and_after_closing(self):
        src = (HERE / "CleanView.pyw").read_text(encoding="utf8")
        main = src[src.index('if __name__ == "__main__":'):]
        self.assertLess(main.index('_ollama_care("autostart_off")'), main.index("mainloop()"))
        self.assertLess(main.index("mainloop()"), main.index('_ollama_care("stop_later")'))

    def test_shipped_with_updates(self):
        import json
        files = json.loads((HERE / "version.json").read_text(encoding="utf8"))["files"]
        self.assertIn("ollama_care.py", files)


class WindowStaysQuick(unittest.TestCase):
    def test_one_core_left_free(self):
        self.assertEqual(VQ.threads_each(1, cpus=6), 5)
        self.assertEqual(VQ.threads_each(1, cpus=1), 1)
        self.assertEqual(VQ.threads_each(2, cpus=16), 7)
        self.assertEqual(VQ.threads_each(1, cpus=32), 8)

    @unittest.skipUnless(os.name == "nt", "Windows priorities")
    def test_work_runs_below_normal(self):
        self.assertTrue(cl._NOWIN["creationflags"] & 0x00004000, "ffmpeg")
        self.assertTrue(cl._NOWIN["creationflags"] & 0x08000000, "still no console window")
        got = {}

        def popen(cmd, **kw):
            got.update(kw)
            raise OSError("stop here")
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(VQ.subprocess, "Popen", popen):
            w = VQ.Workers(lambda k, m: None)
            with self.assertRaises(OSError):
                w.start(0, {"video": "x.mkv", "work": d})
        self.assertTrue(got["creationflags"] & 0x00004000, "video workers")


if __name__ == "__main__":
    unittest.main()
