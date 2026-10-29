"""
Claude (or ChatGPT, or Gemini) inside CleanView.

Claude goes through Claude Code, Anthropic's own program: signed in with your
Claude account it uses your Claude plan. ChatGPT goes through Codex, OpenAI's
own program, the same way (see cleanview_gpt.py), and Gemini through Google's
Gemini CLI (cleanview_gemini.py). No API keys, nothing extra to pay. Only the
episode's dialogue is sent, as text, never video or sound.

use("claude") / use("chatgpt") / use("gemini") picks which one the functions
below talk to.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

APP_DATA = Path(os.environ.get("LOCALAPPDATA") or Path.home() / ".local" / "share") / "CleanView"
_NOWIN = {"creationflags": 0x08000000} if os.name == "nt" else {}
MODEL = os.environ.get("CLEANVIEW_CLAUDE_MODEL", "sonnet")


class ClaudeError(Exception):
    pass


import cleanview_accounts as accounts  # noqa: E402
import cleanview_gpt as gpt  # noqa: E402
import cleanview_gemini as gem  # noqa: E402

PROVIDER = "claude"
NAMES = {"claude": "Claude", "chatgpt": "ChatGPT", "gemini": "Gemini"}
OTHERS = {"chatgpt": gpt, "gemini": gem}       # the ones that aren't Claude Code
OTHER_ERRORS = (gpt.GptError, gem.GeminiError)


def use(provider):
    global PROVIDER
    PROVIDER = provider if provider in NAMES else "claude"


def name(provider=None):
    return NAMES.get(provider or PROVIDER, "Claude")


def find_claude():
    exe = shutil.which("claude")
    if exe:
        return exe
    home = Path.home()
    for p in (home / ".local" / "bin" / "claude.exe", home / ".local" / "bin" / "claude",
              Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "claude" / "claude.exe"):
        if p.exists():
            return str(p)
    return None


def install_claude(progress=None):
    """Run Anthropic's own installer (per-user, no admin rights)."""
    say = progress or (lambda f, m: None)
    if os.name != "nt":
        raise ClaudeError("Install Claude Code from claude.com/claude-code, then try again.")
    say(0.1, "Installing Claude Code (Anthropic's program that lets CleanView talk to Claude)…")
    r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
                        "irm https://claude.ai/install.ps1 | iex"],
                       capture_output=True, text=True, timeout=900, **_NOWIN)
    if not find_claude():
        raise ClaudeError("Claude Code didn't install.\n\n" + (r.stderr or r.stdout)[-500:])
    say(1.0, "Claude Code is installed.")


def _env(folder=None):
    """folder: a sign-in folder of CleanView's own (cleanview_accounts); else the one in use."""
    env = dict(os.environ)
    env.pop("ANTHROPIC_API_KEY", None)   # always use the Claude plan, never a paid key
    return accounts.env("claude", env, folder)


def _auth(folder=None):
    """Claude Code's "auth status" ({} if it can't tell)."""
    exe = find_claude()
    if not exe:
        return {}
    try:
        r = subprocess.run([exe, "auth", "status"], capture_output=True, text=True, timeout=30,
                           env=_env(folder), **_NOWIN)
    except Exception:
        return {}
    if r.returncode != 0:
        return {}
    try:
        return json.loads(r.stdout)
    except ValueError:
        return {"authMethod": "unknown"}


def signed_in(folder=None):
    return _auth(folder).get("authMethod", "none") != "none"


def account_name(folder=None):
    """The email of the Claude account signed in ("" if it can't tell)."""
    return _auth(folder).get("email") or ""


def open_sign_in(folder=None):
    """Open a window that walks through signing in with the browser."""
    exe = find_claude()
    if not exe:
        raise ClaudeError("Claude Code isn't installed yet.")
    if os.name == "nt":
        accounts.sign_in_window(
            "claude", "Sign in to Claude",
            ["Sign in to Claude in the web page that opens.",
             "When it says you are signed in, close this window and go back to CleanView.",
             "If no web page opens, hold Ctrl and click the link below."],
            [exe, "auth", "login"], _env(folder))
    else:
        subprocess.Popen([exe, "auth", "login"], env=_env(folder))


def status(provider=None):
    """'missing', 'signed_out' or 'ready'."""
    if (provider or PROVIDER) in OTHERS:
        return OTHERS[provider or PROVIDER].status()
    if not find_claude():
        return "missing"
    return "ready" if signed_in() else "signed_out"


def is_installed(provider=None):
    p = provider or PROVIDER
    return bool(OTHERS[p].find() if p in OTHERS else find_claude())


def is_signed_in(provider=None):
    p = provider or PROVIDER
    return OTHERS[p].signed_in() if p in OTHERS else signed_in()


def install(provider=None):
    p = provider or PROVIDER
    try:
        OTHERS[p].install() if p in OTHERS else install_claude()
    except OTHER_ERRORS as ex:
        raise ClaudeError(str(ex))


def sign_in(provider=None, folder=None):
    p = provider or PROVIDER
    try:
        if folder:
            OTHERS[p].open_sign_in(folder) if p in OTHERS else open_sign_in(folder)
        else:
            OTHERS[p].open_sign_in() if p in OTHERS else open_sign_in()
    except OTHER_ERRORS as ex:
        raise ClaudeError(str(ex))


# Someone else's own account on the same PC (cleanview_accounts).
def can_switch(provider=None):
    return (provider or PROVIDER) in accounts.HOME_VAR


def who(provider=None):
    """The email of the account in use ("" if it can't tell)."""
    p = provider or PROVIDER
    if not can_switch(p):
        return ""
    try:
        return OTHERS[p].account_name() if p in OTHERS else account_name()
    except Exception:
        return ""


