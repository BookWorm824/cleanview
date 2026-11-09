"""
What CleanView learns from your choices on the review page, kept per show
(and one shared file for movies) in %LOCALAPPDATA%\\CleanView\\learned.

- Lines you mute (or add yourself) are muted again when they come back
  (catchphrases, theme-song lyrics, recaps), and lines you unmute
  start unticked next time.
- Scene types you nearly always untick in a show start unticked there.
- Swear words you keep unticking start unticked.
- Only what you change yourself counts: something the AI unticked and you
  left alone isn't taken as your choice.
- Your past choices are shown to the dialogue readers (the AI on this PC
  and Claude) as examples of what you do and don't want.
- Claude's verdicts teach the AI on this PC too: lines Claude said to remove
  or that were fine are added to its examples (your own choices come first),
  and words Claude said were fine in a phrase ("Hell's Kitchen") start
  unticked when that phrase comes back.
- Every Claude finding is also kept in claude_findings.csv (opens in Excel).
- export() puts everything learned into one file to send in, so it can be
  merged into shared_learned.json, which ships with CleanView updates and
  gives every copy (people without Claude or ChatGPT too) the same head start.
  Your own choices always beat the shared ones.
- send() sends such a file to the CleanView inbox (tools/cleanview_inbox.gs, a
  Google script in the owner's Drive), so nobody has to attach it anywhere.
"""
import csv
import json
from datetime import date
import os
import re
import shutil
import urllib.request
from pathlib import Path

import cvcore

APP_DATA = Path(os.environ.get("LOCALAPPDATA") or Path.home() / ".local" / "share") / "CleanView"
DIR = APP_DATA / "learned"
MAX_LINES = 400
# A muted conversation is learned line by line, so short everyday lines in it ("What do
# you think?", "Right.") would be muted in every later episode (The Resident). Lines this
# short are never muted again just because they were learned.
LEARNED_SHORTEST = 5
# The CleanView inbox's web app address (tools/README-inbox.txt; set up 2026-10-28 in the
# owner's Google account). Empty: the file is only saved and the person is told where.
SEND_URL = ("https://script.google.com/macros/s/"
            "AKfycbxfh9Cv3ctELA3352GTuVA1lshmGZKbwwPDsd39DEImZ-bRjFYml78iYKYZ5a2RGt8/exec")
MAX_SEND = 2_000_000        # the inbox refuses more


def send_url():
    return os.environ.get("CLEANVIEW_INBOX") or SEND_URL


def send(path, kind):
    """Send an exported file (kind "learned" or "refined") to the CleanView inbox.
    Raises if it couldn't: no inbox yet, no internet, or the inbox said no."""
    url = send_url()
    if not url:
        raise RuntimeError("CleanView's inbox isn't set up yet")
    path = Path(path)
    body = json.dumps({"app": "CleanView", "kind": kind, "name": path.name,
                       "data": json.loads(path.read_text(encoding="utf8"))}).encode("utf8")
    if len(body) > MAX_SEND:
        raise RuntimeError("the file is too big to send")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        answer = json.loads(r.read().decode("utf8") or "{}")
    if not answer.get("ok"):
        raise RuntimeError(f"the inbox didn't take it ({answer.get('why') or 'no reason given'})")


HERE = Path(__file__).resolve().parent
SHARED_PATH = HERE / "shared_learned.json"
_shared = None


def shared():
    """Built-in knowledge that comes with CleanView updates:
    {"shows": {key: {"muted": [], "kept": [], "ok_words": []}}, "general": {...}}."""
    global _shared
    if _shared is None:
        try:
            _shared = json.loads(SHARED_PATH.read_text("utf8"))
        except Exception:
            _shared = {}
        _shared.setdefault("shows", {})
        _shared.setdefault("general", {})
    return _shared


AGES = ("young", "kids", "teens", "adults")      # strictest first


