"""Lauren's Person of Interest S1E3 report (1.18.104, 2026-11-14, adults, the AI helper, made on
1.18.102; the owner: "Yes, do both"). Every mute was right; four lines went through: "Who's the
other woman?" / "Looks like Joey's other woman's got a little girl" and "Bank robber and a
cheat" (talk of cheating), "...the land of tequila / and grateful señoritas" (innuendo, split
over two lines) and "Latimer screwed us" (like "we're screwed")."""
import unittest

import support  # noqa: F401  (sets up the sandbox first)
import cvcore as cl
import cleanview as engine

CATS = list(cl.CATS)


def found(text, cats=CATS):
    w = [x for x in (cl.norm(t) for t in text.split()) if x]
    return [(" ".join(w[i:j]), c) for i, j, c in cl.find_language(w, cats)]


class OtherWoman(unittest.TestCase):
    CASUAL = engine.LINE_WORDS["casual"]

    def test_found(self):
        for text in ("So... Who's the other woman?", "Who is the other woman?",
                     "Looks like Joey's other woman's got a little girl.",
                     "He went back to his other woman."):
            self.assertTrue(self.CASUAL.search(text), text)

    def test_other_women_and_men_left_alone(self):
        for text in ("Where's the other woman going?", "the two other women in the car",
                     "We don't want him to hurt other women.",
                     "Did you recognize any of the other men over there tonight?",
                     "They followed two other men out.", "How I begged him to take other women on"):
            self.assertIsNone(self.CASUAL.search(text), text)

    def test_just_other_woman_muted(self):
        text = "Looks like Joey's other woman's got a little girl."
        lines = [{"s": 1193.35, "e": 1195.9, "text": text}]
        heard = [[w, 1193.35 + 0.3 * k, 1193.6 + 0.3 * k] for k, w in enumerate(text.split())]
        o = engine.full_opts({})
        for k in engine.LINE_KINDS:
            o[k] = False
        o["casual"] = True
        flags, _ = engine.find_lines(lines, o, False)
        self.assertEqual([f.get("words") for f in flags], [["other woman"]])
        st = {"path": "none.mp4", "mutes": [], "asr": heard, "info": {}, "lines": flags,
              "dialogue": lines, "opts": o}
        engine.list_words_only(st)
        self.assertEqual([(m["raw"], m["cat"]) for m in st["mutes"]], [("other woman", "casual")])
        self.assertFalse(st["lines"][0]["mute"], "just those words, the line offered unticked")


class Senoritas(unittest.TestCase):
    def test_found_with_or_without_the_accent(self):
        sexref = engine.LINE_WORDS["sexref"]
        for text in ("and grateful señoritas.", "and grateful senoritas.", "a grateful señorita",
                     "and grateful seoritas"):        # (as norm() leaves it)
            self.assertTrue(sexref.search(text), text)
        self.assertIsNone(sexref.search("Buenos días, señorita."))


class Screwed(unittest.TestCase):
    def test_found_with_the_mild_words(self):
        for text, said in (("Latimer screwed us.", "screwed us"),
                           ("He screwed me over.", "screwed me over"),
                           ("You don't screw with us.", "screw with us"),
                           ("Someone is screwing with me.", "screwing with me"),
                           ("Every crook HR screwed over", "screwed over"),
                           ("We didn't want to screw Max over.", "screw max over")):
            self.assertEqual(found(text), [(said, "mild")], text)
        self.assertEqual(found("Latimer screwed us.", ["strong", "deity"]), [])

    def test_placed_with_s_on_the_last_word(self):
        for heard_it in (True, False):
            text = "Looks like Joey's other woman's got a little girl."
            line = {"s": 10.0, "e": 13.0, "text": text, "mute": True}
            heard = [[w, 10.0 + 0.3 * k, 10.25 + 0.3 * k] for k, w in enumerate(text.split())]
            st = {"path": "none.mp4", "mutes": [], "asr": heard if heard_it else [], "info": {},
                  "lines": [line], "dialogue": [line], "opts": {}}
            m = engine.word_mute(st, line, "other woman", "x", [])
            self.assertIsNotNone(m, heard_it)
            self.assertEqual(m["raw"], "other woman")
            if heard_it:
                # "other" 10.9-11.15 to "woman's" 11.2-11.45 (a little wider at the edges)
                self.assertLessEqual(m["s"], 10.9)
                self.assertGreaterEqual(m["e"], 11.45)
                self.assertLess(m["e"] - m["s"], 1.2)

    def test_screws_and_messing_up_left_alone(self):
        for text in ("He screwed him up good.", "They screwed it in tight.",
                     "Hand me the screw you dropped.", "I screwed up.",
                     "Screw the lid over the jar.", "a titanium screw with a flat head"):
            self.assertEqual(found(text), [], text)

    def test_screw_you_as_before(self):
        self.assertEqual(found("Screw you."), [("screw you", "mild")])
        self.assertEqual(found("if it is that, we're screwed."), [("we're screwed", "mild")])


class Taught(unittest.TestCase):
    def test_a_cheat_for_person_of_interest(self):
        import cleanview_learn as learn
        for text in ("Bank robber and a cheat.", "Bank robber and a cheet."):
            line = learn.norm(text)
            muted = learn._sh("person-of-interest", "muted")
            self.assertIn(line, muted)
            self.assertIn(line, learn._for_filters("person-of-interest", muted, {"casual"}))
            self.assertNotIn(line, learn._for_filters("person-of-interest", muted, {"sexref"}))

    def test_cheater_not_on_the_list(self):
        # "You big cheater!" (Gummi Bears, a game), "Are you calling me a cheater, Harold?"
        for text in ("You big cheater!", "Are you calling me a cheater, Harold?"):
            self.assertIsNone(engine.LINE_WORDS["casual"].search(text), text)


if __name__ == "__main__":
    unittest.main()
