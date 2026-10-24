"""
Claude (or ChatGPT) inside CleanView.

Claude goes through Claude Code, Anthropic's own program: signed in with your
Claude account it uses your Claude plan. ChatGPT goes through Codex, OpenAI's
own program, the same way (see cleanview_gpt.py). No API keys, nothing extra
to pay. Only the episode's dialogue is sent, as text, never video or sound.

use("claude") / use("chatgpt") picks which one the functions below talk to.
"""
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


import cleanview_gpt as gpt  # noqa: E402

PROVIDER = "claude"
NAMES = {"claude": "Claude", "chatgpt": "ChatGPT"}


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


def _env():
    env = dict(os.environ)
    env.pop("ANTHROPIC_API_KEY", None)   # always use the Claude plan, never a paid key
    return env


def signed_in():
    exe = find_claude()
    if not exe:
        return False
    try:
        r = subprocess.run([exe, "auth", "status"], capture_output=True, text=True, timeout=30,
                           env=_env(), **_NOWIN)
    except Exception:
        return False
    if r.returncode != 0:
        return False
    try:
        return json.loads(r.stdout).get("authMethod", "none") != "none"
    except ValueError:
        return True


def open_sign_in():
    """Open a window that walks through signing in with the browser."""
    exe = find_claude()
    if not exe:
        raise ClaudeError("Claude Code isn't installed yet.")
    if os.name == "nt":
        subprocess.Popen(["cmd", "/c", "start", "Sign in to Claude", "cmd", "/k",
                          f'echo Sign in to Claude in the browser window that opens. & echo When '
                          f'it says you are signed in, close this window and go back to '
                          f'CleanView. & echo. & "{exe}" auth login'], env=_env())
    else:
        subprocess.Popen([exe, "auth", "login"], env=_env())


def status(provider=None):
    """'missing', 'signed_out' or 'ready'."""
    if (provider or PROVIDER) == "chatgpt":
        return gpt.status()
    if not find_claude():
        return "missing"
    return "ready" if signed_in() else "signed_out"


def is_installed(provider=None):
    return bool(gpt.find() if (provider or PROVIDER) == "chatgpt" else find_claude())


def is_signed_in(provider=None):
    return gpt.signed_in() if (provider or PROVIDER) == "chatgpt" else signed_in()


def install(provider=None):
    try:
        gpt.install() if (provider or PROVIDER) == "chatgpt" else install_claude()
    except gpt.GptError as ex:
        raise ClaudeError(str(ex))


def sign_in(provider=None):
    try:
        gpt.open_sign_in() if (provider or PROVIDER) == "chatgpt" else open_sign_in()
    except gpt.GptError as ex:
        raise ClaudeError(str(ex))


def ask(prompt, schema, stdin_text="", system=None, session=None, keep=False, timeout=600):
    """One request to Claude or ChatGPT. Returns (answer_dict, session_id)."""
    if PROVIDER == "chatgpt":
        try:
            return gpt.ask(prompt, schema, stdin_text, system, session, keep, timeout)
        except gpt.GptError as ex:
            raise ClaudeError(str(ex))
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


# ---------------------------------------------------------------------------
# What CleanView asks Claude
# ---------------------------------------------------------------------------
SYSTEM = ("You help a family make movies and TV shows fit their standards by muting dialogue "
          "and cutting scenes. You only ever see the dialogue as numbered lines. Be accurate: "
          "flag what clearly fits what they asked for, and nothing else. Don't lecture or add "
          "opinions about their choices.")

TYPE_TEXT = {
    "sexref": "sexual references, sexual jokes or innuendo",
    "casual": "sleeping around: casual sex, hooking up, affairs, cheating",
    "samesex": "same-sex romance or relationships, including flirting or romantic interest "
               "between two men or two women",
    "oppsex": "an unmarried man and woman living or sleeping together",
    "crude": "crude humor: bathroom, bodily-function or gross-out jokes",
    "bullying": "bullying: mocking, taunting, demeaning someone or cruel name-calling",
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
    "mute_lines": {"type": "array", "items": {"type": "integer"}},
    "cut_scenes": {"type": "array", "items": {"type": "object", "properties": {
        "from_line": {"type": "integer"}, "to_line": {"type": "integer"},
        "why": {"type": "string"}}, "required": ["from_line", "to_line", "why"]}}},
    "required": ["reply", "mute_lines", "cut_scenes"]}


