"""The owner, 2026-11-12: "on the save to area, when someone selects a folder to save can it be
remembered even when clean view closes and reopens". The folder chosen under "Save to" (or with
"Change..." on the review page) is kept in the settings and used again, with "Next to the video"
to go back; a folder that isn't there now (an unplugged drive) is passed over but kept."""
import json
import shutil
import tkinter as tk
import unittest
from unittest import mock

import support
import test_ui

ui = test_ui.ui
SETTINGS = ui.APP_DATA / "cleanview_settings.json"


def settings():
    try:
        return json.loads(SETTINGS.read_text())
    except Exception:
        return {}


class SaveFolder(unittest.TestCase):
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
            cls.app.use_video_folder()
            cls.app.destroy()
        except tk.TclError:
            pass
        ui.App._check_update, ui.App._check_every_ai = cls.real

    def setUp(self):
        self.folder = support.SANDBOX / "My clean movies"
        self.folder.mkdir(parents=True, exist_ok=True)
        self.app.reset()
        self.app.use_video_folder()
        self.app.update()

    def choose(self, folder):
        with mock.patch.object(ui.filedialog, "askdirectory", lambda **k: str(folder)):
            self.app.pick_out()
        self.app.update()

    def reopen(self):
        """As if CleanView closed and opened again: a fresh start from the settings file."""
        self.app._save_settings()
        self.app.save_to = "not read yet"
        self.app.videos, self.app.outdir = [], None
        self.app.show_setup()
        self.app.update()

    def test_kept_after_closing(self):
        self.choose(self.folder)
        self.assertEqual(settings().get("save_to"), str(self.folder))
        self.reopen()
        self.assertEqual(self.app.outdir, str(self.folder))
        self.assertIn("My clean movies", self.app.out_lbl.cget("text"))
        self.assertTrue(self.app.next_to_btn.winfo_ismapped())

    def test_choosing_videos_keeps_it(self):
        self.choose(self.folder)
        video = support.SANDBOX / "Episode 1.mp4"
        video.write_bytes(b"\0")
        with mock.patch.object(ui.filedialog, "askopenfilenames", lambda **k: [str(video)]), \
                mock.patch.object(ui.App, "_lengths", lambda self, v, then: None):
            self.app.pick_files()
        self.assertEqual(self.app.outdir, str(self.folder))

    def test_next_to_the_video_goes_back(self):
        self.choose(self.folder)
        self.app.use_video_folder()
        self.app.update()
        self.assertIsNone(self.app.outdir)
        self.assertIsNone(settings().get("save_to"))
        self.assertEqual(self.app.out_lbl.cget("text"), ui.NEXT_TO_VIDEO)
        self.assertFalse(self.app.next_to_btn.winfo_ismapped())
        self.reopen()
        self.assertIsNone(self.app.outdir)

    def test_a_missing_folder_is_passed_over_but_kept(self):
        gone = support.SANDBOX / "USB drive" / "Clean"
        gone.mkdir(parents=True, exist_ok=True)
        self.choose(gone)
        shutil.rmtree(gone.parent)
        self.reopen()
        self.assertIsNone(self.app.outdir)                 # next to the video this time
        self.assertEqual(settings().get("save_to"), str(gone))   # and back when it's there

    def test_other_settings_dont_lose_it(self):
        self.choose(self.folder)
        self.app._save_settings()                          # e.g. on Start or closing
        self.assertEqual(settings().get("save_to"), str(self.folder))
        self.assertIn("profiles", settings())

    def test_change_on_the_review_page_is_kept(self):
        support.write_review()
        self.assertTrue(self.app._resume())
        self.app.update()
        with mock.patch.object(ui.filedialog, "askdirectory", lambda **k: str(self.folder)):
            self.app._change_save_folder()
        self.assertEqual(settings().get("save_to"), str(self.folder))


if __name__ == "__main__":
    unittest.main()
