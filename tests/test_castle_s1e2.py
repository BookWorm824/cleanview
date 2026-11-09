"""Lauren's Castle S1E2 report (2026-11-09, teens, word lists only). She asked the chat to mute
just the words instead of whole lines, and it muted the phrase "explain how that works later"
as one squashed word ("explainhowthatworkslater"): not found in what was heard, so only 1.2 s
around its middle was muted. A phrase is now found word by word and muted from its first word
to its last (`word_mute`)."""
import unittest

import support  # noqa: F401  (sets up the sandbox first)
import cleanview as engine

LINE = {"s": 715.88, "e": 717.8, "text": "Sex? I'll explain how that works later."}
HEARD = [["Sex?", 715.9, 716.3], ["I'll", 716.4, 716.55], ["explain", 716.55, 716.9],
         ["how", 716.9, 717.0], ["that", 717.0, 717.15], ["works", 717.15, 717.4],
         ["later.", 717.4, 717.75]]


def near(case, got, want):
    """the edges are moved a little into silence (snap_edges), so about where they're said"""
    for g, w in zip(got, want):
        case.assertAlmostEqual(g, w, delta=0.2)


def st(asr):
    return {"path": "none.mp4", "mutes": [], "asr": asr, "info": {}}


class PhraseMutes(unittest.TestCase):

    def test_a_heard_phrase_is_muted_first_word_to_last(self):
        m = engine.word_mute(st(HEARD), LINE, "explain how that works later", "you asked")
        near(self, (m["s"], m["e"]), (716.55, 717.75))
        self.assertEqual(m["raw"], "explain how that works later")
        self.assertEqual(m["src"], "claude")

    def test_an_unheard_phrase_covers_all_of_it(self):
        m = engine.word_mute(st([]), LINE, "explain how that works later", "you asked")
        self.assertEqual(m["src"], "claude-estimated")
        self.assertLessEqual(m["s"], 716.4)            # from about "explain"
        self.assertGreaterEqual(m["e"], 717.7)         # to the end of "later"

    def test_two_words_and_one_word_as_before(self):
        line = {"s": 753.9, "e": 757.9, "text": "is a sexual predator, especially with him using a condom."}
        heard = [["is", 753.9, 754.0], ["a", 754.0, 754.1], ["sexual", 754.1, 754.5],
                 ["predator,", 754.5, 755.0], ["especially", 755.1, 755.6], ["with", 755.6, 755.7],
                 ["him", 755.7, 755.8], ["using", 755.8, 756.1], ["a", 756.1, 756.2],
                 ["condom.", 756.2, 756.8]]
        m = engine.word_mute(st(heard), line, "sexual predator", "you asked")
        near(self, (m["s"], m["e"]), (754.1, 755.0))
        self.assertEqual(m["raw"], "sexual predator")
        m = engine.word_mute(st(heard), line, "condom", "you asked")
        near(self, (m["s"], m["e"]), (756.2, 756.8))

    def test_an_old_squashed_word_still_found(self):
        # learned before this fix as one word, and muted again next time
        m = engine.word_mute(st(HEARD), LINE, "explainhowthatworkslater", "you asked")
        near(self, (m["s"], m["e"]), (716.55, 717.75))


if __name__ == "__main__":
    unittest.main()
