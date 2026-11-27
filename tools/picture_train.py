"""Step 2 of teaching the picture check (after picture_embed.py): labels each still by the
scenes Claude judged (her own changes win), prints 5-fold numbers with the rule CleanView uses
(each still with its neighbours 2 s apart, CFG; the descriptions' candidates as they are, plus taught runs of 2 s or more that don't overlap
one), and writes <outdir>/picture_taught.json (taught from every video: copy it to the repo to
ship it), picture_taught_fold<k>.json (taught without fold k, to try on those videos) and
val_videos.json ([view id, path, fold]).
Pictures the owner gave as examples of what a kind is NOT (picture_examples.py's x_*.npz in an
examples folder, the 4th argument; 1.18.173, a butcher cutting meat isn't gore) are taught with
every fold, each still counting EXTRA_W times, and never scored: the numbers stay the videos'.
usage: picture_train.py %LOCALAPPDATA%\\CleanView\\views <embeddings folder> <outdir>"""
import glob, json, os, sys, zlib, collections, hashlib, time
import numpy as np
sys.stdout.reconfigure(encoding="utf8")
views, embdir, outdir = sys.argv[1], sys.argv[2], sys.argv[3]
exdir = sys.argv[4] if len(sys.argv) > 4 else None
EXTRA_W = float(os.environ.get("EXTRA_W", "200"))
KINDS = {"fight": ("Violence", "Disturbing"), "gore": ("Gore", "Graphic violence", "Medical"),
         "kiss": ("Kiss",), "bed": ("Sex scene", "Intimate scene")}
OPT = {"fight": ("violence",), "gore": ("gore", "graphic", "medical"), "kiss": ("kiss_os", "kiss_ss"),
       "bed": ("sex",)}
THRESH = {"kiss": 0.6, "bed": 0.6, "gore": 0.6, "fight": 0.65}
MINF = {"kiss": 3, "bed": 4, "gore": 2, "fight": 3}


def kind_of(sc):
    k = sc["kind"]; k = k[0] if isinstance(k, list) else k
    return str(k).split(" ·")[0].split(" (")[0]


V = []
for f in sorted(glob.glob(embdir + "/*.npz")):
    vid = os.path.basename(f)[:-4]; d = os.path.join(views, vid)
    st = json.load(open(os.path.join(d, "analysis.json"), encoding="utf8"))
    pic = json.load(open(os.path.join(d, "pictures.json"), encoding="utf8"))
    z = np.load(f); t = z["t"].astype(float); e = z["emb"].astype(np.float32)
    o = st.get("opts") or {}
    clip = pic.get("clip") or {}
    ct = {int(round(x)): r for x, r in zip(clip.get("t", []), clip.get("scores", []))}
    lum = pic.get("lum") or []; fps = pic.get("fps", 2.0)
    dark = np.array([(lambda i: i < len(lum) and (lum[i][0] < 40 or lum[i][1] < 18))(int(round(x * fps))) for x in t])
    v = {"vid": vid, "path": st.get("path"), "t": t, "e": e, "dark": dark, "lab": {}, "scenes": {}, "base": {}}
    for cat, kinds in KINDS.items():
        if not any(o.get(k) not in (None, False, "off", "Keep") for k in OPT[cat]):
            continue
        sp = []
        for sc in st.get("scenes") or []:
            if kind_of(sc) not in kinds: continue
            real = sc.get("cut") if sc.get("by_you") else (sc.get("claude") or {}).get("decision") == "remove"
            if real: sp.append((sc["s"], sc["e"]))
        v["scenes"][cat] = sp
        v["lab"][cat] = np.array([any(a <= x <= b for a, b in sp) for x in t])
        v["base"][cat] = np.array([(ct.get(int(round(x)), {}) or {}).get(cat, 0.0) for x in t])
    V.append(v)
