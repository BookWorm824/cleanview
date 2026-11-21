"""The app shows "CleanView Save" at the top left and on its window (1.18.156; the owner: "rename
... clean view as clean view save", "when opening the app on top left where it says clean
view"), beside "CleanView Play". Only what's shown: the update seal and folders stay CleanView."""
import tkinter as tk
import unittest

import support  # noqa: F401  (must come first)
import test_ui

import launcher

ui = test_ui.ui


def every(w, out=None):
    out = [] if out is None else out
    out.append(w)
    for c in w.winfo_children():
        every(c, out)
    return out


class ShownName(unittest.TestCase):
    def setUp(self):
        self.saved = ui.App._check_update, ui.App._check_every_ai
        ui.App._check_update = lambda self, manual=False: None
        ui.App._check_every_ai = lambda self: None
        try:
            self.app = ui.App()
        except tk.TclError as ex:
            ui.App._check_update, ui.App._check_every_ai = self.saved
            raise unittest.SkipTest(f"no screen to draw on ({ex})")
        self.app.update()

    def tearDown(self):
        try:
            self.app.destroy()
        finally:
            ui.App._check_update, ui.App._check_every_ai = self.saved

    def test_top_left_and_window(self):
        self.assertEqual(ui.SHOWN_NAME, "CleanView Save")
        labels = [w.cget("text") for w in every(self.app) if isinstance(w, tk.Label)]
        self.assertIn("CleanView Save", labels)
        self.assertTrue(self.app.title().startswith("CleanView Save"))

    def test_updates_still_cleanview(self):
        # the seal installed copies check goes by the launcher's name, which stays
        self.assertEqual(launcher.APP_NAME, "CleanView")
        # and the launcher still finds the open window by its title
        self.assertTrue(self.app.title().startswith(launcher.APP_NAME))


if __name__ == "__main__":
    unittest.main()
