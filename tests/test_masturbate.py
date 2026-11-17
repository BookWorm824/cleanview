"""Masturbation words are sexual references (1.18.126; the owner, 2026-11-17, in the CleanStream
chat, for every app: "we need to add some words to sex filter", "masturbate and masterbating").
Subtitles spell it both ways; with sexual references ticked just the word is muted, as for the
rest of the short list."""
import unittest

import support  # noqa: F401  (must come first)
import cleanview as engine

SEXREF = engine.LINE_WORDS["sexref"]


class Masturbate(unittest.TestCase):
    def test_found(self):
        for line, word in (("He was masturbating in the car.", "masturbating"),
                           ("Stop masterbating!", "masterbating"),
                           ("Masturbation is a sin, he said.", "Masturbation"),
                           ("a compulsive masturbator", "masturbator"),
                           ("Did he masturbate?", "masturbate"),
                           ("She masturbated.", "masturbated")):
            m = SEXREF.search(line)
            self.assertTrue(m, line)
            self.assertEqual(m.group(0), word, line)

    def test_not_found(self):
        for line in ("He made a mast turban.", "The master batted it away.",
                     "Masterful batting today."):
            self.assertFalse(SEXREF.search(line), line)

    def test_just_the_word(self):
        self.assertTrue(engine.LIST_WORDS_ONLY & {"sexref"} if isinstance(
            engine.LIST_WORDS_ONLY, (set, frozenset)) else "sexref" in engine.LIST_WORDS_ONLY)


if __name__ == "__main__":
    unittest.main()
