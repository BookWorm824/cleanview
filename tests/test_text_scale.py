"""Each text size one step bigger (1.18.114; the owner: "lets make each starting size one size
bigger"), and a window doesn't take another's text size as the PC's own: Tk keeps one scale for
the whole process, so with "Normal" at 1.15 each window grew the last one's again."""
import tkinter as tk
import unittest

import support  # noqa: F401  (must come first)
import test_ui

ui = test_ui.ui


class OneScaleForEveryWindow(unittest.TestCase):
    def test_the_same_in_each_window(self):
        saved = ui.App._check_update, ui.App._check_every_ai
        ui.App._check_update = lambda self, manual=False: None
        ui.App._check_every_ai = lambda self: None
        seen = []
        try:
            for _ in range(3):
                try:
                    app = ui.App()
                except tk.TclError as ex:
                    self.skipTest(f"no screen to draw on ({ex})")
                try:
                    app.update()
                    seen.append((round(app._base_scaling, 4),
                                 round(float(app.tk.call("tk", "scaling")), 4)))
                finally:
                    app.destroy()
        finally:
            ui.App._check_update, ui.App._check_every_ai = saved
        self.assertEqual(len(set(seen)), 1, seen)
        base, now = seen[0]
        self.assertAlmostEqual(now, base * ui.TEXT_SIZES[app.text_size], delta=0.005)

    def test_each_one_step_bigger(self):
        self.assertEqual(ui.TEXT_SIZES, {"Normal": 1.15, "Larger": 1.3, "Largest": 1.45})


if __name__ == "__main__":
    unittest.main()
