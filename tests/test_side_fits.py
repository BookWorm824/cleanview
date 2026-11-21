"""Everything in the start page's left column fits, with its margin, at every text size
(1.18.158; her screenshot at "Larger": "Send what CleanView Save learned…" was cut off at both
ends after the rename, and it only just fitted here)."""
import tkinter as tk
import unittest

import support  # noqa: F401  (must come first)
import test_ui

ui = test_ui.ui


def walk(w, out=None):
    out = [] if out is None else out
    out.append(w)
    for c in w.winfo_children():
        walk(c, out)
    return out


class SideFits(unittest.TestCase):
    def setUp(self):
        self.saved = ui.App._check_update, ui.App._check_every_ai, ui.App._set_text_size
        ui.App._check_update = lambda self, manual=False: None
        ui.App._check_every_ai = lambda self: None
        try:
            self.app = ui.App()
        except tk.TclError as ex:
            ui.App._check_update, ui.App._check_every_ai, _ = self.saved
            raise unittest.SkipTest(f"no screen to draw on ({ex})")
        self.app.update()

    def tearDown(self):
        try:
            self.app._set_text_size("Normal")
            self.app.destroy()
        finally:
            ui.App._check_update, ui.App._check_every_ai, _ = self.saved

    def test_every_size(self):
        for size in ui.TEXT_SIZES:
            with self.subTest(size=size):
                self.app._set_text_size(size)
                self.app.update()
                side = next(w for w in self.app.page.winfo_children()
                            if isinstance(w, tk.Frame) and w.cget("bg") == ui.SIDE)
                width = side.winfo_width()
                margin = self.app._px(14)       # the column's own side margin
                for w in walk(side):
                    if isinstance(w, tk.Label) and w.cget("text"):
                        right = w.winfo_rootx() - side.winfo_rootx() + w.winfo_reqwidth()
                        self.assertLessEqual(right, width - margin, (size, w.cget("text")))

    def test_the_send_link(self):
        texts = [w.cget("text") for w in walk(self.app) if isinstance(w, tk.Label)]
        self.assertIn("Send what it learned…", texts)


if __name__ == "__main__":
    unittest.main()