def own_account(provider=None):
    """True when CleanView uses an account signed in inside CleanView, not the PC's."""
    return accounts.home(provider or PROVIDER) is not None


def start_other_account(provider=None):
    """Open the sign-in for another account; returns its folder, for other_account_ready()
    and keep_account(). Nothing changes until keep_account()."""
    p = provider or PROVIDER
    folder = accounts.new_folder(p)
    sign_in(p, folder)
    return folder


def other_account_ready(folder, provider=None):
    p = provider or PROVIDER
    return OTHERS[p].signed_in(folder) if p in OTHERS else signed_in(folder)


def keep_account(folder, provider=None):
    accounts.keep(provider or PROVIDER, folder)


def sign_out(provider=None):
    """Sign out of the account signed in inside CleanView (back to the PC's own)."""
    accounts.forget(provider or PROVIDER)


ANSWERS = APP_DATA / "answers"
KEEP_ANSWERS = 3000          # the newest this many are kept (a few MB)


def _answer_key(prompt, schema, stdin_text, system, images):
    """The same question to the same AI: same words, settings, pictures and model."""
    h = hashlib.sha256()
    for part in (PROVIDER, OTHERS[PROVIDER].MODEL if PROVIDER in OTHERS else MODEL, prompt,
                 stdin_text or "", system or "", json.dumps(schema, sort_keys=True)):
        h.update(part.encode("utf8") + b"\0")
    for label, path in images or []:
        h.update(label.encode("utf8") + b"\0" + Path(path).read_bytes())
    return h.hexdigest()[:32]


def _saved_answer(key):
    try:
        return json.loads((ANSWERS / f"{key}.json").read_text("utf8"))["answer"]
    except (OSError, ValueError, KeyError):
        return None


def _save_answer(key, answer):
    try:
        ANSWERS.mkdir(parents=True, exist_ok=True)
        tmp = ANSWERS / f"{key}.tmp"
        tmp.write_text(json.dumps({"answer": answer}), encoding="utf8")
        os.replace(tmp, ANSWERS / f"{key}.json")
        old = sorted(ANSWERS.glob("*.json"), key=lambda f: f.stat().st_mtime)
        for f in old[:-KEEP_ANSWERS]:
            f.unlink()
    except OSError:
        pass


def ask(prompt, schema, stdin_text="", system=None, session=None, keep=False, timeout=600,
        images=None, fresh=False):
    """One request to Claude or ChatGPT. Returns (answer_dict, session_id).
    images: [(label, path_to_jpg), ...] shown before the prompt.
    The same one-off question gets the same answer as last time: the AI doesn't answer
    the same way twice, so without this the same episode came out different each run.
    fresh=True asks again anyway (and keeps the new answer). Chats are never reused."""
    if session or keep:
        return _ask_now(prompt, schema, stdin_text, system, session, keep, timeout, images)
    key = _answer_key(prompt, schema, stdin_text, system, images)
    saved = None if fresh else _saved_answer(key)
    if saved is not None:
        return saved, None
    answer, sid = _ask_now(prompt, schema, stdin_text, system, session, keep, timeout, images)
    _save_answer(key, answer)
    return answer, sid


def _ask_now(prompt, schema, stdin_text="", system=None, session=None, keep=False, timeout=600,
             images=None):
    if PROVIDER in OTHERS:
        try:
            return OTHERS[PROVIDER].ask(prompt, schema, stdin_text, system, session, keep,
                                        timeout, images)
        except OTHER_ERRORS as ex:
            raise ClaudeError(str(ex))
    if images:
        return _ask_images(prompt, schema, images, system, timeout)
    exe = find_claude()
    if not exe:
        raise ClaudeError("Claude isn't set up yet.")
    work = APP_DATA / "claude"
    work.mkdir(parents=True, exist_ok=True)
    cmd = [exe, "-p", prompt, "--output-format", "json", "--json-schema", json.dumps(schema),
           "--tools", "", "--strict-mcp-config", "--model", MODEL]
    if system:
        cmd += ["--system-prompt", system]
    if session:
        cmd += ["--resume", session]
    elif not keep:
        cmd += ["--no-session-persistence"]
    try:
        r = subprocess.run(cmd, input=stdin_text, capture_output=True, text=True,
                           encoding="utf8", errors="replace", timeout=timeout, cwd=str(work),
                           env=_env(), **_NOWIN)
    except subprocess.TimeoutExpired:
        raise ClaudeError("Claude took too long to answer. Try again.")
    out = (r.stdout or "").strip()
    try:
        d = json.loads(out.splitlines()[-1] if out else "{}")
    except ValueError:
        d = {}
    msg = str(d.get("result") or r.stderr or out)[-400:]
    if r.returncode != 0 or d.get("is_error") or "structured_output" not in d:
        low = msg.lower()
        if any(k in low for k in ("not logged in", "login", "authenticat", "/login", "401")):
            raise ClaudeError("Claude isn't signed in. Use the Sign in button, then try again.")
        if any(k in low for k in ("usage limit", "rate limit", "limit reached", "quota")):
            raise ClaudeError("You've reached your Claude usage limit for now. It resets after a "
                              "few hours; CleanView's own checks still work meanwhile.")
        raise ClaudeError("Claude couldn't answer: " + msg)
    return d["structured_output"], d.get("session_id")


