"""The line that says CleanView was updated goes away by itself (1.18.84; the owner, 2026-11-13:
"when it updates clean view it leaves a long bar on the top it should go away after 3 seconds",
"it says updated to version")."""
import os
import time
import unittest
import tkinter as tk

import support
from test_ui import ui


def spin(win, secs):
    end = time.time() + secs
    while time.time() < end:
        win.update()
        time.sleep(0.02)


class UpdatedNote(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.real = (ui.App._check_update, ui.App._check_every_ai, ui.UPDATED_SHOWN_SECS)
        ui.App._check_update = lambda self, manual=False: None
        ui.App._check_every_ai = lambda self: None
        os.environ.pop("CLEANVIEW_UPDATED", None)
        try:
            cls.app = ui.App()
        except tk.TclError as ex:
            ui.App._check_update, ui.App._check_every_ai = cls.real[:2]
            raise unittest.SkipTest(f"no screen to draw on ({ex})")
        cls.app.update()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.app.destroy()
        except tk.TclError:
            pass
        ui.App._check_update, ui.App._check_every_ai, ui.UPDATED_SHOWN_SECS = cls.real
        os.environ.pop("CLEANVIEW_UPDATED", None)

    def texts(self, w=None):
        w = w or self.app
        out = [str(w.cget("text"))] if isinstance(w, tk.Label) else []
        for c in w.winfo_children():
            out += self.texts(c)
        return out

    def said(self, what):
        return any(what in t for t in self.texts())

    def test_three_seconds(self):
        self.assertEqual(self.real[2], 3)

    def test_shown_then_gone(self):
        ui.UPDATED_SHOWN_SECS = 2.0       # (drawing the page takes a part of a second itself)
        for note in ("CleanView was updated to version 9.9.9.", "CleanView is up to date."):
            os.environ["CLEANVIEW_UPDATED"] = note
            began = time.time()
            self.app.show_setup()
            self.app.update()
            self.assertLess(time.time() - began, 1.8, "the page took too long to tell")
            self.assertTrue(self.said(note), note)
            self.assertNotIn("CLEANVIEW_UPDATED", os.environ)
            spin(self.app, began + 2.6 - time.time())
            self.assertFalse(self.said(note), "gone by itself")

    def test_not_there_without_an_update(self):
        self.app.show_setup()
        self.app.update()
        self.assertFalse(self.said("was updated to version"))

    def test_a_page_built_again_meanwhile(self):
        ui.UPDATED_SHOWN_SECS = 0.3
        os.environ["CLEANVIEW_UPDATED"] = "CleanView was updated to version 9.9.9."
        self.app.show_setup()
        self.app.update()
        self.app.show_setup()             # e.g. she changes the text size straight away
        spin(self.app, 0.6)               # the old line is gone with its page: no error
        self.assertFalse(self.said("was updated to version"))


if __name__ == "__main__":
    unittest.main()
