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

    def shell_data(self, path):
        """File Explorer's own IDataObject for a file, the way a drag hands it over."""
        import ctypes
        from ctypes import wintypes
        _, _, ole32, GUID, *_ = cvdrop._ole()
        shell32 = ctypes.WinDLL("shell32")
        item, data = ctypes.c_void_p(), ctypes.c_void_p()
        iid_item = cvdrop._guid(GUID, "43826d1e-e718-42ee-bc55-a1e261c37bfe")
        self.assertEqual(shell32.SHCreateItemFromParsingName(
            ctypes.c_wchar_p(path), None, ctypes.byref(iid_item), ctypes.byref(item)), 0)
        vtbl = ctypes.cast(item, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]
        bind = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_void_p,
                                  ctypes.POINTER(GUID), ctypes.POINTER(GUID),
                                  ctypes.POINTER(ctypes.c_void_p))(vtbl[3])
        bhid = cvdrop._guid(GUID, "B8C0BD9F-ED24-455c-83E6-D5390C4FE8C4")
        iid_data = cvdrop._guid(GUID, "0000010e-0000-0000-C000-000000000046")
        self.assertEqual(bind(item, None, ctypes.byref(bhid), ctypes.byref(iid_data),
                              ctypes.byref(data)), 0)
        return data.value

    def call_target(self, index, *args):
        """Call the registered IDropTarget's method number index, as Windows does."""
        import ctypes
        from ctypes import wintypes
        target = cvdrop._kept[-1] if isinstance(cvdrop._kept[-1], cvdrop.DropTarget) else             next(t for t in reversed(cvdrop._kept) if isinstance(t, cvdrop.DropTarget))
        vtbl = ctypes.cast(ctypes.c_void_p(target.pointer),
                           ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]
        effect = wintypes.DWORD(99)
        if index in (3, 6):          # DragEnter, Drop: (data, keys, point, effect)
            fn = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_void_p,
                                    wintypes.DWORD, ctypes.c_uint64,
                                    ctypes.POINTER(wintypes.DWORD))(vtbl[index])
            self.assertEqual(fn(target.pointer, args[0], 0, 0, ctypes.byref(effect)), 0)
        return effect.value

    def test_a_drag_from_file_explorer(self):
        # registered on the window's inside, which holds every widget: Windows looks for it up
        # from the widget under the mouse (WM_DROPFILES alone didn't reach it: "the drag and
        # drop doesnt work")
        self.assertIn(self.app.winfo_id(), cvdrop.OLE_REGISTERED)
        movie, = make(self.tmp.name, "Explorer/Black Beauty.mkv")
        data = self.shell_data(movie)
        self.assertEqual(self.call_target(3, data), cvdrop.DROPEFFECT_COPY)   # the copy cursor
        self.assertEqual(self.call_target(6, data), cvdrop.DROPEFFECT_COPY)   # dropped
        self.pump(0.5)
        self.assertEqual([os.path.normcase(v) for v in self.app.videos],
                         [os.path.normcase(movie)])

    def test_a_folder_dragged_from_file_explorer(self):
        eps = make(self.tmp.name, "Season/Ep 2.mkv", "Season/Ep 1.mkv")
        self.call_target(6, self.shell_data(os.path.join(self.tmp.name, "Season")))
        self.pump(0.5)
        self.assertEqual([os.path.normcase(v) for v in self.app.videos],
                         sorted(os.path.normcase(e) for e in eps))

    def leave_target(self):
        """IDropTarget::DragLeave (method 5), as Windows calls it."""
        import ctypes
        target = next(t for t in reversed(cvdrop._kept) if isinstance(t, cvdrop.DropTarget))
        vtbl = ctypes.cast(ctypes.c_void_p(target.pointer),
                           ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]
        fn = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p)(vtbl[5])
        self.assertEqual(fn(target.pointer), 0)

    def test_lit_up_while_held_over(self):
        # 1.18.134 (the owner: "their should be a visual that it is ready to drop. maybe
        # highlight a border around the big oval that has the file picker")
        app = self.app
        app._go_step(3)                                  # elsewhere on the start page
        movie, = make(self.tmp.name, "Held/Over.mkv")
        data = self.shell_data(movie)
        self.assertEqual(self.call_target(3, data), cvdrop.DROPEFFECT_COPY)   # held over
        self.pump(0.4)
        self.assertEqual(app._setup_step, 1)             # the card can be seen
        self.assertEqual(app.drop_card.edge, ui.ACCENT)
        self.assertEqual(app.drop_card.edge_w, ui.DROP_EDGE)
        self.assertEqual(app.drop_tip.cget("text"), ui.DROP_READY)
        self.leave_target()                               # dragged away again
        self.pump(0.5)
        self.assertEqual(app.drop_card.edge, ui.SOFT_EDGE)
        self.assertEqual(app.drop_tip.cget("text"), ui.DROP_TIP)
        self.assertEqual(app.videos, [])

    def test_light_goes_off_when_dropped(self):
        app = self.app
        movie, = make(self.tmp.name, "Held/Dropped.mkv")
        data = self.shell_data(movie)
        self.call_target(3, data)
        self.call_target(6, data)
        self.pump(0.6)
        self.assertEqual(app.drop_card.edge, ui.SOFT_EDGE)
        self.assertEqual([os.path.normcase(v) for v in app.videos], [os.path.normcase(movie)])

    def test_a_quick_leave_and_enter_doesnt_flicker(self):
        app = self.app
        app._drag_over(True)
        app._drag_over(False)                             # moving between the window's parts
        app._drag_over(True)
        self.pump(0.4)
        self.assertEqual(app.drop_card.edge, ui.ACCENT)
        app._drag_over(False)
        self.pump(0.4)
        self.assertEqual(app.drop_card.edge, ui.SOFT_EDGE)

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