def _ask_images(prompt, schema, images, system, timeout):
    """Claude Code with pictures: the request goes in as one message with the
    images in it (stream-json), so no tools are needed."""
    import base64
    exe = find_claude()
    if not exe:
        raise ClaudeError("Claude isn't set up yet.")
    work = APP_DATA / "claude"
    work.mkdir(parents=True, exist_ok=True)
    content = []
    for label, path in images:
        content.append({"type": "text", "text": label})
        content.append({"type": "image", "source": {
            "type": "base64", "media_type": "image/jpeg",
            "data": base64.b64encode(Path(path).read_bytes()).decode()}})
    content.append({"type": "text", "text": prompt})
    msg = json.dumps({"type": "user", "message": {"role": "user", "content": content}})
    cmd = [exe, "-p", "--input-format", "stream-json", "--output-format", "stream-json",
           "--verbose", "--json-schema", json.dumps(schema), "--tools", "",
           "--strict-mcp-config", "--model", MODEL, "--no-session-persistence"]
    if system:
        cmd += ["--system-prompt", system]
    try:
        r = subprocess.run(cmd, input=msg + "\n", capture_output=True, text=True, encoding="utf8",
                           errors="replace", timeout=timeout, cwd=str(work), env=_env(), **_NOWIN)
    except subprocess.TimeoutExpired:
        raise ClaudeError("Claude took too long to answer. Try again.")
    result = {}
    for line in (r.stdout or "").splitlines():
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if ev.get("type") == "result":
            result = ev
    if result.get("is_error") or "structured_output" not in result:
        low = str(result.get("result") or r.stderr or r.stdout)[-400:].lower()
        if any(k in low for k in ("not logged in", "login", "authenticat", "401")):
            raise ClaudeError("Claude isn't signed in. Use the Sign in button, then try again.")
        if any(k in low for k in ("usage limit", "rate limit", "limit reached", "quota")):
            raise ClaudeError("You've reached your Claude usage limit for now. It resets after a "
                              "few hours; CleanView's own checks still work meanwhile.")
        raise ClaudeError("Claude couldn't answer: " + low[-300:])
    return result["structured_output"], None


# ---------------------------------------------------------------------------
# What CleanView asks Claude
# ---------------------------------------------------------------------------
SYSTEM = ("You help a family make movies and TV shows fit their standards by muting dialogue "
          "and cutting scenes. You only ever see the dialogue as numbered lines. Be accurate: "
          "flag what clearly fits what they asked for, and nothing else. When there are no "
          "subtitles the dialogue comes from speech recognition, which mishears names and made-"
          "up words (\"Grafi\" for the character Gruffi): never mute a character's name or a "
          "word just because it looks odd, only words that really are on their list. Don't "
          "lecture or add opinions about their choices.")

TYPE_TEXT = {
    "sexref": "sexual references, sexual jokes or innuendo",
    "casual": "sleeping around: casual sex, hooking up, affairs, cheating",
    "samesex": "same-sex romance or relationships, including flirting or romantic interest "
               "between two men or two women",
    "oppsex": "an unmarried man and woman living or sleeping together",
    "crude": "crude humor: bathroom, bodily-function or gross-out jokes",
    "bullying": "bullying: mocking, taunting, demeaning someone or cruel name-calling",
    "religion": "religious conversations: any talk about God, Jesus, faith, prayer or praying, "
                "church, the Bible, heaven or hell as places, angels, sin, or the beliefs, "
                "practices, clergy or holidays of any religion; the whole conversation, not just "
                "the line that names it. Not: God's or Jesus' name said as a swear or "
                "exclamation, 'bless you' after a sneeze, a character's name",
    "christmas": "Christmas: any talk about Christmas, Santa, Christmas trees, presents or "
                 "carols; the whole conversation. Not: winter or snow alone",
    "halloween": "Halloween: any talk about Halloween, trick-or-treating, Halloween costumes "
                 "or jack-o'-lanterns; the whole conversation. Not: a story's own witches, "
                 "ghosts or monsters",
    "birthday": "birthday candles: talk about the candles on a birthday cake (blowing them "
                "out, making a wish over them); just those lines. Not: birthdays, birthday "
                "parties, cake, presents or singing Happy Birthday, which are fine",
    "valentine": "Valentine's Day: any talk about Valentine's Day, valentines or Cupid; the "
                 "whole conversation. Not: someone named Valentine",
    "easter": "Easter: any talk about Easter, the Easter bunny, Easter eggs or egg hunts; the "
              "whole conversation. Not: ordinary eggs or rabbits, Easter Island",
    "darkmagic": "dark magic and the occult: any talk about or use of witchcraft, sorcery, "
                 "curses or hexes, black magic, voodoo, summoning demons or spirits, talking to "
                 "the dead, seances, Ouija boards, fortune telling, tarot, psychics or devil "
                 "worship; the whole conversation. Not: 'witch' as an insult, stage magic tricks",
    "magic": "magic: any talk about or use of spells, magic wands, wizards, witches or fairies "
             "doing magic, magic potions, enchantments, magic powers, a genie's wishes or a "
             "magic object; the whole conversation. Not: dark magic (a separate choice), stage "
             "magic tricks, 'magic' meaning wonderful ('it was magic', 'the magic word')",
}


def numbered(lines, voices=None):
    out = []
    for i, l in enumerate(lines):
        v = (voices[i] if voices and i < len(voices) else None) or {}
        who = l.get("who") or v.get("spk") or ""
        g = v.get("g")
        tag = ", ".join(x for x in (who, f"{g}'s voice" if g in ("man", "woman", "child") else "")
                        if x)
        m, s = divmod(int(l["s"]), 60)
        out.append(f"{i + 1} [{m // 60}:{m % 60:02d}:{s:02d}]{' (' + tag + ')' if tag else ''} "
                   f"{l['text']}")
    return "\n".join(out)


def _examples(examples):
    if not examples:
        return ""
    want, keep = examples.get("muted", [])[:15], examples.get("kept", [])[:15]
    txt = ""
    if want:
        txt += "\nIn this show they have muted lines like:\n" + "\n".join(f"- {t}" for t in want)
    if keep:
        txt += "\nAnd chose NOT to mute lines like:\n" + "\n".join(f"- {t}" for t in keep)
    return txt + "\n"


