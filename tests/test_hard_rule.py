"""The owner's hard rule, 2026-11-13: "Sometimes i forget reasons for having words removed....so
these words: Fart, Condom (always falls under sexual reference), Seman (always falls under sexual
reference) Should always be removed", then "fart is fine to leave under crude humor" and "Also
add visuals of a condom needs to be removed". With their tick box on, the words are muted
wherever they're said, an AI can't call them fine, they're never learned or shared as fine,
and a condom in the picture is a scene to cut."""
import json
import unittest

import support
import cleanview as engine
import cleanview_ai as ai
import cleanview_claude as cc
import cleanview_learn as learn
import cvcore as cl
from test_learning import Item, review

SEX = engine.full_opts({"sexref": True})
NO_SEX = engine.full_opts({"sexref": False})


def state(lines, **opts):
    """A made-up analysis: each line heard word by word, half a second a word."""
    dialogue, asr, t = [], [], 10.0
    for text in lines:
        words = text.split()
        dialogue.append({"s": t, "e": t + 0.5 * len(words), "text": text})
        for k, w in enumerate(words):
            asr.append([w, t + 0.5 * k, t + 0.5 * k + 0.4])
        t += 0.5 * len(words) + 2
    return {"path": "nowhere.mp4", "dialogue": dialogue, "asr": asr, "mutes": [], "lines": [],
            "scenes": [], "opts": engine.full_opts(opts)}


class TheWords(unittest.TestCase):

    def test_always_removed(self):
        for text in ("fart", "farts", "farted", "farting", "a boring old fart", "condom",
                     "condoms", "the guy wore a condom", "semen", "Fart!", "Condoms."):
            with self.subTest(text=text):
                self.assertTrue(cl.always_removed(text))
                self.assertTrue(cl.never_fine(text), "an AI can't call it fine")

    def test_not_other_words(self):
        for text in ("farther", "farthing", "a condominium", "condo", "seaman", "seamen",
                     "the men", "art", "", "hell"):
            with self.subTest(text=text):
                self.assertFalse(cl.always_removed(text))
                self.assertFalse(cl.never_fine(text))

    def test_slurs_still_never_fine(self):
        self.assertTrue(cl.never_fine("retarded"))
        self.assertFalse(cl.always_removed("retarded"))

    def test_which_box(self):
        self.assertEqual(engine.hard_rule_filter("Farting"), "crude")
        self.assertEqual(engine.hard_rule_filter("condoms"), "sexref")
        self.assertEqual(engine.hard_rule_filter("semen"), "sexref")

    def test_on_the_short_lists(self):
        self.assertTrue(engine.LINE_WORDS["sexref"].search("or presence of any semen"))
        self.assertTrue(engine.LINE_WORDS["sexref"].search("The guy wore a condom."))
        self.assertTrue(engine.LINE_WORDS["crude"].search("called him a boring old fart"))
        self.assertFalse(engine.LINE_WORDS["sexref"].search("An able seaman on the deck."))


class MutedWhereverSaid(unittest.TestCase):

    def test_a_line_left_alone_still_has_the_word_muted(self):
        # (she unticked this line in Castle S2E3, and it was taught as fine: not any more)
        st = state(["And called Calvin Klein a boring old fart, to his face."], crude=True)
        self.assertEqual(engine.hard_rule_words(st), 1)
        (m,) = st["mutes"]
        self.assertEqual((m["raw"], m["keep"], m["cat"], m["hard"]), ("fart", False, "crude", True))
        self.assertAlmostEqual(m["s"], 13.5, delta=0.7)       # the 8th word, not the whole line

    def test_only_with_its_box_ticked(self):
        st = state(["A boring old fart.", "Lab says condoms are a match."], crude=False,
                   sexref=False)
        self.assertEqual(engine.hard_rule_words(st), 0)
        self.assertEqual(st["mutes"], [])
        st = state(["A boring old fart.", "Lab says condoms are a match."], crude=False,
                   sexref=True)
        engine.hard_rule_words(st)
        self.assertEqual([m["raw"] for m in st["mutes"]], ["condoms"])

    def test_case_talk_with_the_coroner_box_off(self):
        st = state(["Or presence of any semen, so what's the evidence?",
                    "Traces of spermicide. The guy wore a condom."], sexref=True, forensic=False)
        engine.hard_rule_words(st)
        self.assertEqual(sorted(m["raw"] for m in st["mutes"]), ["condom", "semen"])
        self.assertTrue(all(m["cat"] == "sexref" and not m["keep"] for m in st["mutes"]))

    def test_detective_and_coroner_lines_are_no_exception(self):
        # the owner, 2026-11-13 (in the CleanListen session): "Detective or coroner lines -
        # condom and semen should still be removed even in this instance - this is a hard rule"
        for forensic in (True, False):
            with self.subTest(coroner_box=forensic):
                st = state(["The coroner said semen was found on the sheet.",
                            "Detective Ryan found a condom in the car."],
                           sexref=True, forensic=forensic)
                engine.hard_rule_words(st)
                self.assertEqual(sorted(m["raw"] for m in st["mutes"]), ["condom", "semen"])
                self.assertFalse(any(m["keep"] for m in st["mutes"]))

    def test_a_word_already_muted_isnt_muted_twice(self):
        st = state(["The guy wore a condom."], sexref=True)
        engine.hard_rule_words(st)
        engine.hard_rule_words(st)
        self.assertEqual(len(st["mutes"]), 1)

    def test_her_own_untick_this_time_is_hers(self):
        st = state(["The guy wore a condom."], sexref=True)
        engine.hard_rule_words(st)
        st["mutes"][0].update(keep=True, by_you=True)
        engine.hard_rule_words(st)
        self.assertTrue(st["mutes"][0]["keep"])


