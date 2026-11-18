"""Reviewing the videos done while the rest are checked (1.18.132; the owner, 2026-11-18, of a
season 2 at once: "2 show they are done going through...can you make it where you can go ahead
and review them so there is less down time"), and "Jump to:" on the Found tab, as CleanListen
has ("CleanListen has a list at the top where you can jump to different sections that it
removed...can you add that to CleanView as well")."""
import copy
import json
import threading
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


def review(name):
    st = support.sample_review()
    st["path"] = str(support.SANDBOX / name)
    return st


def job(name, done=True):
    work = support.APP_DATA / "views" / name.replace(" ", "_")
    work.mkdir(parents=True, exist_ok=True)
    st = review(name) if done else None
    if st:
        (work / "analysis.json").write_text(json.dumps(st), encoding="utf8")
    return {"video": str(support.SANDBOX / name), "work": work, "analysis": st, "error": None,
            "cuts": [], "lines": [], "words": []}


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.real = (ui.App._check_update, ui.App._check_every_ai, ui.App._lengths,
                    ui.messagebox.showinfo, ui.messagebox.askyesno)
        ui.App._check_update = lambda self, manual=False: None
        ui.App._check_every_ai = lambda self: None
        ui.App._lengths = lambda self, videos, then: None
        cls.told, cls.answer = [], [False]
        ui.messagebox.showinfo = lambda t, m, **k: cls.told.append(m)
        ui.messagebox.askyesno = lambda t, m, **k: cls.told.append(m) or cls.answer[0]
        try:
            cls.app = ui.App()
        except tk.TclError as ex:
            cls.restore()
            raise unittest.SkipTest(f"no screen to draw on ({ex})")
        cls.app.update()

    @classmethod
    def restore(cls):
        (ui.App._check_update, ui.App._check_every_ai, ui.App._lengths,
         ui.messagebox.showinfo, ui.messagebox.askyesno) = cls.real

    @classmethod
    def tearDownClass(cls):
        try:
            cls.app.destroy()
        except tk.TclError:
            pass
        cls.restore()

    def settle(self, secs=0.2):
        end = time.time() + secs
        while time.time() < end:
            self.app.update()
            time.sleep(0.02)


class ReviewWhileChecking(Base):
    def setUp(self):
        app = self.app
        self.told.clear()
        self.answer[0] = False
        app.chat_history, app.chat_sessions = [], {}
        app.jobs = [job("Show_S01E09.mp4"), job("Show_S01E10.mp4"),
                    job("Show_S01E11.mp4", done=False), job("Show_S01E12.mp4", done=False)]
        app.videos = [j["video"] for j in app.jobs]
        app.run = getattr(app, "run", 0) + 1
        self.stop = threading.Event()
        app.work_thread = threading.Thread(target=self.stop.wait, daemon=True)
        app.work_thread.start()
        app._scan_run = app.run              # as _analyze_now sets it
        app.show_working("Watching and listening…", can_stop=True)
        for k, state in enumerate(("done", "done", "now", "now")):
            app._handle(("for_run", app.run, ("job", k, state)))
        app._handle(("for_run", app.run, ("jobmsg", 2, "Listening to the dialogue")))
        self.settle()

    def tearDown(self):
        self.stop.set()

    def test_the_button_on_the_progress_page(self):
        b = self.app.early_btn
        self.assertEqual(b.winfo_manager(), "pack")
        self.assertEqual(b.cget("text"), "Review the 2 done now")

    def test_review_add_and_back(self):
        app = self.app
        app.early_btn.invoke()
        self.settle()
        self.assertEqual(app.page_name, "review")
        self.assertIn("Still checking 2 more videos.", app._early_text.cget("text"))
        self.assertEqual(app._early_add.winfo_manager(), "")
        self.assertEqual(len(app._on_page), 2)

        app._save_from_review()                          # not yet: the rest are coming
        self.assertIn("2 more videos are still being checked", self.told[-1])
        self.assertEqual(app.page_name, "review")

        v, j0, m = app.word_vars[0]                      # her untick, kept when one's added
        v.set(False)
        app.jobs[2]["analysis"] = review("Show_S01E11.mp4")
        app._handle(("for_run", app.run, ("job", 2, "done")))
        self.settle()
        said = app._early_text.cget("text")
        self.assertIn("Still checking 1 more video.", said)
        self.assertIn("1 more is ready to review: Show_S01E11.", said)
        self.assertEqual(app._early_add.cget("text"), "Add it")
        self.assertEqual(app._early_add.winfo_manager(), "pack")
        app._early_add.invoke()
        self.settle()
        self.assertEqual(len(app._on_page), 3)
        self.assertFalse([v for v, j, mm in app.word_vars if j is j0][0].get())
        self.assertEqual([s[0] for s in app._jump_spots], ["S01E09", "S01E10", "S01E11"])

        app._early_prog.invoke()                          # "See progress"
        self.settle()
        self.assertEqual(app.page_name, "working")
        icons = [r[0].cget("text") for r in app.job_rows]
        self.assertEqual(icons, ["✓", "✓", "✓", "▶"])
        self.assertEqual(app.job_notes[2].cget("text"), "")
        self.assertEqual(app.early_btn.cget("text"), "Review the 3 done now")

        app.early_btn.invoke()                            # and back again, ticks as she left them
        self.settle()
        self.assertFalse([v for v, j, mm in app.word_vars if j is j0][0].get())

        app.jobs[3]["analysis"] = review("Show_S01E12.mp4")      # the last one, then all done
        app._handle(("for_run", app.run, ("job", 3, "done")))
        self.stop.set()
        app.work_thread.join()
        app._handle(("for_run", app.run, ("analyzed",)))
        self.settle()
        self.assertEqual(app.page_name, "review")         # still where she was
        self.assertIn("Every video has been checked. 1 more is ready to review",
                      app._early_text.cget("text"))
        self.assertEqual(app._early_prog.winfo_manager(), "")

        app._save_from_review()                           # saving adds it first
        self.assertIn("just finished were added", self.told[-1])
        self.assertEqual(len(app._on_page), 4)
        self.assertFalse(app._early_text.winfo_exists() if app._early_text else False)

    def test_back_to_start_asks_first(self):
        app = self.app
        app.early_btn.invoke()
        self.settle()
        run = app.run
        app._back_to_start()
        self.assertIn("Stop checking them", self.told[-1])
        self.assertEqual(app.page_name, "review")         # No: stays
        self.answer[0] = True
        app._back_to_start()
        self.assertEqual(app.run, run + 1)                # the rest stop at their next check
        self.assertFalse(app._still_scanning())
        self.assertEqual(app.page_name, "setup")

    def test_not_while_saving(self):
        app = self.app
        app._scan_run = None
        app.show_working("Saving the clean copies…", [j["video"] for j in app.jobs])
        self.assertIsNone(app.early_btn)