def chat(question, lines, voices, flagged_summary, session=None):
    """Ask about this episode. Returns (reply, mute_line_indexes, scenes, session_id)."""
    if session:
        res, sid = ask(question, CHAT_SCHEMA, system=None, session=session)
    else:
        prompt = (
            "The input is the numbered dialogue of one episode or movie (time, and where known "
            "who is speaking and a man/woman/child voice guess, which can be wrong).\n\n"
            "Everything CleanView found, and what's ticked now (S = scene to cut, L = line to "
            "mute, W = word to mute):\n" + (flagged_summary or "(nothing)") + "\n\n"
            "Answer the person's question in a few plain sentences. If they want something "
            "removed, or ask you to find something, put the line numbers to mute in "
            "\"mute_lines\" and any stretch to cut in \"cut_scenes\" (first and last line). "
            "Only suggest what fits what they asked. Leave both lists empty if nothing should "
            "change.\n\nTheir question: " + question)
        res, sid = ask(prompt, CHAT_SCHEMA, numbered(lines, voices), system=SYSTEM, keep=True)
    mute = [int(i) - 1 for i in res.get("mute_lines", []) if 0 < int(i) <= len(lines)]
    scenes = []
    for s in res.get("cut_scenes", []):
        i, j = int(s.get("from_line", 0)) - 1, int(s.get("to_line", 0)) - 1
        if 0 <= i <= j < len(lines):
            scenes.append({"from": i, "to": j, "why": str(s.get("why", ""))[:120]})
    return str(res.get("reply", "")).strip(), mute, scenes, sid


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
                   f"Said during it: {(sc.get('said') or '(no talking)')[:300]}" + _said(sc, with_review))
    for k, l in enumerate(st.get("lines", []), 1):
        i = f"L{k}"
        items[i] = ("line", l)
        out.append(f"{i} line {_t(l['s'])} [{', '.join(l.get('types', []))}] "
                   f"\"{l.get('plain') or l['text']}\"; currently "
                   f"{'MUTED' if l.get('mute', True) else 'kept'}{_yours(l)}" + _said(l, with_review))
    for k, m in enumerate(st.get("mutes", []), 1):
        i = f"W{k}"
        items[i] = ("word", m)
        out.append(f"{i} word {_t(m['s'])} [{m.get('cat', '')}] \"{m.get('raw') or m['word']}\" "
                   f"after: \"{m.get('ctx', '')}\"; currently "
                   f"{'kept' if m.get('keep') else 'MUTED'}{_yours(m)}" + _said(m, with_review))
    return items, "\n".join(out)


WORD_REASON = re.compile(r"\b(contains?|word|language|swear\w*|profan\w*|curse\w*|cuss\w*|"
                         r"crude word|bad word|says?)\b", re.I)


MORE_THAN_WORD = re.compile(r"\b(refer\w*|innuendo|joke\w*|sexual\w*|sex|flirt\w*|romanc\w*|"
                            r"affair|bull\w*|mock\w*|crude humor|gross)\b", re.I)


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


def review(st, wanted_text, examples=None, extra_sounds=""):
    """Claude looks over everything at once. Returns (items {id: (kind, item)},
    decisions {id: (decision, why)}, missed_lines [(idx, why)], missed_scenes
    [{"from","to","why"}], summary)."""
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
        "alarm (\"not an issue\", e.g. the 'gunshots' are fireworks at a party).\n"
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
                 timeout=900)
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
                                          MORE_THAN_WORD.search(str(d.get("why", "")))):
                dec = "remove"            # a joke or innuendo: the whole line goes
            decisions[i] = (dec, str(d.get("why", ""))[:140], word)
    missed = []
    for m in res.get("missed_lines", []):
        k = int(m.get("line", 0)) - 1
        if 0 <= k < len(lines):
            missed.append((k, str(m.get("why", ""))[:140], str(m.get("word") or "").strip()))
    scenes = []
    for s in res.get("missed_scenes", []):
        a, b = int(s.get("from_line", 0)) - 1, int(s.get("to_line", 0)) - 1
        if 0 <= a <= b < len(lines):
            scenes.append({"from": a, "to": b, "why": str(s.get("why", ""))[:140]})
    return items, decisions, missed, scenes, str(res.get("summary", "")).strip()
