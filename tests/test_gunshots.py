"""Real gunshots Lauren sent (2026-11-07, gunshot training sounds), as CleanView's sound tagger
heard them (`gunshot_sounds.json`: the scores, not the sounds), also with background noise
mixed in 20 and 10 dB under the bang, the way a movie has talking and music under it.

000, 094 and 095 are cut as violence and must stay so, whatever is changed in the sound
rules (e.g. the Shawshank look-alikes, `test_shawshank.py`). 001 (heard as a "cap gun") and
002 (heard as "chop") aren't found by sound alone: counting those labels, or matching
windows against these gunshots, also cut soda cans, clapping, glass and footsteps among
2,000 everyday sounds (ESC-50), which is worse. Subtitles ("[gunshot]") still find them."""
import json
import unittest
from pathlib import Path

import support  # noqa: F401  (sets up a throwaway LOCALAPPDATA first)

import cleanview as engine

DATA = json.loads((Path(__file__).parent / "gunshot_sounds.json").read_text(encoding="utf8"))
FOUND = {"gunshot_000.wav", "gunshot_094.wav", "gunshot_095.wav"}


def scan(f):
    labels = engine.TRACKED
    return {"labels": labels, "t": [w["t"] for w in f["wins"]],
            "p": [[w["p"].get(k, 0.0) for k in labels] for w in f["wins"]]}


class RealGunshots(unittest.TestCase):
    def test_found_as_violence(self):
        for f in DATA["files"]:
            if f["file"] in FOUND:
                with self.subTest(f["file"], noise=f["noise"]):
                    sc = engine.violence_scenes(scan(f), [])
                    self.assertEqual(len(sc), 1)
                    self.assertTrue(sc[0]["sure"])      # gunfire cuts; it isn't only offered
                    self.assertRegex(sc[0]["why"], "gunshot|gunfire")

    def test_every_file_is_here(self):
        names = {f["file"] for f in DATA["files"]}
        self.assertEqual(len(DATA["files"]), 15)       # five sounds, three ways each
        self.assertLessEqual(FOUND, names)


CLIPS = json.loads((Path(__file__).parent / "gunfire_clips.json").read_text(encoding="utf8"))["clips"]
# (latest start, earliest end) of the cut: from the first shots to the last (1.18.29). Before,
# 5554's cut started at 6.5 s though the shooting at the car starts at about 3 s.
EDGES = {"preview_593.mkv": (5.0, 12.0), "preview_1553.mkv": (11.0, 18.0),
         "preview_5554.mkv": (2.0, 14.0)}


def rows_scan(times, rows):
    labels = engine.TRACKED
    return {"labels": labels, "t": times, "p": [[r.get(k, 0.0) for k in labels] for r in rows]}


class GunfireInAMovie(unittest.TestCase):
    """G.I. Joe: Retaliation clips Lauren sent (2026-11-08): gunfire under talking and music."""

    def test_cut_from_the_first_shots_to_the_last(self):
        for name, (start, end) in EDGES.items():
            with self.subTest(name):
                c = CLIPS[name]
                sc = engine.violence_scenes(rows_scan(c["t"], c["p"]), [])
                self.assertEqual(len(sc), 1)
                self.assertTrue(sc[0]["sure"])
                self.assertLessEqual(sc[0]["s"], start)
                self.assertGreaterEqual(sc[0]["e"], end)

    def test_quieter_shots_alone_arent_a_scene(self):
        rows = [{"Gunshot, gunfire": 0.3}] * 6           # never loud enough on their own
        self.assertEqual(engine.violence_scenes(rows_scan([i * 1.5 for i in range(6)], rows), []), [])

    def test_only_gunfire_widens(self):
        loud = {"Gunshot, gunfire": 0.9}
        for before, widens in (({"Gunshot, gunfire": 0.3}, True),
                               ({"Screaming": 0.4}, False),                 # not gunfire
                               ({"Gunshot, gunfire": 0.3, "Slam": 0.6}, False),   # a door
                               ({"Gunshot, gunfire": 0.1}, False)):         # too faint
            with self.subTest(before):
                rows = [{}, before, loud, loud, loud, {}]
                sc = engine.violence_scenes(rows_scan([i * 1.5 for i in range(6)], rows), [])
                self.assertEqual(len(sc), 1)
                self.assertEqual(sc[0]["s"], 0.5 if widens else 2.0)


if __name__ == "__main__":
    unittest.main()
