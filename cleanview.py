#!/usr/bin/env python3
"""
CleanView engine — mute bad language and cut nudity, sex scenes and violence
out of movie and TV files you own. Its own copy of the speech model, word
lists and tools lives beside it. Used by the CleanView app; can also run from a command line:

  python cleanview.py analyze WORKDIR VIDEO [--no-nudity] [--no-sex] [--no-violence]
  python cleanview.py render  WORKDIR OUTDIR
  python cleanview.py visualscan VIDEO OUT.json      (internal: runs in its own process)
"""
import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cvcore as cl  # noqa: E402  (speech model, word lists, ffmpeg helpers)
import cleanview_ai as ai  # noqa: E402  (picture AI and the local AI helper)
import cleanview_claude as cc  # noqa: E402  (Claude, through Claude Code)
import cleanview_learn as learn  # noqa: E402  (what your past choices taught it)

SR = cl.SR
VIDEO_EXTS = (".mp4", ".m4v", ".mkv", ".avi", ".mov", ".wmv", ".webm", ".mpg", ".mpeg",
              ".ts", ".m2ts", ".mts", ".vob", ".flv", ".3gp")
TAG_NAME = "sherpa-onnx-ced-mini-audio-tagging-2024-04-19"
TAG_URL = f"https://github.com/k2-fsa/sherpa-onnx/releases/download/audio-tagging-models/{TAG_NAME}.tar.bz2"
TAG_DIR = HERE / "models" / TAG_NAME
VISUAL_FPS = 2.0


# ---------------------------------------------------------------------------
# Options and one-time tools
# ---------------------------------------------------------------------------
CLOUD = ("claude", "chatgpt")      # readers that use your Claude or ChatGPT plan
LINE_KINDS = ("sexref", "casual", "samesex", "oppsex", "crude", "bullying")
DEFAULTS = {"nudity": True, "implied": False, "sex": True, "violence": True, "gore": True,
            "kiss_os": "off", "kiss_ss": "off", "samesex": False, "casual": False,
            "oppsex": False, "sexref": False, "immodest": False, "smoking": False,
            "drinking": False, "drugs": False, "crude": False, "bullying": False, "ai": True,
            "autosubs": True, "reader": "local", "look": True}


def full_opts(opts=None):
    o = dict(DEFAULTS)
    o.update(opts or {})
    return o


def needs(opts):
    """Which scanners these options need."""
    o = full_opts(opts)
    clip_cats = []
    if o["kiss_os"] != "off" or o["kiss_ss"] != "off":
        clip_cats.append("kiss")
    if o["sex"] or o["samesex"] or o["oppsex"]:
        clip_cats.append("bed")
    if o["gore"]:
        clip_cats.append("gore")
    if o["violence"]:
        clip_cats.append("fight")
    for k in ("smoking", "drinking", "drugs", "immodest"):
        if o[k]:
            clip_cats.append(k)
    lines = [k for k in LINE_KINDS if o[k]]
    return {"sound": o["violence"] or o["sex"],
            "voices": (o["ai"] or o.get("reader") in CLOUD) and bool(lines),
            "subs": o.get("autosubs", True),
            "nudenet": o["nudity"] or o["sex"] or o["implied"],
            "clip": clip_cats,
            "lines": lines,
            "ai": o["ai"] and bool(clip_cats or lines)}


def _venv_python():
    exe = Path(sys.executable)
    py = exe.with_name("python.exe") if os.name == "nt" else exe
    return str(py if py.exists() else exe)


def nudity_model():
    spec = importlib.util.find_spec("nudenet")
    if not spec or not spec.origin:
        return None
    p = Path(spec.origin).parent / "320n.onnx"
    return p if p.exists() else None


def _subs_mark():
    return HERE / "models" / "subtitle_finder_tried.txt"


def _subs_tried():
    return _subs_mark().exists()


def _upgrade_mark():
    return HERE / "models" / ("ai_models_tried_" + re.sub(r"[^a-z0-9]+", "_", "_".join(
        ai.VISION_MODELS[:1] + ai.TEXT_MODELS[:1]).lower()) + ".txt")


def _upgrade_tried():
    return _upgrade_mark().exists()


def tools_missing(opts=None):
    """What still needs downloading (empty list = ready)."""
    nd = needs(opts)
    need = []
    if (nd["nudenet"] or nd["clip"]) and (not importlib.util.find_spec("onnxruntime")
                                          or not nudity_model()):
        need.append("picture checker")
    if (nd["sound"] or nd["voices"]) and not (TAG_DIR / "model.int8.onnx").exists():
        need.append("sound checker")
    if nd["voices"] and not ai.speakers_ready():
        need.append("speaker separator")
    if nd["subs"] and importlib.util.find_spec("subliminal") is None and not _subs_tried():
        need.append("subtitle finder")
    if nd["clip"] and not ai.clip_ready():
        need.append("picture AI")
    if nd["ai"]:
        if not (ai.ollama_running() and ai.model_ready()):
            need.append("AI helper")
        elif not (ai.model_ready(ai.VISION_MODELS[0]) and ai.model_ready(ai.TEXT_MODELS[0])) \
                and not _upgrade_tried():
            need.append("newer AI models")
    return need


def install_tools(opts=None, progress=None, log=print):
    say = progress or (lambda f, m: None)
    nd = needs(opts)
    if (nd["nudenet"] or nd["clip"]) and (not importlib.util.find_spec("onnxruntime")
                                          or not nudity_model()):
        say(0.02, "Getting the picture checker (one time, about 60 MB)…")
        py = _venv_python()
        for args in (["onnxruntime"], ["--no-deps", "nudenet"]):
            r = cl.run([py, "-m", "pip", "install", "--quiet", "--disable-pip-version-check", *args],
                       capture_output=True, text=True)
            if r.returncode != 0:
                raise RuntimeError("Couldn't download the picture checker. Check your internet "
                                   "connection and try again.\n\n" + r.stderr[-600:])
        importlib.invalidate_caches()
    if nd["voices"] and not ai.speakers_ready():
        try:
            ai.install_speakers(lambda f, m: say(0.02 + 0.03 * f, m))
        except Exception as ex:
            log(f"Speaker separator download failed: {ex}")   # carry on without it
    if nd["subs"] and importlib.util.find_spec("subliminal") is None and not _subs_tried():
        say(0.05, "Getting the subtitle finder (one time)…")
        r = cl.run([_venv_python(), "-m", "pip", "install", "--quiet", "--disable-pip-version-check",
                    "subliminal"], capture_output=True, text=True)
        try:
            _subs_mark().parent.mkdir(parents=True, exist_ok=True)
            _subs_mark().write_text("tried\n")
        except OSError:
            pass
        if r.returncode != 0:
            log("Subtitle finder download failed: " + r.stderr[-300:])
        importlib.invalidate_caches()
    if (nd["sound"] or nd["voices"]) and not (TAG_DIR / "model.int8.onnx").exists():
        say(0.05, "Getting the sound checker (one time, about 45 MB)…")
        TAG_DIR.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(suffix=".tar.bz2", dir=TAG_DIR.parent)
        os.close(fd)
        try:
            urllib.request.urlretrieve(TAG_URL, tmp)
            with tarfile.open(tmp, "r:bz2") as tf:
                for m in tf.getmembers():
                    name = Path(m.name).name
                    if name in ("model.int8.onnx", "class_labels_indices.csv") and m.isfile():
                        with tf.extractfile(m) as src, open(TAG_DIR / (name + ".part"), "wb") as dst:
                            shutil.copyfileobj(src, dst)
                        os.replace(TAG_DIR / (name + ".part"), TAG_DIR / name)
        finally:
            try:
                os.remove(tmp)
            except OSError:
                pass
        if not (TAG_DIR / "model.int8.onnx").exists():
            raise RuntimeError("The sound checker download looked wrong. Try again.")
    if nd["clip"] and not ai.clip_ready():
        try:
            ai.install_clip(_venv_python(), lambda f, m: say(0.1 + 0.2 * f, m))
        except Exception as ex:
            log(f"Picture AI download failed: {ex}")   # the run goes on without it
        importlib.invalidate_caches()
    if nd["ai"]:
        try:
            ai.ensure_ai(lambda f, m: say(0.3 + 0.7 * f, m))
        finally:
            if ai.model_ready():   # don't retry a failed upgrade on every run
                try:
                    _upgrade_mark().parent.mkdir(parents=True, exist_ok=True)
                    _upgrade_mark().write_text("tried\n")
                except OSError:
                    pass
    say(1.0, "Ready.")

# ---------------------------------------------------------------------------
# Looking inside the video file
# ---------------------------------------------------------------------------
TEXT_SUBS = {"subrip", "srt", "ass", "ssa", "mov_text", "webvtt", "text"}


class VideoError(Exception):
    pass


def _dar(v):
    """Display shape of the picture (DVDs store stretched pixels)."""
    w, h = v.get("width") or 16, v.get("height") or 9
    try:
        a, b = (v.get("sample_aspect_ratio") or "1:1").split(":")
        sar = int(a) / int(b) if int(a) and int(b) else 1.0
    except ValueError:
        sar = 1.0
    return w * sar / h if h else 16 / 9


def probe(path):
    r = cl.run([cl._tool("ffprobe"), "-v", "error", "-show_streams", "-show_format",
                "-of", "json", str(path)], capture_output=True, text=True, encoding="utf8",
               errors="replace")
    try:
        info = json.loads(r.stdout or "{}")
    except ValueError:
        info = {}
    streams = info.get("streams") or []
    fmt = info.get("format") or {}
    name = Path(path).name
    if any((s.get("codec_tag_string") or "").lower() in ("drmi", "drms", "encv", "enca")
           for s in streams) or "encrypt" in (r.stderr or "").lower():
        raise VideoError(f"{name} is copy-protected (DRM), so it can't be cleaned. This works with "
                         "DRM-free files, like DVD or Blu-ray rips and home videos.")
    vids = [s for s in streams if s.get("codec_type") == "video"
            and not (s.get("disposition") or {}).get("attached_pic")]
    auds = [s for s in streams if s.get("codec_type") == "audio"]
    if not vids:
        raise VideoError(f"{name} has no video in it.")
    if not auds:
        raise VideoError(f"{name} has no sound in it.")

    def lang(s):
        return ((s.get("tags") or {}).get("language") or "").lower()

    def title(s):
        return ((s.get("tags") or {}).get("title") or "").lower()

    def audio_rank(s):
        d = s.get("disposition") or {}
        return ("comment" in title(s) or d.get("comment") or d.get("visual_impaired"),
                lang(s) not in ("", "eng", "en", "und"), not d.get("default"), s["index"])

    audio = sorted(auds, key=audio_rank)[0]
    subs = []
    for s in streams:
        if s.get("codec_type") != "subtitle" or s.get("codec_name") not in TEXT_SUBS:
            continue
        d = s.get("disposition") or {}
        subs.append({"index": s["index"], "lang": lang(s), "title": title(s),
                     "forced": bool(d.get("forced")) or "forced" in title(s),
                     "sdh": bool(d.get("hearing_impaired")) or "sdh" in title(s)})

    def num(x, default=0.0):
        try:
            return float(x)
        except (TypeError, ValueError):
            return default

    dur = num(fmt.get("duration")) or num(vids[0].get("duration")) or num(audio.get("duration"))
    return {"path": str(path), "duration": dur, "start": num(fmt.get("start_time")),
            "video": {"index": vids[0]["index"], "codec": vids[0].get("codec_name"),
                      "width": vids[0].get("width"), "height": vids[0].get("height"),
                      "dar": _dar(vids[0])},
            "audio": {"index": audio["index"], "channels": int(audio.get("channels") or 2),
                      "codec": audio.get("codec_name"), "lang": lang(audio),
                      "bit_rate": int(num(audio.get("bit_rate")))},
            "subs": subs, "audio_tracks": len(auds)}


# ---------------------------------------------------------------------------
# Subtitles
# ---------------------------------------------------------------------------
def _srt_time(s):
    h, m, rest = s.strip().replace(".", ",").split(":")
    sec, ms = (rest.split(",") + ["0"])[:2]
    return int(h) * 3600 + int(m) * 60 + int(sec) + int(ms.ljust(3, "0")[:3]) / 1000


