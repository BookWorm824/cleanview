"""Mutes and cuts land at the right time: on files whose clock doesn't start at 0
(.ts/.m2ts/.vob/.mpg rips), on files whose sound starts later than the picture
(common in MKV/DVD rips), and at the edges of a word (cvcore.snap_edges).
Uses tiny videos made with ffmpeg, so it skips where there's no ffmpeg."""
import json
import subprocess
import tempfile
import unittest
import wave
from pathlib import Path

import numpy as np

import support
import cleanview as engine
import cvcore as cl

SR = 16000
LOUD = 0.05          # ffmpeg's test tone is about 0.09
needs_ffmpeg = unittest.skipUnless(support.FFMPEG, "no ffmpeg here")


def ffmpeg(*args):
    subprocess.run([support.FFMPEG, "-v", "error", "-y", *map(str, args)], check=True,
                   capture_output=True)


def sound_of(path, *extra):
    """The first sound track as 16 kHz mono samples, as read for ffmpeg's own clock."""
    r = subprocess.run([support.FFMPEG, "-v", "error", "-i", str(path), *extra, "-ac", "1",
                        "-ar", str(SR), "-f", "f32le", "-"], capture_output=True, check=True)
    return np.frombuffer(r.stdout, dtype=np.float32)


def loudness(samples, a, b):
    seg = samples[int(a * SR):int(b * SR)]
    return float(np.sqrt(np.mean(seg ** 2))) if len(seg) else 0.0


def clean(video, mutes, cuts):
    """render() on a made-up analysis of `video`; returns the clean copy's path."""
    work = Path(tempfile.mkdtemp(dir=support.SANDBOX))
    info = engine.probe(video)
    st = {"path": str(video), "info": info, "duration": info["duration"], "groups": [],
          "mutes": [], "scenes": [], "lines": [], "cues": [], "notes": []}
    (work / "analysis.json").write_text(json.dumps(st))
    words = [{"s": s, "e": e, "word": "d**n", "raw": "damn", "cat": "mild", "src": "audio"}
             for s, e in mutes]
    scenes = [{"s": s, "e": e, "kind": ["Violence"], "why": "made up", "cut": True}
              for s, e in cuts]
    res = engine.render(work, work / "Clean", scenes, encoders=[engine.ENCODERS[-1]],
                        lines=[], words=words, log=lambda m: None)
    return Path(res["out"])


@needs_ffmpeg
class FilesThatDontStartAtZero(unittest.TestCase):
    """A .ts whose clock starts at 10 s: a mute at 3-4 s and a cut at 5-6 s must
    land there, not 10 s later (past the end, so nothing happened at all)."""

    @classmethod
    def setUpClass(cls):
        cls.src = support.SANDBOX / "starts at ten.ts"
        ffmpeg("-f", "lavfi", "-i", "testsrc=size=160x120:rate=25:duration=8",
               "-f", "lavfi", "-i", "sine=frequency=440:duration=8:sample_rate=48000",
               "-c:v", "mpeg2video", "-c:a", "mp2", "-output_ts_offset", "10", cls.src)
        cls.out = clean(cls.src, mutes=[(3.0, 4.0)], cuts=[(5.0, 6.0)])
        cls.sound = sound_of(cls.out)

    def test_file_really_starts_late(self):
        self.assertGreater(engine.probe(self.src)["start"], 5)

    def test_mute_lands_on_time(self):
        self.assertLess(loudness(self.sound, 3.15, 3.85), 0.01)
        self.assertGreater(loudness(self.sound, 1.0, 2.0), LOUD)
        self.assertGreater(loudness(self.sound, 4.2, 4.8), LOUD)

    def test_cut_happens(self):
        self.assertAlmostEqual(engine.probe(self.out)["duration"], 7.0, delta=0.3)


