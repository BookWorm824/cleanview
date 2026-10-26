"""What CleanView learns from her choices (cleanview_learn) and how a review
uses it (cleanview.apply_review). Each test uses its own show key, so they
don't share learned files."""
import unittest

import support
import cleanview as engine
import cleanview_learn as learn


def review(st, decisions):
    """Run apply_review on lines/words/scenes with made-up decisions:
    {item: ("remove" | "not an issue" | "just the word", word)}."""
    items, decs = {}, {}
    for n, (it, (dec, word)) in enumerate(decisions.items(), 1):
        kind = "scene" if "kind" in it else "word" if "cat" in it else "line"
        items[n] = (kind, it)
        decs[n] = (dec, "made-up reason", word)
    engine.apply_review(st, (items, decs, [], [], ""))


class Item(dict):
    __hash__ = object.__hash__      # so items can be dict keys in review()


class OldDataCleanUp(unittest.TestCase):
    """Learned files from before 1.11.4 are reset once, with a backup."""

    def setUp(self):
        support.write_learned("oldshow", support.old_learned())
        self.d = learn.load("oldshow")

    def test_snowballed_scene_counts_reset(self):
        self.assertEqual(self.d["scenes"]["Graphic violence"]["kept"], 0)  # was Gore: 65
        self.assertEqual(self.d["scenes"]["Kiss"]["cut"], 1)

    def test_word_kept_counts_reset(self):
        self.assertEqual(self.d["words"]["hell"], {"muted": 3, "kept": 0})

    def test_old_kept_lines_become_hints(self):
        self.assertEqual(self.d["kept"], [])
        self.assertEqual(self.d["old_kept"], support.old_learned()["kept"])
        line = {"s": 1, "e": 2, "text": "The AI said this one was fine", "mute": True}
        learn.apply("oldshow", [], [line], [], [])
        self.assertFalse(line["mute"])
        self.assertIn("hint", line)
        self.assertNotIn("learned", line)

    def test_muted_lines_kept(self):
        self.assertEqual(self.d["muted"], support.old_learned()["muted"])

    def test_backup_written(self):
        self.assertTrue((support.APP_DATA / "learned" / "oldshow.before-1.11.4.bak").exists())

    def test_runs_only_once(self):
        learn.save("oldshow", self.d)
        learn.record("oldshow", [{"text": "she unticked this herself", "_shown": True}],
                     [False], [], [], [], [], [], [])
        self.assertIn("she unticked this herself", learn.load("oldshow")["kept"])


class OnlyHerChoicesCount(unittest.TestCase):
    """Something the AI (or learning) unticked and she left alone isn't her choice."""

    def test_scenes(self):
        by_ai = {"kind": ["Gore"], "cut": False, "_shown": False, "learned": "you usually keep these"}
        by_her = {"kind": ["Kiss"], "cut": False, "_shown": True}
        ticked = {"kind": ["Violence"], "cut": True, "_shown": True}
        for _ in range(5):
            learn.record("scenes", [], [], [], [by_ai, by_her, ticked], [False, False, True],
                         [], [], [])
        d = learn.load("scenes")
        self.assertNotIn("Gore", d["scenes"])
        self.assertEqual(d["scenes"]["Kiss"], {"cut": 0, "kept": 5})
        self.assertEqual(d["scenes"]["Violence"], {"cut": 5, "kept": 0})
        later = [{"kind": ["Gore"], "cut": True}, {"kind": ["Kiss"], "cut": True}]
        learn.apply("scenes", [], [], later, [])
        self.assertTrue(later[0]["cut"], "the AI's habit doesn't untick scenes")
        self.assertFalse(later[1]["cut"], "her habit does")

    def test_earlier_change_still_counts(self):
        sc = {"kind": ["Kiss"], "cut": False, "_shown": False, "by_you": True}
        learn.record("earlier", [], [], [], [sc], [False], [], [], [])
        self.assertEqual(learn.load("earlier")["scenes"]["Kiss"]["kept"], 1)

    def test_lines(self):
        by_ai = {"text": "the AI said fine", "_shown": False}
        by_her = {"text": "she unticked this line", "_shown": True}
        ticked = {"text": "left ticked to be muted", "_shown": True}
        learn.record("lines", [by_ai, by_her, ticked], [False, False, True], [], [], [], [], [], [])
        d = learn.load("lines")
        self.assertNotIn("the ai said fine", d["kept"])
        self.assertIn("she unticked this line", d["kept"])
        self.assertIn("left ticked to be muted", d["muted"])

    def test_words(self):
        by_ai = {"raw": "heck", "keep": True, "_shown": False}
        by_her = {"raw": "gosh", "keep": True, "_shown": True}
        for _ in range(2):
            learn.record("words", [], [], [], [], [], [], [by_ai, by_her], [False, False])
        d = learn.load("words")
        self.assertNotIn("heck", d["words"])
        self.assertEqual(d["words"]["gosh"], {"muted": 0, "kept": 2})