def _age_keys(key, older=False):
    """The shared keys for this show at this age ("castle@teens"; adults have no "@"), and
    with older=True every older age's too: a line muted for adults is muted for teens and kids
    as well (Lauren's Castle S1E3, 2026-11-09, teens: the show's 191 built-in lines were all
    under "castle", learned from adults' reports, so none were used). What an older age keeps
    is never used for a younger one."""
    base, _, age = key.partition("@")
    age = age if age in AGES else "adults"
    out = [key]
    for a in AGES[AGES.index(age):] if older else (age,):
        out += [base, f"{base}@adults"] if a == "adults" else [f"{base}@{a}"]
    return list(dict.fromkeys(out))


def _sh(key, k):
    s = shared()
    out = []
    for kk in _age_keys(key, older=k == "muted"):
        out += s["shows"].get(kk, {}).get(k, [])
    return list(dict.fromkeys(out + list(s["general"].get(k, []))))


def _for_filters(key, lines, on):
    """Shared lines to mute, without those learned for a filter that isn't ticked now
    ("muted_for": line -> dialogue kind; lines without one count for every filter)."""
    if on is None:
        return list(lines)
    s = shared()
    kinds = dict(s["general"].get("muted_for", {}))
    for kk in reversed(_age_keys(key, older=True)):      # this age's own say wins
        kinds.update(s["shows"].get(kk, {}).get("muted_for", {}))
    return [t for t in lines if t not in kinds or kinds[t] in on]


def show_key(title):
    """title from cleanview.guess_title: (show, season, episode) or (movie, None, None)."""
    if title and title[1] is not None:
        return re.sub(r"[^a-z0-9]+", "-", title[0].lower()).strip("-") or "_unknown"
    return "_movies"


def norm(text):
    return " ".join(re.sub(r"[^a-z0-9' ]+", " ", text.lower().replace("’", "'")).split())


def _path(key):
    return DIR / f"{key}.json"


def load(key):
    try:
        d = json.loads(_path(key).read_text("utf8"))
    except Exception:
        d = {}
    for k, v in (("muted", []), ("kept", []), ("scenes", {}), ("words", {}), ("old_kept", []),
                 ("claude_muted", []), ("claude_kept", []), ("claude_ok_words", []),
                 ("videos", {}), ("word_only", {})):
        d.setdefault(k, v)
    if not d.get("v2"):     # "Gore" used to mean any blood; that's "Graphic violence" now
        if "Gore" in d["scenes"]:
            d["scenes"]["Graphic violence"] = d["scenes"].pop("Gore")
        d["v2"] = True
    if not d.get("v3"):
        # Before 1.11.4 anything left unticked counted as your choice, even when the AI (or
        # this file) had unticked it, so "kept" snowballed (Castle: Gore kept 65, cut 0).
        # Those counts can't be told apart from your real choices, so start them over;
        # the old kept lines become hints a new review can overrule.
        _backup(key)
        d["old_kept"] = d["kept"] + [t for t in d["old_kept"] if t not in d["kept"]]
        d["kept"] = []
        for s in d["scenes"].values():
            s["kept"] = 0
        for s in d["words"].values():
            s["kept"] = 0
        d["v3"] = True
    return d


def _backup(key):
    """A copy of the learned file as it was before the 1.11.4 clean-up, just in case."""
    try:
        old = DIR / f"{key}.before-1.11.4.bak"
        if _path(key).exists() and not old.exists():
            shutil.copyfile(_path(key), old)
    except OSError:
        pass


def save(key, d):
    try:
        DIR.mkdir(parents=True, exist_ok=True)
        for k in ("muted", "kept", "old_kept", "claude_muted", "claude_kept", "claude_ok_words"):
            d[k] = d[k][-MAX_LINES:]
        tmp = _path(key).with_suffix(".tmp")
        tmp.write_text(json.dumps(d, indent=1), encoding="utf8")
        os.replace(tmp, _path(key))
    except OSError:
        pass


def scene_kind(sc):
    return (sc.get("kind") or ["scene"])[0].split(" · ")[0]


MAX_VIDEOS = 300


def video_key(path):
    """One movie or episode, by its file name (her choices on its scenes are kept for it)."""
    return norm(Path(str(path or "")).stem) if path else ""


