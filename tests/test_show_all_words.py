"""A "Show all words" tick above the words to mute (1.18.115; the owner, 2026-11-16: "if you have
several words its a lot of back and forth. can you put a show all tick above the main section of
works to cut that will show all the word in the box. but also leaving the individual ones
too")."""
import copy
import time
import tkinter as tk
import unittest
from tkinter import ttk

import support
from test_ui import ui


def every(w, kind, out=None):
    out = [] if out is None else out
    if isinstance(w, kind):
        out.append(w)
    for c in w.winfo_children():
        every(c, kind, out)
    return out


class ShowAllWords(unittest.TestCase):
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

    def settle(self, secs=0.2):
        end = time.time() + secs
        while time.time() < end:
            self.app.update()
            time.sleep(0.02)

    def open_review(self, words=3):
        app = self.app
        st = support.sample_review()
        first = st["mutes"][0]
        st["mutes"] = []
        for i, (shown, raw) in enumerate([("d**n", "darn"), ("h**l", "hell"),
                                          ("cr*p", "crap")][:words]):
            m = copy.deepcopy(first)
            m.update(s=14.2 + i * 10, e=14.5 + i * 10, word=shown, raw=raw)
            m.pop("claude", None)
            st["mutes"].append(m)
        app.jobs = [{"video": st["path"], "work": support.write_review(), "analysis": st,
                     "error": None, "cuts": [], "lines": [], "words": []}]
        app.videos = [st["path"]]
        app.chat_history, app.chat_sessions = [], {}
        app.show_review()
        self.settle()

    def boxes(self):
        return [b for b in every(self.app, ttk.Checkbutton) if b.cget("text") == "Show all words"]

    def links(self):
        return [w for w in every(self.app, tk.Label) if w.cget("text") in ("Show", "Hide")]

    def words(self):
        out = []
        for t in every(self.app, tk.Text):
            r = t.tag_ranges("w")
            if r:
                out.append(t.get(r[0], r[1]).strip())
        return out

    def setUp(self):
        self.app.show_all_words = False

    def test_ticked_shows_every_word_and_each_still_works(self):
        self.open_review()
        box, = self.boxes()
        self.assertEqual(self.words(), ["d**n", "h**l", "cr*p"])
        box.invoke()
        self.settle()
        self.assertEqual(self.words(), ["darn", "hell", "crap"])
        self.assertEqual([w.cget("text") for w in self.links()], ["Hide"] * 3)
        first = self.links()[0]                       # one on its own, as before
        first.event_generate("<Button-1>")
        self.settle()
        self.assertEqual(self.words(), ["d**n", "hell", "crap"])
        self.assertEqual(first.cget("text"), "Show")
        box.invoke()                                  # unticked: all hidden again
        self.settle()
        self.assertEqual(self.words(), ["d**n", "h**l", "cr*p"])
        self.assertEqual([w.cget("text") for w in self.links()], ["Show"] * 3)

    def test_still_on_when_the_page_is_built_again(self):
        self.open_review()
        self.boxes()[0].invoke()
        self.app.show_review()                        # e.g. after a change from the chat
        self.settle()
        self.assertEqual(self.words(), ["darn", "hell", "crap"])

    def test_not_there_for_one_word(self):
        self.open_review(words=1)
        self.assertEqual(self.boxes(), [])
        self.assertEqual(self.words(), ["d**n"])


if __name__ == "__main__":
    unittest.main()
