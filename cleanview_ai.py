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
import time
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
CLIP_DIR = HERE / "models" / "clip-vit-base-patch32"
CLIP_BASE = "https://huggingface.co/Xenova/clip-vit-base-patch32/resolve/main/"
CLIP_FILES = {"vision_model_quantized.onnx": "onnx/vision_model_quantized.onnx",
              "text_model_quantized.onnx": "onnx/text_model_quantized.onnx",
              "tokenizer.json": "tokenizer.json"}
OLLAMA = os.environ.get("CLEANVIEW_OLLAMA", "http://127.0.0.1:11434")
# Newest first; an older one is used if the newer can't be downloaded or run.
VISION_MODELS = [m for m in (os.environ.get("CLEANVIEW_VISION_MODEL"), "qwen3-vl:8b",
                             "qwen2.5vl:7b") if m]          # looks at pictures
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
    "smoking": ["a person smoking a cigarette", "a person smoking"],
    "drinking": ["a person drinking alcohol", "people drinking beer", "a glass of wine"],
    "drugs": ["a person using drugs", "a person snorting cocaine", "a person injecting drugs"],
    "immodest": ["a woman in a bikini", "a person in revealing underwear",
                 "a woman in a revealing low-cut outfit"],
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
    def __init__(self, ort, threads=4):
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = threads
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


# ---------------------------------------------------------------------------
# Turning CLIP scores into candidate scenes
# ---------------------------------------------------------------------------
THRESH = {"kiss": 0.6, "bed": 0.6, "gore": 0.6, "fight": 0.65, "smoking": 0.65,
          "drinking": 0.7, "drugs": 0.6, "immodest": 0.65}
MIN_FRAMES = {"kiss": 3, "bed": 4, "gore": 2, "fight": 3, "smoking": 3, "drinking": 3,
              "drugs": 2, "immodest": 3}   # seconds of hits a scene needs


