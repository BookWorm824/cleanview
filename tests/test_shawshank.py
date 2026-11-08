"""Jason's The Shawshank Redemption review (2026-11-07). Of five scenes cut as
"gunshot-like bangs", four were cell doors clanking, Andy at a typewriter, sobbing and a
door clanging. The sound tagger knows those sounds too: when one is heard more clearly than
the gunfire in the same 3 seconds, it isn't gunfire."""
import unittest

import support

import cleanview as engine


def scan(rows):
    """A made-up sound scan: one row of {label: probability} per 1.5 s window."""
    labels = engine.TRACKED
    return {"labels": labels, "t": [i * 1.5 for i in range(len(rows))],
            "p": [[r.get(k, 0.0) for k in labels] for r in rows]}


class LookAlikes(unittest.TestCase):
    def test_listened_for(self):
        for k in ("Door", "Slam", "Typewriter", "Crying, sobbing"):
            self.assertIn(k, engine.TRACKED)

    def test_cell_doors_arent_gunfire(self):
        rows = [{"Gunshot, gunfire": 0.6, "Slam": 0.8, "Door": 0.5}] * 4
        self.assertEqual(engine.violence_scenes(scan(rows), []), [])

    def test_typewriter_and_sobbing_arent_gunfire(self):
        for k in ("Typewriter", "Crying, sobbing"):
            with self.subTest(k):
                rows = [{"Machine gun": 0.55, k: 0.7}] * 5
                self.assertEqual(engine.violence_scenes(scan(rows), []), [])

    def test_real_gunshots_still_cut(self):
        rows = [{"Gunshot, gunfire": 0.9, "Slam": 0.3}] * 4
        sc = engine.violence_scenes(scan(rows), [])
        self.assertEqual(len(sc), 1)
        self.assertTrue(sc[0]["sure"])
        self.assertIn("gunshot-like bangs", sc[0]["why"])

    def test_a_scream_isnt_undone_by_a_door(self):
        rows = [{"Screaming": 0.7, "Door": 0.8}] * 4      # only gunfire and blows yield
        self.assertEqual(len(engine.violence_scenes(scan(rows), [])), 1)

    def test_older_scans_as_before(self):
        labels = [k for k in engine.TRACKED if k not in engine.LOOK_ALIKE_SOUNDS]
        snd = {"labels": labels, "t": [0, 1.5, 3, 4.5],
               "p": [[0.6 if k == "Gunshot, gunfire" else 0.0 for k in labels]] * 4}
        self.assertEqual(len(engine.violence_scenes(snd, [])), 1)


if __name__ == "__main__":
    unittest.main()
