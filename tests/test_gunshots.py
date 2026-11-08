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


if __name__ == "__main__":
    unittest.main()
