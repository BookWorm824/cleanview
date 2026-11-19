"""CleanListen cfdc3db's re-check of its free classics (1.18.144): a hen's "cuck-cuck", "Darn
her," as an oath, and more that was drunk."""
import unittest

import support  # noqa: F401  (must come first)
import cleanview as engine
import cvcore as cl

SEXREF = engine.LINE_WORDS["sexref"]
CRUDE = engine.LINE_WORDS["crude"]


def minced(text):
    ws = [w for w in (cl.norm(t) for t in text.split()) if w]
    return [" ".join(ws[i:j]) for i, j, _ in cl.find_language(ws, ["minced"])]


def drunk(text):
    return [m for m in CRUDE.finditer(text) if m.group(0).lower() == "drunk"]


class HenSound(unittest.TestCase):
    def test_the_hen_is_left(self):
        for line in ("\u201cCuck-cuck-cuck-cur-r-r-cuck-k-k!\u201d",
                     "The hen said cuck cuck and ran off."):
            self.assertIsNone(SEXREF.search(line), line)

    def test_the_slang_still_counts(self):
        for line in ("Don't be such a cuck.", "He's a total cuck.", "His wife cuckolded him."):
            self.assertIsNotNone(SEXREF.search(line), line)


class DarnOath(unittest.TestCase):
    def test_the_oath(self):
        for line in ("Darn her, exploded Davy.", "Oh, darn it", "darn you, said Tom",
                     "Darn her! She took it.", "Darn the luck", "Darn his hide!"):
            self.assertTrue(minced(line), line)

    def test_sewing(self):
        for line in ("She sat down to darn her stockings.", "He had to darn his socks.",
                     "Abigail would darn the elbows.", "I'll darn her dress tonight."):
            self.assertFalse(minced(line), line)


class WhatWasDrunk(unittest.TestCase):
    def test_classics_what_was_drunk(self):
        for line in ("the loving-cup has always been drunk at English banquets",
                     "currant wine was not meant to be drunk three tumblerfuls at a time",
                     "a most surprising number of the bottles had been drunk out"):
            self.assertFalse(drunk(line), line)

    def test_classics_still_drunk(self):
        for line in ("Set Diana drunk!", "They got drunk whenever they could.",
                     "the men were lying drunk below", "The wine was gone, but she was drunk.",
                     "The beer was cold and he was drunk.", "The wine was gone but Tom was drunk.",
                     "Two bottles had been opened and Tom was drunk."):
            self.assertTrue(drunk(line), line)


if __name__ == "__main__":
    unittest.main()
