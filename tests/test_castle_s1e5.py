"""Lauren's Castle S1E5 report (2026-11-09, adults, the AI helper): "affair" went through in
four lines. "How long was the affair?" and "They end an affair because they're scared" weren't
on the short list (it only had "having/had an affair" and "an affair with"), and in "Please. No
one ends an affair" and "They have a fight. About the affair." (lines learned to mute whole)
she unticked the line, which left the word playing. In S1E2 she chose "Just the word"."""
import unittest

import support  # noqa: F401  (sets up the sandbox first)
import cleanview as engine

CASUAL = engine.LINE_WORDS["casual"]


def found(text):
    return [engine.LIST_WORD_TRIM.sub("", m.group(0)) for m in CASUAL.finditer(text)]


class TheAffair(unittest.TestCase):

    def test_her_lines(self):
        for text in ("How long was the affair?", "Please. No one ends an affair",
                     "They end an affair because they're scared.",
                     "They have a fight. About the affair.",
                     "She found out he was having an affair.",
                     "your buddy Sam had an affair right",
                     "somewhere around the time the two of you were having an affair.",
                     "I had a love affair with her", "his affair with the nanny",
                     "Their affair lasted two years."):
            self.assertEqual(found(text), ["affair"], text)

    def test_everyday_uses_left_alone(self):
        for text in ("Internal Affairs is here.", "He's from Internal Affairs.",
                     "That is none of your affair.", "It's my affair, not yours.",
                     "The wedding was quite an affair.", "What an affair that was!",
                     "It was a black-tie affair.", "It's a family affair.",
                     "the affair of the diamond necklace", "foreign affairs",
                     "She put her affairs in order.", "the current state of affairs"):
            self.assertEqual(found(text), [], text)


LINES = [{"s": 1294.0, "e": 1296.0, "text": "How long was the affair?"},
         {"s": 1300.46, "e": 1302.5, "text": "Please. No one ends an affair"}]
HEARD = [[w, l["s"] + 0.3 * k, l["s"] + 0.3 * k + 0.25]
         for l in LINES for k, w in enumerate(l["text"].split())]


def opts(**on):
    o = engine.full_opts({})
    for k in engine.LINE_KINDS:
        o[k] = False
    o.update(on)
    return o


class UntickedStillMutesTheWord(unittest.TestCase):

    def test_a_learned_line_unticked_keeps_affair_muted(self):
        o = opts(casual=True)
        flags, _ = engine.find_lines(LINES, o, False)
        self.assertEqual([f.get("words") for f in flags], [["affair"], ["affair"]])
        flags[1]["learned"] = "you muted this before"      # muted whole, as she muted it once
        st = {"path": "none.mp4", "mutes": [], "asr": HEARD, "info": {}, "lines": flags,
              "dialogue": LINES, "opts": o}
        self.assertEqual(engine.list_words_only(st), 1)     # the first: just the word
        self.assertEqual([f["mute"] for f in st["lines"]], [False, True])
        self.assertEqual([(m["raw"], m["keep"], m["cat"]) for m in st["mutes"]],
                         [("affair", False, "casual")] * 2)
        late = next(m for m in st["mutes"] if m["s"] > 1300)
        self.assertGreater(late["s"], 1301.5)               # the word, not the whole line

    def test_filter_off_mutes_nothing_extra(self):
        flags = [{"s": 1300.46, "e": 1302.5, "text": LINES[1]["text"], "plain": LINES[1]["text"],
                  "types": ["learned"], "mute": True, "idx": 1,
                  "learned": "you muted this before"}]
        st = {"path": "none.mp4", "mutes": [], "asr": HEARD, "info": {}, "lines": flags,
              "dialogue": LINES, "opts": opts(sexref=True)}
        engine.list_words_only(st)
        self.assertEqual(st["mutes"], [])
        self.assertTrue(flags[0]["mute"])


class BuiltIn(unittest.TestCase):

    def test_checked_castle_lessons_shipped(self):
        import json
        shows = json.loads((support.REPO / "shared_learned.json").read_text("utf8"))["shows"] \
            if hasattr(support, "REPO") else None
        if shows is None:
            from pathlib import Path
            shows = json.loads((Path(engine.__file__).parent / "shared_learned.json")
                               .read_text("utf8"))["shows"]
        c, t = shows["castle"], shows["castle@teens"]
        self.assertEqual(c["muted_for"]["you're not webcamming again i hope"], "sexref")
        # a coroner's finding: the coroner/doctor box since 1.18.72 ("leave coroners talk")
        self.assertEqual(c["muted_for"]["i mean it could have been a rape but my best guess is"],
                         "forensic")
        self.assertTrue(any("conquest" in n for n in c["notes"]))
        self.assertEqual(t["muted_for"]["she's my interior decorator but then we slept together "
                                        "so i don't really know what she is now"], "casual")
        # not taught: "Sites like these" heard as "Sex like these", her word-only affair lines
        every = {x for v in shows.values() for x in v.get("muted", [])}
        self.assertNotIn("sex like these are designed to evade authorities", every)
        self.assertNotIn("please no one ends an affair", every)


if __name__ == "__main__":
    unittest.main()
