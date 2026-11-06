"""Jason, 2026-11-06: "making the movie title a little bigger and bolder" on the progress
page. The title is the file's name without ".m4v", in big bold letters."""
import tkinter as tk
import unittest
from tkinter import font as tkfont

import support  # noqa: F401
from test_at_once import run_workers
import test_ui

ui = test_ui.ui


class TitleOnTheProgressPage(unittest.TestCase):
    def test_name_without_the_extension(self):
        _, msgs = run_workers(["That Thing You Do.m4v"], at_once=1)
        self.assertIn(("which", "That Thing You Do"), msgs)

    def test_several_say_which_one(self):
        _, msgs = run_workers(["Ep 1.mp4", "Ep 2.mp4"], at_once=1)
        self.assertIn(("which", "Video 1 of 2:  Ep 1"), msgs)

    def test_big_and_bold(self):
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
                f = tkfont.Font(font=app.which.cget("font"))
                status = tkfont.Font(font=app.status.cget("font"))
                self.assertEqual(f.actual("weight"), "bold")
                self.assertGreater(abs(f.actual("size")), abs(status.actual("size")))
            finally:
                app.destroy()
        finally:
            ui.App._check_update, ui.App._check_every_ai, ui.App._lengths = saved


if __name__ == "__main__":
    unittest.main()
