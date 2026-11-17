"""The "Your last review isn't finished" box keeps both its buttons (the owner, 2026-11-17: "when
going back after scannin a movie", "wher it says pick up where i lefft off", "the disregard
button", "is missing"). The words, the Pick up button and Discard sat side by side, and a long
name ("Call the Midwife - Christmas Special S1.avi") left Discard no room; at the largest text
size Pick up went too."""
import json
import os
import tempfile
import time
import tkinter as tk
import unittest
from pathlib import Path

import support  # noqa: F401  (must come first)
import test_ui

ui = test_ui.ui
LONG = "Call the Midwife - Christmas Special S1.avi"


class BothButtons(unittest.TestCase):
    def setUp(self):
        self.saved = (ui.App._check_update, ui.App._check_every_ai, ui.App.SESSION)
        ui.App._check_update = lambda self, manual=False: None
        ui.App._check_every_ai = lambda self: None
        self.tmp = tempfile.TemporaryDirectory()
        ui.App.SESSION = Path(self.tmp.name, "last_review.json")

    def tearDown(self):
        ui.App._check_update, ui.App._check_every_ai, ui.App.SESSION = self.saved
        self.tmp.cleanup()

    def buttons(self, name, size=None):
        ui.App.SESSION.write_text(json.dumps({"saved": "Nov 17 at 9:41 AM",
                                              "jobs": [{"video": "C:/v/" + name}]}))
        try:
            app = ui.App()
        except tk.TclError as ex:
            raise unittest.SkipTest(f"no screen to draw on ({ex})")
        was = app.text_size
        try:
            if size:
                app._set_text_size(size)
            app.geometry("940x800")
            app.update()
            found = {}

            def walk(w):
                for c in w.winfo_children():
                    try:
                        t = str(c.cget("text"))
                    except tk.TclError:
                        t = ""
                    if t in ("Pick up where I left off", "Discard"):
                        found[t] = (c.winfo_ismapped(), c.winfo_width(), c.winfo_reqwidth())
                    walk(c)
            walk(app)
            return found
        finally:
            if app.text_size != was:        # it's saved: later tests would start at Largest
                app._set_text_size(was)
            app.destroy()

    def check(self, found):
        self.assertEqual(set(found), {"Pick up where I left off", "Discard"})
        for name, (shown, width, wants) in found.items():
            self.assertTrue(shown, name)
            self.assertGreaterEqual(width, wants, name)        # its whole width, not squeezed

    def test_a_long_name(self):
        self.check(self.buttons(LONG))

    def test_a_long_name_at_the_largest_text(self):
        self.check(self.buttons(LONG, "Largest"))

    def test_a_short_name(self):
        self.check(self.buttons("Movie.mp4"))

    def test_the_update_note_goes_and_the_box_stays(self):
        # 1.18.120's first try named the box's words "said", as the update note above it is
        # named, and the note's timer took the box's words away instead of the note
        ui.App.SESSION.write_text(json.dumps({"saved": "Nov 17 at 9:41 AM",
                                              "jobs": [{"video": "C:/v/" + LONG}]}))
        os.environ.pop("CLEANVIEW_UPDATED", None)
        try:
            app = ui.App()
        except tk.TclError as ex:
            raise unittest.SkipTest(f"no screen to draw on ({ex})")
        saved_secs = ui.UPDATED_SHOWN_SECS
        try:
            ui.UPDATED_SHOWN_SECS = 0.5         # the start page built with the note, as after
            os.environ["CLEANVIEW_UPDATED"] = "CleanView was updated to version 9.9.9."
            app.show_setup()                    # an update (test_updated_note does the same)
            def labels(w):
                out = [str(w.cget("text"))] if isinstance(w, tk.Label) else []
                for c in w.winfo_children():
                    out += labels(c)
                return out

            def texts(w):
                return " | ".join(labels(w))
            app.update()
            self.assertIn("updated to version 9.9.9", texts(app))
            end = time.time() + 1.5
            while time.time() < end:
                app.update()
                time.sleep(0.02)
            self.assertNotIn("updated to version 9.9.9", texts(app))
            self.assertIn("Your last review isn't finished", texts(app))
        finally:
            ui.UPDATED_SHOWN_SECS = saved_secs
            os.environ.pop("CLEANVIEW_UPDATED", None)
            app.destroy()


if __name__ == "__main__":
    unittest.main()
