"""Preview opens one player (1.18.91; the owner, 2026-11-13: "when the after report comes up,
and you want to preview a potential scene and hit preview, it can take a few second to open the
player, so if you think it not opening you can click preview again and it opens a 2nd player.
it should only open one").

While a preview is being made and for a few seconds after it's handed to the player, the
button says "Opening…" and pressing Preview again (that one or another) does nothing."""
import time
import unittest
import tkinter as tk
from tkinter import ttk

import support
from test_ui import ui
from test_ask_box import every


class OnePreview(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.real = (ui.App._check_update, ui.App._check_every_ai, ui.App._pick_review_ai,
                    ui.cc.status, ui.open_path, ui.engine.make_preview, ui.PREVIEW_OPENING_SECS)
        ui.App._check_update = lambda self, manual=False: None
        ui.App._check_every_ai = lambda self: None
        ui.App._pick_review_ai = lambda self, good: "claude"
        ui.cc.status = lambda p=None: "ready"
        cls.opened, cls.made = [], []

        def make(path, s, e, work):
            cls.made.append((s, e))
            time.sleep(0.4)                     # making the clip takes a moment
            if cls.fail:
                raise RuntimeError("Couldn't make the preview:\nmade-up ffmpeg error")
            return f"preview_{int(s)}_{int(e)}.mkv"
        cls.fail = False
        ui.open_path = cls.opened.append
        ui.engine.make_preview = make
        ui.PREVIEW_OPENING_SECS = 1
        try:
            cls.app = ui.App()
        except tk.TclError as ex:
            cls.put_back()
            raise unittest.SkipTest(f"no screen to draw on ({ex})")
        cls.app.update()

    @classmethod
    def put_back(cls):
        (ui.App._check_update, ui.App._check_every_ai, ui.App._pick_review_ai,
         ui.cc.status, ui.open_path, ui.engine.make_preview, ui.PREVIEW_OPENING_SECS) = cls.real

    @classmethod
    def tearDownClass(cls):
        try:
            cls.app.destroy()
        except tk.TclError:
            pass
        cls.put_back()

    def setUp(self):
        self.opened.clear()
        self.made.clear()
        type(self).fail = False
        support.BOXES_SHOWN.clear()
        app = self.app
        app._previewing = False
        st = support.sample_review()
        app.jobs = [{"video": st["path"], "work": support.write_review(), "analysis": st,
                     "error": None, "cuts": [], "lines": [], "words": []}]
        app.videos = [st["path"]]
        app.chat_history, app.chat_sessions = [], {}
        app.ai_state = {"claude": "ready"}
        app.show_review()
        self.settle()

    def settle(self, secs=0.25):
        end = time.time() + secs
        while time.time() < end:
            self.app.update()
            time.sleep(0.02)

    def buttons(self):
        return [b for b in every(self.app, ttk.Button)
                if b.cget("text") in ("Preview ▸", "Opening…")]

    def test_pressed_twice_one_player(self):
        first, second = self.buttons()[:2]          # the review has two scenes
        first.invoke()
        self.settle(0.1)
        self.assertEqual(first.cget("text"), "Opening…")
        first.invoke()                               # "is it opening?"
        second.invoke()                              # another scene meanwhile
        self.settle(0.8)
        self.assertEqual(len(self.made), 1)
        self.assertEqual(len(self.opened), 1)
        first.invoke()                               # still opening in the player
        self.settle(0.2)
        self.assertEqual(len(self.opened), 1)
        self.settle(1.2)                             # the player has had its time
        self.assertEqual(first.cget("text"), "Preview ▸")
        first.invoke()                               # to watch it again
        self.settle(0.8)
        self.assertEqual(len(self.opened), 2)

    def test_a_preview_that_fails_says_so_and_can_be_pressed_again(self):
        type(self).fail = True
        first = self.buttons()[0]
        first.invoke()
        self.settle(0.8)
        self.assertEqual(self.opened, [])
        self.assertTrue(any(k == "showerror" for k, _ in support.BOXES_SHOWN))
        self.assertEqual(first.cget("text"), "Preview ▸")
        type(self).fail = False
        first.invoke()
        self.settle(0.8)
        self.assertEqual(len(self.opened), 1)

    def test_the_page_built_again_meanwhile(self):
        self.buttons()[0].invoke()
        self.app.show_review()                       # e.g. the chat changed something
        self.settle(3.0)
        self.assertEqual(len(self.opened), 1)        # no error from the old button
        self.assertFalse(self.app._previewing)
        self.assertTrue(all(b.cget("text") == "Preview ▸" for b in self.buttons()))


if __name__ == "__main__":
    unittest.main()
