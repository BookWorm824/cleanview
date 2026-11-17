"""No internet: say so and ask before cleaning (1.18.85; the owner, 2026-11-13, once the
subtitle switch was gone: "the only caveat i can think of if someone wants to clean but there
is not internet service to look for subtitles", "if there s no internet connected could it pop
up a small window saying no internet, cant look up subtitles. want to clean without them?",
"with a yes no button").

Nothing here touches the network: the check is given a stand-in socket, or told the answer."""
import os
import socket
import tempfile
import unittest
import tkinter as tk
from pathlib import Path
from unittest import mock

import support
import cleanview as engine
from test_spanish import SRT
from test_ui import ui


class TheCheck(unittest.TestCase):
    def test_told_the_answer(self):
        with mock.patch.dict(os.environ, {"CLEANVIEW_ONLINE": "1"}), \
                mock.patch.object(socket, "create_connection", side_effect=AssertionError):
            self.assertTrue(engine.online())
        with mock.patch.dict(os.environ, {"CLEANVIEW_ONLINE": "0"}), \
                mock.patch.object(socket, "create_connection", side_effect=AssertionError):
            self.assertFalse(engine.online())

    def really(self, **how):
        env = {k: v for k, v in os.environ.items() if k != "CLEANVIEW_ONLINE"}
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(socket, "create_connection", **how) as tried:
            return engine.online(), tried

    def test_one_answer_is_enough(self):
        ok, tried = self.really(return_value=mock.Mock())
        self.assertTrue(ok)
        # every place is tried at once (1.18.128), each only briefly
        self.assertEqual({c[0][0] for c in tried.call_args_list}, set(engine.ONLINE_HOSTS))
        self.assertLessEqual(tried.call_args[1]["timeout"], 2)      # the window isn't held long

    def test_a_slow_place_doesnt_hold_it_up(self):
        # 1.18.128 (the owner, 2026-11-17: the scanned-before box "was slow to come up"): the
        # places were tried one after the other, each waited for up to 1.5 s
        import time

        def connect(host, timeout):
            if host == engine.ONLINE_HOSTS[0]:
                time.sleep(1.2)
                raise OSError("timed out")
            return mock.Mock()
        t = time.perf_counter()
        ok, _ = self.really(side_effect=connect)
        self.assertTrue(ok)
        self.assertLess(time.perf_counter() - t, 0.6)

    def test_the_first_place_down_the_next_tried(self):
        ok, tried = self.really(side_effect=[OSError("down"), mock.Mock()])
        self.assertTrue(ok)
        self.assertEqual(tried.call_count, 2)

    def test_no_internet(self):
        ok, tried = self.really(side_effect=OSError("no route"))
        self.assertFalse(ok)
        self.assertEqual(tried.call_count, len(engine.ONLINE_HOSTS))


