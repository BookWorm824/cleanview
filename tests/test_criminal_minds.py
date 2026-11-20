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
        # S1E19's boyfriend line is same-sex; S1E20's mother's affairs are sleeping around
        other = {"he didn't point the finger at his boyfriend": "samesex",
                 "what did she pick men up": "casual",
                 "but because she was a cheater he also saw her as a sinner": "casual"}
        for line in show["muted"]:
            self.assertEqual(show["muted_for"][line], other.get(line, "sexref"), line)

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

class Episode19(unittest.TestCase):
    """Her S1E19 report (1.18.149, made on 1.18.145, adults, the AI helper; the owner: "All of
    them"): "sex criminals" had "sex" muted while six "sex crimes" played; the boyfriend line and
    the explicit knife line went through; three scenes taught for the episode."""

    # (start, text) of her copy's subtitles around the three scenes; each ends at the next
    CUES = [(146.38, "LET ME GET YOU MORE TO DRINK."), (156.63, "BUT I AM GETTING OLDER. I NEED HELP."),
            (171.63, "NO."), (173.17, "NO! NO!"),
            (185.95, "HEY, WHAT'S UP WITH THAT? WHAT'S THAT ALL ABOUT?"),
            (189.5, "IT'S OK. IT'S OK."),
            (2209.9, "HELLO?"), (2210.9, "ARE YOU ALL RIGHT?"), (2213.2, "CAN YOU HEAR ME?"),
            (2222.3, "HOTCH!"), (2225.3, "WE'RE A LITTLE LATE."),
            (2228.2, "SOUVENIRS FOR HIS MOTHER?"), (2229.3, "ANNA'S NECKLACE."),
            (2233.6, "ELLE, LOOK AT THIS."), (2236.7, "HIS RAPE VICTIMS."),
            (2346.2, "MILAGROS VILLANUEVA."), (2349.1, "HE'S GONNA KILL HER MOTHER."),
            (2374.5, "Elle: MORGAN?"), (2403.3, "ELLE."), (2405.2, "OVER HERE!"),
            (2411.5, "GOT ME?"), (2412.6, "Elle: GOT YOU."),
            (2437.7, "HE PRETENDED TO BE A WOMAN."), (2439.9, "NOW HE DOESN'T HAVE TO PRETEND."),
            (2466.7, "MUCHAS GRACIAS.")]

    def dialogue(self):
        c = self.CUES
        return [{"s": s, "e": min(s + 2.5, c[i + 1][0] - 0.1) if i + 1 < len(c) else s + 2.5,
                 "text": t} for i, (s, t) in enumerate(c)]

    def scenes(self, ticked, episode=(1, 19)):
        return learn.title_scenes("criminal-minds@adults", "Criminal Minds", self.dialogue(),
                                  ticked, episode=episode)

    def test_sex_criminals_is_case_talk(self):
        sexref = engine.LINE_WORDS["sexref"]
        for line in ("BRINGING IN THE SEX CRIMINALS.", "HE GRADUALLY ESCALATED FROM SEX CRIMES.",
                     "A KNOWN SEX CRIMINAL."):
            self.assertIsNone(sexref.search(line), line)
            self.assertTrue(FORENSIC.search(line), line)
        self.assertIsNotNone(sexref.search("They had sex."))

    def test_two_lines_taught(self):
        with open(support.ROOT / "shared_learned.json", encoding="utf-8") as f:
            show = json.load(f)["shows"]["criminal-minds"]
        ll = learn.LearnedLines(show["muted"])
        for said, kind in (("HE DIDN'T POINT THE FINGER AT HIS BOYFRIEND.", "samesex"),
                           ("AND THEN ABUSES THEM SEXUALLY WITH THE KNIFE.", "sexref")):
            self.assertTrue(ll.match(learn.norm(said)), said)
            self.assertEqual(show["muted_for"][learn.norm(said)], kind)

    def test_the_episode(self):
        self.assertEqual(engine.episode_of("Criminal Minds - 1-19 -- Machissmo.m4v"), (1, 19))
        self.assertIsNone(engine.episode_of("Forest Gump.mp4"))
        self.assertIsNone(engine.episode_of(None))

    def test_three_scenes(self):
        got = self.scenes({"disturbing", "gore"})
        self.assertEqual(len(got), 3)
        opening, house, end = sorted(got, key=lambda s: s["s"])
        # from the end of "I need help" to just before the next scene's first line
        self.assertEqual(opening["kind"], ["Disturbing"])
        self.assertAlmostEqual(opening["s"], 159.13, places=1)
        self.assertAlmostEqual(opening["e"], 185.75, places=1)
        self.assertEqual(house["kind"], ["Gore"])
        self.assertLess(house["s"], 2222.3)              # before "HOTCH!": the body found
        self.assertGreater(house["e"], 2233.6)           # through the necklace
        self.assertEqual(end["kind"], ["Disturbing"])
        self.assertLess(end["s"], 2374.5)                # the attack before the team comes
        self.assertGreater(end["e"], 2441.0)             # "...doesn't have to pretend"
        for sc in got:
            self.assertTrue(sc["sure"])

    def test_only_with_their_filters(self):
        self.assertEqual(self.scenes({"sexref", "violence"}), [])
        self.assertEqual([s["kind"] for s in self.scenes({"graphic"})], [["Gore"]])
        self.assertEqual(len(self.scenes({"disturbing"})), 2)

    def test_only_that_episode(self):
        self.assertEqual(self.scenes({"disturbing", "gore"}, episode=(1, 18)), [])
        self.assertEqual(self.scenes({"disturbing", "gore"}, episode=None), [])
        self.assertEqual(learn.title_scenes("criminal-minds", "Castle", self.dialogue(),
                                            None, episode=(1, 19)), [])

    def test_movies_still_placed(self):
        # a scene with no "episode" (Forest Gump's) doesn't need one
        lines = [{"s": 0.0, "e": 2.0, "text": "He's on vacation."},
                 {"s": 20.0, "e": 22.0, "text": "You don't say much, do you?"}]
        got = learn.title_scenes("_movies@adults", "Forest Gump", lines, {"sex"})
        self.assertEqual([(s["s"], s["e"]) for s in got], [(2.0, 22.5)])


