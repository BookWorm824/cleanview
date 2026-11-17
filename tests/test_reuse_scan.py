"""A video scanned before, opened again with the same choices, uses that scan with what CleanView
has learned since added (1.18.117; the owner, 2026-11-16: "we are having to have people scan
things multiple times to get the results", then "Yes, build that")."""
import copy
import json
import queue
import tempfile
import time
import tkinter as tk
import unittest
from pathlib import Path

import support
import cleanview as engine
from test_ui import ui

OPTS = dict(engine.DEFAULTS, profile="kids", sexref=True, sex=True, violence=False, gore=False,
            graphic=False, disturbing=False, medical=False, reader="local", ai=True)
LINES = [(520.0, "We're talking about five little points here."),
         (535.0, "He's on vacation."),
         (554.5, "Well, your mama sure does care about your schooling, son."),
         (564.0, "You don't say much, do you?"),
         (600.0, "Have you ever been with a girl, Forrest?"),
         (700.0, "Did you lose your pecker in the war or something?"),
         (800.0, "I'm living off the government tit.")]


def old_scan(video, opts=OPTS, groups=("swearing", "mild")):
    """A scan made before the Forest Gump lessons: one of the lines found then (and unticked by
    her), no scenes."""
    dialogue = [{"s": s, "e": s + 2.0, "text": t, "who": ""} for s, t in LINES]
    return {"path": str(video), "groups": list(groups), "show": "_movies@kids",
            "opts": engine.full_opts(opts), "duration": 900.0, "notes": ["Checked with: x."],
            "dialogue": dialogue, "mutes": [], "quiet": [], "cues": [],
            "asr": [[w, 600.0 + k * 0.3, 600.2 + k * 0.3]
                    for k, w in enumerate("have you ever been with a girl".split())],
            "lines": [{"id": 1, "s": 600.0, "e": 602.0, "text": LINES[4][1],
                       "plain": LINES[4][1], "types": ["sexref"], "mute": False}],
            "scenes": []}


class Engine(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.work = Path(self.tmp.name)
        self.video = self.work / "Forest Gump.mp4"
        (self.work / "analysis.json").write_text(json.dumps(old_scan(self.video)))

    def tearDown(self):
        self.tmp.cleanup()

    def saved(self, opts=OPTS, groups=("swearing", "mild"), video=None):
        return engine.saved_scan(self.work, str(video or self.video), opts, list(groups))

    def test_the_same_choices(self):
        self.assertIsNotNone(self.saved())
        self.assertIsNotNone(self.saved(dict(OPTS, offline=True, autosubs=False)))
        self.assertIsNotNone(self.saved(groups=("mild", "swearing")))

    def test_other_choices_scan_again(self):
        for change in ({"crude": True}, {"profile": "adults"}, {"reader": "claude"},
                       {"ai": False}, {"kiss_os": "all"}, {"language": "es"},
                       {"mywords": ["gosh"]}):
            with self.subTest(change):
                self.assertIsNone(self.saved(dict(OPTS, **change)))
        self.assertIsNone(self.saved(groups=("swearing",)))
        self.assertIsNone(self.saved(video=self.work / "Other.mp4"))

    def test_none_without_a_scan(self):
        (self.work / "analysis.json").unlink()
        self.assertIsNone(self.saved())

    def test_lessons_added_and_her_ticks_kept(self):
        st = self.saved()
        lines, scenes = engine.add_new_lessons(st, reused=True)
        self.assertEqual((lines, scenes), (2, 1))
        got = {l["text"]: l["mute"] for l in st["lines"]}
        self.assertEqual(got, {LINES[4][1]: False,               # hers: still unticked
                               LINES[2][1]: True, LINES[5][1]: True})   # (not the crude one:
        #                                                                  crude isn't ticked)
        sc, = st["scenes"]
        self.assertEqual((sc["s"], sc["e"], sc["kind"], sc["cut"]), (537.0, 566.5,
                                                                     ["Sex scene"], True))
        self.assertNotIn("thumbs", sc)                            # made in the background
        self.assertEqual(sorted(l["id"] for l in st["lines"]), [1, 2, 3])
        self.assertTrue(any(n.startswith(engine.SCAN_REUSED) and "2 lines to mute and 1 scene"
                            in n for n in st["notes"]), st["notes"])

    def test_twice_adds_nothing_more(self):
        st = self.saved()
        engine.add_new_lessons(st, reused=True)
        before = copy.deepcopy(st)
        self.assertEqual(engine.add_new_lessons(st, reused=True), (0, 0))
        self.assertEqual(before["lines"], st["lines"])
        self.assertEqual(before["scenes"], st["scenes"])
        self.assertEqual(sum(n.startswith(engine.SCAN_REUSED) for n in st["notes"]), 1)

    def test_only_for_filters_ticked(self):
        st = self.saved()
        st["opts"].update(sexref=False, sex=False)
        self.assertEqual(engine.add_new_lessons(st), (0, 0))
        self.assertEqual(st["notes"], ["Checked with: x."])        # nothing new: nothing said


class InTheWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.real = (ui.App._check_update, ui.App._check_every_ai, ui.messagebox.askyesno,
                    ui.VQ.Workers)
        ui.App._check_update = lambda self, manual=False: None
        ui.App._check_every_ai = lambda self: None
        try:
            cls.app = ui.App()
        except tk.TclError as ex:
            cls.put_back()
            raise unittest.SkipTest(f"no screen to draw on ({ex})")
        cls.app.update()

    @classmethod
    def put_back(cls):
        (ui.App._check_update, ui.App._check_every_ai, ui.messagebox.askyesno,
         ui.VQ.Workers) = cls.real

    @classmethod
    def tearDownClass(cls):
        try:
            cls.app.destroy()
        except tk.TclError:
            pass
        cls.put_back()

    def test_reused_without_a_worker(self):
        started = []

        class NoWorkers:
            def __init__(self, on_event):
                pass

            def start(self, k, job):
                started.append(k)
                raise RuntimeError("no worker should start")

            def stop_all(self):
                pass
        ui.VQ.Workers = NoWorkers
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            video = work / "Forest Gump.mp4"
            st = old_scan(video)
            app = self.app
            app.jobs = [{"video": str(video), "work": work, "analysis": None, "error": None,
                         "reuse": st}]
            app.cancel_flag = app.stop_after = False
            app.at_once = 1
            app.scan_opts = {"ai": False}          # (no AI helper started for this)
            app.q = queue.Queue()
            app._run_workers(getattr(app, "run", 0), app.jobs)
            self.assertEqual(started, [])
            job = app.jobs[0]
            self.assertIsNone(job["error"])
            self.assertEqual(len(job["analysis"]["lines"]), 3)
            self.assertEqual(len(job["analysis"]["scenes"]), 1)
            kept = json.loads((work / "analysis.json").read_text())   # kept for next time
            self.assertEqual(len(kept["lines"]), 3)

    def test_the_question(self):
        self.assertIn("This video was scanned before", ui.reuse_ask(1, 1))
        self.assertIn("2 of these 5 videos were", ui.reuse_ask(2, 5))
        self.assertIn("All 3 of these videos were", ui.reuse_ask(3, 3))
        self.assertIn("scan again from the start", ui.reuse_ask(1, 1))


if __name__ == "__main__":
    unittest.main()
