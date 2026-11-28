"""The Resident S2E18, Emergency Contact (1.18.176, 2026-11-27; the owner: "did not catch
everything on clean up", then "Teach the dating lines"). Kit's dating around went through with
sleeping around ticked: "Another FOW?" (flavor of the week), "I write my dance card in pencil",
"my current flavor of the week". The two long lines are taught for the show; the two short
"FOW?" exchanges only for this episode, as sound-muted stretches: taught as lines, "Haven't you
had enough of those? FOW?" would also have muted an ordinary "Haven't you had enough of those?"
anywhere in the show."""
import json
import unittest
from pathlib import Path

import support  # noqa: F401  (must come first)
import cleanview as engine
import cleanview_learn as learn

SHARED = json.loads((Path(engine.__file__).parent / "shared_learned.json").read_text("utf8"))

LINES = [(731.0, "When he says friend, does he mean good friend?"),
         (734.0, "No. Stop it. Another FOW?"), (736.0, "Haven't you had enough of those? FOW?"),
         (738.0, "What am I missing? Stop worrying about me."),
         (1043.0, "Nothing's more important than you."),
         (1045.0, "Listen, I'm sorry, I just got to ask. FOW?"),
         (1049.0, "If you don't tell me, it'll keep me up all night."),
         (1051.0, "Brett knows I write my dance card in pencil."),
         (1054.0, "He was asking if you were my current flavor of the week."),
         (1058.0, "As an ex-husband, I find it interesting that Brett cares.")]
DIALOGUE = [{"s": s, "e": s + 1.8, "text": t} for s, t in LINES]


class Episode18(unittest.TestCase):
    def scenes(self, ticked, episode=(2, 18)):
        return learn.title_scenes("the-resident@adults", "The Resident", DIALOGUE, ticked,
                                  episode=episode)

    def test_fow_talk_muted(self):
        a, b = self.scenes(["casual"])
        for sc in (a, b):
            self.assertTrue(sc["mute_only"])
            self.assertEqual(sc["kind"], ["Sleeping around"])
        self.assertLess(a["s"], 734.0)
        self.assertLessEqual(a["e"], 738.0)                # not "What am I missing?"
        self.assertLess(b["s"], 1045.0)
        self.assertGreater(b["e"], 1055.0)
        self.assertLess(b["e"], 1058.0)                    # not "As an ex-husband..."

    def test_only_with_sleeping_around_and_only_this_episode(self):
        self.assertEqual(self.scenes(["sexref", "samesex"]), [])
        self.assertEqual(self.scenes(["casual"], episode=(2, 17)), [])

    def test_long_lines_taught_for_the_show(self):
        sh = SHARED["shows"]["the-resident"]
        for t in ("Brett knows I write my dance card in pencil.",
                  "He was asking if you were my current flavor of the week."):
            self.assertEqual(sh["muted_for"][learn.norm(t)], "casual", t)

    def test_ordinary_lines_arent_taught(self):
        sh = SHARED["shows"]["the-resident"]
        ll = learn.LearnedLines(sh["muted"])
        for t in ("Haven't you had enough of those?", "Listen, I'm sorry, I just got to ask.",
                  "What am I missing?", "Haven't you had enough of those cookies?"):
            self.assertIsNone(ll.match(learn.norm(t)), t)