class Episode20(unittest.TestCase):
    """Her S1E20 report (1.18.152, made on 1.18.149, adults, the AI helper, coroner talk off; the
    owner: "All of them"): case talk the AI helper called sexual was muted whole; "unfaithful",
    "infidelity" and three lines went through; three disturbing scenes weren't cut."""

    CASE = "THAT SOUNDS LIKE STATUTORY RAPE. I'M NOT SURPRISED. YOU TALK TO HOTCH?"
    # (start, text) of her copy's subtitles around the scenes; each ends at the next
    CUES = [(1141.53, "NO. I'M SAYING YOU'RE MAKING EXCUSES."),
            (1143.13, "I'M NOT SURE IT DID HIM ANY FAVORS."), (1159.31, "YOU'RE GONNA BE OK."),
            (1199.17, "WAKE UP."),
            (1217.4, "BASED ON THESE INTERVIEWS, IT LOOKS LIKE THE FIRST VICTIM WASN'T BEING "
                     "UNFAITHFUL."),
            (1863.6, "BUT HE PROTECTED ONE,"),
            (1865.4, "AND NOW AT LEAST 6 WOMEN ARE DEAD BECAUSE OF IT."), (1872.89, "COME ON."),
            (1873.91, "MOVE IT."), (1879.57, "NO!"),
            (1899.16, "HEY, CAN'T BE IN THE POOL WITH YOUR CLOTHES ON."),
            (1906.1, "HELP ME. IT'S MY WIFE. SHE FELL IN THE POOL."),
            (1919.64, "WELL, SHE'S NOT BREATHING."),
            (1923.27, "LOOK, MAN, I'M DOING THE BEST THAT I CAN."),
            (1946.4, "YOU'RE BREATHING. THERE YOU GO, HONEY."),
            (1958.2, "FOUND OTHER SUSPICIOUS DROWNINGS THE LAST COUPLE OF DAYS?"),
            (2291.9, "YOU GUYS HEAR THAT?"), (2294.39, "IT'S OVER THERE. COME ON, LET'S GO."),
            (2345.12, "NO!"), (2346.96, "PLEASE!"),
            (2348.45, "NO ONE WILL HEAR YOU. SOMEBODY HELP ME!"),
            (2351.21, "IT'S JUST THE TWO OF US OUT HERE."),
            (2369.86, "IT'S CLEAR. NOBODY IN THE CAR."),
            (2374.26, "WE'RE GOING INTO THE WOODS. KEEP YOU POSTED."),
            (2384.88, "HELP ME!"), (2386.26, "HELP ME!"), (2388.1, "SOMEBODY HELP!"),
            (2389.46, "THAT'S COMING FROM UP OVER THERE."), (2393.0, "NO!"),
            (2441.81, "MARK GREGORY, FBI! PUT IT DOWN!"),
            (2451.4, "COME HERE. I GOT YOU."), (2454.0, "OK.")]

    def dialogue(self):
        c = self.CUES
        return [{"s": s, "e": min(s + 2.5, c[i + 1][0] - 0.1) if i + 1 < len(c) else s + 2.5,
                 "text": t} for i, (s, t) in enumerate(c)]

    def test_case_talk_offered_unticked(self):
        self.assertTrue(engine.case_talk_only(self.CASE, {"sexref"}))
        lines = [{"s": 652.7, "e": 655.9, "text": self.CASE}]
        o = engine.full_opts({"sexref": True, "forensic": False})
        out, _ = engine.find_lines(lines, o, False, claude_found={0: {"sexref"}})
        self.assertFalse(out[0]["mute"])
        self.assertEqual(out[0]["why"], engine.CASE_TALK_UNTICKED)
        o["forensic"] = True                  # coroner talk ticked: muted as before
        out, _ = engine.find_lines(lines, o, False, claude_found={0: {"sexref"}})
        self.assertTrue(out[0]["mute"])

    def test_innuendo_beside_case_talk_still_muted(self):
        for t in ("HAD AN INTENSE AFFECTION FOR LADIES WITH LEARNER'S PERMITS.",
                  "HE RAPED HER, THEN HAD SEX WITH HER SISTER.", "SIGNS OF FORCED PENETRATION."):
            self.assertFalse(engine.case_talk_only(t, {"sexref"}), t)
        self.assertFalse(engine.case_talk_only(self.CASE, {"sexref", "casual"}))

    def test_unfaithful_and_infidelity(self):
        casual = engine.LINE_WORDS["casual"]
        for t in ("MARK WAS OBSESSED WITH THINKING SHE WAS UNFAITHFUL.", "WAS SHE BEING UNFAITHFUL?",
                  "THAT EXPLAINS HIS ISSUES WITH INFIDELITY,"):
            self.assertTrue(casual.search(t), t)
        self.assertIsNone(casual.search("the wicked and unfaithful servant"))

    def test_three_lines_taught(self):
        with open(support.ROOT / "shared_learned.json", encoding="utf-8") as f:
            show = json.load(f)["shows"]["criminal-minds"]
        ll = learn.LearnedLines(show["muted"])
        for said, kind in (("YOU'RE GETTIN' SOME LOVIN', AREN'T YOU? YOU GOT A BOYFRIEND.", "sexref"),
                           ("WHAT? DID SHE PICK MEN UP?", "casual"),
                           ("BUT BECAUSE SHE WAS A CHEATER, HE ALSO SAW HER AS A SINNER.", "casual")):
            self.assertTrue(ll.match(learn.norm(said)), said)
            self.assertEqual(show["muted_for"][learn.norm(said)], kind)

    def test_her_four_cuts(self):
        # 1.18.153: her own edges after her review (the owner: "like this has a cut of a minute
        # and a half", "when the man is saving her from the pool doesn't need cut", "15" seconds
        # of the agents by the bushes; her refined report): torture 19:10-20:08, the pool 31:25-
        # 32:03, and the creek in two, the grab 39:04-39:14 and the drowning 39:46-40:42
        got = learn.title_scenes("criminal-minds@adults", "Criminal Minds", self.dialogue(),
                                 {"disturbing"}, episode=(1, 20))
        self.assertEqual([s["kind"] for s in got], [["Disturbing"]] * 4)
        self.assertEqual([(round(s["s"], 1), round(s["e"], 1))
                          for s in sorted(got, key=lambda s: s["s"])],
                         [(1150.0, 1208.0), (1885.0, 1923.0), (2344.0, 2354.0), (2386.0, 2442.0)])

    def test_edges_follow_the_lines(self):
        # another copy, 2.5 s later throughout: the same cuts 2.5 s later
        later = [dict(l, s=l["s"] + 2.5, e=l["e"] + 2.5) for l in self.dialogue()]
        got = learn.title_scenes("criminal-minds@adults", "Criminal Minds", later,
                                 {"disturbing"}, episode=(1, 20))
        self.assertEqual(sorted(round(s["s"], 1) for s in got), [1152.5, 1887.5, 2346.5, 2388.5])
        self.assertEqual(learn.title_scenes("criminal-minds@adults", "Criminal Minds",
                                            self.dialogue(), {"disturbing"}, episode=(1, 19)), [])
        self.assertEqual(learn.title_scenes("criminal-minds@adults", "Criminal Minds",
                                            self.dialogue(), {"violence"}, episode=(1, 20)), [])


if __name__ == "__main__":
    unittest.main()