def _kinds(sc):
    if sc.get("kinds"):                 # as remembered
        return set(sc["kinds"])
    return {k.split(" · ")[0] for k in sc.get("kind") or ["scene"]}


def _same_scene(a, b):
    """The same scene found again: it overlaps by half of the shorter one, of the same kind."""
    over = min(a["e"], b["e"]) - max(a["s"], b["s"])
    short = max(0.5, min(a["e"] - a["s"], b["e"] - b["s"]))
    return over >= 0.5 * short and bool(_kinds(a) & _kinds(b))


def _remember_scene(d, video, sc, cut):
    """Her choice on one scene of this video (Jason, 2026-11-05: a phone slam he kept, a
    shirt he said wasn't nudity, joyful screaming: back again on the next scan of the same
    movie when no AI read his notes)."""
    vk = video_key(video)
    if not vk or "s" not in sc or "e" not in sc:
        return
    lst = d["videos"].pop(vk, [])            # most recent last (the oldest go first)
    new = {"s": round(sc["s"], 2), "e": round(sc["e"], 2), "kinds": sorted(_kinds(sc)),
           "cut": bool(cut)}
    lst = [x for x in lst if not _same_scene(new, x)] + [new]
    d["videos"][vk] = lst
    while len(d["videos"]) > MAX_VIDEOS:
        d["videos"].pop(next(iter(d["videos"])))


def _word_only(l, on, mutes, word_choice):
    """The words she (or the chat, for her) muted in this line instead of the whole line."""
    if on or "s" not in l or "e" not in l:
        return []
    return sorted({(m.get("raw") or m.get("word", "")).lower()
                   for m, mon in zip(mutes, word_choice)
                   if mon and (m.get("by_you") or _changed(m, mon))
                   and l["s"] - 1.0 <= m.get("s", -99) <= l["e"] + 1.0} - {""})


def word_only(key):
    """Lines she muted just a word of: {line (norm): [words]}."""
    return dict(load(key)["word_only"])


def _remember(lst, text):
    n = norm(text)
    if len(n.split()) >= 2 and n not in lst:
        lst.append(n)


def _changed(it, on):
    """True if you set this yourself: ticked or unticked it on the review page
    (this time, or in an earlier look at it)."""
    return bool(it.get("by_you")) or ("_shown" in it and it["_shown"] != on)


def record(key, flagged_lines, line_choice, extra_lines, scenes, scene_choice, added_scenes,
           mutes, word_choice, video=None):
    """Store what you did. *_choice are parallel lists of True (mute/cut) / False.
    Something ticked and left ticked counts as yours (you let it be changed);
    something left unticked only counts if you unticked it yourself, since the AI
    or what was learned before may have unticked it. video: the file, so her own choices
    on its scenes are used again when the same one is scanned again.
    A line she unticked while a word in it stays muted ("just the word", Jason 2026-11-05:
    "only mute the word christmas") is learned as that, not as a line that's fine."""
    d = load(key)
    for l, on in zip(flagged_lines, line_choice):
        n = norm(l.get("plain") or l["text"])
        # ...also when the line started unticked because she kept it before: Jason's
        # "Jiminy Christmas" was learned as fine on 1.18.19, so it came back unticked and
        # his "just the word" in the chat never counted (2026-11-06)
        just = _word_only(l, on, mutes, word_choice) \
            if _changed(l, on) or (not on and n in d["kept"]) else []
        if on:
            _remember(d["muted"], n)
            if n in d["kept"]:
                d["kept"].remove(n)
            d["word_only"].pop(n, None)
        elif just and len(n.split()) >= 2:
            d["word_only"][n] = just
            for k in ("kept", "muted"):
                if n in d[k]:
                    d[k].remove(n)
        elif _changed(l, on):
            _remember(d["kept"], n)
            if n in d["muted"]:
                d["muted"].remove(n)
            d["word_only"].pop(n, None)
    for l in extra_lines:
        _remember(d["muted"], l.get("plain") or l["text"])
    for sc, on in zip(scenes, scene_choice):
        _count(d["scenes"], scene_kind(sc), sc, on if on or _changed(sc, on) else None,
               "cut", "kept")
        if video and _changed(sc, on):
            _remember_scene(d, video, sc, on)
    for sc in added_scenes:
        _count(d["scenes"], "Added by you", sc, True, "cut", "kept")
    for m, on in zip(mutes, word_choice):
        _count(d["words"], m.get("raw") or m.get("word", ""), m,
               on if on or _changed(m, on) else None, "muted", "kept")
    save(key, d)


