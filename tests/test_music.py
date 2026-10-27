"""Turning down loud hard rock, metal and rap where nobody is talking: finding it
(cleanview.loud_music, on made-up sound-checker results and subtitles), turning it down
when saving (render on a tiny video made with ffmpeg), and the review page."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

import numpy as np

import support
import cleanview as engine

SR = 16000
LABELS = engine.TRACKED


def heard(spans, length=60.0):
    """Made-up sound-checker results: windows every 1.5 s. spans: (start, end, scores)
    where scores sets labels for windows starting in [start, end)."""
    ts = [round(k * engine.SOUND_HOP, 2) for k in range(int(length / engine.SOUND_HOP))]
    rows = []
    for t in ts:
        row = dict.fromkeys(LABELS, 0.0)
        row["Speech"] = 0.8
        for a, b, scores in spans:
            if a <= t < b:
                row.update(scores)
        rows.append([row[k] for k in LABELS])
    return {"labels": LABELS, "t": ts, "p": rows}


ROCK = {"Rock music": 0.15, "Music": 0.7, "Speech": 0.05}       # like the Castle song
RAP = {"Hip hop music": 0.3, "Rapping": 0.4, "Music": 0.7, "Speech": 0.1}


def words(*times):
    return [["word", t, t + 0.3] for t in times]


class FindingIt(unittest.TestCase):

    def test_rock_with_nobody_talking(self):
        got = engine.loud_music(heard([(10, 25, ROCK)]), words(5, 40), [], 60)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["kind"], "Rock or metal music")
        self.assertAlmostEqual(got[0]["s"], 10, delta=0.5)
        self.assertAlmostEqual(got[0]["e"], 26.5, delta=1.0)
        self.assertTrue(got[0]["lower"])

    def test_lyrics_are_not_talking(self):
        """The speech recognition hears the words of the song; while the checker hardly
        hears speech, they're lyrics, so the music still gets turned down."""
        got = engine.loud_music(heard([(10, 25, ROCK)]), words(12, 13, 14, 15, 20), [], 60)
        self.assertEqual(len(got), 1)

    def test_talking_over_it_keeps_its_volume(self):
        talk = dict(ROCK, Speech=0.8)
        snd = heard([(10, 30, ROCK), (16.5, 21, talk)])
        got = engine.loud_music(snd, words(18, 19), [], 60)
        self.assertEqual(len(got), 2, "split around the talking")
        self.assertLessEqual(got[0]["e"], 17.7)
        self.assertGreaterEqual(got[1]["s"], 19.6)

    def test_rap(self):
        got = engine.loud_music(heard([(10, 25, RAP)]), words(12, 14), [], 60)
        self.assertEqual([g["kind"] for g in got], ["Rap music"])

    def test_not_from_a_blip(self):
        self.assertEqual(engine.loud_music(heard([(10, 12, ROCK)]), [], [], 60), [])

    def test_quiet_rock_or_other_music_left_alone(self):
        weak = {"Rock music": 0.08, "Music": 0.7, "Speech": 0.05}
        pop = {"Pop music": 0.6, "Music": 0.9, "Speech": 0.05}
        self.assertEqual(engine.loud_music(heard([(10, 25, weak)]), [], [], 60), [])
        self.assertEqual(engine.loud_music(heard([(10, 25, pop)]), [], [], 60), [])

    def test_too_short_between_talk(self):
        talking = dict(ROCK, Speech=0.8)          # rock playing, and clearly someone talking
        got = engine.loud_music(heard([(10, 16, talking)]), words(9, 12.5, 16), [], 60)
        self.assertEqual(got, [])

    def test_sound_scan_from_before_music_was_listened_for(self):
        old = {"labels": list(engine.VIOLENCE_SOUNDS), "t": [0.0], "p": [[0.0] * 10]}
        self.assertEqual(engine.loud_music(old, [], [], 60), [])

    def test_subtitles_that_describe_the_music(self):
        cues = [{"s": 40.0, "e": 52.0, "text": "[heavy metal music playing]"},
                {"s": 52.0, "e": 55.0, "text": "♪ We will rock you ♪"},
                {"s": 70.0, "e": 80.0, "text": "(rap music playing)"},
                {"s": 76.0, "e": 78.0, "text": "Turn that down!"}]
        got = engine.loud_music(None, [], cues, 120)
        self.assertEqual([(g["kind"], g["s"], g["e"]) for g in got],
                         [("Rock or metal music", 40.0, 52.0), ("Rap music", 70.0, 75.8)])

    def test_listened_for_when_ticked(self):
        self.assertFalse(engine.DEFAULTS["loudmusic"])
        self.assertTrue(engine.needs({"loudmusic": True, "violence": False, "sex": False})["sound"])
        for k in ("Rock music", "Heavy metal", "Hip hop music", "Rapping", "Speech", "Music"):
            self.assertIn(k, engine.TRACKED)


