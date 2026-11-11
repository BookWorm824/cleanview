"""Telling voices apart is faster with the same results (1.18.52, 2026-11-10; the owner: "1, 2
and 3"). Speaker separation was 3-4 minutes of an episode, mostly sherpa making its voice prints
one at a time: CleanView now does sherpa's own steps with the windows and voice prints several at
a time (the same speakers, checked against the speakers saved for real videos), uses 8 threads
for sherpa's own where it still runs, and guesses man/woman/child for several lines at once."""
import inspect
import unittest
from types import SimpleNamespace
from unittest import mock

import numpy as np

import support  # noqa: F401  (sets up the sandbox first)
import cleanview as engine
import cleanview_ai as ai

SR = 16000


def voice(f0, formants, secs, rng):
    """Made-up voice-like sound: a buzz at f0 through vowel-like resonances, in syllables."""
    t = np.arange(int(secs * SR)) / SR
    f = f0 * (1 + 0.04 * np.sin(2 * np.pi * 3 * t))
    phase = 2 * np.pi * np.cumsum(f) / SR
    src = sum(np.sin(k * phase) / k for k in range(1, 20))
    out = np.zeros_like(src)
    try:
        from scipy.signal import lfilter
    except ImportError:
        lfilter = None
    for fc, bw in formants:
        r = np.exp(-np.pi * bw / SR)
        a = [1.0, -2 * r * np.cos(2 * np.pi * fc / SR), r * r]
        if lfilter is not None:
            y = lfilter([1.0], a, src)
        else:
            y = np.zeros_like(src)
            for n in range(2, len(src)):
                y[n] = src[n] - a[1] * y[n - 1] - a[2] * y[n - 2]
        out += y / np.abs(y).max()
    env = np.clip(np.sin(np.pi * np.arange(len(t)) / len(t)) * 3, 0, 1)
    return (out * env * (0.6 + 0.4 * np.sin(2 * np.pi * 4 * t) ** 2)).astype(np.float32)


def conversation(n=10, seed=1):
    rng = np.random.default_rng(seed)
    a = [(700, 110), (1220, 120), (2600, 160)]
    b = [(400, 90), (2000, 130), (2800, 170)]
    parts = []
    for k in range(n):
        f0, fm = (120, a) if k % 2 == 0 else (230, b)
        parts += [voice(f0, fm, 2.5 + rng.random() * 2, rng),
                  np.zeros(int(SR * (0.4 + rng.random())), np.float32)]
    x = np.concatenate(parts)
    return (x * 0.3 + 0.003 * rng.standard_normal(len(x))).astype(np.float32)


def sherpas_own(x):
    import sherpa_onnx
    cfg = sherpa_onnx.OfflineSpeakerDiarizationConfig(
        segmentation=sherpa_onnx.OfflineSpeakerSegmentationModelConfig(
            pyannote=sherpa_onnx.OfflineSpeakerSegmentationPyannoteModelConfig(
                model=str(ai.SEG_DIR / "model.onnx")), num_threads=4),
        embedding=sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=str(ai.EMB_FILE),
                                                              num_threads=4),
        clustering=sherpa_onnx.FastClusteringConfig(num_clusters=-1, threshold=0.95),
        min_duration_on=0.3, min_duration_off=0.5)
    return [(float(r.start), float(r.end), int(r.speaker))
            for r in sherpa_onnx.OfflineSpeakerDiarization(cfg).process(x).sort_by_start_time()]


# The repo has no models\ folder: borrow the installed app's speaker models (read only) when
# they aren't here, as support does with ffmpeg.
_INSTALLED = support._installed_bin.parent / "models"
SEG_DIR = ai.SEG_DIR if ai.speakers_ready() else _INSTALLED / ai.SEG_NAME
EMB_FILE = ai.EMB_FILE if ai.speakers_ready() else _INSTALLED / ai.EMB_NAME
HAVE_MODELS = (SEG_DIR / "model.onnx").exists() and EMB_FILE.exists()


def sherpa_version():
    try:
        import sherpa_onnx
        return sherpa_onnx.__version__
    except Exception:
        return ""