def _count(table, name, it, now, yes, no):
    """Count one choice (True/False, or None for not hers). Her choices are learned when
    she leaves the review ("Back to start", Jason) and again when she saves it, so a
    choice already counted is only moved if she changed it since (it["_learned_as"])."""
    prev = it.get("_learned_as")
    if prev == now:
        return
    counts = table.setdefault(name, {yes: 0, no: 0})
    if prev is not None:
        counts[yes if prev else no] = max(0, counts[yes if prev else no] - 1)
    if now is not None:
        counts[yes if now else no] += 1
    it["_learned_as"] = now


def _toks(n):
    return [t.strip("'") for t in n.split() if t.strip("'")]


class LearnedLines:
    """Learned lines to mute, found in dialogue worded or split a little differently
    (Lauren's Castle S1E1, 2026-11-08: the shared lines came from subtitles, this run's from
    what was heard, and only 1 of 8 matched exactly). A dialogue line matches a learned one
    when the learned line is all inside it ("But if it makes you feel any better, I'd be happy
    to let you spank me"), when it's most of the learned line ("Not so loud. I'm still hoping
    to get lucky"), or when only a word or two differ ("can" for "could"). A small piece of a
    learned line doesn't ("You do know I'm wearing a gun?" from "A little Cops Gone Wild? You
    do know I'm wearing a gun"): it can be harmless on its own."""
    MOST = 0.6          # a piece must be this much of the learned line
    ALIKE = 0.85        # token similarity for "a word or two differ"
    LONG = 7            # inside or a piece: only learned lines this long ("I don't know what
    #                     happens", muted as part of a conversation, isn't in "...happens next")

    def __init__(self, lines):
        self.lines = [(n, _toks(n)) for n in lines]
        self.lines = [(n, t) for n, t in self.lines if len(t) >= LEARNED_SHORTEST]
        self.index = {}
        for k, (_, t) in enumerate(self.lines):
            for w in set(t):
                self.index.setdefault(w, set()).add(k)

    @staticmethod
    def _inside(small, big):
        m = len(small)
        return any(big[i:i + m] == small for i in range(len(big) - m + 1))

    def match(self, n):
        from difflib import SequenceMatcher
        d = _toks(n)
        if len(d) < 3:
            return None
        votes = {}
        for w in set(d):
            for k in self.index.get(w, ()):
                votes[k] = votes.get(k, 0) + 1
        for k, shared in sorted(votes.items(), key=lambda kv: -kv[1]):
            name, t = self.lines[k]
            if shared < 0.5 * min(len(t), len(d)):
                break
            if self.LONG <= len(t) <= len(d) and self._inside(t, d):
                return name                              # all of it, inside a longer line
            if len(t) >= self.LONG and len(d) >= LEARNED_SHORTEST and \
                    len(d) >= self.MOST * len(t) and self._inside(d, t):
                return name                              # most of it, on its own
            if min(len(d), len(t)) >= LEARNED_SHORTEST + 1 and \
                    SequenceMatcher(None, d, t).ratio() >= self.ALIKE:
                return name                              # a word or two heard differently
            if len(t) >= self.LONG and self._overlap(d, t) >= max(self.LONG + 1, self.MOST * len(t)):
                return name                              # most of it, split differently
        return None

    @staticmethod
    def _overlap(d, t):
        """The longest stretch the two lines share, a word heard differently now and then
        (Castle S1E3, 2026-11-09: "instead of getting your freak on with writer boy" was heard
        as "Getting a drink with me after work instead of getting your freak on with Ryder
        Boy?", and "You don't think with a body like that she's gonna swoon..." ran across
        two learned lines). Longer than LONG: "I'm not ready to buy our attacker" isn't "...as a
        sexual predator" on its own."""
        from difflib import SequenceMatcher
        best = run = 0
        last = None
        for a, b, size in SequenceMatcher(None, d, t, autojunk=False).get_matching_blocks():
            if not size:
                continue
            near = last is not None and a - last[0] <= 1 and b - last[1] <= 1
            run = run + size if near else size
            best, last = max(best, run), (a + size, b + size)
        return best


