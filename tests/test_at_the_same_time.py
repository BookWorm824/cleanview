"""Three checks run while other work goes on (the owner, 2026-11-09: "are there any other
checks you can see that dont happen simultaneously?", then "yes do all 3. build it so that if a
gpu isnt available it will still perform all of the double checks"):
1. Claude/ChatGPT's look through the whole picture starts once what was heard and the
   subtitles are in, instead of after all the PC's own checks;
2. voices are told apart while the picture model checks the scenes, only when that model is
   all on the graphics card; anything that couldn't be checked meanwhile is looked at again;
3. subtitles are looked for online while it listens.
The same inputs and the same checks give the same results."""
import copy
import inspect
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import support
import cleanview as engine
import cleanview_ai as ai
import cleanview_claude as cc


class Subtitles(unittest.TestCase):

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(dir=support.SANDBOX))
        self.video = self.dir / "Castle Season 1 - Ep. 3.mp4"
        self.video.write_bytes(b"")
        self.work = self.dir / "work"
        self.work.mkdir()

    def fetch(self, **o):
        return engine.fetch_subtitles(self.video, {"subs": []}, self.work,
                                      dict({"autosubs": True}, **o), log=lambda m: None)

    def test_one_next_to_the_video_comes_first(self):
        (self.dir / "Castle Season 1 - Ep. 3.en.srt").write_text("".join(
            f"{k}\n00:00:0{k},000 --> 00:00:0{k},900\nHello there.\n\n" for k in range(1, 8)),
            encoding="utf8")
        with mock.patch.object(engine, "download_subtitles", side_effect=AssertionError):
            cues, note, text, why = self.fetch()
        self.assertEqual([c["text"] for c in cues], ["Hello there."] * 7)
        self.assertIsNone(text)

    def test_downloaded_and_kept(self):
        srt = "1\n00:00:01,000 --> 00:00:02,000\nHello there.\n"
        with mock.patch.object(engine, "download_subtitles", return_value=(srt, "from online")):
            cues, note, text, why = self.fetch()
        self.assertEqual((cues, text, why), ([], srt, "from online"))
        self.assertEqual((self.work / "downloaded.srt").read_text("utf8"), srt)
        with mock.patch.object(engine, "download_subtitles", side_effect=AssertionError):
            self.assertEqual(self.fetch()[2], srt)          # next time: no download

    def test_none_online_remembered(self):
        miss = engine.MISS_REMEMBER + " anywhere"
        with mock.patch.object(engine, "download_subtitles", return_value=(None, miss)):
            self.fetch()
        with mock.patch.object(engine, "download_subtitles", side_effect=AssertionError):
            self.assertEqual(self.fetch()[3], miss)

    def test_off_means_no_download(self):
        with mock.patch.object(engine, "download_subtitles", side_effect=AssertionError):
            self.assertEqual(self.fetch(autosubs=False), ([], "", None, ""))

    def test_started_before_listening(self):
        src = inspect.getsource(engine.analyze)
        self.assertLess(src.index("subs_job = in_background(get_subs)"), src.index("transcribe("))
        self.assertLess(src.index("transcribe("), src.index("wait_for(subs_job"))


SCENES = [{"id": 1, "s": 100.0, "e": 110.0, "kind": ["Violence"], "why": "bangs", "cut": True}]
FINDS = [{"s": 100.5, "e": 109.0, "what": "fighting", "who": "n/a", "level": "n/a",
          "why": "a fist fight"},
         {"s": 300.0, "e": 306.0, "what": "kissing", "who": "man & woman", "level": "passionate",
          "why": "a long kiss"}]


