"""Call the Midwife's Christmas special (the owner, 2026-11-17: "running a scan now to purposely
push the scanner ... i turned on christmas filter then chose a christmas holiday special"). The
nativity play, Advent and the carols went through; the nativity's "his name will be Jesus" and
"Two little dicky birds" heard as "titty birds" were muted."""
import unittest

import support  # noqa: F401  (must come first)
import cleanview as engine
import cvcore as cl

XMAS = engine.LINE_WORDS["christmas"]


def muted(text):
    words = [cl.norm(t) for t in text.split()]
    return [" ".join(words[a:b]) for a, b, _ in cl.find_language(words, list(cl.CATS), [])]


class TheNativity(unittest.TestCase):
    def test_nativity_lines_are_christmas(self):
        for line in ("We're putting our semaphore to one side this week and concentrating on "
                     "our nativity play.",
                     "The sisters spent Advent in prayer and meditation.",
                     "I've been making inquiries about a manger.",
                     "In Bethlehem, 2,000 years ago, accommodation was makeshift.",
                     "The wise men followed somewhat confused directions.",
                     "Now, I want gold, frankincense, and myrrh and the three kings to stand "
                     "at the back.",
                     "O holy night, the stars are brightly shining.",
                     "Pass me a mince pie.",
                     "We open the Advent calendar every morning.",
                     "Away in a manger, no crib for a bed."):
            self.assertTrue(XMAS.search(line), line)

    def test_not_christmas(self):
        for line in ("The advent of television changed everything.",
                     "Cuba was a surveillance state long before the advent",
                     "He's a dog in the manger about that car.",
                     "He worked at Bethlehem Steel for thirty years.",
                     "I'd like to present my report.",
                     "Shepherd's pie for tea."):
            self.assertFalse(XMAS.search(line), line)


class TheSecondSpecial(unittest.TestCase):
    """Her second special (1.18.124): carols, tinsel, reindeers and the nativity story went
    through; "the infant Jesus" had "Jesus" muted."""

    def test_christmas(self):
        for line in ("We like the right faces round the table, the right carols to be sung.",
                     "They're getting themselves in the mood for carol singing.",
                     "No, I've hung up my Carol Singer's lantern.",
                     "She'll be sprucing them up with tinsel and some glitter.",
                     "Reindeers don't have cubs, they have calves.",
                     "I feel rather like Mary when Herod decreed the colour of the firstborn and "
                     "she had to flee to Egypt with the",
                     "infant Jesus.",
                     "We went carolling round the flats.",
                     "Wrap the Christ child in swaddling clothes."):
            self.assertTrue(XMAS.search(line), line)

    def test_not_christmas(self):
        for line in ("Thank you, Carol.", "You need any help, Carol?",
                     "They live in South Carolina.", "Caroline Turing.",
                     "Hey Egypt, you throw about as good as a cross-eyed troll.",
                     "Sweet baby Jesus, look at that!", "Tinseltown is all lies."):
            self.assertFalse(XMAS.search(line), line)

    def test_the_infant_jesus_left_alone(self):
        self.assertEqual(muted("flee to Egypt with the infant Jesus."), [])
        self.assertEqual(muted("The Christ child is born."), [])
        self.assertEqual(muted("Christ, child, get down from there!"), ["christ"])


class WordsLeftAlone(unittest.TestCase):
    def test_the_nativity_names_jesus(self):
        self.assertEqual(muted("You will have a baby and his name will be Jesus."), [])
        self.assertEqual(muted("They named him Jesus."), [])
        self.assertEqual(muted("Put the baby Jesus in the manger."), [])

    def test_oaths_still_muted(self):
        self.assertEqual(muted("Sweet baby Jesus, look at that!"), ["jesus"])
        self.assertEqual(muted("Jesus, that hurt."), ["jesus"])

    def test_dicky_birds_heard_as_titty(self):
        self.assertEqual(muted("Two little titty birds sitting on the wall."), [])
        self.assertEqual(muted("Look at those titties."), ["titties"])


if __name__ == "__main__":
    unittest.main()