def check_dialogue(lines, voices, wanted, examples=None, chunk=500):
    """Flag lines and conversations. Returns ({line_index: set(types)}, scenes) where
    scenes are [{"from": i, "to": j, "type": t, "why": str}]."""
    if not lines or not wanted:
        return {}, []
    kinds = [k for k in wanted if k in TYPE_TEXT]
    defs = "\n".join(f'- "{k}": {TYPE_TEXT[k]}' for k in kinds)
    schema = {"type": "object", "properties": {
        "lines": {"type": "array", "items": {"type": "object", "properties": {
            "line": {"type": "integer"}, "type": {"type": "string", "enum": kinds},
            "why": {"type": "string"}}, "required": ["line", "type", "why"]}},
        "scenes": {"type": "array", "items": {"type": "object", "properties": {
            "from_line": {"type": "integer"}, "to_line": {"type": "integer"},
            "type": {"type": "string", "enum": kinds}, "why": {"type": "string"}},
            "required": ["from_line", "to_line", "type", "why"]}}},
        "required": ["lines", "scenes"]}
    found, scenes = {}, []
    for a in range(0, len(lines), chunk):
        part = lines[a:a + chunk + 20]
        prompt = (
            "The dialogue of one episode or movie is in the input, one numbered line each, with "
            "the time and, where known, who is speaking and whether it sounds like a man, woman "
            "or child (these can be wrong; also use names, he/she and who is talking to whom).\n\n"
            "They want to remove:\n" + defs + "\n" + _examples(examples) +
            "\nReturn every single line that clearly contains one of these (\"lines\"), and every "
            "conversation where it runs across several lines, such as one person flirting with "
            "another (\"scenes\", from the first to the last line of that part). Use the line "
            "numbers from the input. Keep each \"why\" to a few plain words.")
        res, _ = ask(prompt, schema, numbered(part, (voices or [])[a:a + len(part)]),
                     system=SYSTEM)
        for f in res.get("lines", []):
            i = a + int(f.get("line", 0)) - 1
            if a <= i < a + len(part) and f.get("type") in kinds:
                found.setdefault(i, set()).add(f["type"])
        for s in res.get("scenes", []):
            i, j = a + int(s.get("from_line", 0)) - 1, a + int(s.get("to_line", 0)) - 1
            if a <= i <= j < a + len(part) and s.get("type") in kinds:
                scenes.append({"from": i, "to": j, "type": s["type"],
                               "why": str(s.get("why", ""))[:120]})
    return found, scenes


CHAT_SCHEMA = {"type": "object", "properties": {
    "reply": {"type": "string"},
    "tick": {"type": "array", "items": {"type": "string"}},
    "untick": {"type": "array", "items": {"type": "string"}},
    "mute_lines": {"type": "array", "items": {"type": "integer"}},
    "mute_words": {"type": "array", "items": {"type": "object", "properties": {
        "line": {"type": "integer"}, "word": {"type": "string"}},
        "required": ["line", "word"]}},
    "cut_scenes": {"type": "array", "items": {"type": "object", "properties": {
        "from_line": {"type": "integer"}, "to_line": {"type": "integer"},
        "why": {"type": "string"}}, "required": ["from_line", "to_line", "why"]}},
    "cut_times": {"type": "array", "items": {"type": "object", "properties": {
        "from": {"type": "string"}, "to": {"type": "string"},
        "why": {"type": "string"}}, "required": ["from", "to", "why"]}}},
    "required": ["reply", "tick", "untick", "mute_lines", "mute_words", "cut_scenes",
                 "cut_times"]}

CHAT_HOW = (
    "You can change the list directly, and your changes happen as soon as you answer:\n"
    "- \"tick\": ids from the list (S/L/W) to cut or mute\n"
    "- \"untick\": ids from the list to keep (not cut or muted)\n"
    "- \"mute_lines\": dialogue line numbers to mute whole\n"
    "- \"mute_words\": a line number and the exact word to mute just that word\n"
    "- \"cut_scenes\": first and last dialogue line of a stretch to cut\n"
    "- \"cut_times\": a stretch to cut by time, like {\"from\": \"12:30\", \"to\": \"13:05\"}\n"
    "Do what they ask: if they say to remove, keep, mute or cut something, make that change "
    "(\"keep the kiss at 12:30\" = untick that scene; \"just mute the word\" = untick the line "
    "and mute_words). If they only ask a question, answer it and change nothing unless they ask. "
    "Leave every list empty when nothing should change. In \"reply\", say in a few plain "
    "sentences what you found and exactly what you changed, using times (like 12:30) rather "
    "than ids or line numbers. Plain text only: no bullet points, bold or headings.")


