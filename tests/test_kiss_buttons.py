"""The kissing choices say "Cut" (1.18.103, 2026-11-14; the owner: "under the kisses tab when
choosing it say "keep" "passonate" "all kisses" arent the 2 redundant"). They weren't: one cuts
only passionate kisses, the other every kiss, but "Passionate" didn't say so. The buttons read
"Keep", "Cut passionate", "Cut all kisses"; what each one sets is as before, and they fit the
window at every text size."""
import unittest
import tkinter as tk

import support  # noqa: F401
from test_ui import ui


class KissButtons(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.real = (ui.App._check_update, ui.App._check_every_ai)
        ui.App._check_update = lambda self, manual=False: None
        ui.App._check_every_ai = lambda self: None
        try:
            cls.app = ui.App()
        except tk.TclError as ex:
            raise unittest.SkipTest(f"no screen to draw on ({ex})")
        cls.app.update()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.app._set_text_size("Normal")
            cls.app.destroy()
        except tk.TclError:
            pass
        ui.App._check_update, ui.App._check_every_ai = cls.real

    def kiss_buttons(self):
        app = self.app
        app._go_step(2)
        app._section_heads["Romance and relationships"][3](True)
        app.update()
        found = []

        def walk(w):
            if isinstance(w, ui.look.Segmented) and any(v == "Cut all kisses" for v, _ in w.options):
                found.append(w)
            for c in w.winfo_children():
                walk(c)
        walk(app)
        return found

    def test_say_cut(self):
        segs = self.kiss_buttons()
        self.assertEqual(len(segs), 2, "man & woman, and same-sex")
        for s in segs:
            self.assertEqual([label for _, label in s.options],
                             ["Keep", "Cut passionate", "Cut all kisses"])
            self.assertEqual([v for v, _ in s.options],
                             ["Keep", "Cut passionate kisses", "Cut all kisses"])

    def test_still_set_the_same(self):
        self.kiss_buttons()
        for name, level in (("Keep", "off"), ("Cut passionate kisses", "passionate"),
                            ("Cut all kisses", "all")):
            self.app.opts["kiss_os"].set(name)
            self.assertEqual(self.app._current_opts()["kiss_os"], level, name)

    def test_fit_at_every_text_size(self):
        for size in ("Normal", "Largest"):
            self.app._set_text_size(size)
            self.app.update()
            for s in self.kiss_buttons():
                self.app.update()
                right = s.winfo_rootx() + s.winfo_width()
                edge = self.app.winfo_rootx() + self.app.winfo_width()
                self.assertLessEqual(right, edge, f"{size}: the buttons run off the window")
                self.assertTrue(s.winfo_ismapped())


if __name__ == "__main__":
    unittest.main()
