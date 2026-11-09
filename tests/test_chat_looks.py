"""The chat looks at the picture (Lauren, 2026-11-08). Told "near the beginning they are holding
hands", the chat said it could only see the dialogue and cut a whole 49-second visit; told
"you are supposed to view photos as well", it said again it couldn't. And the picture check
itself could only report two women kissing, not holding hands. Now the chat asks to see a
stretch, CleanView shows it stills, and it cuts what it saw; the picture check reports a
same-sex couple's affection, judged by the context ("hand holding needs to be done by
context": a mother and child holding hands is fine)."""
import subprocess
import tempfile
import unittest
from pathlib import Path

import support
import cleanview as engine
import cleanview_claude as cc

NONE = {"reply": "", "tick": [], "untick": [], "mute_lines": [], "mute_words": [],
        "cut_scenes": [], "cut_times": [], "remember": []}


def episode():
    return {"dialogue": [{"s": 431.0, "e": 434.0, "text": "I brought you an espresso and a pastry."},
                         {"s": 470.0, "e": 473.0, "text": "You're the best, babe."},
                         {"s": 1642.0, "e": 1645.0, "text": "I'm going to connect you to your wife now."}],
            "scenes": [], "lines": [], "mutes": [], "duration": 2580.0, "path": "Episode.mkv"}


class AsksToLook(unittest.TestCase):

    def setUp(self):
        self.asked, self.real = [], cc.ask
        self.addCleanup(lambda: setattr(cc, "ask", self.real))
        self.looked, self.said = [], []

    def fake(self, answers):
        def ask(prompt, schema, stdin_text="", system=None, session=None, keep=False,
                images=None, **k):
            self.asked.append({"prompt": prompt, "schema": schema, "images": images or []})
            return dict(NONE, **answers.pop(0)), "s1"
        cc.ask = ask

    def look(self, a, b):
        self.looked.append((a, b))
        t0 = a - a % 40
        return [(f"sheet_{int(t)}.jpg", float(t)) for t in range(int(t0), int(b), 40)]

    def test_it_looks_and_cuts_just_what_it_saw(self):
        self.fake([{"reply": "I'll look at the first ten minutes.",
                    "look_at": [{"from": "0:00", "to": "10:00"}]},
                   {"reply": "Maddy and Amy hold hands at 7:24 to 7:31; I've cut that.",
                    "cut_times": [{"from": "7:24", "to": "7:31", "why": "two women holding hands"}]},
                   {"reply": ""}])                       # nothing in the last 2 minutes
        st = episode()
        reply, acts, items, sid = cc.chat("near the beginning they are holding hands", st,
                                          look=self.look, say=self.said.append)
        self.assertEqual(self.looked, [(0.0, 600.0)])
        self.assertIn("looking at the picture from 0:00:00 to 0:10:00", self.said[0])
        pics = self.asked[1]["images"]
        self.assertEqual(len(pics), 12)                         # 15 sheets: 12, then 3
        self.assertEqual(len(self.asked), 3)
        self.assertIn("tile 1 is at 0:07:20", pics[11][0])
        self.assertIn("near the beginning they are holding hands", self.asked[1]["prompt"])
        self.assertIn("2 [0:07:50] You're the best, babe.", self.asked[1]["prompt"])
        self.assertNotIn("look_at", self.asked[1]["schema"]["properties"])
        self.assertEqual(acts["cut_times"], [{"from": "7:24", "to": "7:31",
                                              "why": "two women holding hands"}])
        self.assertIn("7:24", reply)
        # the chat itself hears what it saw, next time
        self.assertIn("showed you stills from 0:00:00 to 0:10:00", st["chat_seen"])
        self.fake([{"reply": "Yes."}])
        cc.chat("did you get it?", st, session="s1", look=self.look)
        self.assertIn("showed you stills", self.asked[-1]["prompt"])
        self.assertNotIn("chat_seen", st)

    def test_the_chat_is_told_it_can_look(self):
        self.assertIn("look_at", cc.CHAT_SCHEMA["required"])
        self.assertIn("never tell them you can't see it", cc.CHAT_HOW)
        self.assertNotIn("look_at", cc.SEEN_HOW)
        self.assertIn("Do what they ask", cc.SEEN_HOW)
        self.fake([{"reply": "ok"}])
        cc.chat("hi", episode())
        self.assertIn("\"look_at\": to see the picture", self.asked[0]["prompt"])

    def test_no_stills_says_so(self):
        self.fake([{"reply": "Let me look.", "look_at": [{"from": "7:00", "to": "8:00"}]}])
        reply, acts, *_ = cc.chat("they hold hands", episode(), look=lambda a, b: [])
        self.assertIn("couldn't take stills", reply)
        self.assertEqual(len(self.asked), 1)

    def test_without_a_way_to_look_nothing_breaks(self):
        self.fake([{"reply": "ok", "look_at": [{"from": "7:00", "to": "8:00"}]}])
        reply, acts, *_ = cc.chat("they hold hands", episode())
        self.assertEqual(reply, "ok")

    def test_what_it_may_look_at(self):
        self.assertEqual(cc.look_spans([{"from": "0:00", "to": "10:00"}]), [(0.0, 600.0)])
        self.assertEqual(cc.look_spans([{"from": "7:24", "to": "7:24"}]), [(434.0, 454.0)])
        self.assertEqual(cc.look_spans([{"from": "0:00", "to": "1:00:00"}]), [(0.0, 1200.0)])
        self.assertEqual(cc.look_spans([{"from": "5:00", "to": "6:00"}, {"from": "1:00", "to": "2:00"},
                                        {"from": "5:30", "to": "7:00"}]),
                         [(60.0, 120.0), (300.0, 420.0)])
        self.assertEqual(cc.look_spans([{"from": "40:00", "to": "50:00"}], dur=2580.0),
                         [(2400.0, 2580.0)])
        self.assertEqual(cc.look_spans([{"from": "soon", "to": "later"}, "x"]), [])


