"""
ChatGPT inside CleanView, through OpenAI's Codex program on this PC.

Codex is OpenAI's own program. Signed in with your ChatGPT account, it uses
your ChatGPT plan (Plus, Pro, Business...; no API key, nothing extra to pay).
CleanView sends it only the episode's dialogue as text, never video or sound,
and runs it in an empty folder with read-only access so it only answers.
"""
import base64
import copy
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import cleanview_accounts as accounts

APP_DATA = Path(os.environ.get("LOCALAPPDATA") or Path.home() / ".local" / "share") / "CleanView"
_NOWIN = {"creationflags": 0x08000000} if os.name == "nt" else {}
MODEL = os.environ.get("CLEANVIEW_CHATGPT_MODEL", "")      # empty: your plan's default


class GptError(Exception):
    pass


def find():
    exe = shutil.which("codex")
    if exe:
        return exe
    la = Path(os.environ.get("LOCALAPPDATA", ""))
    ad = Path(os.environ.get("APPDATA", ""))
    for p in (la / "Programs" / "OpenAI" / "Codex" / "bin" / "codex.exe",
              la / "Microsoft" / "WinGet" / "Links" / "codex.exe",
              ad / "npm" / "codex.cmd",
              Path.home() / ".local" / "bin" / "codex"):
        if str(p) not in (".", "") and p.exists():
            return str(p)
    return None


def install(progress=None):
    """Run OpenAI's own installer (per-user, no admin rights)."""
    say = progress or (lambda f, m: None)
    if os.name != "nt":
        raise GptError("Install Codex from chatgpt.com/codex, then try again.")
    say(0.1, "Installing Codex (OpenAI's program that lets CleanView talk to ChatGPT)…")
    env = dict(os.environ, CODEX_NON_INTERACTIVE="1")
    r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
                        "irm https://chatgpt.com/codex/install.ps1 | iex"],
                       capture_output=True, text=True, timeout=900, env=env, **_NOWIN)
    if not find():
        raise GptError("Codex didn't install.\n\n" + (r.stderr or r.stdout)[-500:])
    say(1.0, "Codex is installed.")


def _env(folder=None):
    """folder: a sign-in folder of CleanView's own (cleanview_accounts); else the one in use."""
    env = dict(os.environ)
    for k in ("OPENAI_API_KEY", "CODEX_API_KEY"):   # always use the ChatGPT plan, never a paid key
        env.pop(k, None)
    return accounts.env("chatgpt", env, folder)


def signed_in(folder=None):
    exe = find()
    if not exe:
        return False
    try:
        r = subprocess.run([exe, "login", "status"], capture_output=True, text=True, timeout=30,
                           env=_env(folder), **_NOWIN)
    except Exception:
        return False
    out = (r.stdout + r.stderr).lower()
    return r.returncode == 0 and "not logged in" not in out


def account_name(folder=None):
    """The email of the ChatGPT account signed in, from the sign-in Codex keeps in
    auth.json ("" if it can't tell)."""
    home = Path(folder or accounts.home("chatgpt") or os.environ.get("CODEX_HOME")
                or Path.home() / ".codex")
    try:
        token = json.loads((home / "auth.json").read_text(encoding="utf8"))["tokens"]["id_token"]
        part = token.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))
        return claims.get("email") or ""
    except Exception:
        return ""


def open_sign_in(folder=None):
    exe = find()
    if not exe:
        raise GptError("Codex isn't installed yet.")
    if os.name == "nt":
        subprocess.Popen(["cmd", "/c", "start", "Sign in to ChatGPT", "cmd", "/k",
                          f'echo Sign in with your ChatGPT account in the browser window that '
                          f'opens. & echo When it says you are signed in, close this window and go '
                          f'back to CleanView. & echo. & "{exe}" login'], env=_env(folder))
    else:
        subprocess.Popen([exe, "login"], env=_env(folder))


