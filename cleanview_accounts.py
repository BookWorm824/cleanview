"""
Each person's own Claude, ChatGPT or Gemini account, signed in inside CleanView.

Claude Code, Codex and the Gemini CLI keep their sign-in in a folder (CLAUDE_CONFIG_DIR,
CODEX_HOME, GEMINI_CLI_HOME).
Signing in to a different account from CleanView uses a folder of CleanView's own
(APP_DATA\\accounts\\<ai>\\<n>), so a family member can use their own plan on the same PC
without signing anyone out, and the sign-in Claude Code or Codex has for the PC's owner is
never changed. With no account of CleanView's own, the PC's sign-in is used, as before.

A new sign-in goes into a new folder and only replaces the one in use once it worked, so
closing the browser half way leaves things as they were.
"""
import json
import os
import shutil
import time
from pathlib import Path

APP_DATA = Path(os.environ.get("LOCALAPPDATA") or Path.home() / ".local" / "share") / "CleanView"
ACCOUNTS = APP_DATA / "accounts"
HOME_VAR = {"claude": "CLAUDE_CONFIG_DIR", "chatgpt": "CODEX_HOME", "gemini": "GEMINI_CLI_HOME"}


def _read():
    try:
        return json.loads((ACCOUNTS / "using.json").read_text(encoding="utf8"))
    except Exception:
        return {}


def _write(d):
    ACCOUNTS.mkdir(parents=True, exist_ok=True)
    (ACCOUNTS / "using.json").write_text(json.dumps(d), encoding="utf8")


def home(ai):
    """The folder of CleanView's own sign-in in use for ai, or None (the PC's own)."""
    name = _read().get(ai)
    p = ACCOUNTS / ai / name if name else None
    return p if p and p.is_dir() else None


def env(ai, base, folder=None):
    """base (an environment dict) pointed at folder, or at the sign-in in use."""
    folder = folder or home(ai)
    if folder and ai in HOME_VAR:
        base[HOME_VAR[ai]] = str(folder)
    return base


def _tidy(ai, keep=None):
    """Remove sign-in folders nobody uses (a sign-in given up half way)."""
    using = home(ai)
    for d in (ACCOUNTS / ai).glob("*") if (ACCOUNTS / ai).is_dir() else ():
        if d.is_dir() and d != using and d != keep:
            shutil.rmtree(d, ignore_errors=True)


def new_folder(ai):
    """An empty folder for signing in to another account (not used until keep())."""
    _tidy(ai)
    d = ACCOUNTS / ai / str(int(time.time() * 1000))
    d.mkdir(parents=True, exist_ok=True)
    return d


def keep(ai, folder):
    """Use the account just signed in to in folder from now on."""
    d = _read()
    d[ai] = Path(folder).name
    _write(d)
    _tidy(ai)


def forget(ai):
    """Sign out of CleanView's own account; the PC's own sign-in is used again."""
    d = _read()
    d.pop(ai, None)
    _write(d)
    _tidy(ai)
