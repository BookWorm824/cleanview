"""The review page is quick to draw again (1.18.82; the owner, 2026-11-13: asking Claude a
question on the review page, "if you click anywhere else clean view says not responding and
then the whole screen refreshes. it comes back with a response ... i just think it shouldn't
do that").

When the answer changes the list, the review page is built again on the window's own thread.
Tk stretches a rounded button's picture by repeating its middle one copy at a time, and the
middle was one pixel wide: the page's 18 buttons took about 2.5 seconds to draw (0.2 s with
them plain). The pictures have a wide middle now, and the buttons are no bigger for it."""
import unittest
import tkinter as tk
from tkinter import ttk

import support
from test_ui import ui

look = ui.look


class WidePictures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.real = (ui.App._check_update, ui.App._check_every_ai)
        ui.App._check_update = lambda self, manual=False: None
        ui.App._check_every_ai = lambda self: None
        try:
            cls.app = ui.App()
        except tk.TclError as ex:
            ui.App._check_update, ui.App._check_every_ai = cls.real
            raise unittest.SkipTest(f"no screen to draw on ({ex})")
        cls.app.update()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.app.destroy()
        except tk.TclError:
            pass
        ui.App._check_update, ui.App._check_every_ai = cls.real

    def button(self, text, style):
        b = ttk.Button(self.app, text=text, style=style)
        b.pack()
        self.addCleanup(b.destroy)
        self.app.update()
        return b

    def test_the_middle_tk_repeats_is_wide(self):
        self.assertGreaterEqual(look.STRETCH, 32)
        pic = look._corner_img(12, "#2F6F62", "#FFFFFF")
        self.assertEqual(pic.shape[:2], (27, 27 + look.STRETCH))
        # a piece that gives its own size keeps it (the scroll bar's grip, the progress bar)
        self.assertEqual(look._corner_img(4, "#2F6F62", "#FFFFFF", w=10, h=30).shape[:2], (30, 10))

    def test_every_rounded_buttons_picture(self):
        for style in ("Accent.TButton", "Go.TButton", "Plain.TButton", "Small.TButton"):
            self.button("Save clean copy", style)
        made = self.app._round_made
        self.assertGreaterEqual(len(made), 4)
        for name, pictures in made.items():
            for p in pictures:
                self.assertGreaterEqual(p.width() - p.height(), look.STRETCH, name)

    def test_the_tabs_pictures(self):
        for p in self.app._round_tabs[0]:
            self.assertGreaterEqual(p.width() - p.height(), look.STRETCH)

    def test_the_rounded_drop_downs_pictures(self):
        # (1.18.85: the language list's box, rounded like the rest)
        pictures, r = self.app._round_drop
        self.assertEqual(len(pictures), 2)                  # resting, and the one being used
        for p in pictures:
            self.assertGreaterEqual(p.width() - p.height(), look.STRETCH)
        box = ttk.Combobox(self.app, values=["English", "A much longer language name"],
                           state="readonly", width=4, style="Round.TCombobox")
        box.pack()
        self.addCleanup(box.destroy)
        self.app.update()
        self.assertLess(box.winfo_reqwidth(), pictures[0].width())     # no wider for it

    def test_buttons_are_no_bigger_for_it(self):
        self.assertEqual(look._slim(9), {"width": 21, "height": 21})
        # a button told to be as narrow as its word is narrower than its picture
        for style in ("Small.TButton", "Plain.TButton", "Go.TButton", "Accent.TButton"):
            b = ttk.Button(self.app, text="X", style=style, width=1)
            b.pack()
            self.addCleanup(b.destroy)
            self.app.update()
            self.assertTrue(b.cget("style").startswith("on_"), b.cget("style"))   # drawn rounded
            picture = self.app._round_made[b.cget("style")][0]
            self.assertLess(b.winfo_reqwidth(), picture.width() - look.STRETCH // 2, style)
            self.assertLessEqual(b.winfo_reqheight(), picture.height() + 2, style)


if __name__ == "__main__":
    unittest.main()
