"""Lauren's Castle S1E1 report (2026-11-08, adults, word lists only). The shared lessons had the
episode's lines ("I'd be happy to let you spank me", "still hoping to get lucky", "another one
of your conquests"...), taken from subtitles, but this run read what was heard, worded or split
a little differently, and only 1 of them matched exactly, so the rest went through. And she
ticked "Hell" in "right out of Hell Hath No Fury" both times it was left unticked as a title."""
import json
import unittest

import support
import cleanview as engine
import cleanview_learn as learn

LEARNED = ["shh shh shh not so loud i'm still hoping to get lucky",
           "i'd be happy to let you spank me",
           "why castle so i could be another one of your conquests",
           "and the ever popular will you sign my 'chest'",
           "a little cops gone wild you do know i'm wearing a gun",
           "how was the slammer anyone make you their bitch"]


class WordedDifferently(unittest.TestCase):

    def setUp(self):
        self.find = learn.LearnedLines(LEARNED)

    def match(self, text):
        return self.find.match(learn.norm(text))

    def test_inside_a_longer_line(self):
        self.assertEqual(self.match("But if it makes you feel any better, I'd be happy to let you "
                                    "spank me."), "i'd be happy to let you spank me")

    def test_most_of_it(self):
        self.assertEqual(self.match("Not so loud. I'm still hoping to get lucky."), LEARNED[0])

    def test_a_word_heard_differently(self):
        self.assertEqual(self.match("Why, Castle? So I can be another one of your conquests?"),
                         LEARNED[2])
        self.assertEqual(self.match('And the ever popular, "Will you sign my chest?"'), LEARNED[3])

    def test_a_harmless_piece_isnt(self):
        for text in ("You do know I'm wearing a gun?", "Not so loud.", "Why, Castle?",
                     "I'd be happy to help you with that.", "How was the trip?"):
            with self.subTest(text):
                self.assertIsNone(self.match(text))

    def test_a_short_everyday_line_stays_exact(self):
        find = learn.LearnedLines(["i don't know what happens"])
        for text in ("I don't know what happens next, honey.", "I don't know what happened."):
            with self.subTest(text):
                self.assertIsNone(find.match(learn.norm(text)))

    def test_muted_when_applied(self):
        d = learn.load("castle-test")
        d["muted"] = list(LEARNED)
        learn.save("castle-test", d)
        dialogue = [{"s": 284.4, "e": 286.8, "text": "Not so loud. I'm still hoping to get lucky."},
                    {"s": 419.5, "e": 424.0, "text": "But if it makes you feel any better, I'd be "
                                                    "happy to let you spank me."},
                    {"s": 1932.4, "e": 1934.0, "text": "You do know I'm wearing a gun?"}]
        added, _ = learn.apply("castle-test", dialogue, [], [], [])
        self.assertEqual([round(l["s"], 1) for l in added], [284.4, 419.5])
        self.assertEqual({l["learned_from"] for l in added}, {"you"})


class HellInATitle(unittest.TestCase):

    def test_still_muted_in_a_title(self):
        from test_reports_nov import subtitle_words
        sw, cue, cues = subtitle_words(["And this is how we found him, right out of Hell Hath No Fury.",
                                        "Detective Dern is here."])
        names = [sw[k] for k in range(len(sw)) if engine.name_in_subtitles(sw, cue, cues, k)]
        self.assertNotIn("Hell", names)
        self.assertIn("Dern", names)

    def test_the_shared_note_agrees(self):
        d = json.loads((support.ROOT / "shared_learned.json").read_text(encoding="utf8"))
        note = d["shows"]["castle"]["notes"][0]
        self.assertIn("still muted", note)
        self.assertNotIn("is the title of a book", note)


if __name__ == "__main__":
    unittest.main()
