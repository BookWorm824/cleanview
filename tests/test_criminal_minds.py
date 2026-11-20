"""The owner's Criminal Minds S1E1 report (1.18.125, 2026-11-17, adults, the AI helper, made on
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


class Episode9(unittest.TestCase):
    """Her S1E9 report (1.18.139, made on 1.18.135; the owner: "Yes, fix both")."""

    def check(self, said, heard):
        import cvcore as cl
        sw = [w for w in engine.spoken_words(said) if cl.norm(w)]
        sn = [cl.norm(w) for w in sw]
        asr_n = [cl.norm(w) for w in heard.split()]
        mutes = [{"src": "audio", "at": i, "cat": cat, "raw": " ".join(asr_n[i:j])}
                 for i, j, cat in cl.find_language(asr_n, list(cl.CATS))]
        engine.subtitle_word_there(mutes, cl.align(sn, asr_n), sw, sn, asr_n)
        return mutes

    def test_elle_heard_out_of_order(self):
        # "hell" twice where the captions say "MORGAN: WHAT? ELLE." / "ELLE? WHAT?", heard in
        # another order, so not lined up with them
        mutes = self.check("A TRAIN IN TEXAS? MY GOD. Morgan: WHAT? ELLE. ELLE? WHAT? "
                           "Gideon: ROBERT OXTON BOLTON WROTE,",
                           "a train in texas my god hell hell what what robert oxton bolton wrote")
        hells = [m for m in mutes if m["raw"] == "hell"]
        self.assertEqual(len(hells), 2)
        for m in hells:
            self.assertTrue(m.get("keep"), "misheard: offered unticked")
            self.assertIn("ELLE", m["sub"])
        god = [m for m in mutes if m["raw"] == "my god"]
        self.assertFalse(god[0].get("keep"))

    def test_said_out_of_order_stays_muted(self):
        mutes = self.check("A TRAIN IN TEXAS? MY GOD. WHAT? HELL. ELLE? WHAT? "
                           "ROBERT OXTON BOLTON WROTE,",
                           "a train in texas my god hell what elle what robert oxton bolton wrote")
        self.assertFalse([m for m in mutes if m["raw"] == "hell"][0].get("keep"))

    def test_screw_the(self):
        import cvcore as cl
        cats = [c for g in ("swearing", "mild", "deity", "minced", "rude") for c in cl.GROUPS[g]]

        def muted(text):
            words = [w for w in (cl.norm(t) for t in text.split()) if w]
            return [" ".join(words[i:j]) for i, j, _ in cl.find_language(words, cats)]
        self.assertEqual(muted("SCREW THE GOVERNMENT."), ["screw the government"])
        self.assertEqual(muted("Screw the show and the Greenwoods."), ["screw the show"])
        for text in ("Screw the lid on tight.", "Screw the bulb back in.",
                     "Just screw the cap on.", "Screw the pieces together.",
                     "I want to screw the bracket to the wall."):
            self.assertEqual(muted(text), [], text)


class Episode11(unittest.TestCase):
    """Her S1E11 report (1.18.141, made on 1.18.139)."""

    def test_wish_to_god(self):
        import cvcore as cl
        cats = [c for g in ("swearing", "mild", "deity") for c in cl.GROUPS[g]]

        def muted(text):
            words = [w for w in (cl.norm(t) for t in text.split()) if w]
            return [" ".join(words[i:j]) for i, j, _ in cl.find_language(words, cats)]
        self.assertEqual(muted("I WISH TO GOD HE'D NEVER SPOKEN TO YOU!"), ["wish to god"])
        self.assertEqual(muted("And I hope to God I can."), ["hope to god"])
        self.assertEqual(muted("I pray to God he's all right."), [])

    def lines(self, heard_shift=None, heard_same=False):
        """Ten subtitle lines of three words, line k at 10k s, heard word for word; the
        third line's words ("oh god forgive") lined up with the sixth line's heard words."""
        import cvcore as cl
        texts = ["it ain't right", "i'm so sorry", "oh god forgive"] + \
                [f"word{k} more{k} yet{k}" for k in range(3, 10)]
        cues = [{"s": 10.0 * k, "e": 10.0 * k + 3, "text": t} for k, t in enumerate(texts)]
        sw, sw_cue = [], []
        for ci, c in enumerate(cues):
            for w in engine.spoken_words(c["text"]):
                sw.append(w)
                sw_cue.append(ci)
        sn = [cl.norm(w) for w in sw]
        asr = [{"s": cues[k // 3]["s"] + (k % 3), "e": cues[k // 3]["s"] + (k % 3) + 0.8,
                "part": 0} for k in range(len(sn))]
        asr_n = list(sn)
        mapping = list(range(len(sn)))
        if heard_shift:
            for k in range(6, 9):
                mapping[k] = k + heard_shift
                if heard_same:
                    asr_n[k + heard_shift] = sn[k]
        return sn, asr_n, asr, mapping, engine.sub_word_where(sw_cue, cues)

    def test_lined_up_with_the_wrong_words(self):
        # "OH, GOD, FORGIVE ME." at 12:59 muted at 13:13, over "I'M SORRY!"
        sn, asr_n, asr, mapping, where = self.lines(heard_shift=9)
        s = asr[mapping[6]]["s"]
        there = engine.sub_place_slipped(6, 8, s, mapping, sn, asr_n, asr, where)
        self.assertIsNotNone(there)
        self.assertLess(abs(there - where[6]), 1.0)

    def test_placed_right_stays(self):
        sn, asr_n, asr, mapping, where = self.lines()
        self.assertIsNone(engine.sub_place_slipped(6, 8, asr[6]["s"], mapping, sn, asr_n,
                                                   asr, where))

    def test_heard_right_there_stays(self):
        # a song's "God knows" heard where it was placed, its subtitle line earlier
        sn, asr_n, asr, mapping, where = self.lines(heard_shift=9, heard_same=True)
        self.assertIsNone(engine.sub_place_slipped(6, 8, asr[mapping[6]]["s"], mapping, sn,
                                                   asr_n, asr, where))


if __name__ == "__main__":
    unittest.main()