@needs_ffmpeg
class SoundStartsLate(unittest.TestCase):
    """An MKV whose sound starts 1 s after the picture: what the speech recognition
    hears must be on the same clock as render() mutes by."""

    @classmethod
    def setUpClass(cls):
        cls.src = support.SANDBOX / "sound one second late.mkv"
        ffmpeg("-f", "lavfi", "-i", "testsrc=size=160x120:rate=25:duration=8",
               "-itsoffset", "1", "-f", "lavfi", "-i",
               "sine=frequency=440:duration=6:sample_rate=48000",
               "-map", "0:v", "-map", "1:a", "-c:v", "mpeg4", "-c:a", "pcm_s16le", cls.src)
        cls.info = engine.probe(cls.src)

    def test_heard_on_the_files_clock(self):
        r = subprocess.run(engine._audio_cmd(self.src, self.info, True), capture_output=True,
                           check=True)
        heard = np.frombuffer(r.stdout, dtype=np.float32)
        self.assertLess(loudness(heard, 0.1, 0.9), 0.01, "silence first, where there's no sound")
        self.assertGreater(loudness(heard, 1.1, 2.0), LOUD, "the sound from 1 s on")

    def test_mute_lands_on_time(self):
        out = clean(self.src, mutes=[(3.0, 4.0)], cuts=[])
        heard = sound_of(out, "-af", "aresample=async=1:first_pts=0")
        self.assertLess(loudness(heard, 3.15, 3.85), 0.01)
        self.assertGreater(loudness(heard, 2.0, 2.8), LOUD)


def write_wav(path, channels):
    """channels: one float array per channel (16 kHz)."""
    data = np.stack(channels, axis=1)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(len(channels))
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(data, -1, 1) * 32767).astype("<i2").tobytes())


def swear(length=2.0, f_at=1.00, vowel_at=1.15, vowel_end=1.45):
    """Quiet room, then a soft "f" 30 dB below the vowel that follows: a swear."""
    rng = np.random.default_rng(1)
    t = np.arange(int(length * SR)) / SR
    x = rng.normal(0, 0.0001, len(t))
    f = (t >= f_at) & (t < vowel_at)
    x[f] += rng.normal(0, 0.01, f.sum())
    v = (t >= vowel_at) & (t < vowel_end)
    x[v] += 0.3 * np.sin(2 * np.pi * 220 * t[v])
    return x


@needs_ffmpeg
class WordEdges(unittest.TestCase):
    """The speech recognition puts this word's start at 1.15 s, at the vowel, after
    its soft "f" (from 1.00 s): the mute must start before the "f"."""

    def test_soft_first_sound_is_muted(self):
        p = support.SANDBOX / "swear.wav"
        write_wav(p, [swear()])
        s, e = cl.snap_edges(p, 1.15, 1.45)
        self.assertLessEqual(s, 0.99)
        self.assertGreaterEqual(e, 1.45)
        self.assertGreater(s, 0.8, "but not far into the silence before")

    def test_continuous_speech_is_padded(self):
        p = support.SANDBOX / "talking.wav"
        t = np.arange(2 * SR) / SR
        write_wav(p, [0.3 * np.sin(2 * np.pi * 180 * t)])
        s, e = cl.snap_edges(p, 1.0, 1.3)
        self.assertLessEqual(s, 0.85)
        self.assertGreaterEqual(e, 1.45)

    def test_surround_listens_to_the_centre(self):
        """5.1 with loud music on the sides: listening to the mix finds no silence.
        Listening to the centre channel (the dialogue) does."""
        p = support.SANDBOX / "surround.wav"
        t = np.arange(2 * SR) / SR
        music = 0.2 * np.sin(2 * np.pi * 330 * t)
        quiet = np.zeros(len(t))
        write_wav(p, [music, music, swear(), quiet, music, music])  # FL FR FC LFE BL BR
        s, _ = cl.snap_edges(p, 1.15, 1.45, audio={"index": 0, "channels": 6})
        self.assertLessEqual(s, 0.99)


if __name__ == "__main__":
    unittest.main()
