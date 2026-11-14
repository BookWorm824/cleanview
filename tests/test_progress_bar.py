"""The green bar shows real overall progress (1.18.99; the owner, through CleanView Play: "the
green bar when you are cleaning jumps to about two thirds on the early steps being finish but
then it takes the whole rest of the video like 45 mins to finish the rest"). Each step's share
of the bar is the time it's expected to take: this PC's remembered speed, else a laptop's
(`STEP_PACE`); work saved from before gets a sliver; telling voices apart has its own part and
moves while it works."""
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import support
import test_timing as T
from test_overlap import LINES, OPTS, Recorder

import cleanview as engine
import cleanview_ai as ai

EPISODE = 43 * 60        # a Castle episode


def laptop_bar(pace=None, saved=(), local=True):
    """The bar as analyze lays it out for her laptop's usual settings (the AI helper reads,
    picture AI, same-sex ticked)."""
    lines = "lines+local+talk" if local else "lines+claude"
    keys = {"asr": "asr", "snd": "snd", "lang": "lang", "vis": "vis+ai", "look": "look",
            "voices": "voices", "lines": lines, "end": "end"}
    order = ["asr", "snd", "lang", "vis", "look", "voices", "lines", "pics", "end"]
    secs = {k: engine.step_secs(keys[k], EPISODE, pace) for k in keys}
    return engine.bar_shares(order, secs, saved)


class Shares(unittest.TestCase):
    def test_the_slow_steps_get_most_of_the_bar(self):
        bar = laptop_bar()
        b, w = bar["vis"]
        self.assertLess(b + w, 0.35)            # the picture scan done: about a quarter, not 73%
        self.assertGreater(bar["lines"][1], 0.45)       # the reading: about half
        # her Castle S2E6 report: listening, subtitles and the picture were 12 of 47 minutes
        self.assertAlmostEqual(b + w, 12.2 / 47, delta=0.06)

    def test_the_old_bar_was_wrong_this_way(self):
        old = {"asr": 0.35, "snd": 0.08, "lang": 0.01, "vis": 0.45, "look": 0.08,
               "lines": 0.12, "end": 0.03}
        self.assertGreater((old["asr"] + old["snd"] + old["lang"] + old["vis"])
                           / sum(old.values()), 0.7)

    def test_in_order_with_no_gaps_and_full(self):
        bar = laptop_bar()
        acc = 0.0
        for k in ["asr", "snd", "lang", "vis", "look", "voices", "lines", "pics", "end"]:
            b, w = bar[k]
            self.assertAlmostEqual(b, acc)
            acc += w
        self.assertAlmostEqual(acc, 1.0)
        self.assertEqual(bar["pics"][1], 0.0)            # a step that doesn't run gets nothing

    def test_this_pcs_own_speed_wins(self):
        fast = laptop_bar({"lines+local+talk": 0.05, "vis+ai": 0.3})
        self.assertGreater(fast["vis"][1], fast["lines"][1])
        # an older remembered "lines+local" stands in for the reading with conversations
        older = laptop_bar({"lines+local": 0.05})
        self.assertLess(older["lines"][1], laptop_bar()["lines"][1])

    def test_saved_work_gets_a_sliver(self):
        bar = laptop_bar(saved={"asr", "vis"})
        self.assertLess(bar["asr"][1], 0.01)
        self.assertLess(bar["vis"][1], 0.01)
        self.assertGreater(bar["lines"][1], 0.6)

    def test_every_step_that_runs_shows(self):
        bar = laptop_bar(local=False)                    # the cloud reads quickly
        self.assertGreaterEqual(bar["lang"][1], engine.BAR_LEAST * 0.9)
        self.assertGreaterEqual(bar["lines"][1], engine.BAR_LEAST * 0.9)

    def test_laid_out_again_from_where_it_is(self):
        secs = {"lang": 30, "vis": 300, "lines": 900, "end": 30}
        bar = engine.bar_shares(["lang", "vis", "lines", "end"], secs, start=0.2)
        self.assertAlmostEqual(bar["lang"][0], 0.2)
        self.assertAlmostEqual(sum(w for _, w in bar.values()), 0.8)

    def test_step_secs_falls_back(self):
        self.assertAlmostEqual(engine.step_secs("pics+claude", 100), 15)
        self.assertAlmostEqual(engine.step_secs("lines+gemini", 100), 4)
        self.assertAlmostEqual(engine.step_secs("pics+claude", 100, {"pics+claude": 0.5}), 50)
        self.assertAlmostEqual(engine.step_secs("something new", 100), 5)

    def test_voices_timed_for_next_time(self):
        now = [0.0]
        tl = engine.TimeLeft(EPISODE, {}, clock=lambda: now[0])
        tl.base = {"voices": (0.4, 0.1), "lines": (0.5, 0.5)}
        tl.left(0.4)
        now[0] = 240.0
        tl.left(0.4 + 0.1 * 0.999)
        self.assertAlmostEqual(tl.paces()["voices"], 240 / 0.999 / EPISODE, places=4)


