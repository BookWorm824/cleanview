"""CleanListen 1.15.3's Blue Ridge findings, as they apply to CleanView (2026-11-05):
1. Claude learns from her, not from itself: its own past answers were shown to it as "this
   family has muted / chose NOT to mute", so a mistake it made once came back as her choice.
2. A part of Claude's dialogue reading that fails is asked once more, and if it fails again
   only that part is read by the AI on this PC; the rest of Claude's reading is kept."""
import importlib.util
import unittest
from unittest import mock

import support

import cleanview as engine
import cleanview_ai as ai
import cleanview_claude as cc
import cleanview_learn as learn

_spec = importlib.util.spec_from_file_location("merge_learned",
                                               support.ROOT / "tools" / "merge_learned.py")
merge_learned = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(merge_learned)


def dialogue(n):
    return [{"s": k * 3.0, "e": k * 3.0 + 2.0, "text": f"plain line number {k}"}
            for k in range(n)]


class OnlyHerChoices(unittest.TestCase):
    def setUp(self):
        d = learn.load("fromher")
        d["muted"].append("she muted this line")
        d["kept"].append("she kept this line")
        d["claude_muted"].append("claude wanted this gone")
        d["claude_kept"].append("claude thought this fine")
        learn.save("fromher", d)

    def test_claude_is_not_shown_its_own_answers_as_hers(self):
        ex = learn.examples("fromher")
        self.assertIn("she muted this line", ex["muted"])
        self.assertIn("she kept this line", ex["kept"])
        self.assertNotIn("claude wanted this gone", ex["muted"])
        self.assertNotIn("claude thought this fine", ex["kept"])
        told = cc._examples(ex)
        self.assertNotIn("claude wanted", told)
        self.assertNotIn("claude thought", told)

    def test_shared_lines_are_families_choices_only(self):
        shared = {}
        merge_learned.merge(shared, {"shows": {"show": {
            "muted": ["she muted this"], "kept": ["she kept this"],
            "claude_muted": ["claude wanted this gone"], "claude_kept": ["claude thought fine"]}}})
        sh = shared["shows"]["show"]
        self.assertEqual(sh["muted"], ["she muted this"])
        self.assertEqual(sh["kept"], ["she kept this"])


class FailedPart(unittest.TestCase):
    """The asking is faked: each part of 500 lines is one question."""

    def ask_with(self, fails):
        """fails: {part number: how many times it fails before answering}"""
        self.calls = []

        def fake(prompt, schema, text="", **k):
            part = self._part(text)
            self.calls.append(part)
            if fails.get(part, 0) > self.calls.count(part) - 1:
                raise cc.ClaudeError("Claude didn't answer in time")
            return {"lines": [{"line": 1, "type": "sexref", "why": "x"}], "scenes": []}, None
        p = mock.patch.object(cc, "ask", fake)
        p.start()
        self.addCleanup(p.stop)

    def _part(self, text):
        # numbered() starts each part at line 1: tell the parts apart by the first time shown
        for n, start in enumerate(self.starts):
            if start in text.splitlines()[0]:
                return n
        return -1

    def setUp(self):
        self.lines = dialogue(1300)                     # three parts: 0-499, 500-999, 1000-1299
        self.starts = [f"line number {a}" for a in (0, 500, 1000)]

    def read(self, unread):
        return cc.check_dialogue(self.lines, None, ["sexref"], unread=unread)

    def test_asked_once_more(self):
        self.ask_with({1: 1})
        unread = []
        found, _ = self.read(unread)
        self.assertEqual(unread, [])
        self.assertEqual(sorted(found), [0, 500, 1000])
        self.assertEqual(self.calls.count(1), 2)

    def test_the_rest_is_kept_when_a_part_fails_again(self):
        self.ask_with({1: 2})
        unread = []
        found, _ = self.read(unread)
        self.assertEqual(unread, [(500, 1000)])
        self.assertEqual(sorted(found), [0, 1000])

    def test_last_part_failing(self):
        self.ask_with({2: 2})
        unread = []
        self.read(unread)
        self.assertEqual(unread, [(1000, 1300)])

    def test_not_working_at_all_is_still_an_error(self):
        self.ask_with({0: 9, 1: 9, 2: 9})
        with self.assertRaises(cc.ClaudeError):
            self.read([])
        self.assertEqual(self.calls, [0, 0, 1, 1], "stops after the first two parts")

    def test_without_a_list_it_is_an_error_as_before(self):
        self.ask_with({1: 2})
        with self.assertRaises(cc.ClaudeError):
            self.read(None)

    def test_one_part_that_fails_is_an_error(self):
        self.lines = dialogue(40)
        self.ask_with({0: 2})
        with self.assertRaises(cc.ClaudeError):
            self.read([])


class OnlyThatPartReadOnThisPC(unittest.TestCase):
    def test_the_ai_on_this_pc_reads_just_the_unread_part(self):
        lines = dialogue(6)
        got = []

        def classify(part, wanted, progress=None, cancel=None, **k):
            got.append([l["text"] for l in part])
            return {1: {"sexref"}}
        with mock.patch.object(ai, "classify_dialogue", classify):
            out, how = engine.find_lines(lines, engine.full_opts({"sexref": True}), True,
                                         claude_found={0: {"sexref"}}, unread=[(3, 5)])
        self.assertEqual(got, [["plain line number 3", "plain line number 4"]])
        self.assertEqual(sorted(l["idx"] for l in out), [0, 4])
        self.assertIn("the AI helper", how)

    def test_nothing_unread_is_claude_alone(self):
        with mock.patch.object(ai, "classify_dialogue", side_effect=AssertionError):
            out, how = engine.find_lines(dialogue(3), engine.full_opts({"sexref": True}), True,
                                         claude_found={0: {"sexref"}})
        self.assertNotIn("AI helper", how)


if __name__ == "__main__":
    unittest.main()
