"""
What CleanView learns from your choices on the review page, kept per show
(and one shared file for movies) in %LOCALAPPDATA%\\CleanView\\learned.

- Lines you mute (or add yourself) are muted again when they come back
  (catchphrases, theme-song lyrics, recaps), and lines you leave unmuted
  start unticked next time.
- Scene types you nearly always keep in a show start unticked there.
- Swear words you keep unticking start unticked.
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
"""
import csv
import json
from datetime import date
import os
import re
from pathlib import Path

APP_DATA = Path(os.environ.get("LOCALAPPDATA") or Path.home() / ".local" / "share") / "CleanView"
DIR = APP_DATA / "learned"
MAX_LINES = 400


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


def _sh(key, k):
    s = shared()
    return list(s["shows"].get(key, {}).get(k, [])) + list(s["general"].get(k, []))


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
    for k, v in (("muted", []), ("kept", []), ("scenes", {}), ("words", {}),
                 ("claude_muted", []), ("claude_kept", []), ("claude_ok_words", [])):
        d.setdefault(k, v)
    return d


def save(key, d):
    try:
        DIR.mkdir(parents=True, exist_ok=True)
        for k in ("muted", "kept", "claude_muted", "claude_kept", "claude_ok_words"):
            d[k] = d[k][-MAX_LINES:]
        tmp = _path(key).with_suffix(".tmp")
        tmp.write_text(json.dumps(d, indent=1), encoding="utf8")
        os.replace(tmp, _path(key))
    except OSError:
        pass


def scene_kind(sc):
    return (sc.get("kind") or ["scene"])[0].split(" · ")[0]


def _remember(lst, text):
    n = norm(text)
    if len(n.split()) >= 2 and n not in lst:
        lst.append(n)


def record(key, flagged_lines, line_choice, extra_lines, scenes, scene_choice, added_scenes,
           mutes, word_choice):
    """Store what you did. *_choice are parallel lists of True (mute/cut) / False."""
    d = load(key)
    for l, on in zip(flagged_lines, line_choice):
        n = norm(l.get("plain") or l["text"])
        if on:
            _remember(d["muted"], n)
            if n in d["kept"]:
                d["kept"].remove(n)
        else:
            _remember(d["kept"], n)
            if n in d["muted"]:
                d["muted"].remove(n)
    for l in extra_lines:
        _remember(d["muted"], l.get("plain") or l["text"])
    for sc, on in zip(scenes, scene_choice):
        k = scene_kind(sc)
        s = d["scenes"].setdefault(k, {"cut": 0, "kept": 0})
        s["cut" if on else "kept"] += 1
    if added_scenes:
        s = d["scenes"].setdefault("Added by you", {"cut": 0, "kept": 0})
        s["cut"] += len(added_scenes)
    for m, on in zip(mutes, word_choice):
        w = m.get("raw") or m.get("word", "")
        s = d["words"].setdefault(w, {"muted": 0, "kept": 0})
        s["muted" if on else "kept"] += 1
    save(key, d)


def apply(key, dialogue, line_flags, scenes, mutes, label_learned="learned"):
    """Use what was learned. Changes line_flags / scenes / mutes in place and
    returns (added_lines, notes)."""
    d = load(key)
    notes = []
    muted, kept = set(d["muted"]), set(d["kept"])
    kept |= set(d["claude_kept"]) - muted          # Claude's calls, unless you decided otherwise
    shared_muted = set(_sh(key, "muted")) - kept - set(d["claude_kept"])
    kept |= set(_sh(key, "kept")) - muted - shared_muted
    muted |= shared_muted
    flagged_at = {(round(l["s"], 2), round(l["e"], 2)) for l in line_flags}
    n_kept = 0
    for l in line_flags:
        n = norm(l.get("plain") or l["text"])
        if n in kept:
            l["mute"] = False
            l["learned"] = ("you left this unmuted before" if n in d["kept"] else
                            "Claude said this was fine before" if n in d["claude_kept"] else
                            "CleanView learned this is fine")
            n_kept += 1
    added = []
    mine_muted = set(d["muted"])
    for l in dialogue:
        if (round(l["s"], 2), round(l["e"], 2)) in flagged_at:
            continue
        n = norm(l["text"])
        if n in muted:
            added.append(dict(l, learned_from="you" if n in mine_muted else "shared"))
    n_sc = 0
    for sc in scenes:
        s = d["scenes"].get(scene_kind(sc))
        if s and s["kept"] >= 3 and s["kept"] >= 0.75 * (s["kept"] + s["cut"]):
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
        elif _phrase(m) in ok_words and not (s and s["muted"]):
            m["keep"] = True
            m["learned"] = ("Claude said this was fine here before"
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
    return added, notes


def _phrase(m):
    """A swear word with the two words before it, e.g. "dinner at hell"."""
    ctx = norm(m.get("ctx", "")).split()[-2:]
    return " ".join(ctx + [norm(m.get("raw") or m.get("word", ""))])


def examples(key):
    """Some of your past choices, and Claude's, for the dialogue readers.
    Yours come first; Claude's fill the rest."""
    d = load(key)
    out = {}
    for k in ("muted", "kept"):
        mine = d[k][-15:]
        theirs = [t for t in d["claude_" + k][::-1] if t not in mine][:15 - len(mine)]
        built_in = [t for t in _sh(key, k)[::-1] if t not in mine + theirs]
        out[k] = (mine + theirs + built_in)[:15]
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
        if c["decision"] == "not an issue":
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
        allrows = []
        for f in sorted(FINDINGS.glob("*.json")):
            try:
                j = json.loads(f.read_text("utf8"))
            except Exception:
                continue
            allrows += [[j.get("date", ""), j.get("show", ""), r[0], j.get("reviewer", "Claude")]
                        + r[1:] for r in j.get("rows", [])]
        tmp = CSV_PATH.with_suffix(".tmp")
        with open(tmp, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.writer(fh)
            w.writerow(["Date", "Show", "Video", "Reviewer", "Time", "What", "Flagged as",
                        "Text", "Verdict", "Word", "Why"])
            w.writerows(allrows)
        os.replace(tmp, CSV_PATH)
    except OSError:
        pass
