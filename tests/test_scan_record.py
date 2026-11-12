"""How each scan went, written down (1.18.58, the owner: "yes to adding the name of the version,
if you can think of any other data that would help in that can add it"): the CleanView
version, the AI helper's models, how long each step took, the closer look's counts and the PC,
in the notes (review page and report) and in "Send what we refined"."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import support
import cleanview as engine
import cleanview_ai as ai
import cleanview_learn as learn


class Steps(unittest.TestCase):
    def test_messages_belong_to_steps(self):
        S = engine.scan_step
        self.assertEqual(S("Loading the listening model…"), "listening")
        self.assertEqual(S("Listening to the dialogue · about 3 min left"), "listening")
        self.assertEqual(S("Listening for fights, gunfire and other sounds…"), "sound check")
        self.assertEqual(S("Looking for subtitles online…"), "language and subtitles")
        self.assertEqual(S("Watching the picture with the picture AI · 2 min left"), "picture scan")
        self.assertEqual(S("Taking a closer look at the scenes found · 3–4 of 9"), "closer look")
        self.assertEqual(S("Taking another look at scenes that couldn't be checked"),
                         "closer look")
        self.assertEqual(S("Telling voices apart…"), "voices")
        self.assertEqual(S("Reading the dialogue · lines 1–25 of 900"), "reading the dialogue")
        self.assertEqual(S("Reading each conversation · 2 of 40"), "reading each conversation")
        self.assertEqual(S("Claude is reading the dialogue…"), "reading the dialogue")
        self.assertEqual(S("Claude is looking through the whole picture · 2 min left"),
                         "looking through the picture")
        self.assertEqual(S("ChatGPT is reviewing everything that was found…"), "final review")
        self.assertEqual(S("Putting the scene list together…"), "scene list")
        self.assertEqual(S("something new"), "getting ready")

    def test_took_note(self):
        note = engine.took_note({"listening": 1.84, "sound check": 0.01, "picture scan": 4.3})
        self.assertEqual(note, "Took 6 min: listening 1.8, picture scan 4.3 (minutes).")
        self.assertEqual(engine.took_note({"closer look": 0.1, "voices": 0.2}),
                         "Took under a minute: closer look 0.1, voices 0.2 (minutes).")


class OnTheCard(unittest.TestCase):
    def ps(self, models):
        def api(path, payload=None, timeout=10):
            r = mock.MagicMock()
            r.__enter__.return_value = r
            r.read.return_value = json.dumps({"models": models}).encode()
            return r
        return api

    def test_share_of_a_loaded_model(self):
        with mock.patch.object(ai, "_api", self.ps([{"name": "qwen3-vl:8b-instruct",
                                                     "size": 6.9e9, "size_vram": 5.3e9}])):
            self.assertEqual(ai.on_card_share("qwen3-vl:8b-instruct"), 0.77)
            self.assertIsNone(ai.on_card_share("qwen3:8b"))          # not loaded: not known
        with mock.patch.object(ai, "_api", side_effect=OSError("not running")):
            self.assertIsNone(ai.on_card_share("qwen3:8b"))


class SentIn(unittest.TestCase):
    def test_the_refined_file_has_it(self):
        scan = {"app_version": "1.18.58", "models": {"pictures": "p", "dialogue": "d"},
                "minutes": {"listening": 1.5}, "pc": {"threads": 8, "memory_gb": 16.0},
                "closer_look": {"checked": 3, "kept": 1, "dropped": 2, "failed": 0}}
        st = {"path": "Movie.m4v", "show": "_movies", "notes": [], "scenes": [], "lines": [],
              "mutes": [], "dialogue": [], "scan": scan}
        out = learn.export_refined([st], dest_dir=tempfile.mkdtemp(dir=support.SANDBOX))
        self.assertEqual(json.loads(Path(out).read_text("utf8"))["videos"][0]["scan"], scan)

    def test_a_review_from_before_has_none(self):
        st = {"path": "Old.m4v", "notes": [], "scenes": [], "lines": [], "mutes": [],
              "dialogue": []}
        out = learn.export_refined([st], dest_dir=tempfile.mkdtemp(dir=support.SANDBOX))
        self.assertIsNone(json.loads(Path(out).read_text("utf8"))["videos"][0]["scan"])

    def test_the_pc(self):
        self.assertGreater(engine.total_memory_gb(), 0)
        self.assertTrue(engine.app_version())


if __name__ == "__main__":
    unittest.main()
