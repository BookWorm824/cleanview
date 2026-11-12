"""Sexual talk looked for one conversation at a time (1.18.70; the owner, after the AI helper
missed Castle S2E3's innuendo: "Yes, build it"): a quick yes or no, then which lines (their
words must really be there), then each line on its own, worded to count innuendo."""
import unittest
from unittest import mock

import support  # noqa: F401  (sets up the sandbox first)
import cleanview as engine
import cleanview_ai as ai

LINES = [{"s": 0.0, "e": 2.0, "text": "Oh, a fountain! Let's skinny dip!"},
         {"s": 2.5, "e": 4.0, "text": "Now? Are you kidding?"},
         {"s": 4.5, "e": 6.0, "text": "If you catch me, you can have me."},
         {"s": 30.0, "e": 32.0, "text": "Canvass the buildings around the plaza."},
         {"s": 32.5, "e": 34.0, "text": "Aye, aye."}]


class Fake:
    def __init__(self, sexual=(0,), which=None, fits=True):
        self.sexual, self.which, self.fits, self.asked = sexual, which, fits, []

    def __call__(self, prompt, *a, schema=None, **k):
        props = (schema or {}).get("properties", {})
        conv = 0 if "fountain" in prompt else 1
        if "sexual" in props:
            self.asked.append(("quick", conv))
            return {"sexual": conv in self.sexual}
        if "lines" in props:
            self.asked.append(("which", conv))
            return {"lines": self.which if self.which is not None else
                    [{"line": 1, "words": "Let's skinny dip"},
                     {"line": 3, "words": "you can have me"}]}
        self.asked.append(("line", prompt.split('Line: "')[1][:12]))
        return {"fits": self.fits}


class Conversations(unittest.TestCase):
    def run_with(self, fake):
        with mock.patch.object(ai, "chat", fake):
            return ai.sexual_talk(LINES)

    def test_found_and_confirmed(self):
        fake = Fake()
        self.assertEqual(self.run_with(fake), {0, 2})
        self.assertIn(("quick", 1), fake.asked)
        self.assertNotIn(("which", 1), fake.asked)     # the quiet conversation: no details

    def test_words_must_be_there(self):
        fake = Fake(which=[{"line": 2, "words": "take off your clothes"}])
        self.assertEqual(self.run_with(fake), set())

    def test_the_second_look_can_say_no(self):
        self.assertEqual(self.run_with(Fake(fits=False)), set())

    def test_none_said(self):
        self.assertEqual(self.run_with(Fake(sexual=())), set())

    def test_innuendo_counts_in_the_second_look(self):
        seen = []

        def chat(prompt, *a, schema=None, **k):
            if "sexual" in (schema or {}).get("properties", {}):
                return {"sexual": True}
            if "lines" in (schema or {}).get("properties", {}):
                return {"lines": [{"line": 1, "words": "Let's skinny dip"}]}
            seen.append(prompt)
            return {"fits": True}
        with mock.patch.object(ai, "chat", chat):
            ai.sexual_talk(LINES)
        self.assertTrue(seen and "Innuendo counts too" in seen[0])

    def test_conversations_split_at_pauses(self):
        self.assertEqual(ai.conversations(LINES), [[0, 1, 2], [3, 4]])


class InTheReading(unittest.TestCase):
    def find(self, o, claude=None):
        with mock.patch.object(ai, "classify_dialogue", lambda *a, **k: {}), \
                mock.patch.object(ai, "sexual_talk", lambda lines, p=None, c=None: {2}) as st:
            out, how = engine.find_lines(LINES, engine.full_opts(o), True, claude_found=claude)
        return out, how

    def test_added_as_sexual_references(self):
        out, how = self.find(dict(sexref=True))
        line = next(l for l in out if l["idx"] == 2)
        self.assertEqual(line["types"], ["sexref"])
        self.assertTrue(line["mute"])
        self.assertEqual(how, "the AI helper")

    def test_a_listed_word_stays_just_the_word(self):
        lines = LINES[:2] + [{"s": 4.5, "e": 6.0, "text": "I got tree branches poking my boobs"}]
        with mock.patch.object(ai, "classify_dialogue", lambda *a, **k: {}), \
                mock.patch.object(ai, "sexual_talk", lambda l, p=None, c=None: {2}):
            out, _ = engine.find_lines(lines, engine.full_opts(dict(sexref=True)), True)
        (line,) = [l for l in out if l["idx"] == 2]
        self.assertEqual(line["words"], ["boobs"])

    def test_only_with_that_filter(self):
        out, _ = self.find(dict(sexref=False, crude=True))
        self.assertFalse(any(l["idx"] == 2 for l in out))

    def test_not_when_claude_reads(self):
        out, _ = self.find(dict(sexref=True), claude={})
        self.assertFalse(any(l["idx"] == 2 for l in out))


if __name__ == "__main__":
    unittest.main()
