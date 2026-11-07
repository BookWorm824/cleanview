"""Jason, 2026-11-07: the drive filled up while saving Snow White. "One thing we should
change is being able to tell it where to save", and "estimate how many megabytes the clean
copy will take before saving... show it in the screen". The review page now says where it
saves, about how big it'll be and how much room there is ("Change..." picks the folder),
and saving asks first when it won't fit."""
import tkinter as tk
import unittest
from unittest import mock

import support
import test_ui

import cleanview as engine

ui = test_ui.ui
GB = 1024 ** 3


class Estimate(unittest.TestCase):
    def setUp(self):
        self.video = support.SANDBOX / "Snow White size.mp4"
        self.video.write_bytes(b"\0" * 1_000_000)

    def test_no_cuts_is_the_original_size(self):
        self.assertEqual(engine.clean_size(self.video, 100.0), 1_000_000)

    def test_cuts_make_it_again_at_a_set_quality(self):
        # a tiny, squeezed original: the copy made again at 1080p is far bigger
        n = engine.clean_size(self.video, 100.0, 10.0, 1920, 1080)
        self.assertAlmostEqual(n, 1920 * 1080 * 24 * 0.07 / 8 * 90, delta=10)

    def test_big_original_shrinks_with_the_cuts(self):
        big = 50 * GB          # (pretend) a Blu-ray copy, half of it cut
        with mock.patch.object(engine.os.path, "getsize", lambda p: big):
            self.assertEqual(engine.clean_size(self.video, 100.0, 50.0, 1920, 1080), big // 2)

    def test_free_space_of_a_folder_not_made_yet(self):
        self.assertGreater(engine.free_space(support.SANDBOX / "not" / "made" / "Clean"), 0)

    def test_sizes_said_plainly(self):
        self.assertEqual(ui.fmt_bytes(int(2.25 * GB)), "2.2 GB")
        self.assertEqual(ui.fmt_bytes(650 * 1024 ** 2), "650 MB")


class OnTheReviewPage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.saved = (ui.App._check_update, ui.App._check_every_ai)
        ui.App._check_update = lambda self, manual=False: None
        ui.App._check_every_ai = lambda self: None
        support.write_review()
        try:
            cls.app = ui.App()
        except tk.TclError as ex:
            ui.App._check_update, ui.App._check_every_ai = cls.saved
            raise unittest.SkipTest(f"no screen to draw on ({ex})")

    @classmethod
    def tearDownClass(cls):
        try:
            cls.app.destroy()
        except tk.TclError:
            pass
        ui.App._check_update, ui.App._check_every_ai = cls.saved

    def setUp(self):
        support.write_review()
        self.assertTrue(self.app._resume())
        self.app.update()

    def test_says_where_and_how_much(self):
        text = self.app.space_lbl.cget("text")
        self.assertIn("Saves to", text)
        self.assertIn("free there", text)

    def test_change_picks_the_folder(self):
        new = str(support.SANDBOX / "Other drive")
        with mock.patch.object(ui.filedialog, "askdirectory", lambda **k: new):
            self.app._change_save_folder()
        self.assertEqual(self.app.outdir, new)
        self.assertIn("Other drive", self.app.space_lbl.cget("text"))

    def ask(self, answer, free=1 * 1024 ** 2, picked=""):
        asked = []
        with mock.patch.object(ui.engine, "free_space",
                               lambda f: 500 * GB if "Big drive" in str(f) else free), \
                mock.patch.object(self.app, "_clean_bytes", lambda: 3 * GB), \
                mock.patch.object(ui, "chime", lambda: None), \
                mock.patch.object(ui.filedialog, "askdirectory", lambda **k: picked), \
                mock.patch.object(ui.messagebox, "askyesnocancel",
                                  lambda t, m, **k: asked.append(m) or answer):
            ok = self.app._room_to_save()
        return ok, asked

    def test_enough_room_doesnt_ask(self):
        ok, asked = self.ask(None, free=900 * GB)
        self.assertTrue(ok)
        self.assertEqual(asked, [])

    def test_not_enough_room_asks(self):
        ok, asked = self.ask(None)
        self.assertFalse(ok)                          # Cancel: back to the review
        self.assertIn("needs about 3.0 GB", asked[0])

    def test_save_there_anyway(self):
        ok, _ = self.ask(False)
        self.assertTrue(ok)

    def test_choose_another_drive(self):
        ok, asked = self.ask(True, picked=str(support.SANDBOX / "Big drive"))
        self.assertTrue(ok)
        self.assertEqual(len(asked), 1)               # the new place has room: no more asking
        self.assertIn("Big drive", self.app.outdir)


if __name__ == "__main__":
    unittest.main()
