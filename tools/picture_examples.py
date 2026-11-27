"""Pictures the owner gave as examples of what is NOT a kind (1.18.173: a butcher, a deli or a
kitchen cutting meat isn't gore or graphic; her photos and stills, training/meat-cutting):
the picture AI's view of each, saved as <out>/x_<name>.npz for picture_train.py (t, emb float16,
not = the kinds it isn't). Stills named <name>-<seconds>s.<ext> (taken 2 s apart from one video)
are kept together, in order, so each has its real neighbours; any other picture stands alone.
usage (with CleanView's venv Python):
  picture_examples.py <repo> <pictures folder> <out folder> <kind,kind...>"""
import collections, glob, os, re, sys
from pathlib import Path
import numpy as np
sys.stdout.reconfigure(encoding="utf8")
repo, folder, out, kinds = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4].split(",")
sys.path.insert(0, repo)
import subprocess
import onnxruntime as ort
import cleanview_ai as ai
import cvcore as cl
ai.CLIP_DIR = Path(os.environ["LOCALAPPDATA"]) / "CleanView" / "app" / "models" / "clip-vit-base-patch32"
clip = ai.Clip(ort, threads=int(os.environ.get("THREADS", "4")))

def picture(f):
    """The picture as rows x columns x RGB, read by ffmpeg (no picture library in the venv)."""
    wh = subprocess.run([cl._tool("ffprobe"), "-v", "error", "-select_streams", "v:0",
                         "-show_entries", "stream=width,height", "-of", "csv=p=0", f],
                        capture_output=True, text=True).stdout.strip().split(",")
    w, h = int(wh[0]), int(wh[1])
    raw = subprocess.run([cl._tool("ffmpeg"), "-v", "error", "-i", f, "-frames:v", "1",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    return np.frombuffer(raw[:w * h * 3], np.uint8).reshape(h, w, 3)


groups = collections.defaultdict(list)
for f in sorted(glob.glob(os.path.join(folder, "*"))):
    if not f.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
        continue
    stem = os.path.splitext(os.path.basename(f))[0]
    m = re.fullmatch(r"(.+)-(\d+)s", stem)
    if m:
        groups[m.group(1)].append((int(m.group(2)), f))
    else:
        groups[stem].append((0, f))

runs = {}                       # a sequence with stills missing is split where they're missing
for name, items in groups.items():
    items.sort()
    part = 0
    for i, it in enumerate(items):
        if i and it[0] - items[i - 1][0] > 2:
            part += 1
        runs.setdefault(name + (f"-part{part + 1}" if part else ""), []).append(it)

for name, items in sorted(runs.items()):
    ts, embs = [], []
    for t, f in sorted(items):
        rgb = picture(f)
        cs = ai.clip_crops(rgb)
        e = clip.vis.run([clip.vout], {clip.vin: np.stack(cs).astype(np.float32)})[0]
        e = e / np.linalg.norm(e, axis=1, keepdims=True)
        m = e.mean(axis=0)
        ts.append(float(t)); embs.append(m / np.linalg.norm(m))
    np.savez_compressed(os.path.join(out, f"x_{name}.npz"), t=np.array(ts, np.float32),
                        emb=np.array(embs, np.float16), no=np.array(kinds))
    print(name, len(ts), "pictures")