@unittest.skipUnless(support.FFMPEG, "no ffmpeg here")
class TurningItDown(unittest.TestCase):
    """A tiny video with a steady tone; the music from 2 s to 6 s turned down."""

    @classmethod
    def setUpClass(cls):
        cls.src = support.SANDBOX / "loud music.mkv"
        subprocess.run([support.FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i",
                        "testsrc=size=160x120:rate=25:duration=8", "-f", "lavfi", "-i",
                        "sine=frequency=440:duration=8:sample_rate=48000", "-c:v", "mpeg4",
                        "-c:a", "pcm_s16le", str(cls.src)], check=True, capture_output=True)
        work = Path(tempfile.mkdtemp(dir=support.SANDBOX))
        info = engine.probe(cls.src)
        st = {"path": str(cls.src), "info": info, "duration": info["duration"], "groups": [],
              "mutes": [], "scenes": [], "lines": [], "cues": [], "notes": [],
              "quiet": [{"s": 2.0, "e": 6.0, "kind": "Rock or metal music", "lower": True},
                        {"s": 6.5, "e": 7.5, "kind": "Rap music", "lower": False}]}
        (work / "analysis.json").write_text(json.dumps(st))
        mute = [{"s": 4.0, "e": 4.5, "word": "d**n", "raw": "damn", "cat": "mild", "src": "audio"}]
        res = engine.render(work, work / "Clean", [], encoders=[engine.ENCODERS[-1]], lines=[],
                            words=mute, log=lambda m: None)
        r = subprocess.run([support.FFMPEG, "-v", "error", "-i", res["out"], "-ac", "1", "-ar",
                            str(SR), "-f", "f32le", "-"], capture_output=True, check=True)
        cls.sound = np.frombuffer(r.stdout, dtype=np.float32)
        cls.report = (work / "Clean" / "Reports" /
                      "loud music - CleanView report.txt").read_text("utf8")

    def loud(self, a, b):
        seg = self.sound[int(a * SR):int(b * SR)]
        return float(np.sqrt(np.mean(seg ** 2)))

    def test_turned_down_to_a_quarter(self):
        full = self.loud(0.5, 1.5)
        self.assertGreater(full, 0.05)
        self.assertAlmostEqual(self.loud(2.7, 3.8) / full, 0.25, delta=0.03)
        self.assertAlmostEqual(self.loud(5.0, 5.4) / full, 0.25, delta=0.03)

    def test_eases_in_and_back_up(self):
        full = self.loud(0.5, 1.5)
        self.assertTrue(0.3 < self.loud(2.15, 2.3) / full < 0.95, "half way down at the edge")
        self.assertAlmostEqual(self.loud(6.6, 7.4) / full, 1.0, delta=0.05)

    def test_mutes_still_silent_inside(self):
        self.assertLess(self.loud(4.1, 4.4), 0.003)

    def test_unticked_music_left_alone_and_report_says_so(self):
        self.assertIn("turned down  rock or metal music for 4 seconds", self.report)
        self.assertNotIn("rap music", self.report)


if __name__ == "__main__":
    unittest.main()
