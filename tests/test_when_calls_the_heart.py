"""Lauren's When Calls the Heart (Movie) report (1.18.134, 2026-11-18, adults, the AI helper, made
on 1.18.132; the owner: "yes to all"). No subtitles came during her scan ("no matching subtitles
were found online"), though the 2013 movie's came straight away afterwards; so "hold the dam
back" was heard as the swear, and "Dear Lord, please help us." was muted as an oath. Now the
subtitles are asked for once more during the picture check, and a "none online" is only
remembered when the site really has none."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import support  # noqa: F401  (must come first)
import test_timing as T

import cleanview as engine
import cleanview_ai as ai
import cvcore as cl


def listed(text):
    return cl.find_language([cl.norm(t) for t in text.split()], list(cl.CATS), [])


class TheDam(unittest.TestCase):
    def test_a_dam(self):
        for text in ("I'm already doing everything in my power to hold the damn back.",
                     "The damn burst last spring.", "There's a beaver damn on the creek.",
                     "Keep the damn back, boys!"):
            self.assertEqual(listed(text), [], text)

    def test_still_the_swear(self):
        for text in ("Close the damn back door!", "Hold the damn phone.", "Damn it!",
                     "Get the damn car started."):
            self.assertTrue(listed(text), text)


class DearLord(unittest.TestCase):
    def test_a_prayer(self):
        self.assertEqual(listed("Dear Lord, please help us."), [])
        self.assertEqual(listed("Dear God, thank you for this food."), [])

    def test_an_oath(self):
        self.assertTrue(listed("Oh dear God!"))
        self.assertTrue(listed("Dear God, when I came here"))


class TheLocalPolice(unittest.TestCase):
    def test_hooked_up_with_the_local_police(self):          # CleanListen's note
        casual = engine.LINE_WORDS["casual"]
        self.assertIsNone(casual.search("He hooked up with the local police."))
        self.assertIsNotNone(casual.search("She hooked up with Brandon."))


class SiteDidntSend(unittest.TestCase):
    def test_listed_but_none_sent(self):
        import subliminal
        d = Path(tempfile.mkdtemp(dir=support.SANDBOX))
        video = d / "When Calls the Heart (Movie).m4v"
        video.write_bytes(b"\0" * 1000)

        def listing(videos, languages, **k):
            return {v: ["one listed"] for v in videos}
        with mock.patch.object(subliminal, "download_best_subtitles", lambda *a, **k: {}), \
                mock.patch.object(subliminal, "list_subtitles", listing):
            text, why = engine.download_subtitles(str(video), str(d), log=lambda m: None)
        self.assertIsNone(text)
        self.assertEqual(why, engine.SITE_DIDNT_SEND)
        with mock.patch.object(subliminal, "download_best_subtitles", lambda *a, **k: {}), \
                mock.patch.object(subliminal, "list_subtitles", lambda v, l, **k: {}):
            text, why = engine.download_subtitles(str(video), str(d), log=lambda m: None)
        self.assertTrue(why.startswith(engine.MISS_REMEMBER))


class RememberedOnlyAfterTwoTries(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(dir=support.SANDBOX))
        self.video = self.dir / "When Calls the Heart (Movie).m4v"
        self.video.write_bytes(b"\0" * 1000)
        self.work = self.dir / "work"
        self.work.mkdir()
        self.miss = self.work / "no_subtitles_online.txt"

    def fetch(self, **k):
        return engine.fetch_subtitles(self.video, {"subs": []}, self.work, {"autosubs": True},
                                      log=lambda m: None, **k)

    def test_first_try_not_remembered(self):
        miss = engine.MISS_REMEMBER
        with mock.patch.object(engine, "download_subtitles", return_value=(None, miss)):
            self.fetch(remember_miss=False)
        self.assertFalse(self.miss.exists())
        with mock.patch.object(engine, "download_subtitles", return_value=(None, miss)):
            self.fetch(again=True)
        self.assertTrue(engine.remembered_miss(self.miss))

    def test_a_hiccup_never_remembered(self):
        with mock.patch.object(engine, "download_subtitles",
                               return_value=(None, engine.SITE_DIDNT_SEND)):
            self.fetch(again=True)
        self.assertFalse(self.miss.exists())

    def test_an_old_miss_is_asked_again(self):
        self.miss.write_text(engine.MISS_REMEMBER + "\nlooked up as: movie or episode (1.18.34)",
                             encoding="utf8")
        self.assertFalse(engine.remembered_miss(self.miss))   # her scan's, from before


class AskedAgainDuringThePicture(unittest.TestCase):
    """A whole analyze() with stand-ins: the first try gets nothing, the second (during the
    picture check) gets subtitles, and they're used."""

    @classmethod
    def setUpClass(cls):
        cls.video = support.SANDBOX / "When Calls the Heart (Movie).mp4"
        if not cls.video.exists():
            T.ffmpeg("-f", "lavfi", "-i", "testsrc=size=64x48:rate=10:duration=20", "-f",
                     "lavfi", "-i", "sine=frequency=300:duration=20", "-c:v", "libx264",
                     "-c:a", "aac", "-shortest", cls.video)

    def scan(self, answers):
        work = Path(tempfile.mkdtemp(dir=support.SANDBOX))
        asr = [{"t": w, "s": 3.0 + 0.3 * k, "e": 3.2 + 0.3 * k} for k, w in enumerate(
            "i'm doing everything in my power to hold the damn back".split())]
        srt_cues = [{"s": 2.9, "e": 7.0, "text": "I'm doing everything in my power to hold "
                     "the dam back."}]
        n = int(20 * engine.VISUAL_FPS)
        vis = {"version": engine.PICTURE_VERSION, "fps": engine.VISUAL_FPS,
               "classes": list(engine.KEEP), "scores": [[0.0] * len(engine.KEEP)] * n,
               "lum": [[120.0, 40.0]] * n, "lifted": [], "notes": []}
        calls, order = [], []

        def fetch(path, info, work_, o, log=None, remember_miss=True, again=False):
            calls.append((remember_miss, again))
            return answers[len(calls) - 1]

        def picture(*a, **k):
            import time
            start = len(calls)
            time.sleep(1.0)
            order.append(("picture", start, len(calls)))
            return vis

        def synced(text, why, heard, others=()):
            return srt_cues, 1.0, text, why
        with mock.patch.object(engine, "SUB_RETRY_WAIT", 0.3), \
                mock.patch.object(ai, "start_ollama", lambda *a, **k: True), \
                mock.patch.object(ai, "choose_models", lambda: True), \
                mock.patch.object(ai, "clip_ready", lambda: False), \
                mock.patch.object(ai, "on_graphics_card", lambda model=None: True), \
                mock.patch.object(ai, "free_memory", lambda: None), \
                mock.patch.object(ai, "romance_scenes", lambda *a, **k: []), \
                mock.patch.object(engine, "available_memory_gb", lambda: 16.0), \
                mock.patch.object(engine, "load_listeners", lambda *a: [None]), \
                mock.patch.object(engine, "transcribe", lambda *a, **k: [dict(w) for w in asr]), \
                mock.patch.object(engine, "fetch_subtitles", fetch), \
                mock.patch.object(engine, "pick_subtitles", synced), \
                mock.patch.object(engine, "visual_scan", picture), \
                mock.patch.object(engine, "find_voices", lambda lines, *a, **k:
                                  [{"g": "m", "spk": 1} for _ in lines]), \
                mock.patch.object(engine, "find_lines", lambda *a, **k: ([], "the AI helper")), \
                mock.patch.object(engine, "decide_picture_scenes", lambda *a, **k: []), \
                mock.patch.object(engine, "make_thumbs", lambda *a, **k: None):
            engine.analyze(str(self.video), str(work), groups=["swearing", "mild"],
                           opts={"nudity": True, "sexref": False, "sex": False,
                                 "violence": False, "loudmusic": False, "ai": True,
                                 "reader": "local", "autosubs": True, "look": True},
                           progress=lambda f, m: None, log=lambda m: None)
        return json.loads((work / "analysis.json").read_text()), calls, order

    def test_second_try_used(self):
        srt = "1\n00:00:02,900 --> 00:00:07,000\nI'm doing everything in my power to hold " \
              "the dam back.\n"
        st, calls, order = self.scan([([], "", None, engine.MISS_REMEMBER),
                                      ([], "", srt, "subtitles downloaded from opensubtitles")])
        self.assertEqual(calls, [(False, False), (True, True)])
        self.assertEqual(order, [("picture", 1, 2)])       # asked again during the picture
        self.assertTrue(st["cues"])
        self.assertEqual([m for m in st["mutes"] if m["raw"] == "damn"
                          and not m.get("keep")], [])     # the dam, by the subtitles

    def test_not_asked_again_for_a_real_miss_from_before(self):
        st, calls, _ = self.scan([([], "", None, "No subtitles: none came")])
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