def clip_candidates(clipdata, wanted, gap=4.0, pad=1.0, lum=None, fps=2.0):
    """Runs of frames where a wanted category wins. Returns
    [{"cat", "s", "e", "peak_t", "peak", "who": {...}, "frames": [...]}]."""
    if not clipdata or not clipdata.get("t"):
        return []
    ts, rows = clipdata["t"], clipdata["scores"]
    if lum:   # leave out frames too dark or murky to judge
        keep = [k for k, t in enumerate(ts) if int(round(t * fps)) >= len(lum)
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
            out.append({"cat": cat, "s": max(0.0, run[0][0] - pad), "e": run[-1][0] + pad,
                        "peak_t": peak[0], "peak": round(peak[1][cat], 3), "who": who,
                        "frames": [t for t, _ in sorted(run, key=lambda x: -x[1][cat])[:3]]})
    return sorted(out, key=lambda c: c["s"])


# ---------------------------------------------------------------------------
# Ollama: the local language-and-vision model
# ---------------------------------------------------------------------------
def _api(path, payload=None, timeout=10):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(OLLAMA + path, data=data,
                                 headers={"Content-Type": "application/json"})
    return urllib.request.urlopen(req, timeout=timeout)


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


def start_ollama(wait=60):
    if ollama_running():
        return True
    exe = find_ollama()
    if not exe:
        return False
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


def chat(prompt, images=None, schema=None, timeout=300, model=None):
    msg = {"role": "user", "content": prompt}
    if images:
        msg["images"] = images
    model = model or (VISION_MODEL if images else TEXT_MODEL)
    payload = {"model": model, "messages": [msg], "stream": False,
               "options": {"temperature": 0, "num_ctx": 8192}}
    if schema:
        payload["format"] = schema
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
def grab_frames(ffmpeg, path, times, run):
    out = []
    for t in times:
        r = run([ffmpeg, "-v", "error", "-ss", f"{max(0, t):.2f}", "-i", str(path), "-map", "0:v:0",
                 "-frames:v", "1", "-vf", "scale=640:-2", "-f", "image2", "-c:v", "mjpeg",
                 "-q:v", "4", "-"], capture_output=True)
        if r.returncode == 0 and r.stdout:
            out.append(base64.b64encode(r.stdout).decode())
    return out


PREFACE = ("These are a few frames from one moment of a TV show or movie. First describe in "
           "one short sentence what you can actually see. If the frames are dark, blurry or "
           "unclear, say so. Then answer the question. Answer yes only if you can clearly see "
           "it in the frames; if you are not sure, answer no. ")
LOOK = {
    "kiss": ("Question: are two people kissing on the lips? If yes, who is kissing (a man and a "
             "woman, two men, two women), and is it a light kiss (a short peck) or a passionate "
             "one (long, open-mouthed, making out)? A kiss on the cheek, a hug, or faces close "
             "together while talking is NOT kissing.",
             {"type": "object", "properties": {
                 "see": {"type": "string"},
                 "kissing": {"type": "boolean"},
                 "who": {"type": "string", "enum": ["man and woman", "two men", "two women",
                                                    "unclear"]},
                 "level": {"type": "string", "enum": ["light", "passionate", "none"]}},
              "required": ["see", "kissing", "who", "level"]}),
    "bed": ("Question: is a couple shown in a sexual or intimate way (in bed together, making "
            "out, undressing each other)? Who is the couple (a man and a woman, two men, two "
            "women)? Someone simply lying in bed alone, or sitting on a bed talking, is NOT.",
            {"type": "object", "properties": {
                "see": {"type": "string"},
                "intimate": {"type": "boolean"},
                "who": {"type": "string", "enum": ["man and woman", "two men", "two women",
                                                   "unclear"]}},
             "required": ["see", "intimate", "who"]}),
    "gore": ("Question: how bloody is it? Answer \"insides\" only if the inside of a body is "
             "shown on the outside: organs, entrails, brains, bone through skin, a severed body "
             "part. Answer \"blood\" if there is visible blood, a bloody wound or a bloody body "
             "but nothing inside showing. Answer \"none\" if there's no visible blood (a covered "
             "body, a crime scene without blood, a dark red object).",
             {"type": "object", "properties": {
                 "see": {"type": "string"},
                 "level": {"type": "string", "enum": ["insides", "blood", "none"]}},
              "required": ["see", "level"]}),
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
    "drugs": ("Question: is someone using illegal drugs (smoking a joint, snorting, injecting)?",
              {"type": "object", "properties": {"see": {"type": "string"},
                                                "yes": {"type": "boolean"}},
               "required": ["see", "yes"]}),
    "nudity": ("Question: is anyone naked? Answer \"shown\" only if bare breasts, bare buttocks "
               "or genitals are clearly visible. Answer \"implied\" if someone is undressed but "
               "covered: under a sheet or blanket, in a towel, a bare back or shoulders, a shower "
               "or bath shown from the shoulders up, or private parts hidden by an object or the "
               "camera angle. Answer \"none\" if everyone is dressed, or it's a shirtless man, "
               "swimwear, or just skin-toned objects.",
               {"type": "object", "properties": {
                   "see": {"type": "string"},
                   "nudity": {"type": "string", "enum": ["shown", "implied", "none"]}},
                "required": ["see", "nudity"]}),
    "immodest": ("Question: is someone dressed immodestly (swimsuit, underwear, lingerie, very "
                 "revealing clothes)?",
                 {"type": "object", "properties": {"see": {"type": "string"},
                                                   "yes": {"type": "boolean"}},
                  "required": ["see", "yes"]}),
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


def second_look(cands, frames_for, progress=None, cancel=None):
    """Ask the local model about each candidate. Adds "verdict" to each:
    {"keep": bool, "who": "mf|mm|ff|?", "level": "light|passionate|?", "what": str}."""
    for n, c in enumerate(cands):
        if cancel and cancel():
            raise KeyboardInterrupt
        if progress:
            progress(n / max(1, len(cands)))
        q, schema = LOOK[c["cat"]]
        schema = dict(schema, properties=dict(schema["properties"], clear={"type": "boolean"}),
                      required=schema["required"] + ["clear"])
        imgs = frames_for(c)
        if not imgs:
            c["verdict"] = {"keep": True, "who": "?", "level": "?", "what": "", "error": "no frames"}
            continue
        try:
            a = chat(PREFACE + q + CLEAR_ASK + " Answer in JSON.", imgs, schema, timeout=240)
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
            v["level"] = {"insides": "gore", "blood": "graphic"}.get(a.get("level"), "none")
            v["keep"] = v["level"] != "none"
        elif c["cat"] == "fight":
            v["keep"] = bool(a.get("violent"))
            v["level"] = "disturbing" if a.get("kind") == "helpless" else "combat"
        elif c["cat"] == "nudity":
            v["level"] = a.get("nudity") if a.get("nudity") in ("shown", "implied") else "none"
            v["keep"] = v["level"] != "none"
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
LINE_TYPES = {
    "sexref": ("talks about sex or sexual body parts, or makes a sexual joke or sexual double "
               "meaning. NOT: swearing, insults, lying, drinking, drugs, violence, crime, threats, "
               "compliments, or ordinary love and affection"),
    "casual": ("says or clearly implies someone had, or wants, sex outside a committed "
               "relationship: hooking up, a one-night stand, an affair, cheating, sleeping with "
               "someone, sleeping around. NOT: dating, going out, being in love, marriage, family, "
               "drinking together"),
    "samesex": ("clearly refers to romance, dating, attraction or a sexual relationship between "
                "two men or two women (for example a man saying 'my boyfriend', 'her wife', "
                "'he's gay'). NOT: friends, coworkers, police or business partners, family"),
    "oppsex": ("says an unmarried man and woman live together or sleep together. NOT: married "
               "couples, dating, roommates, family"),
    "crude": ("crude humor: jokes or talk about bodily functions, bathroom or toilet humor, "
              "gross-out jokes, crude jokes about body parts. NOT: ordinary jokes, sarcasm, "
              "plain insults"),
    "bullying": ("bullying: mocking, taunting or demeaning someone, cruel name-calling, picking "
                 "on someone weaker, trying to humiliate them. NOT: ordinary arguments, police "
                 "questioning or warnings, friendly teasing between friends"),
    "religion": ("talks about religion or faith: God, Jesus, prayer or praying, church, the "
                 "Bible, heaven or hell as places, angels, sin, or the beliefs, practices, "
                 "clergy or holidays of any religion. NOT: 'oh my God' or 'Jesus' said as a "
                 "swear or exclamation, 'bless you' after a sneeze, 'thank heavens', a "
                 "character's name"),
}
LINE_NAMES = {"sexref": "a sexual reference", "casual": "talk of sleeping around",
              "samesex": "a same-sex romance", "oppsex": "an unmarried couple living or sleeping "
                                                         "together",
              "crude": "crude humor", "bullying": "bullying", "religion": "religious talk"}


def _letters(t):
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


def dialogue_lines(cues, asr, spoken):
    """Lines of dialogue with times: subtitle lines when there are subtitles,
    otherwise sentences from what was heard."""
    lines = []
    if cues:
        for c in cues:
            txt = " ".join(spoken(c["text"])).strip()
            if txt:
                m = re.match(r"\s*-?\s*([A-Z][A-Za-z .'-]{1,20}):", c["text"])
                lines.append({"s": c["s"], "e": c["e"], "text": txt,
                              "who": m.group(1).strip().title() if m else ""})
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
                      genders=None, examples=None):
    """Returns {line_index: set(types)} for the wanted LINE_TYPES.

    Small local models guess a lot, so a line only counts when (1) the model
    quotes the exact words in that line that fit, and (2) a second, one-line
    question about just that line agrees."""
    if not lines or not wanted:
        return {}
    genders = genders or [{}] * len(lines)
    defs = "\n".join(f'- "{k}": {LINE_TYPES[k]}' for k in wanted if k in LINE_TYPES)
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
        if progress:
            progress(0.7 * n / len(starts))
        part = lines[a:a + chunk]
        listing = "\n".join(f"{i + 1}: {_tag(l, genders[a + i])}{l['text']}"
                             for i, l in enumerate(part))
        prompt = ("You help a family decide which lines of TV or movie dialogue to mute. Most "
                  "lines are ordinary and must NOT be flagged. Where known, a line starts with "
                  "who is speaking (a name, or 'Speaker 3' when the same voice speaks again) and "
                  "whether it sounds like a man, woman or child (these can be wrong); also use "
                  "names, he/she and who is talking to whom. Here are numbered lines in "
                  "order:\n\n" + listing + "\n\nFlag a line only if it clearly fits one of "
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
        if progress:
            progress(0.7 + 0.3 * n / max(1, len(todo)))
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
    """[(start, end, speaker_number)] for 16 kHz mono audio."""
    import sherpa_onnx
    threads = threads or max(1, min(4, (os.cpu_count() or 2)))
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


def line_voices(audio, lines, tagger, segs=None):
    """For each line: {"spk": "Speaker 3" or "", "g": "man"|"woman"|"child"|"?"}.

    The man/woman/child guess comes from the sound model's speech classes on
    the line itself; lines it can't call borrow the clear majority of the
    same speaker's other lines."""
    out = []
    for l in lines:
        s0 = max(0.0, l["s"] - 0.2)
        e0 = max(l["e"] + 0.2, s0 + 1.5)
        x = audio[int(s0 * VSR):int(e0 * VSR)]
        g = "?"
        if len(x) > VSR * 0.5:
            st = tagger.create_stream()
            st.accept_waveform(VSR, x)
            got = {e.name: e.prob for e in tagger.compute(st, top_k=527)}
            m, f, c = (got.get(k, 0.0) for k in VOICE_CLASSES)
            if c > 0.1 and c > 2 * max(m, f):
                g = "child"
            elif m > 0.02 and m > 2 * f:
                g = "man"
            elif f > 0.02 and f > 2 * m:
                g = "woman"
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
            minority = min(kinds, key=vs.count)
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


# ---------------------------------------------------------------------------
# Flirting and romance, judged a whole conversation at a time
# ---------------------------------------------------------------------------
BETWEEN = {"two men": "mm", "two women": "ff", "a man and a woman": "mf"}


def romance_scenes(lines, genders, progress=None, cancel=None):
    """Conversations where someone flirts or shows romantic or sexual interest.
    Returns [{"s", "e", "between": "mm|ff|mf|?", "what"}], each confirmed twice."""
    if not lines:
        return []
    genders = genders or [{}] * len(lines)
    # split the dialogue into conversations at long pauses, at most 30 lines each
    convs, cur = [], [0]
    for i in range(1, len(lines)):
        if lines[i]["s"] - lines[i - 1]["e"] > 6 or len(cur) >= 30:
            convs.append(cur)
            cur = [max(cur[-1] - 2, cur[0])] if len(cur) >= 30 else []
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
        if progress:
            progress(n / len(convs))
        listing = "\n".join(f"{k + 1}: {_tag(lines[i], genders[i])}{lines[i]['text']}"
                            for k, i in enumerate(conv))
        prompt = ("Here is one conversation from a TV show or movie. Where known, each line "
                  "starts with who is speaking (a name, or 'Speaker 3' when the same voice speaks "
                  "again) and whether it sounds like a man, woman or child (these can be wrong; "
                  "also use names, he/she, 'handsome', 'pretty' and who is talking to "
                  "whom).\n\n" + listing + "\n\n"
                  "Does anyone flirt or show romantic or sexual interest in someone here "
                  "(flirting, asking someone out, a romantic compliment, a pass, talk about "
                  "dating or being attracted to someone)? Friendly chat, work talk, police "
                  "questioning and family love do NOT count. If yes, say who it is between (two "
                  "men, two women, or a man and a woman), the numbers of the flirting lines, the "
                  "exact words of one of them, and one sentence on what happens. If unsure, "
                  "answer no. Answer in JSON.")
        try:
            a = chat(prompt, schema=schema, timeout=300)
        except Exception:
            continue
        if not a.get("romance"):
            continue
        nums = [int(x) - 1 for x in a.get("lines", []) if str(x).lstrip("-").isdigit()]
        nums = [k for k in nums if 0 <= k < len(conv)]
        quote = _letters(str(a.get("quote", "")))
        if not nums or len(quote) < 3 or not any(quote in _letters(lines[i]["text"]) for i in conv):
            continue   # can't point to the words: a guess
        idx = [conv[k] for k in nums]
        lo, hi = max(0, min(idx) - 1), min(len(lines) - 1, max(idx) + 1)
        excerpt = "\n".join(_tag(lines[i], genders[i]) + lines[i]["text"] for i in range(lo, hi + 1))
        try:
            b = chat("Here is part of a conversation from a TV show or movie (speaker and "
                     "voice guesses in brackets may be wrong):\n\n" + excerpt + "\n\n"
                     "Is someone clearly flirting with, or showing romantic or sexual interest "
                     "in, someone else here? If so, is it between two men, two women, or a man "
                     "and a woman? Answer false if it's friendly, work talk, or you're unsure.",
                     schema=yes, timeout=180)
        except Exception:
            continue
        if b.get("romance") is not True:
            continue
        between = BETWEEN.get(b.get("between")) or BETWEEN.get(a.get("between")) or "?"
        found.append({"s": lines[min(idx)]["s"], "e": lines[max(idx)]["e"], "between": between,
                      "what": str(a.get("what", ""))[:120]})
    if progress:
        progress(1.0)
    return found