def parse_srt(text):
    cues = []
    for block in re.split(r"\n\s*\n", text.replace("\r", "").strip()):
        lines = block.strip().split("\n")
        k = next((i for i, l in enumerate(lines) if "-->" in l), None)
        if k is None:
            continue
        try:
            a, b = lines[k].split("-->")
            s, e = _srt_time(a), _srt_time(b.strip().split(" ")[0])
        except (ValueError, IndexError):
            continue
        body = "\n".join(lines[k + 1:])
        body = re.sub(r"\{[^}]*\}", "", body)        # ASS styling
        body = re.sub(r"<[^>]+>", "", body)          # <i>, <font>
        body = body.replace("\\N", "\n").strip()
        if body:
            cues.append({"s": s, "e": e, "text": body})
    return cues


def find_subtitles(path, info, workdir):
    """Best English subtitles: a matching .srt next to the video, else a text
    track inside it. Returns (cues, description) or ([], "")."""
    p = Path(path)
    sidecars = sorted(f for f in p.parent.iterdir() if f.is_file() and f.suffix.lower() == ".srt"
                      and f.name.lower().startswith(p.stem.lower()))
    sidecars.sort(key=lambda f: (not re.search(r"\.(en|eng|english)\b", f.name.lower()),
                                 "forced" in f.name.lower(), len(f.name)))
    for f in sidecars:
        if "forced" in f.name.lower():
            continue
        raw = f.read_bytes()
        for enc in ("utf-8-sig", "cp1252", "latin-1"):
            try:
                cues = parse_srt(raw.decode(enc))
                break
            except UnicodeDecodeError:
                cues = []
        if len(cues) > 5:
            return cues, f"subtitles from {f.name}"
    tracks = [s for s in info["subs"] if not s["forced"] and s["lang"] in ("", "eng", "en", "und")]
    best = []
    for s in sorted(tracks, key=lambda s: (s["lang"] not in ("eng", "en"), not s["sdh"])):
        out = Path(workdir) / f"sub_{s['index']}.srt"
        if not out.exists():
            r = cl.run([cl._tool("ffmpeg"), "-y", "-v", "error", "-i", str(path), "-map",
                        f"0:{s['index']}", "-f", "srt", str(out)], capture_output=True)
            if r.returncode != 0:
                continue
        cues = parse_srt(out.read_text("utf8", "replace"))
        if len(cues) > max(5, len(best)):
            best = cues
            if s["sdh"] or len(tracks) == 1:
                break
    return best, ("subtitles inside the video" if best else "")


# ---------------------------------------------------------------------------
# Downloading subtitles for videos that have none
# ---------------------------------------------------------------------------
def guess_title(path):
    """("Castle", 1, 7) for an episode, ("Farm Movie (2024)", None, None) for a
    movie, or None when the name doesn't say which episode it is. Uses the
    folder names too: E:\\Movies\\Castle\\Season 1\\S01E07_Title.mp4."""
    p = Path(path)
    stem = p.stem.replace("_", " ").replace(".", " ")
    parent, grand = p.parent.name, p.parent.parent.name
    season = episode = None
    m = (re.search(r"\b[Ss](\d{1,2})\s*[Ee](\d{1,3})\b", stem)
         or re.search(r"\b(\d{1,2})x(\d{2,3})\b", stem))
    show = ""
    if m:
        season, episode = int(m.group(1)), int(m.group(2))
        show = stem[:m.start()].strip(" -#")
    else:
        fs = re.match(r"(?i)\s*(season|series|s)\s*(\d{1,2})\s*$", parent)
        em = re.match(r"\s*#?\s*(?:e|ep|episode)?\s*(\d{1,3})\b(?!\s*[xX:])", stem, re.I)
        if fs and em:
            season, episode = int(fs.group(2)), int(em.group(1))
        elif fs or re.search(r"(?i)\b(s\d{1,2}|d\d|t\d{1,2}|disc|title|track)\b", stem):
            return None   # a disc/track name: can't tell which episode
    if season is not None:
        if not re.search(r"[A-Za-z]{2}", show):
            fs = re.match(r"(?i)\s*(season|series|s)\s*\d{1,2}\s*$", parent)
            show = grand if fs else parent
        show = re.sub(r"\s*[\(\[].*?[\)\]]\s*", " ", show).strip()
        return (show, season, episode) if show else None
    title = stem.strip()
    return (title, None, None) if re.search(r"[A-Za-z]{2}", title) else None


def download_subtitles(path, workdir, log=print):
    """Look up English subtitles online (hearing-impaired ones first). Returns
    (srt_text, where_from) or (None, reason)."""
    if importlib.util.find_spec("subliminal") is None:
        return None, "the subtitle finder isn't installed"
    t = guess_title(path)
    if not t:
        return None, "couldn't tell which episode this is from its name"
    import subliminal
    from babelfish import Language
    try:
        subliminal.region.configure("dogpile.cache.memory", replace_existing_backend=True)
    except Exception:
        pass
    ext = Path(path).suffix or ".mkv"
    name = (f"{t[0]}.S{t[1]:02d}E{t[2]:02d}{ext}" if t[1] is not None else f"{t[0]}{ext}")
    video = subliminal.Video.fromname(name)
    try:
        scanned = subliminal.scan_video(path)
        video.size = scanned.size
        subliminal.refine(scanned, refiners=["hash"])
        video.hashes = getattr(scanned, "hashes", {}) or {}
    except Exception:
        pass
    try:
        got = subliminal.download_best_subtitles({video}, {Language("eng")}, only_one=True,
                                                 subtitle_categories="hi,n")
    except Exception as ex:
        return None, f"the subtitle sites couldn't be reached ({str(ex)[:60]})"
    subs = got.get(video) or []
    for sub in subs:
        text = getattr(sub, "text", None)
        if text and "-->" in text:
            label = "hearing-impaired " if getattr(sub, "hearing_impaired", False) else ""
            return text, f"{label}subtitles downloaded from {sub.provider_name}"
    return None, "no matching subtitles were found online"


def sync_cues(cues, asr, min_match=0.25):
    """Re-time downloaded subtitles to the words actually heard (they are often
    from a different release: shifted, sped up, or cut differently). Returns
    (retimed_cues, matched_fraction)."""
    if not cues or not asr:
        return [], 0.0
    words, where = [], []
    for ci, c in enumerate(cues):
        toks = [cl.norm(w) for w in spoken_words(c["text"])]
        toks = [w for w in toks if w]
        for k, w in enumerate(toks):
            words.append(w)
            where.append(c["s"] + (c["e"] - c["s"]) * (k + 0.5) / max(1, len(toks)))
    asr_n = [w["n"] if "n" in w else cl.norm(w["t"]) for w in asr]
    mapping = cl.align(words, asr_n)
    pairs = [(where[i], (asr[j]["s"] + asr[j]["e"]) / 2) for i, j in enumerate(mapping)
             if j is not None]
    frac = len(pairs) / max(1, len(words))
    if frac < min_match or len(pairs) < 10:
        return [], frac
    x = np.array([p[0] for p in pairs])
    y = np.array([p[1] for p in pairs])

    def local(d, t):
        # offset from the nearest matched words, so a jump in timing is followed
        near = np.argsort(np.abs(x - t))[:min(9, len(x))]
        return float(np.median(d[near]))

    # speed differences between releases are frame-rate ratios (PAL 25 vs film
    # 23.976 and so on); offsets can jump where the releases were cut differently
    best = None
    for rate in (1.0, 25 / 23.976, 23.976 / 25, 24 / 23.976, 23.976 / 24, 25 / 24, 24 / 25):
        d = y - rate * x
        err = float(np.median(np.abs(d - np.array([local(d, t) for t in x]))))
        if best is None or err < best[0]:
            best = (err, rate, d)
    err, rate, d = best
    if err > 1.0:
        return [], frac

    def fix(t):
        return rate * t + local(d, t)

    out = []
    for c in cues:
        s, e = fix(c["s"]), fix(c["e"])
        if e > s > -1:
            out.append({"s": max(0.0, s), "e": e, "text": c["text"]})
    return out, frac


SPOKEN_STRIP = re.compile(r"\[[^\]]*\]|\([^)]*\)|^[A-Z][A-Z .'-]{1,20}:|^\s*-\s*|♪", re.M)
SDH_VIOLENCE = re.compile(r"gun|shot|scream|explo|punch|stab|groan|grunt|gasp|shriek|thud|"
                          r"fight|struggl|body falls|bones? crack|blood|machine gun", re.I)
SDH_SEX = re.compile(r"moan|pant|sexual|climax|orgasm|kissing passionately|bed creak", re.I)


def spoken_words(text):
    """Words actually said in a cue (no [sound tags], (notes) or SPEAKER: labels)."""
    return SPOKEN_STRIP.sub(" ", text).split()


# ---------------------------------------------------------------------------
# Listening (dialogue) and the sound-event scan
# ---------------------------------------------------------------------------
def _audio_cmd(path, info, dialogue):
    a = info["audio"]
    mix = ["-af", "pan=mono|c0=FC"] if dialogue and a["channels"] >= 5 else ["-ac", "1"]
    return [cl._tool("ffmpeg"), "-v", "error", "-i", str(path), "-map", f"0:{a['index']}",
            "-vn", "-sn", *mix, "-ar", str(SR), "-f", "f32le", "-"]


