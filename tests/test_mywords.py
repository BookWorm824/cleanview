"""Her own words and phrases to mute, typed on the start page, one per line."""
import unittest

import support  # noqa: F401  (sets up the sandbox first)
import cleanview as engine
import cvcore as cl


def found(text, mine, cats=()):
    words = [w for w in (cl.norm(t) for t in text.split()) if w]
    return [(" ".join(words[i:j]), cat) for i, j, cat in cl.find_language(words, list(cats), mine)]


class ReadingTheList(unittest.TestCase):

    def test_tidied_up(self):
        o = {"mywords": ["Grow some STONES!", "", "  nimrod  ", "nimrod", "half-wit", "f***"]}
        self.assertEqual(engine.my_words(o), [("grow", "some", "stones"), ("nimrod",),
                                              ("half", "wit"), ("fuck",)])

    def test_none_typed(self):
        self.assertEqual(engine.my_words({}), [])
        self.assertEqual(engine.my_words(engine.full_opts()), [])


class Matching(unittest.TestCase):
    mine = [("grow", "some", "stones"), ("nimrod",)]

    def test_whole_phrase_muted_even_with_nothing_ticked(self):
        self.assertEqual(found("You need to grow some stones, kid.", self.mine),
                         [("grow some stones", "mine")])
        self.assertEqual(found("Don't be a Nimrod!", self.mine), [("nimrod", "mine")])

    def test_whole_words_only(self):
        self.assertEqual(found("We passed the milestones.", [("stones",)]), [])
        self.assertEqual(found("Grow some tomatoes.", self.mine), [])

    def test_longest_phrase_wins(self):
        self.assertEqual(found("grow some stones", [("stones",), ("grow", "some", "stones")]),
                         [("grow some stones", "mine")])

    def test_alongside_the_built_in_lists(self):
        self.assertEqual(found("Damn you, nimrod", self.mine, ["mild"]),
                         [("damn", "mild"), ("nimrod", "mine")])

    def test_an_ai_may_mute_them(self):
        self.assertTrue(cl.listed_word("nimrod", self.mine))
        self.assertFalse(cl.listed_word("nimrod"))
        self.assertTrue(engine._words_listed("nimrod", self.mine))

    def test_reviewer_is_told(self):
        self.assertIn("'grow some stones'", engine.wanted_text({"mywords": ["grow some stones"]},
                                                               []))

    def test_blanked_in_the_clean_copys_subtitles(self):
        cues = engine.clean_cues([{"s": 0.0, "e": 2.0, "text": "You nimrod!"}], [], [], [], (),
                                 [("nimrod",)])
        self.assertNotIn("nimrod", cues[0]["text"].lower())


if __name__ == "__main__":
    unittest.main()
