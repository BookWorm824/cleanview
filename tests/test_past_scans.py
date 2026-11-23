"""Lessons from the past scans on this PC (1.18.166; the owner: "Yes, teach them"). The 136
videos scanned here were read again for lines that should have been muted; each find was
checked against its own dialogue before it was taught."""
import json
import unittest
from pathlib import Path

import support  # noqa: F401  (must come first)
import cleanview as engine
import cleanview_learn as learn

SHARED = json.loads((Path(engine.__file__).parent / "shared_learned.json").read_text("utf8"))


def taught(show, line, where="muted"):
    return learn.norm(line) in SHARED["shows"][show][where]


class Taught(unittest.TestCase):
    def test_lines_muted_for_their_filter(self):
        for show, line, kind in [
                ("castle", "WE COULD, UH, GO TO DINNER, DEBRIEF EACH OTHER.", "sexref"),
                ("person-of-interest", "Maybe next time I'll even see some action.", "sexref"),
                ("person-of-interest", "So...how long have you and Zoe been...special friends?",
                 "casual"),
                ("the-resident", "Mm. May your egos have a wonderful time spooning.", "sexref"),
                ("the-resident", "I'm ready. Let's move in together.", "oppsex")]:
            self.assertTrue(taught(show, line), line)
            self.assertEqual(SHARED["shows"][show]["muted_for"][learn.norm(line)], kind)

    def test_innocent_lines_kept(self):
        self.assertTrue(taught("adventures-of-the-gummi-bears", "But you're only fairy tales.",
                               "kept"))
        self.assertTrue(taught("person-of-interest",
                               "You're not still pining for that girl in Staad.", "kept"))


class CheatingPartner(unittest.TestCase):
    def hits(self, text):
        return [w for ws in engine.list_hits([{"s": 0, "e": 1, "text": text}],
                                             ["casual"]).get(0, {}).values() for w in ws]

    def test_caught(self):
        for t in ("and I'm making sure the cheating boyfriend",
                  "SO NOW ALL WE HAVE IS A CHEATING HUSBAND",
                  "Next, you're having your cheating husband's STD"):
            self.assertTrue(self.hits(t), t)

    def test_left_alone(self):
        for t in ("He was cheating at cards again.", "Stop cheating, Tommy!",
                  "cheating death is what we do here"):
            self.assertFalse(self.hits(t), t)


if __name__ == "__main__":
    unittest.main()
