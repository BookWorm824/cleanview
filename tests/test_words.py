"""Swear words getting through: words missing from the lists, swears bleeped in
subtitles ("f***ing"), phrases ("shut up", "screw you"), and a subtitle word
dropped because another word was muted close by."""
import unittest

import support  # noqa: F401  (sets up the sandbox first)
import cleanview as engine
import cvcore as cl

EVERY_GROUP = list(cl.CATS)


def found(text, cats=EVERY_GROUP):
    """The words of `text` that would be muted, with their list."""
    words = [cl.norm(w) for w in text.split()]
    words = [w for w in words if w]
    return [(" ".join(words[i:j]), cat) for i, j, cat in cl.find_language(words, cats)]


class MissingWords(unittest.TestCase):

    def test_now_found(self):
        for word, cat in [("goddammit", "mild"), ("godammit", "mild"), ("sonofabitch", "moderate"),
                          ("sonuvabitch", "moderate"), ("asshat", "moderate"),
                          ("asskicking", "moderate"), ("dangit", "minced"), ("omigod", "deity"),
                          ("ohmygod", "deity"), ("craphole", "mild"), ("bullcrap", "mild"),
                          ("goshdarn", "minced"), ("jeeze", "minced"), ("frick", "minced")]:
            with self.subTest(word=word):
                self.assertIn(cat, [c for _, c in found(word, [cat])])
                self.assertTrue(cl.listed_word(word))

    def test_with_punctuation_and_capitals(self):
        self.assertEqual(found("Goddammit, Castle!"), [("goddammit", "mild")])

    def test_innocent_words_still_left_alone(self):
        for text in ("a glass of water", "the class assistant", "hello shell", "scrap metal",
                     "Gruffi and Grammi", "a dangerous road"):
            with self.subTest(text=text):
                self.assertEqual(found(text), [])


class BleepedSubtitles(unittest.TestCase):

    def test_bleeps_read_as_the_word(self):
        for bleeped, word in [("f***", "fuck"), ("F***ing", "fucking"), ("f**king", "fucking"),
                              ("s**t", "shit"), ("s***", "shit"), ("bulls**t", "bullshit"),
                              ("a**hole", "asshole"), ("b****", "bitch"), ("d*mn", "damn"),
                              ("h***", "hell"), ("G*d", "god"), ("motherf***er", "motherfucker"),
                              ("f--k", "fuck"), ("#@$%", "fuck"), ("f***!", "fuck")]:
            with self.subTest(bleeped=bleeped):
                self.assertEqual(cl.norm(bleeped), word)

    def test_ordinary_text_untouched(self):
        for text, same in [("#1", "1"), ("x-ray", "xray"), ("well--", "well"), ("$5", "5"),
                           ("*", ""), ("hello", "hello"), ("Hey!", "hey")]:
            with self.subTest(text=text):
                self.assertEqual(cl.norm(text), same)

    def test_found_in_a_subtitle_line(self):
        self.assertEqual(found("What the f*** is that?", ["strong"]), [("fuck", "strong")])
        self.assertEqual(found("That's bulls**t.", ["moderate"]), [("bullshit", "moderate")])


class Phrases(unittest.TestCase):

    def test_ai_may_mute_phrases_on_the_lists(self):
        for phrase in ("shut up", "Shut up!", "screw you", "you suck", "shut your mouth",
                       "oh my god", "oh shut up"):
            with self.subTest(phrase=phrase):
                self.assertTrue(cl.listed_word(phrase))

    def test_names_and_ordinary_words_still_not_listed(self):
        for word in ("Grafi", "Gruffi", "nice day", "shut", "screw"):
            with self.subTest(word=word):
                self.assertFalse(cl.listed_word(word))

    def test_screw_you_is_mild_language(self):
        self.assertEqual(found("oh screw you", ["mild"]), [("screw you", "mild")])
        self.assertEqual(found("oh screw you", ["moderate"]), [("screw you", "moderate")])

    def test_not_rude_when_its_about_doing_something(self):
        for text, cats in [("shut it down now", ["rude"]), ("screw it in tightly", ["mild"]),
                           ("screw them on to the wall", ["mild"]), ("shut it off", ["rude"])]:
            with self.subTest(text=text):
                self.assertEqual(found(text, cats), [])

    def test_still_rude(self):
        self.assertEqual(found("just shut it", ["rude"]), [("shut it", "rude")])
        self.assertEqual(found("shut up", ["rude"]), [("shut up", "rude")])
        self.assertEqual(found("screw it let's go", ["mild"]), [("screw it", "mild")])


