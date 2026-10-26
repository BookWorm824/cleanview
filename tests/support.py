"""Shared set-up for the tests.

Every test module imports this first. It points LOCALAPPDATA at a throwaway
folder before any CleanView module is imported (they read it at import time),
so the tests never touch real settings, learned choices or reviews. It also
puts the app folder on sys.path and makes small made-up sample data, so the
tests don't depend on anyone's real videos or files."""
import atexit
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SANDBOX = Path(tempfile.mkdtemp(prefix="cleanview-tests-"))
os.environ["LOCALAPPDATA"] = str(SANDBOX)
os.environ.pop("CLEANVIEW_RESUME", None)
APP_DATA = SANDBOX / "CleanView"
(APP_DATA / "learned").mkdir(parents=True)
sys.path.insert(0, str(ROOT))
atexit.register(shutil.rmtree, SANDBOX, ignore_errors=True)


def old_learned():
    """A learned file as versions before 1.11.4 left it: anything left unticked
    was counted as "kept", so the counts snowballed (as Castle's Gore did)."""
    return {
        "muted": ["you are such a creep", "get your hands off me"],
        "kept": ["the ai said this one was fine", "she really did leave this one"],
        "scenes": {"Gore": {"cut": 0, "kept": 65}, "Kiss": {"cut": 1, "kept": 1}},
        "words": {"hell": {"muted": 3, "kept": 4}, "damn": {"muted": 7, "kept": 0}},
        "claude_muted": [], "claude_kept": ["claude thought this was fine"],
        "claude_ok_words": [],
    }


def write_learned(key, data):
    (APP_DATA / "learned" / f"{key}.json").write_text(json.dumps(data), encoding="utf8")


def sample_review():
    """A made-up analysis.json with everything the review page needs: 30 lines of
    dialogue, two flagged lines, one word to mute and two scenes."""
    dialogue = [{"s": 2.0 + 3 * i, "e": 4.0 + 3 * i, "text": f"Made-up line number {i}.",
                 "who": f"Speaker {i % 3 + 1}"} for i in range(30)]
    dialogue[4]["text"] = "Oh darn it, the cart tipped over."
    flagged = []
    for n, i in enumerate((7, 12), 1):
        d = dialogue[i]
        flagged.append({"id": n, "s": d["s"], "e": d["e"], "text": d["text"], "plain": d["text"],
                        "types": ["bullying"], "mute": True, "idx": i,
                        "claude": {"decision": "remove", "why": "made-up reason"}})
    return {
        "path": str(SANDBOX / "Sample Show S01E01.mp4"),
        "info": {"path": "", "duration": 95.0, "start": 0.0,
                 "video": {"index": 0, "codec": "h264", "width": 640, "height": 360, "dar": 1.78},
                 "audio": {"index": 1, "channels": 2, "codec": "aac", "lang": "eng",
                           "bit_rate": 128000},
                 "subs": [], "audio_tracks": 1},
        "groups": ["mild"],
        "mutes": [{"s": 14.2, "e": 14.5, "cat": "minced", "src": "asr", "word": "d**n",
                   "raw": "darn", "ctx": "Oh", "keep": False}],
        "scenes": [{"id": 1, "s": 30.0, "e": 38.0, "kind": ["Violence"], "why": "a fight",
                    "cut": True, "sure": True, "said": ""},
                   {"id": 2, "s": 60.0, "e": 64.0, "kind": ["Kiss"], "why": "kissing seen",
                    "cut": False, "sure": False, "said": ""}],
        "lines": flagged,
        "cues": [], "show": "sample-show", "dialogue": dialogue,
        "voices": [{"spk": d["who"], "g": "?"} for d in dialogue],
        "reader": "the AI on this PC", "reviewer": None, "notes": [],
        "asr": [[w, d["s"], d["e"]] for d in dialogue for w in d["text"].split()[:1]],
        "duration": 95.0, "words": 120, "opts": {}, "used_ai": False, "used_clip": False,
    }


def write_review():
    """Save the sample review where the app keeps its work, plus a saved session
    pointing at it ("Pick up where I left off"). Returns the work folder."""
    work = APP_DATA / "views" / "sample"
    work.mkdir(parents=True, exist_ok=True)
    st = sample_review()
    (work / "analysis.json").write_text(json.dumps(st), encoding="utf8")
    (APP_DATA / "last_review.json").write_text(json.dumps(
        {"saved": "now", "outdir": str(SANDBOX / "Clean"),
         "jobs": [{"video": st["path"], "work": str(work)}]}), encoding="utf8")
    return work
