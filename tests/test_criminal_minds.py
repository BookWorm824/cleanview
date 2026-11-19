"""Lauren's Criminal Minds S1E1 report (1.18.125, 2026-11-17, adults, the AI helper, made on
1.18.122; the owner: "yes fi them", "and the subtitle look up also"). "Criminal Minds - 1-1 --
Extreme Aggressor.m4v" was looked up as a movie (the wrong subtitles, 3% lined up) and learned
under movies; its rape case talk went through with coroner and detective talk ticked; and the
taunt's first line went through while the two after it were muted."""
import json
import unittest

import support  # noqa: F401  (must come first)
import cleanview as engine
import cleanview_learn as learn

FORENSIC = engine.LINE_WORDS["forensic"]


class TheName(unittest.TestCase):
    def test_season_dash_episode(self):
        self.assertEqual(engine.guess_title("Criminal Minds - 1-1 -- Extreme Aggressor.m4v"),
                         ("Criminal Minds", 1, 1))
        self.assertEqual(engine.guess_title("Criminal Minds - 2-14 - Sex, Birth, Death.m4v"),
                         ("Criminal Minds", 2, 14))
        self.assertEqual(engine.guess_title("Criminal Minds - 1-1.m4v"), ("Criminal Minds", 1, 1))
        self.assertEqual(learn.show_key(engine.guess_title(
            "Criminal Minds - 1-1 -- Extreme Aggressor.m4v")), "criminal-minds")

    def test_still_movies(self):
        for name in ("Apollo 13 - 1-1 Draft.mp4", "Ocean 11 - 2-3.mp4",
                     "Star Wars - 4-6 Collection.mkv"):
            self.assertIsNone(engine.guess_title(name)[1], name)


class RapeCaseTalk(unittest.TestCase):
    def test_coroner_and_detective_talk(self):
        for line in ("Murders have all involved rapes.",
                     "But rape without penetration is a form of voyeurism.",
                     "The last four murderers show he's an anger excitation rapist.",
                     "In 1979, they outfitted a van to rape and murder girls in California.",
                     "She was raped.", "slips them a sedative, then rapes them."):
            self.assertTrue(FORENSIC.search(line), line)

    def test_not_rape(self):
        for line in ("My therapist says hi.", "Grape juice, please.", "The rapeseed fields.",
                     "Hand me the rapier."):
            self.assertFalse(FORENSIC.search(line), line)

    def test_without_penetration_is_explicit(self):
        self.assertTrue(engine.EXPLICIT_FINDING.search(
            "But rape without penetration is a form of voyeurism"))


class TheTaunt(unittest.TestCase):
    def test_taught_for_the_show(self):
        with open(support.ROOT / "shared_learned.json", encoding="utf-8") as f:
            show = json.load(f)["shows"]["criminal-minds"]
        line = learn.norm("What'd they come up with when you fumbled your way into some girl's "
                          "pants and she started laughing when she got a good look at just")
        self.assertIn(line, show["muted"])
        self.assertEqual(show["muted_for"][line], "sexref")


class Episode3(unittest.TestCase):
    """Her S1E3 report (1.18.133, made on 1.18.129; the owner: "Yes, fix them")."""

    def test_hooked_up_with_an_agency_is_teaming_up(self):
        casual = engine.LINE_WORDS["casual"]
        for line in ("MORGAN HOOKED UP WITH ATF.", "I hooked up with the FBI in Boston.",
                     "We'll hook up with the team later.", "He hooked up with local P.D."):
            self.assertIsNone(casual.search(line), line)
        for line in ("BUT ONLY BECAUSE HE FOUND OUT I HOOKED UP WITH BRANDON.",
                     "We'll hook up with someone.", "She hooked up with him last night."):
            self.assertIsNotNone(casual.search(line), line)

    def test_impotent(self):
        sexref = engine.LINE_WORDS["sexref"]
        self.assertIsNotNone(sexref.search("YEAH. HE'S IMPOTENT."))
        self.assertIsNotNone(sexref.search("It's about his impotence."))
        for line in ("Our existing medications are likely impotent against it.",
                     "He shook with impotent rage."):
            self.assertIsNone(sexref.search(line), line)

    def test_two_lines_taught(self):
        with open(support.ROOT / "shared_learned.json", encoding="utf-8") as f:
            show = json.load(f)["shows"]["criminal-minds"]
        for said in ("SIGNATURE'S THE THING THAT THEY GET OFF ON,",
                     "GIVES THEM AN EMOTIONAL OR SEXUAL RELEASE."):
            line = learn.norm(said)
            self.assertIn(line, show["muted"])
            self.assertEqual(show["muted_for"][line], "sexref")