def apply(key, dialogue, line_flags, scenes, mutes, label_learned="learned", on=None,
          video=None):
    """Use what was learned. Changes line_flags / scenes / mutes in place and
    returns (added_lines, notes). on: the dialogue kinds ticked now (None: all).
    video: the file; her own choices on its scenes last time come first."""
    d = load(key)
    notes = []
    muted, mine_kept = set(d["muted"]), set(d["kept"])
    # Claude's past calls, and what CleanView learned elsewhere, start lines unticked too,
    # but only as a hint ("hint", not "learned"): a new review may still say to remove them.
    # Only your own choices ("learned") are never undone.
    hint_kept = (set(d["claude_kept"]) | set(d["old_kept"])) - muted
    shared_muted = set(_for_filters(key, _sh(key, "muted"), on)) - mine_kept - hint_kept
    hint_kept |= set(_sh(key, "kept")) - muted - shared_muted
    hint_kept -= mine_kept
    muted |= shared_muted
    flagged_at = {(round(l["s"], 2), round(l["e"], 2)) for l in line_flags}
    n_kept = 0
    for l in line_flags:
        n = norm(l.get("plain") or l["text"])
        if n in mine_kept:
            l["mute"] = False
            l["learned"] = "you left this unmuted before"
            n_kept += 1
        elif n in hint_kept:
            l["mute"] = False
            l["hint"] = ("Claude said this was fine before" if n in d["claude_kept"] else
                         "CleanView learned this is fine")
            n_kept += 1
    added = []
    mine_muted = set(d["muted"])
    find = LearnedLines(muted)
    for l in dialogue:
        if (round(l["s"], 2), round(l["e"], 2)) in flagged_at:
            continue
        n = norm(l["text"])
        hit = n if n in muted else find.match(n)
        if hit and len(hit.split()) >= LEARNED_SHORTEST:
            added.append(dict(l, learned_from="you" if hit in mine_muted else "shared"))
    n_sc = n_again = 0
    def usually_kept(kind):
        s = d["scenes"].get(kind)
        return bool(s) and s["kept"] >= 3 and s["kept"] >= 0.75 * (s["kept"] + s["cut"])

    before = d["videos"].get(video_key(video), []) if video else []
    for sc in scenes:
        mine = next((x for x in reversed(before) if _same_scene(sc, x)), None) \
            if "s" in sc and "e" in sc else None
        if mine is not None:            # her own choice on this very scene last time
            sc["cut"] = mine["cut"]
            sc["learned"] = "you cut this scene before" if mine["cut"] else \
                "you kept this scene before"
            # settled by her: "(not double-checked, so ...)" no longer says why it's set so
            # (Jason, 2026-11-06: "the kisses are ticked... why are you saying left unticked?")
            sc["why"] = UNSETTLED.sub("", sc.get("why") or "")
            if mine["cut"]:
                n_again += 1
            else:
                n_sc += 1
            continue
        # every kind in it, not just the first: a drinking scene joined to a sex scene stays
        # cut (Julie & Julia: "you usually keep these" left the whole sex scene in)
        kinds = {k.split(" · ")[0] for k in sc.get("kind") or ["scene"]}
        if all(usually_kept(k) for k in kinds):
            if sc.get("cut", True):
                sc["cut"] = False
                sc["learned"] = "you usually keep these in this show"
                sc["why"] = (sc.get("why") or "") + " (you usually keep these in this show)"
                n_sc += 1
    n_w = 0
    ok_words = set(d["claude_ok_words"]) | set(_sh(key, "ok_words"))
    for m in mutes:
        s = d["words"].get(m.get("raw") or m.get("word", ""))
        if s and s["kept"] >= 2 and s["muted"] == 0:
            m["keep"] = True
            m["learned"] = "you usually keep this word"
            n_w += 1
        elif _phrase(m) in ok_words and not (s and s["muted"]) and \
                not cvcore.never_fine(m.get("raw") or m.get("word", "")):
            m["keep"] = True
            m["hint"] = ("Claude said this was fine here before"
                         if _phrase(m) in d["claude_ok_words"] else
                         "CleanView learned this is fine here")
            n_w += 1
    n_you = sum(1 for l in added if l["learned_from"] == "you")
    if n_you:
        notes.append(f"Muted {n_you} line(s) you muted before in this show.")
    if len(added) - n_you:
        notes.append(f"Muted {len(added) - n_you} line(s) CleanView has learned to mute in this "
                     "show.")
    if n_kept or n_sc or n_w:
        bits = [f"{n_kept} line(s)" if n_kept else "", f"{n_sc} scene(s)" if n_sc else "",
                f"{n_w} word(s)" if n_w else ""]
        notes.append("Left unticked because of what CleanView has learned: " +
                     ", ".join(b for b in bits if b) + ".")
    if n_again:
        notes.append(f"Ticked to cut again because you cut them before: {n_again} scene(s).")
    return added, notes


