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
"""
import json
import os
import re
from pathlib import Path

APP_DATA = Path(os.environ.get("LOCALAPPDATA") or Path.home() / ".local" / "share") / "CleanView"
DIR = APP_DATA / "learned"
MAX_LINES = 400


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
    for k, v in (("muted", []), ("kept", []), ("scenes", {}), ("words", {})):
        d.setdefault(k, v)
    return d


def save(key, d):
    try:
        DIR.mkdir(parents=True, exist_ok=True)
        d["muted"], d["kept"] = d["muted"][-MAX_LINES:], d["kept"][-MAX_LINES:]
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
    flagged_at = {(round(l["s"], 2), round(l["e"], 2)) for l in line_flags}
    n_kept = 0
    for l in line_flags:
        if norm(l.get("plain") or l["text"]) in kept:
            l["mute"] = False
            l["learned"] = "you left this unmuted before"
            n_kept += 1
    added = []
    for l in dialogue:
        if (round(l["s"], 2), round(l["e"], 2)) in flagged_at:
            continue
        if norm(l["text"]) in muted:
            added.append(l)
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
    for m in mutes:
        s = d["words"].get(m.get("raw") or m.get("word", ""))
        if s and s["kept"] >= 2 and s["muted"] == 0:
            m["keep"] = True
            m["learned"] = "you usually keep this word"
            n_w += 1
    if added:
        notes.append(f"Muted {len(added)} line(s) you muted before in this show.")
    if n_kept or n_sc or n_w:
        bits = [f"{n_kept} line(s)" if n_kept else "", f"{n_sc} scene(s)" if n_sc else "",
                f"{n_w} word(s)" if n_w else ""]
        notes.append("Left unticked because of your past choices: " +
                     ", ".join(b for b in bits if b) + ".")
    return added, notes


def examples(key):
    """Some of your past choices, for the dialogue readers."""
    d = load(key)
    return {"muted": d["muted"][-15:], "kept": d["kept"][-15:]}
