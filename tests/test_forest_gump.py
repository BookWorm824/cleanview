"""The owner's Forest Gump report (1.18.111, 2026-11-16, kids, the AI helper, made on 1.18.110; the
owner: "lets train from this", then "Teach the 9 lines", "Add the 2 words", "Fix Dr Pepper
and Dick", "Forest Gump note", and "any of the strip club stuff needs cut for all ages if it is
checked")."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import support  # noqa: F401  (must come first)
import test_timing as T

import cleanview as engine
import cleanview_ai as ai
import cleanview_claude as cc
import cleanview_learn as learn
import cvcore as cl

CATS = list(cl.CATS)       # every list (slurs and sexual words have their own since 1.18.150)


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

    def test_the_nine_for_every_age(self):
        # taught for kids at first; every age since 2026-11-16 (the owner: "whenever a report is
        # sent to learn from, apply it to every age. under the proper category")
        for key in ("_movies@kids", "_movies@young", "_movies@teens", "_movies@adults"):
            got = self.muted(key, {"sexref", "crude"})
            self.assertTrue(set(self.LINES) <= got, key)
            self.assertFalse(got & set(self.EVERYDAY), key)
        self.assertFalse(self.muted("_movies@adults", set()) & set(self.LINES))
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


class TheOtherScenes(unittest.TestCase):
    """The scenes the picture checks missed on two PCs (her laptop and another, 1.18.113); her
    picks "Strip club", "Dorm room", "Bare bottom", "New Year's bed"."""
    LINES = [(2160.0, "I took the bus up to Memphis to see her perform in that show."),
             (2162.0, "That was Amber, Amber Flame."),
             (2276.0, "Forrest, let me down!"),
             (1662.0, "I want to be able to say things, just one-to-one."),
             (1673.0, "Have you ever been with a girl, Forrest?"),
             (1754.0, "I don't care. I don't like her, anyway."),
             (3791.0, "I'd kind of like to see that."),
             (3808.0, "God damn, son."),
             (4859.0, "Happy New Year!"),
             (4882.0, "Happy New Year, Lieutenant Dan!"),
             (4950.0, "You retard. Loser. You freak.")]

    def got(self, ticked, key="_movies@kids"):
        dl = [{"s": s, "e": s + 2.0, "text": t} for s, t in sorted(self.LINES)]
        return {(s["kind"][0], s["s"], s["e"])
                for s in learn.title_scenes(key, "Forest Gump", dl, ticked)}

    def test_each_where_its_lines_are(self):
        self.assertTrue({("Nudity", 2162.0, 2278.5), ("Sex scene", 1664.0, 1756.5),
                         ("Nudity", 3793.0, 3810.5), ("Sex scene", 4884.0, 4952.5)}
                        <= self.got({"nudity", "implied", "sex", "sexref"}))

    def test_each_by_its_own_filters(self):
        self.assertEqual({k for k, s, e in self.got({"nudity"})}, {"Nudity", "Sex scene"})
        self.assertNotIn(("Sex scene", 4884.0, 4952.5), self.got({"nudity"}))   # not New Year's
        self.assertNotIn(("Nudity", 3793.0, 3810.5), self.got({"sexref"}))      # not the bottom
        self.assertIn(("Nudity", 2162.0, 2278.5), self.got({"sexref"}, "_movies"))  # the club,
        self.assertIn(("Nudity", 2162.0, 2278.5), self.got({"nudity"}, "_movies@teens"))  # any age
        self.assertEqual(self.got({"crude", "bullying"}), set())


@T.needs_ffmpeg
class ThroughAWholeScan(unittest.TestCase):
    """1.18.112 added the taught scene after the scenes were numbered: no "id", no "cut", and
    the stills made at the end of analyze() would have failed the scan (found by the CleanView
    Play chat while merging it). A whole analyze() with stand-ins for the slow parts."""

    @classmethod
    def setUpClass(cls):
        cls.video = support.SANDBOX / "Forest Gump.mp4"
        if not cls.video.exists():
            T.ffmpeg("-f", "lavfi", "-i", "testsrc=size=64x48:rate=10:duration=20", "-f",
                     "lavfi", "-i", "sine=frequency=300:duration=20", "-c:v", "libx264",
                     "-c:a", "aac", "-shortest", cls.video)

    def scan(self, opts):
        work = Path(tempfile.mkdtemp(dir=support.SANDBOX))
        lines = [{"s": 1.0, "e": 2.5, "text": "We're talking about five little points here."},
                 {"s": 3.0, "e": 4.0, "text": "He's on vacation."},
                 {"s": 9.0, "e": 11.0, "text": "Well, your mama sure does care about your schooling, son."},
                 {"s": 12.0, "e": 13.0, "text": "You don't say much, do you?"},
                 {"s": 16.0, "e": 17.5, "text": "Finally, he had to try."}]
        asr = [{"t": w, "s": 3.0 + 0.3 * k, "e": 3.2 + 0.3 * k}
               for k, w in enumerate("he's on vacation".split())]
        n = int(20 * engine.VISUAL_FPS)
        vis = {"version": engine.PICTURE_VERSION, "fps": engine.VISUAL_FPS,
               "classes": list(engine.KEEP), "scores": [[0.0] * len(engine.KEEP)] * n,
               "lum": [[120.0, 40.0]] * n, "lifted": [], "notes": []}
        stills = []

        def make_thumbs(path, scenes, work, *a, **k):     # as the real one names its stills
            stills.extend(f"{sc['id']}_{i}.png" for sc in scenes for i in range(3))
        found = [{"s": 0.5, "e": 2.0, "kind": ["Nudity"], "why": "a stand-in find"}]
        with mock.patch.object(ai, "start_ollama", lambda *a, **k: True), \
                mock.patch.object(ai, "choose_models", lambda: True), \
                mock.patch.object(ai, "clip_ready", lambda: False), \
                mock.patch.object(ai, "on_graphics_card", lambda model=None: True), \
                mock.patch.object(ai, "free_memory", lambda: None), \
                mock.patch.object(ai, "dialogue_lines", lambda *a, **k: [dict(l) for l in lines]), \
                mock.patch.object(ai, "romance_scenes", lambda *a, **k: []), \
                mock.patch.object(engine, "available_memory_gb", lambda: 16.0), \
                mock.patch.object(engine, "load_listeners", lambda *a: [None]), \
                mock.patch.object(engine, "transcribe", lambda *a, **k: asr), \
                mock.patch.object(engine, "fetch_subtitles",
                                  lambda *a, **k: ([], "", None, "none online")), \
                mock.patch.object(engine, "visual_scan", lambda *a, **k: vis), \
                mock.patch.object(engine, "find_voices", lambda *a, **k: [{"g": "m", "spk": 1}
                                                                           for _ in lines]), \
                mock.patch.object(engine, "find_lines", lambda *a, **k: ([], "the AI helper")), \
                mock.patch.object(engine, "decide_picture_scenes",
                                  lambda *a, **k: [dict(f) for f in found]), \
                mock.patch.object(engine, "make_thumbs", make_thumbs):
            engine.analyze(str(self.video), str(work), groups=["swearing"], opts=opts,
                           progress=lambda f, m: None, log=lambda m: None)
        return json.loads((work / "analysis.json").read_text()), stills

    def test_numbered_ticked_and_stills_made(self):
        st, stills = self.scan({"nudity": True, "sexref": True, "sex": False, "violence": False,
                                "loudmusic": False, "ai": True, "reader": "local",
                                "autosubs": True, "look": True})
        learned = [sc for sc in st["scenes"] if sc.get("learned")]
        self.assertEqual([(sc["s"], sc["e"], sc["cut"]) for sc in learned], [(4.0, 13.5, True)])
        ids = [sc["id"] for sc in st["scenes"]]
        self.assertEqual(len(ids), len(set(ids)))                     # each its own number
        self.assertEqual(len(st["scenes"]), 2)                         # with the stand-in find
        self.assertIn(f"{learned[0]['id']}_0.png", stills)
        self.assertIn("CleanView learned this scene", learned[0]["why"])

    def test_not_there_unticked(self):
        st, _ = self.scan({"nudity": True, "sexref": False, "sex": False, "violence": False,
                           "loudmusic": False, "ai": True, "reader": "local", "autosubs": True,
                           "look": True})
        self.assertEqual([sc for sc in st["scenes"] if sc.get("learned")], [])


if __name__ == "__main__":
    unittest.main()
