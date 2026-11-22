"""Her Castle S2E10 report (1.18.161, adults, the AI helper, made on 1.18.158; the owner: "Yes,
both"): affair lines the list didn't know, and lines taught for Castle."""
import json
import unittest
from pathlib import Path

import support  # noqa: F401  (must come first)
import cleanview as engine
import cleanview_learn as learn

CASUAL = engine.LINE_WORDS["casual"]


def found(t):
    return [engine.LIST_WORD_TRIM.sub("", m.group(0)) for m in CASUAL.finditer(t)]


class NewPhrasings(unittest.TestCase):
    def test_caught_just_the_words(self):
        for t, words in (
                ("Did you know that Sam was cheating on Helen?", ["cheating on"]),
                ("He wanted the freedom to cheat on my sister.", ["cheat on my sister"]),
                ("I guess Helen did know about her husband's affair.", ["affair"]),
                ("If she thinks that her six-month affair can hold a candle to that...",
                 ["affair"]),
                ("Was it a two-year affair?", ["affair"]),
                ("And Nicole and Jeremy's affair was news to her.", ["affair"]),
                ("Well, I wondered at first, because he wouldn't sleep with me.",
                 ["wouldn't sleep with me"]),
                ("I didn't sleep with her, but I did kiss her.", ["didn't sleep with her"])):
            self.assertEqual(found(t), words, t)

    def test_left_alone(self):
        for t in ("He cheated on his taxes.", "She cheated on the test.", "He cheated on Monday.",
                  "Can I sleep with you tonight?", "That's my affair, not yours.",
                  "It's a family affair.", "none of your affair", "Cheating on It was easy."):
            self.assertEqual(found(t), [], t)


class TaughtForCastle(unittest.TestCase):
    def test_taught(self):
        d = json.loads((Path(engine.__file__).parent / "shared_learned.json").read_text("utf8"))
        c = d["shows"]["castle"]
        for text, kind in (("That sounded dirtier than I meant it.", "sexref"),
                           ("I think I must be rubbing off on you.", "sexref"),
                           ("Our love triangle just became a love square.", "casual"),
                           ("when they discovered they weren't the only woman in his life.",
                            "casual")):
            k = learn.norm(text)
            self.assertIn(k, c["muted"])
            self.assertEqual(c["muted_for"][k], kind)


if __name__ == "__main__":
    unittest.main()
