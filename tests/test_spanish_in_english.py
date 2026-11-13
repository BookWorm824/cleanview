"""A short list of Spanish swear words on the English lists (1.18.86; the owner, 2026-11-13,
asked whether loading known Spanish swear words into the English filter would help: "add the
short list and we will look at the other option later").

A mostly English video with some Spanish in it is cleaned as English, so the Spanish word lists
aren't used. These few are unmistakable (they mean nothing else in English) and are caught
where the subtitles spell them out, or where the English listening happens to hear them. Words
that are ordinary English words or names are left off: "con", "concha", "polla", and "coño",
which English spelling turns into "coo"."""
import unittest

import support
import cvcore as cl

ALL = list(cl.CATS)
SWEARING = cl.GROUPS["swearing"]


def found(text, cats=ALL):
    words = [w for w in (cl.norm(t) for t in text.split()) if w]
    return [(" ".join(words[i:j]), cat) for i, j, cat in cl.find_language(words, cats, ())]


class SpanishWordsInAnEnglishVideo(unittest.TestCase):
    def test_the_short_list(self):
        for text, word in (("You hijo de puta, get out of my house.", "puta"),
                           ("He called her a puta in front of everyone.", "puta"),
                           ("Shut your mouth, puto.", "puto"),
                           ("Those putos took my truck.", "putos"),
                           ("Listen to me, pendejo.", "pendejo"),
                           ("Don't be a pendeja about it.", "pendeja"),
                           ("That cabron owes me money.", "cabron"),
                           ("Those cabrones are back again.", "cabrones"),
                           ("Joder, that was close.", "joder"),
                           ("The whole deal is jodido now.", "jodido"),
                           ("Vete al carajo, amigo.", "carajo"),
                           ("Chinga tu madre, he yelled.", "chinga"),
                           ("Hijo de la chingada, he muttered.", "chingada"),
                           ("He is a chingon and he knows it.", "chingon"),
                           ("What a gilipollas that guy is.", "gilipollas")):
            with self.subTest(text):
                self.assertEqual(found(text, SWEARING), [(word, "moderate")])

    def test_written_with_their_accents(self):
        # English spelling drops an accented letter: "cabrón" is read as "cabrn"
        self.assertEqual(found("That cabrón owes me money.", SWEARING), [("cabrn", "moderate")])
        self.assertEqual(found("He is a chingón and he knows it.", SWEARING),
                         [("chingn", "moderate")])
        self.assertEqual(found("Jódete, he said, and left.", SWEARING), [("jdete", "moderate")])

    def test_the_slur_goes_with_the_same_sex_words(self):
        self.assertEqual(found("He called him a maricon and walked off.", cl.GROUPS["samesexwords"]),
                         [("maricon", "samesex")])
        self.assertEqual(found("He called him a maricón and walked off.", cl.GROUPS["samesexwords"]),
                         [("maricn", "samesex")])
        self.assertEqual(found("He called him a maricon and walked off.", SWEARING), [])

    def test_already_there(self):
        self.assertEqual(found("Mierda, I left the keys inside.", SWEARING), [("mierda", "moderate")])

    def test_only_with_swearing_ticked(self):
        self.assertEqual(found("Listen to me, pendejo.", cl.GROUPS["mild"]), [])

    def test_an_ai_may_mute_them_alone(self):
        for word in ("puta", "pendejo", "cabrón", "joder", "carajo", "chingada", "gilipollas"):
            self.assertTrue(cl.listed_word(word), word)

    def test_everyday_english_is_left_alone(self):
        for text in ("The dove's soft coo woke her up.",
                     "We ordered chili con carne for the table.",
                     "Mrs. Concha Ortiz teaches third grade.",
                     "Mr. Ching and Mrs. Chang arrived at noon.",
                     "The computer was put away for the night.",
                     "He put a pole in the ground by the garage.",
                     "She studied the Carajas mine in Brazil.",
                     "The carbon fiber layup is on page nine.",
                     "Jody and Jodie joined the choir.",
                     "A Puerto Rican flag hung over the door."):
            with self.subTest(text):
                self.assertEqual(found(text), [])


if __name__ == "__main__":
    unittest.main()
