"""The answer under a scene, line or word can be read in full (1.18.85; the owner, 2026-11-13:
"in the after report. when looking at what was found and you hit ask the box that opens on the
response is clipping off on both left and right. i cant see the full response").

The answer was wrapped at a set width. Where its box was narrower (the lines card, a narrower
window, bigger text) the words ran off both sides. It now wraps to the room the box has."""
import time
import unittest
import tkinter as tk

import support
from test_ui import ui

LONG = ("It was marked as a mild sexual innuendo. At 4:05 the woman up in the tree says branches "
        "are poking her and spotlights are shining up at her. The man's reply at 4:09 is a joke "
        "about someone looking up from below. It was caught as a sex reference because of that "
        "joke, and the line is currently muted. I changed nothing. If you think it's just a quip "
        "about her climbing the tree, tell me and I'll unmute it.")


def every(w, kind, out=None):
    out = [] if out is None else out
    if isinstance(w, kind):
        out.append(w)
    for c in w.winfo_children():
        every(c, kind, out)
    return out


class AskBox(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.real = (ui.App._check_update, ui.App._check_every_ai, ui.App._pick_review_ai,
                    ui.cc.status)
        ui.App._check_update = lambda self, manual=False: None
        ui.App._check_every_ai = lambda self: None
        ui.App._pick_review_ai = lambda self, good: "claude"
        ui.cc.status = lambda p=None: "ready"
        try:
            cls.app = ui.App()
        except tk.TclError as ex:
            cls.put_back()
            raise unittest.SkipTest(f"no screen to draw on ({ex})")
        cls.app.update()

    @classmethod
    def put_back(cls):
        (ui.App._check_update, ui.App._check_every_ai, ui.App._pick_review_ai,
         ui.cc.status) = cls.real

    @classmethod
    def tearDownClass(cls):
        try:
            cls.app._set_text_size("Normal")
            cls.app.destroy()
        except tk.TclError:
            pass
        cls.put_back()

    def settle(self, secs=0.25):
        end = time.time() + secs
        while time.time() < end:
            self.app.update()
            time.sleep(0.02)

    def open_review(self, size="Normal", width=None, answered=False):
        app = self.app
        app._set_text_size(size)
        st = support.sample_review()
        if answered:
            st["scenes"][0]["chat_answer"] = LONG
        app.jobs = [{"video": st["path"], "work": support.write_review(), "analysis": st,
                     "error": None, "cuts": [], "lines": [], "words": []}]
        app.videos = [st["path"]]
        app.chat_history, app.chat_sessions = [], {}
        app.ai_state = {"claude": "ready"}
        if width:
            app.geometry(f"{width}x{app.winfo_height()}")
        app.show_review()
        self.settle()

    def ask_everything(self):
        """Open the Ask box under every scene, line and word and put a long answer in each."""
        for link in [l for l in every(self.app, tk.Label)
                     if str(l.cget("text")) in ("Ask", "Ask AI about this…")]:
            link.event_generate("<Button-1>")
            self.app.update()
        boxes = [f for f in every(self.app, tk.Frame) if hasattr(f, "reply")]
        for box in boxes:
            box.reply.config(text="Claude: " + LONG)
            box.reply.pack(anchor="w", pady=(4, 0))
        self.settle()
        return boxes

    def fits(self, boxes, where):
        kinds = set()
        for box in boxes:
            kind = "scene" if "kind" in box.item else "line" if "text" in box.item else "word"
            kinds.add(kind)
            for label in every(box, tk.Label):
                self.assertLessEqual(label.winfo_reqwidth(), label.winfo_width() + 1,
                                     f"{where}: the {kind}'s box cuts off {label.cget('text')[:30]!r}")
                self.assertLessEqual(label.winfo_width(), box.winfo_width())
        self.assertEqual(kinds, {"scene", "line", "word"})

    def test_the_answer_fits_at_each_text_size(self):
        for size in ui.TEXT_SIZES:
            self.open_review(size)
            self.fits(self.ask_everything(), size)

    def test_in_a_narrow_window(self):
        for size in ("Normal", "Largest"):
            self.open_review(size, width=round(700 * ui.TEXT_SIZES[size]))
            self.fits(self.ask_everything(), f"narrow, {size}")

    def test_after_the_window_is_made_narrower(self):
        self.open_review("Normal")
        boxes = self.ask_everything()
        self.app.geometry(f"720x{self.app.winfo_height()}")
        self.settle(0.4)
        self.fits(boxes, "made narrower")
        self.app.geometry(f"1100x{self.app.winfo_height()}")       # and wider again: uses it
        self.settle(0.4)
        self.fits(boxes, "made wider")
        scene = next(b for b in boxes if "kind" in b.item)
        self.assertGreater(int(str(scene.reply.cget("wraplength"))), 800)

    def test_the_answer_kept_on_the_card(self):
        self.open_review("Normal", width=700, answered=True)
        kept = [l for l in every(self.app, tk.Label) if LONG[:40] in str(l.cget("text"))]
        self.assertEqual(len(kept), 1)
        self.assertLessEqual(kept[0].winfo_reqwidth(), kept[0].winfo_width() + 1)


if __name__ == "__main__":
    unittest.main()
