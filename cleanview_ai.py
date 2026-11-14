"""
CleanView's AI helpers, all running on your own computer:

- CLIP (OpenAI's free image model) scores every frame against plain-English
  descriptions: kissing, gore, a gun pointed at someone, smoking, a couple in
  bed. It finds candidate scenes even when they make no sound.
- A local language-and-vision model run by Ollama (gemma3:4b) takes a second
  look at those candidates (who is kissing, light or passionate, is it really
  gore) and reads the dialogue for sexual references, sleeping around and
  relationship talk.

Every step is optional: if a model is missing or fails, CleanView carries on
without it.
"""
import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np

import cvlang    # the language being cleaned (1.18.80)

HERE = Path(__file__).resolve().parent


def counted(progress, f, a, z, total, what=""):
    """progress(f) as always, and progress(f, "21\u201340 of 95") when it takes the count, for
    the line under the progress bar (the owner, 2026-11-09, after a step sat unchanged for a
    long time in CleanRead: "is it frozen?"; CleanListen/CleanRead 1.17.10 do the same)."""
    if not progress:
        return
    n = f"{a:,} of {total:,}" if a >= z else f"{a:,}\u2013{z:,} of {total:,}"
    try:
        progress(f, f"{what} {n}" if what else n)
    except TypeError:
        progress(f)

CLIP_DIR = HERE / "models" / "clip-vit-base-patch32"
CLIP_BASE = "https://huggingface.co/Xenova/clip-vit-base-patch32/resolve/main/"
CLIP_FILES = {"vision_model_quantized.onnx": "onnx/vision_model_quantized.onnx",
              "text_model_quantized.onnx": "onnx/text_model_quantized.onnx",
              "tokenizer.json": "tokenizer.json"}
OLLAMA = os.environ.get("CLEANVIEW_OLLAMA", "http://127.0.0.1:11434")
# Newest first; an older one is used if the newer can't be downloaded or run.
# The picture model is qwen3-vl's "instruct" build (1.18.56, 2026-11-11; the owner: "Yes, build
# it"): plain "qwen3-vl:8b" is the thinking build, which ignores think=False and works through
# each question silently first (200-1,000 tokens for a 60-word answer), ~16 s a closer look on
# this PC, and 11 of 183 ran past the 4-minute limit with no answer (9 of 29 kisses). The
# instruct build took ~7 s, never timed out, and was as good or better on kisses, drugs (no
# drips and blood draws as "illegal drugs"), gestures and nudity; on gore, asked as a
# checklist (LOOK["gore"]), it got 29 of 30 clear-cut scenes right, the thinking build 28.
# Existing installs download it once on "Getting ready" (tools_missing: "newer AI models").
VISION_MODELS = [m for m in (os.environ.get("CLEANVIEW_VISION_MODEL"), "qwen3-vl:8b-instruct",
                             "qwen3-vl:8b", "qwen2.5vl:7b") if m]          # looks at pictures
TEXT_MODELS = [m for m in (os.environ.get("CLEANVIEW_TEXT_MODEL"), "qwen3:8b",
                           "qwen2.5:7b") if m]               # reads the dialogue
VISION_MODEL, TEXT_MODEL = VISION_MODELS[0], TEXT_MODELS[0]
MODEL = VISION_MODEL
OLLAMA_SETUP_URL = "https://ollama.com/download/OllamaSetup.exe"
_NOWIN = {"creationflags": 0x08000000} if os.name == "nt" else {}


# ---------------------------------------------------------------------------
# What CLIP looks for. Each frame is compared with all of these; a category
# "wins" a frame when its descriptions beat the everyday ones.
# ---------------------------------------------------------------------------
EVERYDAY = [
    "people talking", "a person standing", "a close-up of a face", "a landscape",
    "a room", "people walking", "a city street", "people eating at a table", "a car",
    "people hugging", "a group of people", "a person sitting", "an animal",
    "a person smiling", "a dark scene", "text on a screen", "a person running",
    "a person cooking", "children playing", "a person lying in bed asleep",
]
CLIP_CATS = {
    "kiss": ["two people kissing on the lips", "a couple kissing", "a passionate kiss"],
    "kiss_mf": ["a man and a woman kissing"],
    "kiss_mm": ["two men kissing"],
    "kiss_ff": ["two women kissing"],
    "bed": ["a couple in bed together", "a couple making out", "two people undressing each other"],
    "gore": ["a bloody wound", "gore and blood", "a dead body covered in blood",
             "a person being stabbed", "a person being shot with blood"],
    "fight": ["people fighting", "a person punching another person",
              "a person pointing a gun at someone", "a violent attack"],
    "smoking": ["a person smoking a cigarette", "a person smoking",
                "a person vaping an e-cigarette", "a person smoking a cigar or a pipe"],
    "drinking": ["a person drinking alcohol", "people drinking beer", "a glass of wine",
                 "people drinking at a bar"],
    "drugs": ["a person using drugs", "a person snorting cocaine", "a person injecting drugs",
              "a person smoking a marijuana joint", "a person smoking from a bong"],
    "immodest": ["a woman in a bikini", "a person in revealing underwear",
                 "a woman in a revealing low-cut outfit",
                 "a woman dancing provocatively in a revealing outfit",
                 "a stripper dancing on a pole"],
    "christmas": ["a decorated christmas tree", "santa claus", "christmas presents under a tree",
                  "christmas decorations and lights"],
    "halloween": ["a carved jack-o'-lantern pumpkin", "children trick-or-treating in halloween "
                  "costumes", "halloween decorations"],
    # only the candles: a birthday party, balloons or a cake on its own are fine
    "birthday": ["a birthday cake with lit candles", "blowing out birthday candles",
                 "candles on a cake"],
    "valentine": ["valentine's day cards and red hearts", "a heart-shaped box of chocolates",
                  "valentine decorations with cupid"],
    "easter": ["the easter bunny", "children hunting for easter eggs",
               "a basket of decorated easter eggs"],
    "stpatricks": ["a leprechaun", "st. patrick's day decorations with green shamrocks",
                   "a st. patrick's day parade", "a leprechaun's pot of gold"],
    "darkmagic": ["a witch casting an evil spell", "a dark occult ritual with a pentagram",
                  "a person summoning a demon", "a voodoo doll", "a fortune teller with a crystal "
                  "ball", "a seance with a ouija board", "a wizard casting a spell with a wand",
                  "a wizard in a pointed hat and robes"],
    "magic": ["glowing magic sparkles from a magic wand", "a person casting a spell with "
              "glowing magic from their hands", "a fairy doing magic"],
    "vampires": ["a vampire with fangs", "dracula in a black cape", "a werewolf",
                 "a person turning into a werewolf"],
    "gestures": ["a person giving the middle finger", "a person flipping someone off with "
                 "their middle finger", "a person making an obscene hand gesture",
                 "a person making a crude sexual gesture with their hands",
                 "a person thrusting their hips in a crude sexual way",
                 "a person grabbing their own crotch"],
    # the owner's hard rule (2026-11-13): "visuals of a condom needs to be removed"; under
    # the sexual references box, as the word is
    "condom": ["a condom", "a condom in its foil wrapper", "a box of condoms",
               "a hand holding a condom"],
}
# kiss_mf / kiss_mm / kiss_ff only decide *who*, never whether there is a kiss
WHO = ("kiss_mf", "kiss_mm", "kiss_ff")


def clip_prompts():
    names, texts = [], []
    for t in EVERYDAY:
        names.append("everyday")
        texts.append(f"a movie still of {t}")
    for cat, ts in CLIP_CATS.items():
        for t in ts:
            names.append(cat)
            texts.append(f"a movie still of {t}")
    return names, texts


def clip_signature():
    """A short fingerprint of what the picture AI looks for. Saved with each picture scan,
    so a scan made before the descriptions changed is done again."""
    import hashlib
    names, texts = clip_prompts()
    return hashlib.sha1("|".join(f"{n}:{t}" for n, t in zip(names, texts)).encode()).hexdigest()[:12]


def clip_ready():
    import importlib.util
    return (all((CLIP_DIR / f).exists() for f in CLIP_FILES)
            and importlib.util.find_spec("tokenizers") is not None
            and importlib.util.find_spec("onnxruntime") is not None)


