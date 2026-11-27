"""Meat being cut isn't gore (1.18.173, 2026-11-27; the owner, in the Play chat: "begin
training", with her photos, a meat market's photos and stills every 2 s from six butcher and
kitchen videos: 122 in all, meat_examples.npz holds how the picture AI sees each). Before, the
taught gore check found the cook slicing ribeye off a whole roast (0.81, over its 0.70) and
the descriptions nearly called the band saw's red slice gore (0.68)."""
import json
import unittest
from pathlib import Path

import numpy as np

import support  # noqa: F401  (sets up the sandbox first)
import cleanview_ai as ai

HERE = Path(__file__).parent
EX = np.load(HERE / "meat_examples.npz")
CLIP = support._installed_bin.parent / "models" / "clip-vit-base-patch32"     # the installed one


def runs():
    """Each example video's stills (2 s apart, in order) and each photo on its own."""
    out = {}
    for name, t, e in zip(EX["name"], EX["t"], EX["emb"]):
        out.setdefault(str(name), []).append((float(t), e.astype(np.float32)))
    return out


class TaughtGore(unittest.TestCase):
    def setUp(self):
        ai._taught = None

    def test_no_meat_is_found(self):
        self.assertEqual(len(EX["name"]), 122)
        for name, stills in runs().items():
            ts = [t for t, _ in stills]
            rows = [ai.taught_scores(e[None, :]) for _, e in stills]
            got = ai.taught_candidates(ts, rows, ["gore", "fight"], [], fps=1.0)
            self.assertEqual(got, [], name)

    def test_only_gore_was_taught_again(self):
        d = json.loads((ai.HERE / "picture_taught.json").read_text(encoding="utf8"))
        self.assertIn("122 stills of meat", d["gore"])
        self.assertEqual(set(d["probes"]), {"fight", "gore", "kiss", "bed"})


@unittest.skipUnless((CLIP / "text_model_quantized.onnx").exists(), "the picture AI isn't installed")
class Descriptions(unittest.TestCase):
    def test_meat_isnt_gore(self):
        import onnxruntime as ort
        old = ai.CLIP_DIR
        ai.CLIP_DIR = CLIP
        try:
            clip = ai.Clip(ort, threads=2)
        finally:
            ai.CLIP_DIR = old
        self.assertIn("a meat band saw cutting beef", ai.EVERYDAY)
        main = [i for i, n in enumerate(clip.names) if n not in ai.WHO]
        e = EX["emb"].astype(np.float32)
        lg = 100.0 * e @ clip.text[main].T
        p = np.exp(lg - lg.max(axis=1, keepdims=True))
        p /= p.sum(axis=1, keepdims=True)
        names = [clip.names[i] for i in main]
        for cat in ("gore", "fight"):
            share = p[:, [k for k, n in enumerate(names) if n == cat]].sum(axis=1)
            self.assertLess(float(share.max()), 0.3, cat)


if __name__ == "__main__":
    unittest.main()
