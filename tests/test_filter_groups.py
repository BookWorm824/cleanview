"""The review page is grouped by filter, each with "Tick all" and "Untick all", as CleanListen has
(1.18.144; the owner, 2026-11-19: "can we organize the filters more like CleanListen? its real
easy to select or unselect all, soreted by filters", "I accidently had a filter on that I didn't
mean too....now I have to unselect 190 filters by hand")."""
import copy
import time
import tkinter as tk
import unittest

import support
from test_ui import ui


def every(w, kind, out=None):
    out = [] if out is None else out
    if isinstance(w, kind):
        out.append(w)
    for c in w.winfo_children():
        every(c, kind, out)
    return out


class FilterGroups(unittest.TestCase):
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

    def review(self, name="Movie.mp4"):
        st = support.sample_review()
        st["path"] = st["path"].replace("sample", name.split(".")[0]) if "sample" in st["path"] \
            else st["path"]
        first = st["mutes"][0]
        st["mutes"] = []
        for i, cat in enumerate(["deity", "mild", "deity", "deity", "mild", "strong"]):
            m = copy.deepcopy(first)
            m.update(s=10.0 + i * 5, e=10.3 + i * 5, cat=cat, word=f"w{i}", raw=f"w{i}")
            m.pop("claude", None)
            m.pop("keep", None)
            st["mutes"].append(m)
        line = st["lines"][0]
        st["lines"] = []
        for i, types in enumerate([["sexref"], ["crude"], ["sexref"]]):
            l = copy.deepcopy(line)
            l.update(s=100.0 + i * 5, e=102.0 + i * 5, types=types, mute=True, text=f"line {i}")
            l.pop("claude", None)
            st["lines"].append(l)
        for sc in st["scenes"]:
            sc.pop("claude", None)
            sc["cut"] = True
        st["scenes"].append(dict(copy.deepcopy(st["scenes"][0]), id=3, s=80.0, e=84.0))
        return st

    def open(self, sts):
        app = self.app
        app.jobs = [{"video": st["path"], "work": support.write_review(), "analysis": st,
                     "error": None, "cuts": [], "lines": [], "words": []} for st in sts]
        app.videos = [st["path"] for st in sts]
        app.chat_history, app.chat_sessions = [], {}
        app.show_review()
        self.settle()

    def heads(self):
        return [w.cget("text") for w in every(self.app, tk.Label)
                if "  (" in w.cget("text") and w.cget("font")]

    def click(self, title, which):
        """Press "Tick all"/"Untick all" beside the heading `title`."""
        head = next(w for w in every(self.app, tk.Label) if w.cget("text") == title).master
        link = next(w for w in every(head, tk.Label) if w.cget("text") == which)
        link.event_generate("<ButtonPress-1>", x=2, y=2)
        link.event_generate("<ButtonRelease-1>", x=2, y=2)
        self.settle(0.05)

    def ticks(self, vars_, kind):
        return [(item.get("cat") or item.get("types") or item.get("kind"), v.get())
                for v, _, item in vars_]

    def test_words_grouped_with_their_own_ticks(self):
        self.open([self.review()])
        heads = self.heads()
        for h in ("Words to mute  (6)", "Swearing  (1)", "Mild words  (2)", "God's name  (3)",
                  "Lines to mute  (3)", "Sexual reference  (2)", "Crude humor  (1)",
                  "Violence  (2)", "Kiss  (1)"):
            self.assertIn(h, heads)
        # in the order of the start page's word groups
        self.assertLess(heads.index("Swearing  (1)"), heads.index("Mild words  (2)"))
        self.assertLess(heads.index("Mild words  (2)"), heads.index("God's name  (3)"))
        self.click("God's name  (3)", "Untick all")
        got = {(m["cat"], v.get()) for v, _, m in self.app.word_vars}
        self.assertEqual(got, {("deity", False), ("mild", True), ("strong", True)})
        self.click("God's name  (3)", "Tick all")
        self.assertTrue(all(v.get() for v, _, _ in self.app.word_vars))

    def test_a_whole_card(self):
        self.open([self.review()])
        self.click("Words to mute  (6)", "Untick all")
        self.assertFalse(any(v.get() for v, _, _ in self.app.word_vars))
        self.assertTrue(all(v.get() for v, _, _ in self.app.line_vars))
        self.click("Lines to mute  (3)", "Untick all")
        self.assertFalse(any(v.get() for v, _, _ in self.app.line_vars))

    def test_lines_and_scenes(self):
        self.open([self.review()])
        self.click("Sexual reference  (2)", "Untick all")
        self.assertEqual([v.get() for v, _, l in self.app.line_vars if l["types"] == ["crude"]],
                         [True])
        self.assertFalse(any(v.get() for v, _, l in self.app.line_vars
                             if l["types"] == ["sexref"]))
        self.click("Violence  (2)", "Untick all")
        self.assertEqual(sorted((sc["kind"][0], v.get()) for v, _, sc in self.app.scene_vars),
                         [("Kiss", True), ("Violence", False), ("Violence", False)])

    def test_headings_in_dark(self):
        # 1.18.151, the owner: "the white bar is hard to read", "all the bars are like that":
        # each heading had Light's white card behind Dark's pale text
        try:
            ui.use_theme("dark")
            self.open([self.review()])
            for title in ("Swearing  (1)", "God's name  (3)", "Sexual reference  (2)"):
                label = next(w for w in every(self.app, tk.Label) if w.cget("text") == title)
                self.assertEqual(label.cget("bg"), ui.CARD, title)
                self.assertEqual(label.master.cget("bg"), ui.CARD, title)
                for link in every(label.master, tk.Label):
                    self.assertNotEqual(link.cget("bg"), ui.LIGHT["CARD"], title)
        finally:
            ui.use_theme("light")

    def test_what_is_unticked_is_what_is_saved(self):
        self.open([self.review()])
        self.click("God's name  (3)", "Untick all")
        app = self.app
        j = app.jobs[0]
        j["words"] = [m for v, jj, m in app.word_vars if v.get() and jj is j]
        self.assertEqual(sorted(m["cat"] for m in j["words"]), ["mild", "mild", "strong"])

    def test_every_video_at_once(self):
        a, b = self.review(), self.review()
        b["path"] = b["path"].replace(".mp4", " 2.mp4").replace(".mkv", " 2.mkv")
        self.open([a, b])
        self.assertIn("Every video, by filter:", [w.cget("text") for w in every(self.app, tk.Label)])
        self.click("God's name  (6)", "Untick all")
        got = {(m["cat"], v.get()) for v, _, m in self.app.word_vars}
        self.assertEqual(got, {("deity", False), ("mild", True), ("strong", True)})
        self.assertEqual(sum(1 for v, _, m in self.app.word_vars if m["cat"] == "deity"), 6)

    def test_no_every_video_row_for_one(self):
        self.open([self.review()])
        self.assertNotIn("Every video, by filter:",
                         [w.cget("text") for w in every(self.app, tk.Label)])


if __name__ == "__main__":
    unittest.main()