def chat(question, st, session=None):
    """Talk about this episode and change the list. Returns (reply, actions, items, session_id):
    actions is the answer's change lists, items maps the S/L/W ids it may use."""
    lines = st.get("dialogue", [])
    items, listing = candidates(st, with_review=True)
    if st.get("claude_summary"):
        listing += "\n\nYour earlier review said: " + st["claude_summary"]
    if session:
        prompt = ("The list as it is now (ids may have changed since last time):\n" + listing +
                  "\n\n" + CHAT_HOW + "\n\nThey say: " + question)
        res, sid = ask(prompt, CHAT_SCHEMA, system=None, session=session)
    else:
        prompt = (
            "The input is the numbered dialogue of one episode or movie (time, and where known "
            "who is speaking and a man/woman/child voice guess, which can be wrong).\n\n"
            "Everything CleanView found, and what's ticked now (S = scene to cut, L = line to "
            "mute, W = word to mute):\n" + (listing or "(nothing)") + "\n\n" + CHAT_HOW +
            "\n\nThey say: " + question)
        res, sid = ask(prompt, CHAT_SCHEMA, numbered(lines, st.get("voices")), system=SYSTEM,
                       keep=True)
    n = len(lines)
    acts = {"tick": [str(x).strip().upper() for x in res.get("tick", [])],
            "untick": [str(x).strip().upper() for x in res.get("untick", [])],
            "mute_lines": [int(i) - 1 for i in res.get("mute_lines", []) if 0 < int(i) <= n],
            "mute_words": [(int(w.get("line", 0)) - 1, str(w.get("word", "")).strip())
                           for w in res.get("mute_words", [])
                           if 0 < int(w.get("line", 0)) <= n and str(w.get("word", "")).strip()],
            "cut_scenes": [], "cut_times": []}
    for c in res.get("cut_scenes", []):
        i, j = int(c.get("from_line", 0)) - 1, int(c.get("to_line", 0)) - 1
        if 0 <= i <= j < n:
            acts["cut_scenes"].append({"from": i, "to": j, "why": str(c.get("why", ""))[:120]})
    for c in res.get("cut_times", []):
        acts["cut_times"].append({"from": str(c.get("from", "")), "to": str(c.get("to", "")),
                                  "why": str(c.get("why", ""))[:120]})
    return str(res.get("reply", "")).strip(), acts, items, sid


# ---------------------------------------------------------------------------
# The full review: everything the other checks found, judged in context
# ---------------------------------------------------------------------------
REVIEW_SCHEMA = {"type": "object", "properties": {
    "decisions": {"type": "array", "items": {"type": "object", "properties": {
        "id": {"type": "string"},
        "decision": {"type": "string",
                     "enum": ["remove", "just the word", "not an issue", "can't tell"]},
        "word": {"type": "string"},
        "why": {"type": "string"}}, "required": ["id", "decision", "why"]}},
    "missed_lines": {"type": "array", "items": {"type": "object", "properties": {
        "line": {"type": "integer"}, "word": {"type": "string"},
        "why": {"type": "string"}}, "required": ["line", "why"]}},
    "missed_scenes": {"type": "array", "items": {"type": "object", "properties": {
        "from_line": {"type": "integer"}, "to_line": {"type": "integer"},
        "why": {"type": "string"}}, "required": ["from_line", "to_line", "why"]}},
    "summary": {"type": "string"}},
    "required": ["decisions", "missed_lines", "missed_scenes", "summary"]}


def _t(sec):
    sec = int(max(0, sec))
    return f"{sec // 3600}:{sec % 3600 // 60:02d}:{sec % 60:02d}"


def _yours(it):
    if it.get("by_you"):
        return " (they set this themselves)"
    if it.get("learned"):
        return f" (from their past choices: {it['learned']})"
    if it.get("hint"):
        return f" (an earlier review's call, which you may overrule: {it['hint']})"
    return ""


def _said(it, show):
    c = it.get("claude") if show else None
    if not c:
        return ""
    w = f" '{c['word']}'" if c.get("word") else ""
    return f" Your review said: {c['decision']}{w} ({c.get('why', '')})."


def candidates(st, with_review=False):
    """Everything found, as an id -> item map plus the text Claude reads."""
    items, out = {}, []
    for k, sc in enumerate(st.get("scenes", []), 1):
        i = f"S{k}"
        items[i] = ("scene", sc)
        out.append(f"{i} scene {_t(sc['s'])}-{_t(sc['e'])} [{', '.join(sc.get('kind', []))}] "
                   f"found by: {sc.get('why', '')}; currently "
                   f"{'CUT' if sc.get('cut', True) else 'kept'}{_yours(sc)}. "
                   f"Said during it: {(sc.get('said') or '(no talking)')[:300]}" +
                   (f" Already checked by looking at the picture: {sc['claude']['decision']} "
                    f"({sc['claude'].get('why', '')})." if (sc.get("claude") or {}).get("seen")
                    else _said(sc, with_review)))
    for k, l in enumerate(st.get("lines", []), 1):
        i = f"L{k}"
        items[i] = ("line", l)
        out.append(f"{i} line {_t(l['s'])} [{', '.join(l.get('types', []))}] "
                   f"\"{l.get('plain') or l['text']}\"; currently "
                   f"{'MUTED' if l.get('mute', True) else 'kept'}{_yours(l)}" + _said(l, with_review))
    for k, m in enumerate(st.get("mutes", []), 1):
        i = f"W{k}"
        items[i] = ("word", m)
        heard = HEARD.get(m.get("src", ""), "")
        out.append(f"{i} word {_t(m['s'])} [{m.get('cat', '')}{heard}] "
                   f"\"{m.get('raw') or m['word']}\" "
                   f"after: \"{m.get('ctx', '')}\"; currently "
                   f"{'kept' if m.get('keep') else 'MUTED'}{_yours(m)}" + _said(m, with_review))
    return items, "\n".join(out)


WORD_REASON = re.compile(r"\b(contains?|word|language|swear\w*|profan\w*|curse\w*|cuss\w*|"
                         r"crude word|bad word|says?)\b", re.I)


MORE_THAN_WORD = re.compile(r"\b(refer\w*|innuendo|joke\w*|sexual\w*|sex|flirt\w*|romanc\w*|"
                            r"affair|bull\w*|mock\w*|crude humor|gross|relig\w*|faith|pray\w*|"
                            r"church\w*|bible|worship\w*|scripture\w*|spiritual\w*|christmas|"
                            r"santa|halloween|trick.or.treat\w*|birthday\w*|candles?|"
                            r"valentine\w*|easter|magic\w*|spells?|witch\w*|wizard\w*|"
                            r"sorcer\w*|occult|demon\w*|hex\w*|potions?|enchant\w*)\b", re.I)