class UndressingAfterAKiss(unittest.TestCase):
    """The opening scene was found as a passionate kiss; told only that, the closer look at
    where it ends stopped when the kissing did, and Julian undressing to her bra right after it
    (4 s) stayed in her clean copy ("there is a scene that Julian is undressing"). It's now told
    everything she removes."""

    def test_the_scene_edges_are_told_what_she_removes(self):
        import cleanview_claude as cc
        from unittest import mock
        seen = {}

        def ask(prompt, schema, **k):
            seen["prompt"] = prompt
            return {"scenes": [{"scene": 1, "seen": True, "parts": [{"first_tile": 3,
                                "last_tile": 20}], "continues_before": False,
                                "continues_after": False}]}, None
        o = engine.full_opts({"sex": True, "kiss_os": "passionate"})
        with mock.patch.object(cc, "ask", ask):
            cc.scene_bounds([(1, "Kiss · man & woman · passionate", "1.jpg")],
                            wanted=engine.picture_wanted(o))
        p = seen["prompt"]
        self.assertIn("sex scenes", p)
        self.assertIn("undressing", p)
        self.assertIn("underwear", p)
        with mock.patch.object(cc, "ask", ask):
            cc.scene_bounds([(1, "Kiss · man & woman · passionate", "1.jpg")])
        self.assertNotIn("not only what the scene was found for", seen["prompt"])

    def test_passed_on_from_the_picture_check(self):
        from unittest import mock
        got = {}

        def bounds(items, progress=None, wanted=None):
            got["wanted"] = wanted
            return {}
        sc = {"id": 1, "s": 192.0, "e": 218.0, "kind": ["Kiss · man & woman · passionate"],
              "cut": True}
        with mock.patch.object(engine, "bounds_sheet", lambda *a: ("1.jpg", 1.0)), \
                mock.patch.object(engine.cc, "scene_bounds", bounds), \
                mock.patch.object(engine, "snap_to_shots", lambda *a, **k: None):
            engine.refine_bounds("v.mp4", ".", 2600.0, [sc], [], wanted="- sex scenes")
        self.assertEqual(got["wanted"], "- sex scenes")
        src = Path(engine.__file__).read_text("utf8")
        self.assertRegex(src, r"say\(0\.9 \+ 0\.09 \* f, m\),\s+wanted=wanted\)")


class BedroomBeforeAndAfter(unittest.TestCase):
    """The owner: "any bedroom scenes that are any where near intimate scenes (after or before)
    need removed", and of the end of S2E18: "the edge of the bed, then ... julian getting
    dressed, then ... devon smiling, then ... them dancing (all those need removed)"."""

    def test_close_intimate_cuts_become_one(self):
        a = {"id": 1, "s": 2390.0, "e": 2435.0, "cut": True,
             "kind": ["Intimate scene · man & woman", "Kiss · man & woman · passionate"]}
        b = {"id": 2, "s": 2443.0, "e": 2477.0, "cut": True,
             "kind": ["Intimate scene · man & woman", "Kiss · man & woman · passionate"]}
        self.assertEqual(engine.join_gap(a, b), engine.INTIMATE_JOIN)
        fight = {"kind": ["Violence"]}
        self.assertIsNone(engine.join_gap(fight, dict(fight)))      # fights stay in pieces
        kisses = {"kind": ["Kiss · man & woman · passionate"]}
        self.assertIsNone(engine.join_gap(kisses, dict(kisses)))    # two kisses alone too
        from unittest import mock
        with mock.patch.object(engine, "bounds_sheet", lambda *a: (None, 1.0)),                 mock.patch.object(engine, "snap_to_shots", lambda *a, **k: None):
            out, _ = engine.refine_bounds("v.mp4", ".", 2600.0, [a, b], [])
        self.assertEqual([(sc["s"], sc["e"]) for sc in out], [(2390.0, 2477.0)])

    def test_told_the_bedroom_rule(self):
        import cleanview_claude as cc
        self.assertIn("any where near intimate scenes", cc.PIC_RULES)
        self.assertIn("just before or after", engine.PIC_TEXT["sex"])
        self.assertIn("just before or after", engine.OPT_TEXT["sex"])

    def test_later_batches_hear_of_earlier_intimate_scenes(self):
        import cleanview_claude as cc
        self.assertEqual(cc.earlier_intimate([{"what": "smoking", "s": 10, "e": 20}]), "")
        note = cc.earlier_intimate([{"what": "sex", "s": 194, "e": 224, "who": "man & woman",
                                     "why": "clothes coming off"}])
        self.assertIn("3:14", note)
        self.assertIn("bedroom", note)
        src = Path(cc.__file__).read_text("utf8")
        self.assertIn("prompt += earlier_intimate(out)", src)


if __name__ == "__main__":
    unittest.main()
