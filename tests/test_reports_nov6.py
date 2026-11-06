"""The 2026-11-06 reports: Jason's That Thing You Do on 1.18.20 (no AI) and Lauren's The
Resident season 3 (Claude).
1. "Jiminy Christmas" was learned as fine on 1.18.19, so it came back unticked, and muting just
   "christmas" in it never counted: now it's learned as just the word.
2. A scene set the way she chose before no longer says "(not double-checked, so left
   unticked)" while it's ticked, and the note doesn't call cut scenes "left unticked".
3. One moan or pant in the subtitles near bare skin (a hurt patient) is offered, not cut.
4. The checked Resident lessons and the drug store note ship built in."""
import unittest

import support  # noqa: F401

import cleanview as engine
import cleanview_learn as learn

MOVIE = r"D:\Movies\That Thing You Do.m4v"
LINE = "Movie cameras. Jiminy Christmas."


class JustTheWordAfterAnOldKeep(unittest.TestCase):
    def test_learned_as_just_the_word(self):
        key = "nov6_wordonly"
        d = learn.load(key)
        d["kept"].append(learn.norm(LINE))          # what 1.18.19 learned from his chat
        learn.save(key, d)
        # it starts unticked because of that (not by him this time), and the chat mutes the word
        line = {"s": 1655.6, "e": 1658.9, "text": LINE, "mute": False,
                "learned": "you left this unmuted before"}
        word = {"s": 1657.9, "e": 1658.5, "raw": "christmas", "word": "christmas",
                "cat": "you asked", "by_you": True}
        learn.record(key, [line], [False], [], [], [], [], [word], [True])
        d = learn.load(key)
        self.assertEqual(d["word_only"][learn.norm(LINE)], ["christmas"])
        self.assertNotIn(learn.norm(LINE), d["kept"])

    def test_a_kept_line_with_no_word_stays_kept(self):
        key = "nov6_kept"
        d = learn.load(key)
        d["kept"].append(learn.norm(LINE))
        learn.save(key, d)
        line = {"s": 1.0, "e": 3.0, "text": LINE, "mute": False}
        learn.record(key, [line], [False], [], [], [], [], [], [])
        d = learn.load(key)
        self.assertIn(learn.norm(LINE), d["kept"])
        self.assertNotIn(learn.norm(LINE), d["word_only"])


class RememberedScenesSayWhy(unittest.TestCase):
    def setUp(self):
        self.key = "nov6_scenes"
        kiss = {"s": 6088.0, "e": 6099.0, "kind": ["Kiss · man & woman"], "cut": True,
                "by_you": True}
        shirt = {"s": 149.0, "e": 153.0, "kind": ["Nudity"], "cut": False, "by_you": True}
        learn.record(self.key, [], [], [], [kiss, shirt], [True, False], [], [], [],
                     video=MOVIE)

    def test_why_and_notes(self):
        why = "kissing seen (not double-checked, so only cut if you tick it)"
        again = [{"s": 6088.0, "e": 6099.0, "kind": ["Kiss · man & woman"], "cut": False,
                  "why": why},
                 {"s": 149.0, "e": 153.0, "kind": ["Nudity"], "cut": True, "why": "nudity seen"}]
        _, notes = learn.apply(self.key, [], [], again, [], video=MOVIE)
        self.assertTrue(again[0]["cut"])
        self.assertEqual(again[0]["why"], "kissing seen")
        self.assertIn("Ticked to cut again because you cut them before: 1 scene(s).", notes)
        self.assertIn("Left unticked because of what CleanView has learned: 1 scene(s).", notes)

    def test_old_saved_wording_too(self):
        again = [{"s": 6088.0, "e": 6099.0, "kind": ["Kiss · man & woman"], "cut": False,
                  "why": "kissing seen (not double-checked, so left unticked)"}]
        learn.apply(self.key, [], [], again, [], video=MOVIE)
        self.assertEqual(again[0]["why"], "kissing seen")

    def test_new_wording_reads_true_when_ticked(self):
        o = {"kiss_os": "all", "kiss_ss": "all"}
        (sc,) = engine.decide_picture_scenes(
            [{"cat": "kiss", "s": 10.0, "e": 15.0, "who": {"kiss_mf": 0.9}}], o, False)
        self.assertIn("(not double-checked, so only cut if you tick it)", sc["why"])
        self.assertNotIn("left unticked", sc["why"])


class OneMoanNearBareSkin(unittest.TestCase):
    def scenes(self, cues):
        return engine.sex_scenes(None, cues, [], [], [cues[0]["s"]], [])

    def test_one_is_offered(self):
        (sc,) = self.scenes([{"s": 739.0, "e": 742.0, "text": "[panting]"}])
        self.assertFalse(sc["sure"])
        self.assertIn("just one moan", sc["why"])

    def test_several_still_cut(self):
        (sc,) = self.scenes([{"s": 739.0, "e": 742.0, "text": "[moaning]"},
                             {"s": 745.0, "e": 748.0, "text": "[panting]"},
                             {"s": 751.0, "e": 754.0, "text": "[moaning]"}])
        self.assertTrue(sc.get("sure", True))

    def test_a_plain_sex_tag_still_cuts(self):
        (sc,) = engine.sex_scenes(None, [{"s": 5.0, "e": 8.0, "text": "[making love]"}],
                                  [], [], [], [])
        self.assertTrue(sc.get("sure", True))


class BuiltInLessons(unittest.TestCase):
    def test_drug_store_note(self):
        self.assertTrue(any("drug store" in n for n in learn.notes("_movies@teens")))

    def test_resident_lessons(self):
        sh = learn.shared()["shows"]["the-resident"]
        self.assertEqual(sh["muted_for"]["no more schtupping my wife"], "sexref")
        self.assertEqual(sh["muted_for"]["he talked for a while about conversion therapy"],
                         "samesex")
        self.assertIn("in that big old rusty sexy truck of yours", sh["kept"])
        # her own unticks of prayer lines are her choice, never taught as fine
        for t in ("i pray it's not too late", "you're the answer to my prayers",
                  "we were about to say grace"):
            self.assertNotIn(t, sh["kept"])


if __name__ == "__main__":
    unittest.main()
