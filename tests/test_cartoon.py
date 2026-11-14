"""Cartoons are judged as cartoons (1.18.94; the owner, 2026-11-14: "can we teach when something
is animated", then "build it"). Lauren's Monsters University (kids, the AI helper) had eight
cuts, none of them real: three "Christmas", a "St. Patrick's Day", "Magic" for a glowing
creature, and four gunfire-like sounds in a film with no guns.

A few stills tell a cartoon from live action (or what she said for the show). In a cartoon:
sound-only violence and unconfirmed nudity are offered unticked, the closer look is told it's
a cartoon (holidays and magic need their own signs), and the review page says so with a "Not a
cartoon" button that ticks those again and is remembered."""
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock
import tkinter as tk
from tkinter import ttk

import support
import cleanview as engine
import cleanview_ai as ai
import cleanview_learn as learn


def words(text, start):
    return [{"t": w, "s": start + 0.3 * k, "e": start + 0.3 * k + 0.2}
            for k, w in enumerate(text.split())]


class TellingACartoon(unittest.TestCase):
    def test_most_stills_animated(self):
        self.assertEqual(engine.cartoon_verdict([0.9] * 20 + [0.2] * 4), (True, 0.83))
        self.assertEqual(engine.cartoon_verdict([0.9] * 12 + [0.3] * 12), (False, 0.5))
        self.assertEqual(engine.cartoon_verdict([0.1] * 24), (False, 0.0))
        # the closest live action here: a dark Person of Interest with the Machine's screens
        self.assertEqual(engine.cartoon_verdict([0.86, 0.71, 0.65, 0.6, 0.54, 0.38, 0.31, 0.27,
                                                 0.1, 0.1, 0.1, 0.1])[0], False)
        # the two real cartoons tried (their scores as the picture AI gave them)
        superman = [0.45, 0.52, 0.68, 0.69, 0.7, 0.71, 0.78, 0.79, 0.82, 0.83, 0.85, 0.85,
                    0.86, 0.91, 0.93, 0.95, 0.95, 0.95, 0.97, 0.97, 0.97, 0.97]
        self.assertEqual(engine.cartoon_verdict(superman), (True, 0.95))

    def test_too_few_stills_cant_tell(self):
        self.assertEqual(engine.cartoon_verdict([0.9] * 5), (None, 0.0))

    def test_what_she_said_wins_then_the_stills_are_kept(self):
        work = Path(tempfile.mkdtemp(dir=support.SANDBOX))
        video = str(support.SANDBOX / "Gummi Bears S01E02.mp4")
        key = "gummi-bears@kids"
        (work / "cartoon.json").write_text(json.dumps({"scores": [0.9] * 24}))
        self.assertEqual(engine.tell_cartoon(video, work, key, True),
                         (True, "100% of the stills looked animated"))
        learn.set_animated(key, video, False)
        self.assertEqual(engine.tell_cartoon(video, work, key, True), (False, "you said so"))
        # the whole show, every age
        self.assertIs(learn.animated("gummi-bears@teens", "other episode.mp4"), False)

    def test_a_movie_is_remembered_by_its_file(self):
        learn.set_animated("_movies@kids", "Monster's University.m4v", True)
        self.assertIs(learn.animated("_movies", "Monster's University.m4v"), True)
        self.assertIsNone(learn.animated("_movies@kids", "Red Eye.m4v"))

    def test_without_the_picture_ai_it_cant_tell(self):
        work = Path(tempfile.mkdtemp(dir=support.SANDBOX))
        self.assertEqual(engine.tell_cartoon("x.mp4", work, "_movies", False), (None, ""))

    def test_a_check_that_fails_changes_nothing(self):
        work = Path(tempfile.mkdtemp(dir=support.SANDBOX))
        failed = mock.Mock(returncode=1, stderr="no picture AI")
        with mock.patch.object(engine.cl, "run", lambda *a, **k: failed):
            self.assertEqual(engine.tell_cartoon("y.mp4", work, "_movies", True, log=lambda m: None),
                             (None, ""))