class SlangForPrivateParts(unittest.TestCase):
    """"Grow some stones": stones, balls and nuts are only slang in these phrases."""

    def test_whole_phrase_muted(self):
        for text, phrase in [("Grow some stones, Castle.", "grow some stones"),
                             ("You need to grow a pair.", "grow a pair"),
                             ("He finally grew some balls", "grew some balls"),
                             ("Nobody has the balls to say it", "has the balls to"),
                             ("She kicked him in the nuts", "kicked him in the nuts"),
                             ("You've got some stones, kid", "you've got some stones"),
                             ("That's ballsy", "ballsy"), ("Show some cojones", "cojones")]:
            with self.subTest(text=text):
                self.assertEqual(found(text, ["moderate"]), [(phrase, "moderate")])

    def test_everyday_stones_balls_and_nuts_left_alone(self):
        for text in ("I got some stones for the garden", "Grab the tennis balls",
                     "a bag of mixed nuts", "Kidney stones hurt", "We grow some tomatoes",
                     "the stones in the wall", "He's nuts", "Rolling Stones concert",
                     "a pair of shoes", "grow up"):
            with self.subTest(text=text):
                self.assertEqual(found(text), [])

    def test_ai_may_mute_the_phrase_but_not_the_plain_word(self):
        self.assertTrue(cl.listed_word("grow some stones"))
        self.assertFalse(cl.listed_word("stones"))

    def test_reviewer_is_told(self):
        self.assertIn("grow some stones", engine.wanted_text({}, ["swearing"]))


class ShortForms(unittest.TestCase):
    """D-bag, SOB and ball buster. "sob" is also a real word, so it only counts written
    as an abbreviation (capitals or dots) or spelled out."""

    def test_caught(self):
        for text, phrase in [("You SOB!", "sonofabitch"), ("You S.O.B.", "sonofabitch"),
                             ("those SOBs", "sonofabitch"), ("you s o b", "s o b"),
                             ("What a D-bag.", "douchebag"), ("Those d-bags", "douchebag"),
                             ("Total dbag", "douchebag"), ("You d bag", "d bag"),
                             ("She's a ball buster", "ball buster"),
                             ("ball-buster", "ballbuster"), ("ballbusting boss", "ballbusting"),
                             ("Quit busting my balls", "busting my balls")]:
            with self.subTest(text=text):
                self.assertEqual(found(text, ["moderate"]), [(phrase, "moderate")])

    def test_everyday_words_left_alone(self):
        for text in ("She let out a sob.", "It's a sob story", "He sobbed", "a bag of chips",
                     "D. Bagwell", "the ball bounced", "bust a move"):
            with self.subTest(text=text):
                self.assertEqual(found(text), [])

    def test_ai_may_mute_them(self):
        for word in ("D-bag", "SOB", "ball buster"):
            self.assertTrue(cl.listed_word(word))
        self.assertFalse(cl.listed_word("sob"))

    def test_shown_masked(self):
        self.assertEqual(cl.mask("S.O.B."), "S**")
        self.assertEqual(cl.mask("D-bag"), "D***")


class SubtitleWordsNearOtherMutes(unittest.TestCase):
    """'what the hell, damn it': listening caught "damn", the subtitles add "hell"
    half a second earlier. That's another word, not the same one twice."""

    damn = {"s": 1.5, "e": 1.8, "raw": "damn"}

    def test_another_word_close_by_is_added(self):
        self.assertFalse(engine.already_muted([self.damn], "hell", 1.0, 1.3))

    def test_the_same_word_is_not_added_twice(self):
        self.assertTrue(engine.already_muted([self.damn], "damn", 1.6, 1.9))

    def test_a_word_already_inside_a_mute_is_not_added(self):
        self.assertTrue(engine.already_muted([self.damn], "dang", 1.52, 1.78))


if __name__ == "__main__":
    unittest.main()
