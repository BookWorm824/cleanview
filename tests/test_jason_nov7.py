"""Jason, 2026-11-07:
1. "Claude's findings (spreadsheet)" had every movie he'd ever done: now it's just the
   video(s) on the review page, newest first in the full one.
2. The progress page was "a lot of dead space": CleanView's logo sits in the middle."""
import csv
import os
import tkinter as tk
import unittest

import support  # noqa: F401
import test_ui

import cleanview_learn as learn

ui = test_ui.ui


def review(video, text):
    return {"show": "_movies", "path": video, "reviewer": "Claude", "mutes": [], "scenes": [],
            "lines": [{"s": 5.0, "e": 7.0, "text": text, "types": ["sexref"],
                       "claude": {"decision": "remove", "why": "innuendo"}}]}


class FindingsForThisVideo(unittest.TestCase):
    def setUp(self):
        learn.record_claude(review(r"D:\Movies\Old Movie.m4v", "an old line from long ago"))
        old = learn.FINDINGS / "Old Movie.m4v.json"
        os.utime(old, (old.stat().st_mtime - 86400,) * 2)       # reviewed a day before
        learn.record_claude(review(r"D:\Movies\That Thing You Do.m4v", "the line in this one"))

    def test_just_this_video(self):
        rows = learn.findings_rows([r"D:\Movies\That Thing You Do.m4v"])
        self.assertEqual({r[2] for r in rows}, {"That Thing You Do.m4v"})
        self.assertIn("the line in this one", [r[7] for r in rows])

    def test_spreadsheet_file(self):
        path = support.SANDBOX / "Findings for this video.csv"
        n = learn.write_findings(path, ["That Thing You Do.m4v"])
        with open(path, encoding="utf-8-sig", newline="") as fh:
            got = list(csv.reader(fh))
        self.assertEqual(got[0][:3], ["Date", "Show", "Video"])
        self.assertEqual(len(got) - 1, n)
        self.assertTrue(all(r[2] == "That Thing You Do.m4v" for r in got[1:]))

    def test_all_of_them_newest_first(self):
        videos = [r[2] for r in learn.findings_rows()]
        self.assertIn("Old Movie.m4v", videos)
        self.assertLess(videos.index("That Thing You Do.m4v"), videos.index("Old Movie.m4v"))

    def test_none_for_a_new_video(self):
        self.assertEqual(learn.findings_rows(["Never Reviewed.mp4"]), [])


class LogoOnTheProgressPage(unittest.TestCase):
    def test_logo_png_from_the_icon(self):
        png = ui.logo_png(128)
        self.assertTrue(png.startswith(b"\x89PNG"))

    def test_logo_shown_for_one_video(self):
        saved = ui.App._check_update, ui.App._check_every_ai, ui.App._lengths
        ui.App._check_update = lambda self, manual=False: None
        ui.App._check_every_ai = lambda self: None
        ui.App._lengths = lambda self, videos, done: None
        try:
            try:
                app = ui.App()
            except tk.TclError as ex:
                self.skipTest(f"no screen to draw on ({ex})")
            try:
                app.jobs = [{"video": r"D:\Movies\That Thing You Do.m4v"}]
                app.show_working("Saving the clean copy…")
                app.update()
                self.assertTrue(app.logo.winfo_exists())
                self.assertEqual(int(app.logo.winfo_reqwidth()) >= 128, True)
            finally:
                app.destroy()
        finally:
            ui.App._check_update, ui.App._check_every_ai, ui.App._lengths = saved


if __name__ == "__main__":
    unittest.main()
