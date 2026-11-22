"""Her Castle S2E19-24 report (1.18.162, adults, the AI helper, made in Play 1.0.72 / 1.18.158;
the owner: "Yes, both"): phrasings for every show, and lines taught for Castle."""
import json
import unittest
from pathlib import Path

import support  # noqa: F401  (must come first)
import cleanview as engine
import cleanview_learn as learn


def found(kind, t):
    return [m.group(0) for m in engine.LINE_WORDS[kind].finditer(t)]


class NewPhrasings(unittest.TestCase):
    def test_caught(self):
        for kind, t, words in (
                ("sexref", "He was banging my daughter right under my nose?", ["banging my daughter"]),
                ("sexref", "I would've done her.", ["I would've done her"]),
                ("sexref", "I would maybe do her.", ["I would maybe do her"]),
                ("sexref", "Not her. Or her, but I'd do her.", ["I'd do her"]),
                ("casual", "The bitch that he was two-timing me with.", ["two-timing"]),
                ("casual", "...a cheap motel in Jersey to have a tryst.", ["tryst"]),
                ("casual", "David doesn't sleep with every girl who walks by.",
                 ["sleep with every girl"])):
            self.assertEqual(found(kind, t), words, t)

    def test_left_alone(self):
        for t in ("I'd do her hair.", "I'd do her a favor.", "Who would have done her harm?",
                  "Would you have done her homework?", "the band was banging their drums",
                  "Who would have done her in?"):
            self.assertEqual(found("sexref", t), [], t)


class TaughtForCastle(unittest.TestCase):
    def test_taught(self):
        d = json.loads((Path(engine.__file__).parent / "shared_learned.json").read_text("utf8"))
        c = d["shows"]["castle"]
        for text, kind in (("In fact, it's the first time he's pulled out of anything in five "
                            "years.", "sexref"),
                           ("You know, I hear it helps if you think about baseball.", "sexref"),
                           ("Wolf did his best work in the kitchen.", "sexref"),
                           ("Tracked down and killed his wife's lover.", "casual"),
                           ("So, I can stay on top of him while he finishes his book.", "sexref")):
            k = learn.norm(text)
            self.assertIn(k, c["muted"])
            self.assertEqual(c["muted_for"][k], kind)


if __name__ == "__main__":
    unittest.main()
