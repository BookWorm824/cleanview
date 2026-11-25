"""A ChatGPT that never starts is stopped soon, said plainly and noted (1.18.169; the owner,
2026-11-25, of CleanListen on her other PC: "ChatGPT couldn't check it" after every part
waited out its 20 minutes, "I don't think you have chat set up correctly", then "you need to
also check CleanView is set up correct"). Codex says "thread.started" first thing; one that
hasn't in START_WAIT is stuck, not slow. Each request leaves a few lines in
chatgpt_log.txt (never what was sent). Nothing here talks to ChatGPT: a stand-in Codex
(a Python script) answers, hangs, or hangs after starting."""
import json
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

import support  # noqa: F401
import cleanview_claude as cc
import cleanview_gpt as gpt

FAKE = "fake-codex.exe"
SCRIPT = r'''
import json, sys, time
how = sys.argv[1]
args = sys.argv[2:]
sys.stdin.read()
if how == "silent":
    time.sleep(60)
print(json.dumps({"type": "thread.started", "thread_id": "t1"}), flush=True)
if how == "slow":
    time.sleep(60)
print(json.dumps({"type": "turn.started"}), flush=True)
print(json.dumps({"type": "item.completed"}), flush=True)
print(json.dumps({"type": "item.completed"}), flush=True)
out = args[args.index("-o") + 1]
open(out, "w", encoding="utf8").write(json.dumps({"lines": []}))
print(json.dumps({"type": "turn.completed"}), flush=True)
'''


class Stall(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        script = self.tmp / "codex_stand_in.py"
        script.write_text(SCRIPT, encoding="utf8")
        self.how = "answer"
        real_popen = subprocess.Popen
        saved = (gpt.APP_DATA, gpt.find, gpt.START_WAIT, subprocess.Popen, gpt._env)

        def popen(cmd, *a, **k):
            if isinstance(cmd, list) and cmd and cmd[0] == FAKE:
                cmd = [sys.executable, str(script), self.how] + cmd[1:]
            return real_popen(cmd, *a, **k)

        gpt.APP_DATA = self.tmp / "app"
        gpt.find = lambda: FAKE
        gpt.START_WAIT = 2
        gpt._env = lambda folder=None: None
        subprocess.Popen = popen

        def undo():
            (gpt.APP_DATA, gpt.find, gpt.START_WAIT, subprocess.Popen, gpt._env) = saved
            shutil.rmtree(self.tmp, ignore_errors=True)
        self.addCleanup(undo)

    def log(self):
        return (gpt.APP_DATA / "chatgpt" / "chatgpt_log.txt").read_text("utf8")

    def ask(self, timeout=6):
        return gpt.ask("Find the bad lines.", {"type": "object", "properties": {}},
                       "SECRET DIALOGUE LINE", timeout=timeout)

    def test_an_answer(self):
        answer, sid = self.ask()
        self.assertEqual(answer, {"lines": []})
        self.assertEqual(sid, "t1")
        log = self.log()
        self.assertIn("exit 0", log)
        self.assertIn("messages: thread.started > turn.started > item.completed > "
                      "turn.completed", log)                 # repeats said once
        self.assertNotIn("SECRET DIALOGUE LINE", log)        # never what was sent
        self.assertNotIn("Find the bad lines", log)

    def test_never_started_is_stopped_soon(self):
        self.how = "silent"
        t0 = time.monotonic()
        with self.assertRaises(gpt.GptError) as ex:
            self.ask(timeout=30)
        self.assertLess(time.monotonic() - t0, 20)           # not the whole 30
        self.assertEqual(str(ex.exception), gpt.NOT_STARTED)
        self.assertIn("didn't start on this PC", gpt.NOT_STARTED)
        log = self.log()
        self.assertIn("TIMED OUT", log)
        self.assertIn("messages: (none)", log)
        self.assertEqual(list((gpt.APP_DATA / "chatgpt").glob("tmp*")), [])   # tidied

    def test_started_but_slow_took_too_long(self):
        self.how = "slow"
        with self.assertRaises(gpt.GptError) as ex:
            self.ask(timeout=4)
        self.assertIn("took too long", str(ex.exception))
        self.assertIn("messages: thread.started", self.log())

    def test_log_stays_short(self):
        log = gpt.APP_DATA / "chatgpt" / "chatgpt_log.txt"
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text(("old line\n" * 40_000), encoding="utf8")     # 360 KB
        self.ask()
        text = self.log()
        self.assertLess(len(text), gpt.LOG_KEEP + 2_000)
        self.assertTrue(text.rstrip().splitlines()[-2].endswith(
            "chars · fake-codex.exe exec -s read-only -C empty --color never"),
            text.rstrip().splitlines()[-2])          # the first 8 words, folders by name


class NoUseAskingAgain(unittest.TestCase):
    """The dialogue is read in parts, each asked twice: a ChatGPT that didn't start (or isn't
    signed in, or is out of uses) isn't asked again, nor for the parts after."""

    def setUp(self):
        saved = cc.ask
        self.addCleanup(lambda: setattr(cc, "ask", saved))
        self.asked = 0

    def reading(self, error):
        def ask(*a, **k):
            self.asked += 1
            raise cc.ClaudeError(error)
        cc.ask = ask
        lines = [{"text": f"line {n}", "s": n, "e": n + 1} for n in range(1500)]
        unread = []
        with self.assertRaises(cc.ClaudeError):
            cc.check_dialogue(lines, None, ["sexref"], chunk=500, unread=unread)
        return unread

    def test_didnt_start_asks_once(self):
        unread = self.reading(gpt.NOT_STARTED)
        self.assertEqual(self.asked, 1)
        self.assertEqual(unread, [(0, 500), (500, 1000), (1000, 1500)])

    def test_signed_out_asks_once(self):
        self.reading("ChatGPT isn't signed in. Use the Sign in button, then try again.")
        self.assertEqual(self.asked, 1)

    def test_other_trouble_is_asked_again(self):
        self.reading("ChatGPT couldn't answer: something odd")
        self.assertEqual(self.asked, 4)          # the first two parts, twice each, as before


if __name__ == "__main__":
    unittest.main()
