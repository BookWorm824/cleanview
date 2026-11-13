"""A video that fails while it's watched and listened to offers to send a note (1.18.87; the
owner, 2026-11-13: "if clean view crashes or has a save issue. is that sent to you someway? is
it in any report you would get?", and "yes" to adding the one case that wasn't offered: a
crash and a failed save already asked).

Nothing is really sent: the sending is a stand-in, and the inbox is the tests' own."""
import json
import time
import unittest
import tkinter as tk
from pathlib import Path

import support
from test_ui import ui

HOME = str(Path.home())


class CheckFailed(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.real = (ui.App._check_update, ui.App._check_every_ai, ui.messagebox.askyesno,
                    ui.messagebox.showinfo, ui.learn.send, ui.learn.send_url, ui.chime,
                    ui.App._send_by_hand)
        ui.App._check_update = lambda self, manual=False: None
        ui.App._check_every_ai = lambda self: None
        ui.chime = lambda *a, **k: None
        try:
            cls.app = ui.App()
        except tk.TclError as ex:
            cls.put_back()
            raise unittest.SkipTest(f"no screen to draw on ({ex})")
        cls.app.update()

    @classmethod
    def put_back(cls):
        (ui.App._check_update, ui.App._check_every_ai, ui.messagebox.askyesno,
         ui.messagebox.showinfo, ui.learn.send, ui.learn.send_url, ui.chime,
         ui.App._send_by_hand) = cls.real

    @classmethod
    def tearDownClass(cls):
        try:
            cls.app.destroy()
        except tk.TclError:
            pass
        cls.put_back()

    def setUp(self):
        for f in support.APP_DATA.glob("CleanView couldn't check*.json"):
            f.unlink()
        self.asked, self.told, self.sent, self.by_hand = [], [], [], []
        ui.learn.send_url = lambda: support.NO_INBOX
        ui.learn.send = lambda path, kind: self.sent.append((Path(path), kind))
        ui.messagebox.showinfo = lambda t, m, **k: self.told.append(m)
        ui.App._send_by_hand = lambda app, path, first="": self.by_hand.append((path, first))
        self.app.scan_opts = {"reader": "local", "ai": True, "look": True, "language": "en",
                              "profile": "adults", "nudity": True}

    def fail(self, answer, *jobs):
        """after_analyze with these failed videos, answering the question box."""
        ui.messagebox.askyesno = lambda t, m, **k: self.asked.append((t, m)) or answer
        self.app.jobs = [dict({"analysis": None, "work": support.SANDBOX / "w"}, **j)
                         for j in jobs]
        self.app.after_analyze()
        end = time.time() + 3
        while time.time() < end and answer and not (self.told or self.by_hand):
            self.app.update()
            time.sleep(0.02)
        self.app.update()

    UNEXPECTED = {"video": HOME + r"\Videos\Show S01E02.mp4",
                  "error": "Show S01E02.mp4: Something unexpected went wrong.",
                  "details": HOME + "\\Videos\\Show S01E02.mp4\n\nTraceback (most recent call "
                             "last):\n  File \"cleanview.py\", line 1, in analyze\nKeyError: 'x'"}
    PROTECTED = {"video": HOME + r"\Videos\Bought Movie.m4v", "video_error": True,
                 "error": "Bought Movie.m4v is copy-protected (DRM), so it can't be cleaned.",
                 "details": HOME + "\\Videos\\Bought Movie.m4v\n\nVideoError"}

    def test_she_is_asked_once_with_the_reason(self):
        self.fail(False, self.UNEXPECTED)
        self.assertEqual(len(self.asked), 1)
        title, said = self.asked[0]
        self.assertEqual(title, "CleanView ran into a problem")
        self.assertIn("These couldn't be cleaned and will be skipped", said)
        self.assertIn("Show S01E02.mp4: Something unexpected went wrong.", said)
        self.assertIn("Send a note about what went wrong, so it can be fixed?", said)
        self.assertIn("No video or sound.", said)
        self.assertEqual(self.app.page_name, "setup")           # nothing to review

    def test_no_sends_nothing(self):
        self.fail(False, self.UNEXPECTED)
        self.assertEqual(self.sent, [])
        self.assertEqual(list(support.APP_DATA.glob("CleanView couldn't check*.json")), [])

    def test_yes_sends_the_note(self):
        self.fail(True, self.UNEXPECTED)
        self.assertEqual(len(self.sent), 1)
        path, kind = self.sent[0]
        self.assertEqual(kind, "problem")
        self.assertTrue(path.name.startswith("CleanView couldn't check "))
        note = json.loads(path.read_text(encoding="utf8"))
        self.assertEqual(note["app"], "CleanView")
        self.assertEqual(note["what"], "couldn't check a video")
        self.assertEqual(note["version"], ui._app_version())
        self.assertIn("KeyError: 'x'", note["note"])
        self.assertIn("Show S01E02.mp4", note["note"])
        self.assertNotIn(HOME, note["note"])                    # her own folder isn't sent
        self.assertIn("~", note["note"])
        self.assertEqual((note["videos"], note["failed"]), (1, 1))
        self.assertEqual(note["settings"]["reader"], "local")
        self.assertNotIn("nudity", note["settings"])            # not her filter choices
        self.assertEqual(self.told, ["Sent. Thank you!"])

    def test_a_copy_protected_video_alone_is_only_told(self):
        self.fail(True, self.PROTECTED)
        self.assertEqual(self.sent, [])
        self.assertEqual(len(self.asked), 1)                    # the old box: open the details?
        self.assertNotIn("Send a note", self.asked[0][1])
        self.assertIn("copy-protected", self.asked[0][1])

    def test_one_of_each_is_offered_and_has_both(self):
        self.fail(True, self.PROTECTED, self.UNEXPECTED)
        self.assertIn("Send a note", self.asked[0][1])
        note = json.loads(self.sent[0][0].read_text(encoding="utf8"))
        self.assertIn("Bought Movie.m4v", note["note"])
        self.assertIn("KeyError", note["note"])
        self.assertEqual((note["videos"], note["failed"]), (2, 2))

    def test_no_inbox_is_the_old_box(self):
        ui.learn.send_url = lambda: ""
        self.fail(True, self.UNEXPECTED)
        self.assertEqual(self.sent, [])
        self.assertNotIn("Send a note", self.asked[0][1])

    def test_a_send_that_fails_keeps_the_file(self):
        def no_internet(path, kind):
            raise OSError("no route to the inbox")
        ui.learn.send = no_internet
        self.fail(True, self.UNEXPECTED)
        self.assertEqual(self.told, [])
        self.assertEqual(len(self.by_hand), 1)
        path, first = self.by_hand[0]
        self.assertTrue(Path(path).exists())
        self.assertIn("Couldn't send it", first)

    def test_the_videos_that_worked_are_still_reviewed(self):
        good = support.sample_review()
        ui.messagebox.askyesno = lambda t, m, **k: self.asked.append((t, m)) or False
        self.app.jobs = [dict({"analysis": None, "work": support.SANDBOX / "w"}, **self.UNEXPECTED),
                         {"video": good["path"], "work": support.write_review(),
                          "analysis": good, "error": None}]
        self.app.after_analyze()
        self.app.update()
        self.assertIn("Send a note", self.asked[0][1])
        self.assertEqual(self.app.page_name, "review")


if __name__ == "__main__":
    unittest.main()
