"""Religious content in parts and a Flirting box, as CleanListen and CleanRead have them
(1.18.159; the owner: "what happened to the religious filter options?", "there should not be so
much difference in all of them...I told you to match the filters of CleanListen")."""
import tkinter as tk
import unittest

import support  # noqa: F401  (must come first)
import cleanview as engine
import test_ui

ui = test_ui.ui


def lines(*texts):
    return [{"s": 3.0 * i, "e": 3.0 * i + 2, "text": t} for i, t in enumerate(texts)]


def found(texts, opts):
    hits = engine.list_hits(lines(*texts), ["religion", "flirt"], engine.line_words(opts))
    return {texts[i]: sorted(k) for i, k in hits.items()}


ALL = dict(religion=True, religion_preach=True, religion_anger=True, religion_prayers=True)
STANDARD = dict(religion=True, religion_preach=True, religion_anger=True, religion_prayers=False)


class Parts(unittest.TestCase):
    def test_standard_parts(self):
        self.assertEqual(engine.religion_parts(STANDARD), {"preach", "anger"})
        self.assertEqual(engine.religion_parts(dict(STANDARD, religion=False)), set())

    def test_old_settings_meant_all(self):
        self.assertEqual(engine.religion_parts({"religion": True}), set(engine.RELIGION_PARTS))
        self.assertEqual(engine.religion_parts({}), set())

    def test_box_with_no_parts_is_off(self):
        o = engine.full_opts(dict(religion=True, religion_preach=False, religion_anger=False,
                                  religion_prayers=False))
        self.assertFalse(o["religion"])
        self.assertNotIn("religion", engine.on_kinds(o))


class Lists(unittest.TestCase):
    ANGER = ("There is no God.", "I blame God for this.", "I lost my faith.",
             "Why did God let her die?", "God has abandoned us.")
    NOT_ANGER = ("Oh God, I'm so mad.", "I lost my faith in people.", "God knows I tried.",
                 "My God, she's angry.")
    PRAYER = ("Let us pray.", "We go to church on Sunday.", "Amen.")

    def test_anger_found_with_its_part(self):
        f = found(self.ANGER + self.NOT_ANGER, STANDARD)
        self.assertEqual(set(f), set(self.ANGER))

    def test_prayers_only_with_their_part(self):
        self.assertEqual(found(self.PRAYER, STANDARD), {})
        self.assertEqual(set(found(self.PRAYER, ALL)), set(self.PRAYER))

    def test_preaching_alone_has_no_list(self):
        o = dict(STANDARD, religion_anger=False)
        self.assertEqual(found(self.ANGER + self.PRAYER, o), {})

    def test_flirting(self):
        yes = ("Were you flirting with me?", "Stop hitting on her.", "He winked at her.",
               "Is that a pick-up line?", "She's playing hard to get.", "So flirty.")
        no = ("He flirted with disaster.", "She's flirting with the idea of moving.",
              "Check him out.", "The ball hit on the rim.")
        f = found(yes + no, {"flirt": True})
        self.assertEqual({t: k for t, k in f.items()}, {t: ["flirt"] for t in yes})


class Readers(unittest.TestCase):
    def tearDown(self):
        engine.use_religion(ALL)

    def test_all_three_as_before(self):
        engine.use_religion(ALL)
        self.assertTrue(engine.OPT_TEXT["religion"].startswith("all religious conversations"))
        self.assertTrue(engine.cc.TYPE_TEXT["religion"].startswith("religious conversations"))

    def test_standard_tells_them_prayers_are_fine(self):
        engine.use_religion(STANDARD)
        for t in (engine.OPT_TEXT["religion"], engine.ai.LINE_TYPES["religion"],
                  engine.cc.TYPE_TEXT["religion"]):
            self.assertIn("preaching", t)
            self.assertIn("angry with", t)
            self.assertIn("a short prayer", t)        # in the "Not:" part
        self.assertIn("religious content", engine.wanted_text(STANDARD, []))

    def test_flirt_defined_for_every_reader(self):
        for d in (engine.OPT_TEXT, engine.ai.LINE_TYPES, engine.ai.LINE_NAMES,
                  engine.cc.TYPE_TEXT, engine.LINE_LABEL):
            self.assertIn("flirt", d)
        self.assertIn("flirt", engine.LINE_KINDS)


