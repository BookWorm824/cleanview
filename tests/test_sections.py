"""The start page's filters in sections by topic, each with a box that ticks or unticks all of
it and folds away to one line (1.18.74; the owner: "a main box for each category to tick all if
wanted, but if only some of the subcategories are wanted just those can be ticked. vid angel had
a system like that", "maybe not as long", and Medical its own section)."""
import unittest
import tkinter as tk

import support
from test_ui import ui

SECTIONS = ["Bad language", "Sex and nudity", "Romance and relationships", "Violence",
            "Medical", "Attitude", "Smoking, drinking and drugs", "Faith, holidays and magic",
            "Music"]


class StartPage(unittest.TestCase):
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
            cls.app.destroy()
        except tk.TclError:
            pass
        ui.App._check_update, ui.App._check_every_ai = cls.real

    def setUp(self):
        if self.app.page_name != "setup":
            self.app.show_setup()
            self.app.update()
        self.heads = self.app._section_heads

    def test_every_filter_in_a_section(self):
        self.assertEqual(list(self.heads), SECTIONS)
        for k in ui.FILTER_KEYS:
            self.assertIn(k, self.app.opts, k)

    def test_medical_on_its_own(self):
        master, count, tick_all, show = self.heads["Medical"]
        self.app.opts["medical"].set(True)
        self.app.opts["forensic"].set(False)
        self.assertEqual(count.cget("text"), "1 of 2 ticked")
        self.assertEqual(str(master.cget("image")), str(self.app._ticks["some"]))

    def test_tick_all_then_untick_all(self):
        master, count, tick_all, show = self.heads["Violence"]
        self.app.opts["gore"].set(False)
        tick_all()                                  # some ticked: all
        self.assertTrue(all(self.app.opts[k].get() for k in
                            ("violence", "graphic", "gore", "disturbing")))
        self.assertEqual(str(master.cget("image")), str(self.app._ticks["on"]))
        tick_all()                                  # all ticked: none
        self.assertFalse(any(self.app.opts[k].get() for k in
                             ("violence", "graphic", "gore", "disturbing")))
        self.assertEqual(count.cget("text"), "0 of 4 ticked")

    def test_kissing_menus_follow_the_section_box(self):
        master, count, tick_all, show = self.heads["Romance and relationships"]
        self.app.opts["kiss_os"].set("Keep")
        tick_all()
        o = self.app._current_opts()
        self.assertEqual((o["kiss_os"], o["kiss_ss"]), ("all", "all"))
        tick_all()
        o = self.app._current_opts()
        self.assertEqual((o["kiss_os"], o["kiss_ss"]), ("off", "off"))
        self.app.opts["kiss_os"].set("Cut passionate kisses")    # a menu counts as ticked
        self.assertEqual(count.cget("text"), "1 of 5 ticked")

    def test_folds_and_remembers(self):
        show = self.heads["Attitude"][3]
        show(True)
        self.assertIn("Attitude", self.app._open_sections)
        self.app._save_settings()
        self.assertIn("Attitude", self.app._load_settings()["open_sections"])
        show(False)
        self.assertNotIn("Attitude", self.app._open_sections)

    def test_changing_age_updates_the_counts(self):
        self.app.profile_var.set("adults")
        self.app._profile_changed()
        self.assertEqual(self.heads["Medical"][1].cget("text"), "0 of 2 ticked")
        self.app.profile_var.set("young")
        self.app._profile_changed()
        self.assertEqual(self.heads["Medical"][1].cget("text"), "2 of 2 ticked")


if __name__ == "__main__":
    unittest.main()
