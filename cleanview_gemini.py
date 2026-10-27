"""
Gemini inside CleanView, through Google's Gemini CLI program on this PC.

The Gemini CLI is Google's own program. Signed in with your Google account it
uses your own Gemini allowance (no API key, nothing extra to pay). CleanView
sends it only the episode's dialogue as text (and, if you let it look at the
picture, small still pictures), never video or sound. It runs in an empty
folder, where it can't change anything: in this hands-off mode the CLI leaves
out its tools that would need someone to approve them.

Unlike Claude Code and Codex, the CLI can't be handed the exact shape of the
answer, so the shape is described in the request and the answer is checked
(and asked for once more if it doesn't fit). Chats are kept here, not by the CLI.
"""
import json
import os
import re
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

import cleanview_accounts as accounts

APP_DATA = Path(os.environ.get("LOCALAPPDATA") or Path.home() / ".local" / "share") / "CleanView"
_NOWIN = {"creationflags": 0x08000000} if os.name == "nt" else {}
MODEL = os.environ.get("CLEANVIEW_GEMINI_MODEL", "")       # empty: the CLI's own choice
PACKAGE = "@google/gemini-cli"


class GeminiError(Exception):
    pass


def _npm_dirs():
    ad = Path(os.environ.get("APPDATA", ""))
    return [ad / "npm"] if str(ad) not in (".", "") else []


def find():
    """The Gemini CLI as a command to run: [node, the CLI's script] where possible (no
    command-prompt quoting in between), else the gemini command itself. None if missing."""
    exe = shutil.which("gemini")
    places = [Path(exe).parent] if exe else []
    places += _npm_dirs()
    node = shutil.which("node") or next(
        (str(p) for p in (Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "nodejs" /
                          "node.exe",) if p.exists()), None)
    for d in places:
        script = d / "node_modules" / "@google" / "gemini-cli" / "dist" / "index.js"
        if node and script.exists():
            return [node, str(script)]
    if exe:
        return [exe]
    for d in _npm_dirs():
        for name in ("gemini.cmd", "gemini"):
            if (d / name).exists():
                return [str(d / name)]
    return None


def _npm():
    npm = shutil.which("npm")
    if npm:
        return npm
    p = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "nodejs" / "npm.cmd"
    return str(p) if p.exists() else None


def install(progress=None):
    """Install Google's Gemini CLI for this user (npm, no admin rights). It needs Node.js;
    if that's missing too, Windows' own installer adds it (Windows may ask first)."""
    say = progress or (lambda f, m: None)
    if os.name != "nt":
        raise GeminiError("Install the Gemini CLI from github.com/google-gemini/gemini-cli, then "
                          "try again.")
    if not _npm():
        say(0.1, "Installing Node.js, which the Gemini CLI needs…")
        subprocess.run(["winget", "install", "-e", "--id", "OpenJS.NodeJS.LTS", "--silent",
                        "--accept-package-agreements", "--accept-source-agreements"],
                       capture_output=True, text=True, timeout=1200, **_NOWIN)
        if not _npm():
            raise GeminiError("Node.js didn't install, and the Gemini CLI needs it. Install "
                              "Node.js from nodejs.org, then try again.")
    say(0.5, "Installing the Gemini CLI (Google's program that lets CleanView talk to Gemini)…")
    r = subprocess.run([_npm(), "install", "-g", PACKAGE], capture_output=True, text=True,
                       timeout=1200, **_NOWIN)
    if not find():
        raise GeminiError("The Gemini CLI didn't install.\n\n" + (r.stderr or r.stdout)[-500:])
    say(1.0, "The Gemini CLI is installed.")


def _env(folder=None):
    """folder: a sign-in folder of CleanView's own (cleanview_accounts); else the one in use."""
    env = dict(os.environ, NO_COLOR="1")
    for k in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):   # always your Google account, never a paid key
        env.pop(k, None)
    return accounts.env("gemini", env, folder)


def _home(folder=None):
    """The folder the CLI keeps .gemini in (GEMINI_CLI_HOME, else your user folder)."""
    return Path(folder or accounts.home("gemini") or os.environ.get("GEMINI_CLI_HOME")
                or Path.home())


def signed_in(folder=None):
    """Signed in with Google: the CLI keeps that sign-in in .gemini in its home folder."""
    return find() is not None and (_home(folder) / ".gemini" / "oauth_creds.json").exists()


def account_name(folder=None):
    """The email of the Google account signed in ("" if it can't tell)."""
    try:
        d = json.loads((_home(folder) / ".gemini" / "google_accounts.json").read_text("utf8"))
        return d.get("active") or ""
    except Exception:
        return ""


def open_sign_in(folder=None):
    """Open the CLI in a window, where it asks how to sign in: Sign in with Google."""
    cmd = find()
    if not cmd:
        raise GeminiError("The Gemini CLI isn't installed yet.")
    run = " ".join(f'"{c}"' for c in cmd)
    if os.name == "nt":
        subprocess.Popen(["cmd", "/c", "start", "Sign in to Gemini", "cmd", "/k",
                          "echo Choose Sign in with Google, then sign in in the browser window "
                          "that opens. & echo When Gemini is ready for a question, close this "
                          f"window and go back to CleanView. & echo. & {run}"], env=_env(folder))
    else:
        subprocess.Popen(cmd, env=_env(folder))


def status():
    if not find():
        return "missing"
    return "ready" if signed_in() else "signed_out"