def _stream_chunks(cmd, chunk, overlap, cancel=None):
    """Yield (offset_seconds, samples, is_last) from ffmpeg's raw output."""
    proc = cl.popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    C, O = int(chunk * SR), int(overlap * SR)
    buf, offset, eof = np.zeros(0, dtype=np.float32), 0.0, False
    try:
        while True:
            if cancel and cancel():
                raise KeyboardInterrupt
            while not eof and len(buf) < C:
                data = proc.stdout.read((C - len(buf)) * 4)
                if not data:
                    eof = True
                    break
                data = data[: len(data) // 4 * 4]
                buf = np.concatenate([buf, np.frombuffer(data, dtype=np.float32)])
            last = eof and len(buf) <= C
            yield offset, buf[:C], last
            if last:
                break
            buf = buf[C - O:]
            offset += (C - O) / SR
    finally:
        proc.kill()
        proc.wait()


def transcribe(path, info, rec, progress=None, cancel=None, chunk=30.0, overlap=2.0):
    def go(dialogue):
        out, first = [], True
        for offset, seg, last in _stream_chunks(_audio_cmd(path, info, dialogue), chunk, overlap, cancel):
            if len(seg) > SR * 0.2:
                s = rec.create_stream()
                s.accept_waveform(SR, seg)
                rec.decode_stream(s)
                lo = offset + (overlap / 2 if not first else -1)
                hi = offset + chunk - overlap / 2 if not last else 1e12
                out.extend(w for w in cl.tokens_to_words(s.result, offset) if lo <= w["s"] < hi)
            first = False
            if progress:
                progress(offset + len(seg) / SR)
        return out

    words = go(True)
    if not words and info["audio"]["channels"] >= 5:
        words = go(False)  # no centre (dialogue) channel after all: use the full mix
    return words


# label -> weight. Violence is judged by sound (gunfire, explosions,
# screaming, blows); there is no reliable way to "see" gore on a home PC.
VIOLENCE_SOUNDS = {"Gunshot, gunfire": 1.0, "Machine gun": 1.0, "Fusillade": 1.0,
                   "Artillery fire": 0.8, "Explosion": 0.7, "Screaming": 0.8,
                   "Battle cry": 0.5, "Slap, smack": 0.5, "Whack, thwack": 0.5,
                   "Smash, crash": 0.25}
INTIMATE_SOUNDS = {"Breathing": 0.6, "Pant": 0.8, "Gasp": 0.5, "Sigh": 0.4,
                   "Wail, moan": 0.8, "Groan": 0.5}
SOUND_WORDS = {"Gunshot, gunfire": "gunshot-like bangs", "Machine gun": "gunfire-like bursts",
               "Fusillade": "gunfire-like bursts", "Artillery fire": "heavy bangs",
               "Explosion": "an explosion", "Screaming": "screaming", "Battle cry": "shouting",
               "Slap, smack": "hitting", "Whack, thwack": "hitting", "Smash, crash": "crashing"}
TRACKED = list(VIOLENCE_SOUNDS) + [k for k in INTIMATE_SOUNDS if k not in VIOLENCE_SOUNDS]
SOUND_WIN, SOUND_HOP = 3.0, 1.5


def load_tagger(threads=None):
    import sherpa_onnx
    threads = threads or max(1, min(4, (os.cpu_count() or 2)))
    cfg = sherpa_onnx.AudioTaggingConfig(
        model=sherpa_onnx.AudioTaggingModelConfig(ced=str(TAG_DIR / "model.int8.onnx"),
                                                  num_threads=threads),
        labels=str(TAG_DIR / "class_labels_indices.csv"), top_k=5)
    return sherpa_onnx.AudioTagging(cfg)


def sound_scan(path, info, tagger, progress=None, cancel=None):
    """Probabilities of the tracked sounds in 3-second windows every 1.5 s.
    Returns {"t": [...window starts], "p": [[...per TRACKED label]]}."""
    ts, rows = [], []
    for offset, seg, last in _stream_chunks(_audio_cmd(path, info, False), SOUND_WIN,
                                            SOUND_WIN - SOUND_HOP, cancel):
        if len(seg) < SR * 0.5:
            continue
        s = tagger.create_stream()
        s.accept_waveform(SR, seg)
        got = {e.name: e.prob for e in tagger.compute(s, top_k=527)}
        ts.append(round(offset, 2))
        rows.append([round(float(got.get(k, 0.0)), 3) for k in TRACKED])
        if progress:
            progress(offset + len(seg) / SR)
    return {"labels": TRACKED, "t": ts, "p": rows}


# ---------------------------------------------------------------------------
# The picture scan (runs in its own process so its libraries never clash
# with the speech model's)
# ---------------------------------------------------------------------------
NUDE_CLASSES = ["FEMALE_GENITALIA_COVERED", "FACE_FEMALE", "BUTTOCKS_EXPOSED",
                "FEMALE_BREAST_EXPOSED", "FEMALE_GENITALIA_EXPOSED", "MALE_BREAST_EXPOSED",
                "ANUS_EXPOSED", "FEET_EXPOSED", "BELLY_COVERED", "FEET_COVERED",
                "ARMPITS_COVERED", "ARMPITS_EXPOSED", "FACE_MALE", "BELLY_EXPOSED",
                "MALE_GENITALIA_EXPOSED", "ANUS_COVERED", "FEMALE_BREAST_COVERED",
                "BUTTOCKS_COVERED"]
NUDITY = {"FEMALE_BREAST_EXPOSED": 0.6, "FEMALE_GENITALIA_EXPOSED": 0.55,
          "MALE_GENITALIA_EXPOSED": 0.55, "BUTTOCKS_EXPOSED": 0.6, "ANUS_EXPOSED": 0.55}
DARK_MEAN, FLAT_STD = 40, 18   # frames darker or flatter than this are too murky to judge
SKIN = {"MALE_BREAST_EXPOSED": 0.45, "BELLY_EXPOSED": 0.45, "ARMPITS_EXPOSED": 0.45}
KEEP = list(NUDITY) + list(SKIN)


PICTURE_VERSION = 3


def _visual_scan_here(path, out_json, use_clip=False, fps=VISUAL_FPS):
    import onnxruntime as ort
    info = probe(path)
    dar = info["video"].get("dar") or 16 / 9
    H = 256
    W = max(64, int(round(H * dar / 2)) * 2)
    threads = max(1, min(6, (os.cpu_count() or 2) - 1))
    opts = ort.SessionOptions()
    opts.intra_op_num_threads = threads
    sess = ort.InferenceSession(str(nudity_model()), opts, providers=["CPUExecutionProvider"])
    name = sess.get_inputs()[0].name
    cols = [NUDE_CLASSES.index(k) for k in KEEP]
    clip = None
    if use_clip:
        try:
            clip = ai.Clip(ort, threads)
        except Exception as ex:   # carry on without it rather than fail the whole scan
            print(f"E picture AI unavailable: {ex}", flush=True)
    cmd = [cl._tool("ffmpeg"), "-v", "error", "-i", str(path), "-map", "0:v:0", "-an", "-sn",
           "-vf", f"fps={fps},scale={W}:{H},setsar=1,format=rgb24", "-f", "rawvideo", "-"]
    proc = cl.popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    size, batch, n, out, lum = W * H * 3, 8, 0, [], []
    ct, cs = [], []
    try:
        while True:
            frames = []
            for _ in range(batch):
                data = proc.stdout.read(size)
                if len(data) < size:
                    break
                frames.append(np.frombuffer(data, dtype=np.uint8).reshape(H, W, 3))
            if not frames:
                break
            x = np.stack([ai.nudenet_input(f) for f in frames]).astype(np.float32)
            y = sess.run(None, {name: x})[0]          # (batch, 4 + 18, anchors)
            best = y[:, 4:, :].max(axis=2)            # best score per class per frame
            for k, row in enumerate(best):
                out.append([round(float(row[c]), 3) for c in cols])
                g = frames[k].mean(axis=2)
                lum.append([round(float(g.mean()), 1), round(float(g.std()), 1)])
                fn = n + k
                if clip is not None and fn % 2 == 0:  # picture AI once a second
                    ct.append(round(fn / fps, 2))
                    cs.append({c: round(v, 3) for c, v in clip.scores(frames[k]).items()})
            n += len(frames)
            print(f"P {n / fps:.1f}", flush=True)
            if len(frames) < batch:
                break
    finally:
        proc.kill()
        proc.wait()
    Path(out_json).write_text(json.dumps({
        "version": PICTURE_VERSION, "fps": fps, "classes": KEEP, "scores": out, "lum": lum,
        "clip": {"t": ct, "scores": cs} if clip is not None else None}))


def visual_scan(path, out_json, use_clip=False, progress=None, cancel=None):
    cmd = [_venv_python(), str(HERE / "cleanview.py"), "visualscan", str(path), str(out_json)]
    if use_clip:
        cmd.append("--clip")
    errf = Path(out_json).with_suffix(".err.txt")
    notes = []
    with open(errf, "w", encoding="utf8") as err:
        proc = cl.popen(cmd, stdout=subprocess.PIPE, stderr=err, text=True)
        try:
            for line in proc.stdout:
                if cancel and cancel():
                    proc.kill()
                    raise KeyboardInterrupt
                if line.startswith("P ") and progress:
                    progress(float(line[2:]))
                elif line.startswith("E "):
                    notes.append(line[2:].strip())
            proc.wait()
        finally:
            if proc.poll() is None:
                proc.kill()
    if proc.returncode != 0 or not Path(out_json).exists():
        raise RuntimeError("The picture check failed:\n" + errf.read_text("utf8", "replace")[-800:])
    res = json.loads(Path(out_json).read_text())
    res["notes"] = notes
    return res


# ---------------------------------------------------------------------------
# Turning scan results into scenes
# ---------------------------------------------------------------------------
def _group(times, gap):
    """Group sorted times into runs where neighbours are <= gap apart."""
    runs = []
    for t in times:
        if runs and t - runs[-1][-1] <= gap:
            runs[-1].append(t)
        else:
            runs.append([t])
    return runs


def nudity_scenes(vis, start_off=0.0):
    if not vis or not vis["scores"]:
        return [], []
    fps, cls = vis["fps"], vis["classes"]
    nude_i = [cls.index(k) for k in NUDITY]
    skin_i = [cls.index(k) for k in SKIN]
    hits, strong, skin = [], {}, []
    lum = vis.get("lum") or []
    for n, row in enumerate(vis["scores"]):
        t = start_off + n / fps
        if n < len(lum) and (lum[n][0] < DARK_MEAN or lum[n][1] < FLAT_STD):
            continue   # too dark or murky: the checker guesses on frames like these
        best = max((row[i] / NUDITY[cls[i]], cls[i]) for i in nude_i)
        if best[0] >= 1.0:
            hits.append(t)
            strong[t] = row[cls.index(best[1])]
        if any(row[i] >= SKIN[cls[i]] for i in skin_i):
            skin.append(t)
    scenes = []
    for run_ in _group(hits, 5.0):
        # brief or weak hits are usually false alarms (a bare shoulder, a skin-toned blur)
        peak = max(strong[t] for t in run_)
        if len(run_) < 3 and peak < 0.85:
            continue
        scenes.append({"s": max(0.0, run_[0] - 1.5), "e": run_[-1] + 1.5, "kind": ["Nudity"],
                       "sure": peak >= 0.75 and len(run_) >= 4,
                       "why": f"nudity seen in {len(run_)} picture checks (strongest {peak:.0%})"})
    return scenes, skin


def violence_scenes(snd, cues):
    if not snd or not snd["t"]:
        return []
    labels = snd["labels"]
    vi = [(labels.index(k), w) for k, w in VIOLENCE_SOUNDS.items()]
    flagged, why, strong = [], {}, set()
    for t, row in zip(snd["t"], snd["p"]):
        score = sum(row[i] * w for i, w in vi)
        if score >= 0.45:
            flagged.append(t)
            if score >= 0.55:
                strong.add(t)
            top = max(vi, key=lambda iw: row[iw[0]] * iw[1])
            why.setdefault(t, SOUND_WORDS.get(labels[top[0]], labels[top[0]].lower()))
    # SDH subtitles often describe violence: [gunshot], [screaming], [grunts]
    for c in cues:
        tags = " ".join(a or b for a, b in re.findall(r"\[([^\]]*)\]|\(([^)]*)\)", c["text"]))
        if tags and SDH_VIOLENCE.search(tags):
            for t in np.arange(c["s"], max(c["s"], c["e"] - SOUND_WIN) + 0.01, SOUND_HOP):
                flagged.append(round(float(t), 2))   # the whole time the tag is on screen
            why.setdefault(round(float(c["s"]), 2), tags.lower()[:30])
    flagged.sort()
    scenes = []
    for run_ in _group(flagged, 8.0):
        span = run_[-1] - run_[0]
        if len(run_) < 3 and span < 3 and not strong.intersection(run_):
            continue   # one quiet bang or slap isn't a violent scene; a loud burst is
        kinds = []
        for t in run_:
            w = why.get(t)
            if w and w not in kinds:
                kinds.append(w)
        scenes.append({"s": max(0.0, run_[0] - 1.0), "e": run_[-1] + SOUND_WIN + 1.0,
                       "kind": ["Violence"], "why": ", ".join(kinds[:4])})
    return scenes


def sex_scenes(snd, cues, asr_n, asr, skin, nude):
    """Sex scenes without visible nudity: intimate sounds together with bare
    skin on screen, SDH tags like [moaning], or explicit dialogue."""
    marks = []
    if snd and snd["t"]:
        labels = snd["labels"]
        ii = [(labels.index(k), w) for k, w in INTIMATE_SOUNDS.items()]
        intimate = [t for t, row in zip(snd["t"], snd["p"])
                    if sum(row[i] * w for i, w in ii) >= 0.5]
        skin_set = sorted(skin + [s["s"] for s in nude])
        import bisect
        for run_ in _group(intimate, 4.5):
            if run_[-1] - run_[0] < 6:
                continue
            k = bisect.bisect_left(skin_set, run_[0] - 10)
            if k < len(skin_set) and skin_set[k] <= run_[-1] + 10:
                marks.append((run_[0], run_[-1] + SOUND_WIN, "intimate sounds with bare skin"))
    for c in cues:
        if any(SDH_SEX.search(t) for t in re.findall(r"\[([^\]]*)\]", c["text"])):
            marks.append((c["s"], c["e"], "subtitles describe it"))
    # explicit dialogue (same scoring CleanListen uses for books)
    k = 0
    while k < len(asr):
        j = k
        while j < len(asr) and asr[j]["s"] - asr[k]["s"] < 60:
            j += 1
        if cl.sex_score(asr_n[k:j]) >= cl.SEX_WINDOW_SCORE:
            hits = [x for x in range(k, j) if cl.is_explicit([asr_n[x]])]
            marks.append((asr[hits[0]]["s"] - 2, asr[hits[-1]]["e"] + 2, "explicit dialogue"))
        k = j if j > k else k + 1
    marks.sort()
    scenes = []
    for s, e, w in marks:
        if scenes and s - scenes[-1]["e"] <= 10:
            scenes[-1]["e"] = max(scenes[-1]["e"], e)
            if w not in scenes[-1]["why"]:
                scenes[-1]["why"] += ", " + w
        else:
            scenes.append({"s": max(0.0, s - 1.0), "e": e + 1.0, "kind": ["Sex scene"], "why": w})
    return scenes


def merge_scenes(scenes):
    out = []
    for sc in sorted(scenes, key=lambda x: x["s"]):
        if out and sc["s"] <= out[-1]["e"] + 2.0:
            o = out[-1]
            o["e"] = max(o["e"], sc["e"])
            o["kind"] += [k for k in sc["kind"] if k not in o["kind"]]
            o["why"] = "; ".join(x for x in (o["why"], sc["why"]) if x)
            o["sure"] = o.get("sure", True) and sc.get("sure", True)
        else:
            out.append(dict(sc, kind=list(sc["kind"])))
    return out


# ---------------------------------------------------------------------------
# Analyze
# ---------------------------------------------------------------------------
LINE_WORDS = {   # only phrases that are hard to mistake
    "sexref": re.compile(r"\b(sex|sexy|horny|make love|made love|making love|condoms?|boobs|"
                         r"hookers?|prostitutes?|strippers?|orgasms?|threesome|blow ?job|porn|"
                         r"have sex|had sex|having sex)\b", re.I),
    "casual": re.compile(r"\b(one[- ]night stand|hook(ed|ing)? up with|slept with|sleep(ing)? "
                         r"around|having an affair|had an affair|an affair with|cheat(ed|ing)? "
                         r"on (him|her|me|you)|booty call|friends with benefits)\b", re.I),
    "samesex": re.compile(r"\b(gay|lesbians?|homosexual|bisexual|same[- ]sex|"
                          r"husband and husband|wife and wife)\b", re.I),
    "oppsex": re.compile(r"\b(moved in together|living together|shacking up|"
                         r"sleeping together|slept together)\b", re.I),
    "crude": re.compile(r"\b(farts?|farted|farting|poop(ed|ing)?|butt crack|boogers?|"
                        r"peed (my|his|her|your) pants)\b", re.I),
    "bullying": re.compile(r"\b(nobody likes you|you're worthless|you are worthless|"
                           r"fatso|four[- ]eyes|crybaby|you freak)\b", re.I),
}
LINE_LABEL = {"crude": "Crude humor", "bullying": "Bullying", "learned": "You muted this before",
              "added": "Added by you", "claude": "Found by Claude",
              "shared": "CleanView learned", "chat": "You asked in the chat",
              "sexref": "Sexual reference", "casual": "Sleeping around",
              "samesex": "Same-sex relationship", "oppsex": "Unmarried couple"}
WHO_LABEL = {"mf": "man & woman", "mm": "two men", "ff": "two women"}
CAT_LABEL = {"gore": "Gore", "fight": "Violence", "smoking": "Smoking", "drinking": "Drinking",
             "drugs": "Drugs", "immodest": "Immodest clothing"}


GROUP_TEXT = {"swearing": "swear words (strong and moderate)",
              "mild": "mild language such as crap, screw you, damn, hell",
              "deity": "God's or Jesus' name used as a swear (not sincere prayer or talk about God)",
              "minced": "minced oaths such as gosh, darn, heck",
              "samesexwords": "words about same-sex relationships (gay, lesbian, homosexual...)"}
OPT_TEXT = {"nudity": "nudity (private parts actually shown)",
            "implied": "implied nudity (undressed but covered by sheets, towels or the camera)",
            "sex": "sex scenes", "violence": "violence",
            "gore": "graphic gore", "immodest": "immodest clothing", "smoking": "smoking",
            "drinking": "drinking", "drugs": "drug use",
            "samesex": "same-sex relationships and romance, including flirting",
            "casual": "sleeping around (casual sex, hooking up, affairs)",
            "oppsex": "unmarried man and woman living or sleeping together",
            "sexref": "sexual references and innuendo", "crude": "crude humor",
            "bullying": "bullying"}
KISS_TEXT = {"passionate": "passionate kissing (light kisses are fine)", "all": "all kissing"}


def sound_cues(cues, limit=150):
    """Sound descriptions from hearing-impaired subtitles ([gunshot], (moaning))."""
    out = []
    for c in cues or []:
        tags = [a or b for a, b in re.findall(r"\[([^\]]*)\]|\(([^)]*)\)", c["text"])]
        tags = [t.strip() for t in tags if t.strip()]
        if tags:
            s = int(c["s"])
            out.append(f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d} " + "; ".join(tags))
    return "\n".join(out[:limit])


def wanted_text(o, groups):
    o = full_opts(o)
    out = [GROUP_TEXT[g] for g in groups if g in GROUP_TEXT]
    out += [t for k, t in OPT_TEXT.items() if o.get(k)]
    for k, who in (("kiss_os", "between a man and a woman"), ("kiss_ss", "between two men or two women")):
        if o.get(k) in KISS_TEXT:
            out.append(KISS_TEXT[o[k]] + " " + who)
    return "\n".join("- " + t for t in out) or "- (nothing chosen)"


def _set_on(kind, it, on):
    if kind == "scene":
        it["cut"] = on
    elif kind == "line":
        it["mute"] = on
    else:
        it["keep"] = not on


def word_mute(st, line, word, why):
    """Mute just one word of a dialogue line (Claude's "just the word").
    Uses a word already on the list if there is one, else finds the word's
    time in what was heard, else estimates it from its place in the line."""
    target = cl.norm(word.replace("-", ""))
    if not target:
        return None
    a, b = line["s"] - 0.6, line["e"] + 0.6
    for m in st.get("mutes", []):          # already on the list (timings can be ~2 s off)
        if a - 2.0 <= m["s"] <= b + 1.0 and \
                target in cl.norm((m.get("raw") or m["word"]).replace(" ", "")):
            return m
    s = e = None
    src = "claude"
    heard = [w for w in st.get("asr", []) if a <= w[1] <= b]
    for k, w in enumerate(heard):
        n = cl.norm(w[0])
        if n == target or (len(target) > 3 and target in n):
            s, e = w[1], w[2]
            break
        if k + 1 < len(heard) and n + cl.norm(heard[k + 1][0]) == target:   # "sweet" "ass"
            s, e = w[1], heard[k + 1][2]
            break
    if s is None:                 # not heard clearly: place it by its position in the line
        toks = [cl.norm(t) for t in (line.get("plain") or line["text"]).replace("-", " ").split()]
        parts = [cl.norm(p) for p in word.replace("-", " ").split()] or [target]
        pos = next((k for k in range(len(toks)) if toks[k:k + len(parts)] == parts), None)
        if pos is None:
            return None
        mid = line["s"] + (line["e"] - line["s"]) * (pos + len(parts) / 2) / max(1, len(toks))
        s, e = max(line["s"], mid - 0.6), min(line["e"], mid + 0.6)
        src = "claude-estimated"
    ctx_words = [w[0] for w in st.get("asr", []) if line["s"] - 0.3 <= w[1] < s][-6:]
    m = {"s": round(s, 3), "e": round(e, 3), "cat": "claude", "src": src,
         "word": " ".join(cl.mask(p) for p in word.split()), "raw": target,
         "ctx": " ".join(ctx_words) or (line.get("plain") or line["text"])[:60]}
    try:
        m["s"], m["e"] = cl.snap_edges(st["path"], m["s"], m["e"], wide=src != "claude")
    except Exception:
        pass
    st.setdefault("mutes", []).append(m)
    st["mutes"].sort(key=lambda x: x["s"])
    return m


def _set_on(kind, it, on):
    if kind == "scene":
        it["cut"] = on
    elif kind == "line":
        it["mute"] = on
    else:
        it["keep"] = not on


def apply_review(st, result):
    """Put Claude's full review into the analysis: tick/untick what it judged
    and add what it found missing. Never changes what she set herself."""
    items, decisions, missed, missed_scenes, summary = result
    lines = st.get("dialogue", [])
    n_drop = n_add = n_word = 0
    for i, (kind, it) in items.items():
        if not (it.get("claude") or {}).get("seen"):
            it.pop("claude", None)
    for i, (kind, it) in items.items():
        d = decisions.get(i)
        if not d or (it.get("claude") or {}).get("seen"):
            continue                       # scenes already checked by looking at the picture
        dec, why, word = d
        it["claude"] = {"decision": dec, "why": why}
        if word and dec == "just the word":
            it["claude"]["word"] = word
        mine = it.get("by_you") or it.get("learned")
        if dec == "just the word":
            ms = [word_mute(st, it, w.strip(), why) for w in re.split(r"[|,]", word) if w.strip()]
            m = None if (not ms or None in ms) else ms[0]
            if m is None:                 # couldn't place the word: keep the whole line muted
                it["claude"]["decision"] = "remove"
                it["claude"]["why"] = why + " (couldn't pin down when the word is said, so the " \
                                            "whole line is muted to be safe)"
                if not mine:
                    _set_on(kind, it, True)
                continue
            for m in ms:
                if not m.get("by_you") and not m.get("learned"):
                    m["keep"] = False
                m.setdefault("claude", {"decision": "remove", "why": f"from the line: {why}"})
            if not mine:
                _set_on(kind, it, False)
                n_word += 1
        elif mine:
            continue
        elif dec == "not an issue":
            n_drop += 1
            _set_on(kind, it, False)
        elif dec == "remove":
            _set_on(kind, it, True)
    have = {l.get("idx") for l in st.get("lines", [])}
    for k, why, word in missed:
        if k in have:
            continue
        l = lines[k]
        ms = [word_mute(st, l, w.strip(), why) for w in re.split(r"[|,]", word) if w.strip()]
        if ms and None not in ms:
            for m in ms:
                m["keep"] = False
                m.setdefault("claude", {"decision": "remove", "why": why})
            n_add += 1
            continue
        st["lines"].append({"s": l["s"], "e": l["e"], "text": l["text"], "plain": l["text"],
                            "types": ["claude"], "mute": True, "idx": k,
                            "claude": {"decision": "remove", "why": why}})
        have.add(k)
        n_add += 1
    st["lines"].sort(key=lambda l: l["s"])
    for n, l in enumerate(st["lines"], 1):
        l["id"] = n
    for s in missed_scenes:
        a, b = max(0.0, lines[s["from"]]["s"] - 1.0), lines[s["to"]]["e"] + 1.0
        b = min(b, st.get("duration", b))
        if any(sc["s"] <= a + 2 and sc["e"] >= b - 2 for sc in st["scenes"]):
            continue
        over = [sc for sc in st["scenes"] if sc["s"] < b and sc["e"] > a and not sc.get("by_you")]
        if over:                          # overlaps a scene already listed: widen that one
            sc = over[0]
            sc["s"], sc["e"] = round(min(sc["s"], a), 2), round(max(sc["e"], b), 2)
            sc["cut"] = True
            sc["claude"] = {"decision": "remove", "why": s["why"] + f" (widened by {st.get('reviewer', 'Claude')})"}
            sc["said"] = " ".join(l["text"] for l in lines if sc["s"] - 0.5 <= l["s"] <= sc["e"])[:600]
            sc.pop("thumbs", None)
            n_add += 1
            continue
        st["scenes"].append({"id": max([sc.get("id", 0) for sc in st["scenes"]] + [0]) + 1,
                             "s": round(a, 2), "e": round(b, 2),
                             "kind": ["Found by " + st.get("reviewer", "Claude")],
                             "why": s["why"], "cut": True,
                             "said": " ".join(l["text"] for l in lines[s["from"]:s["to"] + 1])[:600],
                             "claude": {"decision": "remove", "why": s["why"]}})
        n_add += 1
    st["scenes"].sort(key=lambda sc: sc["s"])
    st["claude_summary"] = summary
    st["claude_counts"] = {"dropped": n_drop, "added": n_add, "words": n_word}
    return n_drop, n_add


def _secs(t):
    try:
        x = 0.0
        for part in str(t).strip().split(":"):
            x = x * 60 + float(part)
        return x
    except ValueError:
        return None


def apply_chat(st, items, acts, work=None):
    """Make the changes asked for in the chat, straight away. Everything changed
    counts as the person's own choice. Returns a list of plain descriptions."""
    lines = st.get("dialogue", [])
    who = st.get("reviewer") or cc.name()
    done = []

    def t(sec):
        return cl.fmt_t(sec)
    for ids, on in ((acts.get("tick", []), True), (acts.get("untick", []), False)):
        for i in ids:
            if i not in items:
                continue
            kind, it = items[i]
            _set_on(kind, it, on)
            it["by_you"] = True
            what = {"scene": "scene", "line": "line", "word": "word"}[kind]
            verb = ("cut" if kind == "scene" else "mute") if on else "keep"
            done.append(f"{verb} the {what} at {t(it['s'])}")
    have = {l.get("idx"): l for l in st.get("lines", [])}
    for k in acts.get("mute_lines", []):
        l = have.get(k)
        if l is not None:
            l["mute"], l["by_you"] = True, True
        else:
            d = lines[k]
            st["lines"].append({"s": d["s"], "e": d["e"], "text": d["text"], "plain": d["text"],
                                "types": ["chat"], "mute": True, "idx": k, "by_you": True})
        done.append(f"mute the line at {t(lines[k]['s'])}")
    for k, word in acts.get("mute_words", []):
        m = word_mute(st, lines[k], word, "you asked")
        if m is None:
            done.append(f"couldn't find \u201c{word}\u201d at {t(lines[k]['s'])}")
            continue
        m["keep"], m["by_you"] = False, True
        l = have.get(k)
        ticked = {id(items[i][1]) for i in acts.get("tick", []) if i in items}
        if l is not None and l.get("mute", True) and k not in acts.get("mute_lines", []) \
                and id(l) not in ticked:
            l["mute"], l["by_you"] = False, True       # just the word now, not the whole line
            done.append(f"stop muting the whole line at {t(l['s'])}")
        done.append(f"mute \u201c{word}\u201d at {t(lines[k]['s'])}")
    st["lines"].sort(key=lambda l: l["s"])
    for n, l in enumerate(st["lines"], 1):
        l["id"] = n
    new = []
    for c in acts.get("cut_scenes", []):
        a, b = max(0.0, lines[c["from"]]["s"] - 0.5), lines[c["to"]]["e"] + 0.5
        new.append((a, b, c["why"]))
    dur = st.get("duration", 1e9)
    for c in acts.get("cut_times", []):
        a, b = _secs(c["from"]), _secs(c["to"])
        if a is not None and b is not None and b > a and a < dur:
            new.append((a, min(b, dur), c["why"]))
    for a, b, why in new:
        sc = {"id": max([x.get("id", 0) for x in st["scenes"]] + [0]) + 1,
              "s": round(a, 2), "e": round(b, 2), "kind": [f"Asked {who}"],
              "why": why or "you asked in the chat", "cut": True, "by_you": True,
              "added": True,
              "said": " ".join(l["text"] for l in lines if a - 0.5 <= l["s"] <= b)[:600]}
        st["scenes"].append(sc)
        done.append(f"cut {t(a)} to {t(b)}")
    st["scenes"].sort(key=lambda x: x["s"])
    if work is not None and new:
        try:
            make_thumbs(st["path"], [x for x in st["scenes"] if "thumbs" not in x], work)
        except Exception:
            pass
    return done


def claude_review(st, work=None):
    """Claude's final review of everything found (also used by the
    "Review everything again" button). Raises cc.ClaudeError."""
    st["reviewer"] = cc.name()
    res = cc.review(st, wanted_text(st.get("opts"), st.get("groups", [])),
                    learn.examples(st.get("show", "_movies")), sound_cues(st.get("cues")))
    n = apply_review(st, res)
    who = st.get("reviewer", "Claude")
    st["notes"] = [x for x in st.get("notes", []) if " reviewed everything:" not in x]
    nw = st["claude_counts"].get("words", 0)
    st["notes"].append(f"{who} reviewed everything: {n[0]} found item(s) look fine in context "
                       f"and were unticked, {n[1]} missed item(s) were added"
                       + (f", and {nw} line(s) now mute just the bad word instead of the whole line"
                          if nw else "") + ".")
    try:
        learn.record_claude(st)          # teaches the AI on this PC, and the spreadsheet
    except Exception:
        pass
    if work is not None:
        new = [sc for sc in st["scenes"] if "thumbs" not in sc]
        if new:
            make_thumbs(st["path"], new, work)
        (Path(work) / "analysis.json").write_text(json.dumps(st, indent=1))
    return n


# --- Claude / ChatGPT looking at the picture ----------------------------------
PIC_TEXT = {"violence": "violence (fighting, shooting, attacks, threatening with a weapon)",
            "gore": "graphic gore (blood, wounds, bodies)",
            "nudity": "nudity (bare breasts, buttocks or genitals actually shown)",
            "implied": "implied nudity (undressed but covered: under sheets, in a towel, bare "
                       "back or shoulders, shower from the shoulders up)",
            "sex": "sex scenes or a couple in bed", "immodest": "immodest clothing",
            "smoking": "smoking", "drinking": "drinking alcohol", "drugs": "drug use"}
PIC_LABEL = {"violence": "Violence", "gore": "Gore", "nudity": "Nudity",
             "implied nudity": "Implied nudity", "sex": "Sex scene",
             "immodest": "Immodest clothing", "smoking": "Smoking", "drinking": "Drinking",
             "drugs": "Drugs"}
WHO_FROM = {"man & woman": "mf", "two men": "mm", "two women": "ff"}


def picture_wanted(o):
    o = full_opts(o)
    out = [t for k, t in PIC_TEXT.items() if o.get(k)]
    for k, who in (("kiss_os", "between a man and a woman"),
                   ("kiss_ss", "between two men or two women")):
        if o.get(k) in KISS_TEXT:
            out.append(KISS_TEXT[o[k]] + " " + who)
    if o.get("samesex") and o.get("kiss_ss") == "off":
        out.append("same-sex romance: two men or two women kissing or being intimate")
    return "\n".join("- " + t for t in out)


def _pic_wanted(f, o):
    """Does a find from the picture review fit the chosen settings? -> scene label or None."""
    w = f["what"]
    if w == "kissing":
        who = WHO_FROM.get(f.get("who"), "?")
        setting = o["kiss_os"] if who == "mf" else o["kiss_ss"] if who in ("mm", "ff") else \
            ("all" if "all" in (o["kiss_os"], o["kiss_ss"]) else
             "passionate" if "passionate" in (o["kiss_os"], o["kiss_ss"]) else "off")
        if who in ("mm", "ff") and o.get("samesex"):
            setting = "all"
        if setting == "off" or (setting == "passionate" and f.get("level") == "light"):
            return None
        return "Kiss" + (f" · {WHO_LABEL[who]}" if who in WHO_LABEL else "") + \
            (f" · {f['level']}" if f.get("level") in ("light", "passionate") else "")
    if w == "sex" and not o.get("sex"):
        return None
    if w == "implied nudity":
        return "Implied nudity" if o.get("implied") else None
    if w in PIC_LABEL and (w == "sex" or o.get(w)):
        return PIC_LABEL[w]
    return None


def make_sheets(path, work, dur):
    """Stills every 2 seconds, 20 to a sheet (5 x 4), each sheet 40 seconds."""
    d = Path(work) / "sheets"
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    r = cl.run([cl._tool("ffmpeg"), "-v", "error", "-i", str(path), "-map", "0:v:0", "-vf",
                "fps=1/2,scale=320:-2,tile=5x4:padding=4:color=white", "-q:v", "4",
                str(d / "sheet_%04d.jpg")], capture_output=True)
    files = sorted(d.glob("sheet_*.jpg"))
    if not files:
        raise RuntimeError("couldn't take stills from the video")
    return [(str(f), k * 40.0) for k, f in enumerate(files)]


def scene_sheet(path, sc, work):
    """6 sharper stills from inside one scene (3 x 2)."""
    d = Path(work) / "sheets"
    d.mkdir(parents=True, exist_ok=True)
    out = d / f"scene_{sc['id']}.jpg"
    length = max(0.6, sc["e"] - sc["s"])
    cl.run([cl._tool("ffmpeg"), "-v", "error", "-y", "-ss", f"{sc['s']:.2f}", "-t", f"{length:.2f}",
            "-i", str(path), "-map", "0:v:0", "-vf",
            f"fps={6 / length:.4f},scale=480:-2,tile=3x2:padding=4:color=white", "-frames:v", "1",
            "-q:v", "4", str(out)], capture_output=True)
    return str(out) if out.exists() else None


DIALOGUE_KINDS = ("Same-sex romance", "Found by", "Suggested by", "Added by you")


def look_at_picture(path, work, dur, scenes, o, asr, progress=None, cancel=None):
    """Claude/ChatGPT checks the picture: confirms or rules out each scene the
    picture/sound checks found, and adds what they missed. Returns (scenes, note)."""
    say = progress or (lambda f, m: None)
    o = full_opts(o)
    wanted = picture_wanted(o)
    if not wanted:
        return scenes, "Nothing picture-related was chosen, so the picture wasn't looked at."
    say(0.02, "is taking stills of the whole video")
    sheets = make_sheets(path, work, dur)
    if cancel and cancel():
        raise KeyboardInterrupt
    finds = cc.picture_review(sheets, wanted,
                              progress=lambda f: say(0.05 + 0.6 * f, "is looking through the "
                                                     "whole picture"))
    finds = [dict(f, label=_pic_wanted(f, o)) for f in finds]
    finds = [f for f in finds if f["label"]]
    used = set()
    confirmed = 0
    for sc in scenes:
        hit = [k for k, f in enumerate(finds) if f["s"] < sc["e"] and f["e"] > sc["s"]]
        if "Nudity" in sc.get("kind", []):     # nudity must be confirmed by a nudity find
            nh = [k for k in hit if finds[k]["label"] in ("Nudity", "Implied nudity")]
            if not nh:
                continue                       # goes to the closer look below
            if all(finds[k]["label"] == "Implied nudity" for k in nh):
                sc["kind"] = ["Implied nudity" if x == "Nudity" else x for x in sc["kind"]]
        if hit:
            used.update(hit)
            sc["claude"] = {"decision": "remove", "why": "seen: " + finds[hit[0]]["why"],
                            "seen": True}
            sc["cut"] = True
            confirmed += 1
    # a closer look at the rest of the scenes the picture/sound checks found
    todo = [sc for sc in scenes if "claude" not in sc
            and not any(k.startswith(DIALOGUE_KINDS) for k in sc.get("kind", []))]
    for n, sc in enumerate(scenes, 1):
        sc.setdefault("id", n)
    items = []
    for sc in todo:
        p = scene_sheet(path, sc, work)
        if p:
            items.append((sc["id"], ", ".join(sc.get("kind", [])), sc.get("why", ""), p))
    ruled_out = 0
    if items:
        verdicts = cc.verify_scenes(items, wanted, progress=lambda f: say(
            0.7 + 0.28 * f, "is taking a closer look at each scene found"))
        for sc in todo:
            v = verdicts.get(sc["id"])
            if not v:
                continue
            dec, why, nud = v
            if "Nudity" in sc.get("kind", []) and len(sc["kind"]) == 1:
                if nud == "implied":
                    sc["kind"] = ["Implied nudity"]
                    if o.get("implied"):
                        dec = "remove"
                    else:
                        dec, why = "not an issue", "only implied nudity: " + why
                elif nud == "none" and dec == "remove":       # not nudity, but something else
                    sc["kind"] = [f"Seen by {cc.name()}"]
                    why = "not nudity, but: " + why
                elif nud == "none" and dec != "can't tell":   # unsure stays as it is
                    dec, why = "not an issue", "no nudity: " + why
                elif nud == "shown" and o.get("nudity"):
                    dec = "remove"
            v = (dec, why)
            sc["claude"] = {"decision": v[0], "why": v[1], "seen": True}
            if v[0] == "not an issue":
                sc["cut"] = False
                ruled_out += 1
            elif v[0] == "remove":
                sc["cut"] = True
                confirmed += 1
    # what only the picture review saw: join neighbouring finds of the same kind
    new = []
    for k, f in sorted(enumerate(finds), key=lambda kv: kv[1]["s"]):
        if k in used:
            continue
        if new and new[-1]["kind"][0] == f["label"] and f["s"] <= new[-1]["e"] + 4:
            new[-1]["e"] = max(new[-1]["e"], f["e"])
            continue
        new.append({"s": round(f["s"], 2), "e": round(min(f["e"], dur), 2), "kind": [f["label"]],
                    "why": "seen: " + f["why"], "cut": True, "sure": True,
                    "claude": {"decision": "remove", "why": "seen: " + f["why"], "seen": True}})
    top = max([sc.get("id", 0) for sc in scenes] + [0])
    for k, sc in enumerate(new, 1):
        sc["id"] = top + k
        said = [w["t"] for w in asr if sc["s"] <= w["s"] <= sc["e"]]
        sc["said"] = " ".join(said[:80]) + (" …" if len(said) > 80 else "")
    merged = []                 # join scenes to cut that touch or overlap
    for sc in sorted(scenes + new, key=lambda sc: sc["s"]):
        last = merged[-1] if merged else None
        if last and last.get("cut", True) and sc.get("cut", True) and sc["s"] <= last["e"] + 2.0:
            last["e"] = max(last["e"], sc["e"])
            last["kind"] += [k for k in sc["kind"] if k not in last["kind"]]
            if sc.get("why") and sc["why"] not in last.get("why", ""):
                last["why"] = "; ".join(x for x in (last.get("why"), sc["why"]) if x)
            if sc.get("claude") and last.get("claude") and sc["claude"]["why"] not in last["claude"]["why"]:
                last["claude"] = dict(last["claude"], why=last["claude"]["why"] + "; " +
                                      sc["claude"]["why"].replace("seen: ", ""))
            last.pop("thumbs", None)
            said = [w["t"] for w in asr if last["s"] <= w["s"] <= last["e"]]
            last["said"] = " ".join(said[:80]) + (" …" if len(said) > 80 else "")
        else:
            merged.append(sc)
    for k, sc in enumerate(merged, 1):
        sc["id"] = k
    scenes = merged
    who = cc.name()
    note = (f"{who} looked through the whole picture ({len(sheets) * 20} stills): it confirmed "
            f"{confirmed} scene(s), ruled out {ruled_out} false alarm(s) and found {len(new)} "
            f"the other checks missed.")
    return scenes, note


def decide_picture_scenes(cands, o, have_ai):
    """Turn picture-AI candidates (after the second look) into scenes,
    following the chosen settings."""
    rank = {"off": 0, "passionate": 1, "all": 2}
    scenes = []
    for c in cands:
        v = c.get("verdict") or {}
        if have_ai and v and not v.get("keep", True) and not v.get("error"):
            continue
        who = v.get("who", "?") if v else "?"
        if who == "?" and c.get("who"):
            w, pw = max(c["who"].items(), key=lambda kv: kv[1])
            if pw >= 0.5:
                who = w.replace("kiss_", "")
        level = v.get("level", "?") if v else "?"
        checked = bool(v) and not v.get("error")
        note = "" if checked else " (not double-checked, so left unticked)"
        if c["cat"] == "kiss":
            if who == "mf":
                setting = o["kiss_os"]
            elif who in ("mm", "ff"):
                setting = o["kiss_ss"]
            else:
                setting = max(o["kiss_os"], o["kiss_ss"], key=lambda x: rank[x])
            if setting == "off" or (setting == "passionate" and level == "light"):
                continue
            label = "Kiss" + (f" · {WHO_LABEL[who]}" if who in WHO_LABEL else "") + \
                    (f" · {level}" if level in ("light", "passionate") else "")
            why = "kissing seen" + ("" if level != "?" or setting != "passionate"
                                    else ", couldn't tell how passionate") + note
        elif c["cat"] == "bed":
            if not (o["sex"] or (who in ("mm", "ff") and o["samesex"])
                    or (who == "mf" and o["oppsex"])):
                continue
            label = "Intimate scene" + (f" · {WHO_LABEL[who]}" if who in WHO_LABEL else "")
            why = "a couple in bed or making out" + note
        else:
            label = CAT_LABEL[c["cat"]]
            why = f"{label.lower()} seen" + note
        if checked and v.get("what"):
            why = f"{why} — {v['what']}"
        scenes.append({"s": c["s"], "e": c["e"], "kind": [label], "why": why, "sure": checked})
    return scenes


def find_voices(path, info, work, lines, cancel=None):
    """Speaker numbers and man/woman/child guesses for each line."""
    a = info["audio"]
    mix = ["-af", "pan=mono|c0=FC"] if a["channels"] >= 5 else ["-ac", "1"]
    r = cl.run([cl._tool("ffmpeg"), "-v", "error", "-i", path, "-map", f"0:{a['index']}", "-vn",
                "-sn", *mix, "-ar", str(ai.VSR), "-f", "f32le", "-"], capture_output=True)
    if r.returncode != 0 or not r.stdout:
        raise RuntimeError("couldn't read the sound")
    audio = np.frombuffer(r.stdout[: len(r.stdout) // 4 * 4], dtype=np.float32)
    if cancel and cancel():
        raise KeyboardInterrupt
    segs = None
    sfile = Path(work) / "speakers.json"
    if sfile.exists():
        segs = [tuple(x) for x in json.loads(sfile.read_text())]
    elif ai.speakers_ready():
        try:
            segs = ai.separate_speakers(audio)
            sfile.write_text(json.dumps(segs))
        except Exception:
            segs = None
    return ai.line_voices(audio, lines, load_tagger(), segs)


def find_lines(lines, o, have_ai, progress=None, cancel=None, genders=None, claude_found=None,
               examples=None):
    wanted = [k for k in LINE_KINDS if o[k]]
    if not wanted or not lines:
        return [], ""
    found, how = {}, "word lists"
    if claude_found is not None:
        found = {i: set(t) for i, t in claude_found.items()}
        how = cc.name()
    elif have_ai:
        try:
            found = ai.classify_dialogue(lines, wanted, progress, cancel, genders=genders,
                                         examples=examples)
            how = "the AI helper"
        except KeyboardInterrupt:
            raise
        except Exception:
            found = {}
    for i, l in enumerate(lines):
        for k in wanted:
            if LINE_WORDS[k].search(l["text"]):
                found.setdefault(i, set()).add(k)
    out = []
    for i in sorted(found):
        l = lines[i]
        toks = l["text"].split()
        normed = [cl.norm(t) for t in toks]
        for a_, b_, _ in cl.find_language(normed, list(cl.CATS)):
            for q in range(a_, b_):
                toks[q] = cl.mask(toks[q])
        out.append({"id": len(out) + 1, "s": round(l["s"], 2), "e": round(l["e"], 2),
                    "text": " ".join(toks), "plain": l["text"], "types": sorted(found[i]),
                    "mute": True, "idx": i})
    return out, how


def analyze(path, workdir, groups=("swearing", "mild", "deity"), opts=None, progress=None,
            log=print, cancel=None, model_dir=cl.DEFAULT_MODEL, threads=None, **legacy):
    """progress(fraction 0..1, message). Saves and returns workdir/analysis.json.
    opts: see DEFAULTS. (find_nudity / find_sex / find_violence still work.)"""
    o = full_opts(opts)
    for k_old, k_new in (("find_nudity", "nudity"), ("find_sex", "sex"), ("find_violence", "violence")):
        if k_old in legacy:
            o[k_new] = bool(legacy[k_old])
    nd = needs(o)
    work = Path(workdir)
    work.mkdir(parents=True, exist_ok=True)
    path = str(Path(path).resolve())
    say = progress or (lambda f, m: None)
    info = probe(path)
    dur = info["duration"] or 1.0
    cats = [c for g in groups for c in cl.GROUPS[g]]
    t_start = time.time()
    use_clip = bool(nd["clip"]) and ai.clip_ready()
    have_ai = nd["ai"] and ai.start_ollama(wait=20) and ai.choose_models()
    notes = []

    def eta(frac_done):
        el = time.time() - t_start
        if frac_done < 0.03 or el < 20:
            return "estimating time…"
        return f"about {max(1, el / frac_done * (1 - frac_done) / 60):.0f} min left"

    # how much of the progress bar each step gets
    steps = [("asr", 0.35), ("snd", 0.08 if nd["sound"] else 0),
             ("vis", (0.45 if use_clip else 0.3) if (nd["nudenet"] or use_clip) else 0),
             ("look", 0.08 if (have_ai and use_clip) else 0),
             ("lines", 0.12 if (have_ai and nd["lines"]) else 0),
             ("pics", 0.15 if (o.get("reader") in CLOUD and o.get("look", True)) else 0),
             ("end", 0.03)]
    tot = sum(w for _, w in steps)
    base, acc = {}, 0.0
    for k, w in steps:
        base[k] = (acc / tot, w / tot)
        acc += w

    def at(step, frac):
        b, w = base[step]
        return b + w * max(0.0, min(1.0, frac))

    tfile = work / "transcript.json"
    if tfile.exists():
        asr = json.loads(tfile.read_text())
    else:
        say(0.0, "Loading the listening model…")
        rec = load_recognizer(model_dir, threads)

        def p_asr(sec):
            f = at("asr", sec / dur)
            say(f, f"Listening to the dialogue · {eta(f)}")
        asr = transcribe(path, info, rec, p_asr, cancel)
        tfile.write_text(json.dumps(asr))
        del rec
    log(f"Heard {len(asr)} words")
    for w in asr:
        w["n"], w["part"] = cl.norm(w["t"]), 0
    asr_n = [w["n"] for w in asr]

    snd = None
    if nd["sound"]:
        sfile = work / "sounds.json"
        if sfile.exists():
            snd = json.loads(sfile.read_text())
        else:
            say(at("snd", 0), "Listening for fights, gunfire and other sounds…")
            tagger = load_tagger()

            def p_snd(sec):
                f = at("snd", sec / dur)
                say(f, f"Listening for fights, gunfire and other sounds · {eta(f)}")
            snd = sound_scan(path, info, tagger, p_snd, cancel)
            sfile.write_text(json.dumps(snd))

    vis = None
    if nd["nudenet"] or use_clip:
        vfile = work / "pictures.json"
        if vfile.exists():
            vis = json.loads(vfile.read_text())
            if vis.get("version", 1) < PICTURE_VERSION or (use_clip and not vis.get("clip")):
                vis = None
        if vis is None:
            what = "Watching the picture" + (" with the picture AI" if use_clip else " for nudity")
            say(at("vis", 0), what + "…")

            def p_vis(sec):
                f = at("vis", sec / dur)
                say(f, f"{what} · {eta(f)}")
            vis = visual_scan(path, vfile, use_clip, p_vis, cancel)
            notes += vis.get("notes", [])
    if nd["clip"] and not use_clip:
        notes.append("The picture AI isn't installed, so kissing, gore, smoking and the like "
                     "weren't checked by sight.")

    say(at("end", 0), "Finding language…")
    cues, sub_note = find_subtitles(path, info, work)
    if not cues and o.get("autosubs") and asr:
        dl = work / "downloaded.srt"
        miss = work / "no_subtitles_online.txt"
        text, why = None, ""
        if dl.exists():
            text, why = dl.read_text("utf8", "replace"), (work / "downloaded.txt").read_text("utf8")
        elif not (miss.exists() and time.time() - miss.stat().st_mtime < 3 * 86400):
            say(at("end", 0.1), "Looking for subtitles online…")
            try:
                text, why = download_subtitles(path, work, log)
            except Exception as ex:
                text, why = None, f"the subtitle finder ran into a problem ({str(ex)[:60]})"
            if text:
                dl.write_text(text, encoding="utf8")
                (work / "downloaded.txt").write_text(why, encoding="utf8")
            else:
                miss.write_text(why, encoding="utf8")
        else:
            why = miss.read_text("utf8", "replace")
        if text:
            synced, frac = sync_cues(parse_srt(text), asr)
            if synced:
                cues = synced
                sub_note = f"{why} and matched to the sound ({frac:.0%} of words lined up)"
            else:
                notes.append(f"Subtitles were found online but didn't match this video "
                             f"({frac:.0%} of words lined up), so they weren't used.")
        else:
            notes.append(f"No subtitles: {why}.")
    mutes = [{"s": asr[i]["s"], "e": asr[j - 1]["e"], "cat": cat, "src": "audio",
              "word": " ".join(cl.mask(asr[k]["t"]) for k in range(i, j)),
              "raw": " ".join(asr[k]["n"] for k in range(i, j)),
              "ctx": " ".join(asr[k]["t"] for k in range(max(0, i - 6), i))}
             for i, j, cat in cl.find_language(asr_n, cats)]
    if cues and cats:
        sw, sw_cue = [], []
        for ci, c in enumerate(cues):
            for w in spoken_words(c["text"]):
                if cl.norm(w):
                    sw.append(w)
                    sw_cue.append(ci)
        sn = [cl.norm(w) for w in sw]
        mapping = cl.align(sn, asr_n) if asr_n else [None] * len(sn)
        added = 0
        for i, j, cat in cl.find_language(sn, cats):
            t = cl.est_time(i, mapping, asr) if asr else None
            if t:
                s, e, exact = t[0], t[1], t[2]
                if j - i > 1:
                    t2 = cl.est_time(j - 1, mapping, asr)
                    if t2:
                        e = max(e, t2[1])
                src = "subtitles" if exact else "subtitles-estimated"
            else:
                # fall back on the subtitle's own timing: place the word by its
                # position in the line and mute generously around it
                c = cues[sw_cue[i]]
                words_in = [k for k, ci in enumerate(sw_cue) if ci == sw_cue[i]]
                frac = (words_in.index(i) + 0.5) / max(1, len(words_in))
                mid = c["s"] + (c["e"] - c["s"]) * frac
                s, e = max(c["s"], mid - 0.7), min(c["e"], mid + 0.7 + 0.3 * (j - i - 1))
                src = "subtitles-estimated"
            if any(m["s"] - 0.8 <= s <= m["e"] + 0.8 for m in mutes):
                continue
            mutes.append({"s": round(s, 3), "e": round(e, 3), "cat": cat, "src": src,
                          "word": " ".join(cl.mask(w) for w in sw[i:j]),
                          "raw": " ".join(sn[i:j]),
                          "ctx": " ".join(sw[max(0, i - 6):i])})
            added += 1
        sub_note = f"Checked against {sub_note}: caught {added} extra word(s)."
        log(sub_note)
    elif cats:
        sub_note = "No subtitles found, so language was found by listening only."
    mutes.sort(key=lambda m: m["s"])
    for m in mutes:
        m["s"], m["e"] = cl.snap_edges(path, m["s"], m["e"], wide=m["src"] != "audio")

    # picture AI candidates, double-checked by the AI helper when it's there
    cands = []
    if use_clip and vis and vis.get("clip"):
        cands = ai.clip_candidates(vis["clip"], nd["clip"], lum=vis.get("lum"), fps=vis["fps"])
        if have_ai and cands:
            say(at("look", 0), "Taking a closer look at the scenes found…")
            todo = sorted(cands, key=lambda c: -c["peak"])[:150]
            ff = cl._tool("ffmpeg")
            ai.second_look(todo, lambda c: ai.grab_frames(ff, path, c["frames"], cl.run),
                           lambda f: say(at("look", f), f"Taking a closer look at the scenes found · "
                                                        f"{eta(at('look', f))}"), cancel)

    # dialogue: sexual references, sleeping around, relationship talk
    lines = ai.dialogue_lines(cues, asr, spoken_words)
    genders = None
    title = guess_title(path)
    key = learn.show_key(title)
    examples = learn.examples(key)
    if o.get("reader") in CLOUD:
        cc.use(o["reader"])
    who = cc.name()
    use_claude = o.get("reader") in CLOUD and bool(nd["lines"]) and bool(lines)
    if (have_ai or use_claude) and nd["lines"] and lines:
        say(at("lines", 0), "Telling voices apart…")
        try:
            genders = find_voices(path, info, work, lines, cancel)
            # a name from the subtitles ("DEREK: ...") names that voice's other lines too
            named = {}
            for l, g in zip(lines, genders):
                if l.get("who") and g["spk"]:
                    named.setdefault(g["spk"], {}).setdefault(l["who"], 0)
                    named[g["spk"]][l["who"]] += 1
            for g in genders:
                if g["spk"] in named and len(named[g["spk"]]) == 1:
                    g["spk"] = next(iter(named[g["spk"]]))
            known = sum(1 for v in genders if v["g"] != "?")
            spk = len({v["spk"] for v in genders if v["spk"]})
            notes.append(f"Voices: {spk} speakers told apart; man/woman/child guessed for "
                         f"{known} of {len(lines)} lines.")
        except KeyboardInterrupt:
            raise
        except Exception as ex:
            genders = None
            notes.append(f"Voices couldn't be told apart this time ({str(ex)[:80]}).")
    claude_found, claude_scenes = None, []
    if use_claude:
        say(at("lines", 0.1), f"{who} is reading the dialogue…")
        try:
            claude_found, claude_scenes = cc.check_dialogue(
                lines, genders, [k for k in LINE_KINDS if o[k]], examples)
            for c in claude_scenes:          # talk spread over a few lines: mute those lines
                if c["type"] != "samesex":
                    for i in range(c["from"], c["to"] + 1):
                        claude_found.setdefault(i, set()).add(c["type"])
        except cc.ClaudeError as ex:
            claude_found = None
            notes.append(f"{who} couldn't read the dialogue this time: {ex}")
    line_mutes, line_how = find_lines(
        lines, o, have_ai and claude_found is None,
        lambda f: say(at("lines", 0.6 * f), f"Reading the dialogue · {eta(at('lines', 0.6 * f))}"),
        cancel, genders, claude_found, examples)
    flirts = []
    for c in claude_scenes:
        if c["type"] == "samesex":
            flirts.append({"s": lines[c["from"]]["s"], "e": lines[c["to"]]["e"], "between": "ss",
                           "what": c["why"] or "same-sex romance or flirting"})
    if have_ai and o["samesex"] and lines and claude_found is None:
        flirts = ai.romance_scenes(
            lines, genders,
            lambda f: say(at("lines", 0.6 + 0.4 * f), f"Reading each conversation · "
                                                     f"{eta(at('lines', 0.6 + 0.4 * f))}"), cancel)
    if nd["lines"]:
        notes.append(f"Dialogue was checked with {line_how}.")
    if nd["ai"] and not have_ai:
        notes.append("The AI helper wasn't running, so scenes weren't double-checked and "
                     "dialogue was checked with word lists only.")

    used = ["listening to the dialogue"]
    if snd:
        used.append("sound check")
    if vis:
        used.append("nudity check")
    if use_clip and vis and vis.get("clip"):
        used.append("picture AI")
    if have_ai:
        used.append("AI helper")
    notes.insert(0, "Checked with: " + ", ".join(used) + ".")
    say(at("end", 0.6), "Putting the scene list together…")
    nude, skin = nudity_scenes(vis) if vis else ([], [])
    scenes = []
    if (o["nudity"] or o["implied"]) and nude:
        if have_ai:                     # the AI on this PC: really shown, or only implied?
            say(at("end", 0.65), "Taking a closer look at the nudity found…")
            cands = [{"cat": "nudity", "s": sc["s"], "e": sc["e"],
                      "frames": [sc["s"] + (sc["e"] - sc["s"]) * (k + 1) / 5 for k in range(4)]}
                     for sc in nude]
            ff = cl._tool("ffmpeg")
            ai.second_look(cands, lambda c: ai.grab_frames(ff, path, c["frames"], cl.run),
                           None, cancel)
            kept, n_impl, n_none = [], 0, 0
            for sc, c in zip(nude, cands):
                v = c.get("verdict") or {}
                if v.get("error"):
                    kept.append(sc)
                    continue
                if v.get("level") == "implied":
                    n_impl += 1
                    if o["implied"]:
                        kept.append(dict(sc, kind=["Implied nudity"], sure=True,
                                         why=f"implied nudity — {v.get('what', '')}"))
                elif v.get("level") == "shown":
                    if o["nudity"]:
                        kept.append(dict(sc, sure=True, why=f"{sc['why']} — {v.get('what', '')}"))
                else:
                    n_none += 1
            if n_impl or n_none:
                notes.append(f"Nudity check: {n_none} false alarm(s) dropped, {n_impl} scene(s) "
                             "only implied nudity" + (" (listed as implied)" if o["implied"] else
                                                       " (dropped; implied nudity isn't ticked)") + ".")
            nude = kept
        elif not o["nudity"]:
            nude = []
        scenes += nude
    if o["violence"]:
        scenes += violence_scenes(snd, cues)
    if o["sex"]:
        scenes += sex_scenes(snd, cues, asr_n, asr, skin, nude)
    scenes += decide_picture_scenes(cands, o, have_ai)
    for f in flirts:
        if f["between"] in ("mm", "ff", "ss"):
            scenes.append({"s": max(0.0, f["s"] - 1.0), "e": f["e"] + 1.0,
                           "kind": ["Same-sex romance" + (f" · {WHO_LABEL[f['between']]}"
                                                          if f["between"] in WHO_LABEL else "")],
                           "why": f["what"] or "flirting or romantic interest", "sure": True})
    scenes = merge_scenes(scenes)
    for n, sc in enumerate(scenes, 1):
        sc["id"], sc["cut"] = n, sc.get("sure", True)
        sc["e"] = min(sc["e"], dur)
        sc["s"], sc["e"] = round(sc["s"], 2), round(sc["e"], 2)
        said = [w["t"] for w in asr if sc["s"] <= w["s"] <= sc["e"]]
        sc["said"] = " ".join(said[:80]) + (" …" if len(said) > 80 else "")
    if o.get("reader") in CLOUD and o.get("look", True) and dur > 5:
        say(at("pics", 0), f"{who} is looking through the whole picture…")
        try:
            scenes, pic_note = look_at_picture(
                path, work, dur, scenes, o, asr,
                lambda f, m: say(at("pics", f), f"{who} {m} · {eta(at('pics', f))}"), cancel)
            notes.append(pic_note)
        except cc.ClaudeError as ex:
            notes.append(f"{who} couldn't look at the picture this time: {ex}")
        except KeyboardInterrupt:
            raise
        except Exception as ex:
            notes.append(f"{who} couldn't look at the picture this time ({str(ex)[:80]}).")
    learned_lines, learned_notes = learn.apply(key, lines, line_mutes, scenes, mutes)
    for l in learned_lines:
        line_mutes.append({"id": len(line_mutes) + 1, "s": round(l["s"], 2),
                           "e": round(l["e"], 2), "text": l["text"], "plain": l["text"],
                           "types": ["learned" if l.get("learned_from") == "you" else "shared"],
                           "mute": True,
                           "idx": next(k for k, x in enumerate(lines)
                                       if x["s"] == l["s"] and x["text"] == l["text"])})
    line_mutes.sort(key=lambda l: l["s"])
    notes += learned_notes

    st = {"path": path, "info": info, "groups": list(groups), "mutes": mutes, "scenes": scenes,
          "lines": line_mutes, "cues": cues, "show": key,
          "dialogue": [{"s": round(l["s"], 2), "e": round(l["e"], 2), "text": l["text"],
                        "who": l.get("who", "")} for l in lines],
          "voices": genders, "reader": who if claude_found is not None else line_how,
          "reviewer": who if o.get("reader") in CLOUD else None,
          "sub_note": sub_note, "notes": notes,
          "asr": [[w["t"], round(w["s"], 2), round(w["e"], 2)] for w in asr],
          "duration": dur, "words": len(asr), "opts": o, "used_ai": have_ai,
          "used_clip": use_clip}
    # Claude's final review: everything above, judged together in context
    if o.get("reader") in CLOUD and (lines or scenes or mutes):
        say(at("end", 0.75), f"{who} is reviewing everything that was found…")
        try:
            claude_review(st)
        except cc.ClaudeError as ex:
            notes.append(f"{who} couldn't do the final review this time: {ex}")
        except Exception as ex:          # never lose the scan over the review
            notes.append(f"Claude's final review didn't work this time ({str(ex)[:80]}).")
    make_thumbs(path, st["scenes"], work)
    (work / "analysis.json").write_text(json.dumps(st, indent=1))
    say(1.0, "Done.")
    return st


def load_recognizer(model_dir=cl.DEFAULT_MODEL, threads=None):
    return cl.load_recognizer(model_dir, threads)


def make_thumbs(path, scenes, work):
    """Three heavily blurred stills per scene, so you can tell scenes apart
    without seeing anything you don't want to."""
    d = Path(work) / "thumbs"
    d.mkdir(exist_ok=True)
    for sc in scenes:
        sc["thumbs"] = []
        for k in range(3):
            t = sc["s"] + (sc["e"] - sc["s"]) * (k + 1) / 4
            out = d / f"{sc['id']}_{k}.png"
            r = cl.run([cl._tool("ffmpeg"), "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", str(path),
                        "-map", "0:v:0", "-frames:v", "1", "-vf",
                        "scale=24:-2,scale=180:-2:flags=bilinear,boxblur=6:2,format=rgb24", str(out)], capture_output=True)
            if r.returncode == 0 and out.exists():
                sc["thumbs"].append(str(out))


def make_preview(path, s, e, workdir):
    """A short copy of one scene to look at in your own video player."""
    out = Path(workdir) / f"preview_{int(s)}.mkv"
    if not out.exists():
        start = max(0.0, s - 2)
        r = cl.run([cl._tool("ffmpeg"), "-y", "-v", "error", "-ss", f"{start:.2f}", "-i", str(path),
                    "-t", f"{e - start + 1:.2f}", "-map", "0:v:0", "-map", "0:a:0?", "-c", "copy",
                    str(out)], capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError("Couldn't make the preview:\n" + r.stderr[-400:])
    return str(out)


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------
ENCODERS = [
    ("h264_nvenc", ["-preset", "p5", "-rc", "vbr", "-cq", "21", "-b:v", "0", "-pix_fmt", "yuv420p"]),
    ("h264_qsv", ["-global_quality", "22", "-preset", "medium", "-pix_fmt", "nv12"]),
    ("h264_amf", ["-quality", "quality", "-rc", "cqp", "-qp_i", "20", "-qp_p", "22", "-qp_b", "24",
                  "-pix_fmt", "yuv420p"]),
    ("libx264", ["-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p"]),
]


def working_encoders():
    """Hardware video encoders that actually work on this PC, fastest first;
    libx264 (always works, slower) last."""
    ok = []
    for name, args in ENCODERS[:-1]:
        r = cl.run([cl._tool("ffmpeg"), "-v", "error", "-f", "lavfi", "-i",
                    "color=c=black:s=320x240:d=0.3", "-c:v", name, *args, "-f", "null", "-"],
                   capture_output=True)
        if r.returncode == 0:
            ok.append((name, args))
    return ok + [ENCODERS[-1]]


def _ranges(rs, off):
    return "+".join(f"between(t,{s + off:.3f},{e + off:.3f})" for s, e in rs)


def _removed_expr(cuts, off):
    return "+".join(f"gte(T,{e + off:.3f})*{e - s:.3f}" for s, e in cuts) or "0"


def _merge(rs):
    out = []
    for s, e in sorted(rs):
        if out and s <= out[-1][1]:
            out[-1][1] = max(out[-1][1], e)
        else:
            out.append([s, e])
    return [tuple(x) for x in out]


def _shift(t, cuts):
    removed = sum(min(e, t) - s for s, e in cuts if s < t)
    return max(0.0, t - removed)


def clean_cues(cues, cats, mutes, cuts, line_rs=()):
    """Subtitles for the clean copy: language blanked, muted lines and cut
    scenes dropped, times moved up to match."""
    out = []
    for c in cues:
        if any(s <= c["s"] and c["e"] <= e for s, e in cuts):
            continue
        dur_c = max(0.01, c["e"] - c["s"])
        if any(min(e, c["e"]) - max(s, c["s"]) >= 0.5 * dur_c for s, e in line_rs):
            continue
        s, e = c["s"], c["e"]
        for cs, ce in cuts:
            if cs < e and ce > s:          # partly inside a cut: keep the part outside
                if cs > s:
                    e = min(e, cs)
                else:
                    s = max(s, ce)
        if e - s < 0.3:
            continue
        text = c["text"]
        if cats:
            toks = re.split(r"(\s+)", text)
            idx = [k for k, tk in enumerate(toks) if tk.strip()]
            normed = [cl.norm(toks[k]) for k in idx]
            for i, j, _ in cl.find_language(normed, cats):
                for q in range(i, j):
                    tk = toks[idx[q]]
                    lead = re.match(r"^\W*", tk).group(0)
                    trail = re.search(r"\W*$", tk).group(0)
                    toks[idx[q]] = lead + "—" + trail
            text = "".join(toks)
        out.append({"s": _shift(s, cuts), "e": _shift(e, cuts), "text": text})
    return out


def _fmt_srt(t):
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms % 3600000 // 60000:02d}:{ms % 60000 // 1000:02d},{ms % 1000:03d}"


def write_srt(cues, dst):
    Path(dst).write_text("\n".join(f"{n}\n{_fmt_srt(c['s'])} --> {_fmt_srt(c['e'])}\n{c['text']}\n"
                                   for n, c in enumerate(cues, 1)), encoding="utf8")


def render(workdir, outdir, cuts=None, progress=None, log=print, cancel=None, encoders=None,
           lines=None, words=None):
    """Write the clean copy. cuts: list of {"s","e"} (default: scenes with cut=True).
    lines: dialogue lines to mute (default: lines with mute=True)."""
    work = Path(workdir)
    st = json.loads((work / "analysis.json").read_text())
    if cuts is None:
        cuts = [c for c in st["scenes"] if c.get("cut")]
    say = progress or (lambda f, m: None)
    info = st["info"]
    src = Path(st["path"])
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    dur = st["duration"]
    off = info.get("start", 0.0)
    if lines is None:
        lines = [l for l in st.get("lines", []) if l.get("mute")]
    if words is not None:          # the swear words left ticked on the review page
        st["mutes"] = list(words)
    cut_rs = _merge((max(0.0, c["s"]), min(dur, c["e"])) for c in cuts)
    line_rs = _merge((l["s"], l["e"]) for l in lines)
    mute_rs = _merge([(m["s"], m["e"]) for m in st["mutes"]] + line_rs)
    reencode = bool(cut_rs)
    mp4 = reencode or src.suffix.lower() in (".mp4", ".m4v", ".mov")
    dst = out / f"{src.stem} (Clean){'.mp4' if mp4 else '.mkv'}"

    cats = [c for g in st["groups"] for c in cl.GROUPS[g]]
    subs = clean_cues(st["cues"], cats, mute_rs, cut_rs, line_rs) if st["cues"] else []
    srt = None
    if subs:
        srt = work / "clean.srt"
        write_srt(subs, srt)

    a = info["audio"]
    afilt = ["aresample"]   # copes with files whose speaker layout changes mid-stream
    if mute_rs:
        afilt.append(f"volume=volume=0:enable='{_ranges(mute_rs, off)}'")
    if cut_rs:
        afilt.append(f"aselect='not({_ranges(cut_rs, off)})',"
                     f"asetpts='PTS-({_removed_expr(cut_rs, off)})/TB'")
    (work / "afilter.txt").write_text(",".join(afilt))
    (work / "vfilter.txt").write_text(
        f"select='not({_ranges(cut_rs, off)})',setpts='PTS-({_removed_expr(cut_rs, off)})/TB'"
        if cut_rs else "null")
    abr = "448k" if a["channels"] > 2 else "192k"
    if a["bit_rate"]:
        abr = str(min(max(a["bit_rate"], 128000), 640000 if a["channels"] > 2 else 320000))

    encs = (encoders or working_encoders()) if reencode else [("copy", [])]
    expected = max(1.0, dur - sum(e - s for s, e in cut_rs))
    tmp = dst.with_name(dst.stem + ".partial" + dst.suffix)

    def build(vname, vargs, new_style):
        def fopt(kind):  # ffmpeg 7+ spells it "-/filter:a"; older builds "-filter_script:a"
            return f"-/filter:{kind}" if new_style else f"-filter_script:{kind}"
        cmd = [cl._tool("ffmpeg"), "-y", "-v", "error", "-nostats", "-progress", "pipe:1",
               "-i", str(src)]
        if srt:
            cmd += ["-i", str(srt)]
        cmd += ["-map", f"0:{info['video']['index']}", "-map", f"0:{a['index']}",
                "-disposition:v:0", "default", "-disposition:a:0", "default"]
        if srt:
            cmd += ["-map", "1:0", "-c:s", "mov_text" if mp4 else "srt",
                    "-metadata:s:s:0", "language=eng",
                    "-disposition:s:0", "0"]      # there if wanted, but off unless turned on
        ch = a["channels"]
        cmd += [fopt("a"), str(work / "afilter.txt"), "-c:a", "aac", "-b:a", abr,
                "-ac", str(ch if ch in (1, 2, 6, 8) else 2)]
        if reencode:
            cmd += [fopt("v"), str(work / "vfilter.txt"), "-c:v", vname, *vargs, "-fps_mode", "vfr"]
        else:
            cmd += ["-c:v", "copy"]
            if mp4 and info["video"]["codec"] == "hevc":
                cmd += ["-tag:v", "hvc1"]
        cmd += ["-map_metadata", "0", "-map_chapters", "-1" if reencode else "0"]
        if mp4:
            cmd += ["-movflags", "+faststart"]
        return cmd + [str(tmp)]

    def attempt(cmd, label):
        say(0.0, label + "…")
        errf = work / "render_err.txt"
        with open(errf, "w", encoding="utf8") as err:
            proc = cl.popen(cmd, stdout=subprocess.PIPE, stderr=err, text=True)
            t0 = time.time()
            try:
                for line in proc.stdout:
                    if cancel and cancel():
                        raise KeyboardInterrupt
                    if line.startswith("out_time_us="):
                        try:
                            sec = int(line.split("=")[1]) / 1e6
                        except ValueError:
                            continue
                        f = min(0.99, max(0.0, sec / expected))
                        el = time.time() - t0
                        left = f" · about {el / f * (1 - f) / 60:.0f} min left" if f > 0.03 and el > 15 else "…"
                        say(f, label + left)
                proc.wait()
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait()
        if proc.returncode == 0:
            os.replace(tmp, dst)
            return True, ""
        try:
            os.remove(tmp)
        except OSError:
            pass
        return False, errf.read_text("utf8", "replace")

    done, last_err = False, ""
    for vname, vargs in encs:
        label = "Saving the clean copy" + (" (using your graphics card)"
                                          if vname.endswith(("nvenc", "qsv", "amf")) else "")
        for new_style in (True, False):
            done, last_err = attempt(build(vname, vargs, new_style), label)
            if done or ("Unrecognized option" not in last_err and "Option not found" not in last_err):
                break
        if done:
            break
        log(f"{vname} didn't work, trying the next way: {last_err[-200:]}")
    if not done:
        raise RuntimeError(f"Couldn't save the clean copy of {src.name}:\n{last_err[-800:]}")

    # no separate .srt file next to the video: players show those automatically
    removed = sum(e - s for s, e in cut_rs)
    rep = [f"CleanView report — {src.name}", "=" * 40,
           f"{len(st['mutes'])} words/phrases muted, {len(lines)} lines muted, {len(cut_rs)} "
           f"scenes cut ({removed / 60:.1f} minutes removed)."]
    if st.get("sub_note"):
        rep.append(st["sub_note"])
    rep += st.get("notes", [])
    if info.get("audio_tracks", 1) > 1:
        rep.append("Only the main soundtrack was kept (other languages and commentary "
                   "weren't cleaned, so they were left out).")
    rep.append("")
    src_note = {"audio": "", "claude": f"   (only this word, per {st.get('reviewer') or 'the AI review'})",
                "claude-estimated": f"   (only this word, per {st.get('reviewer') or 'the AI review'})"}
    events = [(m["s"], f"muted  {m['word']}" + src_note.get(m.get("src"), "   (caught by subtitles)"))
              for m in st["mutes"]]
    events += [(l["s"], "muted line  (" + ", ".join(LINE_LABEL.get(t, t) for t in l["types"]) + ")")
               for l in lines]
    events += [(c["s"], f"CUT {c['e'] - c['s']:.0f} seconds  {' + '.join(c.get('kind') or ['scene'])}"
                        f"  ({c.get('why', '')})") for c in cuts]
    rep += [f"  {cl.fmt_t(t)}  {txt}" for t, txt in sorted(events)]
    (out / f"{src.stem} - CleanView report.txt").write_text("\n".join(rep) + "\n", encoding="utf8")
    say(1.0, "Saved.")
    log(f"Saved {dst}")
    return {"mutes": len(st["mutes"]) + len(lines), "cuts": len(cut_rs), "cut_minutes": removed / 60,
            "out": str(dst), "folder": str(out)}


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------
def _cli():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    an = sub.add_parser("analyze")
    an.add_argument("workdir")
    an.add_argument("video")
    an.add_argument("--groups", default="swearing,mild,deity")
    an.add_argument("--opts", default="{}", help='JSON, e.g. {"kiss_os": "passionate", "ai": false}')
    rn = sub.add_parser("render")
    rn.add_argument("workdir")
    rn.add_argument("outdir")
    vs = sub.add_parser("visualscan")
    vs.add_argument("video")
    vs.add_argument("out")
    vs.add_argument("--clip", action="store_true")
    a = ap.parse_args()
    if a.cmd == "visualscan":
        _visual_scan_here(a.video, a.out, a.clip)
    elif a.cmd == "analyze":
        st = analyze(a.video, a.workdir, [g for g in a.groups.split(",") if g], json.loads(a.opts),
                     progress=lambda f, m: print(f"[{f * 100:3.0f}%] {m}", flush=True))
        print(f"{st['words']} words; {len(st['mutes'])} to mute; {len(st['lines'])} lines; "
              f"{len(st['scenes'])} scenes flagged")
    else:
        print(render(a.workdir, a.outdir, progress=lambda f, m: print(f"[{f * 100:3.0f}%] {m}", flush=True)))


if __name__ == "__main__":
    _cli()
