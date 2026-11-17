"""The chosen age lights up in the logo's green (1.18.126; the owner, 2026-11-17: "in the young
kid kid teen area, when you make a selection of the 4, it makes a darker oval around one, can we
have that oval light up the logo green to shows it on"), with white writing, in Light and Dark.
The other pickers (Light/Dark, the kissing choices) keep their white oval."""
import unittest
import tkinter as tk

import support  # noqa: F401  (must come first)
import test_ui

ui = test_ui.ui
look = ui.look


def hexrgb(c):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


class AgesGreen(unittest.TestCase):
    def setUp(self):
        self.saved = ui.App._check_update, ui.App._check_every_ai
        ui.App._check_update = lambda self, manual=False: None
        ui.App._check_every_ai = lambda self: None

    def tearDown(self):
        ui.App._check_update, ui.App._check_every_ai = self.saved

    def pickers(self, app):
        found = []

        def walk(w):
            for c in w.winfo_children():
                if isinstance(c, look.Segmented):
                    found.append(c)
                walk(c)
        walk(app)
        return found

    def check(self, theme):
        try:
            app = ui.App()
        except tk.TclError as ex:
            raise unittest.SkipTest(f"no screen to draw on ({ex})")
        was = app.theme_var.get()
        try:
            if was != theme:
                app._set_theme(theme)
            app.update()
            ages = [s for s in self.pickers(app) if s.var is app.profile_var]
            self.assertEqual(len(ages), 1)
            s = ages[0]
            for value, _ in ui.PROFILES:
                s.var.set(value)
                app.update()
                x0, x1, _, label = [sp for sp in s._spots if sp[2] == value][0]
                h = int(s.cget("height"))
                self.assertEqual(s._img.get(int(x0 + (x1 - x0) * 0.15), h // 2),
                                 hexrgb(ui.ACCENT), label)
                fills = {s.itemcget(i, "text"): s.itemcget(i, "fill")
                         for i in s.find_all() if s.type(i) == "text"}
                self.assertEqual(fills[label].upper(), "#FFFFFF", label)
                self.assertTrue(all(f.upper() != "#FFFFFF" for t, f in fills.items() if t != label))
            others = [p for p in self.pickers(app) if p is not s]
            self.assertTrue(others)
            self.assertTrue(all(p._on is None for p in others))      # theirs stay white
        finally:
            if app.theme_var.get() != was:
                app._set_theme(was)
            app.destroy()

    def test_light(self):
        self.check("light")

    def test_dark(self):
        self.check("dark")


if __name__ == "__main__":
    unittest.main()
