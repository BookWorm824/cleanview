"""The short no-AI list mutes just its words, not the whole line (Lauren, 2026-11-09, after
Castle S1E2: she had the chat switch 22 lines to just "sex", "condom", "affair"..., and chose
"Just the word" for the list). The line starts unticked, so she can still mute all of it.
What an AI flags, other dialogue filters, and lines learned to mute whole stay whole."""
import unittest

import support  # noqa: F401  (sets up the sandbox first)
import cleanview as engine

LINES = [{"s": 710.85, "e": 715.0, "text": "is the fact that she had sex within the hours before her death."},
         {"s": 729.2, "e": 732.8, "text": "Traces of spermicide. The guy wore a condom."},
         {"s": 1236.31, "e": 1238.5, "text": "And, yes, I was having an affair."},
         {"s": 1300.0, "e": 1302.0, "text": "Let's go get some coffee."},
         {"s": 1400.0, "e": 1403.0, "text": "She was with them over Christmas."}]
HEARD = [[w, 710.85 + 0.3 * k, 710.85 + 0.3 * k + 0.25]
         for k, w in enumerate(LINES[0]["text"].split())] + \
        [[w, 729.2 + 0.4 * k, 729.2 + 0.4 * k + 0.35] for k, w in enumerate(LINES[1]["text"].split())] + \
        [[w, 1236.31 + 0.3 * k, 1236.31 + 0.3 * k + 0.25] for k, w in enumerate(LINES[2]["text"].split())] + \
        [[w, 1400.0 + 0.4 * k, 1400.0 + 0.4 * k + 0.35] for k, w in enumerate(LINES[4]["text"].split())]


def opts(**on):
    o = engine.full_opts({})
    for k in engine.LINE_KINDS:
        o[k] = False
    o.update(on)
    return o


def st_for(flags):
    return {"path": "none.mp4", "mutes": [], "asr": HEARD, "info": {}, "lines": flags,
            "dialogue": LINES}


class JustTheWord(unittest.TestCase):

    def test_the_list_mutes_just_its_words(self):
        flags, how = engine.find_lines(LINES, opts(sexref=True, casual=True), False)
        self.assertEqual(how, "word lists")
        self.assertEqual([f.get("words") for f in flags], [["sex"], ["condom"], ["affair"]])
        st = st_for(flags)
        self.assertEqual(engine.list_words_only(st), 3)
        self.assertEqual([f["mute"] for f in st["lines"]], [False, False, False])
        self.assertEqual(sorted(m["raw"] for m in st["mutes"]), ["affair", "condom", "sex"])
        self.assertTrue(all(m["keep"] is False for m in st["mutes"]))
        self.assertEqual({m["cat"] for m in st["mutes"]}, {"sexref", "casual"})
        self.assertNotIn("words", st["lines"][0])
        # the whole sentence still plays: just "sex" is muted, not "before her death"
        sex = next(m for m in st["mutes"] if m["raw"] == "sex")
        self.assertLess(sex["e"] - sex["s"], 1.0)

    def test_what_an_ai_found_stays_whole(self):
        flags, how = engine.find_lines(LINES, opts(sexref=True), False,
                                       claude_found={0: {"sexref"}})
        self.assertNotIn("words", flags[0])               # Claude flagged it: its call
        self.assertEqual(flags[1].get("words"), ["condom"])

    def test_other_filters_stay_whole(self):
        flags, _ = engine.find_lines(LINES, opts(christmas=True), False)
        self.assertEqual([(f["plain"], f.get("words")) for f in flags],
                         [("She was with them over Christmas.", None)])

    def test_learned_or_hinted_lines_left_as_they_are(self):
        flags, _ = engine.find_lines(LINES, opts(sexref=True), False)
        flags[0]["learned"] = "you muted this before"
        flags[1]["mute"], flags[1]["hint"] = False, "CleanView learned this is fine"
        st = st_for(flags)
        self.assertEqual(engine.list_words_only(st), 0)
        self.assertTrue(st["lines"][0]["mute"])
        self.assertEqual(st["mutes"], [])

    def test_a_word_that_cant_be_placed_keeps_the_line_muted(self):
        flags = [{"s": 1.0, "e": 2.0, "text": "made love", "plain": "made love", "types": ["sexref"],
                  "mute": True, "idx": 0, "words": ["have sex"]}]
        st = st_for(flags)
        self.assertEqual(engine.list_words_only(st), 0)
        self.assertTrue(st["lines"][0]["mute"])


if __name__ == "__main__":
    unittest.main()
