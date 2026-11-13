"""The start page's filters in sections by topic, each with a box that ticks or unticks all of
it and folds away to one line (1.18.74; the owner: "a main box for each category to tick all if
wanted, but if only some of the subcategories are wanted just those can be ticked. vid angel had
a system like that", "maybe not as long", and Medical its own section).

Since 1.18.77 (the owner: "the ui also feels clunky and dated, can you make it feel classy",
then "B, step by step") each section is a tile with a switch for all of it (on, off, or pale
for some), "N of M on" and "Choose"; its boxes open under the tiles, one section at a time. The
start page shows one step at a time, with the four steps listed down the left."""
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
        self.assertEqual(count.cget("text"), "1 of 2 on")
        self.assertEqual(master.state, "some")

    def test_tick_all_then_untick_all(self):
        master, count, tick_all, show = self.heads["Violence"]
        self.app.opts["gore"].set(False)
        tick_all()                                  # some ticked: all
        self.assertTrue(all(self.app.opts[k].get() for k in
                            ("violence", "graphic", "gore", "disturbing")))
        self.assertEqual(master.state, "on")
        tick_all()                                  # all ticked: none
        self.assertFalse(any(self.app.opts[k].get() for k in
                             ("violence", "graphic", "gore", "disturbing")))
        self.assertEqual(count.cget("text"), "Off")
        self.assertEqual(master.state, "off")
        master.click()                              # the switch itself does the same
        self.assertTrue(all(self.app.opts[k].get() for k in
                            ("violence", "graphic", "gore", "disturbing")))

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
        self.assertEqual(count.cget("text"), "1 of 5 on")

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
        self.assertEqual(self.heads["Medical"][1].cget("text"), "Off")
        self.app.profile_var.set("young")
        self.app._profile_changed()
        self.assertEqual(self.heads["Medical"][1].cget("text"), "2 of 2 on")

    def test_boxes_open_right_under_their_own_row_of_tiles(self):
        # (the owner, 2026-11-13: they opened below all nine; "id like each one to open right
        # below its chosen option")
        detail = self.app._section_detail
        self.app._go_step(2)                        # the step the tiles are on
        for title in ("Bad language", "Romance and relationships", "Violence", "Attitude",
                      "Music"):
            row = SECTIONS.index(title) // 3
            self.heads[title][3](True)
            self.app.update()
            self.assertEqual(int(detail.grid_info()["row"]), 2 * row + 1, title)
            self.assertEqual(int(detail.grid_info()["columnspan"]), 3)
            self.assertTrue(detail.winfo_ismapped())
        self.heads["Music"][3](False)
        self.assertEqual(detail.grid_info(), {})

    def test_one_section_open_at_a_time(self):
        self.heads["Attitude"][3](True)
        self.heads["Violence"][3](True)
        self.assertEqual(self.app._open_sections, {"Violence"})
        self.heads["Violence"][3](False)
        self.assertEqual(self.app._open_sections, set())


