"""Lauren's Forest Gump report (1.18.111, 2026-11-16, kids, the AI helper, made on 1.18.110; the
owner: "lets train from this", then "Teach the 9 lines", "Add the 2 words", "Fix Dr Pepper
and Dick", "Forest Gump note", and "any of the strip club stuff needs cut for all ages if it is
checked")."""
import json
import os
import tempfile
import unittest

import support  # noqa: F401  (must come first)

import cleanview as engine
import cleanview_ai as ai
import cleanview_claude as cc
import cleanview_learn as learn
import cvcore as cl

CATS = ["strong", "moderate", "mild", "deity", "minced", "samesex", "rude"]


def found(text):
    ws = [w for w in (cl.norm(w) for w in text.split()) if w]
    return [" ".join(ws[i:j]) for i, j, _ in cl.find_language(ws, CATS)]


def name_there(text, word):
    sw = text.split()
    k = [i for i, w in enumerate(sw) if cl.norm(w) == word][0]
    return engine.name_in_subtitles(sw, [0] * len(sw), [{"text": text}], k)


class TheTwoWords(unittest.TestCase):
    def test_the_slur(self):
        self.assertEqual(found("Coons are trying to get into school."), ["coons"])
        self.assertEqual(found("Get lost, you big coons!"), ["coons"])
        for fine in ("a Maine Coon", "a coon dog", "we went coon hunting",
                     "I haven't seen you in a coon's age", "a coonskin cap",
                     "Not raccoons, you idiot", "raccoons on the porch"):
            self.assertNotIn("coon", " ".join(found(fine)), fine)

    def test_faggotty(self):
        self.assertIn("faggotty", found("Get your faggotty ass on the bus."))
        self.assertIn("faggoty", found("that faggoty little"))


class StripClubs(unittest.TestCase):
    def test_on_the_list_for_every_age(self):
        sx = engine.LINE_WORDS["sexref"]
        for t, w in (("He took me to a strip club.", "strip club"), ("a striptease", "striptease"),
                     ("she gave him a lap dance", "lap dance"), ("an exotic dancer", "exotic dancer"),
                     ("pole dancing", "pole dancing"), ("a strip joint", "strip joint")):
            self.assertEqual([m.group(0) for m in sx.finditer(t)], [w], t)
        for t in ("a comic strip", "strip the bed", "the Vegas strip", "a pole vault",
                  "a strip of land"):
            self.assertEqual(list(sx.finditer(t)), [], t)


class SodaIsntDrinking(unittest.TestCase):
    def test_told(self):
        self.assertIn("Dr Pepper", ai.LOOK["drinking"][0])
        self.assertIn("soda", ai.LOOK["drinking"][0])
        self.assertIn("soda", cc.PIC_RULES)


class DickTheName(unittest.TestCase):
    def test_a_name_written_so(self):
        self.assertTrue(name_there("Well, it's easy if you try, Dick.", "dick"))  # Dick Cavett
        self.assertTrue(name_there("Hey, Dick, how are you?", "dick"))
        self.assertTrue(engine.can_be_name("moderate", "Dick"))
        self.assertFalse(engine.can_be_name("moderate", "shit"))

    def test_still_the_insult(self):
        for t in ("Don't be such a Dick.", "You Dick!", "He's a total dick."):
            self.assertFalse(name_there(t, "dick"), t)