class CartoonRules(unittest.TestCase):
    def sound_scene(self, s, sdh=False):
        return {"s": s, "e": s + 8, "kind": ["Violence"], "sure": True,
                "why": "gunfire-like bursts", "sdh": sdh}

    def test_sound_effects_offered_unticked(self):
        sc = engine.cartoon_sound([self.sound_scene(100)], words("Release the stuffed animals", 98))[0]
        self.assertFalse(sc["sure"])
        self.assertTrue(sc["cartoon"])
        self.assertIn("a cartoon: likely a sound effect", sc["why"])

    def test_a_gun_talked_about_or_subtitles_still_cut(self):
        gun = engine.cartoon_sound([self.sound_scene(100)], words("He has a gun get down", 99))[0]
        tagged = engine.cartoon_sound([self.sound_scene(200, sdh=True)], [])[0]
        for sc in (gun, tagged):
            self.assertTrue(sc["sure"])
            self.assertNotIn("cartoon", sc)

    def test_live_action_unchanged(self):
        sc = engine.cartoon_sound([self.sound_scene(100)], [], cartoon=False)[0]
        self.assertTrue(sc["sure"])
        self.assertNotIn("cartoon", sc)

    def test_nudity_only_with_the_ai_helpers_yes(self):
        unchecked = {"s": 10, "e": 14, "kind": ["Nudity"], "sure": True,
                     "why": "nudity seen in 5 picture checks (strongest 90%)"}
        confirmed = {"s": 50, "e": 54, "kind": ["Nudity"], "sure": True,
                     "why": "nudity seen in 5 picture checks (strongest 90%) — a bare chest"}
        out = engine.cartoon_nudity([unchecked, confirmed])
        self.assertFalse(out[0]["sure"])
        self.assertIn("isn't reliable on drawn skin", out[0]["why"])
        self.assertTrue(out[1]["sure"])
        self.assertNotIn("cartoon", out[1])

    def test_joined_to_a_fight_seen_its_cut_as_that(self):
        sound = engine.cartoon_sound([self.sound_scene(100)], [])[0]
        fight = {"s": 104, "e": 112, "kind": ["Violence"], "sure": True, "why": "fighting seen"}
        merged = engine.cartoon_joined(engine.merge_scenes([sound, fight]))
        self.assertEqual(len(merged), 1)
        self.assertTrue(merged[0]["sure"])
        self.assertNotIn("cartoon", merged[0])
        self.assertNotIn("sound effect", merged[0]["why"])

    def test_the_closer_look_is_told(self):
        asked = []

        def chat(prompt, imgs, schema, timeout=None):
            asked.append(prompt)
            return {"see": "a cartoon monster with green lights", "yes": False, "clear": True}
        cands = [{"cat": "christmas", "frames": [1.0]}, {"cat": "magic", "frames": [2.0]}]
        with mock.patch.object(ai, "chat", chat):
            ai.second_look([dict(c) for c in cands], lambda c: ["img"], cartoon=True)
            ai.second_look([dict(c) for c in cands], lambda c: ["img"])
        self.assertTrue(all(ai.CARTOON_NOTE in p for p in asked[:2]))
        self.assertFalse(any(ai.CARTOON_NOTE in p for p in asked[2:]))
        self.assertIn("Christmas tree", ai.CARTOON_NOTE)
        self.assertIn("not a creature or object that simply glows", ai.CARTOON_NOTE)


class NotACartoon(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from test_ui import ui
        cls.ui = ui
        cls.real = (ui.App._check_update, ui.App._check_every_ai, ui.App._pick_review_ai,
                    ui.cc.status)
        ui.App._check_update = lambda self, manual=False: None
        ui.App._check_every_ai = lambda self: None
        ui.App._pick_review_ai = lambda self, good: "claude"
        ui.cc.status = lambda p=None: "ready"
        try:
            cls.app = ui.App()
        except tk.TclError as ex:
            cls.put_back()
            raise unittest.SkipTest(f"no screen to draw on ({ex})")
        cls.app.update()

    @classmethod
    def put_back(cls):
        ui = cls.ui
        (ui.App._check_update, ui.App._check_every_ai, ui.App._pick_review_ai,
         ui.cc.status) = cls.real

    @classmethod
    def tearDownClass(cls):
        try:
            cls.app.destroy()
        except tk.TclError:
            pass
        cls.put_back()

    def settle(self, secs=0.3):
        end = time.time() + secs
        while time.time() < end:
            self.app.update()
            time.sleep(0.02)

    def open(self, animated, mine_unticked=False):
        app = self.app
        st = support.sample_review()
        st["path"] = str(support.SANDBOX / "Cartoon Movie.mp4")
        st["opts"] = {"profile": "kids"}
        st["cartoon"] = {"animated": animated, "how": "90% of the stills looked animated"}
        st["notes"] = [engine.CARTOON_SAID] if animated else []
        st["scenes"].append({"id": 3, "s": 70.0, "e": 78.0, "kind": ["Violence"], "cut": False,
                             "sure": False, "cartoon": True, "said": "",
                             "why": "gunfire-like bursts" + engine.CARTOON_SOUND,
                             **({"by_you": True} if mine_unticked else {})})
        app.jobs = [{"video": st["path"], "work": support.write_review(), "analysis": st,
                     "error": None, "cuts": [], "lines": [], "words": []}]
        app.videos = [st["path"]]
        app.chat_history, app.chat_sessions = [], {}
        app.ai_state = {"claude": "ready"}
        app.show_review()
        self.settle()
        return st

    def buttons(self):
        from test_ask_box import every
        return [b for b in every(self.app, ttk.Button) if b.cget("text") == "Not a cartoon"]

    def labels(self):
        from test_ask_box import every
        return [l.cget("text") for l in every(self.app, tk.Label)]

    def test_said_once_with_its_button(self):
        self.open(True)
        self.assertEqual(len(self.buttons()), 1)
        self.assertEqual(sum(engine.CARTOON_SAID in t for t in self.labels()), 1)

    def test_not_said_for_live_action(self):
        self.open(False)
        self.assertEqual(self.buttons(), [])

    def test_not_a_cartoon_ticks_them_again_and_is_remembered(self):
        st = self.open(True)
        self.buttons()[0].invoke()
        self.settle()
        sc = next(s for s in st["scenes"] if s["id"] == 3)
        self.assertTrue(sc["cut"])
        self.assertNotIn("cartoon", sc)
        self.assertNotIn("sound effect", sc["why"])
        self.assertEqual(st["cartoon"]["animated"], False)
        self.assertEqual(self.buttons(), [])
        self.assertIs(learn.animated(engine.learned_key(st["path"], st["opts"]), st["path"]),
                      False)

    def test_her_own_untick_stays(self):
        st = self.open(True, mine_unticked=True)
        self.buttons()[0].invoke()
        self.settle()
        sc = next(s for s in st["scenes"] if s["id"] == 3)
        self.assertFalse(sc["cut"])


if __name__ == "__main__":
    unittest.main()
