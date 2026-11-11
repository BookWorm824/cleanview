"""What runs side by side, and what doesn't (1.18.54, 2026-11-10; the owner: "All four", then,
after measuring, "Yes, trim and test"):
1. the AI helper starts in the background (the window and each video waited up to 20 s);
2. nothing heavy runs beside the AI helper: it slows down badly whenever the processor is
   busy (reading during the picture scan made a clean twice as long; voices during the
   closer look made its checks time out), so voices aren't told apart during the closer
   look any more, and checks that failed are always looked at again;
3. the progress bar doesn't jump to 97% at "Finding language" and back;
4. speaker numbers are the same every run (a tie was split by a set's random order).
A whole analyze() with stand-ins for the slow parts gives the same analysis either way."""
import inspect
import json
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

import support
import test_timing as T

import cleanview as engine
import cleanview_ai as ai

OPTS = {"nudity": True, "sexref": True, "samesex": True, "violence": False, "sex": False,
        "loudmusic": False, "ai": True, "reader": "local", "autosubs": True, "look": True}
LINES = [{"s": 1.0 + 2 * k, "e": 2.5 + 2 * k, "text": f"line number {k} said here"}
         for k in range(5)]


class Recorder:
    def __init__(self):
        self.t0 = time.monotonic()
        self.ev = []
        self.lock = threading.Lock()

    def span(self, name, secs, result):
        def f(*a, **k):
            s = time.monotonic() - self.t0
            time.sleep(secs)
            with self.lock:
                self.ev.append((name, s, time.monotonic() - self.t0))
            return result() if callable(result) else result
        return f

    def at(self, name):
        return next((s, e) for n, s, e in self.ev if n == name)