# What a scene's "why" says about its starting tick, which her own choice replaces.
UNSETTLED = re.compile(r" \((?:not double-checked|hard to see), so (?:left unticked|only cut "
                       r"if you tick it)\)")


def _phrase(m):
    """A swear word with the two words before it, e.g. "dinner at hell"."""
    ctx = norm(m.get("ctx", "")).split()[-2:]
    return " ".join(ctx + [norm(m.get("raw") or m.get("word", ""))])


MAX_NOTES = 40


def _notes_key(key, everywhere):
    """Where a note lives: the show's own file, or "_all" (per age, like the rest)."""
    if not everywhere:
        return key
    return "_all" + key[key.index("@"):] if "@" in key else "_all"


def add_note(key, text, title="", everywhere=False):
    """Something they told the chat to keep in mind from now on ("the Genie's magic is
    fine, it's Aladdin"; Jason, 2026-10-30: the chat said it couldn't learn). For a movie
    it's kept for that movie only (title), for a show for every episode, or for everything
    they clean. Returns True if it's new."""
    text = " ".join(str(text).split())[:300]
    if not text:
        return False
    k = _notes_key(key, everywhere)
    t = norm(title) if not everywhere and key.startswith("_movies") else ""
    d = load(k)
    notes = d.setdefault("notes", [])
    if any(n["text"].lower() == text.lower() and n.get("title", "") == t for n in notes):
        return False
    notes.append({"text": text, "title": t, "added": date.today().isoformat()})
    d["notes"] = notes[-MAX_NOTES:]
    save(k, d)
    return True


def notes(key, title=""):
    """The notes that apply to this video: the built-in ones (checked lessons from the
    reports sent in, shipped in shared_learned.json), then theirs for everything, then for
    this show or movie."""
    t, out = norm(title or ""), []
    s = shared()
    built_in = list(s["general"].get("notes", []))
    for k in dict.fromkeys((key, key.split("@")[0])):
        built_in += s["shows"].get(k, {}).get("notes", [])
    mine = [n for k in dict.fromkeys((_notes_key(key, True), key))
            for n in load(k).get("notes", [])]
    for n in built_in + mine:
        n = n if isinstance(n, dict) else {"text": n}
        if (not n.get("title") or norm(n["title"]) == t) and n["text"] not in out:
            out.append(n["text"])
    return out


