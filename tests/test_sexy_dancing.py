"""Sexy dancing is a sexual reference (1.18.175, 2026-11-27; the owner: "have sexy dancing under
sexual reference instead of immodesty"). It was part of "Immodest clothing" (swimsuits,
underwear, sexy dancing), which is off for every age as standard, so it was only looked for when
that box was ticked. Now it's looked for with "Sexual references and innuendo" (on for every
age), the way a condom shown is, and shows on the review page under "Sexual reference".
Immodest clothing is clothes only."""
import unittest

import support  # noqa: F401  (sets up the sandbox first)
import cleanview as engine
import cleanview_ai as ai
import cleanview_claude as cc

SEXREF = engine.full_opts({"sexref": True, "immodest": False})
IMMODEST = engine.full_opts({"sexref": False, "immodest": True})
NEITHER = engine.full_opts({"sexref": False, "immodest": False})


class LookedForWithSexualReferences(unittest.TestCase):
    def test_the_picture_ai_looks_for_it_with_that_box(self):
        self.assertIn("dancing", engine.needs(SEXREF)["clip"])
        self.assertNotIn("dancing", engine.needs(IMMODEST)["clip"])
        self.assertNotIn("dancing", engine.needs(NEITHER)["clip"])
        for table in (ai.THRESH, ai.MIN_FRAMES, ai.LOOK):
            self.assertIn("dancing", table)

    def test_found_where_the_immodest_descriptions_win(self):
        # the descriptions stay as they were (split, immodest found 4 of 93 stills): nothing
        # is scanned again, and the closer look asks the dancing question
        self.assertNotIn("dancing", ai.CLIP_CATS)
        self.assertEqual(ai.SAME_SCORES["dancing"], "immodest")
        self.assertTrue([p for p in ai.CLIP_CATS["immodest"] if "pole" in p])
        clip = {"t": [20.0, 22.0, 24.0, 26.0], "scores": [{"immodest": 0.8}] * 4}
        cands = ai.clip_candidates(clip, ["dancing"])
        self.assertEqual([(c["cat"], c["s"], c["e"]) for c in cands], [("dancing", 19.0, 27.0)])
        self.assertEqual(ai.clip_candidates({"t": [20.0], "scores": [{"immodest": 0.3}]},
                                            ["dancing"]), [])

    def test_immodest_is_clothes_only(self):
        self.assertNotIn("danc", ai.LOOK["immodest"][0])
        self.assertNotIn("danc", engine.OPT_TEXT["immodest"])
        self.assertNotIn("danc", engine.PIC_TEXT["immodest"])
        self.assertIn("danc", engine.OPT_TEXT["sexref"])

    def test_found_scenes_are_sexual_references(self):
        cands = [{"cat": "dancing", "s": 10, "e": 14}, {"cat": "dancing", "s": 40, "e": 44}]
        answers = iter([{"see": "A woman pole dancing in a club", "yes": True, "clear": True},
                        {"see": "A couple dancing at a wedding", "yes": False, "clear": True}])
        saved, ai.chat = ai.chat, lambda *a, **k: next(answers)
        try:
            ai.second_look(cands, lambda c: ["a frame"])
        finally:
            ai.chat = saved
        scenes = engine.decide_picture_scenes(cands, SEXREF, True)
        self.assertEqual([(s["kind"], s["s"], s["sure"]) for s in scenes],
                         [([engine.SEXY_DANCING], 10, True)])
        self.assertIn("NOT", ai.LOOK["dancing"][0])

    def test_review_page_heading_is_sexual_reference(self):
        self.assertEqual(engine.SEXY_DANCING.split(" · ")[0], engine.LINE_LABEL["sexref"])

    def test_claude_chatgpt_and_gemini(self):
        self.assertIn("sexy dancing", cc.PIC_KINDS)
        self.assertIn("sexy dancing", cc.PIC_RULES)
        self.assertIn("sexy dancing", engine.picture_wanted(SEXREF))
        self.assertNotIn("danc", engine.picture_wanted(IMMODEST))
        find = {"what": "sexy dancing", "s": 100, "e": 104}
        self.assertEqual(engine._pic_wanted(find, SEXREF), engine.SEXY_DANCING)
        self.assertIsNone(engine._pic_wanted(find, IMMODEST))
        self.assertIsNone(engine._pic_wanted(find, NEITHER))


if __name__ == "__main__":
    unittest.main()
