"""Christmas, Halloween, birthday candles, Valentine's Day and Easter: heard (lines muted,
whole conversations) and seen (scenes cut, by the AI on this PC and by Claude/ChatGPT).
For birthdays only the candles on the cake count: parties, cake and "happy birthday" are fine."""
import unittest

import support  # noqa: F401  (sets up the sandbox first)
import cleanview as engine
import cleanview_ai as ai
import cleanview_claude as cc

HOLIDAYS = ("christmas", "halloween", "valentine", "easter", "stpatricks", "birthday")
PIC_KIND = {"stpatricks": "st patrick's day"}      # what Claude's picture review calls it
ALL_ON = engine.full_opts(dict.fromkeys(HOLIDAYS, True))


def dialogue(*texts, gap=3.0):
    return [{"s": k * gap, "e": k * gap + 2.0, "text": t} for k, t in enumerate(texts)]


def flagged(lines, opts=ALL_ON):
    out, _ = engine.find_lines(lines, opts, have_ai=False)
    return {l["idx"]: [t for t in l["types"] if t in HOLIDAYS] for l in out}


class Heard(unittest.TestCase):

    def test_off_unless_ticked(self):
        for k in HOLIDAYS:
            self.assertFalse(engine.DEFAULTS[k])
        self.assertEqual(flagged(dialogue("Merry Christmas!"), engine.full_opts()), {})

    def test_found_without_any_ai(self):
        for text, kind in [("Merry Christmas, everyone!", "christmas"),
                           ("Santa Claus is coming tonight.", "christmas"),
                           ("Trick or treat!", "halloween"),
                           ("Look at my jack-o'-lantern.", "halloween"),
                           ("Now blow out the candles.", "birthday"),
                           ("Look at all the birthday candles!", "birthday"),
                           ("She blew out the candles.", "birthday"),
                           ("Rudolph the red-nosed reindeer", "christmas"),
                           ("Put the candles on the cake.", "birthday"),
                           ("Will you be my valentine?", "valentine"),
                           ("Who's ready for the Easter egg hunt?", "easter"),
                           ("The Easter bunny came!", "easter"),
                           ("Happy St. Patrick's Day!", "stpatricks"),
                           ("A leprechaun stole my shoe!", "stpatricks"),
                           ("Find the pot of gold.", "stpatricks")]:
            with self.subTest(text=text):
                self.assertEqual(flagged(dialogue(text)), {0: [kind]})

    def test_everyday_words_left_alone(self):
        for text in ("The snow is falling.", "Light the candles, it's dark.", "We have a present "
                     "for you.", "Pumpkin pie for dinner.", "The witch cast a spell.",
                     "Make a wish on that star.", "Easter Island has huge statues.",
                     "Scrambled eggs for breakfast.", "Mass at St. Patrick's Cathedral.",
                     "Happy Thanksgiving!", "Pass the turkey, it's Thanksgiving.",
                     "Rudolph Hill called the office."):
            with self.subTest(text=text):
                self.assertEqual(flagged(dialogue(text)), {})

    def test_one_holidays_box(self):
        """Lauren, 2026-10-29: the holidays are one tick box. Birthday candles are their own."""
        o = engine.full_opts({"holidays": True})
        for k in engine.HOLIDAYS:
            self.assertTrue(o[k], k)
        self.assertFalse(o["birthday"])
        self.assertEqual(flagged(dialogue("Merry Christmas!", "Happy St. Patrick's Day!"), o),
                         {0: ["christmas"], 1: ["stpatricks"]})
        self.assertFalse(engine.full_opts({})["christmas"])

    def test_birthdays_are_fine_only_the_candles_count(self):
        for text in ("Happy birthday to you!", "It's my birthday today.",
                     "Are you coming to my birthday party?", "Have some cake.",
                     "What do you want for your birthday?"):
            with self.subTest(text=text):
                self.assertEqual(flagged(dialogue(text)), {})
        # just the candle lines, not the conversation around them
        lines = dialogue("Happy birthday, Sam!", "Thanks, Mom.", "Now blow out your candles!",
                         "Cake for everyone!")
        self.assertEqual(flagged(lines), {2: ["birthday"]})
        self.assertNotIn("birthday", engine.WHOLE_CONVERSATIONS)
        self.assertIn("candles", ai.LOOK["birthday"][0])
        self.assertNotIn("party", " ".join(ai.CLIP_CATS["birthday"]))

    def test_whole_conversation(self):
        lines = dialogue("What do you want for Christmas?", "A bike.", "And a puppy!",
                         "Santa might bring both.", "Time for school.")
        self.assertEqual(sorted(flagged(lines)), [0, 1, 2, 3])

    def test_every_reader_knows_them(self):
        for k in HOLIDAYS:
            self.assertIn(k, ai.LINE_TYPES)
            self.assertIn(k, ai.LINE_NAMES)
            self.assertIn(k, cc.TYPE_TEXT)
            self.assertIn(k, engine.LINE_LABEL)
            self.assertIn(k, cc.WHOLE_LINE_TYPES)
        self.assertIn("Christmas", engine.wanted_text(ALL_ON, []))