class Steps(unittest.TestCase):
    """One step at a time, the four listed down the left with what's chosen in each."""

    @classmethod
    def setUpClass(cls):
        cls.real = (ui.App._check_update, ui.App._check_every_ai, ui.App._lengths)
        ui.App._check_update = lambda self, manual=False: None
        ui.App._check_every_ai = lambda self: None
        ui.App._lengths = lambda self, videos, then: None
        try:
            cls.app = ui.App()
        except tk.TclError as ex:
            ui.App._check_update, ui.App._check_every_ai, ui.App._lengths = cls.real
            raise unittest.SkipTest(f"no screen to draw on ({ex})")
        cls.app.update()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.app.destroy()
        except tk.TclError:
            pass
        ui.App._check_update, ui.App._check_every_ai, ui.App._lengths = cls.real

    def setUp(self):
        self.app.reset()
        self.app.update()

    def shown(self):
        return [i for i, p in enumerate(self.app._panes, 1) if p.winfo_manager()]

    def test_starts_on_step_one_and_shows_only_that(self):
        self.assertEqual(self.shown(), [1])
        self.assertEqual(self.app._step_title.cget("text"), "Movie or episodes")
        self.assertEqual(self.app._step_tag.cget("text"), "STEP 1 OF 4")
        self.assertFalse(self.app.back_btn.winfo_manager(), "nothing to go back to")
        self.assertEqual(self.app.next_btn.cget("text"), "Next: What to remove")

    def test_next_and_back(self):
        self.app.next_btn.invoke()
        self.assertEqual(self.shown(), [2])
        self.app.next_btn.invoke()
        self.app.next_btn.invoke()
        self.assertEqual(self.shown(), [4])
        self.assertFalse(self.app.next_btn.winfo_manager(), "the last step")
        self.assertTrue(self.app.start_btn.winfo_manager(), "Start cleaning on every step")
        self.app.back_btn.invoke()
        self.assertEqual(self.shown(), [3])

    def test_every_setting_is_there_whichever_step_shows(self):
        for k in list(ui.FILTER_KEYS) + ["ai", "reader", "look"]:
            self.assertIn(k, self.app.opts, k)
        self.assertIn("swearing", self.app._current_opts())

    def test_subtitles_are_always_looked_for(self):
        # (the owner, 2026-11-13: "that part says look for subtitles with a choice. i think
        # subtitles are important enough that they should be standard")
        import json
        app = self.app
        self.assertNotIn("autosubs", app.opts)                  # no switch for it any more
        self.assertIs(app._current_opts()["autosubs"], True)
        settings = app._load_settings()
        settings["autosubs"] = False                            # turned off in an older version
        (support.APP_DATA / "cleanview_settings.json").write_text(json.dumps(settings))
        app.show_setup()
        app.update()
        self.assertIs(app._current_opts()["autosubs"], True)
        app._save_settings()
        self.assertIs(app._load_settings()["autosubs"], True)

        def texts(w):
            out = [str(w.cget("text"))] if isinstance(w, tk.Label) else []
            for c in w.winfo_children():
                out += texts(c)
            return out
        said = " ".join(texts(app))
        self.assertNotIn("Find subtitles online for videos that don't have any", said)
        self.assertIn("ones found online when it has none", said)

    def test_the_list_says_what_is_chosen(self):
        app = self.app
        said = lambda n: app._step_rows[n - 1][3].cget("text")     # noqa: E731
        self.assertEqual(said(1), "Nothing chosen yet")
        video = support.SANDBOX / "Episode 1.mp4"
        video.write_bytes(b"")
        app.videos = [str(video), str(video)]
        app._refresh_labels()
        self.assertEqual(said(1), "2 videos chosen")
        app.profile_var.set("teens")
        app._profile_changed()
        self.assertEqual(said(2), "Teens")
        app.opts["reader"].set("claude")
        self.assertEqual(said(3), "Claude")
        app.opts["reader"].set("local")
        self.assertEqual(said(3), "This PC")
        app.opts["ai"].set(False)
        self.assertEqual(said(3), "Off")
        app.opts["ai"].set(True)
        self.assertEqual(said(4), "Next to the videos")
        app.profile_var.set("young")
        app._profile_changed()

    def test_start_without_videos_goes_to_step_one(self):
        said, saved = [], ui.messagebox.showinfo
        ui.messagebox.showinfo = lambda t, m, **k: said.append(m)
        try:
            self.app._go_step(3)
            self.app.start()
        finally:
            ui.messagebox.showinfo = saved
        self.assertIn("Choose files", said[-1])
        self.assertEqual(self.shown(), [1])
        self.assertEqual(self.app.page_name, "setup")

    def test_start_with_a_video_that_has_gone(self):
        # (the code check, 2026-11-13: it did nothing at all, with no message)
        said, saved = [], ui.messagebox.showinfo
        ui.messagebox.showinfo = lambda t, m, **k: said.append(m)
        try:
            self.app.videos = [str(support.SANDBOX / "unplugged drive" / "Episode 3.mp4")]
            self.app.start()
        finally:
            ui.messagebox.showinfo = saved
            self.app.videos = []
        self.assertIn("Can't find Episode 3.mp4", said[-1])
        self.assertEqual(self.app.page_name, "setup")

    def test_a_click_is_a_press_and_a_let_go_on_the_button(self):
        # (the code check: letting go alone counted, so the second click of a double-click
        # in the file box could press whatever was under it)
        app, went = self.app, []
        btn = app.next_btn
        saved, btn._command = btn._command, lambda: went.append(1)
        try:
            app.update()
            btn.event_generate("<ButtonRelease-1>", x=5, y=5)
            self.assertEqual(went, [], "let go without a press")
            btn.event_generate("<ButtonPress-1>", x=5, y=5)
            btn.event_generate("<ButtonRelease-1>", x=5, y=5)
            self.assertEqual(went, [1])
            btn.event_generate("<ButtonPress-1>", x=5, y=5)
            btn.event_generate("<ButtonRelease-1>", x=-40, y=-40)
            self.assertEqual(went, [1], "slid off before letting go")
        finally:
            btn._command = saved


if __name__ == "__main__":
    unittest.main()