def examples(key, on=None, title=""):
    """Some of your past choices for the dialogue readers, plus what they told the chat to
    keep in mind. Yours come first; the built-in ones fill the rest. on: the dialogue kinds
    ticked now. Claude's own past answers are never among them: they were shown to it as
    "this family has muted / chose not to mute", so a mistake it made once came back as her
    choice and was made again (CleanListen 1.15.3, Blue Ridge, 2026-11-05)."""
    d = load(key)
    out = {"notes": notes(key, title)}
    for k in ("muted", "kept"):
        mine = d[k][-15:]
        sh = _sh(key, k)
        if k == "muted":
            sh = _for_filters(key, sh, on)
        built_in = [t for t in sh[::-1] if t not in mine]
        out[k] = (mine + built_in)[:15]
    return out


def export(dest_dir=None):
    """Everything CleanView has learned on this PC, in one file to send in.
    Returns the file's path."""
    out = {"what": "CleanView learned", "date": date.today().isoformat(), "shows": {},
           "findings": []}
    try:
        out["version"] = json.loads((HERE / "version.json").read_text())["version"]
    except Exception:
        pass
    if DIR.exists():
        for f in sorted(DIR.glob("*.json")):
            try:
                out["shows"][f.stem] = json.loads(f.read_text("utf8"))
            except Exception:
                pass
    if FINDINGS.exists():
        for f in sorted(FINDINGS.glob("*.json")):
            try:
                out["findings"].append(json.loads(f.read_text("utf8")))
            except Exception:
                pass
    dest = Path(dest_dir) if dest_dir else next(
        (d for d in (Path.home() / "OneDrive" / "Desktop", Path.home() / "Desktop",
                     Path.home() / "Documents") if d.exists()), Path.home())
    path = dest / f"CleanView learned {out['date']}.json"
    path.write_text(json.dumps(out, indent=1), encoding="utf8")
    return path


FINDINGS = APP_DATA / "claude_findings"
CSV_PATH = APP_DATA / "claude_findings.csv"


def record_claude(st):
    """Remember Claude's verdicts for this show, and keep them in a spreadsheet."""
    key = st.get("show", "_movies")
    d = load(key)
    rows = []
    video = os.path.basename(st.get("path", ""))

    def t(sec):
        sec = int(sec)
        return f"{sec // 3600}:{sec % 3600 // 60:02d}:{sec % 60:02d}"
    for l in st.get("lines", []):
        c = l.get("claude")
        if not c:
            continue
        text = l.get("plain") or l["text"]
        if c["decision"] == "remove":
            _remember(d["claude_muted"], text)
        elif c["decision"] in ("not an issue", "just the word"):
            _remember(d["claude_kept"], text)
        rows.append([video, t(l["s"]), "line", ", ".join(l.get("types", [])), text,
                     c["decision"], c.get("word", ""), c.get("why", "")])
    for m in st.get("mutes", []):
        c = m.get("claude")
        if not c:
            continue
        if c["decision"] == "not an issue" and not cvcore.never_fine(m.get("raw") or m["word"]):
            p = _phrase(m)
            if p and p not in d["claude_ok_words"]:
                d["claude_ok_words"].append(p)
        rows.append([video, t(m["s"]), "word", m.get("cat", ""),
                     (m.get("ctx", "") + " [" + (m.get("raw") or m["word"]) + "]").strip(),
                     c["decision"], "", c.get("why", "")])
    for sc in st.get("scenes", []):
        c = sc.get("claude")
        if c:
            rows.append([video, t(sc["s"]) + "-" + t(sc["e"]), "scene",
                         ", ".join(sc.get("kind", [])), (sc.get("said") or "")[:300],
                         c["decision"], "", c.get("why", "")])
    save(key, d)
    try:                      # one file per video (a re-review replaces it), then one spreadsheet
        FINDINGS.mkdir(parents=True, exist_ok=True)
        name = re.sub(r"[^A-Za-z0-9._ -]+", "_", video) or "video"
        (FINDINGS / f"{name}.json").write_text(json.dumps(
            {"show": key, "date": date.today().isoformat(), "rows": rows,
             "reviewer": st.get("reviewer") or "Claude"}), encoding="utf8")
        write_findings(CSV_PATH)
    except OSError:
        pass


