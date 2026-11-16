"""The taught picture check (1.18.106; the owner, 2026-11-15: "picture first", then "Yes, build
it"): a small check per kind of scene, taught from what Claude judged in 151 past cleans, finds
fights, blood, kisses and bed scenes the descriptions miss; its finds count only once the AI
helper's closer look agrees."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np

import support  # noqa: F401  (sets up the sandbox first)
import cleanview as engine
import cleanview_ai as ai

ON = engine.full_opts({"violence": True, "gore": True, "graphic": True, "sex": True,
                       "kiss_os": "all", "kiss_ss": "all"})


def rows(n, hot=(), key="taught_fight_0", today=None):
    """n frames a second apart; the taught part +3 (0.95 alone) for the seconds in hot, else -3."""
    out = []
    for t in range(n):
        r = {"fight": 0.1, "gore": 0.1, "kiss": 0.1, "bed": 0.1, "kiss_mf": 0.8,
             "kiss_mm": 0.1, "kiss_ff": 0.1, key: 3.0 if t in hot else -3.0}
        if today and t in today:
            r["fight"] = 0.9
        out.append(r)
    return {"t": [float(t) for t in range(n)], "scores": out}


def checks(rows_each=1):
    """Stand-in checks: the scores in rows() are the whole story (weights unused here)."""
    z = np.zeros((rows_each, 512), np.float32)
    return {"fight": (z, 0.0, 0.8), "kiss": (z, 0.0, 0.9)}


class Shipped(unittest.TestCase):
    def test_four_kinds_with_weights(self):
        ai._taught = None
        checks = ai.taught_checks()
        self.assertEqual(set(checks), {"fight", "gore", "kiss", "bed"})
        for w, b, th in checks.values():
            self.assertEqual(w.shape[1], 512)
            self.assertEqual(len(w) % 2, 1)          # the still, and as many on either side
            self.assertTrue(0.3 <= th < 1.0)
        self.assertIn("picture_taught.json",
                      json.loads((engine.HERE / "version.json").read_text())["files"])

    def test_scores_for_a_frame(self):
        e = np.random.default_rng(1).normal(size=(3, 512)).astype(np.float32)
        e /= np.linalg.norm(e, axis=1, keepdims=True)
        s = ai.taught_scores(e)
        self.assertEqual(set(s), {f"taught_{c}_{j}" for c, (w, _, _) in ai.taught_checks().items()
                                  for j in range(len(w))})
        self.assertTrue(all(abs(v) < 100 for v in s.values()))


class Candidates(unittest.TestCase):
    def setUp(self):
        ai._taught = checks()

    def tearDown(self):
        ai._taught = None

    def test_a_run_is_a_find(self):
        cands = ai.clip_candidates(rows(60, hot=range(20, 27)), ["fight"])
        self.assertEqual(len(cands), 1)
        c = cands[0]
        self.assertTrue(c["taught"])
        # smoothed with the stills 2 s either side, 22-24 s are hits (the edges, 0.725, aren't)
        self.assertEqual((c["cat"], c["s"], c["e"]), ("fight", 21.0, 25.0))
        self.assertEqual(sorted(c["frames"]), [22.0, 23.0, 24.0])

    def test_a_blip_isnt(self):
        self.assertEqual(ai.clip_candidates(rows(60, hot={30}), ["fight"]), [])
        self.assertEqual(ai.clip_candidates(rows(60, hot={30, 31}), ["fight"]), [])

    def test_only_kinds_looked_for(self):
        self.assertEqual(ai.clip_candidates(rows(60, hot=range(20, 27)), ["kiss"]), [])

    def test_not_twice_where_the_descriptions_found_it(self):
        cands = ai.clip_candidates(rows(60, hot=range(20, 27), today=range(21, 25)), ["fight"])
        self.assertEqual([c.get("taught", False) for c in cands], [False])

    def test_too_dark_left_out(self):
        lum = [[10, 5]] * 120          # every frame too dark (two a second)
        self.assertEqual(ai.clip_candidates(rows(60, hot=range(20, 27)), ["fight"], lum=lum), [])

    def test_who_is_kissing(self):
        c = ai.clip_candidates(rows(60, hot=range(20, 27), key="taught_kiss_0"), ["kiss"])[0]
        self.assertAlmostEqual(c["who"]["kiss_mf"], 0.8)

    def test_the_stills_either_side(self):
        """Taught on a still with the ones 2 s before and after: here only the one after
        counts, so the run comes 2 s earlier."""
        ai._taught = checks(3)
        clip = rows(60, hot=range(22, 29), key="taught_fight_2")
        for r in clip["scores"]:
            r.update(taught_fight_0=0.0, taught_fight_1=0.0)
        c = ai.clip_candidates(clip, ["fight"])[0]
        self.assertEqual((c["s"], c["e"]), (21.0, 25.0))

    def test_without_the_file_nothing_changes(self):
        saved = ai.TAUGHT_FILE
        try:
            ai.TAUGHT_FILE, ai._taught = Path(tempfile.gettempdir()) / "no_such_taught.json", None
            self.assertEqual(ai.clip_candidates(rows(60, hot=range(20, 27)), ["fight"]), [])
            self.assertEqual(ai.taught_scores(np.ones((1, 512), np.float32)), {})
        finally:
            ai.TAUGHT_FILE, ai._taught = saved, None


class Signature(unittest.TestCase):
    def test_scans_redone_when_what_it_learned_changes(self):
        saved = ai.TAUGHT_FILE
        d = Path(tempfile.mkdtemp())
        try:
            copy = d / "picture_taught.json"
            shutil.copy(saved, copy)
            ai.TAUGHT_FILE, ai._taught = copy, None
            before = ai.clip_signature()
            data = json.loads(copy.read_text())
            data["probes"]["fight"]["th"] = 0.85
            copy.write_text(json.dumps(data))
            ai._taught = None
            self.assertNotEqual(ai.clip_signature(), before)
        finally:
            ai.TAUGHT_FILE, ai._taught = saved, None
            shutil.rmtree(d, ignore_errors=True)


class OnlyWithTheCloserLook(unittest.TestCase):
    def cand(self, verdict=None):
        c = {"cat": "fight", "s": 10.0, "e": 20.0, "peak": 0.9, "who": {}, "frames": [12, 14, 16],
             "taught": True}
        if verdict is not None:
            c["verdict"] = verdict
        return c

    def test_kept_when_the_ai_helper_agrees(self):
        v = {"keep": True, "who": "?", "level": "combat", "what": "two men fight"}
        scenes = engine.decide_picture_scenes([self.cand(v)], ON, True)
        self.assertEqual([(s["kind"], s["sure"], s.get("taught")) for s in scenes],
                         [(["Violence"], True, True)])

    def test_dropped_otherwise(self):
        for verdict, have_ai in ((None, False), (None, True),
                                 ({"keep": False, "level": "combat"}, True),
                                 ({"keep": True, "error": "timed out"}, True)):
            self.assertEqual(engine.decide_picture_scenes([self.cand(verdict)], ON, have_ai), [],
                             (verdict, have_ai))

    def test_found_by_the_descriptions_as_before(self):
        c = self.cand()
        del c["taught"]
        scenes = engine.decide_picture_scenes([c], ON, False)
        self.assertEqual([s["sure"] for s in scenes], [False])     # offered unticked


class GarbledAnswer(unittest.TestCase):
    """Person of Interest S3E2 (1.18.106): two taught blood finds kept as gore, the AI helper's
    description just "none of these"; asked again it said no to both."""

    def look(self, answer):
        c = {"cat": "gore", "s": 10.0, "e": 20.0, "peak": 0.9, "who": {}, "frames": [12],
             "taught": True}
        saved, ai.chat = ai.chat, lambda *a, **k: answer
        try:
            ai.second_look([c], lambda c: ["a frame"])
        finally:
            ai.chat = saved
        return c

    def test_dropped_not_cut(self):
        """Offered unticked in 1.18.106; dropped since 1.18.112 (the owner, after Forest Gump's
        27 "graphic violence (hard to see)": "Drop the taught ones")."""
        c = self.look({"see": "none of these", "visible": ["organs or entrails"],
                       "medical": False, "clear": True})
        self.assertTrue(c["verdict"]["unclear"])
        self.assertEqual(engine.decide_picture_scenes([c], ON, True), [])

    def test_hard_to_see_taught_dropped_found_by_descriptions_offered(self):
        c = {"cat": "gore", "s": 10.0, "e": 20.0, "peak": 0.9, "who": {}, "frames": [12],
             "taught": True, "verdict": {"keep": True, "unclear": True, "level": "blood",
                                         "what": "hard to tell"}}
        self.assertEqual(engine.decide_picture_scenes([c], ON, True), [])
        del c["taught"]                       # the picture AI's own descriptions found it
        self.assertEqual([s["sure"] for s in engine.decide_picture_scenes([c], ON, True)], [False])

    def test_a_real_description_as_before(self):
        c = self.look({"see": "A body with its insides showing on an autopsy table",
                       "visible": ["organs or entrails"], "medical": False, "clear": True})
        self.assertNotIn("unclear", c["verdict"])
        self.assertEqual([s["sure"] for s in engine.decide_picture_scenes([c], ON, True)], [True])

    def test_a_plain_no_dropped(self):
        c = self.look({"see": "no", "visible": [], "medical": False, "clear": True})
        self.assertEqual(engine.decide_picture_scenes([c], ON, True), [])


if __name__ == "__main__":
    unittest.main()
