"""Coroner, medical examiner and doctor talk is its own filter (1.18.72; the owner: "is it
possible to categorize coroner, medical examiner and dr talk into its own ticked box", then "b
and yes those ages"): graphic findings about a body or a victim (wounds, organs, cause of death,
an autopsy) and case talk about rape, sexual assault or sex offenders. Ticked for Young kids,
Kids and Teens, not Adults; with it off, case talk isn't muted as a sexual reference either."""
import unittest

import support  # noqa: F401  (sets up the sandbox first)
import cleanview as engine
import cleanview_ai as ai
import cleanview_claude as cc
import cleanview_learn as learn

CASE = ["Any signs of sexual assault?", "I'll have my guys run any registered sex offenders",
        "Cause of death? Stabbing.", "So you're saying she was raped?",
        "Single GSW to the chest, fairly large caliber.", "The autopsy shows blunt force trauma."]


class TheFilter(unittest.TestCase):
    def test_everywhere_a_filter_needs(self):
        self.assertIn("forensic", engine.LINE_KINDS)
        self.assertFalse(engine.DEFAULTS["forensic"])
        self.assertEqual(engine.LINE_LABEL["forensic"], "Coroner and doctor talk")
        self.assertIn("forensic", engine.OPT_TEXT)
        self.assertIn("coroner", ai.LINE_TYPES["forensic"])
        self.assertIn("forensic", ai.LINE_NAMES)
        self.assertIn("forensic", cc.TYPE_TEXT)

    def test_ages(self):
        from test_ui import ui
        self.assertIn("forensic", ui.FILTER_KEYS)
        for p in ("young", "kids", "teens"):
            self.assertTrue(ui.PRESETS[p]["forensic"], p)
        self.assertFalse(ui.PRESETS["adults"]["forensic"])
        self.assertIn("Coroner", ui.CHIP)


class Words(unittest.TestCase):
    def test_case_talk_found(self):
        r = engine.LINE_WORDS["forensic"]
        for t in CASE:
            with self.subTest(t):
                self.assertIsNotNone(r.search(t))

    def test_everyday_left_alone(self):
        r = engine.LINE_WORDS["forensic"]
        for t in ("I ran a tox screen.", "He'll be fine.", "Time to go home.",
                  "She's stable now.", "That's a big wound to my pride, Castle."):
            with self.subTest(t):
                self.assertIsNone(r.search(t))

    def test_not_a_sexual_reference(self):
        s = engine.LINE_WORDS["sexref"]
        self.assertIsNone(s.search("I'll have my guys run any registered sex offenders"))
        self.assertIsNone(s.search("He was arrested for sex crimes."))
        self.assertIsNotNone(s.search("Look, we had sex, okay?"))

    def test_the_readers_told(self):
        for text in (ai.LINE_TYPES["sexref"], cc.TYPE_TEXT["sexref"]):
            self.assertIn("separate choice", text)


class InTheReading(unittest.TestCase):
    def lines(self):
        return [{"s": float(i), "e": i + 0.5, "text": t} for i, t in enumerate(CASE)]

    def test_off_left_alone(self):
        out, _ = engine.find_lines(self.lines(), engine.full_opts(dict(sexref=True)), False)
        self.assertEqual(out, [])

    def test_on_muted(self):
        out, _ = engine.find_lines(self.lines(), engine.full_opts(dict(sexref=True,
                                                                      forensic=True)), False)
        self.assertEqual(len(out), len(CASE))
        self.assertTrue(all("forensic" in l["types"] for l in out))
        self.assertTrue(all(l["mute"] and not l.get("words") for l in out))   # the whole line


class CastleLessons(unittest.TestCase):
    def test_coroner_lessons_only_with_the_box(self):
        line = "i mean it could have been a rape"
        self.assertNotIn(line, learn._for_filters("castle", [line], {"sexref", "casual"}))
        self.assertIn(line, learn._for_filters("castle", [line], {"sexref", "forensic"}))


if __name__ == "__main__":
    unittest.main()