WHOLE_LINE_TYPES = {"religion", "christmas", "halloween", "birthday", "valentine", "easter",
                    "darkmagic", "magic"}   # never just a word
# Where a single word was found, for the review. Heard by listening means it really is said:
# Radio's review unticked "hell", "damn", "shit" heard there for not being in the subtitles.
HEARD = {"audio": ", heard in the sound", "subtitles": ", in the subtitles",
         "subtitles-estimated": ", in the subtitles"}


def _only_word(line, why, mutes):
    """Claude said to remove a whole line, but its reason is just one word
    ("Contains 'ass'"). Return that word so only it is muted, else ''."""
    if MORE_THAN_WORD.search(why):
        return ""
    text = line.get("plain") or line["text"]
    toks = re.findall(r"[A-Za-z][A-Za-z'\-]*", text)
    low = {t.lower().strip("'"): t for t in toks}
    for q in re.findall(r"['\"\u2018\u201c]([A-Za-z][A-Za-z'\- ]{0,20}?)['\"\u2019\u201d]", why):
        q = q.strip().lower()
        if q in low:
            return low[q]
        for t in toks:                       # 'ass' named, 'sweet-ass' said
            parts = t.lower().split("-")
            if len(parts) > 1 and q in parts:
                return t
    if MORE_THAN_WORD.search(why):
        return ""
    if WORD_REASON.search(why):
        on_list = [m for m in mutes if line["s"] - 0.6 <= m["s"] <= line["e"] + 0.6]
        if on_list:                          # the listed words in this line
            return "|".join(m.get("raw") or m["word"] for m in on_list)
    return ""


def review(st, wanted_text, examples=None, extra_sounds="", fresh=False):
    """Claude looks over everything at once. Returns (items {id: (kind, item)},
    decisions {id: (decision, why)}, missed_lines [(idx, why)], missed_scenes
    [{"from","to","why"}], summary). fresh: don't reuse the last answer."""
    lines = st.get("dialogue", [])
    items, cand = candidates(st)
    prompt = (
        "CleanView has checked one episode or movie for this family. Your job is the final "
        "review: look over everything it found, in the context of the whole story and the "
        "dialogue, and decide what really needs removing, what is a false alarm, and what it "
        "missed.\n\n"
        "What they want removed:\n" + wanted_text + "\n" + _examples(examples) + "\n"
        "Everything CleanView found (S = scene to cut, L = line to mute, W = single word to "
        "mute):\n" + (cand or "(nothing)") + "\n\n" +
        (("Sounds the subtitles describe:\n" + extra_sounds + "\n\n") if extra_sounds else "") +
        "The full dialogue is in the input: numbered lines with the time and, where known, who "
        "is speaking and whether it sounds like a man, woman or child (these can be wrong).\n\n"
        "Instructions:\n"
        "1. Give a decision for EVERY item above, using its id: \"remove\" if it fits what they "
        "want removed; \"just the word\" for a line (L) whose ONLY problem is one bad word, "
        "such as 'sweet-ass deal' or 'what the hell' (always use this when the problem is a "
        "word, whatever the word is; if there are several bad words, put them all, separated "
        "by |; put that word, exactly as said, in "
        "\"word\"; CleanView then mutes only that word and keeps the rest of the line); "
        "\"not an issue\" if in context it doesn't (for example 'hell' in a place "
        "name, 'God' in a sincere prayer when they only want God's name used as a swear "
        "removed, a line that only sounds suggestive out of context), or \"can't tell\" (the "
        "tick then stays as it is). You can't see the picture, so for scenes found in the "
        "picture or the sound (nudity, kissing, violence, smoking...) say \"can't tell\" "
        "unless the dialogue clearly confirms it (\"remove\") or clearly shows it's a false "
        "alarm (\"not an issue\", e.g. the 'gunshots' are fireworks at a party). A word "
        "\"heard in the sound\" really is said, even when the dialogue line doesn't have it: "
        "subtitles often leave swear words out or soften them, so never call it a false alarm "
        "for not being in the subtitles. Slurs such as 'retarded' or 'retard' are always "
        "\"remove\", even said as a plain description of someone. Scenes "
        "already checked by looking at the picture are settled: answer \"remove\" or \"not an "
        "issue\" to match, and leave them out of the summary.\n"
        "2. List dialogue lines that fit what they want removed but are NOT in the list "
        "(\"missed_lines\", by line number; if only one word in it is the problem, also give "
        "that word in \"word\" so only the word is muted), and stretches of conversation that should be cut "
        "as a whole, such as flirting or romance they asked to remove (\"missed_scenes\", "
        "first and last line).\n"
        "3. Items marked as set by them or from their past choices are their decision: still "
        "give your view, but don't list those lines or scenes again as missed.\n"
        "4. Keep every \"why\" to a few plain words. The summary is one or two plain "
        "sentences for them about this episode: what really needed removing and what was a "
        "false alarm.")
    res, _ = ask(prompt, REVIEW_SCHEMA, numbered(lines, st.get("voices")), system=SYSTEM,
                 timeout=900, fresh=fresh)
    decisions = {}
    for d in res.get("decisions", []):
        i = str(d.get("id", "")).strip().upper()
        if i in items:
            dec = d.get("decision")
            word = str(d.get("word") or "").strip()
            if dec == "remove" and items[i][0] == "line" and not word:
                word = _only_word(items[i][1], str(d.get("why", "")), st.get("mutes", []))
                if word:
                    dec = "just the word"
            if dec == "just the word" and (items[i][0] != "line" or not word or
                                          MORE_THAN_WORD.search(str(d.get("why", ""))) or
                                          WHOLE_LINE_TYPES & set(items[i][1].get("types", []))):
                dec = "remove"            # a joke, innuendo or religious talk: the whole line goes
            decisions[i] = (dec, str(d.get("why", ""))[:140], word)
    missed = []
    for m in res.get("missed_lines", []):
        k = int(m.get("line", 0)) - 1
        if 0 <= k < len(lines):
            why, word = str(m.get("why", ""))[:140], str(m.get("word") or "").strip()
            if MORE_THAN_WORD.search(why):
                word = ""                 # about more than a word: mute the whole line
            missed.append((k, why, word))
    scenes = []
    for s in res.get("missed_scenes", []):
        a, b = int(s.get("from_line", 0)) - 1, int(s.get("to_line", 0)) - 1
        if 0 <= a <= b < len(lines):
            scenes.append({"from": a, "to": b, "why": str(s.get("why", ""))[:140]})
    return items, decisions, missed, scenes, str(res.get("summary", "")).strip()


