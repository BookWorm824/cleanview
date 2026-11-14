"""The owner, 2026-11-14: "in the choose file area, after choosing a file the name of the file
chosen goes in the area, can the text be a couple sizes bigger and bolder a little". Once
videos are chosen, step 1's line is Segoe UI Semibold 12 (it was the plain 10); "Nothing
chosen yet" stays as it was."""
import tkinter as tk
import unittest
from tkinter import font as tkfont

import support  # noqa: F401
import test_ui

ui = test_ui.ui


class ChosenBigger(unittest.TestCase):
    def test_bigger_and_bolder_once_chosen(self):
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
                before = tkfont.Font(font=app.vid_lbl.cget("font"))
                self.assertEqual(app.vid_lbl.cget("text"), "Nothing chosen yet")
                app.videos = [str(support.SANDBOX / "Castle S2E6.mp4")]
                app._refresh_labels()
                app.update_idletasks()
                after = tkfont.Font(font=app.vid_lbl.cget("font"))
                self.assertIn("Castle S2E6.mp4", app.vid_lbl.cget("text"))
                self.assertEqual(abs(after.actual("size")) - abs(before.actual("size")), 2)
                self.assertEqual(after.actual("family"),
                                 tkfont.Font(font=(ui.HEAD, 12)).actual("family"))
                self.assertEqual(ui.CHOSEN_FONT, (ui.HEAD, 12))
            finally:
                app.destroy()
        finally:
            ui.App._check_update, ui.App._check_every_ai, ui.App._lengths = saved


if __name__ == "__main__":
    unittest.main()
