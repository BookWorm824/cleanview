"""Christmas, Halloween, birthdays and Valentine's Day: heard (lines muted, whole
conversations) and seen (scenes cut, by the AI on this PC and by Claude/ChatGPT)."""
import unittest

import support  # noqa: F401  (sets up the sandbox first)
import cleanview as engine
import cleanview_ai as ai
import cleanview_claude as cc

HOLIDAYS = ("christmas", "halloween", "birthday", "valentine")
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
                           ("Happy birthday to you!", "birthday"),
                           ("Now blow out the candles.", "birthday"),
                           ("Will you be my valentine?", "valentine")]:
            with self.subTest(text=text):
                self.assertEqual(flagged(dialogue(text)), {0: [kind]})

    def test_everyday_words_left_alone(self):
        for text in ("The snow is falling.", "Light the candles, it's dark.", "We have a present "
                     "for you.", "Pumpkin pie for dinner.", "The witch cast a spell.",
                     "Make a wish on that star."):
            with self.subTest(text=text):
                self.assertEqual(flagged(dialogue(text)), {})

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
        for word in ("christmas", "halloween", "birthday", "valentine"):
            self.assertIn(word, text)
            self.assertIn(word, cc.PIC_KINDS)
        self.assertEqual(engine._pic_wanted({"what": "birthday"}, ALL_ON), "Birthday")
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
