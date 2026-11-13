"""Light and dark (1.18.78). The owner, 2026-11-13: "how hard would it be to add a dark mode",
"yes it should be optional", "i like the look. i dont like the brown around the pickup where i
left off", "just light dark button option. no windows choice". A Light / Dark button under the
steps; light stays the usual look; the choice is remembered; every page builds in dark."""
import json
import re
import tkinter as tk
import unittest

import support
import test_ui

ui = test_ui.ui
look = ui.look
SETTINGS = ui.APP_DATA / "cleanview_settings.json"
HEX = re.compile(r"#[0-9A-Fa-f]{6}$")


class Palettes(unittest.TestCase):

    def tearDown(self):
        ui.use_theme("light")

    def test_both_looks_name_the_same_colours(self):
        self.assertEqual(set(ui.LIGHT), set(ui.DARK))
        self.assertEqual(set(ui.LIGHT["PIECES"]), set(ui.DARK["PIECES"]))
        for pal in (ui.LIGHT, ui.DARK):
            for k, v in list(pal.items()) + list(pal["PIECES"].items()):
                if k != "PIECES":
                    self.assertRegex(v, HEX, k)

    def test_light_is_the_look_as_it_was(self):
        ui.use_theme("light")
        self.assertEqual((ui.BG, ui.CARD, ui.INK, ui.ACCENT), ("#F6F3EE", "#FFFFFF", "#23211F",
                                                               "#2F6F62"))
        self.assertEqual(ui.NOTE, "#FFF4EC")
        self.assertEqual(look.C["tick_off"], "#FFFFFF")

    def test_dark_sets_every_name_and_the_drawn_pieces(self):
        ui.use_theme("dark")
        self.assertEqual(ui.THEME, "dark")
        for k, v in ui.DARK.items():
            if k != "PIECES":
                self.assertEqual(getattr(ui, k), v, k)
        self.assertEqual(look.C["bg"], ui.DARK["BG"])
        self.assertEqual(look.C["card"], ui.DARK["CARD"])
        for k, v in ui.DARK["PIECES"].items():
            self.assertEqual(look.C[k], v, k)
        ui.use_theme("light")
        self.assertEqual((ui.THEME, ui.BG, look.C["bg"]), ("light", "#F6F3EE", "#F6F3EE"))

    def test_anything_else_is_light(self):
        ui.use_theme("windows")
        self.assertEqual(ui.THEME, "light")

    def test_dark_text_can_be_read(self):
        def bright(c):
            return (int(c[1:3], 16) * 299 + int(c[3:5], 16) * 587 + int(c[5:7], 16) * 114) / 1000
        d = ui.DARK
        for text in ("INK", "MUTED", "WARN", "WORD_INK", "SAY_REMOVE", "SAY_FINE", "SAY_WORD",
                     "NOTE_INK"):
            for back in ("BG", "CARD"):
                self.assertGreater(bright(d[text]) - bright(d[back]), 90, (text, back))

    def test_the_note_box_isnt_brown_in_dark(self):
        r, g = int(ui.DARK["NOTE"][1:3], 16), int(ui.DARK["NOTE"][3:5], 16)
        self.assertLess(r, g, "not a warm brown")

    def test_colours_looked_up_when_used(self):
        item = {"text": "a line", "claude": {"decision": "remove", "why": "because"}}
        self.assertEqual(ui.claude_note(item)[1], ui.LIGHT["SAY_REMOVE"])
        ui.use_theme("dark")
        self.assertEqual(ui.claude_note(item)[1], ui.DARK["SAY_REMOVE"])
        self.assertEqual(ui.claude_note({"claude": {"decision": "who knows"}})[1],
                         ui.DARK["MUTED"])

    def test_no_colour_is_written_into_a_page(self):
        src = (support.ROOT / "CleanView.pyw").read_text(encoding="utf8")
        pages = src[src.index("class App(tk.Tk):"):]
        self.assertEqual(sorted(set(re.findall(r'"#[0-9A-Fa-f]{6}"', pages))), ['"#FFFFFF"'],
                         "name it in LIGHT and DARK instead (white on green is the one left)")


class TheButton(unittest.TestCase):

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
            cls.app.reset()
            cls.app._set_theme("light")           # the next tests' windows start light
            cls.app._save_settings()
            cls.app.destroy()
        except tk.TclError:
            pass
        ui.use_theme("light")
        ui.App._check_update, ui.App._check_every_ai, ui.App._lengths = cls.real

    def setUp(self):
        self.app.reset()
        self.app._set_theme("light")
        self.app.update()

    def test_starts_light(self):
        self.assertEqual(self.app.theme, "light")
        self.assertEqual(self.app.theme_var.get(), "light")
        self.assertEqual(str(self.app.cget("bg")).upper(), ui.LIGHT["BG"])

    def test_the_button_changes_the_look_and_keeps_her_choices(self):
        app = self.app
        video = support.SANDBOX / "Episode 1.mp4"
        video.write_bytes(b"")
        app.videos = [str(video)]
        app.opts["swearing"].set(not app.opts["swearing"].get())
        swearing = app.opts["swearing"].get()
        app._go_step(2)
        app.theme_var.set("dark")
        app._set_theme(app.theme_var.get())
        app.update()
        self.assertEqual((app.theme, ui.THEME), ("dark", "dark"))
        self.assertEqual(str(app.cget("bg")).upper(), ui.DARK["BG"])
        self.assertEqual(str(app.page.cget("bg")).upper(), ui.DARK["BG"])
        self.assertEqual(app.page_name, "setup")
        self.assertEqual(app.videos, [str(video)])
        self.assertEqual(app.opts["swearing"].get(), swearing)
        self.assertEqual(app._setup_step, 2, "still on the step she was on")
        self.assertEqual(app.theme_var.get(), "dark")
        self.assertEqual(json.loads(SETTINGS.read_text())["theme"], "dark", "remembered")
        app.opts["swearing"].set(not swearing)       # back as it was
        app._set_theme("light")
        self.assertEqual(json.loads(SETTINGS.read_text())["theme"], "light")
        self.assertEqual(str(app.page.cget("bg")).upper(), ui.LIGHT["BG"])

    def test_every_page_builds_in_dark(self):
        app = self.app
        app._set_theme("dark")
        for n in (1, 2, 3, 4):
            app._go_step(n)
            app.update()
        app._section_heads["Romance and relationships"][3](True)
        app.update()
        support.write_review()
        self.assertTrue(app._resume())
        app.update()
        self.assertEqual(app.page_name, "review")
        self.assertEqual(str(app.page.cget("bg")).upper(), ui.DARK["BG"])
        jobs = app.jobs
        app.show_working("Watching and listening…", ["Episode 1.mp4", "Episode 2.mp4"],
                         can_stop=True)
        app._job_state(0, "failed") if hasattr(app, "_job_state") else None
        app.update()
        self.assertEqual(str(app.which.cget("bg")).upper(), ui.DARK["CARD"])
        app.jobs = jobs
        app.show_done([{"cut_minutes": 1.0, "mutes": 3, "cuts": 1,
                        "folder": str(support.SANDBOX), "out": str(support.SANDBOX)}],
                      keep_review=True)
        app.update()
        self.assertEqual(app.page_name, "done")


if __name__ == "__main__":
    unittest.main()
