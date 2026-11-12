"""Medical gore is its own filter (1.18.62; the owner: "a lot of the gore that gets flagged is
medical. would it be good to create a separate filter", and "autopsies are medical only for
adults though. ticked everywhere else"). Surgery, autopsies and wounds being treated are
"Medical", cut when that box is ticked (every age but Adults), whatever Gore says."""
import unittest
from unittest import mock

import support  # noqa: F401  (sets up the sandbox first)
import cleanview as engine
import cleanview_ai as ai
import cleanview_claude as cc


def gore(level, medical, s=100.0):
    return {"cat": "gore", "s": s, "e": s + 6, "frames": [s + 2],
            "verdict": {"keep": level != "none", "who": "?", "level": level,
                        "medical": medical, "what": "gloved hands in an open chest"}}


class Settings(unittest.TestCase):
    def test_older_settings_follow_gore(self):
        self.assertTrue(engine.full_opts({"gore": True})["medical"])
        self.assertFalse(engine.full_opts({"gore": False, "graphic": False})["medical"])
        self.assertTrue(engine.full_opts({"gore": False, "graphic": True})["medical"])

    def test_her_own_tick_wins(self):
        self.assertFalse(engine.full_opts({"gore": True, "medical": False})["medical"])
        self.assertTrue(engine.full_opts({"gore": False, "graphic": False,
                                          "medical": True})["medical"])

    def test_medical_alone_needs_the_gore_check(self):
        o = dict(gore=False, graphic=False, medical=True)
        self.assertIn("gore", engine.needs(o)["clip"])
        self.assertNotIn("gore", engine.needs(dict(o, medical=False))["clip"])

    def test_ages(self):
        from test_ui import ui
        self.assertIn("medical", ui.FILTER_KEYS)
        for p in ("young", "kids", "teens"):
            self.assertTrue(ui.PRESETS[p]["medical"], p)
        self.assertFalse(ui.PRESETS["adults"]["medical"])
        self.assertTrue(ui.PRESETS["adults"]["gore"])
        self.assertIn("Medical", ui.CHIP)


class TheAIOnThisPC(unittest.TestCase):
    def test_asked_where_it_is(self):
        q, schema = ai.LOOK["gore"]
        self.assertIn("medical", schema["required"])
        self.assertIn("autopsy", q)

    def test_its_answer_is_kept(self):
        def chat(prompt, imgs, schema, **k):
            return {"see": "surgeons in an operating room", "clear": True, "medical": True,
                    "visible": ["open surgery with the inside of the body showing"]}
        c = {"cat": "gore", "frames": [1.0]}
        with mock.patch.object(ai, "chat", chat):
            ai.second_look([c], lambda c: ["img"])
        self.assertEqual(c["verdict"]["level"], "gore")
        self.assertTrue(c["verdict"]["medical"])

    def test_medical_cut_as_medical(self):
        o = engine.full_opts(dict(gore=True, graphic=True, medical=True))
        (sc,) = engine.decide_picture_scenes([gore("gore", True)], o, True)
        self.assertEqual(sc["kind"], ["Medical"])
        self.assertTrue(sc["sure"])
        (sc,) = engine.decide_picture_scenes([gore("graphic", True)], o, True)
        self.assertEqual(sc["kind"], ["Medical"])

    def test_adults_keep_surgery_and_autopsies(self):
        # offered unticked, not dropped: the AI on this PC called 2 of 23 crime scenes medical
        o = engine.full_opts(dict(gore=True, graphic=True, medical=False))
        for level in ("gore", "graphic"):
            (sc,) = engine.decide_picture_scenes([gore(level, True)], o, True)
            self.assertEqual(sc["kind"], ["Medical"])
            self.assertFalse(sc["sure"])
            self.assertIn("only cut if you tick it", sc["why"])
            self.assertIn("open chest", sc["why"])

    def test_no_blood_boxes_at_all(self):
        o = engine.full_opts(dict(gore=False, graphic=False, medical=False))
        self.assertEqual(engine.decide_picture_scenes([gore("gore", True)], o, True), [])
        self.assertEqual(engine.decide_picture_scenes([gore("gore", False)], o, True), [])

    def test_violent_gore_still_gore(self):
        o = engine.full_opts(dict(gore=True, graphic=True, medical=False))
        (sc,) = engine.decide_picture_scenes([gore("gore", False)], o, True)
        self.assertEqual(sc["kind"], ["Gore"])
        (sc,) = engine.decide_picture_scenes([gore("graphic", False)], o, True)
        self.assertEqual(sc["kind"], ["Graphic violence"])

    def test_medical_without_gore(self):
        o = engine.full_opts(dict(gore=False, graphic=False, medical=True))
        (sc,) = engine.decide_picture_scenes([gore("gore", True)], o, True)
        self.assertEqual(sc["kind"], ["Medical"])
        self.assertEqual(engine.decide_picture_scenes([gore("gore", False)], o, True), [])

    def test_not_double_checked_offered(self):
        c = gore("gore", True)
        c["verdict"] = None
        o = engine.full_opts(dict(gore=False, graphic=False, medical=True))
        (sc,) = engine.decide_picture_scenes([c], o, False)
        self.assertFalse(sc["sure"])


class OnlineAI(unittest.TestCase):
    def test_a_kind_and_a_level(self):
        self.assertIn("medical", cc.PIC_KINDS)
        self.assertIn("medical", cc.VIOLENCE_LEVELS)
        self.assertIn('"medical"', cc.PIC_RULES)

    def test_wanted_only_when_ticked(self):
        on = engine.full_opts(dict(medical=True))
        off = engine.full_opts(dict(medical=False))
        self.assertEqual(engine._pic_wanted({"what": "medical"}, on), "Medical")
        self.assertIsNone(engine._pic_wanted({"what": "medical"}, off))
        self.assertIn("medical (", engine.picture_wanted(on))
        self.assertNotIn("medical (", engine.picture_wanted(off))


if __name__ == "__main__":
    unittest.main()
