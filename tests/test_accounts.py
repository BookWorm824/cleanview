"""Each person signing in to their own Claude, ChatGPT or Gemini inside CleanView
(cleanview_accounts.py). A fake `claude` stands in for Claude Code: it reports the
PC owner's account normally, and another person's when pointed at a CleanView
sign-in folder (CLAUDE_CONFIG_DIR) someone has signed in to."""
import base64
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import support
import cleanview_accounts as accounts
import cleanview_claude as cc
import cleanview_gemini as gem
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


class GeminiAccounts(unittest.TestCase):
    """The Gemini CLI keeps its Google sign-in in .gemini under GEMINI_CLI_HOME."""

    def setUp(self):
        fresh()
        self.saved = gem.find, gem.open_sign_in
        gem.find = lambda: ["gemini"]
        self.opened = []
        gem.open_sign_in = lambda folder=None: self.opened.append(folder)
        self.home, Path.home = Path.home, classmethod(
            lambda cls: support.SANDBOX / "pc-home")
        (support.SANDBOX / "pc-home" / ".gemini").mkdir(parents=True, exist_ok=True)
        self.sign_in(support.SANDBOX / "pc-home", "owner@example.com")
        os.environ.pop("GEMINI_CLI_HOME", None)

    def tearDown(self):
        gem.find, gem.open_sign_in = self.saved
        Path.home = self.home

    @staticmethod
    def sign_in(home, email):
        (home / ".gemini").mkdir(parents=True, exist_ok=True)
        (home / ".gemini" / "oauth_creds.json").write_text("{}")
        (home / ".gemini" / "google_accounts.json").write_text(
            json.dumps({"active": email, "old": []}))

    def test_someone_else_signs_in(self):
        self.assertTrue(cc.can_switch("gemini"))
        self.assertEqual(cc.who("gemini"), "owner@example.com")
        folder = cc.start_other_account("gemini")
        self.assertEqual(self.opened, [folder])
        self.assertFalse(cc.other_account_ready(folder, "gemini"))
        self.sign_in(folder, "sister@example.com")
        cc.keep_account(folder, "gemini")
        self.assertEqual(cc.who("gemini"), "sister@example.com")
        self.assertEqual(cc.status("gemini"), "ready")
        self.assertEqual(gem._env()["GEMINI_CLI_HOME"], str(folder), "questions use hers")
        cc.sign_out("gemini")
        self.assertEqual(cc.who("gemini"), "owner@example.com")
        self.assertNotIn("GEMINI_CLI_HOME", gem._env())


@unittest.skipUnless(os.name == "nt", "the sign-in window is for Windows")
class SignInWindow(unittest.TestCase):
    """1.13.x passed the program's path inside "cmd /k ...", quoted the Python way
    (\\"C:\\...\\"): cmd couldn't run it, so the black window opened and nothing else."""

    def test_the_program_really_runs(self):
        folder = support.SANDBOX / "a folder with spaces"
        folder.mkdir(exist_ok=True)
        script = folder / "pretend sign-in.py"
        script.write_text("import sys; print('SIGNED-IN', sys.argv[1:])", encoding="utf8")
        bat = accounts.sign_in_script("claude", "Sign in to Claude",
                                      ["Sign in to Claude in the web page that opens.", ""],
                                      [sys.executable, "-I", str(script), "auth", "login"])
        r = subprocess.run(["cmd", "/c", str(bat)], capture_output=True, text=True,
                           encoding="utf8", errors="replace", timeout=60)
        self.assertIn("Sign in to Claude in the web page that opens.", r.stdout)
        self.assertIn("SIGNED-IN ['auth', 'login']", r.stdout)
        self.assertNotIn("not recognized", r.stdout + r.stderr)

    def test_each_ai_opens_its_window_with_its_own_sign_in(self):
        opened = []
        saved = accounts.subprocess.Popen
        accounts.subprocess.Popen = lambda args, **kw: opened.append((args, kw.get("env")))
        saved_find, gem_find = cc.find_claude, gem.find
        cc.find_claude = lambda: r"C:\Users\Jason Smith\.local\bin\claude.exe"
        gem.find = lambda: [r"C:\Program Files\nodejs\node.exe", r"C:\npm\gemini\index.js"]
        saved_gpt = gpt.find
        gpt.find = lambda: r"C:\Users\Jason Smith\codex.exe"
        try:
            cc.open_sign_in()
            gpt.open_sign_in()
            gem.open_sign_in()
        finally:
            accounts.subprocess.Popen = saved
            cc.find_claude, gem.find, gpt.find = saved_find, gem_find, saved_gpt
        self.assertEqual(len(opened), 3)
        for (args, env), ai, line in zip(opened, ("claude", "chatgpt", "gemini"), (
                r'"C:\Users\Jason Smith\.local\bin\claude.exe" "auth" "login"',
                r'"C:\Users\Jason Smith\codex.exe" "login"',
                r'"C:\Program Files\nodejs\node.exe" "C:\npm\gemini\index.js"')):
            self.assertEqual(args[:3] + args[4:6], ["cmd", "/c", "start", "cmd", "/k"])
            self.assertFalse(any('\\"' in a for a in args), "no Python-style quotes for cmd")
            bat = Path(args[-1])
            self.assertEqual(bat.name, f"{ai}.cmd")
            self.assertIn(line, bat.read_text(encoding="utf8"))
            self.assertNotIn("ANTHROPIC_API_KEY", env)


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