class WholePicture(unittest.TestCase):

    def run_it(self, early):
        o = engine.full_opts({"violence": True, "kiss_os": "all", "reader": "claude",
                              "look": True})
        asr = [{"t": "hey", "s": 101.0, "e": 101.3}]
        with mock.patch.object(engine, "make_sheets", lambda p, w, d: [("s.jpg", 0.0)]), \
                mock.patch.object(cc, "picture_review",
                                  lambda *a, **k: copy.deepcopy(FINDS)), \
                mock.patch.object(engine, "scene_sheet", lambda *a, **k: None), \
                mock.patch.object(engine, "refine_bounds",
                                  lambda path, work, dur, scenes, asr, progress=None: (scenes, 0)):
            finds = engine.whole_picture("v.mp4", ".", 600.0, o, asr, []) if early else None
            return engine.look_at_picture("v.mp4", ".", 600.0, copy.deepcopy(SCENES), o, asr,
                                          cues=[], finds=finds)

    def test_same_scenes_either_way(self):
        self.assertEqual(self.run_it(early=True), self.run_it(early=False))

    def test_stops_between_batches(self):
        with mock.patch.object(cc, "ask", side_effect=AssertionError):
            with self.assertRaises(KeyboardInterrupt):
                cc.picture_review([("s.jpg", 0.0)], "fights", cancel=lambda: True)

    def test_started_once_heard_and_subtitles_are_in(self):
        src = inspect.getsource(engine.analyze)
        start = src.index("pics_job = in_background(look_through)")
        self.assertLess(src.index("cues, sub_note, text, why = subs[\"found\"]"), start)
        self.assertLess(start, src.index("ai.dialogue_lines("))
        self.assertIn("cues=cues, finds=finds)", src)


class Voices(unittest.TestCase):

    def ps(self, size, vram):
        def api(path, payload=None, timeout=10):
            r = mock.MagicMock()
            r.__enter__.return_value = r
            r.read.return_value = json.dumps({"models": [
                {"name": "qwen3-vl:8b", "size": size, "size_vram": vram}]}).encode()
            return r
        return api

    def test_all_on_the_graphics_card(self):
        with mock.patch.object(ai, "_api", self.ps(6e9, 6e9)):
            self.assertTrue(ai.on_graphics_card("qwen3-vl:8b"))

    def test_most_of_it_counts(self):
        with mock.patch.object(ai, "_api", self.ps(6.9e9, 5.3e9)):     # an 8 GB card
            self.assertTrue(ai.on_graphics_card("qwen3-vl:8b"))

    def test_little_or_none_on_it(self):
        for vram in (2e9, 0):
            with self.subTest(vram=vram), mock.patch.object(ai, "_api", self.ps(6e9, vram)):
                self.assertFalse(ai.on_graphics_card("qwen3-vl:8b"))

    def test_not_knowing_means_one_after_the_other(self):
        with mock.patch.object(ai, "_api", side_effect=OSError("not running")):
            self.assertFalse(ai.on_graphics_card("qwen3-vl:8b"))

    def test_only_with_the_graphics_card(self):
        src = inspect.getsource(engine.analyze)
        self.assertIn("if voices_wanted and ai.on_graphics_card():", src)
        self.assertIn("genders = find_voices(path, info, work, lines, cancel)", src)


class EveryCheckDone(unittest.TestCase):

    def test_what_couldnt_be_checked_is_looked_at_again(self):
        cands = [{"cat": "fight", "verdict": {"keep": True, "error": "timed out"}},
                 {"cat": "kiss", "verdict": {"keep": False}},
                 {"cat": "gore", "verdict": {"keep": True, "error": "no frames"}},
                 {"cat": "nudity", "verdict": {"keep": True, "error": "connection reset"}}]
        looked = []

        def look(redo):
            looked.extend(c["cat"] for c in redo)
            for c in redo:
                c["verdict"] = {"keep": False, "level": "none"}
        self.assertEqual(engine.recheck_failed(cands, look), 2)
        self.assertEqual(looked, ["fight", "nudity"])
        self.assertEqual([c["verdict"].get("error") for c in cands],
                         [None, None, "no frames", None])

    def test_nothing_to_redo(self):
        self.assertEqual(engine.recheck_failed([{"verdict": {"keep": True}}],
                                               lambda r: self.fail("looked")), 0)

    def test_after_every_closer_look_done_alongside_something(self):
        src = inspect.getsource(engine.analyze)
        self.assertEqual(src.count("finish_look()\n"), 2)
        self.assertEqual(src.count("recheck_failed(todo"), 2)


if __name__ == "__main__":
    unittest.main()