@T.needs_ffmpeg
class WholeScan(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.video = support.SANDBOX / "Bar Show S01E01.mp4"
        if not cls.video.exists():
            T.ffmpeg("-f", "lavfi", "-i", "testsrc=size=64x48:rate=10:duration=12", "-f",
                     "lavfi", "-i", "sine=frequency=300:duration=12", "-c:v", "libx264",
                     "-c:a", "aac", "-shortest", cls.video)

    def run_analyze(self, ai_starts=True, voices_secs=2.5):
        rec, said = Recorder(), []
        work = Path(tempfile.mkdtemp(dir=support.SANDBOX))
        n = int(12 * engine.VISUAL_FPS)
        vis = {"version": engine.PICTURE_VERSION, "fps": engine.VISUAL_FPS,
               "classes": list(engine.KEEP), "scores": [[0.0] * len(engine.KEEP)] * n,
               "lum": [[120.0, 40.0]] * n, "lifted": [], "notes": []}
        asr = [{"t": w, "s": 1.0 + 0.4 * k, "e": 1.3 + 0.4 * k}
               for k, w in enumerate("line number one said here".split())]
        voices = [{"g": "m", "spk": 1} for _ in LINES]
        with mock.patch.object(ai, "start_ollama", lambda wait=20: ai_starts), \
                mock.patch.object(ai, "choose_models", lambda: True), \
                mock.patch.object(ai, "clip_ready", lambda: False), \
                mock.patch.object(ai, "free_memory", lambda: None), \
                mock.patch.object(ai, "dialogue_lines", lambda *a, **k: [dict(l) for l in LINES]), \
                mock.patch.object(ai, "romance_scenes", lambda *a, **k: []), \
                mock.patch.object(ai, "who_is_who", lambda *a, **k: {}), \
                mock.patch.object(engine, "load_pace", lambda: {}), \
                mock.patch.object(engine, "save_pace", lambda new: None), \
                mock.patch.object(engine, "available_memory_gb", lambda: 16.0), \
                mock.patch.object(engine, "load_listeners", lambda *a: [None]), \
                mock.patch.object(engine, "transcribe", rec.span("listen", 0.3, asr)), \
                mock.patch.object(engine, "fetch_subtitles",
                                  lambda *a, **k: ([], "", None, "none online")), \
                mock.patch.object(engine, "visual_scan", rec.span("pictures", 0.3, vis)), \
                mock.patch.object(engine, "find_voices", rec.span(
                    "voices", voices_secs, lambda: [dict(v) for v in voices])), \
                mock.patch.object(engine, "find_lines", lambda *a, **k: ([], "the AI helper")), \
                mock.patch.object(engine, "make_thumbs", lambda *a, **k: None):
            engine.analyze(str(self.video), str(work), groups=["swearing"], opts=OPTS,
                           progress=lambda f, m: said.append((f, m)), log=lambda m: None)
        return json.loads((work / "analysis.json").read_text()), said

    def forward(self, said):
        back = [(said[i - 1], said[i]) for i in range(1, len(said))
                if said[i][0] < said[i - 1][0] - 1e-9]
        self.assertEqual(back, [])

    def test_voices_move_and_the_bar_goes_forward(self):
        st, said = self.run_analyze()
        self.forward(said)
        v = [f for f, m in said if m.startswith("Telling voices apart")]
        self.assertGreaterEqual(len(set(v)), 2, said)    # it moved while voices were told apart
        self.assertTrue(st["voices"])
        self.assertIn("voices", st["scan"]["minutes"])
        pics = next(f for f, m in said if m.startswith("Watching the picture"))
        self.assertLess(pics, 0.5)
        reading = [f for f, m in said if m.startswith("Telling voices")]
        self.assertLess(reading[0], 0.7)

    def test_voices_that_fail_are_said(self):
        with mock.patch.object(engine, "name_voices", side_effect=RuntimeError("no sound")):
            st, said = self.run_analyze(voices_secs=0.1)
        self.assertTrue(any("Voices couldn't be told apart" in n for n in st["notes"]))
        self.forward(said)

    def test_no_ai_helper_bar_still_forward(self):
        st, said = self.run_analyze(ai_starts=False, voices_secs=0.1)
        self.forward(said)
        self.assertEqual(said[-1][0], 1.0)


if __name__ == "__main__":
    unittest.main()
