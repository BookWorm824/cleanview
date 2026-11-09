"""The AI helper on this PC gives the same answer to the same question: kept in ai_answers, so
a stopped run picks up where it left off and the same episode comes out the same each run
(the owner, 2026-11-09, after CleanListen 1.17.15 did this for CleanRead: "Yes, add it").
Only an identical question counts, and answers that went wrong are never kept."""
import json
import shutil
import unittest
from unittest import mock

import support  # noqa: F401  (sets up the sandbox first)
import cleanview_ai as ai


class FakeOllama:
    def __init__(self, replies):
        self.replies, self.asked = list(replies), []

    def __call__(self, path, payload=None, timeout=10):
        self.asked.append(payload)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        r = mock.MagicMock()
        r.__enter__.return_value = r
        r.read.return_value = json.dumps({"message": {"content": reply}}).encode()
        return r


class SameQuestionSameAnswer(unittest.TestCase):

    def setUp(self):
        shutil.rmtree(ai.ANSWERS, ignore_errors=True)

    def ask(self, fake, *a, **k):
        with mock.patch.object(ai, "_api", fake):
            return ai.chat(*a, **k)

    def test_asked_once(self):
        fake = FakeOllama(['{"fits": true}', '{"fits": false}'])
        self.assertEqual(self.ask(fake, "Is it rude?", schema={"type": "object"}), {"fits": True})
        self.assertEqual(self.ask(fake, "Is it rude?", schema={"type": "object"}), {"fits": True})
        self.assertEqual(len(fake.asked), 1)

    def test_only_the_very_same_question(self):
        fake = FakeOllama(['{"a": 1}'] * 5)
        self.ask(fake, "Is it rude?", model="qwen3:8b")
        self.ask(fake, "Is it rude?!", model="qwen3:8b")              # other words
        self.ask(fake, "Is it rude?", model="qwen2.5:7b")             # another model
        self.ask(fake, "Is it rude?", images=["AAAA"], model="qwen3-vl:8b")
        self.ask(fake, "Is it rude?", images=["BBBB"], model="qwen3-vl:8b")   # other stills
        self.assertEqual(len(fake.asked), 5)

    def test_what_went_wrong_isnt_kept(self):
        fake = FakeOllama([TimeoutError("timed out"), "no answer here", '{"yes": true}'])
        with self.assertRaises(TimeoutError):
            self.ask(fake, "Do you see a fight?")
        with self.assertRaises(ValueError):
            self.ask(fake, "Do you see a fight?")
        self.assertEqual(self.ask(fake, "Do you see a fight?"), {"yes": True})
        self.assertEqual(len(fake.asked), 3)

    def test_a_stopped_closer_look_picks_up(self):
        cands = [{"cat": "smoking", "s": 10.0 * n, "e": 10.0 * n + 5} for n in range(3)]
        fake = FakeOllama(['{"see": "a man smoking", "yes": true, "clear": true}',
                           TimeoutError("stopped here")])
        with mock.patch.object(ai, "_api", fake):
            ai.second_look([dict(c) for c in cands[:2]], lambda c: [f"frame{c['s']}"])
        fake.replies = ['{"see": "a kitchen", "yes": false, "clear": true}'] * 2
        with mock.patch.object(ai, "_api", fake):
            again = ai.second_look([dict(c) for c in cands], lambda c: [f"frame{c['s']}"])
        self.assertEqual(len(fake.asked), 4)            # the first one wasn't asked again
        self.assertEqual([c["verdict"]["keep"] for c in again], [True, False, False])

    def test_the_same_each_run(self):
        fake = FakeOllama(['{"flags": [{"line": 1, "type": "sexref", "words": "had sex"}]}',
                           '{"fits": true}'])
        lines = [{"s": 1.0, "e": 2.0, "text": "They had sex last night."}]
        with mock.patch.object(ai, "_api", fake):
            first = ai.classify_dialogue(lines, ["sexref"])
        with mock.patch.object(ai, "_api", FakeOllama([])):        # nothing asked at all
            second = ai.classify_dialogue(lines, ["sexref"])
        self.assertEqual(first, second)
        self.assertEqual(first, {0: {"sexref"}})


if __name__ == "__main__":
    unittest.main()
