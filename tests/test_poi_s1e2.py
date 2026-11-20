"""The owner's Person of Interest S1E2 report (1.18.102, 2026-11-14, adults, the AI helper, made on
1.18.100). Two lines went through: "How the hell'd you get in here?" (a listed word with 'd
joined on) and "If you're gonna step out on your wife, you need to think it through"
(cheating, which the short list for sleeping around didn't have)."""
import unittest

import support  # noqa: F401  (sets up the sandbox first)
import cvcore as cl
import cleanview as engine

CATS = list(cl.CATS)


def found(text, cats=CATS):
    w = [x for x in (cl.norm(t) for t in text.split()) if x]
    return [(" ".join(w[i:j]), c) for i, j, c in cl.find_language(w, cats)]


class JoinedOn(unittest.TestCase):
    def test_listed_words_with_d_ll_re_ve(self):
        self.assertEqual(found("How the hell'd you get in here?"), [("how the hell'd", "mild")])
        self.assertEqual(found("Who the hell're you?"), [("who the hell're", "mild")])
        self.assertTrue(found("The hell'll I do now"))
        self.assertTrue(found("Damn'd if I know"))
        self.assertTrue(cl.listed_word("hell'd"))

    def test_possessives_as_before(self):
        self.assertEqual(found("What the hell's going on"), [("what the hell's", "mild")])
        self.assertTrue(cl.listed_word("fool's"))

    def test_everyday_contractions_left_alone(self):
        for text in ("He'd go there", "We'll see", "They're here", "I've been there",
                     "She'll call", "You'd know", "Shell'd be fine"):
            self.assertEqual(found(text), [], text)
        self.assertFalse(cl.listed_word("he'd"))
        self.assertEqual(cl._base("i'd"), "i'd")          # too short to take off


class SteppingOut(unittest.TestCase):
    CASUAL = engine.LINE_WORDS["casual"]

    def test_cheating_on_someone(self):
        for text in ("If you're gonna step out on your wife, you need to think it through.",
                     "My man don't step out on me.", "He stepped out on her.",
                     "She's been stepping out on her husband.",
                     "He cheated on his wife.", "You're cheating on your girlfriend?"):
            self.assertTrue(self.CASUAL.search(text), text)

    def test_stepping_out_onto_things_left_alone(self):
        for text in ("Step out on the balcony.", "She stepped out on her porch.",
                     "Let's step out on the ice.", "He cheated on his taxes.",
                     "Did you cheat on the test?"):
            self.assertIsNone(self.CASUAL.search(text), text)

    def test_found_and_its_words_muted(self):
        lines = [{"s": 95.0, "e": 98.0, "text": "If you're gonna step out on your wife, you need "
                  "to think it through."}]
        heard = [[w, 95.0 + 0.3 * k, 95.25 + 0.3 * k] for k, w in enumerate(lines[0]["text"].split())]
        o = engine.full_opts({})
        for k in engine.LINE_KINDS:
            o[k] = False
        o["casual"] = True
        flags, _ = engine.find_lines(lines, o, False)
        self.assertEqual([f.get("words") for f in flags], [["step out on your wife"]])
        st = {"path": "none.mp4", "mutes": [], "asr": heard, "info": {}, "lines": flags,
              "dialogue": lines, "opts": o}
        engine.list_words_only(st)
        self.assertEqual([(m["raw"], m["cat"]) for m in st["mutes"]],
                         [("step out on your wife", "casual")])
        self.assertFalse(st["lines"][0]["mute"], "just those words, the line offered unticked")


if __name__ == "__main__":
    unittest.main()