class Offline(unittest.TestCase):
    """Cleaning without looking online: what's already there is still used."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(dir=support.SANDBOX))
        self.video = self.dir / "Episode 1.mkv"
        self.video.write_bytes(b"")
        self.work = self.dir / "work"
        self.work.mkdir()

    def fetch(self, **o):
        def never(*a, **k):
            raise AssertionError("looked online")
        with mock.patch.object(engine, "download_subtitles", never):
            return engine.fetch_subtitles(self.video, {"subs": []}, self.work,
                                          dict({"autosubs": True, "offline": True}, **o),
                                          log=lambda m: None)

    def test_nothing_is_looked_up(self):
        cues, note, text, why = self.fetch()
        self.assertEqual((cues, text), ([], None))
        self.assertEqual(why, engine.NO_INTERNET)
        self.assertEqual(list(self.work.iterdir()), [])          # no "none online" remembered

    def test_the_videos_own_subtitles_are_still_used(self):
        (self.dir / "Episode 1.srt").write_text(SRT.replace("{}", "A line"), encoding="utf8")
        cues, note, text, why = self.fetch()
        self.assertEqual(len(cues), 8)
        self.assertEqual(note, "subtitles from Episode 1.srt")

    def test_ones_downloaded_before_are_still_used(self):
        (self.work / "downloaded.srt").write_text(SRT.replace("{}", "A line"), encoding="utf8")
        (self.work / "downloaded.txt").write_text("subtitles found online", encoding="utf8")
        cues, note, text, why = self.fetch()
        self.assertIn("A line 1", text)
        self.assertEqual(why, "subtitles found online")

    def test_online_it_looks_as_before(self):
        with mock.patch.object(engine, "download_subtitles",
                               lambda p, w, log=print: (None, engine.MISS_REMEMBER)):
            cues, note, text, why = engine.fetch_subtitles(
                self.video, {"subs": []}, self.work, {"autosubs": True}, log=lambda m: None)
        self.assertEqual(why, engine.MISS_REMEMBER)


class StartCleaning(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.real = (ui.App._check_update, ui.App._check_every_ai, ui.App.show_working,
                    ui.App._start_work, ui.messagebox.askyesno, ui.chime)
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
        (ui.App._check_update, ui.App._check_every_ai, ui.App.show_working, ui.App._start_work,
         ui.messagebox.askyesno, ui.chime) = cls.real

    @classmethod
    def tearDownClass(cls):
        try:
            cls.app.destroy()
        except tk.TclError:
            pass
        cls.put_back()

    def press_start(self, internet, answer=None):
        app = self.app
        app.show_setup()
        app.opts["reader"].set("local")
        video = support.SANDBOX / "Offline Show S01E01.mp4"
        video.write_bytes(b"not really a video")
        app.videos, app.outdir = [str(video)], str(support.SANDBOX / "Clean")
        asked, started = [], []
        ui.messagebox.askyesno = lambda t, m, **k: asked.append(m) or answer
        ui.App.show_working = lambda self, *a, **k: started.append("page")
        ui.App._start_work = lambda self, target: started.append("work")
        with mock.patch.dict(os.environ, {"CLEANVIEW_ONLINE": "1" if internet else "0"}):
            app.start()
        return asked, started

    def test_with_internet_nothing_is_asked(self):
        asked, started = self.press_start(internet=True)
        self.assertEqual(asked, [])
        self.assertEqual(started, ["page", "work"])
        self.assertNotIn("offline", self.app.scan_opts)
        self.assertIs(self.app.scan_opts["autosubs"], True)

    def test_without_it_she_is_asked(self):
        asked, started = self.press_start(internet=False, answer=False)
        self.assertEqual(len(asked), 1)
        self.assertIn("There's no internet connection", asked[0])
        self.assertIn("can't look for subtitles online", asked[0])
        self.assertTrue(asked[0].rstrip().endswith("Clean without looking online?"))

    def test_no_stays_on_the_start_page(self):
        asked, started = self.press_start(internet=False, answer=False)
        self.assertEqual(started, [])
        self.assertEqual(self.app.page_name, "setup")
        self.assertNotIn("offline", self.app.scan_opts)

    def test_yes_cleans_without_looking_online(self):
        asked, started = self.press_start(internet=False, answer=True)
        self.assertEqual(started, ["page", "work"])
        self.assertIs(self.app.scan_opts["offline"], True)
        self.assertEqual(len(self.app.jobs), 1)

    def test_a_scan_used_again_needs_no_internet(self):
        # 1.18.128 (the owner, 2026-11-17: the scanned-before box "was slow to come up"): the
        # internet is only checked for videos that are scanned anew
        with mock.patch.object(ui.engine, "saved_scan", lambda *a: {"dialogue": [], "lines": []}):
            asked, started = self.press_start(internet=False, answer=True)
        self.assertEqual(len(asked), 1)
        self.assertIn("scanned before", asked[0].lower())
        self.assertEqual(started, ["page", "work"])
        self.assertNotIn("offline", self.app.scan_opts)
        self.assertEqual(str(self.app.cget("cursor")), "")

    def test_scanned_anew_it_still_asks(self):
        with mock.patch.object(ui.engine, "saved_scan", lambda *a: {"dialogue": [], "lines": []}):
            asked, started = self.press_start(internet=False, answer=False)
        self.assertEqual(len(asked), 2)                  # use it again? no; no internet: no
        self.assertIn("There's no internet connection", asked[1])
        self.assertEqual(started, [])
        self.assertEqual(str(self.app.cget("cursor")), "")

    def test_back_online_the_next_clean_looks_again(self):
        self.press_start(internet=False, answer=True)
        asked, started = self.press_start(internet=True)
        self.assertEqual(asked, [])
        self.assertNotIn("offline", self.app.scan_opts)


if __name__ == "__main__":
    unittest.main()
