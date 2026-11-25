"""The review page opens at once with a season (1.18.168; the owner: "after doing several it takes
a long time to load this screen", then "Yes, fix it"). 20 episodes of The Resident took 40 s
here: every tick, label and button is a window of its own, and all 5,563 were placed before
anything showed. Now the first video is built at once and the rest a piece at a time; every
tick is made first, so saving, Tick all and "Every video, by filter" have every video."""
import tkinter as tk
import unittest

import support  # noqa: F401  (must come first)
import test_filter_groups as fg
from test_ui import ui

VIDEOS = 6          # 6 videos of 12+ rows: past LAZY_FROM


class ReviewSpeed(unittest.TestCase):
    setUpClass = fg.FilterGroups.__dict__["setUpClass"]
    tearDownClass = fg.FilterGroups.__dict__["tearDownClass"]
    settle = fg.FilterGroups.settle
    review = fg.FilterGroups.review
    click = fg.FilterGroups.click

    def open(self, n=VIDEOS):
        app = self.app
        self.errors = []
        app.report_callback_exception = lambda *a: self.errors.append(a)
        sts = []
        for i in range(n):
            st = self.review()
            st["path"] = st["path"].replace(".mp4", f" {i}.mp4").replace(".mkv", f" {i}.mkv")
            sts.append(st)
        app.jobs = [{"video": st["path"], "work": support.write_review(), "analysis": st,
                     "error": None, "cuts": [], "lines": [], "words": []} for st in sts]
        app.videos = [st["path"] for st in sts]
        app.chat_history, app.chat_sessions = [], {}
        app.show_review()               # no settling: what she sees first

    def counts(self):
        a = self.app
        return len(a.scene_vars), len(a.line_vars), len(a.word_vars)

    def test_first_video_at_once_every_tick_made(self):
        self.open()
        self.assertEqual(sorted(self.app.found_frames), [0])
        self.assertEqual(self.counts(), (3 * VIDEOS, 3 * VIDEOS, 6 * VIDEOS))
        self.app._build_through(VIDEOS)
        self.assertEqual(sorted(self.app.found_frames), list(range(VIDEOS)))
        self.assertEqual(self.counts(), (3 * VIDEOS, 3 * VIDEOS, 6 * VIDEOS))   # none twice
        self.assertEqual(self.errors, [])

    def test_rest_built_while_the_window_runs(self):
        self.open()
        self.settle(3)
        self.assertFalse(self.app._pending)
        self.assertEqual(len(self.app.found_frames), VIDEOS)
        boxes = [b for b in fg.every(self.app, ttk_check()) if b.cget("variable")]
        names = {str(v) for v, _, _ in self.app.word_vars}
        self.assertEqual(len(names & {str(b.cget("variable")) for b in boxes}), 6 * VIDEOS)
        self.assertEqual(self.errors, [])

    def test_ticks_by_filter_reach_videos_not_built_yet(self):
        self.open()
        vs = self.app._filter_vars["God's name"]           # what its "Untick all" unticks
        self.assertEqual(len(vs), 3 * VIDEOS)
        for v in vs:
            v.set(False)
        last = self.app.jobs[-1]
        self.assertNotIn(VIDEOS - 1, self.app.found_frames)
        self.app._sync_job(last)
        self.assertEqual({(m["cat"], m.get("keep", False)) for m in last["analysis"]["mutes"]},
                         {("deity", True), ("mild", False), ("strong", False)})

    def test_save_takes_every_video(self):
        self.open()
        app = self.app
        self.assertEqual(len({id(jj) for v, jj, _ in app.word_vars if v.get()}), VIDEOS)

    def test_jump_to_a_video_builds_it(self):
        self.open()
        head = next(w for w in fg.every(self.app, tk.Label)
                    if self.app._head_ji.get(str(w)) == 4)
        self.app._jump_to(head)
        self.assertEqual(sorted(self.app.found_frames), list(range(5)))

    def test_scene_added_to_a_video_not_built_yet(self):
        self.open()
        job = self.app.jobs[-1]
        sc = self.app._add_scene(job, 300.0, 310.0, "you added this")
        self.assertIn(sc, [s for _, j, s in self.app.scene_vars if j is job])

    def test_built_again_stops_the_old_build(self):
        self.open()
        old = self.app._pending
        self.app.show_review()
        self.assertIsNot(self.app._pending, old)
        self.settle(3)
        self.assertEqual(self.errors, [])
        self.assertEqual(self.counts(), (3 * VIDEOS, 3 * VIDEOS, 6 * VIDEOS))

    def test_a_small_review_is_built_at_once(self):
        self.open(2)
        self.assertEqual(sorted(self.app.found_frames), [0, 1])
        self.assertFalse(self.app._pending)

    def test_a_piece_that_fails_doesnt_stop_the_rest(self):
        said, real = [], ui.save_details
        broke = []

        def bad(app, card, job, l, *a):
            if not broke:
                broke.append(1)
                raise ValueError("made up")
            return real_row(app, card, job, l, *a)
        real_row = ui.App._line_row
        ui.save_details, ui.App._line_row = said.append, bad
        try:
            self.open()
            self.settle(3)
        finally:
            ui.save_details, ui.App._line_row = real, real_row
        self.assertEqual(len(self.app.found_frames), VIDEOS)
        self.assertTrue(any("made up" in s for s in said))


def ttk_check():
    from tkinter import ttk
    return ttk.Checkbutton


if __name__ == "__main__":
    unittest.main()
