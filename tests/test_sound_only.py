"""A scene can mute its sound and keep its picture (1.18.154; the owner: "we can keep more of the
scene visual and cut audio if needed", then "yes all 3"): a "Mute the sound only" box on each
scene's card, sound-only violence offered that way, and taught scenes that mute ("action":
"mute"; Criminal Minds S1E20's screams between the creek cuts)."""
import json
import tempfile
import tkinter as tk
import unittest
from pathlib import Path

import support
import test_timing as T
import test_filter_groups as tfg
from test_ui import ui

import cleanview as engine
import cleanview_learn as learn


class TheEngine(unittest.TestCase):
    def test_heard_only_is_sound_only(self):
        gun = next(k for k in engine.TRACKED if "gunshot" in k.lower() or "gunfire" in k.lower())
        snd = {"labels": engine.TRACKED, "t": [i * 1.5 for i in range(10, 16)],
               "p": [[0.95 if k == gun else 0.0 for k in engine.TRACKED] for _ in range(6)]}
        got = engine.violence_scenes(snd, [])
        self.assertTrue(got)
        self.assertTrue(all(sc["mute_only"] for sc in got))

    def test_seen_too_is_a_cut(self):
        heard = {"s": 10.0, "e": 20.0, "kind": ["Violence"], "why": "gunfire", "mute_only": True}
        seen = {"s": 15.0, "e": 25.0, "kind": ["Graphic violence"], "why": "blood"}
        merged = engine.merge_scenes([heard, seen])
        self.assertEqual(len(merged), 1)
        self.assertFalse(merged[0]["mute_only"])
        both_heard = engine.merge_scenes([heard, dict(heard, s=19.0, e=24.0)])
        self.assertTrue(both_heard[0]["mute_only"])

    def test_a_taught_scene_can_mute(self):
        with open(support.ROOT / "shared_learned.json", encoding="utf-8") as f:
            muting = [sc for sc in json.load(f)["shows"]["criminal-minds"]["scenes"]
                      if sc.get("action") == "mute"]
        self.assertEqual(len(muting), 2)
        lines = [{"s": 2294.39, "e": 2296.9, "text": "IT'S OVER THERE. COME ON, LET'S GO."},
                 {"s": 2345.12, "e": 2346.9, "text": "NO!"},
                 {"s": 2351.21, "e": 2353.9, "text": "IT'S JUST THE TWO OF US OUT HERE."},
                 {"s": 2369.86, "e": 2372.2, "text": "IT'S CLEAR. NOBODY IN THE CAR."},
                 {"s": 2374.26, "e": 2376.5, "text": "WE'RE GOING INTO THE WOODS. KEEP YOU POSTED."},
                 {"s": 2376.62, "e": 2379.0, "text": "Elle: WHICH WAY TO THE WATER? IT'S OVER THERE."},
                 {"s": 2389.46, "e": 2392.0, "text": "THAT'S COMING FROM UP OVER THERE."},
                 {"s": 2441.81, "e": 2444.6, "text": "MARK GREGORY, FBI! PUT IT DOWN!"}]
        got = sorted(learn.title_scenes("criminal-minds@adults", "Criminal Minds", lines,
                                        {"disturbing"}, episode=(1, 20)), key=lambda s: s["s"])
        sound = [(round(s["s"], 1), round(s["e"], 1)) for s in got if s.get("mute_only")]
        self.assertEqual(sound, [(2354.0, 2369.6), (2379.2, 2386.0)])
        self.assertTrue(all(not s.get("mute_only") for s in got
                            if (round(s["s"], 1), round(s["e"], 1)) not in sound))


def loudest(path, start, secs):
    """The loudest sound (dB) from start for secs."""
    import re
    import subprocess
    out = subprocess.run([support.FFMPEG, "-hide_banner", "-ss", str(start), "-t", str(secs),
                          "-i", str(path), "-vn", "-af", "volumedetect", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    m = re.search(r"max_volume: (-?[\d.]+|-inf) dB", out)
    return -999.0 if not m or m.group(1) == "-inf" else float(m.group(1))


@T.needs_ffmpeg
class Saved(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.video = support.SANDBOX / "Sound Only Show S01E01.mp4"
        if not cls.video.exists():
            T.ffmpeg("-f", "lavfi", "-i", "testsrc=size=64x48:rate=10:duration=30", "-f", "lavfi",
                     "-i", "sine=frequency=440:duration=30", "-c:v", "libx264", "-c:a", "aac",
                     "-shortest", cls.video)

    def render(self, cuts):
        work = Path(tempfile.mkdtemp(dir=support.SANDBOX))
        info = engine.probe(self.video)
        st = {"path": str(self.video), "info": info, "duration": info["duration"],
              "groups": [], "mutes": [], "scenes": [], "lines": [], "notes": [], "cues": []}
        (work / "analysis.json").write_text(json.dumps(st))
        res = engine.render(work, work / "Clean", cuts, lines=[], words=[],
                            encoders=[engine.ENCODERS[-1]], log=lambda m: None)
        rep = (Path(res["folder"]) / "Reports" /
               "Sound Only Show S01E01 - CleanView report.txt").read_text("utf8")
        return res, rep

    def test_sound_muted_picture_kept(self):
        scene = {"s": 10.0, "e": 18.0, "kind": ["Violence"], "why": "screams", "mute_only": True}
        res, rep = self.render([scene])
        self.assertAlmostEqual(engine.probe(res["out"])["duration"], 30.0, delta=0.6)
        self.assertIn("muted the sound for 8 seconds, picture kept", rep)
        self.assertIn("1 scene(s) had only their sound muted", rep)
        self.assertNotIn("instead of a long silence", rep)       # an 8 s mute isn't cut
        self.assertLess(loudest(res["out"], 11.0, 6.0), -50)     # silent there
        self.assertGreater(loudest(res["out"], 2.0, 6.0), -30)    # the tone plays elsewhere

    def test_a_cut_still_cuts(self):
        scene = {"s": 10.0, "e": 18.0, "kind": ["Violence"], "why": "a fight"}
        res, rep = self.render([scene])
        self.assertAlmostEqual(engine.probe(res["out"])["duration"], 22.0, delta=0.6)


class TheCard(tfg.FilterGroups):
    """The scene card's "Mute the sound only" box."""

    def test_the_box(self):
        self.open([self.review()])
        boxes = [w for w in tfg.every(self.app, tk.Widget)
                 if w.winfo_class() == "TCheckbutton" and w.cget("text") == ui.SOUND_ONLY_BOX]
        self.assertTrue(boxes)
        _, _, sc = self.app.scene_vars[0]
        before = self.app._clean_bytes()
        box = boxes[0]
        box.invoke()
        self.settle(0.05)
        tick = [w for w in tfg.every(box.master, tk.Widget) if w.winfo_class() == "TCheckbutton"][0]
        self.assertTrue(tick.cget("text").startswith(ui.SOUND_ONLY_TICK))
        self.assertTrue(sc["mute_only"])
        self.assertGreaterEqual(self.app._clean_bytes(), before)   # nothing cut out now
        box.invoke()
        self.settle(0.05)
        self.assertFalse(sc["mute_only"])
        self.assertTrue(tick.cget("text").startswith("Cut"))


# only the card test here, not every FilterGroups test again
for _name in [n for n in dir(tfg.FilterGroups) if n.startswith("test_")]:
    setattr(TheCard, _name, None)

if __name__ == "__main__":
    unittest.main()