class Episode5(unittest.TestCase):
    """Her S1E5 report (1.18.133, made on 1.18.132): "my god" heard where the subtitles say
    "You're killing my daughter!" was muted; only a phrase's first word was compared."""

    def check(self, said, heard, raw):
        import cvcore as cl
        sw = said.split()
        sn = [cl.norm(w) for w in sw]
        asr_n = [cl.norm(w) for w in heard.split()]
        mapping = cl.align(sn, asr_n)
        at = asr_n.index(raw.split()[0])
        m = {"at": at, "src": "audio", "cat": "deity", "raw": raw, "word": raw}
        engine.subtitle_word_there([m], mapping, sw, sn, asr_n)
        return m

    def test_a_phrase_the_subtitles_have_other_words_for(self):
        m = self.check("Do you- You're killing my daughter! Pick up that phone!",
                       "do you you're killing my god pick up that phone", "my god")
        self.assertEqual(m.get("sub"), "daughter!")
        self.assertTrue(m.get("keep"), "misheard: offered unticked")
        m = self.check("We walked down to the park this morning. Is that my dog? Sit, boy.",
                       "we walked down to the park this morning is that my god sit boy",
                       "my god")
        self.assertTrue(m.get("keep"))

    def test_a_phrase_that_was_said(self):
        m = self.check("Oh, my God. What happened?", "oh my god what happened", "my god")
        self.assertFalse(m.get("keep"))
        self.assertNotIn("sub", m)


class Episode8(unittest.TestCase):
    """Her S1E8 report (1.18.136, made on 1.18.135, Young kids; the owner: "Yes, teach them"):
    Gideon's interrogation and two jokes went through; taught for the show, every age."""

    def lessons(self):
        with open(support.ROOT / "shared_learned.json", encoding="utf-8") as f:
            show = json.load(f)["shows"]["criminal-minds"]
        return show, learn.LearnedLines(show["muted"])

    def test_taught(self):
        show, ll = self.lessons()
        for said in ("I THINK HE DOES THOSE LATE NIGHT COMMERCIALS",
                     "THERE'S NO EVIDENCE THIS GUY CAN'T PERFORM.",
                     "IS IT THE ONLY THING THAT CAN GIVE YOU A SEXUAL RELEASE?",
                     "TAKE THESE OFF AND WE'LL SEE.",
                     "10 BUCKS SAYS THIS INVOLVES NAKED COEDS AND A PLUMBER.",
                     "HIS THURSDAY NIGHTS WITH A WOMAN IN FELLS POINT."):
            self.assertTrue(ll.match(learn.norm(said)), said)
        for line in show["muted"]:
            self.assertEqual(show["muted_for"][line], "sexref")

    def test_the_handcuffs_line_stays(self):
        _, ll = self.lessons()
        self.assertFalse(ll.match(learn.norm("TAKE THESE OFF AND WE'LL REALLY TALK.")))

    def test_sexual_release_listed(self):
        sexref = engine.LINE_WORDS["sexref"]
        self.assertIsNotNone(sexref.search("Is it the only thing that can give you a sexual release?"))
        self.assertIsNotNone(sexref.search("Gives them an emotional or sexual release."))


if __name__ == "__main__":
    unittest.main()
