"""Step 1 of teaching the picture check (picture_taught.json, 1.18.106): the picture AI's view
of every still on the Claude contact sheets of past reviews (the mean of the scanner's crops'
CLIP image embeddings), saved per video as <out>/<view id>.npz (t, emb float16). Videos done
before are skipped. Step 2 is picture_train.py.
usage (with CleanView's venv Python, ffmpeg on PATH):
  picture_embed.py <repo> %LOCALAPPDATA%\\CleanView\\views <out folder> [view id,view id...]"""
import glob, json, os, subprocess, sys, time
from pathlib import Path
import numpy as np
sys.stdout.reconfigure(encoding="utf8")
repo, views, out = sys.argv[1], sys.argv[2], sys.argv[3]
only = set(sys.argv[4].split(",")) if len(sys.argv) > 4 else None
sys.path.insert(0, repo)
import onnxruntime as ort
import cleanview_ai as ai
import cvcore as cl
ai.CLIP_DIR = Path(os.environ["LOCALAPPDATA"]) / "CleanView" / "app" / "models" / "clip-vit-base-patch32"
ffmpeg = cl._tool("ffmpeg")
clip = ai.Clip(ort, threads=int(os.environ.get("THREADS", "12")))
W, TW, PAD = 1616, 320, 4

def sheet_rgb(f):
    raw = subprocess.run([ffmpeg, "-v", "error", "-i", f, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True).stdout
    h = len(raw) // (W * 3)
    return np.frombuffer(raw[:h * W * 3], np.uint8).reshape(h, W, 3)

t0 = time.time(); done = 0
for d in sorted(glob.glob(views + "/*/")):
    vid = os.path.basename(d.rstrip("/\\"))
    if only and vid not in only: continue
    dst = os.path.join(out, vid + ".npz")
    if os.path.exists(dst): continue
    try: st = json.load(open(d + "analysis.json", encoding="utf8"))
    except Exception: continue
    if st.get("reviewer") != "Claude" or not os.path.isdir(d + "sheets"): continue
    dur = (st.get("info") or {}).get("duration") or 1e9
    ts, embs = [], []
    for si, f in enumerate(sorted(glob.glob(d + "sheets/sheet_*.jpg"))):
        img = sheet_rgb(f)
        th = (img.shape[0] - 3 * PAD) // 4
        if th < 50: continue
        crops, tt = [], []
        for k in range(20):
            t = si * 40.0 + k * 2.0
            if t > dur - 0.5: break
            r, c = divmod(k, 5)
            tile = img[r * (th + PAD): r * (th + PAD) + th, c * (TW + PAD): c * (TW + PAD) + TW]
            if tile.mean() < 3: continue          # empty tile at the end
            cs = ai.clip_crops(tile)
            crops.extend(cs); tt.append((t, len(cs)))
        if not crops: continue
        e = clip.vis.run([clip.vout], {clip.vin: np.stack(crops).astype(np.float32)})[0]
        e = e / np.linalg.norm(e, axis=1, keepdims=True)
        i = 0
        for t, n in tt:
            m = e[i:i + n].mean(axis=0); i += n
            ts.append(t); embs.append(m / np.linalg.norm(m))
    np.savez_compressed(dst, t=np.array(ts, np.float32), emb=np.array(embs, np.float16))
    done += 1
    print(f"{done} {vid} {len(ts)} stills {time.time() - t0:.0f}s", flush=True)
print("done", done)
