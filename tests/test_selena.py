"""Lauren's Selena report (1.18.90; 2026-11-13, adults, the AI helper, made on 1.18.86, a movie
with some Spanish in it). Every listed word was muted; there was no Spanish swearing for the
short Spanish list to catch (the Spanish songs aren't in the subtitles). Her three corrections
in the chat are built in for everyone (her "Yes, build them in")."""
import json
import unittest

import support
import cleanview_learn as learn


class SelenaNotes(unittest.TestCase):
    def setUp(self):
        self.shared = json.loads((support.ROOT / "shared_learned.json").read_text(encoding="utf8"))

    def test_built_in_for_everything_cleaned(self):
        notes = " ".join(self.shared["general"]["notes"])
        self.assertIn("A parent and child", notes)
        self.assertIn("is family, not a romance", notes)
        self.assertIn("A couple lying in bed only talking", notes)
        self.assertIn("A performer singing or dancing on stage", notes)

    def test_every_video_gets_them(self):
        for key, title in (("_movies@adults", "Some Other Movie"), ("castle@teens", ""),
                           ("_movies@young", "Selena")):
            got = " ".join(learn.notes(key, title))
            self.assertIn("is family, not a romance", got, key)
            self.assertIn("not a sex scene", got, key)

    def test_the_older_built_in_notes_are_still_there(self):
        notes = " ".join(self.shared["general"]["notes"])
        self.assertIn("pharmacy", notes)
        self.assertIn("prison cell doors", notes)
        self.assertIn("a man's husband", notes)


if __name__ == "__main__":
    unittest.main()