_help = {}


def _has_flag(cmd, flag):
    """Older and newer CLIs differ: use a flag only when this one knows it."""
    if "text" not in _help:
        try:
            r = subprocess.run(cmd + ["--help"], capture_output=True, text=True, timeout=60,
                               env=_env(), encoding="utf8", errors="replace", **_NOWIN)
            _help["text"] = r.stdout + r.stderr
        except Exception:
            _help["text"] = ""
    return flag in _help["text"]


def answer_from(text):
    """The JSON object in Gemini's reply (it may come wrapped in ``` fences or words)."""
    text = (text or "").strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    if fenced:
        text = fenced.group(1)
    a, b = text.find("{"), text.rfind("}")
    if a < 0 or b <= a:
        return None
    try:
        out = json.loads(text[a:b + 1])
    except ValueError:
        return None
    return out if isinstance(out, dict) else None


def fits(answer, schema):
    """Has every top-level field the schema asks for (lists may be empty)."""
    return isinstance(answer, dict) and all(k in answer for k in schema.get("required", []))


def _shape(schema):
    return ("\n\nReply with ONLY one JSON object (no other words, no ``` fences) that matches "
            "this JSON Schema; every field listed under \"required\" must be there:\n" +
            json.dumps(schema))


def _chat_file(session):
    return APP_DATA / "gemini" / "chats" / f"{re.sub(r'[^A-Za-z0-9]', '', session)}.json"


def ask(prompt, schema, stdin_text="", system=None, session=None, keep=False, timeout=600,
        images=None):
    """One request to Gemini. Returns (answer_dict, session_id).
    images: [(label, path_to_jpg), ...], shown in that order."""
    cmd = find()
    if not cmd:
        raise GeminiError("Gemini isn't set up yet.")
    work = APP_DATA / "gemini"
    work.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(dir=work))         # empty but for the pictures
    try:
        history = []
        if session and _chat_file(session).exists():
            try:
                history = json.loads(_chat_file(session).read_text("utf8"))
            except ValueError:
                history = []
        refs, labels = [], []
        for k, (label, path) in enumerate(images or [], 1):
            name = f"picture{k}{Path(path).suffix.lower() or '.jpg'}"
            shutil.copyfile(path, tmp / name)
            refs.append("@" + name)
            labels.append(f"Picture {k} ({name}): {label}")
        text = (system + "\n\n" if system else "")
        if labels:
            text += "The pictures attached are, in order:\n" + "\n".join(labels) + "\n\n"
        if history:
            text += "Earlier in this conversation:\n" + "\n".join(
                f"[They asked]\n{h['q']}\n[You answered]\n{json.dumps(h['a'])}" for h in history[-8:]
            ) + "\n\n[Now they ask]\n"
        text += prompt + "\n\nAnswer only from what's given here. Don't run any commands, " \
                         "open other files or search the web."
        if stdin_text:
            text += "\n\n<input>\n" + stdin_text + "\n</input>"
        args = cmd + ["-o", "json", "--approval-mode", "default"]
        if MODEL:
            args += ["-m", MODEL]
        if _has_flag(cmd, "--skip-trust"):
            args.append("--skip-trust")
        answer, last = None, ""
        for attempt in range(2):          # once more if the answer doesn't fit the shape
            nudge = ("" if not attempt else " Your last reply wasn't a JSON object of that "
                     "shape: reply with only the JSON object.")
            # only the @picture names go on the command line (plain words, so no quoting
            # trouble); everything else goes in through stdin, so nothing hits the limit
            p = (" ".join(refs) + " " if refs else "") + "Follow the instructions above." + nudge
            try:
                r = subprocess.run(args + ["-p", p], input=text + _shape(schema),
                                   capture_output=True, text=True, encoding="utf8",
                                   errors="replace", timeout=timeout, cwd=str(tmp), env=_env(),
                                   **_NOWIN)
            except subprocess.TimeoutExpired:
                raise GeminiError("Gemini took too long to answer. Try again.")
            out = r.stdout or ""
            try:
                d = json.loads(out[out.find("{"):]) if "{" in out else {}
            except ValueError:
                d = {}
            err = d.get("error") or {}
            last = str((err.get("message") if isinstance(err, dict) else err) or r.stderr or
                       out)[-400:]
            if r.returncode != 0 or err or "response" not in d:
                low = last.lower()
                if any(k in low for k in ("auth", "login", "credential", "sign in", "401",
                                          "api key", "api_key")):
                    raise GeminiError("Gemini isn't signed in. Use the Sign in button, then "
                                      "try again.")
                if any(k in low for k in ("quota", "rate limit", "429", "resource_exhausted",
                                          "limit reached")):
                    raise GeminiError("You've reached your Gemini usage limit for now. It "
                                      "resets later; CleanView's own checks still work "
                                      "meanwhile.")
                raise GeminiError("Gemini couldn't answer: " + last)
            answer = answer_from(d.get("response"))
            if fits(answer, schema):
                break
            last = str(d.get("response", ""))[-300:]
        if not fits(answer, schema):
            raise GeminiError("Gemini's answer couldn't be read: " + last)
        sid = None
        if session or keep:
            sid = session or uuid.uuid4().hex
            f = _chat_file(sid)
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(json.dumps(history + [{"q": prompt, "a": answer}]), encoding="utf8")
        return answer, sid
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