# ---------------------------------------------------------------------------
# Looking at the picture: contact sheets of the whole episode, and a closer
# look at each scene the picture checkers found
# ---------------------------------------------------------------------------
PIC_KINDS = ["violence", "graphic violence", "gore", "disturbing", "nudity", "implied nudity",
             "sex", "kissing", "immodest", "smoking", "drinking", "drugs", "christmas",
             "halloween", "birthday", "valentine", "easter", "dark magic", "magic",
             "rude gesture"]
VIOLENCE_LEVELS = ["none", "violence", "graphic violence", "gore", "disturbing"]
PIC_SYSTEM = ("You help a family make movies and TV shows fit their standards by cutting scenes. "
              "You look at still frames and report exactly what is shown. Be accurate: flag what "
              "is clearly shown, not what might happen off screen.")
PIC_RULES = (
    "Be accurate. Police or soldiers simply carrying guns, a hug, a peck on the cheek, a "
    "hospital or crime-scene photo with no visible wounds, or a glass of water are NOT matches. "
    "Violence levels (pick the highest that's shown): \"violence\" = fighting, hitting, "
    "shooting, threatening with a weapon, without much blood; \"graphic violence\" = blood "
    "and wounds shown: bloody injuries, a bloody body, a crime-scene body with visible blood; "
    "\"gore\" = insides on the outside: organs, entrails, brains, bone through skin, "
    "dismemberment, a severed body part; \"disturbing\" = violence outside of combat: "
    "torture, an execution, cruelty or abuse of someone helpless (or an animal). A body with "
    "no visible blood (covered, or just lying there) is none of these. Cartoon and slapstick "
    "fighting IS \"violence\" too: a brawl in a dust cloud, piling on or sitting on someone "
    "after a fight, punching, kicking, shoving or knocking someone to the ground, a villain "
    "roughing up his own henchmen. Report the whole stretch, from the first blow to when it "
    "ends. Nudity means bare breasts, bare "
    "buttocks or genitals actually shown; implied nudity means someone undressed but covered "
    "(under a sheet, in a towel, a bare back or shoulders, a shower from the shoulders up, "
    "private parts hidden by an object or the camera angle). A shirtless man or swimwear is "
    "neither. For kissing, say who (man & woman, two "
    "men, two women) and whether it's light or passionate. For holidays, only what is "
    "clearly about that holiday counts: snow or winter alone, a plain pumpkin, a fantasy "
    "story's own witches or monsters, an ordinary egg or rabbit, or a single red heart are "
    "NOT. \"birthday\" is only candles on a cake (lit, or being blown out): a party, balloons, "
    "presents or a cake with no candles are fine. \"dark magic\" is witchcraft, curses, occult "
    "rituals, summoning, seances, Ouija boards, voodoo and fortune telling; \"magic\" is any "
    "other magic being done (spells, wands, glowing magic, potions); a stage magician's trick "
    "is neither. Immodest includes sexual dancing (stripping, pole dancing, grinding); "
    "smoking includes vaping. A rude gesture is someone raising the middle finger at someone, or a "
    "crude sexual gesture (a hand gesture mimicking sex or oral sex, thrusting the hips, "
    "grabbing the crotch); it's often over in a second, so look closely at hands and bodies. "
    "Waving, pointing, a thumbs up, a peace sign or dancing are NOT.")


def picture_review(sheets, wanted, per_request=12, progress=None):
    """sheets: [(path, start_seconds)], each 20 stills 2 s apart (5 across, 4 down).
    wanted: plain text of what to look for. Returns [{"s","e","what","who","level","why"}]."""
    schema = {"type": "object", "properties": {"found": {"type": "array", "items": {
        "type": "object", "properties": {
            "sheet": {"type": "integer"}, "from_tile": {"type": "integer"},
            "to_tile": {"type": "integer"},
            "what": {"type": "string", "enum": PIC_KINDS},
            "who": {"type": "string", "enum": ["man & woman", "two men", "two women", "n/a"]},
            "level": {"type": "string", "enum": ["light", "passionate", "n/a"]},
            "why": {"type": "string"}},
        "required": ["sheet", "from_tile", "to_tile", "what", "who", "level", "why"]}}},
        "required": ["found"]}
    out = []
    batches = [sheets[a:a + per_request] for a in range(0, len(sheets), per_request)]
    for b, batch in enumerate(batches):
        if progress:
            progress(b / len(batches))
        imgs = [(f"Sheet {k + 1} ({_t(t0)} to {_t(t0 + 40)}):", p) for k, (p, t0) in enumerate(batch)]
        prompt = (
            "Each sheet above is 20 stills from one episode or movie, 2 seconds apart, read left "
            "to right and top to bottom (tiles 1-20, 5 across and 4 down). They want removed:\n" +
            wanted + "\n\n" + PIC_RULES + "\n\nList every stretch that clearly shows one of "
            "these, with the sheet number and the first and last tile. If nothing does, return "
            "an empty list. Keep each \"why\" to a few plain words.")
        res, _ = ask(prompt, schema, images=imgs, system=PIC_SYSTEM, timeout=900)
        for f in res.get("found", []):
            k = int(f.get("sheet", 0)) - 1
            if not 0 <= k < len(batch):
                continue
            t0 = batch[k][1]
            a = max(1, min(20, int(f.get("from_tile", 1))))
            z = max(a, min(20, int(f.get("to_tile", a))))
            out.append({"s": max(0.0, t0 + (a - 1) * 2 - 1.5), "e": t0 + (z - 1) * 2 + 2.5,
                        "what": f.get("what"), "who": f.get("who", "n/a"),
                        "level": f.get("level", "n/a"), "why": str(f.get("why", ""))[:140]})
    return out


