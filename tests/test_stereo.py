"""Clean copies of surround videos play on a Roku (Lauren, 2026-11-08): "Til Death" (Person of
Interest) had 5.1 sound, which her Roku can't play itself, so Jellyfin converted it while
streaming and the Roku kept quitting; "Critical", in stereo, played fine. Surround copies now
have a stereo track first, the default, and the surround second. Makes tiny videos with
ffmpeg, so it skips where there's no ffmpeg."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

import support
import cleanview as engine
import cvcore as cl
from test_timing import clean, loudness, LOUD, SR

import numpy as np

needs_ffmpeg = unittest.skipUnless(support.FFMPEG, "no ffmpeg here")


def ffmpeg(*args):
    subprocess.run([support.FFMPEG, "-v", "error", "-y", *map(str, args)], check=True,
                   capture_output=True)


def audio_tracks(path):
    r = subprocess.run([cl._tool("ffprobe"), "-v", "error", "-select_streams", "a", "-show_entries",
                        "stream=index,channels:stream_disposition=default:stream_tags=title,handler_name",
                        "-of", "json", str(path)], capture_output=True, text=True, check=True)
    return [{"channels": s["channels"], "default": s["disposition"]["default"],
             "title": (s.get("tags") or {}).get("title") or (s.get("tags") or {}).get("handler_name")}
            for s in json.loads(r.stdout)["streams"]]


def track_sound(path, n):
    r = subprocess.run([support.FFMPEG, "-v", "error", "-i", str(path), "-map", f"0:a:{n}",
                        "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                       capture_output=True, check=True)
    return np.frombuffer(r.stdout, dtype=np.float32)


@needs_ffmpeg
class SurroundGetsStereoFirst(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.src = support.SANDBOX / "surround.mkv"
        ffmpeg("-f", "lavfi", "-i", "testsrc=size=160x120:rate=25:duration=8",
               "-f", "lavfi", "-i", "sine=frequency=440:duration=8:sample_rate=48000",
               "-filter_complex", "[1:a]pan=5.1|FL=c0|FR=c0|FC=c0|LFE=c0|BL=c0|BR=c0[a]",
               "-map", "0:v", "-map", "[a]", "-c:v", "mpeg4", "-c:a", "ac3", cls.src)
        cls.out = clean(cls.src, mutes=[(3.0, 4.0)], cuts=[(5.0, 6.0)])
        cls.tracks = audio_tracks(cls.out)

    def test_source_is_surround(self):
        self.assertEqual(engine.probe(self.src)["audio"]["channels"], 6)

    def test_stereo_first_and_default(self):
        self.assertEqual(len(self.tracks), 2)
        self.assertEqual(self.tracks[0], {"channels": 2, "default": 1, "title": "Stereo"})

    def test_surround_kept_second(self):
        self.assertEqual(self.tracks[1], {"channels": 6, "default": 0, "title": "Surround 5.1"})

    def test_both_muted_and_cut(self):
        self.assertAlmostEqual(engine.probe(self.out)["duration"], 7.0, delta=0.3)
        for n in (0, 1):
            with self.subTest(track=n):
                s = track_sound(self.out, n)
                self.assertLess(loudness(s, 3.15, 3.85), 0.01)
                self.assertGreater(loudness(s, 1.0, 2.0), LOUD)


@needs_ffmpeg
class SurroundWithoutCuts(unittest.TestCase):
    """No cuts: the picture is copied and the copy stays an MKV, with the same two tracks."""

    def test_two_tracks_in_an_mkv(self):
        src = support.SANDBOX / "surround no cuts.mkv"
        ffmpeg("-f", "lavfi", "-i", "testsrc=size=160x120:rate=25:duration=4",
               "-f", "lavfi", "-i", "sine=frequency=440:duration=4:sample_rate=48000",
               "-filter_complex", "[1:a]pan=5.1|FL=c0|FR=c0|FC=c0|LFE=c0|BL=c0|BR=c0[a]",
               "-map", "0:v", "-map", "[a]", "-c:v", "mpeg4", "-c:a", "ac3", src)
        out = clean(src, mutes=[(1.0, 2.0)], cuts=[])
        self.assertEqual(out.suffix, ".mkv")
        self.assertEqual(audio_tracks(out), [{"channels": 2, "default": 1, "title": "Stereo"},
                                             {"channels": 6, "default": 0, "title": "Surround 5.1"}])


@needs_ffmpeg
class StereoStaysOneTrack(unittest.TestCase):

    def test_one_stereo_track(self):
        src = support.SANDBOX / "stereo.mkv"
        ffmpeg("-f", "lavfi", "-i", "testsrc=size=160x120:rate=25:duration=4",
               "-f", "lavfi", "-i", "sine=frequency=440:duration=4:sample_rate=48000",
               "-ac", "2", "-c:v", "mpeg4", "-c:a", "aac", src)
        out = clean(src, mutes=[(1.0, 2.0)], cuts=[])
        self.assertEqual([t["channels"] for t in audio_tracks(out)], [2])


if __name__ == "__main__":
    unittest.main()