def status():
    if not find():
        return "missing"
    return "ready" if signed_in() else "signed_out"


def strict(schema):
    """OpenAI's structured output wants every field listed as required and
    no extra fields; optional ones (like "word") just come back empty."""
    s = copy.deepcopy(schema)

    def fix(node):
        if isinstance(node, dict):
            if node.get("type") == "object" and "properties" in node:
                node["required"] = list(node["properties"])
                node["additionalProperties"] = False
            for v in node.values():
                fix(v)
        elif isinstance(node, list):
            for v in node:
                fix(v)
    fix(s)
    return s


def ask(prompt, schema, stdin_text="", system=None, session=None, keep=False, timeout=600,
        images=None):
    """One request to ChatGPT. Returns (answer_dict, session_id).
    images: [(label, path_to_jpg), ...], attached in that order."""
    exe = find()
    if not exe:
        raise GptError("ChatGPT isn't set up yet.")
    work = APP_DATA / "chatgpt"
    work.mkdir(parents=True, exist_ok=True)
    empty = work / "empty"                  # nothing in here for it to look at
    empty.mkdir(exist_ok=True)
    tmp = Path(tempfile.mkdtemp(dir=work))
    sf, of = tmp / "schema.json", tmp / "answer.json"
    sf.write_text(json.dumps(strict(schema)), encoding="utf8")
    full = ((system + "\n\n") if system and not session else "") + prompt + (
        "\n\nAnswer only from the text given here. Don't run any commands, open files or "
        "search the web.")
    common = ["--skip-git-repo-check", "--output-schema", str(sf), "-o", str(of), "--json"]
    if images:
        full = ("The pictures attached are, in order: " +
                "; ".join(f"{k + 1}) {label}" for k, (label, _) in enumerate(images)) +
                ".\n\n" + full)
        for _, path in images:
            common.append(f"--image={path}")   # one per flag, so nothing after is swallowed
    if MODEL:
        common += ["-m", MODEL]
    if session:
        cmd = [exe, "exec", "resume", *common, session, "-"]
        stdin = full if not stdin_text else full + "\n\n<stdin>\n" + stdin_text + "\n</stdin>"
    else:
        cmd = [exe, "exec", "-s", "read-only", "-C", str(empty), "--color", "never", *common]
        if not keep:
            cmd.append("--ephemeral")
        cmd.append("-")
        stdin = full if not stdin_text else full + "\n\n<stdin>\n" + stdin_text + "\n</stdin>"
    try:
        r = subprocess.run(cmd, input=stdin, capture_output=True, text=True, encoding="utf8",
                           errors="replace", timeout=timeout, cwd=str(empty), env=_env(),
                           **_NOWIN)
    except subprocess.TimeoutExpired:
        raise GptError("ChatGPT took too long to answer. Try again.")
    sid, errs = None, []
    for line in (r.stdout or "").splitlines():
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if ev.get("type") == "thread.started":
            sid = ev.get("thread_id")
        elif ev.get("type") in ("error", "turn.failed"):
            e = ev.get("message") or (ev.get("error") or {}).get("message") or ""
            errs.append(str(e))
    try:
        answer = json.loads(of.read_text("utf8"))
    except (OSError, ValueError):
        answer = None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if answer is None or r.returncode != 0 and not isinstance(answer, dict):
        msg = (" ".join(errs) or r.stderr or r.stdout or "")[-400:]
        low = msg.lower()
        if any(k in low for k in ("not logged in", "login", "unauthorized", "401", "sign in")):
            raise GptError("ChatGPT isn't signed in. Use the Sign in button, then try again.")
        if any(k in low for k in ("usage limit", "rate limit", "limit reached", "quota", "429")):
            raise GptError("You've reached your ChatGPT usage limit for now. It resets after a "
                           "while; CleanView's own checks still work meanwhile.")
        raise GptError("ChatGPT couldn't answer: " + msg)
    return answer, sid or session
