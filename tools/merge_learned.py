"""Merge 'CleanView learned <date>.json' files (from the Send button) into
the app's shared_learned.json.

    python merge_learned.py app/shared_learned.json "CleanView learned 2026-10-24.json" [...]

Per show: lines the person muted (or Claude said to remove, unless the
person kept them) and lines they kept (or Claude said were fine, unless they
muted them). Phrases where a word was fine ("dinner at hell") go to
"general" for every show. Later files win over earlier ones on conflicts.
"""
import json
import sys

MAX = 400


def add(lst, items, drop=()):
    for t in items:
        if t in drop:
            continue
        if t in lst:
            lst.remove(t)
        lst.append(t)
    del lst[:-MAX]


def merge(shared, export):
    shows = shared.setdefault("shows", {})
    gen = shared.setdefault("general", {})
    for k in ("muted", "kept", "ok_words"):
        gen.setdefault(k, [])
    n = 0
    for key, d in export.get("shows", {}).items():
        sh = shows.setdefault(key, {"muted": [], "kept": [], "ok_words": []})
        mine_m, mine_k = d.get("muted", []), d.get("kept", [])
        muted = mine_m + [t for t in d.get("claude_muted", []) if t not in mine_k]
        kept = mine_k + [t for t in d.get("claude_kept", []) if t not in mine_m]
        sh["kept"] = [t for t in sh["kept"] if t not in muted]
        sh["muted"] = [t for t in sh["muted"] if t not in kept]
        add(sh["muted"], muted)
        add(sh["kept"], kept)
        add(gen["ok_words"], d.get("claude_ok_words", []))
        n += len(muted) + len(kept)
    shows = {k: v for k, v in shows.items() if any(v.values())}
    shared["shows"] = shows
    return n


if __name__ == "__main__":
    target = sys.argv[1]
    shared = json.load(open(target, encoding="utf8"))
    for f in sys.argv[2:]:
        n = merge(shared, json.load(open(f, encoding="utf8")))
        print(f"{f}: {n} lines merged")
    json.dump(shared, open(target, "w", encoding="utf8"), indent=1, ensure_ascii=False)
    s = shared["shows"]
    print(f"now: {len(s)} shows, {sum(len(v['muted']) for v in s.values())} muted lines, "
          f"{sum(len(v['kept']) for v in s.values())} kept lines, "
          f"{len(shared['general']['ok_words'])} fine-in-context phrases")