def download(url, dest, progress=None, label=""):
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": "CleanView"})
    with urllib.request.urlopen(req, timeout=60) as r, open(tmp, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        got = 0
        while True:
            b = r.read(1 << 20)
            if not b:
                break
            f.write(b)
            got += len(b)
            if progress and total:
                progress(got / total, f"{label} {got / 1e6:.0f} of {total / 1e6:.0f} MB")
    os.replace(tmp, dest)


def install_clip(pip_python, progress=None):
    say = progress or (lambda f, m: None)
    import importlib.util
    if importlib.util.find_spec("tokenizers") is None:
        say(0.0, "Getting the picture AI's word reader…")
        r = subprocess.run([pip_python, "-m", "pip", "install", "--quiet",
                            "--disable-pip-version-check", "tokenizers"],
                           capture_output=True, text=True, **_NOWIN)
        if r.returncode != 0:
            raise RuntimeError("Couldn't download the picture AI.\n" + r.stderr[-500:])
        importlib.invalidate_caches()
    names = list(CLIP_FILES)
    for i, name in enumerate(names):
        if (CLIP_DIR / name).exists():
            continue
        download(CLIP_BASE + CLIP_FILES[name], CLIP_DIR / name,
                 lambda f, m, i=i: say((i + f) / len(names), "Getting the picture AI (one time) · " + m),
                 "")


# ---------------------------------------------------------------------------
# Image helpers (numpy only, no extra libraries)
# ---------------------------------------------------------------------------
def resize(img, w, h):
    """Bilinear resize of an HxWx3 uint8/float image."""
    H, W = img.shape[:2]
    if (W, H) == (w, h):
        return img.astype(np.float32)
    ys = (np.arange(h) + 0.5) * H / h - 0.5
    xs = (np.arange(w) + 0.5) * W / w - 0.5
    y0 = np.clip(np.floor(ys).astype(int), 0, H - 1)
    x0 = np.clip(np.floor(xs).astype(int), 0, W - 1)
    y1, x1 = np.clip(y0 + 1, 0, H - 1), np.clip(x0 + 1, 0, W - 1)
    wy = np.clip(ys - np.floor(ys), 0, 1)[:, None, None]
    wx = np.clip(xs - np.floor(xs), 0, 1)[None, :, None]
    a = img.astype(np.float32)
    top = a[y0][:, x0] * (1 - wx) + a[y0][:, x1] * wx
    bot = a[y1][:, x0] * (1 - wx) + a[y1][:, x1] * wx
    return top * (1 - wy) + bot * wy


LIFT_MOST = 4.0      # a dark frame is brightened at most this many times


def lift_levels(rgb):
    """(low, high): the 1st and 99th percentile of a frame's levels, high at most 255/4 above
    low, so brightening never multiplies noise more than LIFT_MOST times."""
    a = np.asarray(rgb)
    lo, hi = float(np.percentile(a, 1)), float(np.percentile(a, 99))
    return lo, lo + max(hi - lo, 8.0, 255.0 / LIFT_MOST)


def brighten(rgb):
    """A dark frame with its levels stretched to the full range (1.18.50, the owner: "the
    picture scanner skips dark frames, is that going to allow intimate scenes through?"):
    42% of the intimate scenes cut in 148 saved reviews were mostly too dark to judge, and
    brightened, 9 of 11 such scenes in 10 episodes were seen, with no false alarms."""
    lo, hi = lift_levels(rgb)
    a = np.asarray(rgb).astype(np.float32)
    return np.clip((a - lo) * (255.0 / (hi - lo)), 0, 255).astype(np.uint8)


def nudenet_input(rgb):
    """NudeNet's own preparation: pad to a square (bottom/right), shrink to
    320, BGR channel order, 0..1."""
    H, W = rgb.shape[:2]
    s = 320 / max(H, W)
    w, h = max(1, round(W * s)), max(1, round(H * s))
    out = np.zeros((320, 320, 3), np.float32)
    out[:h, :w] = resize(rgb, w, h)
    return out[:, :, ::-1].transpose(2, 0, 1) / 255.0


CLIP_MEAN = np.array([0.48145466, 0.4578275, 0.40821073], np.float32)
CLIP_STD = np.array([0.26862954, 0.26130258, 0.27577711], np.float32)


def clip_crops(rgb):
    """224x224 crops covering the whole width (wide movie frames get three)."""
    H, W = rgb.shape[:2]
    s = 224 / min(H, W)
    w, h = max(224, round(W * s)), max(224, round(H * s))
    img = resize(rgb, w, h)
    if w / h > 1.4:
        xs = [0, (w - 224) // 2, w - 224]
    else:
        xs = [(w - 224) // 2]
    y = (h - 224) // 2
    crops = [img[y:y + 224, x:x + 224] for x in xs]
    return [((c / 255.0 - CLIP_MEAN) / CLIP_STD).transpose(2, 0, 1) for c in crops]


class Clip:
    def __init__(self, ort, threads=4, spin=True):
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = threads
        if not spin:            # sharing the processor: idle threads wait instead of spinning
            opts.add_session_config_entry("session.intra_op.allow_spinning", "0")
        self.vis = ort.InferenceSession(str(CLIP_DIR / "vision_model_quantized.onnx"), opts,
                                        providers=["CPUExecutionProvider"])
        self.vin = self.vis.get_inputs()[0].name
        outs = [o.name for o in self.vis.get_outputs()]
        self.vout = "image_embeds" if "image_embeds" in outs else outs[0]
        self.names, texts = clip_prompts()
        self.text = self._text_embeds(ort, texts, opts)

    def _text_embeds(self, ort, texts, opts):
        key = hashlib.sha1("\n".join(texts).encode()).hexdigest()[:12]
        cache = CLIP_DIR / f"text_{key}.npy"
        if cache.exists():
            return np.load(cache)
        from tokenizers import Tokenizer
        tok = Tokenizer.from_file(str(CLIP_DIR / "tokenizer.json"))
        sess = ort.InferenceSession(str(CLIP_DIR / "text_model_quantized.onnx"), opts,
                                    providers=["CPUExecutionProvider"])
        ins = [i.name for i in sess.get_inputs()]
        outs = [o.name for o in sess.get_outputs()]
        oname = "text_embeds" if "text_embeds" in outs else outs[0]
        embs = []
        for t in texts:
            ids = np.array([tok.encode(t).ids[:77]], dtype=np.int64)
            feed = {"input_ids": ids}
            if "attention_mask" in ins:
                feed["attention_mask"] = np.ones_like(ids)
            e = sess.run([oname], feed)[0][0]
            embs.append(e / np.linalg.norm(e))
        arr = np.stack(embs).astype(np.float32)
        np.save(cache, arr)
        return arr

    def scores(self, rgb):
        """Per-category probability for one frame (max over its crops)."""
        crops = np.stack(clip_crops(rgb)).astype(np.float32)
        e = self.vis.run([self.vout], {self.vin: crops})[0]
        e = e / np.linalg.norm(e, axis=1, keepdims=True)
        logits = 100.0 * e @ self.text.T                       # (crops, prompts)
        out = {}
        main = [i for i, n in enumerate(self.names) if n not in WHO]
        lm = logits[:, main]
        p = np.exp(lm - lm.max(axis=1, keepdims=True))
        p /= p.sum(axis=1, keepdims=True)
        mnames = [self.names[i] for i in main]
        for cat in CLIP_CATS:
            if cat in WHO:
                continue
            idx = [k for k, n in enumerate(mnames) if n == cat]
            out[cat] = float(p[:, idx].sum(axis=1).max())
        # who is kissing: compare the three "who" descriptions on the crop
        # that looked most like a kiss
        best = int(p[:, [k for k, n in enumerate(mnames) if n == "kiss"]].sum(axis=1).argmax())
        who = [i for i, n in enumerate(self.names) if n in WHO]
        lw = logits[best, who]
        pw = np.exp(lw - lw.max())
        pw /= pw.sum()
        for k, i in enumerate(who):
            out[self.names[i]] = float(pw[k])
        return out


# Cartoon or live action (1.18.94; the owner, 2026-11-14: "can we teach when something is
# animated", then "build it"). Monsters University was cut for three "Christmas" scenes, a "St.
# Patrick's Day", "magic" for a glowing creature and four gunfire-like sound effects. A few
# stills of the whole video are asked which of these they look like; the descriptions aren't
# part of clip_prompts, so saved picture scans stay good.
CARTOON_TEXTS = ["an animated cartoon", "a hand-drawn cartoon", "a 3D computer-animated movie",
                 "an anime scene", "cartoon characters"]
LIVE_TEXTS = ["a live-action film with real actors", "real people in a real place",
              "a live-action TV show", "a photograph of real people"]


def cartoon_scores(clip, ort, frames):
    """How much each frame (an RGB array) looks animated rather than live action, 0..1."""
    texts = [f"a movie still of {t}" for t in CARTOON_TEXTS + LIVE_TEXTS]
    emb = clip._text_embeds(ort, texts, ort.SessionOptions())
    n_cartoon = len(CARTOON_TEXTS)
    out = []
    for rgb in frames:
        crops = np.stack(clip_crops(rgb)).astype(np.float32)
        e = clip.vis.run([clip.vout], {clip.vin: crops})[0]
        e = e / np.linalg.norm(e, axis=1, keepdims=True)
        lg = 100.0 * e @ emb.T
        p = np.exp(lg - lg.max(axis=1, keepdims=True))
        p /= p.sum(axis=1, keepdims=True)
        out.append(round(float(p[:, :n_cartoon].sum(axis=1).mean()), 3))
    return out


# Told to the closer look when the video is a cartoon
CARTOON_NOTE = (" These frames are from an animated cartoon. Bright colours, coloured lights, "
                "glowing things and fantasy creatures are everyday sights in cartoons, so only "
                "answer yes when what is asked about is clearly there: for a holiday, its own "
                "signs (a Christmas tree, Santa, presents or stockings; a leprechaun, shamrocks "
                "or a pot of gold; a jack-o'-lantern or trick-or-treaters); for magic, a spell, "
                "a wand or magic clearly being cast, not a creature or object that simply "
                "glows. Cartoon fighting and slapstick still count as fighting.")


# ---------------------------------------------------------------------------
# Turning CLIP scores into candidate scenes
# ---------------------------------------------------------------------------
THRESH = {"kiss": 0.6, "bed": 0.6, "gore": 0.6, "fight": 0.65, "smoking": 0.65,
          "drinking": 0.7, "drugs": 0.6, "immodest": 0.65, "christmas": 0.65,
          "halloween": 0.65, "birthday": 0.65, "valentine": 0.7, "gestures": 0.65,
          "easter": 0.65, "darkmagic": 0.65, "magic": 0.65, "stpatricks": 0.65,
          "vampires": 0.65,
          # lower: on Castle S1E2's saved stills the box of condoms Castle holds up scored
          # 0.58, and of 10,674 stills from nine other videos one scored 0.5 or more
          "condom": 0.5}
MIN_FRAMES = {"kiss": 3, "bed": 4, "gore": 2, "fight": 3, "smoking": 3, "drinking": 3,
              "drugs": 2, "immodest": 3, "christmas": 3, "halloween": 3, "birthday": 3,
              "valentine": 3, "easter": 3, "stpatricks": 3, "darkmagic": 2, "vampires": 2,
              "magic": 2,      # a spell's flash can be over in a couple of seconds
              "gestures": 1,   # seconds of hits a scene needs (a rude gesture is over in a second)
              "condom": 1}     # a wrapper is held up for a moment


def clip_candidates(clipdata, wanted, gap=4.0, pad=1.0, lum=None, fps=2.0, lifted=None):
    """Runs of frames where a wanted category wins. Returns
    [{"cat", "s", "e", "peak_t", "peak", "who": {...}, "frames": [...], "lifted": bool}].
    lifted: the frames too dark to judge that were brightened and checked (1.18.50)."""
    if not clipdata or not clipdata.get("t"):
        return []
    ts, rows = clipdata["t"], clipdata["scores"]
    lifted = set(lifted or ())
    if lum:   # leave out frames too dark or murky to judge (unless brightened)
        keep = [k for k, t in enumerate(ts) if int(round(t * fps)) >= len(lum)
                or int(round(t * fps)) in lifted
                or (lum[int(round(t * fps))][0] >= 40 and lum[int(round(t * fps))][1] >= 18)]
        ts, rows = [ts[k] for k in keep], [rows[k] for k in keep]
    out = []
    for cat in wanted:
        th = THRESH[cat]
        hits = [(t, r) for t, r in zip(ts, rows) if r.get(cat, 0) >= th]
        runs = []
        for t, r in hits:
            if runs and t - runs[-1][-1][0] <= gap:
                runs[-1].append((t, r))
            else:
                runs.append([(t, r)])
        for run in runs:
            if len(run) < MIN_FRAMES[cat] and max(r[cat] for _, r in run) < 0.9:
                continue   # too brief to be a real scene
            peak = max(run, key=lambda x: x[1][cat])
            who = {}
            if cat == "kiss":
                for w in WHO:
                    who[w] = float(np.mean([r[w] for _, r in run]))
            frames = [t for t, _ in sorted(run, key=lambda x: -x[1][cat])[:3]]
            out.append({"cat": cat, "s": max(0.0, run[0][0] - pad), "e": run[-1][0] + pad,
                        "peak_t": peak[0], "peak": round(peak[1][cat], 3), "who": who,
                        "frames": frames,
                        "lifted": any(int(round(t * fps)) in lifted for t in frames)})
    return sorted(out, key=lambda c: c["s"])


# ---------------------------------------------------------------------------
# Ollama: the local language-and-vision model
# ---------------------------------------------------------------------------
def _api(path, payload=None, timeout=10):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(OLLAMA + path, data=data,
                                 headers={"Content-Type": "application/json"})
    return urllib.request.urlopen(req, timeout=timeout)


def free_memory():
    """Ask Ollama to let go of the AI helper's models now instead of 5 minutes later: they hold
    several GB, and on a smaller PC the cloud review, the saving or the next video needs them
    (CleanListen, "The paging file is too small", 2026-11-04). Only models that are loaded are
    asked (asking about one that isn't could load it); a video still using one just loads it
    again. Never a problem of its own."""
    try:
        with _api("/api/ps", timeout=5) as r:
            loaded = {m.get("name") or m.get("model") for m in json.load(r).get("models", [])}
        for m in sorted(loaded & set(VISION_MODELS + TEXT_MODELS)):
            _api("/api/generate", {"model": m, "keep_alive": 0}, timeout=10).close()
    except Exception:
        pass


GPU_MOST = 0.5     # of the picture model on the graphics card (an 8 GB card holds ~76%)


def on_graphics_card(model=None):
    """True when Ollama has most of the picture model on the graphics card, so other work on
    the processor (telling voices apart) can run meanwhile. Loads the model to see, the same
    way chat() uses it (it's about to be used). No graphics card, or not knowing: False, and
    things run one after another as before (the owner, 2026-11-09: "if a gpu isnt available
    it will still perform all of the double checks"). A check that fails meanwhile is done
    again afterwards (cleanview.recheck_failed)."""
    model = model or VISION_MODEL
    try:
        _api("/api/generate", {"model": model, "options": {"num_ctx": NUM_CTX}},
             timeout=600).close()
        with _api("/api/ps", timeout=5) as r:
            for m in json.load(r).get("models", []):
                if model in (m.get("name"), m.get("model")):
                    size, vram = m.get("size") or 0, m.get("size_vram") or 0
                    return size > 0 and vram >= GPU_MOST * size
    except Exception:
        pass
    return False


def on_card_share(model):
    """How much of a model Ollama has loaded on the graphics card now (0-1), or None: for the
    scan's record (1.18.58). Doesn't load anything."""
    try:
        with _api("/api/ps", timeout=5) as r:
            for m in json.load(r).get("models", []):
                if model in (m.get("name"), m.get("model")) and m.get("size"):
                    return round((m.get("size_vram") or 0) / m["size"], 2)
    except Exception:
        pass
    return None


# Without a graphics card the AI helper runs on the processor, 7-8 times slower (2026-11-12,
# this PC with num_gpu 0: a closer look 76 s instead of 9 s, 100 lines read in 62 s instead of
# 9 s); a slower PC could reach the time limits. So each question gets SLOW_TIMES as long when
# the model is mostly off the card (the owner: "Yes, build it").
SLOW_TIMES = 3
_card_share = {}       # model -> share on the graphics card, once it's been loaded


def time_factor(model):
    """How much longer than usual each question may take: SLOW_TIMES when the model isn't
    mostly on the graphics card (or isn't loaded yet: the question also loads it), else 1."""
    share = _card_share.get(model)
    if share is None:
        share = on_card_share(model)
        if share is not None:
            _card_share[model] = share
    return 1 if share is not None and share >= GPU_MOST else SLOW_TIMES


def ollama_running():
    try:
        with _api("/api/tags", timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


def find_ollama():
    exe = shutil.which("ollama")
    if exe:
        return exe
    if os.name == "nt":
        for base in (os.environ.get("LOCALAPPDATA", ""), os.environ.get("ProgramFiles", "")):
            p = Path(base) / "Programs" / "Ollama" / "ollama.exe"
            if p.exists():
                return str(p)
            p = Path(base) / "Ollama" / "ollama.exe"
            if p.exists():
                return str(p)
    return None


def ollama_starting():
    """True when an Ollama server is already running (maybe still starting up: the window
    starts it in the background now, 1.18.54, and a video can ask for it meanwhile), so a
    second one isn't started. Not knowing: False."""
    if os.name != "nt":
        return False
    try:
        r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq ollama.exe", "/NH", "/FO", "CSV"],
                           capture_output=True, text=True, timeout=15, **_NOWIN)
        return '"ollama.exe"' in r.stdout.lower()
    except Exception:
        return False


def start_ollama(wait=60):
    if ollama_running():
        return True
    exe = find_ollama()
    if not exe:
        return False
    if not ollama_starting():
        subprocess.Popen([exe, "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         **_NOWIN)
    for _ in range(wait):
        if ollama_running():
            return True
        time.sleep(1)
    return ollama_running()


def _installed():
    with _api("/api/tags", timeout=5) as r:
        tags = json.loads(r.read())
    have = set()
    for m in tags.get("models", []):
        for k in ("name", "model"):
            if m.get(k):
                have.add(m[k])
                if m[k].endswith(":latest"):
                    have.add(m[k][:-7])
    return have


def _pick(models, have):
    return next((m for m in models if m in have or (m + ":latest") in have), None)


def choose_models():
    """Use the newest installed model of each kind. Returns True when both kinds are there."""
    global VISION_MODEL, TEXT_MODEL, MODEL
    try:
        have = _installed()
    except Exception:
        return False
    v, t = _pick(VISION_MODELS, have), _pick(TEXT_MODELS, have)
    if v:
        VISION_MODEL = MODEL = v
    if t:
        TEXT_MODEL = t
    return bool(v and t)


def model_ready(name=None):
    try:
        have = _installed()
    except Exception:
        return False
    if name:
        return _pick([name], have) is not None
    return _pick(VISION_MODELS, have) is not None and _pick(TEXT_MODELS, have) is not None


def install_ollama(progress=None):
    """Download and run Ollama's own installer (per-user, no admin)."""
    say = progress or (lambda f, m: None)
    if os.name != "nt":
        raise RuntimeError("Install Ollama from ollama.com, then try again.")
    tmp = Path(tempfile.gettempdir()) / "OllamaSetup.exe"
    download(OLLAMA_SETUP_URL, tmp, lambda f, m: say(f * 0.9, "Getting Ollama (one time) · " + m))
    say(0.92, "Installing Ollama…")
    subprocess.run([str(tmp), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-"], **_NOWIN)
    try:
        tmp.unlink()
    except OSError:
        pass
    if not start_ollama(wait=90):
        raise RuntimeError("Ollama installed but didn't start. Restart your PC and try again.")


def pull_model(name, progress=None, label="the AI model"):
    say = progress or (lambda f, m: None)
    with _api("/api/pull", {"model": name, "stream": True}, timeout=600) as r:
        for line in r:
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if d.get("error"):
                raise RuntimeError(f"Couldn't download {label}: " + d["error"])
            if d.get("total"):
                done = d.get("completed", 0)
                say(done / d["total"], f"Getting {label} (one time) · "
                    f"{done / 1e9:.1f} of {d['total'] / 1e9:.1f} GB")
    if not model_ready(name):
        raise RuntimeError(f"The download of {label} didn't finish. Try again.")


def ensure_ai(progress=None):
    """Make sure Ollama is installed and running, and has the newest models
    it can get (falling back to older ones if a newer download fails)."""
    say = progress or (lambda f, m: None)
    if not start_ollama():
        install_ollama(lambda f, m: say(0.2 * f, m))
    for k, (models, label) in enumerate(((VISION_MODELS, "the picture helper"),
                                         (TEXT_MODELS, "the dialogue reader"))):
        base, span = 0.2 + 0.4 * k, 0.4
        if model_ready(models[0]):
            continue
        err = None
        for m in models:
            try:
                pull_model(m, lambda f, msg: say(base + span * f, msg), label)
                err = None
                break
            except Exception as ex:   # e.g. an older Ollama that can't run the newest model
                err = ex
                if model_ready(m):
                    break
        if err and not any(model_ready(m) for m in models):
            raise err
    choose_models()


NUM_CTX = 8192     # the same everywhere, or Ollama loads the model again
APP_DATA = Path(os.environ.get("LOCALAPPDATA") or Path.home() / ".local" / "share") / "CleanView"
ANSWERS = APP_DATA / "ai_answers"
KEEP_ANSWERS = 20000         # the newest this many are kept (a few MB: a season or two)
_saves = [0]


def _answer_key(payload):
    """The same question to the same model: same words, pictures, answer form and settings."""
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf8")).hexdigest()[:32]


def _saved_answer(key):
    try:
        return json.loads((ANSWERS / f"{key}.json").read_text("utf8"))["answer"]
    except (OSError, ValueError, KeyError):
        return None


def _save_answer(key, answer):
    try:
        ANSWERS.mkdir(parents=True, exist_ok=True)
        tmp = ANSWERS / f"{key}.{os.getpid()}.{threading.get_ident()}.tmp"
        tmp.write_text(json.dumps({"answer": answer}), encoding="utf8")
        os.replace(tmp, ANSWERS / f"{key}.json")
        _saves[0] += 1
        if _saves[0] % 200 == 1:             # now and then: keep the newest
            old = sorted(ANSWERS.glob("*.json"), key=lambda f: f.stat().st_mtime)
            for f in old[:-KEEP_ANSWERS]:
                f.unlink()
    except OSError:
        pass


def chat(prompt, images=None, schema=None, timeout=300, model=None):
    """One question to the AI helper on this PC. The same question gets the same answer as
    last time (kept in ai_answers): a stopped or cancelled run picks up where it left off
    instead of asking everything again, and the same episode comes out the same each run
    (the owner, 2026-11-09, after CleanRead did the same in CleanListen 1.17.15: "Yes, add
    it"). Only an identical question counts: same model, words, stills, answer form and
    settings. Answers that went wrong are never kept."""
    if not images:                    # a question about dialogue: say what language it's in
        prompt += cvlang.reader_note(cvlang.LANG)
    msg = {"role": "user", "content": prompt}
    if images:
        msg["images"] = images
    model = model or (VISION_MODEL if images else TEXT_MODEL)
    payload = {"model": model, "messages": [msg], "stream": False,
               "options": {"temperature": 0, "num_ctx": NUM_CTX}}
    if schema:
        payload["format"] = schema
    key = _answer_key(payload)
    saved = _saved_answer(key)
    if saved is not None:
        return saved
    answer = _chat_now(payload, model, timeout * time_factor(model))
    _save_answer(key, answer)
    return answer


def _chat_now(payload, model, timeout):
    if model.startswith("qwen3"):
        payload["think"] = False      # answer directly; much faster
    try:
        with _api("/api/chat", payload, timeout=timeout) as r:
            d = json.loads(r.read())
    except urllib.error.HTTPError as ex:
        if "think" not in payload or ex.code != 400:
            raise
        payload.pop("think")          # an Ollama too old for that switch
        with _api("/api/chat", payload, timeout=timeout) as r:
            d = json.loads(r.read())
    text = (d.get("message") or {}).get("content", "")
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("no JSON in reply")
    return json.loads(m.group(0))


# ---------------------------------------------------------------------------
# Second look at picture candidates
# ---------------------------------------------------------------------------
def grab_frames(ffmpeg, path, times, run, lift=False):
    """Stills for the AI helper, as JPEG (base64). lift: brightened the way the scanner
    brightened them, for a scene found in a dark stretch (1.18.50)."""
    out = []
    for t in times:
        vf = "scale=640:-2"
        at = ["-ss", f"{max(0, t):.2f}", "-i", str(path), "-map", "0:v:0", "-frames:v", "1"]
        if lift:
            r = run([ffmpeg, "-v", "error", *at, "-vf", "scale=160:-2,format=rgb24",
                     "-f", "rawvideo", "-"], capture_output=True)
            if r.returncode == 0 and len(r.stdout) >= 160 * 3:
                px = np.frombuffer(r.stdout, dtype=np.uint8)
                lo, hi = lift_levels(px)
                a, b = lo / 255, min(1.0, hi / 255)
                vf += (f",colorlevels=rimin={a:.4f}:gimin={a:.4f}:bimin={a:.4f}"
                       f":rimax={b:.4f}:gimax={b:.4f}:bimax={b:.4f}")
        r = run([ffmpeg, "-v", "error", *at, "-vf", vf, "-f", "image2", "-c:v", "mjpeg",
                 "-q:v", "4", "-"], capture_output=True)
        if r.returncode == 0 and r.stdout:
            out.append(base64.b64encode(r.stdout).decode())
    return out


# What the gore checklist offers; the inside of a body is Gore, blood alone Graphic, the
# rest nothing (VidAngel's levels: crime-scene blood is Graphic, insides on the outside Gore).
GORE_SEEN = ["blood", "a bloody wound or cut", "open surgery with the inside of the body showing",
             "organs or entrails", "brain", "bone showing", "a severed or mangled body part",
             "a bruise, rash or red mark", "stitches or a closed scar", "none of these"]
GORE_INSIDE = set(GORE_SEEN[2:7])
GORE_BLOOD = set(GORE_SEEN[:2])


def gore_level(answer):
    """"gore", "graphic" or "none" from the checklist (or an older "level" answer)."""
    if "visible" in answer:
        seen = set(answer.get("visible") or [])
        return "gore" if seen & GORE_INSIDE else "graphic" if seen & GORE_BLOOD else "none"
    return {"insides": "gore", "blood": "graphic"}.get(answer.get("level"), "none")


# Medical gore is its own filter (1.18.62, the owner: "a lot of the gore that gets flagged is
# medical"; autopsies too, which only adults keep): the same look says where it is.
MEDICAL_ASK = ("Also answer \"medical\": true if it is in a medical setting: an operating room, "
               "a hospital, an ambulance or doctor's office, a morgue or an autopsy table, or a "
               "doctor, nurse or medic treating, stitching or examining a wound (people in "
               "scrubs, surgical gloves or masks). False for a crime scene, a fight or an "
               "attack, even with police or medics standing by.")


PREFACE = ("These are a few frames from one moment of a TV show or movie. First describe in "
           "one short sentence what you can actually see. If the frames are dark, blurry or "
           "unclear, say so. Then answer the question. Answer yes only if you can clearly see "
           "it in the frames; if you are not sure, answer no. ")
_YES = {"type": "object", "properties": {"see": {"type": "string"}, "yes": {"type": "boolean"}},
        "required": ["see", "yes"]}
# Long hair alone isn't a woman (1.18.96; the owner, 2026-11-14: "one thing clean view
# struggles with is men with long hair. it says same sex when they are with women", "i mean long
# hair in general"; Selena's two kisses with Chris were "two women")
WHO_HOW = (" Long hair alone does not make someone a woman: many men have long hair. Look at "
           "the face (a beard, stubble, the jaw, the brow), the build, the chest and the "
           "clothes. If you can't tell whether one of them is a man or a woman, answer unclear.")
LOOK = {
    "kiss": ("Question: are two people kissing on the lips? If yes, who is kissing (a man and a "
             "woman, two men, two women), and is it a light kiss (a short peck) or a passionate "
             "one (long, open-mouthed, making out)? A kiss on the cheek, a hug, or faces close "
             "together while talking is NOT kissing." + WHO_HOW,
             {"type": "object", "properties": {
                 "see": {"type": "string"},
                 "kissing": {"type": "boolean"},
                 "who": {"type": "string", "enum": ["man and woman", "two men", "two women",
                                                    "unclear"]},
                 "level": {"type": "string", "enum": ["light", "passionate", "none"]}},
              "required": ["see", "kissing", "who", "level"]}),
    "bed": ("Question: is something sexual happening (sex, even with clothes on; making out in "
            "bed; undressing each other; oral sex, such as a head moving at someone's lap or "
            "under the covers below someone's waist; a hand at or inside someone's crotch, "
            "pants or skirt)? Who is the couple (a man and a woman, two men, two women)? Two "
            "people only sitting or lying in bed together talking or sleeping, or someone "
            "alone in bed, is NOT." + WHO_HOW,
            {"type": "object", "properties": {
                "see": {"type": "string"},
                "intimate": {"type": "boolean"},
                "who": {"type": "string", "enum": ["man and woman", "two men", "two women",
                                                   "unclear"]}},
             "required": ["see", "intimate", "who"]}),
    # a checklist (1.18.56): asked "insides, blood or none?", the instruct build answered
    # "blood" even for "an open chest cavity" or "exposed brain tissue" (18 of 39 right);
    # ticking what it sees, with CleanView deciding the level (gore_level), 33 of 39
    "gore": ("Question: which of these can you see in the frames? Tick every one that is "
             "there: " + "; ".join(GORE_SEEN) + ". Surgery where the body is opened up counts "
             "as \"open surgery with the inside of the body showing\" even if it is mostly "
             "blood and drapes. A stump where a limb was cut off counts as \"a severed or "
             "mangled body part\". A bruise, rash or red skin is not blood. Not blood either: a "
             "dark red object, raw meat when cooking. " + MEDICAL_ASK,
             {"type": "object", "properties": {
                 "see": {"type": "string"},
                 "visible": {"type": "array", "items": {"type": "string", "enum": GORE_SEEN}},
                 "medical": {"type": "boolean"}},
              "required": ["see", "visible", "medical"]}),
    "fight": ("Question: are people clearly fighting, hitting, shooting, or threatening someone "
              "with a weapon? People talking, running, or a police officer simply holding a gun "
              "at their side is NOT. If it is violent, is it a fight between people who can "
              "fight back (\"combat\"), or done to someone helpless: torture, an execution, "
              "cruelty, abuse (\"helpless\")?",
              {"type": "object", "properties": {
                  "see": {"type": "string"},
                  "violent": {"type": "boolean"},
                  "kind": {"type": "string", "enum": ["combat", "helpless", "none"]}},
               "required": ["see", "violent", "kind"]}),
    "smoking": ("Question: is someone smoking (cigarette, cigar, vape, pipe)?",
                {"type": "object", "properties": {"see": {"type": "string"},
                                                  "yes": {"type": "boolean"}},
                 "required": ["see", "yes"]}),
    "drinking": ("Question: is someone drinking alcohol (beer, wine, liquor), or clearly drunk?",
                 {"type": "object", "properties": {"see": {"type": "string"},
                                                   "yes": {"type": "boolean"}},
                  "required": ["see", "yes"]}),
    # a medical needle is Medical, never drugs (1.18.63, the owner: "be sure drugs are
    # separated")
    "drugs": ("Question: is someone using illegal drugs (smoking a joint, snorting, injecting "
              "drugs), or is a medical needle going into someone's skin (a doctor, nurse or "
              "dentist giving a shot, a blood draw, an IV needle being put into an arm, a needle "
              "stitching a wound, someone giving themselves insulin)? Someone shooting up drugs "
              "(a tourniquet and a spoon, a dirty needle in a bathroom or an alley) is "
              "\"drugs\". A needle going in for a medical reason is \"medical\". An IV bag or "
              "drip hanging up, tubes already taped in place, vials, blood tubes, pills, a lab, "
              "a pharmacy, or a syringe that isn't going into anyone is \"neither\".",
              {"type": "object", "properties": {
                  "see": {"type": "string"},
                  "kind": {"type": "string", "enum": ["drugs", "medical", "neither"]}},
               "required": ["see", "kind"]}),
    "nudity": ("Question: is anyone naked? Answer \"shown\" only if bare breasts, bare buttocks "
               "or genitals are clearly visible. Answer \"implied\" if someone is undressed but "
               "covered: under a sheet or blanket, in a towel, a bare back or shoulders, a shower "
               "shown from the shoulders up, or private parts hidden by an object or the "
               "camera angle. Answer \"none\" if everyone is dressed, someone is alone in a bath with only "
               "their shoulders above the water or bubbles, or it's a shirtless man, "
               "swimwear, or just skin-toned objects.",
               {"type": "object", "properties": {
                   "see": {"type": "string"},
                   "nudity": {"type": "string", "enum": ["shown", "implied", "none"]}},
                "required": ["see", "nudity"]}),
    "immodest": ("Question: is someone dressed immodestly (swimsuit, underwear, lingerie, very "
                 "revealing clothes), or dancing in a sexual way (stripping, pole dancing, "
                 "grinding)?",
                 {"type": "object", "properties": {"see": {"type": "string"},
                                                   "yes": {"type": "boolean"}},
                  "required": ["see", "yes"]}),
    "christmas": ("Question: is something about Christmas shown: Santa Claus, a decorated "
                  "Christmas tree, Christmas presents, stockings or Christmas decorations? Snow "
                  "or an ordinary winter scene is NOT, and nor is something that is only red "
                  "and green (a toy, clothes).", _YES),
    "halloween": ("Question: is something about Halloween shown: children trick-or-treating, "
                  "Halloween costumes, a carved jack-o'-lantern or Halloween decorations? A "
                  "plain pumpkin, or a fantasy story's own witches or monsters, is NOT.", _YES),
    "birthday": ("Question: are there candles on a cake (lit, or someone blowing them out)? A "
                 "birthday party, balloons, presents or a cake with no candles is NOT.", _YES),
    "valentine": ("Question: is something about Valentine's Day shown: valentine cards, "
                  "Cupid, or hearts used as Valentine decorations? A heart shape on its own (a "
                  "logo, a title card or opening credits, a pattern on fabric, a wall or a "
                  "pillow) is NOT.", _YES),
    "easter": ("Question: is something about Easter shown: the Easter bunny, an Easter egg "
               "hunt, decorated Easter eggs or Easter baskets? An ordinary rabbit or egg, or a cartoon "
               "rabbit with no basket, eggs or other Easter signs (Bambi's Thumper), is NOT.",
               _YES),
    "stpatricks": ("Question: is something about St. Patrick's Day shown: a leprechaun, a pot of "
                   "gold, shamrock decorations, or people dressed up in green for St. Patrick's "
                   "Day or its parade? Ordinary green clothes, a clover field or a rainbow alone "
                   "is NOT.", _YES),
    "darkmagic": ("Question: is dark magic or the occult shown: witchcraft, a witch or wizard "
                  "doing magic, a curse or evil spell being cast, an occult ritual (a pentagram, "
                  "summoning a demon or the dead, a seance, a Ouija board), a voodoo doll, or "
                  "fortune telling (a crystal ball, tarot cards, palm reading)? A Halloween "
                  "costume or decoration is NOT.", _YES),
    "magic": ("Question: is magic being done: someone casting a spell, a magic wand at work, "
              "glowing magic, a magic potion working, a fairy or genie doing magic? A stage "
              "magician's trick (cards, a rabbit from a hat), fireworks, a science-fiction "
              "gadget, ray gun or machine, or a film company's logo is NOT.", _YES),
    "vampires": ("Question: is a vampire or a werewolf shown: someone with vampire fangs or a "
                 "Dracula cape, drinking blood, turning into a bat; a wolf-man, or someone "
                 "changing into a wolf? A real bat, or an ordinary wolf or dog, is NOT.", _YES),
    "gestures": ("Question: is someone making a rude or sexual gesture? That means raising "
                 "the middle finger at someone (flipping them off), or a crude sexual motion: "
                 "a hand or finger gesture that mimics sex or oral sex, thrusting the hips "
                 "suggestively, or grabbing their own crotch. Waving, pointing, a thumbs up, a "
                 "peace sign, counting on fingers, dancing or ordinary exercise is NOT.", _YES),
    "condom": ("Question: is a condom shown? That means the condom itself, a condom in its "
               "small square foil wrapper, or a box or packet of condoms (in a hand, on a "
               "table, in a drawer, a wallet or a shop). A balloon, a rubber glove, a sweet, "
               "gum or tea-bag wrapper, a sauce packet, a pill packet or another small packet "
               "is NOT.", _YES),
}
CLEAR_ASK = (" Also answer \"clear\": false only if the frames themselves are too dark, blurry "
             "or unclear to judge (dark hair, dark clothes or a dark room you can still see "
             "into are fine).")
# Only for a model that skips "clear": phrases about the frames themselves, so a "woman with
# dark hair" or "a dark parking garage" isn't taken as the model being unable to see.
UNCLEAR = re.compile(r"\b(too (dark|blurr?y)|blurr?y|unclear|"
                     r"(image|frame|picture|shot|scene)s? (is|are) (very |quite |too )?(dark|blurr?y)|"
                     r"(can't|cannot|can not|hard to|difficult to) (see|tell|make out)|"
                     r"not (clearly )?visible)\b", re.I)
WHO_KEY = {"man and woman": "mf", "two men": "mm", "two women": "ff"}


def family_said(notes):
    """What they told the chat to keep in mind (learn.notes), for the picture check: Jason
    (2026-11-04) corrects scenes in the chat to teach the AI on this PC."""
    if not notes:
        return ""
    return (" The family has told CleanView to keep these in mind (only some may be about "
            "what's on screen; follow the ones that are): " +
            " ".join(f"- {t.strip()}" for t in notes[:20]))


def second_look(cands, frames_for, progress=None, cancel=None, notes=None, cartoon=False):
    """Ask the local model about each candidate. Adds "verdict" to each:
    {"keep": bool, "who": "mf|mm|ff|?", "level": "light|passionate|?", "what": str}.
    notes: what they told the chat to keep in mind (followed here too). cartoon: the video
    is animated (CARTOON_NOTE)."""
    said = family_said(notes) + (CARTOON_NOTE if cartoon else "")
    for n, c in enumerate(cands):
        if cancel and cancel():
            raise KeyboardInterrupt
        counted(progress, n / max(1, len(cands)), n + 1, n + 1, len(cands))
        q, schema = LOOK[c["cat"]]
        schema = dict(schema, properties=dict(schema["properties"], clear={"type": "boolean"}),
                      required=schema["required"] + ["clear"])
        imgs = frames_for(c)
        if not imgs:
            c["verdict"] = {"keep": True, "who": "?", "level": "?", "what": "", "error": "no frames"}
            continue
        try:
            a = chat(PREFACE + q + said + CLEAR_ASK + " Answer in JSON.", imgs, schema,
                     timeout=240)
        except Exception as ex:
            c["verdict"] = {"keep": True, "who": "?", "level": "?", "what": "", "error": str(ex)}
            continue
        see = str(a.get("see", "")).strip()
        v = {"keep": True, "who": "?", "level": "?", "what": see[:90]}
        if c["cat"] == "kiss":
            v["keep"] = a.get("kissing") is True and a.get("level") != "none"
            v["who"] = WHO_KEY.get(a.get("who"), "?")
            v["level"] = a.get("level") if a.get("level") in ("light", "passionate") else "?"
        elif c["cat"] == "bed":
            v["keep"] = bool(a.get("intimate"))
            v["who"] = WHO_KEY.get(a.get("who"), "?")
        elif c["cat"] == "gore":
            v["level"] = gore_level(a)
            v["keep"] = v["level"] != "none"
            v["medical"] = a.get("medical") is True
        elif c["cat"] == "fight":
            v["keep"] = bool(a.get("violent"))
            v["level"] = "disturbing" if a.get("kind") == "helpless" else "combat"
        elif c["cat"] == "nudity":
            v["level"] = a.get("nudity") if a.get("nudity") in ("shown", "implied") else "none"
            v["keep"] = v["level"] != "none"
        elif c["cat"] == "drugs":
            v["keep"] = a.get("kind") in ("drugs", "medical")
            v["medical"] = a.get("kind") == "medical"
        else:
            v["keep"] = bool(a.get("yes"))
        clear = a.get("clear")
        if clear is False or (clear is None and UNCLEAR.search(see)):
            # the model itself says it can't see clearly: if it still saw something, offer
            # the scene unticked rather than throwing it away
            v["unclear"] = True
        c["verdict"] = v
    if progress:
        progress(1.0)
    return cands


# ---------------------------------------------------------------------------
# Reading the dialogue
# ---------------------------------------------------------------------------
NOT_CASE = ("a coroner's, medical examiner's, doctor's or detective's case talk about a body or "
            "a crime (findings, rape or sexual assault, sex offenders, evidence), which is a "
            "separate choice; but explicit detail in it (vaginal or anal injuries, tearing, "
            "penetration) always counts")
LINE_TYPES = {
    "sexref": ("talks about sex or sexual body parts, or makes a sexual joke or sexual double "
               "meaning, including oral sex or touching someone's private parts, bragging "
               "about sleeping with women ('twelve for twelve with the models'), brothel talk, "
               "and lines like 'be gentle, it's my first time' or 'what was his name?' to "
               "the woman he woke up with, and talk of sex drugs: pills for sex or erections (Viagra, Cialis, 'the little blue pill', erectile dysfunction), aphrodisiacs ('Spanish fly', a love potion meant to make someone want sex) and drugging someone to have sex with them. "
               "NOT: swearing, insults, lying, drinking, other drugs, violence, crime, threats, "
               "compliments, ordinary love and affection, pregnancy or babies, 'sex' meaning men or "
               "women ('the fair sex', 'others of my sex'), 'make love to' in an old film "
               "(courting), a polite 'it's a pleasure', a body part in a threat, "
               "'sleeps with the pigs' meaning where someone sleeps, " + NOT_CASE + ""),
    "casual": ("says or clearly implies someone had, or wants, sex outside a committed "
               "relationship: hooking up, a one-night stand, an affair, cheating, sleeping with "
               "someone, sleeping around; also talk of cheating on a partner, even with nothing sexual "
               "said (an engaged or married person kissing someone else), and planning an affair "
               "('if we're going to have an affair'). Only the lines about it, not alibis or "
               "small talk around it. NOT: dating, going out, "
               "setting people up, dating apps, being in love, marriage, family, drinking together"),
    "samesex": ("clearly refers to romance, dating, attraction or a sexual relationship between "
                "two men or two women (for example a man saying 'my boyfriend', 'her wife', "
                "'he's gay'). NOT: a man and a woman together (dating, engaged or married), friends, "
                "coworkers, police or business partners, family, 'gay' "
                "meaning happy or cheerful (an old song, 'gay apparel')"),
    "oppsex": ("says an unmarried man and woman live together or sleep together, now or in "
               "the past ('my girlfriend kicked me out'). NOT: married couples, dating, "
               "roommates, family, co-workers sharing a room for work"),
    "forensic": ("graphic talk about a body or a victim by a coroner, medical examiner, doctor or detective: wounds and injuries, blood, organs, cause or time of death, an autopsy or what was done to the body, and case talk about rape or sexual assault, sex offenders or sexual evidence (condoms, DNA). NOT: everyday medical talk with nothing graphic (a diagnosis, a prescription, 'he'll be fine', 'she's stable'), the people's own lines about their lives, a suspect's alibi"),
    "crude": ("crude humor: jokes or talk about bodily functions, bathroom or toilet humor, "
              "gross-out jokes, crude jokes about body parts. NOT: ordinary jokes, sarcasm, "
              "plain insults"),
    "disrespect": ("a child or teen being bratty or disrespectful to a parent, teacher or "
                   "other grown-up: talking back, sassing, mocking or insulting them, refusing "
                   "to do what they're told, openly disobeying, sneaking out or lying to them. "
                   "NOT: grown-ups disagreeing with each other, a child politely saying no or "
                   "standing up to something wrong, friendly teasing, a child asking why"),
    "bullying": ("bullying: mocking, taunting or demeaning someone, cruel name-calling, picking "
                 "on someone weaker, trying to humiliate them, mocking someone's catchphrase, "
                 "a grown-up putting a child down. It must be meant to hurt. NOT: simply "
                 "disagreeing ('you're wrong'), ordinary arguments, a married couple arguing, "
                 "police questioning or warnings, friendly teasing between friends, a song or "
                 "grumble about someone who isn't there, a rude customer, a line whose "
                 "only problem is a swear word or one rude word ('you idiot!')"),
    "religion": ("talks about religion or faith: God, Jesus, prayer or praying, church, the "
                 "Bible, heaven or hell as places, angels, sin, or the beliefs, practices, "
                 "clergy or holidays of any religion. NOT: 'oh my God' or 'Jesus' said as a "
                 "swear or exclamation ('thank God', 'dear God', 'go to hell'), idioms ('a match "
                 "made in heaven', 'get to the church on time'), 'bless you' after a sneeze, "
                 "'thank heavens', a passing 'God bless you' or 'Merry Christmas', a "
                 "character's name. Any religion counts, including voodoo or Vodun rituals"),
    "christmas": ("talks about Christmas: Santa, Christmas trees, presents, carols, Christmas "
                  "Eve or Day, 'Merry Christmas'. NOT: a place named Santa something (Santa "
                  "Anita, Santa Monica) or Christmas Island, winter or snow alone, the word "
                  "'present' meaning now or here"),
    "halloween": ("talks about Halloween: trick-or-treating, Halloween costumes or parties, "
                  "jack-o'-lanterns. NOT: a story's own witches, ghosts or monsters, costumes "
                  "for a play"),
    "birthday": ("talks about the candles on a birthday cake: blowing out the candles, making "
                 "a wish over them. NOT: birthdays, birthday parties, cake or presents "
                 "themselves, other candles"),
    "valentine": ("talks about Valentine's Day: valentines, Valentine cards or dates, Cupid. "
                  "NOT: a character or person named Valentine"),
    "easter": ("talks about Easter: the Easter bunny, Easter eggs or egg hunts, Easter baskets, "
               "Easter Sunday. NOT: ordinary eggs or rabbits, Easter Island"),
    "stpatricks": ("talks about St. Patrick's Day: leprechauns, a pot of gold, wearing green or "
                   "shamrocks for the day, its parades. NOT: Ireland or Irish people in "
                   "general, a church or school named St. Patrick's"),
    "darkmagic": ("talks about or uses dark magic or the occult: witchcraft, wizards and "
                  "witches doing magic, sorcery, curses and hexes, black magic, voodoo, "
                  "summoning demons or spirits, talking to the dead, seances, Ouija boards, "
                  "fortune telling, tarot, psychics, devil worship. NOT: 'witch' as an insult, "
                  "'a wizard with numbers', stage magic tricks, a Halloween costume"),
    "magic": ("talks about or uses magic: spells, magic wands, fairies doing magic, magic "
              "potions, enchantments, magic powers, a genie's wishes, a magic object. NOT: dark "
              "magic, wizards or witches (a separate choice), stage magic tricks (a card trick, "
              "a rabbit from a hat), 'magic' meaning wonderful ('it was magic', 'the magic "
              "word')"),
    "vampires": ("talks about vampires or werewolves: vampires, Dracula, drinking someone's "
                 "blood, turning into a bat, werewolves, turning into a wolf at the full moon. "
                 "NOT: vampire bats or other real animals, ordinary wolves"),
}
LINE_NAMES = {"sexref": "a sexual reference", "casual": "talk of sleeping around",
              "samesex": "a same-sex romance", "oppsex": "an unmarried couple living or sleeping "
                                                         "together",
              "crude": "crude humor", "bullying": "bullying", "religion": "religious talk",
              "forensic": "coroner or doctor talk",
              "disrespect": "disrespect or talking back to a parent",
              "christmas": "talk about Christmas", "halloween": "talk about Halloween",
              "birthday": "talk about the candles on a birthday cake",
              "valentine": "talk about Valentine's Day", "easter": "talk about Easter",
              "stpatricks": "talk about St. Patrick's Day",
              "darkmagic": "talk about dark magic or the occult", "magic": "talk about magic",
              "vampires": "talk about vampires or werewolves"}


def _letters(t):
    if cvlang.LANG != "en":           # other alphabets too (Russian was left with nothing)
        return re.sub(r"[^\w]+|_", " ", t.lower().replace("ё", "е")).strip()
    return re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()


def _tag(l, v):
    """How a line is shown to the dialogue reader: the speaker's name from the
    subtitles or a speaker number, plus the man / woman / child voice guess."""
    if isinstance(v, str):
        v = {"spk": "", "g": v}
    v = v or {}
    bits = []
    if l.get("who"):
        bits.append(l["who"])
    elif v.get("spk"):
        bits.append(v["spk"])
    if v.get("g") in ("man", "woman", "child"):
        bits.append(f"{v['g']}'s voice")
    return f"({', '.join(bits)}) " if bits else ""


SUBTITLE_GAP = 90.0     # this long with talking but no subtitles: the subtitles are missing it


def dialogue_lines(cues, asr, spoken):
    """Lines of dialogue with times: subtitle lines when there are subtitles,
    otherwise sentences from what was heard. Where the subtitles leave out a long
    stretch that has talking in it, the heard sentences fill it (Julie & Julia: the
    subtitles found were only the first half of the movie, "CD1", so nothing said after
    0:59 was read)."""
    lines = []
    if cues:
        for c in cues:
            txt = " ".join(spoken(c["text"])).strip()
            if txt:
                m = re.match(r"\s*-?\s*([A-Z][A-Za-z .'-]{1,20}):", c["text"])
                lines.append({"s": c["s"], "e": c["e"], "text": txt,
                              "who": m.group(1).strip().title() if m else ""})
        if lines:
            gaps, last = [], float("-inf")
            for l in sorted(lines, key=lambda l: l["s"]) + [{"s": float("inf"), "e": 0}]:
                if l["s"] - last > SUBTITLE_GAP:
                    gaps.append((last + 2.0, l["s"] - 2.0))
                last = max(last, l["e"])
            heard = []
            for a, b in gaps:               # a minute or more of talking: not a stray word
                ws = [w for w in asr if a <= w["s"] and w["e"] <= b]
                if len(ws) >= 20 and ws[-1]["e"] - ws[0]["s"] >= 60:
                    heard += ws
            if heard:
                extra = dialogue_lines([], heard, spoken)
                for l in extra:
                    l["heard"] = True       # from listening, not the subtitles
                lines = sorted(lines + extra, key=lambda l: l["s"])
        return lines
    cur = []
    for w in asr:
        if cur and (w["s"] - cur[-1]["e"] > 0.8 or len(cur) > 25):
            lines.append({"s": cur[0]["s"], "e": cur[-1]["e"], "text": " ".join(x["t"] for x in cur)})
            cur = []
        cur.append(w)
        if re.search(r"[.?!]$", w["t"]):
            lines.append({"s": cur[0]["s"], "e": cur[-1]["e"], "text": " ".join(x["t"] for x in cur)})
            cur = []
    if cur:
        lines.append({"s": cur[0]["s"], "e": cur[-1]["e"], "text": " ".join(x["t"] for x in cur)})
    return lines


def classify_dialogue(lines, wanted, progress=None, cancel=None, chunk=25, overlap=4,
                      genders=None, examples=None, people=None):
    """Returns {line_index: set(types)} for the wanted LINE_TYPES.

    Small local models guess a lot, so a line only counts when (1) the model
    quotes the exact words in that line that fit, and (2) a second, one-line
    question about just that line agrees."""
    if not lines or not wanted:
        return {}
    genders = genders or [{}] * len(lines)
    defs = "\n".join(f'- "{k}": {LINE_TYPES[k]}' for k in wanted if k in LINE_TYPES)
    if examples and examples.get("notes"):        # what they told the chat to keep in mind
        defs += ("\n\nThe family has said (follow it):\n" +
                 "\n".join(f"- {t}" for t in examples["notes"][:20]))
    if examples and (examples.get("muted") or examples.get("kept")):
        if examples.get("muted"):
            defs += ("\n\nIn this show the family has muted lines like:\n" +
                     "\n".join(f"- {t}" for t in examples["muted"][:10]))
        if examples.get("kept"):
            defs += ("\nAnd chose NOT to mute lines like:\n" +
                     "\n".join(f"- {t}" for t in examples["kept"][:10]))
    wanted = [k for k in wanted if k in LINE_TYPES]
    schema = {"type": "object", "properties": {"flags": {"type": "array", "items": {
        "type": "object", "properties": {"line": {"type": "integer"},
                                         "type": {"type": "string", "enum": list(wanted)},
                                         "words": {"type": "string"}},
        "required": ["line", "type", "words"]}}}, "required": ["flags"]}
    cands = {}
    starts = list(range(0, len(lines), chunk - overlap))
    for n, a in enumerate(starts):
        if cancel and cancel():
            raise KeyboardInterrupt
        part = lines[a:a + chunk]
        counted(progress, 0.7 * n / len(starts), a + 1, a + len(part), len(lines), "lines")
        listing = "\n".join(f"{i + 1}: {_tag(l, genders[a + i])}{l['text']}"
                             for i, l in enumerate(part))
        prompt = ("You help a family decide which lines of TV or movie dialogue to mute. Most "
                  "lines are ordinary and must NOT be flagged. Where known, a line starts with "
                  "who is speaking (a name, or 'Speaker 3' when the same voice speaks again) and "
                  "whether it sounds like a man, woman or child (these can be wrong); also use "
                  "names, he/she and who is talking to whom. Here are numbered lines in "
                  "order:\n\n" + listing + who_here(people, listing) +
                  "\n\nFlag a line only if it clearly fits one of "
                  "these:\n" + defs + "\n\nFor each flagged line give its number, the type, and "
                  "the exact words from that line that fit (copied word for word). If you are "
                  "not sure, do not flag it. Most of the time the list is empty. Answer in JSON "
                  'like {"flags": [{"line": 3, "type": "sexref", "words": "..."}]}.')
        try:
            res = chat(prompt, schema=schema, timeout=300)
        except Exception:
            res = {}
        for f in res.get("flags", []) or []:
            try:
                k = int(f.get("line")) - 1
            except (TypeError, ValueError):
                continue
            t, words = f.get("type"), _letters(str(f.get("words", "")))
            if not (0 <= k < len(part)) or t not in wanted or len(words) < 3:
                continue
            i = a + k
            if words not in _letters(lines[i]["text"]):
                # the model often gets the number wrong: look for its quote nearby
                near = [j for j in range(max(0, i - 2), min(len(lines), i + 3))
                        if words in _letters(lines[j]["text"])]
                if not near:
                    continue   # quoted words aren't in the dialogue at all: a guess
                i = near[0]
            cands.setdefault(i, set()).add(t)
        if a + chunk >= len(lines):
            break
    # second opinion, one line at a time
    found = {}
    todo = [(i, t) for i in sorted(cands) for t in sorted(cands[i])]
    yes = {"type": "object", "properties": {"fits": {"type": "boolean"}}, "required": ["fits"]}
    for n, (i, t) in enumerate(todo):
        if cancel and cancel():
            raise KeyboardInterrupt
        counted(progress, 0.7 + 0.3 * n / max(1, len(todo)), n + 1, n + 1, len(todo),
                "double-checking")
        before = " / ".join(_tag(l, genders[k]) + l["text"]
                            for k, l in enumerate(lines[max(0, i - 6):i], max(0, i - 6)))
        after = " / ".join(_tag(l, genders[k]) + l["text"]
                           for k, l in enumerate(lines[i + 1:i + 3], i + 1))
        q = (f"Dialogue just before: {before or '(none)'}\n"
             f'Line: {_tag(lines[i], genders[i])}"{lines[i]["text"]}"\n'
             f"Dialogue just after: {after or '(none)'}\n\n"
             f"Does the line in quotes contain {LINE_NAMES[t]}? That means it {LINE_TYPES[t]}. "
             "Use the dialogue around it to understand it. Answer false unless it clearly does.")
        try:
            if chat(q, schema=yes, timeout=120).get("fits") is True:
                found.setdefault(i, set()).add(t)
        except Exception:
            continue
    if progress:
        progress(1.0)
    return found


# ---------------------------------------------------------------------------
# Who's a man and who's a woman (1.18.95; Lauren's Castle S2E6, 2026-11-14: "Daemon fell in
# love with Crow" and "He was Crow's boyfriend, not mine" went through with the same-sex
# filter on; the names don't say both are men, and the "he" that does was in another part of
# the 25 lines read at a time). Before the dialogue is read, the people named in talk about
# love, dating or sex are looked up across the whole dialogue (one question), and the readers
# are told.
# ---------------------------------------------------------------------------
RELATION = re.compile(
    r"\b(boy ?friends?|girl ?friends?|lovers?|in love|dat(e|es|ed|ing)|married|marry|husbands?|"
    r"wi(fe|ves)|fianc[eé]e?|partner|ex|exes|kiss(ed|es|ing)?|crush|relationship|romance|"
    r"romantic|flirt(s|ed|ing)?|seeing (someone|him|her|each other)|sleep(ing)? with|slept "
    r"with|hook(ed|ing)? up|affair|broke up|break up|cheat(s|ed|ing)?)\b", re.I)
NOT_NAMES = set("""i i'm i'll i've i'd im ill ive id god lord jesus christ mr mrs ms miss dr doc
sir madam ma'am okay ok oh yeah yes no hey hi hello well so but and or the a an you we they he
she it this that what why who how where when then there here please thanks thank sorry wait come
look listen right now just mom dad mommy daddy mother father sis bro honey baby sweetie darling
dear man guys guy girl boy uh um hmm mmm whoa wow ah huh okay alright all monday tuesday
wednesday thursday friday saturday sunday january february march april may june july august
september october november december christmas halloween easter thanksgiving valentine new york
america american english detective officer captain sergeant lieutenant agent professor""".split())
WHO_CUES = {"man": set("he him his himself mr sir man guy boy boyfriend husband son brother father "
                       "dad daddy king prince gentleman uncle nephew grandson grandfather "
                       "fiance".split()),
            "woman": set("she her hers herself mrs ms miss woman girl girlfriend wife "
                         "daughter sister mother mom mommy queen princess lady aunt niece "
                         "granddaughter grandmother fiancee".split())}
WHO_MOST = 8          # names asked about at most
WHO_LINES = 120       # lines shown at most


def _names_in(text):
    """Capitalised words that may be names ("Crow's" -> "Crow"), not the first of a sentence."""
    out = []
    for m in re.finditer(r"(?:^|(?<=[\s\"'(]))([A-Z][a-z]{2,})(?:'s)?\b", text):
        before = text[:m.start()].rstrip()
        first = not before or before[-1] in ".!?:\"-"
        out.append((m.group(1), first))
    return out


def who_candidates(lines):
    """The names worth asking about: said mid-sentence somewhere, or twice and never written
    small (so a name, not a sentence's first word), and in or next to a line about love,
    dating or sex. Most said first."""
    mid, count, small = set(), {}, set()
    for l in lines:
        small.update(re.findall(r"\b[a-z][a-z']+\b", l["text"]))
        for name, first in _names_in(l["text"]):
            if name.lower() in NOT_NAMES:
                continue
            count[name] = count.get(name, 0) + 1
            if not first:
                mid.add(name)
    mid |= {n for n, c in count.items() if c >= 2 and n.lower() not in small}
    near = {}
    for i, l in enumerate(lines):
        if RELATION.search(l["text"]):
            for j in range(max(0, i - 1), min(len(lines), i + 2)):
                for name, _ in _names_in(lines[j]["text"]):
                    if name in mid:
                        near[name] = near.get(name, 0) + (3 if j == i else 1)
    return sorted(near, key=lambda n: (-near[n], -count[n], n))[:WHO_MOST]


def who_is_who(lines, genders=None, cancel=None):
    """{name: "man" | "woman"} for the people named in talk about love, dating or sex, from
    the whole dialogue (he/she, his/her, Mr./Mrs., boyfriend/girlfriend), each with the words
    that show it, which must be in the dialogue. {} when there's nothing to ask, in another
    language than English, or the question fails."""
    if not lines or cvlang.LANG != "en":
        return {}
    names = who_candidates(lines)
    if not names:
        return {}
    genders = genders or [{}] * len(lines)
    show = []
    for name in names:
        pat = re.compile(rf"\b{re.escape(name)}\b")
        hits = [i for i, l in enumerate(lines) if pat.search(l["text"])][:6]
        for i in hits:
            show += range(max(0, i - 2), min(len(lines), i + 3))
    show = sorted(set(show))[:WHO_LINES]
    if cancel and cancel():
        raise KeyboardInterrupt
    listing = "\n".join(_tag(lines[i], genders[i]) + lines[i]["text"] for i in show)
    schema = {"type": "object", "properties": {"people": {"type": "array", "items": {
        "type": "object", "properties": {"name": {"type": "string"},
                                         "is": {"type": "string",
                                                "enum": ["man", "woman", "unknown"]},
                                         "words": {"type": "string"}},
        "required": ["name", "is", "words"]}}}, "required": ["people"]}
    prompt = ("Here are lines from a TV show or movie, in order (a gap may come between them). "
              "Where known, a line starts with who is speaking and whether the voice sounds "
              "like a man, woman or child (these can be wrong).\n\n" + listing + "\n\n"
              "For each of these names, say whether that person is a man or a woman, judging "
              "from the dialogue: he/him/his or she/her said about them, Mr./Mrs., son/"
              "daughter, boyfriend/girlfriend. Give the exact words from the dialogue that "
              "show it (copied word for word). If it isn't clear, or the name isn't a person, "
              "answer unknown.\nNames: " + ", ".join(names) + "\nAnswer in JSON like "
              '{"people": [{"name": "Sam", "is": "man", "words": "is he in some kind of '
              'trouble"}]}.')
    try:
        res = chat(prompt, schema=schema, timeout=300)
    except Exception:
        return {}
    text = _letters(" ".join(lines[i]["text"] for i in show))
    out = {}
    for p in res.get("people", []) or []:
        name, sex = str(p.get("name", "")).strip(), p.get("is")
        words = _letters(str(p.get("words", "")))
        if name in names and sex in ("man", "woman") and len(words) >= 3 and words in text:
            # the words must say it (The Resident: "Okafor belongs to me" made Dr. Okafor a
            # man; "Ernest LeVasseur", "Ingrid, light of my life" say nothing either way)
            said = set(words.split())
            if said & WHO_CUES[sex] and not said & WHO_CUES["woman" if sex == "man" else "man"]:
                out[name] = sex
    return out


def who_note(people):
    """The line in the report's technical notes ({} -> "")."""
    if not people:
        return ""
    return "Who's who, from the whole dialogue: " + "; ".join(
        f"{n} is a {s}" for n, s in people.items()) + "."


def who_here(people, text):
    """What a reader is told beside the lines it reads: only the people named in them, as a
    plain fact. (Worded as one of the family's rules for every name, it made the AI helper
    answer "no" for the very conversation it was meant to help, Castle S2E6.)"""
    named = [(n, s) for n, s in (people or {}).items() if re.search(rf"\b{re.escape(n)}\b", text)]
    if not named:
        return ""
    return ("\n\nFrom the rest of the dialogue: " +
            ", ".join(f"{n} is a {s}" for n, s in named) + ".")


# ---------------------------------------------------------------------------
# Who is talking: speaker separation (which lines are the same person) and a
# man / woman / child guess for each line from a trained sound model, so the
# dialogue reader can tell two men flirting from a man and a woman.
# ---------------------------------------------------------------------------
VSR = 16000
SEG_NAME = "sherpa-onnx-pyannote-segmentation-3-0"
SEG_URL = ("https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-segmentation-models/"
           f"{SEG_NAME}.tar.bz2")
EMB_NAME = "nemo_en_titanet_small.onnx"
EMB_URL = ("https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-recongition-models/"
           + EMB_NAME)
SEG_DIR = HERE / "models" / SEG_NAME
EMB_FILE = HERE / "models" / EMB_NAME
VOICE_CLASSES = ("Male speech, man speaking", "Female speech, woman speaking",
                 "Child speech, kid speaking")


def speakers_ready():
    return (SEG_DIR / "model.onnx").exists() and EMB_FILE.exists()


def install_speakers(progress=None):
    import tarfile
    say = progress or (lambda f, m: None)
    if not (SEG_DIR / "model.onnx").exists():
        tmp = HERE / "models" / (SEG_NAME + ".tar.bz2")
        download(SEG_URL, tmp, lambda f, m: say(0.2 * f, "Getting the speaker separator · " + m))
        with tarfile.open(tmp, "r:bz2") as tf:
            for mem in tf.getmembers():
                if Path(mem.name).name == "model.onnx" and mem.isfile():
                    SEG_DIR.mkdir(parents=True, exist_ok=True)
                    with tf.extractfile(mem) as src, open(SEG_DIR / "model.onnx.part", "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    os.replace(SEG_DIR / "model.onnx.part", SEG_DIR / "model.onnx")
        try:
            tmp.unlink()
        except OSError:
            pass
    if not EMB_FILE.exists():
        download(EMB_URL, EMB_FILE, lambda f, m: say(0.2 + 0.8 * f, "Getting the voice matcher · " + m))


def separate_speakers(audio, threads=None, threshold=0.95):
    """[(start, end, speaker_number)] for 16 kHz mono audio. The faster copy of sherpa's own
    steps when this is the sherpa it was checked against (same speakers), else sherpa's."""
    import sherpa_onnx
    if getattr(sherpa_onnx, "__version__", "") == PORTED_SHERPA:
        try:
            got = _separate_fast(audio, threshold)
            if got is not None:
                return got
        except Exception:
            pass
    threads = threads or speaker_threads()
    cfg = sherpa_onnx.OfflineSpeakerDiarizationConfig(
        segmentation=sherpa_onnx.OfflineSpeakerSegmentationModelConfig(
            pyannote=sherpa_onnx.OfflineSpeakerSegmentationPyannoteModelConfig(
                model=str(SEG_DIR / "model.onnx")), num_threads=threads),
        embedding=sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=str(EMB_FILE),
                                                              num_threads=threads),
        clustering=sherpa_onnx.FastClusteringConfig(num_clusters=-1, threshold=threshold),
        min_duration_on=0.3, min_duration_off=0.5)
    if not cfg.validate():
        raise RuntimeError("speaker separator settings are invalid")
    sd = sherpa_onnx.OfflineSpeakerDiarization(cfg)
    res = sd.process(audio).sort_by_start_time()
    return [(float(r.start), float(r.end), int(r.speaker)) for r in res]


def _voice_guess(tagger, x):
    """man / woman / child / ? from the sound model's speech classes on one line's sound."""
    if len(x) <= VSR * 0.5:
        return "?"
    st = tagger.create_stream()
    st.accept_waveform(VSR, x)
    got = {e.name: e.prob for e in tagger.compute(st, top_k=527)}
    m, f, c = (got.get(k, 0.0) for k in VOICE_CLASSES)
    if c > 0.1 and c > 2 * max(m, f):
        return "child"
    if m > 0.02 and m > 2 * f:
        return "man"
    if f > 0.02 and f > 2 * m:
        return "woman"
    return "?"


def line_voices(audio, lines, tagger, segs=None):
    """For each line: {"spk": "Speaker 3" or "", "g": "man"|"woman"|"child"|"?"}.

    The man/woman/child guess comes from the sound model's speech classes on
    the line itself; lines it can't call borrow the clear majority of the
    same speaker's other lines. tagger: one, or a list of them to guess several lines at
    once (1.18.52; the same guesses: each line is heard on its own either way)."""
    clips = []
    for l in lines:
        s0 = max(0.0, l["s"] - 0.2)
        e0 = max(l["e"] + 0.2, s0 + 1.5)
        clips.append(audio[int(s0 * VSR):int(e0 * VSR)])
    taggers = tagger if isinstance(tagger, (list, tuple)) else [tagger]
    if len(taggers) > 1:
        import threading
        from concurrent.futures import ThreadPoolExecutor
        free, lock = list(taggers), threading.Lock()

        def one(x):
            with lock:
                t = free.pop()
            try:
                return _voice_guess(t, x)
            finally:
                with lock:
                    free.append(t)
        with ThreadPoolExecutor(len(taggers)) as ex:
            guesses = list(ex.map(one, clips))
    else:
        guesses = [_voice_guess(taggers[0], x) for x in clips]
    out = []
    for l, g in zip(lines, guesses):
        spk = None
        if segs:
            best = 0.0
            for s, e, k in segs:
                if s > l["e"]:
                    break
                o = min(e, l["e"]) - max(s, l["s"])
                if o > best:
                    best, spk = o, k
        out.append({"spk": spk, "g": g})
    # number speakers in order of first appearance; fill unclear voices from
    # the same speaker's other lines when they clearly agree
    order, votes = {}, {}
    for v in out:
        if v["spk"] is not None:
            order.setdefault(v["spk"], len(order) + 1)
            if v["g"] != "?":
                votes.setdefault(v["spk"], []).append(v["g"])
    for v in out:
        k = v["spk"]
        if v["g"] == "?" and k in votes and len(votes[k]) >= 3:
            top = max(set(votes[k]), key=votes[k].count)
            if votes[k].count(top) >= 0.75 * len(votes[k]):
                v["g"] = top
    # a "speaker" heard as both a man and a woman is really two people the
    # separator merged: give the less common voice its own number
    extra = {}
    nxt = len(order) + 1
    for k, vs in votes.items():
        kinds = {g for g in vs if g in ("man", "woman")}
        if len(kinds) == 2:
            # (sorted: on a tie, a set's order changed from run to run, and so did the
            # numbers: 1.18.54)
            minority = min(sorted(kinds), key=vs.count)
            extra[k] = (minority, nxt)
            nxt += 1
    for v in out:
        k = v["spk"]
        if k is None:
            v["spk"] = ""
        elif k in extra and v["g"] == extra[k][0]:
            v["spk"] = f"Speaker {extra[k][1]}"
        else:
            v["spk"] = f"Speaker {order[k]}"
    return out


# Speaker separation, the same steps as sherpa-onnx's own (1.13.8,
# offline-speaker-diarization-pyannote-impl.h), with the 10-second windows and the voice prints
# done several at a time (1.18.52, the owner: "1, 2 and 3"). sherpa makes its 3,000-4,000 voice
# prints for an episode one after another, which was most of the 3-4 minutes; this copy gives
# exactly the same speakers (checked against the speakers saved for real videos) in about a
# third of the time. It uses sherpa's own voice-print maker and grouping, and the same rounding
# (float32), tie-breaking (MSVC's partial_sort) and joining of nearby parts. Any other sherpa
# version, or anything going wrong, uses sherpa's own as before.
PORTED_SHERPA = "1.13.8"
_F = np.float32


def speaker_threads(cpus=None):
    """Threads for sherpa's own speaker separation: 8 on a big PC (15-20% faster than 4 with
    the same speakers; 12 or 15 were no faster), else as before."""
    cpus = cpus or os.cpu_count() or 2
    return min(8, cpus // 2) if cpus >= 8 else max(1, min(4, cpus - 1))


def speaker_workers(cpus=None):
    """(copies, threads each) for the faster speaker separation."""
    cpus = cpus or os.cpu_count() or 2
    return max(1, min(4, (cpus - 1) // 2)), (2 if cpus >= 3 else 1)


def _seg_meta(sess):
    m = sess.get_modelmeta().custom_metadata_map
    md = {k: int(m[k]) for k in ("sample_rate", "window_size", "receptive_field_size",
                                 "receptive_field_shift", "num_speakers",
                                 "powerset_max_classes", "num_classes")}
    ws = 0.1 * md["window_size"]                  # window_shift_ratio 0.1, in double
    md["window_shift"] = 1 if ws < 1 else min(int(ws), md["window_size"])
    return md


def _powerset(md):
    pm = np.zeros((md["num_classes"], md["num_speakers"]), np.int32)
    k, ns = 1, md["num_speakers"]
    for i in range(1, md["powerset_max_classes"] + 1):
        if i == 1:
            for j in range(ns):
                pm[k, j] = 1
                k += 1
        elif i == 2:
            for j in range(ns):
                for m in range(j + 1, ns):
                    pm[k, j] = pm[k, m] = 1
                    k += 1
        else:
            raise RuntimeError("powerset_max_classes > 2")
    return pm


def _top_k(vec, k):
    """The indexes MSVC's std::partial_sort(idx, idx + k, end, vec[a] > vec[b]) puts first,
    ties and all (sherpa's TopkIndex, which picks each frame's speakers)."""
    n = len(vec)
    k = max(0, min(n, k))
    if k == 0:
        return []
    idx = list(range(n))

    def pred(a, b):
        return vec[a] > vec[b]

    def push(hole, top, val):
        i = (hole - 1) >> 1
        while top < hole and pred(idx[i], val):
            idx[hole] = idx[i]
            hole = i
            i = (hole - 1) >> 1
        idx[hole] = val

    def pop_hole(hole, bottom, val):
        top, i = hole, hole
        max_non_leaf = (bottom - 1) >> 1
        while i < max_non_leaf:
            i = 2 * i + 2
            if pred(idx[i], idx[i - 1]):
                i -= 1
            idx[hole] = idx[i]
            hole = i
        if i == max_non_leaf and bottom % 2 == 0:
            idx[hole] = idx[bottom - 1]
            hole = bottom - 1
        push(hole, top, val)

    hole = k >> 1                                    # make_heap(first, mid)
    while hole > 0:
        hole -= 1
        pop_hole(hole, k, idx[hole])
    for nxt in range(k, n):
        if pred(idx[nxt], idx[0]):
            val = idx[nxt]
            idx[nxt] = idx[0]
            pop_hole(0, k, val)
    return idx[:k]


def _frame_start(i, shift, rfs):
    return int(float(_F(_F(_F(i) * _F(shift)) / _F(rfs))) + 0.5)


def _sample_at(k, nfr, size, off):
    return int(_F(_F(_F(k) / _F(nfr)) * _F(size)) + _F(off))


def _separate_fast(audio, threshold=0.95, min_on=0.3, min_off=0.5, workers=None, threads=None):
    """sherpa's speaker separation (see above); None for a single window (left to sherpa)."""
    import threading
    from concurrent.futures import ThreadPoolExecutor
    import onnxruntime as ort
    import sherpa_onnx
    w0, t0 = speaker_workers()
    workers, threads = workers or w0, threads or t0
    so = ort.SessionOptions()
    so.intra_op_num_threads = threads
    so.inter_op_num_threads = 1
    model = str(SEG_DIR / "model.onnx")
    sessions = [ort.InferenceSession(model, so, providers=["CPUExecutionProvider"])]
    md = _seg_meta(sessions[0])
    W, S, RFS, sr = (md["window_size"], md["window_shift"], md["receptive_field_shift"],
                     md["sample_rate"])
    audio = np.ascontiguousarray(audio, dtype=_F)
    n = len(audio)
    if n <= W:
        return None
    pm = _powerset(md)
    num_chunks = (n - W) // S + 1
    has_last = ((n - W) % S) > 0
    sessions += [ort.InferenceSession(model, so, providers=["CPUExecutionProvider"])
                 for _ in range(workers - 1)]
    iname = sessions[0].get_inputs()[0].name
    lock = threading.Lock()

    def take(pool):
        with lock:
            return pool.pop()

    def give(pool, x):
        with lock:
            pool.append(x)

    def seg(i):
        if i < num_chunks:
            x = audio[i * S:i * S + W]
        else:
            x = np.zeros(W, _F)
            rest = audio[num_chunks * S:]
            x[:len(rest)] = rest
        s = take(sessions)
        try:
            out = s.run(None, {iname: x.reshape(1, 1, W)})[0][0]
        finally:
            give(sessions, s)
        return pm[np.argmax(out, axis=1)]            # the first largest, like Eigen's maxCoeff
    with ThreadPoolExecutor(workers) as ex:
        labels = list(ex.map(seg, range(num_chunks + has_last)))
    nch = len(labels)
    nf_total = (W + (nch - 1) * S) // RFS + 1
    count, weight = np.zeros(nf_total, _F), np.zeros(nf_total, _F)
    for i in range(nch):
        st, r = _frame_start(i, S, RFS), labels[i].shape[0]
        count[st:st + r] += labels[i].sum(axis=1).astype(_F)
        weight[st:st + r] += _F(1)
    per_frame = ((count / (weight + _F(1e-12))) + _F(0.5)).astype(np.int32)
    if per_frame.max() == 0:
        return []
    pairs, samples = [], []                          # one voice print per (window, speaker)
    for ci, lab in enumerate(labels):
        alone = np.where((lab.sum(axis=1) < 2)[:, None], lab, 0)     # overlaps left out
        nfr, off = alone.shape[0], ci * S
        for sp in range(md["num_speakers"]):
            d = alone[:, sp]
            if d.sum() < 10:
                continue
            parts, on, s0 = [], False, 0
            for k in range(nfr):
                if d[k] != 0:
                    if not on:
                        on, s0 = True, k
                elif on:
                    on = False
                    parts.append((_sample_at(s0, nfr, W, off), _sample_at(k, nfr, W, off)))
            if on:
                parts.append((_sample_at(s0, nfr, W, off), _sample_at(nfr - 1, nfr, W, off)))
            pairs.append((ci, sp))
            samples.append(parts)
    ecfg = sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=str(EMB_FILE), num_threads=threads)
    extractors = [sherpa_onnx.SpeakerEmbeddingExtractor(ecfg) for _ in range(workers)]

    def emb(parts):
        e = take(extractors)
        try:
            s = e.create_stream()
            for a, b in parts:
                end = b if b <= n else n
                if end - a > 0:
                    s.accept_waveform(sr, audio[a:end])
            s.input_finished()
            if not e.is_ready(s):
                raise RuntimeError("a part too short for a voice print")
            return np.array(e.compute(s), dtype=_F)
        finally:
            give(extractors, e)
    with ThreadPoolExecutor(workers) as ex:
        embs = list(ex.map(emb, samples))
    valid = [i for i, e in enumerate(embs) if not np.isnan(e).any()]
    if not valid:
        return []
    groups = sherpa_onnx.FastClustering(sherpa_onnx.FastClusteringConfig(
        num_clusters=-1, threshold=threshold))(np.stack([embs[i] for i in valid]).astype(_F))
    if not groups:
        return []
    top = max(groups)
    to_group = {pairs[i]: g for i, g in zip(valid, groups)}
    cnt = np.zeros((nf_total, top + 1), np.int32)
    for ci, lab in enumerate(labels):
        new = np.zeros((lab.shape[0], top + 1), np.int32)
        for sp in range(lab.shape[1]):
            g = to_group.get((ci, sp))
            if g is not None and 0 <= g <= top:
                new[lab[:, sp] == 1, g] = 1
        st = _frame_start(ci, S, RFS)
        cnt[st:st + new.shape[0]] += new
    if has_last:
        cnt = cnt[:min(n // RFS, cnt.shape[0] - 1) + 1]
    final = np.zeros_like(cnt)
    for i in range(cnt.shape[0]):
        if per_frame[i]:
            for m in _top_k(cnt[i].tolist(), int(per_frame[i])):
                final[i, m] = 1
    scale = _F(_F(RFS) / _F(sr))
    scale_off = _F(0.5 * md["receptive_field_size"] / sr)
    gap, shortest = _F(min_off), _F(min_on)
    out = []
    ft = final.T
    nfr = ft.shape[1]
    for sp in range(ft.shape[0]):
        this = []
        on = ft[sp, 0] > 0
        s0 = 0 if on else -1
        for f in range(1, nfr):
            if on:
                if ft[sp, f] == 0:
                    this.append([_F(_F(s0) * scale) + scale_off, _F(_F(f) * scale) + scale_off])
                    on = False
            elif ft[sp, f] == 1:
                on, s0 = True, f
        if on:
            this.append([_F(_F(s0) * scale) + scale_off, _F(_F(nfr - 1) * scale) + scale_off])
        joined = True
        while joined:                                # parts closer than min_off are one
            joined = False
            for i in range(len(this) - 1):
                a, b = this[i], this[i + 1]
                m = None
                if a[1] < b[0] and _F(a[1] + gap) >= b[0]:
                    m = [a[0], b[1]]
                elif b[1] < a[0] and _F(b[1] + gap) >= a[0]:
                    m = [b[0], a[1]]
                if m is not None:
                    this[i] = m
                    del this[i + 1]
                    joined = True
                    break
        out += [(a, b, sp) for a, b in this if _F(b - a) > shortest]
    out.sort(key=lambda x: (x[0], x[2]))
    return [(float(a), float(b), int(k)) for a, b, k in out]


# ---------------------------------------------------------------------------
# Flirting and romance, judged a whole conversation at a time
# ---------------------------------------------------------------------------
BETWEEN = {"two men": "mm", "two women": "ff", "a man and a woman": "mf"}
QUICK_YES = {"type": "object", "properties": {"romance": {"type": "boolean"}},
             "required": ["romance"]}


_MALE = re.compile(r"\b(man|men|guy|guys|boy|boys|he|him|his|husband|boyfriend|father|son)\b",
                   re.I)
_FEMALE = re.compile(r"\b(woman|women|girl|girls|she|her|hers|wife|girlfriend|lady|ladies|"
                     r"mother|daughter)\b", re.I)


def _between_checked(between, what):
    """The small model often says "two men" while its own words say a man and a woman
    (That Thing You Do, Jason 2026-11-05: 8 "Same-sex romance · two men" scenes, each "the
    man ... the woman"). Its own sentence wins."""
    if between == "mm" and _FEMALE.search(what or ""):
        return "mf"
    if between == "ff" and _MALE.search(what or ""):
        return "mf"
    return between


def _voices_mixed(genders, lo, hi):
    """A man's and a woman's voice both heard in lines lo..hi (the flirting and the lines
    around it). The model can't tell from names alone who's a man or a woman (Castle S2E1,
    2026-11-11: "Now, that's kind of hot", Castle to Beckett, cut as "two men" because it
    said "Ryan comments on Beckett's behavior")."""
    heard = set()
    for v in genders[lo:hi + 1]:
        g = v if isinstance(v, str) else (v or {}).get("g")
        if g in ("man", "woman"):
            heard.add(g)
    return heard == {"man", "woman"}


def conversations(lines):
    """The dialogue split into conversations at pauses over 6 s, at most 30 lines each (the
    next starts 2 lines back), as line numbers; single lines left out."""
    convs, cur = [], [0]
    for i in range(1, len(lines)):
        if lines[i]["s"] - lines[i - 1]["e"] > 6 or len(cur) >= 30:
            convs.append(cur)
            cur = cur[-2:] if len(cur) >= 30 else []
        cur.append(i)
    convs.append(cur)
    return [c for c in convs if len(c) >= 2]


# Sexual talk, looked for one conversation at a time (1.18.70; the owner: "yes" to looking into
# why the AI helper missed Castle S2E3's innuendo, then "Yes, build it"). Read 25 lines at a
# time and told three times to flag only what it's sure of, it noticed 3 of the 13 lines she'd
# have muted and its second look dropped all 3. Asked per conversation (a quick yes or no, then
# which lines, then each line on its own, worded to count innuendo) it caught 4 of them, plus
# "I wanted to taste you", with no false alarms on a Gummi Bears episode or The Resident S03E12.
SEXUAL_TALK = ("something sexual: talk about sex or sexual body parts, a sexual joke, innuendo "
               "or a double meaning that is sexual in this context, an invitation to undress or "
               "to have sex, talk of sleeping with someone (also to get ahead), naked photos. "
               "NOT: ordinary romance, dating, a kiss, flirting with no sexual meaning, insults or "
               "swearing, crime or police talk, a doctor's or coroner's findings")
INNUENDO = (" Innuendo counts too: a suggestive remark with a sexual meaning in context (an "
            "invitation to undress or to have sex, a line that hints at sex), talk of sleeping "
            "with someone to get ahead, naked photos.")
_SEXUAL = {"type": "object", "properties": {"sexual": {"type": "boolean"}},
           "required": ["sexual"]}
_WHICH = {"type": "object", "properties": {"lines": {"type": "array", "items": {
    "type": "object", "properties": {"line": {"type": "integer"}, "words": {"type": "string"}},
    "required": ["line", "words"]}}}, "required": ["lines"]}


def sexual_talk(lines, progress=None, cancel=None):
    """Line numbers with sexual talk, found a conversation at a time and each confirmed."""
    convs = conversations(lines) if lines else []
    cands = set()
    for n, conv in enumerate(convs):
        if cancel and cancel():
            raise KeyboardInterrupt
        counted(progress, 0.8 * n / len(convs), n + 1, n + 1, len(convs), "conversations")
        listing = "\n".join(f"{k + 1}: {lines[i]['text']}" for k, i in enumerate(conv))
        prompt = ("Here is one conversation from a TV show or movie:\n\n" + listing + "\n\n"
                  "Does anyone here say " + SEXUAL_TALK + "? Answer in JSON.")
        try:
            if not chat(prompt, schema=_SEXUAL, timeout=300).get("sexual"):
                continue
            a = chat(prompt + " If yes, give the number of each such line and the exact words "
                     "from it (copied word for word).", schema=_WHICH, timeout=300)
        except Exception:
            continue
        for f in a.get("lines", []) or []:
            try:
                k = int(f.get("line")) - 1
            except (TypeError, ValueError):
                continue
            words = _letters(str(f.get("words", "")))
            if not (0 <= k < len(conv)) or len(words) < 3:
                continue
            near = [conv[j] for j in range(max(0, k - 2), min(len(conv), k + 3))
                    if words in _letters(lines[conv[j]]["text"])]
            if near:                       # its words are really there: not a guess
                cands.add(near[0])
    found = set()
    yes = {"type": "object", "properties": {"fits": {"type": "boolean"}}, "required": ["fits"]}
    what = LINE_TYPES["sexref"].replace(". NOT:", "." + INNUENDO + " NOT:", 1)
    for n, i in enumerate(sorted(cands)):
        if cancel and cancel():
            raise KeyboardInterrupt
        counted(progress, 0.8 + 0.2 * n / len(cands), n + 1, n + 1, len(cands),
                "double-checking")
        before = " / ".join(l["text"] for l in lines[max(0, i - 6):i])
        after = " / ".join(l["text"] for l in lines[i + 1:i + 3])
        q = (f"Dialogue just before: {before or '(none)'}\n"
             f'Line: "{lines[i]["text"]}"\n'
             f"Dialogue just after: {after or '(none)'}\n\n"
             f"Does the line in quotes contain a sexual reference? That means it {what}. Use the "
             "dialogue around it to understand it. Count innuendo and double meanings that are "
             "sexual in this context. Answer false if it doesn't fit.")
        try:
            if chat(q, schema=yes, timeout=120).get("fits") is True:
                found.add(i)
        except Exception:
            continue
    if progress:
        progress(1.0)
    return found


def romance_scenes(lines, genders, progress=None, cancel=None, notes=None, people=None):
    """Conversations where someone flirts or shows romantic or sexual interest.
    Returns [{"s", "e", "between": "mm|ff|mf|?", "what"}], each confirmed twice; "mixed"
    when it says two men or two women but a man's and a woman's voice are heard there.
    notes: what they told the chat to keep in mind (followed here too)."""
    if not lines:
        return []
    said = family_said(notes)
    genders = genders or [{}] * len(lines)
    # split the dialogue into conversations at long pauses, at most 30 lines each
    convs, cur = [], [0]
    for i in range(1, len(lines)):
        if lines[i]["s"] - lines[i - 1]["e"] > 6 or len(cur) >= 30:
            convs.append(cur)
            cur = cur[-2:] if len(cur) >= 30 else []
        cur.append(i)
    convs.append(cur)
    convs = [c for c in convs if len(c) >= 2]
    schema = {"type": "object", "properties": {
        "romance": {"type": "boolean"},
        "between": {"type": "string", "enum": list(BETWEEN) + ["unclear"]},
        "lines": {"type": "array", "items": {"type": "integer"}},
        "quote": {"type": "string"},
        "what": {"type": "string"}},
        "required": ["romance", "between", "lines", "quote", "what"]}
    yes = {"type": "object", "properties": {
        "romance": {"type": "boolean"},
        "between": {"type": "string", "enum": list(BETWEEN) + ["unclear"]}},
        "required": ["romance", "between"]}
    found = []
    for n, conv in enumerate(convs):
        if cancel and cancel():
            raise KeyboardInterrupt
        counted(progress, n / len(convs), n + 1, n + 1, len(convs))
        listing = "\n".join(f"{k + 1}: {_tag(lines[i], genders[i])}{lines[i]['text']}"
                            for k, i in enumerate(conv))
        prompt = ("Here is one conversation from a TV show or movie. Where known, each line "
                  "starts with who is speaking (a name, or 'Speaker 3' when the same voice speaks "
                  "again) and whether it sounds like a man, woman or child (these can be wrong; "
                  "also use names, he/she, 'handsome', 'pretty' and who is talking to "
                  "whom).\n\n" + listing + who_here(people, listing) + "\n\n"
                  "Does anyone flirt or show romantic or sexual interest in someone here "
                  "(flirting, asking someone out, a romantic compliment, a pass, talk about "
                  "dating or being attracted to someone)? Friendly chat, work talk, police "
                  "questioning and family love do NOT count. If yes, say who it is between (two "
                  "men, two women, or a man and a woman), the numbers of the flirting lines, the "
                  "exact words of one of them, and one sentence on what happens. If unsure, "
                  "answer no." + said + " Answer in JSON.")
        try:
            # first just yes or no, with the very same words (1.18.68): the full answer form
            # made it write 45-170 words for every conversation, slow when the model is only
            # partly on the graphics card (Lauren's laptop: 16 of 40 minutes); asked this way
            # it said yes to every one the full question did, on 270 conversations
            if not chat(prompt, schema=QUICK_YES, timeout=300).get("romance"):
                continue
            a = chat(prompt, schema=schema, timeout=300)
        except Exception:
            continue
        if not a.get("romance"):
            continue
        nums = [int(x) - 1 for x in a.get("lines", []) if str(x).lstrip("-").isdigit()]
        nums = [k for k in nums if 0 <= k < len(conv)]
        quote = _letters(str(a.get("quote", "")))
        # its words may run on into the next line (1.18.95, Castle S2E6: "Daemon fell in love
        # with Crow and his art and talked him into writing a graphic novel" is two subtitle
        # lines, so the find was thrown away)
        said_here = _letters(" ".join(lines[i]["text"] for i in conv))
        if not nums or len(quote) < 3 or quote not in said_here:
            continue   # can't point to the words: a guess
        idx = [conv[k] for k in nums]
        lo, hi = max(0, min(idx) - 1), min(len(lines) - 1, max(idx) + 1)
        excerpt = "\n".join(_tag(lines[i], genders[i]) + lines[i]["text"] for i in range(lo, hi + 1))
        try:
            b = chat("Here is part of a conversation from a TV show or movie (speaker and "
                     "voice guesses in brackets may be wrong):\n\n" + excerpt +
                     who_here(people, excerpt) + "\n\n"
                     "Is someone clearly flirting with, or showing romantic or sexual interest "
                     "in, someone else here? If so, is it between two men, two women, or a man "
                     "and a woman? Answer false if it's friendly, work talk, or you're unsure." +
                     said, schema=yes, timeout=180)
        except Exception:
            continue
        if b.get("romance") is not True:
            continue
        between = BETWEEN.get(b.get("between")) or BETWEEN.get(a.get("between")) or "?"
        between = _between_checked(between, str(a.get("what", "")))
        found.append({"s": lines[min(idx)]["s"], "e": lines[max(idx)]["e"], "between": between,
                      "what": str(a.get("what", ""))[:120],
                      "mixed": between in ("mm", "ff") and _voices_mixed(genders, lo, hi)})
    if progress:
        progress(1.0)
    return found
