"""Claude's and ChatGPT's answers are saved, so the same episode comes out the same
each run: the same question gets the saved answer, a different one asks again,
"Review everything again" always asks again, and chats are never reused.
Nothing here talks to Claude or ChatGPT: the asking itself is faked."""
import itertools
import shutil
import unittest
from pathlib import Path

import support
import cleanview as engine
import cleanview_claude as cc


class SavedAnswers(unittest.TestCase):

    def setUp(self):
        shutil.rmtree(cc.ANSWERS, ignore_errors=True)
        self.asked = []
        n = itertools.count(1)

        def fake(prompt, schema, stdin_text="", system=None, session=None, keep=False,
                 timeout=600, images=None):
            self.asked.append(prompt)
            return {"answer": next(n)}, None     # a different answer every time it's asked
        self.saved_fn, cc._ask_now = cc._ask_now, fake
        self.saved_provider = cc.PROVIDER

    def tearDown(self):
        cc._ask_now = self.saved_fn
        cc.use(self.saved_provider)

    def ask(self, prompt="Which lines?", **kw):
        return cc.ask(prompt, {"type": "object"}, "1. a line", system="be careful", **kw)[0]

    def test_same_question_same_answer(self):
        first = self.ask()
        self.assertEqual(self.ask(), first)
        self.assertEqual(len(self.asked), 1)

    def test_different_question_asks_again(self):
        self.assertNotEqual(self.ask("Which lines?"), self.ask("Which scenes?"))
        self.assertNotEqual(cc.ask("Which lines?", {"type": "object"}, "2. another line")[0],
                            self.ask())

    def test_fresh_asks_again_and_keeps_the_new_answer(self):
        first = self.ask()
        again = self.ask(fresh=True)
        self.assertNotEqual(again, first)
        self.assertEqual(self.ask(), again)

    def test_chats_are_never_reused(self):
        cc.ask("hi", {"type": "object"}, keep=True)
        cc.ask("hi", {"type": "object"}, keep=True)
        cc.ask("hi", {"type": "object"}, session="abc")
        self.assertEqual(len(self.asked), 3)

    def test_claude_and_chatgpt_are_kept_apart(self):
        cc.use("claude")
        a = self.ask()
        cc.use("chatgpt")
        self.assertNotEqual(self.ask(), a)

    def test_pictures_count_by_what_is_in_them(self):
        d = support.SANDBOX / "pics"
        d.mkdir(exist_ok=True)
        (d / "a.jpg").write_bytes(b"picture one")
        (d / "b.jpg").write_bytes(b"picture one")          # same picture, made again
        (d / "c.jpg").write_bytes(b"picture two")
        first = self.ask(images=[("sheet 1", d / "a.jpg")])
        self.assertEqual(self.ask(images=[("sheet 1", d / "b.jpg")]), first)
        self.assertNotEqual(self.ask(images=[("sheet 1", d / "c.jpg")]), first)

    def test_a_damaged_saved_answer_is_asked_again(self):
        self.ask()
        for f in cc.ANSWERS.glob("*.json"):
            f.write_text("{not json", encoding="utf8")
        self.ask()
        self.assertEqual(len(self.asked), 2)

    def test_a_failed_answer_is_not_saved(self):
        def broken(*a, **k):
            raise cc.ClaudeError("Claude took too long to answer. Try again.")
        cc._ask_now = broken
        with self.assertRaises(cc.ClaudeError):
            self.ask()
        self.assertEqual(list(cc.ANSWERS.glob("*.json")) if cc.ANSWERS.exists() else [], [])

    def test_old_answers_are_cleared_out(self):
        saved, cc.KEEP_ANSWERS = cc.KEEP_ANSWERS, 3
        try:
            for k in range(6):
                self.ask(f"question {k}")
            self.assertEqual(len(list(cc.ANSWERS.glob("*.json"))), 3)
        finally:
            cc.KEEP_ANSWERS = saved


class ReviewEverythingAgain(unittest.TestCase):
    """The button really asks again; the review during a scan uses the saved answer."""

    def test_fresh_reaches_the_question(self):
        seen = []

        def fake_review(st, wanted, examples=None, extra_sounds="", fresh=False):
            seen.append(fresh)
            return {}, {}, [], [], ""
        saved, cc.review = cc.review, fake_review
        try:
            st = support.sample_review()
            engine.claude_review(st)
            engine.claude_review(st, fresh=True)
        finally:
            cc.review = saved
        self.assertEqual(seen, [False, True])


@unittest.skipUnless(support.FFMPEG, "no ffmpeg here")
class SheetsAreTheSameEachRun(unittest.TestCase):
    """Saved answers about pictures only help if the contact sheets made from the same
    video come out exactly the same each time."""

    def test_same_bytes(self):
        import subprocess
        video = support.SANDBOX / "sheets.mp4"
        subprocess.run([support.FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i",
                        "testsrc=size=320x240:rate=25:duration=50", "-c:v", "mpeg4", str(video)],
                       check=True, capture_output=True)
        work = support.SANDBOX / "sheets-work"
        first = [Path(p).read_bytes() for p, _ in engine.make_sheets(video, work, 50)]
        second = [Path(p).read_bytes() for p, _ in engine.make_sheets(video, work, 50)]
        self.assertEqual(len(first), 2)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