class Seen(unittest.TestCase):

    def test_picture_ai_looks_for_them_when_ticked(self):
        self.assertEqual([c for c in engine.needs(ALL_ON)["clip"] if c in HOLIDAYS],
                         list(HOLIDAYS))
        self.assertEqual([c for c in engine.needs({})["clip"] if c in HOLIDAYS], [])
        for k in HOLIDAYS:
            self.assertIn(k, ai.CLIP_CATS)
            self.assertIn(k, ai.THRESH)
            self.assertIn(k, ai.MIN_FRAMES)
            self.assertIn(k, ai.LOOK)

    def test_frames_become_a_scene(self):
        clip = {"t": [10.0 + k * 0.5 for k in range(12)],
                "scores": [{"birthday": 0.9} for _ in range(12)]}
        cands = ai.clip_candidates(clip, ["birthday"])
        self.assertEqual([(c["cat"], c["s"]) for c in cands], [("birthday", 9.0)])

    def test_double_checked_by_the_ai_on_this_pc(self):
        cands = [{"cat": "christmas", "s": 10, "e": 20}, {"cat": "halloween", "s": 40, "e": 50}]
        answers = iter([{"see": "A family by a decorated Christmas tree", "yes": True,
                         "clear": True},
                        {"see": "A witch in a fairy tale castle", "yes": False, "clear": True}])
        saved, ai.chat = ai.chat, lambda *a, **k: next(answers)
        try:
            ai.second_look(cands, lambda c: ["a frame"])
        finally:
            ai.chat = saved
        scenes = engine.decide_picture_scenes(cands, ALL_ON, True)
        self.assertEqual([(s["kind"], s["sure"]) for s in scenes], [(["Christmas"], True)])

    def test_claude_looks_for_them_when_ticked(self):
        text = engine.picture_wanted(ALL_ON)
        for k in HOLIDAYS:
            word = PIC_KIND.get(k, k)
            self.assertIn(word, text)
            self.assertIn(word, cc.PIC_KINDS)
        self.assertEqual(engine._pic_wanted({"what": "st patrick's day"}, ALL_ON),
                         "St. Patrick's Day")
        self.assertIsNone(engine._pic_wanted({"what": "st patrick's day"}, engine.full_opts()))
        self.assertEqual(engine._pic_wanted({"what": "birthday"}, ALL_ON), "Birthday candles")
        self.assertEqual(engine._pic_wanted({"what": "easter"}, ALL_ON), "Easter")
        self.assertIsNone(engine._pic_wanted({"what": "birthday"}, engine.full_opts()))


class WholeLines(unittest.TestCase):
    """Claude's review never narrows a holiday line down to one word."""

    def test_review(self):
        st = support.sample_review()
        st["lines"][0]["types"] = ["christmas"]
        saved = cc.ask
        cc.ask = lambda *a, **k: ({
            "decisions": [{"id": "L1", "decision": "just the word", "word": "Christmas",
                           "why": "mentions Christmas"}],
            "missed_lines": [{"line": 5, "why": "talks about a birthday party", "word": "birthday"}],
            "missed_scenes": [], "summary": ""}, None)
        try:
            items, decisions, missed, _, _ = cc.review(st, "- Christmas")
        finally:
            cc.ask = saved
        self.assertEqual(decisions["L1"][0], "remove")
        self.assertEqual(missed[0][2], "")


if __name__ == "__main__":
    unittest.main()