print("videos", len(V))
X_ = []                                  # the owner's "not" examples
for f in sorted(glob.glob((exdir or "//none") + "/x_*.npz")):
    z = np.load(f)
    X_.append({"name": os.path.basename(f)[2:-4], "t": z["t"].astype(float),
               "e": z["emb"].astype(np.float32), "no": [str(k) for k in z["no"]]})
print("examples", len(X_), "pictures", sum(len(x["t"]) for x in X_))
fold = lambda v: zlib.crc32(v["vid"].encode()) % 5


def runs(t, on, gap=4.0):
    out = []
    for x, h in zip(t, on):
        if not h: continue
        if out and x - out[-1][1] <= gap: out[-1][1] = x; out[-1][2] += 1
        else: out.append([x, x, 1])
    return out


CFG = {"fight": (5, 150.0), "gore": (3, 30.0), "kiss": (3, 30.0), "bed": (3, 30.0)}


def feats(e, n):
    """The still with the n // 2 stills before and after it (2 s apart; none there: zeros)."""
    h = n // 2
    z = np.zeros((h, e.shape[1]), e.dtype)
    ez = np.vstack([z, e, z])
    return np.hstack([ez[j:j + len(e)] for j in range(n)])


def feats_alone(e, n):
    """An example's stills: the ones beside it are its own neighbours, and at the ends of a
    run the end still again (a single picture is its own neighbours: the scene goes on)."""
    h = n // 2
    ez = np.vstack([e[:1]] * h + [e] + [e[-1:]] * h)
    return np.hstack([ez[j:j + len(e)] for j in range(n)])


def ridge(X, y, sw=None, LAM=10.0):
    lam = LAM
    pos = y.mean(); cw = np.where(y > 0, 0.5 / max(pos, 1e-6), 0.5 / max(1 - pos, 1e-6))
    if sw is not None:
        cw = cw * sw
    Xb = np.hstack([X, np.ones((len(X), 1), np.float32)])
    A = (Xb * cw[:, None]).T @ Xb + lam * np.eye(Xb.shape[1])
    wb = np.linalg.solve(A, (Xb * cw[:, None]).T @ (2 * y - 1))
    return wb[:-1] * 4, wb[-1] * 4


def probs(v, w, b):
    p = np.convolve(1 / (1 + np.exp(-np.clip(v["f"] @ w + b, -30, 30))), [0.25, 0.5, 0.25], "same")
    p[v["dark"]] = 0
    return p


