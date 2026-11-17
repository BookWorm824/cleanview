"""Videos dragged onto the window (1.18.115; the owner, 2026-11-16: "can you add drag and drop
option", "drag and drop a movie file in"). The drop is sent the way File Explorer sends it
(WM_DROPFILES with the paths), to the window's inside and to its frame."""
import os
import tempfile
import time
import tkinter as tk
import unittest
from pathlib import Path

import support  # noqa: F401  (must come first)
import test_ui
import cvdrop

ui = test_ui.ui


def make(root, *names):
    out = []
    for n in names:
        p = Path(root, n)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x")
        out.append(str(p))
    return out


class WhichVideos(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def names(self, paths):
        return [os.path.relpath(p, self.root).replace("\\", "/") for p in paths]

    def test_a_season_folder_in_episode_order(self):
        make(self.root, "Show/Ep 10.mkv", "Show/Ep 2.mkv", "Show/Ep 1.MP4", "Show/notes.txt",
             "Show/Ep 2.srt", "Show/Clean/Ep 1 (Clean).mp4", "Show/Clean/Reports/r.txt",
             "Show/Ep 3 (Clean).mkv", "Show/Season 2/Ep 1.m4v")
        got = ui.dropped_videos([os.path.join(self.root, "Show")])
        self.assertEqual(self.names(got), ["Show/Ep 1.MP4", "Show/Ep 2.mkv", "Show/Ep 10.mkv",
                                           "Show/Season 2/Ep 1.m4v"])

    def test_files_and_a_clean_copy_dropped_on_its_own(self):
        a, b, c, t = make(self.root, "b.mkv", "a.mp4", "Movie (Clean).mp4", "a.txt")
        self.assertEqual(self.names(ui.dropped_videos([a, b, c, t, b])),
                         ["a.mp4", "b.mkv", "Movie (Clean).mp4"])

    def test_nothing_to_clean(self):
        t, = make(self.root, "report.txt")
        self.assertEqual(ui.dropped_videos([t, os.path.join(self.root, "gone.mp4")]), [])


@unittest.skipUnless(os.name == "nt", "Windows' own drag and drop")
class OnTheWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.saved = (ui.App._check_update, ui.App._check_every_ai, ui.messagebox.showinfo)
        ui.App._check_update = lambda self, manual=False: None
        ui.App._check_every_ai = lambda self: None
        cls.said = []
        ui.messagebox.showinfo = lambda title, text, **kw: cls.said.append(text)
        try:
            cls.app = ui.App()
        except tk.TclError as ex:
            cls.put_back()
            raise unittest.SkipTest(f"no screen to draw on ({ex})")
        cls.pump(0.6)                                   # drops are taken from 0.3 s
        cls.tmp = tempfile.TemporaryDirectory()

    @classmethod
    def put_back(cls):
        ui.App._check_update, ui.App._check_every_ai, ui.messagebox.showinfo = cls.saved

    @classmethod
    def tearDownClass(cls):
        try:
            cls.app.destroy()
        except tk.TclError:
            pass
        cls.put_back()
        cls.tmp.cleanup()

    @classmethod
    def pump(cls, secs):
        end = time.monotonic() + secs
        while time.monotonic() < end:
            cls.app.update()
            time.sleep(0.01)

    def setUp(self):
        self.said.clear()
        if self.app.page_name != "setup":
            self.app.reset()
        self.app.videos = []

    def drop(self, hwnd, paths):
        self.assertTrue(cvdrop.send_drop(hwnd, paths))
        self.pump(0.5)

    def test_both_parts_of_the_window_take_drops(self):
        self.assertEqual(len(cvdrop.window_handles(self.app)), 2)

    def test_a_movie_dropped_inside_is_chosen(self):
        movie, = make(self.tmp.name, "Inside/Forest Gump.mp4")
        self.app._go_step(3)
        self.drop(self.app.winfo_id(), [movie])
        self.assertEqual(self.app.videos, [movie])
        self.assertEqual(self.app._setup_step, 1)              # shown where it's chosen
        self.assertIn("Forest Gump.mp4", self.app.vid_lbl.cget("text"))
        self.assertEqual(self.said, [])

    def test_a_folder_dropped_on_the_frame(self):
        eps = make(self.tmp.name, "Frame/S1/Ep 2.mkv", "Frame/S1/Ep 1.mkv")
        self.drop(int(self.app.wm_frame(), 16), [os.path.join(self.tmp.name, "Frame")])
        self.assertEqual(self.app.videos, sorted(eps))
        self.assertIn("2 videos", self.app.vid_lbl.cget("text"))

    def test_not_a_video_says_so(self):
        t, = make(self.tmp.name, "Words/notes.txt")
        self.drop(self.app.winfo_id(), [t])
        self.assertEqual(self.app.videos, [])
        self.assertEqual(self.said, [ui.NOT_VIDEO_DROPPED])

    def test_busy_says_so_and_keeps_its_videos(self):
        movie, = make(self.tmp.name, "Busy/New.mp4")
        self.app.videos = ["old.mp4"]
        self.app.page_name = "working"
        try:
            self.drop(self.app.winfo_id(), [movie])
        finally:
            self.app.page_name = "setup"
        self.assertEqual(self.app.videos, ["old.mp4"])
        self.assertEqual(self.said, [ui.BUSY_DROPPED])

    def test_the_done_page_starts_afresh(self):
        movie, = make(self.tmp.name, "Done/Next.mkv")
        self.app.page_name = "done"
        self.drop(self.app.winfo_id(), [movie])
        self.assertEqual(self.app.page_name, "setup")
        self.assertEqual(self.app.videos, [movie])

    def test_other_messages_still_reach_the_window(self):
        self.app.title("CleanView drop test")
        self.pump(0.1)
        self.assertEqual(self.app.title(), "CleanView drop test")
        self.app.title("CleanView")
        self.app.geometry("900x700")
        self.pump(0.2)
        self.assertEqual(self.app.winfo_width(), 900)


if __name__ == "__main__":
    unittest.main()
