"""Each person signing in to their own Claude or ChatGPT inside CleanView
(cleanview_accounts.py). A fake `claude` stands in for Claude Code: it reports the
PC owner's account normally, and another person's when pointed at a CleanView
sign-in folder (CLAUDE_CONFIG_DIR) someone has signed in to."""
import base64
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

import support
import cleanview_accounts as accounts
import cleanview_claude as cc
import cleanview_gpt as gpt

FAKE = r'''
import json, os, sys
folder = os.environ.get("CLAUDE_CONFIG_DIR")
if folder:
    signed = os.path.exists(os.path.join(folder, "signed.txt"))
    who = open(os.path.join(folder, "signed.txt")).read() if signed else None
else:
    who = "owner@example.com"
print(json.dumps({"loggedIn": bool(who), "authMethod": "claude.ai" if who else "none",
                  "email": who}))
'''


def fresh():
    import shutil
    shutil.rmtree(accounts.ACCOUNTS, ignore_errors=True)


class Folders(unittest.TestCase):

    def setUp(self):
        fresh()

    def test_pc_sign_in_used_until_someone_signs_in_here(self):
        self.assertIsNone(accounts.home("claude"))
        self.assertNotIn("CLAUDE_CONFIG_DIR", accounts.env("claude", {}))

    def test_new_sign_in_only_used_once_kept(self):
        d = accounts.new_folder("claude")
        self.assertIsNone(accounts.home("claude"), "nothing changes while signing in")
        accounts.keep("claude", d)
        self.assertEqual(accounts.home("claude"), d)
        self.assertEqual(accounts.env("claude", {})["CLAUDE_CONFIG_DIR"], str(d))
        self.assertEqual(accounts.env("chatgpt", {}), {}, "each AI separately")

    def test_switching_again_removes_the_old_one(self):
        first = accounts.new_folder("chatgpt")
        accounts.keep("chatgpt", first)
        second = accounts.new_folder("chatgpt")
        self.assertTrue(first.exists(), "the old one stays until the new one worked")
        accounts.keep("chatgpt", second)
        self.assertFalse(first.exists())
        self.assertEqual(accounts.env("chatgpt", {})["CODEX_HOME"], str(second))

    def test_given_up_sign_in_cleared_next_time(self):
        abandoned = accounts.new_folder("claude")
        accounts.new_folder("claude")
        self.assertFalse(abandoned.exists())

    def test_sign_out_goes_back_to_the_pc(self):
        d = accounts.new_folder("claude")
        accounts.keep("claude", d)
        accounts.forget("claude")
        self.assertIsNone(accounts.home("claude"))
        self.assertFalse(d.exists())


class ClaudeAccounts(unittest.TestCase):

    def setUp(self):
        fresh()
        self.dir = Path(tempfile.mkdtemp(dir=support.SANDBOX))
        (self.dir / "fake_claude.py").write_text(FAKE, encoding="utf8")
        if os.name == "nt":
            exe = self.dir / "claude.cmd"
            exe.write_text(f'@"{sys.executable}" -I "{self.dir / "fake_claude.py"}" %*\n')
        else:
            exe = self.dir / "claude"
            exe.write_text(f'#!/bin/sh\nexec "{sys.executable}" -I "{self.dir / "fake_claude.py"}" "$@"\n')
            exe.chmod(0o755)
        self.saved = cc.find_claude, cc.open_sign_in
        cc.find_claude = lambda: str(exe)
        self.opened = []
        cc.open_sign_in = lambda folder=None: self.opened.append(folder)
        os.environ.pop("CLAUDE_CONFIG_DIR", None)

    def tearDown(self):
        cc.find_claude, cc.open_sign_in = self.saved
        cc.use("claude")

    def test_whose_account(self):
        self.assertEqual(cc.who("claude"), "owner@example.com")
        self.assertFalse(cc.own_account("claude"))

    def test_someone_else_signs_in(self):
        folder = cc.start_other_account("claude")
        self.assertEqual(self.opened, [folder], "the sign-in opens in CleanView's own folder")
        self.assertFalse(cc.other_account_ready(folder, "claude"))
        (folder / "signed.txt").write_text("sister@example.com")
        self.assertTrue(cc.other_account_ready(folder, "claude"))
        self.assertEqual(cc.who("claude"), "owner@example.com", "not used until kept")
        cc.keep_account(folder, "claude")
        self.assertEqual(cc.who("claude"), "sister@example.com")
        self.assertEqual(cc.status("claude"), "ready")
        self.assertEqual(cc._env()["CLAUDE_CONFIG_DIR"], str(folder), "questions use hers")
        cc.sign_out("claude")
        self.assertEqual(cc.who("claude"), "owner@example.com")
        self.assertNotIn("CLAUDE_CONFIG_DIR", cc._env())

    def test_gemini_not_switched(self):
        self.assertFalse(cc.can_switch("gemini"))
        self.assertEqual(cc.who("gemini"), "")


class ChatGptAccountName(unittest.TestCase):

    def setUp(self):
        fresh()

    def test_email_read_from_the_sign_in(self):
        claims = base64.urlsafe_b64encode(json.dumps({"email": "kid@example.com"}).encode())
        token = "x." + claims.decode().rstrip("=") + ".y"
        folder = accounts.new_folder("chatgpt")
        (folder / "auth.json").write_text(json.dumps({"tokens": {"id_token": token}}))
        self.assertEqual(gpt.account_name(folder), "kid@example.com")
        accounts.keep("chatgpt", folder)
        self.assertEqual(gpt.account_name(), "kid@example.com")
        self.assertEqual(gpt._env()["CODEX_HOME"], str(folder))

    def test_no_sign_in_no_name(self):
        self.assertEqual(gpt.account_name(accounts.new_folder("chatgpt")), "")


if __name__ == "__main__":
    unittest.main()
