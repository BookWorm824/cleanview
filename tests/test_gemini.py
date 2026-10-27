"""Gemini, through Google's Gemini CLI, driven like Claude and ChatGPT. A fake `gemini`
(a little Python script) stands in for the CLI: it answers the way the real one does
(`-o json`: {"response": ..., "error": ...}) and reports what it was sent."""
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import support
import cleanview_claude as cc
import cleanview_gemini as gem

FAKE = r'''
import json, os, sys
argv = sys.argv[1:]
if "--help" in argv:                       # CleanView checks which flags this CLI knows
    print("Options: -p, --prompt  -o, --output-format  -m, --model  --approval-mode")
    sys.exit(0)
p = argv[argv.index("-p") + 1] if "-p" in argv else ""
stdin = sys.stdin.read()
mode = os.environ.get("FAKE_GEMINI", "ok")
state = os.environ.get("FAKE_GEMINI_STATE")
calls = 0
if state:
    calls = int(open(state).read() or 0) if os.path.exists(state) else 0
    open(state, "w").write(str(calls + 1))
if mode == "auth":
    print(json.dumps({"error": {"message": "Please set an Auth method in your settings.json"}}))
    sys.exit(1)
if mode == "quota":
    sys.stderr.write("429 RESOURCE_EXHAUSTED: quota exceeded")
    sys.exit(1)
if mode == "garbage" or (mode == "badfirst" and calls == 0):
    print(json.dumps({"response": "Sure! Here is what I found in the dialogue."}))
    sys.exit(0)
answer = {"lines": [], "scenes": [], "p": p, "argv": argv, "stdin": stdin,
          "files": sorted(os.listdir(".")), "api_key": "GEMINI_API_KEY" in os.environ}
print(json.dumps({"session_id": "abc", "response": "```json\n" + json.dumps(answer) + "\n```",
                  "stats": {}}))
'''
SCHEMA = {"type": "object", "properties": {"lines": {"type": "array"},
                                           "scenes": {"type": "array"}},
          "required": ["lines", "scenes"]}