class NoAiCallsThemFine(unittest.TestCase):

    def word(self, raw):
        return Item(s=5, e=5.4, cat="sexref", word=raw[:1] + "*" * (len(raw) - 1), raw=raw,
                    ctx="", src="audio", keep=False)

    def test_review_cant_untick_them(self):
        for raw in ("condom", "semen", "fart"):
            with self.subTest(raw=raw):
                m, other = self.word(raw), self.word("hell")
                review({"dialogue": [], "lines": [], "scenes": [], "mutes": [m, other]},
                       {m: ("not an issue", "evidence talk"), other: ("not an issue", "")})
                self.assertFalse(m["keep"], "still muted")
                self.assertEqual(m["claude"]["decision"], "remove")
                self.assertIn("hard rule", m["claude"]["why"])
                self.assertTrue(other["keep"], "other words can still be fine in context")

    def test_not_learned_as_fine(self):
        m = self.word("condom")
        m["claude"] = {"decision": "not an issue", "why": "evidence"}
        learn.record_claude({"show": "hard-rule-test", "path": "Castle.mp4", "lines": [],
                             "mutes": [m], "scenes": []})
        self.assertEqual(learn.load("hard-rule-test")["claude_ok_words"], [])

    def test_no_built_in_lesson_keeps_them(self):
        d = json.loads((support.ROOT / "shared_learned.json").read_text(encoding="utf8"))
        books = list(d["shows"].values()) + [d["general"]]
        for b in books:
            for k in ("kept", "ok_words"):
                for text in b.get(k, []):
                    self.assertFalse(cl.always_removed(text), text)


class CondomInThePicture(unittest.TestCase):

    def test_looked_for_with_the_sexual_references_box(self):
        self.assertIn("condom", engine.needs(SEX)["clip"])
        self.assertNotIn("condom", engine.needs(NO_SEX)["clip"])
        for table in (ai.CLIP_CATS, ai.THRESH, ai.MIN_FRAMES, ai.LOOK):
            self.assertIn("condom", table)
        self.assertEqual(engine.CAT_LABEL["condom"], "Condom shown")

    def test_a_moment_is_enough(self):
        clip = {"t": [20.0], "scores": [{"condom": 0.8}]}
        cands = ai.clip_candidates(clip, ["condom"])
        self.assertEqual([(c["cat"], c["s"], c["e"]) for c in cands], [("condom", 19.0, 21.0)])

    def test_double_checked_by_the_ai_on_this_pc(self):
        cands = [{"cat": "condom", "s": 10, "e": 12}, {"cat": "condom", "s": 30, "e": 32}]
        answers = iter([{"see": "A hand holds up a condom in its foil wrapper", "yes": True,
                         "clear": True},
                        {"see": "A woman opens a tea bag", "yes": False, "clear": True}])
        saved, ai.chat = ai.chat, lambda *a, **k: next(answers)
        try:
            ai.second_look(cands, lambda c: ["a frame"])
        finally:
            ai.chat = saved
        scenes = engine.decide_picture_scenes(cands, SEX, True)
        self.assertEqual([(s["kind"], s["s"], s["sure"]) for s in scenes],
                         [(["Condom shown"], 10, True)])
        self.assertIn("wrapper", ai.LOOK["condom"][0])
        self.assertIn("NOT", ai.LOOK["condom"][0])

    def test_not_double_checked_is_offered_unticked(self):
        (sc,) = engine.decide_picture_scenes([{"cat": "condom", "s": 10, "e": 12}], SEX, False)
        self.assertFalse(sc["sure"])
        self.assertIn("only cut if you tick it", sc["why"])

    def test_claude_chatgpt_and_gemini_look_for_it(self):
        self.assertIn("condom", cc.PIC_KINDS)
        self.assertIn("condom", cc.PIC_RULES)
        self.assertIn("condom", engine.picture_wanted(SEX))
        self.assertNotIn("condom", engine.picture_wanted(NO_SEX))
        find = {"what": "condom", "s": 100, "e": 104}
        self.assertEqual(engine._pic_wanted(find, SEX), "Condom shown")
        self.assertIsNone(engine._pic_wanted(find, NO_SEX))


if __name__ == "__main__":
    unittest.main()