class NewReviewVersusOld(unittest.TestCase):
    """Claude's past "fine" is a hint a new "remove" overrules; her own choices aren't."""

    def setUp(self):
        d = learn.load("hints")
        d["claude_kept"].append("claude said this was fine")
        d["kept"].append("she unticked this line")
        learn.save("hints", d)
        self.claude_l = Item(s=1, e=2, text="Claude said this was fine", types=["casual"], mute=True)
        self.hers = Item(s=3, e=4, text="She unticked this line", types=["casual"], mute=True)
        learn.apply("hints", [], [self.claude_l, self.hers], [], [])
        self.st = {"dialogue": [], "lines": [self.claude_l, self.hers], "scenes": [], "mutes": []}

    def test_start_unticked(self):
        self.assertFalse(self.claude_l["mute"])
        self.assertEqual(self.claude_l["hint"], "Claude said this was fine before")
        self.assertFalse(self.hers["mute"])
        self.assertEqual(self.hers["learned"], "you left this unmuted before")

    def test_new_remove_wins_over_old_fine(self):
        review(self.st, {self.claude_l: ("remove", ""), self.hers: ("remove", "")})
        self.assertTrue(self.claude_l["mute"])
        self.assertNotIn("hint", self.claude_l)
        self.assertFalse(self.hers["mute"], "her own choice is never undone")

    def test_old_fine_ok_word_is_a_hint(self):
        d = learn.load("hints")
        d["claude_ok_words"].append("welcome to hell")
        learn.save("hints", d)
        m = Item(s=5, e=5.3, cat="swear", word="h**l", raw="hell", ctx="welcome to", keep=False)
        learn.apply("hints", [], [], [], [m])
        self.assertTrue(m["keep"])
        self.assertIn("hint", m)
        self.assertNotIn("learned", m)


class ReviewOfACopy(unittest.TestCase):
    """"Review everything again" asks about a copy; by the time the answer comes, a scene
    may have been added, which shifts the numbers (S1, S2...). Answers must only count
    for the item they were about."""

    def test_answers_follow_their_items(self):
        import copy
        st = support.sample_review()
        asked = copy.deepcopy(st)
        items, _ = engine.cc.candidates(asked)
        res = (items, {"S1": ("not an issue", "made up", ""), "L1": ("remove", "made up", "")},
               [], [], "")
        st["scenes"].insert(0, {"id": 9, "s": 5.0, "e": 9.0, "kind": ["Added by you"],
                                "why": "", "cut": True, "by_you": True})
        keep, decisions, *_ = engine.match_review(st, res)
        self.assertNotIn("S1", keep, "S1 is now her added scene, not the fight it was about")
        self.assertEqual(keep["L1"][1], st["lines"][0])
        self.assertEqual(set(decisions), {"L1"})

    def test_unchanged_review_matches_everything(self):
        st = support.sample_review()
        items, _ = engine.cc.candidates(st)
        keep, *_ = engine.match_review(st, (items, {}, [], [], ""))
        self.assertEqual(set(keep), set(items))


class MutedBeforeStaysMuted(unittest.TestCase):

    def test_not_an_issue_doesnt_unmute_her_line(self):
        line = Item(s=5, e=6, text="x", types=["learned"], mute=True, learned="you muted this before")
        st = {"dialogue": [], "lines": [line], "scenes": [], "mutes": []}
        review(st, {line: ("not an issue", "")})
        self.assertTrue(line["mute"])

    def test_shared_line_can_be_unmuted(self):
        line = Item(s=5, e=6, text="x", types=["shared"], mute=True)
        st = {"dialogue": [], "lines": [line], "scenes": [], "mutes": []}
        review(st, {line: ("not an issue", "")})
        self.assertFalse(line["mute"])


if __name__ == "__main__":
    unittest.main()
