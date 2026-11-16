"""Updates install by themselves when it's safe (1.18.114; the owner, 2026-11-16: "should we have
it auto update instead of relying on some to hit check for updates and then hit update. they
might miss it", then "lets try that. we can alway go back")."""
import time
import tkinter as tk
import unittest

import support  # noqa: F401  (must come first)
import test_ui

ui = test_ui.ui


class UpdatesByItself(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.saved = (ui.App._check_update, ui.App._check_every_ai, ui.AUTO_UPDATE_RETRY)
        ui.App._check_update = lambda self, manual=False: None
        ui.App._check_every_ai = lambda self: None
        ui.AUTO_UPDATE_RETRY = 0.05                     # a retry every 50 ms here, not a minute
        try:
            cls.app = ui.App()
        except tk.TclError as ex:
            cls.put_back()
            raise unittest.SkipTest(f"no screen to draw on ({ex})")
        cls.app.update()

    @classmethod
    def put_back(cls):
        ui.App._check_update, ui.App._check_every_ai, ui.AUTO_UPDATE_RETRY = cls.saved

    @classmethod
    def tearDownClass(cls):
        try:
            cls.app.destroy()
        except tk.TclError:
            pass
        cls.put_back()

    def setUp(self):
        app = self.app
        self.updated = []
        app.update_now = lambda: self.updated.append(app.page_name)
        if getattr(app, "_auto_wait_id", None):
            app.after_cancel(app._auto_wait_id)
        app._auto_updating, app._auto_wait_id = False, None
        app.page_name, app.videos = "setup", []
        app._last_touch = time.monotonic() - 120          # nobody's touched it for 2 minutes

    def pump(self, secs):
        end = time.monotonic() + secs
        while time.monotonic() < end:
            self.app.update()
            time.sleep(0.01)

    def test_idle_start_page_or_done_page(self):
        for page in ("setup", "done"):
            self.setUp()
            self.app.page_name = page
            self.app._auto_update("9.9.9")
            self.assertEqual(self.updated, [page])

    def test_not_while_anything_could_be_lost(self):
        cases = [("working", []), ("review", []), ("setup", [r"D:\Movies\A.m4v"])]
        for page, videos in cases:
            self.setUp()
            self.app.page_name, self.app.videos = page, videos
            self.app._auto_update("9.9.9")
            self.assertEqual(self.updated, [], page)
            self.assertIsNotNone(self.app._auto_wait_id, page)        # it waits

    def test_not_just_after_she_used_it(self):
        self.app.event_generate("<Motion>", x=5, y=5)
        self.app.update()
        self.app._touched()
        self.app._auto_update("9.9.9")
        self.assertEqual(self.updated, [])

    def test_not_with_a_box_open(self):
        box = tk.Toplevel(self.app)
        try:
            self.app.update()
            self.app._auto_update("9.9.9")
            self.assertEqual(self.updated, [])
        finally:
            box.destroy()

    def test_waits_then_goes_once_safe_and_only_one_wait(self):
        self.app.page_name = "review"
        self.app._handle(("update_ready", "9.9.9"))
        self.app._handle(("update_ready", "9.9.9"))                  # the next check
        self.pump(0.2)
        self.assertEqual(self.updated, [])
        self.app.page_name = "done"                                   # reviewed and saved
        self.pump(0.3)
        self.assertEqual(self.updated, ["done"])                      # once
        self.assertIn("updates by itself", self.app.upd_lbl.cget("text"))


if __name__ == "__main__":
    unittest.main()