@unittest.skipUnless(HAVE_MODELS, "the speaker separator isn't installed")
@unittest.skipUnless(sherpa_version() == ai.PORTED_SHERPA, "another sherpa-onnx version")
class SameSpeakers(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.patches = [mock.patch.object(ai, "SEG_DIR", SEG_DIR),
                       mock.patch.object(ai, "EMB_FILE", EMB_FILE)]
        for p in cls.patches:
            p.start()
        cls.x = conversation()
        cls.ref = sherpas_own(cls.x)

    @classmethod
    def tearDownClass(cls):
        for p in cls.patches:
            p.stop()

    def test_the_faster_copy_gives_sherpas_speakers(self):
        self.assertGreater(len(self.ref), 5)                  # it found the talking
        self.assertEqual(ai._separate_fast(self.x), self.ref)
        self.assertEqual(ai._separate_fast(self.x, workers=1, threads=1), self.ref)
        self.assertEqual(ai.separate_speakers(self.x), self.ref)

    def test_one_window_is_left_to_sherpa(self):
        short = self.x[:SR * 8]
        self.assertIsNone(ai._separate_fast(short))
        self.assertEqual(ai.separate_speakers(short), sherpas_own(short))

    def test_another_sherpa_version_or_a_failure_uses_sherpas_own(self):
        import sherpa_onnx
        with mock.patch.object(ai, "_separate_fast", side_effect=AssertionError("not used")), \
                mock.patch.object(sherpa_onnx, "__version__", "9.9.9"):
            self.assertEqual(ai.separate_speakers(self.x), self.ref)
        with mock.patch.object(ai, "_separate_fast", side_effect=RuntimeError("broke")):
            self.assertEqual(ai.separate_speakers(self.x), self.ref)


class PickingSpeakersPerFrame(unittest.TestCase):

    def test_ties_go_as_msvc_partial_sort_puts_them(self):
        self.assertEqual(ai._top_k([3, 5, 5, 1], 1), [1])     # the first of the largest
        self.assertEqual(sorted(ai._top_k([1, 4, 2, 4], 2)), [1, 3])
        self.assertEqual(sorted(ai._top_k([2, 2, 2], 2)), [0, 1])
        self.assertEqual(sorted(ai._top_k([1, 2], 5)), [0, 1])  # more asked than there are
        self.assertEqual(ai._top_k([1, 2], 0), [])

    def test_threads(self):
        self.assertEqual(ai.speaker_threads(16), 8)
        self.assertEqual(ai.speaker_threads(4), 3)            # small PCs as before
        self.assertEqual(ai.speaker_workers(16), (4, 2))
        self.assertEqual(ai.speaker_workers(4), (1, 2))


class FakeTagger:
    """Says man, woman or child from the clip's loudness, so each clip has its own answer."""

    def create_stream(self):
        box = {}
        return SimpleNamespace(accept_waveform=lambda sr, x: box.update(x=x), box=box)

    def compute(self, st, top_k=527):
        level = float(np.abs(st.box["x"]).mean())
        pick = ai.VOICE_CLASSES[int(level * 30) % 3]
        return [SimpleNamespace(name=pick, prob=0.9)]


class SeveralLinesAtOnce(unittest.TestCase):

    def test_the_same_guesses(self):
        rng = np.random.default_rng(3)
        audio = (rng.random(SR * 120) * 0.2).astype(np.float32)
        for k in range(0, 120, 4):
            audio[k * SR:(k + 2) * SR] *= 1 + (k % 7)
        lines = [{"s": float(k), "e": k + 1.5, "text": "x"} for k in range(0, 118, 2)]
        segs = [(float(k), k + 1.8, k % 3) for k in range(0, 118, 2)]
        one = ai.line_voices(audio, lines, FakeTagger(), segs)
        many = ai.line_voices(audio, lines, [FakeTagger() for _ in range(6)], segs)
        self.assertEqual(one, many)
        self.assertEqual(len({v["g"] for v in one}), 3)

    def test_find_voices_uses_several_copies(self):
        src = inspect.getsource(engine.find_voices)
        self.assertIn("[load_tagger(1) for _ in range(copies)]", src)


if __name__ == "__main__":
    unittest.main()
