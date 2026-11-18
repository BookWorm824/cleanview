"""Young kids and Kids go back to their standard ticks after every scan; Teens and Adults keep
theirs (1.18.134; the owner, 2026-11-18: "if someone scan an adult movie and had it on kids and
unchecked something it stays unticked for kids movie next time", "can we make it so teen and
adult remember their ticks, but after every scan kids and young kids go back to defaault")."""
import inspect
import tkinter as tk
import unittest

import support  # noqa: F401  (must come first)
import test_ui

ui = test_ui.ui


class FreshAges(unittest.TestCase):
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

    def pick(self, age):
        self.app.profile_var.set(age)
        self.app._profile_changed()

    def test_after_a_scan(self):
        app = self.app
        for age in ("young", "kids", "teens", "adults"):        # a change on every age
            self.pick(age)
            app.opts["bullying"].set(not ui.PRESETS[age]["bullying"])
        self.pick("kids")                                        # scanning on Kids
        app._fresh_young_ages()
        self.assertEqual(app.opts["bullying"].get(), ui.PRESETS["kids"]["bullying"])   # on screen
        settings = app._load_settings()
        for age in ("young", "kids"):
            self.assertEqual(settings["profiles"][age]["bullying"], ui.PRESETS[age]["bullying"])
        for age in ("teens", "adults"):                          # kept
            self.assertEqual(settings["profiles"][age]["bullying"],
                             not ui.PRESETS[age]["bullying"])
        self.pick("teens")
        self.assertEqual(app.opts["bullying"].get(), not ui.PRESETS["teens"]["bullying"])

    def test_scanning_on_adults_keeps_its_ticks(self):
        app = self.app
        self.pick("adults")
        app.opts["crude"].set(not ui.PRESETS["adults"]["crude"])
        app._fresh_young_ages()
        self.assertEqual(app.opts["crude"].get(), not ui.PRESETS["adults"]["crude"])

    def test_done_when_cleaning_starts(self):
        src = inspect.getsource(ui.App.start)
        self.assertLess(src.index("self._start_jobs()"), src.index("self._fresh_young_ages()"))
        self.assertLess(src.index("self._fresh_young_ages()"), src.index("self.show_working("))
        self.assertLess(src.index("self.scan_opts ="), src.index("self._fresh_young_ages()"))


if __name__ == "__main__":
    unittest.main()