class SameSexAffectionInThePicture(unittest.TestCase):

    def test_reported_for_a_same_sex_couple_only(self):
        o = engine.full_opts({"samesex": True, "kiss_ss": "all"})
        f = {"what": "couple affection", "level": "n/a", "why": "holding hands"}
        self.assertEqual(engine._pic_wanted(dict(f, who="two women"), o),
                         "Same-sex affection · two women")
        self.assertEqual(engine._pic_wanted(dict(f, who="two men"), o), "Same-sex affection · two men")
        self.assertIsNone(engine._pic_wanted(dict(f, who="man & woman"), o))
        self.assertIsNone(engine._pic_wanted(dict(f, who="n/a"), o))
        self.assertIsNone(engine._pic_wanted(dict(f, who="two women"),
                                             engine.full_opts({"samesex": False})))

    def test_asked_for_even_when_kisses_are_already_cut(self):
        w = engine.picture_wanted({"samesex": True, "kiss_ss": "all"})
        self.assertIn("holding hands", w)
        self.assertIn("context shows they're a couple", w)
        self.assertNotIn("holding hands", engine.picture_wanted({"samesex": False}))

    def test_judged_by_context(self):
        self.assertIn("couple affection", cc.PIC_KINDS)
        self.assertIn("Judge it by the context", cc.PIC_RULES)
        self.assertIn("parent and child", cc.PIC_RULES)

    def test_its_own_colour(self):
        import importlib.machinery
        import importlib.util
        loader = importlib.machinery.SourceFileLoader("cv_ui", str(support.ROOT / "CleanView.pyw"))
        ui = importlib.util.module_from_spec(importlib.util.spec_from_loader("cv_ui", loader))
        loader.exec_module(ui)
        self.assertEqual(ui.chip_color("Same-sex affection · two women"), ui.CHIP["Same-sex"])


class Stills(unittest.TestCase):

    def test_the_whole_videos_sheets_are_used_when_there(self):
        work = Path(tempfile.mkdtemp())
        (work / "sheets").mkdir()
        for k in range(1, 6):
            (work / "sheets" / f"sheet_{k:04d}.jpg").write_bytes(b"jpg")
        got = engine.chat_sheets("none.mkv", work, 50, 100)
        self.assertEqual([(Path(p).name, t) for p, t in got],
                         [("sheet_0002.jpg", 40.0), ("sheet_0003.jpg", 80.0)])

    @unittest.skipUnless(support.FFMPEG, "no ffmpeg here")
    def test_just_that_stretch_otherwise(self):
        work = Path(tempfile.mkdtemp())
        video = work / "v.mkv"
        subprocess.run([support.FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i",
                        "testsrc=size=160x120:rate=10:duration=100", str(video)], check=True,
                       capture_output=True)
        got = engine.chat_sheets(video, work, 10, 90)
        self.assertEqual([t for p, t in got], [10.0, 50.0, 90.0][:len(got)])
        self.assertGreaterEqual(len(got), 2)
        self.assertTrue(all(Path(p).exists() for p, t in got))
        self.assertEqual(engine.chat_sheets(video, work, 10, 90), got)    # made once


if __name__ == "__main__":
    unittest.main()