class Lessons(unittest.TestCase):
    """What was taught, replayed on the film's own lines (the shipped shared_learned.json)."""
    LINES = ["Well, your mama sure does care about your schooling, son.",
             "He was always kissing and touching her and her sisters.",
             "Have you ever been with a girl, Forrest?",
             "I bet that never happened in Home Ec.",
             "I think I ruined your roommate's bathrobe.",
             "Hey, Gump, get a load of the tits on her!",
             "rape our women, and destroy our black communities.",
             "I'm living off the government tit.",
             "Did you lose your pecker in the war or something?"]
    CLUB = ["That was Amber, Amber Flame.",
            "direct from Hollywood, California, our very own beatnik beauty,",
            "let's give a big round of applause to the luscious Bobbi Dylan."]
    EVERYDAY = ["Hello.", "Do you want a chocolate?", "I gotta pee.",
                "Give her a big hand, guys. Good job, Amber.", "Stupid is as stupid does."]

    def muted(self, key, on):
        dl = [{"s": float(i), "e": i + 0.9, "text": t}
              for i, t in enumerate(self.LINES + self.CLUB + self.EVERYDAY)]
        added, _ = learn.apply(key, dl, [], [], [], on=on)
        return {a["text"] for a in added}

    def test_the_nine_for_kids_and_young_kids(self):
        for key in ("_movies@kids", "_movies@young"):
            got = self.muted(key, {"sexref", "crude"})
            self.assertTrue(set(self.LINES) <= got, key)
            self.assertFalse(got & set(self.EVERYDAY), key)
        self.assertFalse(self.muted("_movies@teens", {"sexref", "crude"}) & set(self.LINES))
        self.assertEqual(self.muted("_movies@kids", {"crude"}) & set(self.LINES),
                         {"I'm living off the government tit."})          # each its own filter

    def test_the_club_for_every_age_when_ticked(self):
        for key in ("_movies@adults", "_movies@teens", "_movies@kids", "_movies@young"):
            self.assertTrue(set(self.CLUB) <= self.muted(key, {"sexref"}), key)
            self.assertFalse(set(self.CLUB) & self.muted(key, {"crude"}), key)

    def test_notes(self):
        rule = [n for n in learn.notes("_movies@adults", title="Cars") if "strip club" in n]
        self.assertEqual(len(rule), 1)                                  # every movie, every age
        self.assertTrue(any("feather" in n for n in learn.notes("_movies@kids", title="Cars")))
        for title in ("Forest Gump", "Forrest Gump"):                   # her file's spelling too
            self.assertTrue(any("Jenny's dorm room" in n
                                for n in learn.notes("_movies@adults", title=title)), title)
        self.assertFalse(any("Jenny's dorm room" in n
                             for n in learn.notes("_movies@adults", title="Cars")))


class ThePrincipalsVisit(unittest.TestCase):
    """1.18.112, the owner: "there is a scene where a teacher visits his house and you hear
    sounds, then he walks past forest and says 'your mama sure loves you' that needs cut if
    sexual is ticked", "its only gets cut it its ticked"."""
    LINES = [(520.0, "We're talking about five little points here."),
             (535.0, "He's on vacation."),
             (554.5, "Well, your mama sure does care about your schooling, son."),
             (564.0, "You don't say much, do you?"),
             (578.0, "\"Finally, he had to try.")]

    def dialogue(self, shift=0.0):
        return [{"s": s + shift, "e": s + shift + 2.0, "text": t} for s, t in self.LINES]

    def test_cut_from_his_mama_on_vacation_to_you_dont_say_much(self):
        for ticked in ({"sexref"}, {"sex"}, {"sex", "sexref", "crude"}):
            got = learn.title_scenes("_movies@kids", "Forest Gump", self.dialogue(), ticked)
            self.assertEqual([(s["s"], s["e"], s["kind"]) for s in got],
                             [(537.0, 566.5, ["Sex scene"])], ticked)
            self.assertTrue(got[0]["sure"] and got[0]["learned"])     # ticked; no AI undoes it
            self.assertIn("principal", got[0]["why"])                 # shown on the card and
            self.assertIn("CleanView learned this scene", got[0]["why"])   # in the report

    def test_any_copy_any_age_either_spelling(self):
        for key in ("_movies", "_movies@teens", "_movies@young"):
            got = learn.title_scenes(key, "Forrest Gump", self.dialogue(shift=12.0), {"sex"})
            self.assertEqual([(s["s"], s["e"]) for s in got], [(549.0, 578.5)], key)

    def test_only_when_ticked_and_only_this_movie(self):
        self.assertEqual(learn.title_scenes("_movies@kids", "Forest Gump", self.dialogue(),
                                            {"crude", "bullying"}), [])
        self.assertEqual(learn.title_scenes("_movies@kids", "Cars", self.dialogue(),
                                            {"sex", "sexref"}), [])
        self.assertEqual(learn.title_scenes("_movies@kids", "Forest Gump", self.dialogue()[:2],
                                            {"sexref"}), [])           # its lines not there


if __name__ == "__main__":
    unittest.main()
