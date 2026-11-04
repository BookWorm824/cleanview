"""Lessons from the reports sent in on 2026-11-03 (My Fair Lady, Julie & Julia twice,
The Little Mermaid twice)."""
import unittest
from unittest import mock

import support  # noqa: F401  (sets up the sandbox first)

import cleanview as engine
import cleanview_ai as ai
import cleanview_claude as cc
import cleanview_learn as learn
import cvcore as cl


def heard(start, n, gap=0.5):
    return [{"t": f"word{k}" + ("." if k % 8 == 7 else ""), "s": start + k * gap,
             "e": start + k * gap + 0.3} for k in range(n)]


class SubtitlesThatStopHalfway(unittest.TestCase):
    """Julie & Julia: the subtitles found were only the first half ("CD1"), so nothing
    said after 0:59 of a two-hour movie was read for innuendo, and the chat couldn't
    see those lines."""

    def test_the_rest_is_filled_from_what_was_heard(self):
        cues = [{"s": 10.0 + 5 * k, "e": 13.0 + 5 * k, "text": f"Line {k}."} for k in range(20)]
        asr = heard(10.0, 200) + heard(3600.0, 200)
        lines = ai.dialogue_lines(cues, asr, engine.spoken_words)
        late = [l for l in lines if l["s"] >= 3600]
        self.assertTrue(late)
        self.assertTrue(all(l.get("heard") for l in late))
        self.assertEqual(len([l for l in lines if not l.get("heard")]), 20)
        self.assertEqual(lines, sorted(lines, key=lambda l: l["s"]))

    def test_ordinary_pauses_between_subtitles_arent_filled(self):
        cues = [{"s": 10.0 + 30 * k, "e": 13.0 + 30 * k, "text": f"Line {k}."} for k in range(10)]
        asr = heard(10.0, 600)
        lines = ai.dialogue_lines(cues, asr, engine.spoken_words)
        self.assertFalse([l for l in lines if l.get("heard")])

    def test_no_subtitles_is_unchanged(self):
        lines = ai.dialogue_lines([], heard(0.0, 16), engine.spoken_words)
        self.assertEqual(len(lines), 2)
        self.assertFalse([l for l in lines if l.get("heard")])


class ShorterSceneCuts(unittest.TestCase):
    """Lauren: "a shorter cut for all found scenes in general... that way you can tell more
    what is happening" (a 6½-minute cut of The Little Mermaid's ending; the phone ringing
    and the cat after Julie & Julia's sex scene can stay)."""

    def run_bounds(self, scenes, answer):
        def sheet(path, a, b, work, name):
            return "sheet.jpg", (b - a) / 30.0
        with mock.patch.object(engine, "bounds_sheet", sheet), \
                mock.patch.object(engine, "snap_to_shots", lambda *a, **k: None), \
                mock.patch.object(engine.cc, "scene_bounds", lambda items, progress=None:
                                  {i: answer for i, _, _ in items}):
            return engine.refine_bounds("v.mkv", ".", 7200.0, scenes, [])

    def test_a_long_cut_can_be_split_into_just_the_trouble(self):
        sc = {"id": 1, "s": 100.0, "e": 400.0, "kind": ["Sex scene"], "cut": True}
        out, changed = self.run_bounds([sc], ([(3, 8), (20, 22)], False, False))
        self.assertEqual(changed, 1)
        self.assertEqual(len(out), 2)
        self.assertLess(sum(s["e"] - s["s"] for s in out), 150)
        self.assertEqual([s["id"] for s in out], [1, 2])

    def test_a_short_cut_is_only_ever_made_longer(self):
        sc = {"id": 1, "s": 100.0, "e": 110.0, "kind": ["Violence"], "cut": True}
        out, _ = self.run_bounds([sc], ([(14, 15)], False, False))
        self.assertEqual(len(out), 1)
        self.assertLessEqual(out[0]["s"], 100.0)
        self.assertGreaterEqual(out[0]["e"], 110.0)

    def test_a_fight_keeps_a_wider_edge(self):
        calm = {"id": 1, "s": 100.0, "e": 400.0, "kind": ["Drinking"], "cut": True}
        fight = {"id": 1, "s": 100.0, "e": 400.0, "kind": ["Violence"], "cut": True}
        a, _ = self.run_bounds([calm], ([(5, 10)], False, False))
        b, _ = self.run_bounds([fight], ([(5, 10)], False, False))
        self.assertGreater(b[0]["e"] - b[0]["s"], a[0]["e"] - a[0]["s"])

    def test_not_seen_leaves_it_alone(self):
        sc = {"id": 1, "s": 100.0, "e": 400.0, "kind": ["Drinking"], "cut": True}
        with mock.patch.object(engine, "bounds_sheet", lambda *a: ("x.jpg", 10.0)), \
                mock.patch.object(engine, "snap_to_shots", lambda *a, **k: None), \
                mock.patch.object(engine.cc, "scene_bounds", lambda items, progress=None:
                                  {i: None for i, _, _ in items}):
            out, changed = engine.refine_bounds("v.mkv", ".", 7200.0, [sc], [])
        self.assertEqual((out[0]["s"], out[0]["e"], changed), (100.0, 400.0, 0))

    def test_the_answer_is_read_into_parts(self):
        reply = {"scenes": [{"scene": 1, "seen": True, "continues_before": False,
                             "continues_after": True,
                             "parts": [{"first_tile": 20, "last_tile": 22},
                                       {"first_tile": 3, "last_tile": 8},
                                       {"first_tile": 9, "last_tile": 11}]},
                            {"scene": 2, "seen": False, "parts": [],
                             "continues_before": False, "continues_after": False}]}
        with mock.patch.object(cc, "ask", return_value=(reply, None)):
            got = cc.scene_bounds([("a", "Violence", "1.jpg"), ("b", "Smoking", "2.jpg")])
        self.assertEqual(got["a"], ([(3, 11), (20, 22)], False, True))
        self.assertIsNone(got["b"])