class FakeGemini(unittest.TestCase):

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(dir=support.SANDBOX))
        (self.dir / "fake_gemini.py").write_text(FAKE, encoding="utf8")
        self.saved_find, gem.find = gem.find, lambda: [sys.executable, "-I",
                                                       str(self.dir / "fake_gemini.py")]
        gem._help.clear()
        self.saved_env = dict(os.environ)
        os.environ["GEMINI_API_KEY"] = "a-paid-key-that-must-not-be-used"

    def tearDown(self):
        gem.find = self.saved_find
        os.environ.clear()
        os.environ.update(self.saved_env)
        cc.use("claude")

    def ask(self, **kw):
        return gem.ask("Which lines?", SCHEMA, stdin_text="1. a line", system="be careful", **kw)

    def test_answer_read_from_its_reply(self):
        answer, sid = self.ask()
        self.assertEqual((answer["lines"], answer["scenes"]), ([], []))
        self.assertIsNone(sid)
        self.assertIn("-o", answer["argv"])
        self.assertEqual(answer["argv"][answer["argv"].index("-o") + 1], "json")

    def test_everything_goes_in_through_stdin(self):
        answer, _ = self.ask()
        for part in ("be careful", "Which lines?", "1. a line", '"required": ["lines", "scenes"]'):
            self.assertIn(part, answer["stdin"])
        self.assertEqual(answer["p"], "Follow the instructions above.")

    def test_never_a_paid_key(self):
        self.assertFalse(self.ask()[0]["api_key"])

    def test_pictures(self):
        a, b = self.dir / "sheet one.jpg", self.dir / "sheet two.jpg"
        a.write_bytes(b"one")
        b.write_bytes(b"two")
        answer, _ = self.ask(images=[("Sheet 1 (0:00 to 0:40):", a), ("Sheet 2 & more", b)])
        self.assertEqual(answer["files"], ["picture1.jpg", "picture2.jpg"])
        self.assertTrue(answer["p"].startswith("@picture1.jpg @picture2.jpg "))
        self.assertIn("Picture 2 (picture2.jpg): Sheet 2 & more", answer["stdin"])
        self.assertEqual(list((support.APP_DATA / "gemini").glob("tmp*")), [],
                         "the work folder is cleared after")

    def test_asked_again_when_the_shape_is_wrong(self):
        os.environ["FAKE_GEMINI"] = "badfirst"
        os.environ["FAKE_GEMINI_STATE"] = str(self.dir / "calls.txt")
        answer, _ = self.ask()
        self.assertIn("reply with only the JSON object", answer["p"])
        self.assertEqual((self.dir / "calls.txt").read_text(), "2")

    def test_gives_up_after_two_tries(self):
        os.environ["FAKE_GEMINI"] = "garbage"
        with self.assertRaises(gem.GeminiError) as e:
            self.ask()
        self.assertIn("couldn't be read", str(e.exception))

    def test_plain_errors(self):
        os.environ["FAKE_GEMINI"] = "auth"
        with self.assertRaisesRegex(gem.GeminiError, "isn't signed in"):
            self.ask()
        os.environ["FAKE_GEMINI"] = "quota"
        with self.assertRaisesRegex(gem.GeminiError, "usage limit"):
            self.ask()

    def test_chats_remember_earlier_turns(self):
        first, sid = gem.ask("What's in scene 3?", SCHEMA, keep=True)
        self.assertTrue(sid)
        second, sid2 = gem.ask("And scene 4?", SCHEMA, session=sid)
        self.assertEqual(sid2, sid)
        self.assertIn("Earlier in this conversation", second["stdin"])
        self.assertIn("What's in scene 3?", second["stdin"])

    def test_through_the_provider_switch(self):
        cc.use("gemini")
        self.assertEqual(cc.name(), "Gemini")
        shutil.rmtree(cc.ANSWERS, ignore_errors=True)
        answer, _ = cc.ask("Which lines?", SCHEMA, "1. a line")
        self.assertEqual(answer["lines"], [])
        os.environ["FAKE_GEMINI"] = "auth"
        with self.assertRaises(cc.ClaudeError):
            cc.ask("Something new?", SCHEMA, "1. a line")


class ReadingReplies(unittest.TestCase):

    def test_answer_from(self):
        self.assertEqual(gem.answer_from('```json\n{"a": 1}\n```'), {"a": 1})
        self.assertEqual(gem.answer_from('Here you go: {"a": [1, 2]} hope that helps'),
                         {"a": [1, 2]})
        self.assertIsNone(gem.answer_from("No JSON here."))
        self.assertIsNone(gem.answer_from("[1, 2]"))

    def test_fits(self):
        self.assertTrue(gem.fits({"lines": [], "scenes": []}, SCHEMA))
        self.assertFalse(gem.fits({"lines": []}, SCHEMA))

    def test_listed_with_the_others(self):
        self.assertIn("gemini", cc.NAMES)
        self.assertIn("gemini", __import__("cleanview").CLOUD)

    def test_signed_in_needs_the_google_sign_in(self):
        saved_find, saved_home = gem.find, Path.home
        home = Path(tempfile.mkdtemp(dir=support.SANDBOX))
        gem.find = lambda: ["gemini"]
        Path.home = classmethod(lambda cls: home)
        try:
            self.assertEqual(gem.status(), "signed_out")
            (home / ".gemini").mkdir()
            (home / ".gemini" / "oauth_creds.json").write_text("{}")
            self.assertEqual(gem.status(), "ready")
            gem.find = lambda: None
            self.assertEqual(gem.status(), "missing")
        finally:
            gem.find, Path.home = saved_find, saved_home


if __name__ == "__main__":
    unittest.main()
