"""Running low on memory (CleanListen 1.14.4-1.14.5, 2026-11-04: "bad allocation" from the
speech recognizer, "[WinError 1455] The paging file is too small" starting ffmpeg on a smaller
PC). With several videos at once CleanView can meet the same: ffmpeg waits and tries again,
the AI helper lets go of its memory when its part is done, and running out is said plainly.
Also: a missing update.json no longer stops CleanView opening."""
import importlib.machinery
import importlib.util
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import support

import cleanview_ai as ai
import cvcore as cl
import videoqueue as VQ
from test_at_once import run_workers


def _low_memory(code=1455):
    ex = OSError("The paging file is too small for this operation to complete")
    ex.winerror = code
    return ex


class FfmpegWaitsForMemory(unittest.TestCase):
    def test_tries_again_after_waiting(self):
        tries, waits = [], []

        def start(cmd, **kw):
            tries.append(cmd)
            if len(tries) < 3:
                raise _low_memory()
            return "started"
        with mock.patch.object(cl.subprocess, "run", start), \
                mock.patch.object(cl.time, "sleep", waits.append):
            self.assertEqual(cl.run(["ffmpeg", "-version"]), "started")
        self.assertEqual(len(tries), 3)
        self.assertEqual(waits, [5, 15])

    def test_gives_up_after_the_last_wait(self):
        waits = []
        with mock.patch.object(cl.subprocess, "Popen", side_effect=_low_memory(8)), \
                mock.patch.object(cl.time, "sleep", waits.append):
            with self.assertRaises(OSError):
                cl.popen(["ffmpeg"])
        self.assertEqual(waits, list(cl.LOW_MEMORY_WAITS))

    def test_other_problems_are_not_waited_for(self):
        waits = []
        with mock.patch.object(cl.subprocess, "run", side_effect=FileNotFoundError(2, "gone")), \
                mock.patch.object(cl.time, "sleep", waits.append):
            with self.assertRaises(FileNotFoundError):
                cl.run(["nothing"])
        self.assertEqual(waits, [])


class AiHelperLetsGo(unittest.TestCase):
    def test_only_loaded_models_are_unloaded(self):
        calls = []

        class Answer(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *a):
                self.close()

        def api(path, payload=None, timeout=10):
            calls.append((path, payload))
            if path == "/api/ps":
                return Answer(json.dumps({"models": [
                    {"name": ai.TEXT_MODELS[0]}, {"name": "someone-elses:7b"}]}).encode())
            return Answer(b"{}")
        with mock.patch.object(ai, "_api", api):
            ai.free_memory()
        self.assertEqual(calls, [("/api/ps", None),
                                 ("/api/generate", {"model": ai.TEXT_MODELS[0], "keep_alive": 0})])

    def test_never_a_problem_of_its_own(self):
        with mock.patch.object(ai, "_api", side_effect=OSError("not running")):
            ai.free_memory()


class SaidPlainly(unittest.TestCase):
    def test_out_of_memory(self):
        for ex in (MemoryError(), RuntimeError("bad allocation"),
                   RuntimeError("Couldn't read the sound.\nffmpeg said: Cannot allocate memory"),
                   _low_memory(1455), _low_memory(1450),
                   OSError("[WinError 8] Not enough storage is available to process this command")):
            self.assertEqual(VQ.plain_error(ex), VQ.OUT_OF_MEMORY, ex)
        self.assertIn("Videos at once", VQ.OUT_OF_MEMORY)
        self.assertNotIn("allocation", VQ.OUT_OF_MEMORY)

    def test_other_problems_unchanged(self):
        self.assertEqual(VQ.plain_error(RuntimeError("couldn't read the sound\nmore")),
                         "Couldn't read the sound.")
        self.assertEqual(VQ.plain_error(KeyError("x")), "Something unexpected went wrong.")

    def test_a_worker_that_ran_out(self):
        jobs, _ = run_workers(["nomemory 1.mp4", "Fine 2.mp4"])
        self.assertEqual(jobs[0]["error"], "nomemory 1.mp4: " + VQ.OUT_OF_MEMORY)
        self.assertTrue(jobs[1]["analysis"])


class LauncherWithoutUpdateJson(unittest.TestCase):
    def load(self, update_json):
        d = Path(tempfile.mkdtemp(dir=support.SANDBOX))
        shutil.copy(support.ROOT / "launcher.pyw", d / "launcher.pyw")
        if update_json is not None:
            (d / "update.json").write_text(update_json)
        loader = importlib.machinery.SourceFileLoader(f"cv_launcher_{id(d)}",
                                                      str(d / "launcher.pyw"))
        mod = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name,
                                                                              loader))
        loader.exec_module(mod)
        return mod

    def test_missing_or_broken(self):
        for text in (None, "", "{not json", "{}"):
            mod = self.load(text)
            self.assertEqual(mod.RAW,
                             "https://raw.githubusercontent.com/BookWorm824/cleanview/main/")

    def test_its_own_still_used(self):
        mod = self.load(json.dumps({"repo": "someone/else", "branch": "test"}))
        self.assertEqual(mod.RAW, "https://raw.githubusercontent.com/someone/else/test/")


if __name__ == "__main__":
    unittest.main()