def today_runs(v, cat):
    on = v["base"][cat] >= THRESH[cat]; on[v["dark"]] = False
    return [r for r in runs(v["t"], on) if r[2] >= max(1, MINF[cat] // 2)
            or max(v["base"][cat][(v["t"] >= r[0]) & (v["t"] <= r[1])]) >= 0.9]


def taught_runs(v, w, b, th):
    return [r for r in runs(v["t"], probs(v, w, b) >= th) if r[1] - r[0] >= 2.0]


ov = lambda a, b: a[0] < b[1] and b[0] < a[1]


def combined(v, cat, w, b, th):
    tr = [(s - 1, e + 1) for s, e, n in today_runs(v, cat)]
    new = [(s - 1, e + 1) for s, e, n in taught_runs(v, w, b, th)]
    return tr, [p for p in new if not any(ov(p, q) for q in tr)]


def score(vs, cat, pick):
    c = collections.Counter()
    for v in vs:
        pr = pick(v); truth = v["scenes"][cat]
        c.update(a=sum(any(ov(t, p) for p in pr) for t in truth), n=len(truth),
                 pc=sum(any(ov(p, t) for t in truth) for p in pr), pn=len(pr))
    return c


def f1(c):
    R = c["a"] / max(c["n"], 1); P = c["pc"] / max(c["pn"], 1)
    return 2 * R * P / max(P + R, 1e-9)


def best_th(vs, cat, w, b):
    return max((f1(score(vs, cat, lambda v: [(s - 1, e + 1) for s, e, n in taught_runs(v, w, b, th)])), th)
               for th in (0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95))[1]


pr = lambda c: f"found {c['a']}/{c['n']} ({c['a']/max(c['n'],1):.0%}), right {c['pc']}/{c['pn']} ({c['pc']/max(c['pn'],1):.0%})"
final, val, ths = {}, {}, collections.defaultdict(list)
for cat in KINDS:
    vs = [v for v in V if cat in v["lab"]]
    K, LAM = CFG[cat]
    for v in V:
        v["f"] = feats(v["e"], K)
    ex = [x for x in X_ if cat in x["no"]]
    for x in ex:
        x["f"] = feats_alone(x["e"], K)
    exX = np.concatenate([x["f"] for x in ex]) if ex else np.zeros((0, K * 512), np.float32)

    def with_examples(X, y):
        sw = np.concatenate([np.ones(len(y)), np.full(len(exX), EXTRA_W)])
        return np.concatenate([X, exX]), np.concatenate([y, np.zeros(len(exX))]), sw

    def show_examples(w, b, th, said):
        for x in ex:
            p = 1 / (1 + np.exp(-np.clip(x["f"] @ w + b, -30, 30)))
            if len(p) > 2:
                p = np.convolve(p, [0.25, 0.5, 0.25], "same")
            print(f"      {said} {x['name']}: highest {p.max():.2f} (found from {th})")
    tot = collections.defaultdict(collections.Counter)
    for k in range(5):
        tr = [v for v in vs if fold(v) != k]; te = [v for v in vs if fold(v) == k]
        X = np.concatenate([v["f"][~v["dark"]] for v in tr])
        y = np.concatenate([v["lab"][cat][~v["dark"]] for v in tr]).astype(float)
        if y.sum() < 5 or not te: continue
        w, b = ridge(*with_examples(X, y), LAM=LAM); th = best_th(tr, cat, w, b); ths[cat].append(th)
        val.setdefault(k, {})[cat] = {"w": [round(float(x), 5) for x in w], "b": round(float(b), 5), "th": th}
        tot["today"].update(score(te, cat, lambda v: [(s - 1, e + 1) for s, e, n in today_runs(v, cat)]))
        tot["taught only"].update(score(te, cat, lambda v: [(s - 1, e + 1) for s, e, n in taught_runs(v, w, b, th)]))
        tot["today + taught"].update(score(te, cat, lambda v: sum(combined(v, cat, w, b, th), [])))
        tot["(new finds alone)"].update(score(te, cat, lambda v: combined(v, cat, w, b, th)[1]))
    print(cat, "videos", len(vs), "thresholds", ths[cat])
    for name, c in tot.items():
        print(f"   {name:20} {pr(c)}")
    X = np.concatenate([v["f"][~v["dark"]] for v in vs])
    y = np.concatenate([v["lab"][cat][~v["dark"]] for v in vs]).astype(float)
    w, b = ridge(*with_examples(X, y), LAM=LAM)
    show_examples(w, b, float(np.median(ths[cat])), "taught on all:")
    final[cat] = {"w": [round(float(x), 5) for x in w], "b": round(float(b), 5),
                  "th": float(np.median(ths[cat]))}

meta = {"version": 2, "made": time.strftime("%Y-%m-%d"), "videos": len(V),
        "how": "linear check on the mean CLIP image embedding of a frame's crops and of the "
               "stills 2 s apart around it (one row of w per still, the middle the frame's own); "
               "smoothed 0.25/0.5/0.25 over stills 2 s apart; runs of 2 s or more"}
json.dump(dict(meta, probes=final), open(os.path.join(outdir, "picture_taught.json"), "w"), separators=(",", ":"))
for k, pv in val.items():
    json.dump(dict(meta, probes=pv, fold=k), open(os.path.join(outdir, f"picture_taught_fold{k}.json"), "w"), separators=(",", ":"))
held = [(v["vid"], v["path"], fold(v)) for v in V]
json.dump(held, open(os.path.join(outdir, "val_videos.json"), "w"), indent=0)
print("held-out videos", len(held))