class JumpTo(Base):
    def open(self, jobs):
        app = self.app
        app._scan_run = None
        app.jobs, app.videos = jobs, [j["video"] for j in jobs]
        app.chat_history, app.chat_sessions = [], {}
        app.show_review()
        self.settle(0.4)

    def links(self):
        row = self.app._found_inner
        while row is not None and not isinstance(row, ttk.Notebook):
            row = row.master
        heads = [l for l in every(row, tk.Label) if l.cget("text") == "Jump to:"
                 and l.winfo_manager() and l.master.winfo_manager()]
        if not heads:
            return []
        return [l.cget("text") for l in every(heads[0].master, tk.Label) if l is not heads[0]]

    def test_one_video_jumps_to_each_part(self):
        j = job("Movie.mp4")
        st = j["analysis"]
        first = st["mutes"][0]
        st["mutes"] = []
        for i in range(25):                               # a long list of words
            m = copy.deepcopy(first)
            m.update(s=20 + i * 3, e=20.4 + i * 3)
            m.pop("claude", None)
            st["mutes"].append(m)
        self.open([j])
        app = self.app
        names = [s[0] for s in app._jump_spots]
        self.assertEqual(names, ["Scenes", "Lines", "Words"])
        self.assertEqual([s[1] for s in app._jump_spots], [2, 2, 25])
        self.assertIn("Words (25)", self.links())
        c = app._found_canvas
        c.yview_moveto(0)
        app._jump_to(app._jump_spots[2][2])
        self.settle(1.2)
        self.assertGreater(c.yview()[0], 0.05)           # moved down to the words
        app._jump_to(app._jump_spots[0][2])
        self.settle(1.2)
        self.assertLess(c.yview()[0], 0.02)               # and back up to the scenes

    def test_several_videos_jump_to_each_video(self):
        self.open([job("Show_S01E09.mp4"), job("Show 2x10.mp4")])
        self.assertEqual([s[0] for s in self.app._jump_spots], ["S01E09", "Show 2x10"])

    def test_nothing_to_jump_between(self):
        j = job("Quiet.mp4")
        j["analysis"].update(scenes=[], lines=[])
        self.open([j])
        self.assertEqual(len(self.app._jump_spots), 1)
        self.assertEqual(self.links(), [])


if __name__ == "__main__":
    unittest.main()
