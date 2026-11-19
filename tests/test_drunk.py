""""drunk" is on the crude humor list, just the word muted (1.18.137; the owner, in the CleanStream
chat: "add drunk to crude humor"), not where it's what was drunk ("had drunk his tea")."""
import unittest

import support  # noqa: F401  (must come first)
import cleanview as engine

CRUDE = engine.LINE_WORDS["crude"]


def opts(**on):
    o = engine.full_opts(on)
    for k in engine.LINE_KINDS:
        o[k] = on.get(k, False)
    return o


class Drunk(unittest.TestCase):
    def test_being_drunk(self):
        for line in ("He was drunk.", "a bunch of drunk music fans", "rowdy old drunks",
                     "drunken sailors", "She's drunk.", "I'm not a drunk."):
            self.assertIsNotNone(CRUDE.search(line), line)

    def test_what_was_drunk(self):
        for line in ("He had drunk his tea.", "She has drunk the water.",
                     "They drunk from the well.", "She's drunk the whole bottle.",
                     "I'd drunk too much coffee."):
            self.assertIsNone(CRUDE.search(line), line)

    def test_just_the_word(self):
        lines = [{"s": 0.0, "e": 1.0, "text": "He was drunk."},
                 {"s": 5.0, "e": 6.0, "text": "He farted at dinner."}]
        out, _ = engine.find_lines(lines, opts(crude=True), False)
        self.assertEqual([(l["idx"], l["types"], l.get("words")) for l in out],
                         [(0, ["crude"], ["drunk"]), (1, ["crude"], None)])   # fart: whole line

    def test_only_with_crude_ticked(self):
        lines = [{"s": 0.0, "e": 1.0, "text": "He was drunk."}]
        self.assertEqual(engine.find_lines(lines, opts(crude=False, sexref=True), False)[0], [])


class OldUses(unittest.TestCase):
    """CleanListen 62d10cf's classics (1.18.140): more uses where it's what was drunk."""

    def test_what_was_drunk(self):
        for line in ("The toast was drunk in ginger wine.", "The health of the Earl was drunk.",
                     "which was always drunk at such times", "the nectar drunk by the gods",
                     "Thou hast drunk deep.", "He was drunk with the joy of it.",
                     "drunk with delight"):
            self.assertFalse([m for m in CRUDE.finditer(line)
                              if m.group(0).lower() == "drunk"], line)

    def test_still_being_drunk(self):
        for line in ("He was drunk.", "She's drunk.", "He was drunk by noon.",
                     "He was drunk by the time we got there.", "He is always drunk.",
                     "They got drunk with their friends.", "The beer was cold and he was drunk.",
                     "The guy who drank the whiskey was drunk."):
            self.assertIsNotNone(CRUDE.search(line), line)


if __name__ == "__main__":
    unittest.main()