def findings_rows(videos=None):
    """Every saved finding, newest video first. videos: just these (file names, or full
    paths), for the videos being reviewed now (Jason, 2026-11-07: the spreadsheet had every
    movie he'd ever done, and he wanted the one he's working on)."""
    want = None if videos is None else {os.path.basename(v) for v in videos}
    out = []
    for f in sorted(FINDINGS.glob("*.json")) if FINDINGS.exists() else []:
        try:
            j = json.loads(f.read_text("utf8"))
            when = f.stat().st_mtime
        except Exception:
            continue
        rows = [[j.get("date", ""), j.get("show", ""), r[0], j.get("reviewer", "Claude")]
                + r[1:] for r in j.get("rows", []) if want is None or r[0] in want]
        if rows:
            out.append((when, rows))
    out.sort(key=lambda x: -x[0])
    return [r for _, rows in out for r in rows]


def write_findings(path, videos=None):
    """The findings spreadsheet (opens in Excel). Returns how many rows it has."""
    rows = findings_rows(videos)
    path = Path(path)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["Date", "Show", "Video", "Reviewer", "Time", "What", "Flagged as",
                    "Text", "Verdict", "Word", "Why"])
        w.writerows(rows)
    os.replace(tmp, path)
    return len(rows)


def export_refined(analyses, chat=None, dest_dir=None):
    """Everything about how these videos were refined, to send in: what each
    checker found, what Claude/ChatGPT said, what was changed (by hand or
    through the chat) and what was finally muted or cut. No video or sound."""
    def verdict(it):
        c = it.get("claude") or {}
        return {k: c[k] for k in ("decision", "why", "word", "seen") if k in c} or None

    videos = []
    for st in analyses:
        videos.append({
            "video": os.path.basename(st.get("path", "")), "show": st.get("show"),
            "reviewer": st.get("reviewer"), "reader": st.get("reader"),
            "settings": st.get("opts"), "word_groups": st.get("groups"),
            "summary": st.get("claude_summary"), "notes": st.get("notes"),
            "scenes": [{"s": sc["s"], "e": sc["e"], "kind": sc.get("kind"), "why": sc.get("why"),
                        "ai": verdict(sc), "final": "cut" if sc.get("cut", True) else "kept",
                        "changed_by_you": bool(sc.get("by_you")), "added": bool(sc.get("added")),
                        "learned": sc.get("learned")} for sc in st.get("scenes", [])],
            "lines": [{"s": l["s"], "text": l.get("plain") or l["text"], "types": l.get("types"),
                       "ai": verdict(l), "final": "muted" if l.get("mute", True) else "kept",
                       "changed_by_you": bool(l.get("by_you")), "learned": l.get("learned")}
                      for l in st.get("lines", [])],
            "words": [{"s": m["s"], "word": m.get("raw") or m["word"], "before": m.get("ctx"),
                       "category": m.get("cat"), "heard_by": m.get("src"), "ai": verdict(m),
                       "final": "kept" if m.get("keep") else "muted",
                       "changed_by_you": bool(m.get("by_you")), "learned": m.get("learned")}
                      for m in st.get("mutes", [])],
            "dialogue": [[d["s"], d["text"]] for d in st.get("dialogue", [])]})
    out = {"what": "CleanView refined", "date": date.today().isoformat(), "videos": videos,
           "chat": [list(c) for c in (chat or [])]}
    try:
        out["version"] = json.loads((HERE / "version.json").read_text())["version"]
    except Exception:
        pass
    dest = Path(dest_dir) if dest_dir else next(
        (d for d in (Path.home() / "OneDrive" / "Desktop", Path.home() / "Desktop",
                     Path.home() / "Documents") if d.exists()), Path.home())
    first = re.sub(r"[^A-Za-z0-9 ._-]+", "_", Path(videos[0]["video"]).stem if videos else "video")
    name = f"CleanView refined - {first[:50]}" + (f" +{len(videos) - 1}" if len(videos) > 1 else "")
    path = dest / f"{name} {out['date']}.json"
    path.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf8")
    return path