class KeptKindsJoinedToOthers(unittest.TestCase):
    """Julie & Julia: she usually keeps drinking scenes, and a drinking scene joined to a
    sex scene left the whole sex scene in."""

    def test_a_scene_is_only_kept_when_every_kind_in_it_usually_is(self):
        for _ in range(4):
            learn.record("julie", [], [], [], [{"kind": ["Drinking"], "cut": False,
                                                "_shown": True}], [False], [], [], [])
        later = [{"kind": ["Drinking", "Sex scene"], "cut": True},
                 {"kind": ["Drinking"], "cut": True}]
        learn.apply("julie", [], [], later, [])
        self.assertTrue(later[0]["cut"])
        self.assertFalse(later[1]["cut"])


class Words(unittest.TestCase):
    def found(self, text):
        words = [w for w in (cl.norm(w) for w in text.split()) if w]
        return [" ".join(words[i:j]) for i, j, _ in cl.find_language(words, list(cl.CATS))]

    def test_dickens_said_as_an_oath(self):
        """Lauren: "the word dickens should still be removed" (Julie & Julia)."""
        for text, phrase in (("How the dickens did you get in?", "how the dickens"),
                             ("It scared the dickens out of me", "the dickens out of"),
                             ("It hurts like the dickens", "like the dickens"),
                             ("Oh, dickens!", "oh dickens"),
                             ("What the dickens is that?", "what the dickens")):
            with self.subTest(text=text):
                self.assertEqual(self.found(text), [phrase])

    def test_dickens_the_writer_is_fine(self):
        for text in ("Charles Dickens", "the dickens novel", "I love Dickens",
                     "A Dickens Christmas", "Oh, the Dickens museum", "Oh, Dickens novels"):
            with self.subTest(text=text):
                self.assertEqual(self.found(text), [])

    def test_sex_meaning_men_or_women(self):
        """My Fair Lady: "Let the others of my sex", "We are a marvelous sex"."""
        for text in ("Let the others of my sex tie the knot", "We are a marvelous sex"):
            with self.subTest(text=text):
                self.assertIsNone(engine.LINE_WORDS["sexref"].search(text))
                self.assertEqual(cl.sex_score([cl.norm(w) for w in text.split()]), 0)
        self.assertIsNotNone(engine.LINE_WORDS["sexref"].search("They had sex"))


class NewLauncherAfterAnUpdate(unittest.TestCase):
    """An update that brings a new launcher.pyw starts it at once, not on the next start."""

    def run_update(self, old, new):
        import io
        import json
        import tempfile
        from pathlib import Path
        from test_own_exe import load_launcher
        launcher = load_launcher()
        with tempfile.TemporaryDirectory() as d:
            here = Path(d)
            (here / "version.json").write_text('{"version": "1.0.0", "files": []}')
            (here / "launcher.pyw").write_text(old)
            files = {"version.json": json.dumps({"version": "1.0.1", "files": [
                "launcher.pyw", "CleanView.pyw"]}), "launcher.pyw": new, "CleanView.pyw": "x = 1"}

            def urlopen(url, timeout=0):
                return io.BytesIO(files[url.rsplit("/", 1)[1]].encode("utf8"))
            with mock.patch.object(launcher, "HERE", here),                     mock.patch.object(launcher.urllib.request, "urlopen", urlopen):
                self.assertEqual(launcher.update(), "1.0.1")
            return launcher.LAUNCHER_CHANGED

    def test_a_changed_launcher_is_noticed(self):
        self.assertTrue(self.run_update("old = 1", "new = 2"))

    def test_the_same_launcher_isnt(self):
        self.assertFalse(self.run_update("same = 1", "same = 1"))


if __name__ == "__main__":
    unittest.main()