@T.needs_ffmpeg
class SameAnalysisEitherWay(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.video = support.SANDBOX / "Overlap Show S01E01.mp4"
        if not cls.video.exists():
            T.ffmpeg("-f", "lavfi", "-i", "testsrc=size=64x48:rate=10:duration=12", "-f",
                     "lavfi", "-i", "sine=frequency=300:duration=12", "-c:v", "libx264",
                     "-c:a", "aac", "-shortest", cls.video)

    def run_analyze(self, gpu):
        rec, said = Recorder(), []
        work = Path(tempfile.mkdtemp(dir=support.SANDBOX))
        n = int(12 * engine.VISUAL_FPS)
        vis = {"version": engine.PICTURE_VERSION, "fps": engine.VISUAL_FPS,
               "classes": list(engine.KEEP), "scores": [[0.0] * len(engine.KEEP)] * n,
               "lum": [[120.0, 40.0]] * n, "lifted": [], "notes": ["a note from the picture"]}
        asr = [{"t": w, "s": 1.0 + 0.4 * k, "e": 1.3 + 0.4 * k}
               for k, w in enumerate("line number one said here".split())]
        voices = [{"g": "m", "spk": 1} for _ in LINES]
        with mock.patch.object(ai, "start_ollama", rec.span("ai starts", 0.4, True)), \
                mock.patch.object(ai, "choose_models", lambda: True), \
                mock.patch.object(ai, "clip_ready", lambda: False), \
                mock.patch.object(ai, "on_graphics_card", lambda model=None: gpu), \
                mock.patch.object(ai, "free_memory", lambda: None), \
                mock.patch.object(ai, "dialogue_lines", lambda *a, **k: [dict(l) for l in LINES]), \
                mock.patch.object(ai, "romance_scenes", rec.span("conversations", 0.1, [])), \
                mock.patch.object(engine, "available_memory_gb", lambda: 16.0), \
                mock.patch.object(engine, "load_listeners", lambda *a: [None]), \
                mock.patch.object(engine, "transcribe", rec.span("listen", 0.8, asr)), \
                mock.patch.object(engine, "fetch_subtitles",
                                  rec.span("subtitles", 0.0, ([], "", None, "none online"))), \
                mock.patch.object(engine, "visual_scan", rec.span("pictures", 2.0, vis)), \
                mock.patch.object(engine, "find_voices", rec.span(
                    "voices", 0.1, lambda: [dict(v) for v in voices])), \
                mock.patch.object(engine, "find_lines", rec.span(
                    "reading", 0.3, ([], "the AI helper"))), \
                mock.patch.object(engine, "make_thumbs", lambda *a, **k: None):
            engine.analyze(str(self.video), str(work), groups=["swearing"], opts=OPTS,
                           progress=lambda f, m: said.append((f, m)), log=lambda m: None)
        st = json.loads((work / "analysis.json").read_text())
        return st, rec, said

    def test_the_ai_helper_starts_while_it_listens_and_nothing_runs_beside_it(self):
        runs = [self.run_analyze(gpu) for gpu in (False, True)]
        (a, _, _), (b, _, _) = runs
        for st in (a, b):
            st.pop("path", None)
        self.assertEqual(a, b)                          # a graphics card changes nothing now
        self.assertLess(b["notes"].index("a note from the picture"),
                        b["notes"].index("No subtitles: none online."))   # notes' order kept
        for st, r, said in runs:
            self.assertLess(r.at("listen")[0], r.at("ai starts")[1])     # started meanwhile
            order = ["listen", "pictures", "voices", "reading", "conversations"]
            for x, y in zip(order, order[1:]):           # the rest one after the other
                self.assertGreaterEqual(r.at(y)[0], r.at(x)[1] - 0.05, (x, y))
            fr = [f for f, m in said]                    # the progress bar only goes forward
            back = [(said[i - 1], said[i]) for i in range(1, len(fr)) if fr[i] < fr[i - 1] - 1e-9]
            self.assertEqual(back, [])
            lang = next(f for f, m in said if m.startswith("Finding language"))
            self.assertLess(lang, 0.5)                   # not 97% any more

    def test_voices_not_during_the_closer_look_and_failed_checks_looked_at_again(self):
        src = inspect.getsource(engine.analyze)
        self.assertNotIn("tell_voices", src)
        self.assertNotIn("voices_job", src)
        self.assertNotIn("on_graphics_card", src)
        self.assertEqual(src.count("recheck_failed(todo"), 2)   # after each closer look
        self.assertNotIn("if voices_job is not None:\n                    n_redo", src)


TIE = r'''
import json, sys
sys.path.insert(0, sys.argv[1])
from types import SimpleNamespace
import numpy as np
import cleanview_ai as ai

class Tagger:          # a man, a woman, a man, a woman: one "speaker" heard as both, 2 and 2
    def create_stream(self):
        box = {}
        return SimpleNamespace(accept_waveform=lambda sr, x: box.update(x=x), box=box)
    def compute(self, st, top_k=527):
        man = float(st.box["x"].mean()) < 0.5
        return [SimpleNamespace(name=ai.VOICE_CLASSES[0 if man else 1], prob=0.9)]

audio = np.concatenate([np.full(ai.VSR * 3, v, np.float32) for v in (0.1, 0.9, 0.1, 0.9)])
lines = [{"s": 3.0 * k + 0.5, "e": 3.0 * k + 2.0, "text": "x"} for k in range(4)]
print(json.dumps(ai.line_voices(audio, lines, Tagger(), [(0.0, 12.0, 0)])))
'''


class SameSpeakerNumbersEveryRun(unittest.TestCase):
    def test_a_tie_is_split_the_same_way_every_run(self):
        import os
        import sys
        script = support.SANDBOX / "tie.py"
        script.write_text(TIE, encoding="utf8")
        repo = str(Path(engine.__file__).parent)
        got = set()
        for seed in ("0", "7", "17", "8"):     # (the old code split these two ways)
            env = dict(os.environ, PYTHONHASHSEED=seed)
            r = subprocess.run([sys.executable, str(script), repo], capture_output=True,
                               text=True, env=env)
            self.assertEqual(r.returncode, 0, r.stderr)
            got.add(r.stdout.strip())
        self.assertEqual(len(got), 1, got)
        out = json.loads(got.pop())
        self.assertEqual(len({v["spk"] for v in out}), 2)          # split in two


class OneOllama(unittest.TestCase):
    def test_not_started_twice(self):
        started = []
        found = '"ollama.exe","4321","Console","1","120,000 K"\n'
        with mock.patch.object(ai, "ollama_running", side_effect=[False, True]), \
                mock.patch.object(ai, "find_ollama", lambda: "ollama.exe"), \
                mock.patch.object(ai.os, "name", "nt"), \
                mock.patch.object(ai.subprocess, "run",
                                  lambda *a, **k: subprocess.CompletedProcess(a, 0, found, "")), \
                mock.patch.object(ai.subprocess, "Popen", lambda *a, **k: started.append(a)), \
                mock.patch.object(ai.time, "sleep", lambda s: None):
            self.assertTrue(ai.start_ollama(wait=3))
        self.assertEqual(started, [])

    def test_started_when_none_is_running(self):
        started = []
        with mock.patch.object(ai, "ollama_running", side_effect=[False, True]), \
                mock.patch.object(ai, "find_ollama", lambda: "ollama.exe"), \
                mock.patch.object(ai.os, "name", "nt"), \
                mock.patch.object(ai.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(
                    a, 0, "INFO: No tasks are running which match the specified criteria.", "")), \
                mock.patch.object(ai.subprocess, "Popen", lambda *a, **k: started.append(a)), \
                mock.patch.object(ai.time, "sleep", lambda s: None):
            self.assertTrue(ai.start_ollama(wait=3))
        self.assertEqual(len(started), 1)


class TheWindow(unittest.TestCase):
    def test_starts_the_ai_helper_without_waiting(self):
        import test_ui
        src = inspect.getsource(test_ui.ui.App._run_workers)
        self.assertIn("threading.Thread(target=start_ai, daemon=True).start()", src)
        self.assertNotIn("engine.ai.start_ollama(wait=20)\n        except", src)


if __name__ == "__main__":
    unittest.main()