def verify_scenes(items, wanted, per_request=10, progress=None):
    """items: [(scene_id, kind_text, why_found, sheet_path)], each sheet 6 stills of that
    scene (3 across, 2 down). Returns {scene_id: (decision, why, nudity)}."""
    schema = {"type": "object", "properties": {"decisions": {"type": "array", "items": {
        "type": "object", "properties": {
            "scene": {"type": "integer"},
            "decision": {"type": "string", "enum": ["remove", "not an issue", "can't tell"]},
            "nudity": {"type": "string", "enum": ["shown", "implied", "none"]},
            "violence": {"type": "string", "enum": VIOLENCE_LEVELS},
            "why": {"type": "string"}},
        "required": ["scene", "decision", "nudity", "violence", "why"]}}},
        "required": ["decisions"]}
    out = {}
    batches = [items[a:a + per_request] for a in range(0, len(items), per_request)]
    for b, batch in enumerate(batches):
        if progress:
            progress(b / len(batches))
        imgs = [(f"Scene {k + 1}: flagged by the automatic checker as {kind} ({why}). 6 stills:",
                 p) for k, (_, kind, why, p) in enumerate(batch)]
        prompt = (
            "Each numbered scene above was flagged by an automatic picture checker, which often "
            "makes mistakes (dark frames, hugs, ordinary police scenes). They want removed:\n" +
            wanted + "\n\n" + PIC_RULES + "\n\nFor EVERY scene give a decision: \"remove\" if the "
            "stills really show what it was flagged for (or anything else they want removed), "
            "\"not an issue\" if it's a false alarm, or \"can't tell\". Also say for every scene "
            "whether nudity is \"shown\", only \"implied\", or \"none\", and the highest "
            "violence level shown (\"none\", \"violence\", \"graphic violence\", \"gore\" or "
            "\"disturbing\"). Keep each \"why\" to a few plain words.")
        res, _ = ask(prompt, schema, images=imgs, system=PIC_SYSTEM, timeout=900)
        for d in res.get("decisions", []):
            k = int(d.get("scene", 0)) - 1
            if 0 <= k < len(batch):
                out[batch[k][0]] = (d.get("decision"), str(d.get("why", ""))[:140],
                                    d.get("nudity", "none"), d.get("violence", "none"))
    return out


def scene_bounds(items, per_request=8, progress=None):
    """items: [(scene_id, kind_text, sheet_path)], each sheet 30 stills (6 across, 5 down),
    evenly spaced from well before to well after a scene that will be cut. Returns
    {scene_id: (first_tile, last_tile, continues_before, continues_after)} or None for a
    scene where the trouble isn't seen at all."""
    schema = {"type": "object", "properties": {"scenes": {"type": "array", "items": {
        "type": "object", "properties": {
            "scene": {"type": "integer"},
            "seen": {"type": "boolean"},
            "first_tile": {"type": "integer"}, "last_tile": {"type": "integer"},
            "continues_before": {"type": "boolean"}, "continues_after": {"type": "boolean"}},
        "required": ["scene", "seen", "first_tile", "last_tile", "continues_before",
                     "continues_after"]}}}, "required": ["scenes"]}
    out = {}
    batches = [items[a:a + per_request] for a in range(0, len(items), per_request)]
    for b, batch in enumerate(batches):
        if progress:
            progress(b / len(batches))
        imgs = [(f"Scene {k + 1} (to be cut for: {kind}). 30 stills, tiles 1-30, read left to "
                 f"right and top to bottom:", p) for k, (_, kind, p) in enumerate(batch)]
        prompt = (
            "Each numbered scene above is going to be cut out of a family's copy of a show. The "
            "stills run from well before the scene to well after it. For each one, find the "
            "WHOLE stretch to cut: from the first still where that trouble starts (including "
            "the start of a fight, a grab, or someone being attacked or pulled down) to the last "
            "still where it's over (people still struggling, someone still being hurt or in "
            "danger, the attacker still at it). It's better to include a little too much than "
            "leave part of it in. Give first_tile and last_tile. Set continues_before if it "
            "was already going on in tile 1, and continues_after if it's still going on in tile "
            "30. Set seen to false if none of the stills show it.")
        res, _ = ask(prompt, schema, images=imgs, system=PIC_SYSTEM, timeout=900)
        for d in res.get("scenes", []):
            k = int(d.get("scene", 0)) - 1
            if not 0 <= k < len(batch):
                continue
            if not d.get("seen", True):
                out[batch[k][0]] = None
                continue
            a = max(1, min(30, int(d.get("first_tile", 1))))
            z = max(a, min(30, int(d.get("last_tile", 30))))
            out[batch[k][0]] = (a, z, bool(d.get("continues_before")),
                                bool(d.get("continues_after")))
    return out
