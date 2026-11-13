"""CleanView's logo on its window and taskbar button, not Tk's feather (1.18.82; the owner,
2026-11-13: "sometimes the logo for clean view down in the start bar of the computer becomes a
big feather. i noticed it after doing the recent update but it has done it before").

It couldn't be made to happen, so the logo is set more sturdily: for every window of the app,
on the window itself, and again once the window is up; and a try that fails is written down."""
import ctypes
import os
import time
import unittest
import tkinter as tk

import support
from test_ui import ui


def has_icon(win):
    """Whether Windows says this window has an icon of its own (big, as the taskbar shows)."""
    u = ctypes.WinDLL("user32")
    u.SendMessageW.restype = ctypes.c_void_p
    return bool(u.SendMessageW(u.GetParent(win.winfo_id()), 0x7F, 1, 0))      # WM_GETICON, big


def spin(win, secs):
    end = time.time() + secs
    while time.time() < end:
        win.update()
        time.sleep(0.02)


class Logo(unittest.TestCase):
    def setUp(self):
        try:
            self.win = tk.Tk()
        except tk.TclError as ex:
            self.skipTest(f"no screen to draw on ({ex})")
        self.addCleanup(self.close)
        self.win.update()
        self.note = support.APP_DATA / "icon_problem.txt"
        if self.note.exists():
            self.note.unlink()

    def close(self):
        try:
            self.win.destroy()
        except tk.TclError:
            pass                                  # closed by the test already

    @unittest.skipUnless(os.name == "nt", "Windows only")
    def test_the_window_gets_the_logo(self):
        self.assertFalse(has_icon(self.win))              # Tk's feather: no icon of its own
        self.assertTrue(ui.set_icon(self.win))
        self.win.update()
        self.assertTrue(has_icon(self.win))
        self.assertFalse(self.note.exists())

    def test_set_again_once_the_window_is_up(self):
        calls = []
        self.win.iconbitmap = lambda *a, **k: calls.append((a, k))
        self.assertTrue(ui.set_icon(self.win, again=(0.1, 0.3)))
        self.assertEqual(len(calls), 2)                   # for every window, and for this one
        self.assertEqual(calls[0][1], {"default": str(ui.ICON)})
        self.assertEqual(calls[1][0], (str(ui.ICON),))
        spin(self.win, 0.6)
        self.assertEqual(len(calls), 6)
        self.assertGreaterEqual(len(ui.ICON_AGAIN), 2)

    @unittest.skipUnless(os.name == "nt", "Windows only")
    def test_a_try_that_fails_is_written_down_and_the_next_one_works(self):
        real, tries = self.win.iconbitmap, []

        def flaky(*a, **k):
            tries.append(1)
            if len(tries) == 1:
                raise tk.TclError("couldn't read the icon just now")
            return real(*a, **k)
        self.win.iconbitmap = flaky
        self.assertFalse(ui.set_icon(self.win, again=(0.1,)))
        self.assertFalse(has_icon(self.win))
        said = self.note.read_text(encoding="utf8")
        self.assertIn("couldn't read the icon just now", said)
        self.assertIn(ui.engine.app_version(), said)
        spin(self.win, 0.4)
        self.assertTrue(has_icon(self.win))

    def test_a_window_closed_meanwhile_is_left_alone(self):
        ui.set_icon(self.win, again=(0.1,))
        self.win.destroy()
        time.sleep(0.15)                                  # nothing to run it, and no error
        self.assertFalse(self.note.exists())

    def test_a_missing_icon_file_doesnt_stop_the_window(self):
        self.assertFalse(ui.set_icon(self.win, path=support.SANDBOX / "nothing.ico", again=()))
        self.assertTrue(self.note.exists())


class TheApp(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt", "Windows only")
    def test_cleanviews_own_window(self):
        real = (ui.App._check_update, ui.App._check_every_ai)
        ui.App._check_update = lambda self, manual=False: None
        ui.App._check_every_ai = lambda self: None
        try:
            app = ui.App()
        except tk.TclError as ex:
            self.skipTest(f"no screen to draw on ({ex})")
        finally:
            ui.App._check_update, ui.App._check_every_ai = real
        try:
            app.update()
            self.assertTrue(has_icon(app))
        finally:
            app.destroy()


if __name__ == "__main__":
    unittest.main()