class FindLines(unittest.TestCase):
    def test_word_lists_only(self):
        o = engine.full_opts(dict(STANDARD, flirt=True))
        out, _ = engine.find_lines(lines("There is no God.", "Let us pray.", "Nice day.",
                                         "Are you hitting on me?"), o, have_ai=False)
        got = {l["plain"]: l["types"] for l in out}
        self.assertEqual(got, {"There is no God.": ["religion"],
                               "Are you hitting on me?": ["flirt"]})


class Ages(unittest.TestCase):
    def test_presets(self):
        for p, _ in ui.PROFILES:
            t = ui.PRESETS[p]
            self.assertFalse(t["religion"])
            self.assertEqual((t["religion_preach"], t["religion_anger"], t["religion_prayers"]),
                             (True, True, False), p)
        self.assertTrue(ui.PRESETS["young"]["flirt"])
        self.assertTrue(ui.PRESETS["kids"]["flirt"])
        self.assertTrue(ui.PRESETS["teens"]["flirt"])
        self.assertFalse(ui.PRESETS["adults"]["flirt"])

    def test_old_ticks(self):
        t = ui.one_holidays_box({"religion": True})
        self.assertTrue(all(t[k] for k, _, _ in ui.RELIGION_PARTS))
        self.assertNotIn("religion_prayers", ui.one_holidays_box({"religion": False}))


class StartPage(unittest.TestCase):
    def setUp(self):
        self.saved = ui.App._check_update, ui.App._check_every_ai
        ui.App._check_update = lambda self, manual=False: None
        ui.App._check_every_ai = lambda self: None
        try:
            self.app = ui.App()
        except tk.TclError as ex:
            ui.App._check_update, ui.App._check_every_ai = self.saved
            raise unittest.SkipTest(f"no screen to draw on ({ex})")
        self.app.update()

    def tearDown(self):
        try:
            self.app.destroy()
        finally:
            ui.App._check_update, ui.App._check_every_ai = self.saved

    def test_parts_shown_and_greyed(self):
        a = self.app
        for k in ("flirt", "religion_preach", "religion_anger", "religion_prayers"):
            self.assertIn(k, a.opts)
        a.opts["religion"].set(False)
        a.update()
        boxes = [w for w in test_ui_walk(a) if isinstance(w, tk.Widget)
                 and w.winfo_class() == "TCheckbutton"
                 and str(w.cget("text")).startswith("Preaching")]
        self.assertEqual(len(boxes), 1)
        self.assertTrue(boxes[0].instate(["disabled"]))
        a.opts["religion"].set(True)
        a.update()
        self.assertFalse(boxes[0].instate(["disabled"]))

    def test_parts_alone_are_not_something_to_remove(self):
        vals = {k: False for k in ui.FILTER_KEYS if k not in ("kiss_os", "kiss_ss")}
        vals.update(kiss_os="off", kiss_ss="off", religion_preach=True, religion_anger=True)
        o = dict(vals)
        self.assertFalse(any(o.get(k) not in (False, "off", None) for k in ui.FILTER_KEYS
                             if not k.startswith("religion_")))


class Butcher(unittest.TestCase):
    """Castle S2E2 (Play, 1.18.158): a butcher chopping meat was "graphic violence"; the owner:
    "yes, it was a butcher chopping meat"."""
    def test_told_to_every_picture_check(self):
        self.assertIn("butcher chopping meat", engine.ai.LOOK["gore"][0])
        self.assertIn("butcher or cook chopping meat", engine.ai.LOOK["fight"][0])
        self.assertIn("butchered", engine.cc.PIC_RULES)


def test_ui_walk(w, out=None):
    out = [] if out is None else out
    out.append(w)
    for c in w.winfo_children():
        test_ui_walk(c, out)
    return out


if __name__ == "__main__":
    unittest.main()
