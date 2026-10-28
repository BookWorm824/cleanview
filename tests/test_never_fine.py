"""From Lauren's Radio review: Claude unticked "a severely retarded..." ("retarded, which
isn't on your list") and several swears heard in the sound for not being in the subtitles.
Slurs are never "fine here", whatever an AI says, and the review is told heard words are
really said. Nothing like that goes into the shared file either."""
import importlib.util
import unittest

import support
import cleanview as engine
import cleanview_claude as cc
import cleanview_learn as learn
import cvcore as cl
from test_learning import Item, review

_spec = importlib.util.spec_from_file_location("merge_learned",
                                               support.ROOT / "tools" / "merge_learned.py")
merge_learned = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(merge_learned)


def mute(raw, ctx="", src="audio", cat="moderate"):
    return Item(s=5, e=5.4, cat=cat, word=raw[:1] + "*" * (len(raw) - 1), raw=raw, ctx=ctx,
                src=src, keep=False)


class NeverFine(unittest.TestCase):

    def test_slurs(self):
        for text in ("retarded", "a severely retarded boy", "retard", "retards", "retardo",
                     "tard", "libtards", "re tarded", "wetback", "towelhead"):
            with self.subTest(text=text):
                self.assertTrue(cl.never_fine(text))

    def test_everything_else(self):
        for text in ("hell", "damn", "shit", "thank god", "tardy", "fire retardant",
                     "a fag", "the dykes of Holland", ""):
            with self.subTest(text=text):
                self.assertFalse(cl.never_fine(text))

    def test_review_cant_untick_a_slur(self):
        slur, swear = mute("retarded", "experience with having a severely"), mute("hell", "lou")
        review({"dialogue": [], "lines": [], "scenes": [], "mutes": [slur, swear]},
               {slur: ("not an issue", ""), swear: ("not an issue", "")})
        self.assertFalse(slur["keep"], "still muted")
        self.assertEqual(slur["claude"]["decision"], "remove")
        self.assertIn("slur", slur["claude"]["why"])
        self.assertTrue(swear["keep"], "other words can still be fine in context")

    def test_her_own_choice_still_wins(self):
        slur = mute("retarded")
        slur["keep"], slur["by_you"] = True, True
        review({"dialogue": [], "lines": [], "scenes": [], "mutes": [slur]},
               {slur: ("not an issue", "")})
        self.assertTrue(slur["keep"])

    def test_not_learned_as_fine(self):
        slur = mute("retarded", "having a severely")
        slur["claude"] = {"decision": "not an issue", "why": "description"}
        learn.record_claude({"show": "radio-test", "path": "Radio.mp4", "lines": [],
                             "mutes": [slur], "scenes": []})
        self.assertEqual(learn.load("radio-test")["claude_ok_words"], [])
        d = learn.load("radio-test")
        d["claude_ok_words"].append("a severely retarded")      # from before this fix
        learn.save("radio-test", d)
        again = mute("retarded", "having a severely")
        learn.apply("radio-test", [], [], [], [again])
        self.assertFalse(again["keep"])


class ReviewIsToldWhereWordsCameFrom(unittest.TestCase):

    def test_heard_in_the_sound(self):
        st = {"dialogue": [], "lines": [], "scenes": [],
              "mutes": [mute("hell", "had just lost his mother, Lou."),
                        mute("damn", src="subtitles-estimated", cat="mild")]}
        _, text = cc.candidates(st)
        self.assertIn("[moderate, heard in the sound] \"hell\"", text)
        self.assertIn("[mild, in the subtitles] \"damn\"", text)


class SharedFileGetsNoBadFine(unittest.TestCase):

    def word(self, word, category, decision, heard="audio", before="you know", yours=False):
        return {"word": word, "category": category, "heard_by": heard, "before": before,
                "final": "kept", "changed_by_you": yours, "ai": {"decision": decision}}

    def test_only_safe_fines_are_shared(self):
        ref = {"what": "CleanView refined", "videos": [{"show": "_movies", "lines": [], "words": [
            self.word("retarded", "moderate", "not an issue", before="having a severely"),
            self.word("hell", "mild", "not an issue", before="his mother, Lou."),
            self.word("thank god", "deity", "not an issue", before="Third Christmas."),
            self.word("screwed", "claude", "not an issue", before="Oh, we're"),
            self.word("damn", "mild", "not an issue", before="Okay, Mom.", yours=True)]}]}
        ok = merge_learned.from_refined(ref)["shows"]["_movies"]["claude_ok_words"]
        self.assertEqual(ok, ["third christmas thank god", "oh we're screwed", "okay mom damn"])


if __name__ == "__main__":
    unittest.main()
