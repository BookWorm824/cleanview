"""The "Religious conversations" filter: off unless she ticks it, found by word list
(no AI), by the AI on this PC and by Claude/ChatGPT, whole conversations rather than
single lines, and always the whole line, never just one word in it."""
import unittest

import support  # noqa: F401  (sets up the sandbox first)
import cleanview as engine
import cleanview_ai as ai
import cleanview_claude as cc

ON = engine.full_opts({"religion": True})


def dialogue(*texts, gap=3.0):
    return [{"s": k * gap, "e": k * gap + 2.0, "text": t} for k, t in enumerate(texts)]


def flagged(lines, opts=ON):
    out, _ = engine.find_lines(lines, opts, have_ai=False)
    return [l["idx"] for l in out if "religion" in l["types"]]


class Settings(unittest.TestCase):

    def test_off_unless_ticked(self):
        self.assertFalse(engine.DEFAULTS["religion"])
        self.assertIn("religion", engine.LINE_KINDS)
        self.assertEqual(flagged(dialogue("Let us pray."), engine.full_opts()), [])

    def test_told_to_the_reviewer_only_when_ticked(self):
        self.assertIn("religious conversations", engine.wanted_text(ON, []))
        self.assertNotIn("religious", engine.wanted_text(engine.full_opts(), []))

    def test_every_reader_knows_it(self):
        self.assertIn("religion", ai.LINE_TYPES)
        self.assertIn("religion", ai.LINE_NAMES)
        self.assertIn("religion", cc.TYPE_TEXT)
        self.assertEqual(engine.LINE_LABEL["religion"], "Religious talk")


class WordList(unittest.TestCase):
    """Without any AI, only words that are hard to mistake."""

    def test_found(self):
        for text in ("Let us pray.", "We go to church on Sunday.", "Amen.", "The Bible says so.",
                     "Hallelujah!", "God bless you all.", "She's a priest now.",
                     "Sunday school starts at nine.", "He was baptized last year."):
            with self.subTest(text=text):
                self.assertEqual(flagged(dialogue(text)), [0])

    def test_exclamations_and_sneezes_left_alone(self):
        for text in ("Oh my God, look at that!", "Bless you.", "Thank heavens you're here.",
                     "Angela, come here.", "That was a godsend.", "Good grief."):
            with self.subTest(text=text):
                self.assertEqual(flagged(dialogue(text)), [])


class WholeConversations(unittest.TestCase):

    def test_lines_between_go_too(self):
        lines = dialogue("Do you pray?", "Sometimes.", "Every night, at church.", "Want pizza?")
        self.assertEqual(flagged(lines), [0, 1, 2])

    def test_not_across_a_long_gap(self):
        lines = dialogue("Do you pray?", "a", "b", "c", "d", "e", "We went to church.")
        self.assertEqual(flagged(lines), [0, 6])
        lines = dialogue("Do you pray?", "Sometimes.", "We went to church.", gap=30.0)
        self.assertEqual(flagged(lines), [0, 2])

    def test_only_its_own_kind(self):
        found = {0: {"religion"}, 2: {"bullying"}, 3: {"religion"}}
        engine.fill_conversations(found, dialogue("a", "b", "c", "d"), "religion")
        self.assertEqual(found, {0: {"religion"}, 1: {"religion"}, 2: {"bullying", "religion"},
                                 3: {"religion"}})


class ClaudeAndChatGPT(unittest.TestCase):
    """The asking is faked."""

    def setUp(self):
        self.saved = cc.ask
        self.asked = []

    def tearDown(self):
        cc.ask = self.saved

    def answer(self, res):
        def fake(prompt, schema, *a, **k):
            self.asked.append((prompt, schema))
            return res, None
        cc.ask = fake

    def test_asked_to_find_religious_conversations(self):
        self.answer({"lines": [], "scenes": [{"from_line": 1, "to_line": 3, "type": "religion",
                                               "why": "talk about faith"}]})
        found, scenes = cc.check_dialogue(dialogue("a", "b", "c"), None, ["religion"])
        prompt, schema = self.asked[0]
        self.assertIn("religious conversations", prompt)
        self.assertEqual(scenes[0]["type"], "religion")

    def test_never_just_one_word_of_a_religious_line(self):
        st = support.sample_review()
        line = st["lines"][0]
        line["types"] = ["religion"]
        self.answer({"decisions": [{"id": "L1", "decision": "just the word", "word": "God",
                                    "why": "mentions God"}],
                     "missed_lines": [{"line": 5, "why": "talks about prayer", "word": "pray"},
                                      {"line": 6, "why": "says 'hell'", "word": "hell"}],
                     "missed_scenes": [], "summary": ""})
        items, decisions, missed, _, _ = cc.review(st, "- all religious conversations")
        self.assertEqual(decisions["L1"][0], "remove")
        self.assertEqual(missed[0][2], "", "a missed religious line is muted whole")
        self.assertEqual(missed[1][2], "hell", "a swear word on its own still mutes just the word")


if __name__ == "__main__":
    unittest.main()
