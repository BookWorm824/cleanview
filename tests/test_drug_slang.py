"""Drug slang, and drugs in a section of their own (1.18.137; the owner, 2026-11-18: "do a
search on common drug reference and slang", then "group 1 only. start a new menu area where you
can turn on or off drugs. put all drug names and reference there")."""
import tkinter as tk
import unittest

import support  # noqa: F401  (must come first)
import cleanview as engine
import test_ui

ui = test_ui.ui
DRUGS = engine.LINE_WORDS["drugtalk"]


class Slang(unittest.TestCase):
    def test_drug_slang(self):
        for line in ("Pass me the reefer.", "He's a total stoner.", "Your brother's a pothead.",
                     "Want a toke?", "She was high as a kite.", "That crackhead stole my car.",
                     "Some cokehead lawyer.", "They did lines of coke in the bathroom.",
                     "SHE DOESN'T LOOK LIKE A JUNKIE.", "My sister. She OD'd on Oxy.",
                     "She took all my money and spent it on oxy.", "You've got track marks.",
                     "If you introduce me to her, I won't tell anyone you were shooting up.",
                     "He's cooking crystal meth.", "The meth head is trying to kill your father!",
                     "Some tweaker broke in.", "She sells Xanax bars.", "We took shrooms.",
                     "He's on angel dust.", "I was tripping balls.", "Let's get high.",
                     "We got high behind the gym.", "He was high on coke.",
                     "She's strung out again.", "He's jonesing for a fix.",
                     "Sippin' on purple drank.", "a bag of kush", "LSD and Quaaludes"):
            self.assertIsNotNone(DRUGS.search(line), line)

    def test_other_meanings(self):
        for line in ("He's an adrenaline junkie.", "a political junkie", "the Hindu Kush",
                     "and your brother were shooting up the streets",
                     "do not shoot up a homeless encampment", "She got high marks in school.",
                     "We need to get high ground.", "The patrols were strung out along the road.",
                     "an oxy-acetylene torch", "Toledo", "pot roast", "a hip joint",
                     "blunt force trauma", "Ice cream", "Molly, come here.", "behind bars",
                     "High dose steroids", "We've given you some morphine.",
                     "Prescribe OxyContin for the pain after surgery.",
                     "Nic. We've been jonesin' for you."):
            self.assertIsNone(DRUGS.search(line), line)

    def test_booger_sugar(self):
        # 1.18.138 (the owner, in the CleanListen chat: "also add 'booger sugar'"): cocaine
        self.assertIsNotNone(DRUGS.search("You got any booger sugar?"))
        crude = engine.LINE_WORDS["crude"]
        self.assertIsNone(crude.search("You got any booger sugar?"))     # drug talk, not crude
        self.assertIsNotNone(crude.search("He's eating his boogers."))

    def test_oxycontin_misused(self):
        self.assertIsNotNone(DRUGS.search("He got hooked on OxyContin."))

    def test_listed_on_the_start_page(self):
        for w in ("stoned", "junkie", "shrooms", "getting high"):
            self.assertIn(w, engine.DRUG_TALK_SHOWN)


class SavedScan(unittest.TestCase):
    def test_older_scans_still_count(self):
        # a scan made before the box: drug talk's lines are added to it when it's used again
        import json
        import os
        import tempfile
        work = tempfile.mkdtemp()
        video = os.path.join(work, "a.mkv")
        o = engine.full_opts({})
        old = {k: v for k, v in o.items() if k != "drugtalk"}
        with open(os.path.join(work, "analysis.json"), "w") as f:
            json.dump({"path": video, "opts": old, "dialogue": [{"s": 1, "e": 2, "text": "x"}],
                       "lines": [], "groups": []}, f)
        self.assertIsNotNone(engine.saved_scan(work, video, dict(o, drugtalk=True), []))
        old["drugtalk"] = False             # made with the box off, now on: scan again
        with open(os.path.join(work, "analysis.json"), "w") as f:
            json.dump({"path": video, "opts": old, "dialogue": [{"s": 1, "e": 2, "text": "x"}],
                       "lines": [], "groups": []}, f)
        self.assertIsNone(engine.saved_scan(work, video, dict(o, drugtalk=True), []))


class Section(unittest.TestCase):
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

    def test_drugs_has_its_own_section(self):
        heads = self.app._section_heads
        self.assertIn("Drugs", heads)
        self.assertIn("Smoking and drinking", heads)
        self.assertNotIn("Smoking, drinking and drugs", heads)
        switch, count, tick_all, show = heads["Drugs"]
        for k in ("drugs", "drugtalk"):
            self.app.opts[k].set(True)
        tick_all()                                   # the section's switch turns both off
        self.assertFalse(self.app.opts["drugs"].get())
        self.assertFalse(self.app.opts["drugtalk"].get())
        tick_all()
        self.assertTrue(self.app.opts["drugs"].get() and self.app.opts["drugtalk"].get())

    def test_every_age_on(self):
        for p, _ in ui.PROFILES:
            self.assertTrue(ui.PRESETS[p]["drugtalk"], p)

    def test_old_settings_follow_drug_use(self):
        self.assertFalse(ui.one_holidays_box({"drugs": False})["drugtalk"])
        self.assertTrue(ui.one_holidays_box({"drugs": True})["drugtalk"])
        self.assertTrue(ui.one_holidays_box({"drugs": False, "drugtalk": True})["drugtalk"])


if __name__ == "__main__":
    unittest.main()
