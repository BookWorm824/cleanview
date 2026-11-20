"""German and Italian (1.18.145; the owner, 2026-11-19: "i think german , italian, espanola").
The listening model for other languages already heard German (it was refused for want of
word lists), so these are word lists, built like Portuguese and Russian
(test_portuguese_russian.py). Spanish was already in. Dutch now stands in as the language
CleanView names but doesn't clean.

No native speaker has checked the lists, and no German or Italian film has been cleaned here."""
import tempfile
import unittest
from pathlib import Path

import support
import cvcore as cl
import cvlang
import cleanview as engine
from test_spanish import SRT, found


class German(unittest.TestCase):
    def setUp(self):
        cl.use_language("de")
        self.addCleanup(cl.use_language, "en")

    def test_words_as_the_lists_have_them(self):
        self.assertEqual(cl.norm("Scheiße!"), "scheisse")           # ß written out
        self.assertEqual(cl.norm("Scheisse"), "scheisse")           # as subtitles without it
        self.assertEqual(cl.norm("Arschlöcher,"), "arschloecher")    # umlauts written out
        self.assertEqual(cl.norm("schwül"), "schwuel")               # humid, not "schwul"
        self.assertEqual(cl.norm("Café"), "cafe")

    def test_swearing_is_found(self):
        self.assertEqual(found("Scheiße, du Arschloch!"),
                         [("scheisse", "moderate"), ("arschloch", "moderate")])
        self.assertEqual(found("Fick dich, Hurensohn"), [("fick", "strong"), ("hurensohn", "strong")])
        self.assertEqual(found("Das ist total beschissen"), [("beschissen", "moderate")])
        self.assertEqual(found("Verpiss dich, du Wichser"),
                         [("verpiss", "moderate"), ("wichser", "strong")])
        self.assertEqual(found("Was für ein Scheißkerl"), [("scheisskerl", "moderate")])
        self.assertEqual(found("Ich bin so angepisst"), [("angepisst", "moderate")])
        self.assertEqual(found("Shit, das war knapp"), [("shit", "moderate")])

    def test_milder_groups(self):
        self.assertEqual(found("Oh mein Gott, was zum Teufel ist das?"),
                         [("oh mein gott", "deity"), ("zum teufel", "mild")])
        self.assertEqual(found("Verdammt nochmal, so ein Mist"),
                         [("verdammt nochmal", "mild"), ("mist", "minced")])
        self.assertEqual(found("Gott sei Dank, du bist da"), [("gott sei dank", "deity")])
        self.assertEqual(found("Herrgott nochmal!"), [("herrgott", "deity")])
        self.assertEqual(found("Halt die Klappe, du Vollidiot"),
                         [("halt die klappe", "rude"), ("vollidiot", "rude")])
        self.assertEqual(found("Bist du blöd?"), [("bloed", "rude")])
        self.assertEqual(found("Er ist schwul"), [("schwul", "samesex")])
        self.assertEqual(found("Ach du meine Güte"), [("ach du meine guete", "minced")])

    def test_everyday_words_are_left_alone(self):
        for text in ("Es ist heute so schwül",
                     "Den Mist aufs Feld fahren",
                     "Grüß Gott, Herr Müller",
                     "Der Hund wedelt mit dem Schwanz",
                     "Die Sau und das Schwein im Stall",
                     "Das war eine Dummheit",
                     "Homo sapiens lebt in Gruppen",
                     "Der Esel trägt einen Sack",
                     "Das ist doch Blödsinn",
                     "Gott ist die Liebe",
                     "Die Mistel hängt an der Tür",
                     "Eine Scheibe Brot, bitte"):
            self.assertEqual(found(text), [], text)

    def test_only_the_groups_that_are_ticked(self):
        self.assertEqual(found("Scheiße, du Idiot", cl.GROUPS["rude"]), [("idiot", "rude")])
        self.assertEqual(found("Mein Gott, so eine Scheiße", cl.GROUPS["swearing"]),
                         [("scheisse", "moderate")])

    def test_only_listed_words_may_be_muted_alone(self):
        self.assertTrue(cl.listed_word("Scheiße"))
        self.assertTrue(cl.listed_word("Oh mein Gott"))
        self.assertTrue(cl.listed_word("Kondom"))
        self.assertFalse(cl.listed_word("Grafi"))
        self.assertFalse(cl.listed_word("Haus"))
        self.assertFalse(cl.listed_word("Idiot", cats=cl.GROUPS["swearing"]))

    def test_masked_in_the_review(self):
        self.assertEqual(cl.mask("Scheiße"), "S******")


class Italian(unittest.TestCase):
    def setUp(self):
        cl.use_language("it")
        self.addCleanup(cl.use_language, "en")

    def test_words_as_the_lists_have_them(self):
        self.assertEqual(cl.norm("Perché?"), "perche")
        self.assertEqual(cl.norm("dell'idiota"), "idiota")          # joined-on words come off
        self.assertEqual(cl.norm("c'è"), "e")
        self.assertEqual(cl.norm("all'inferno"), "inferno")

    def test_swearing_is_found(self):
        self.assertEqual(found("Vaffanculo, stronzo!"),
                         [("vaffanculo", "strong"), ("stronzo", "strong")])
        self.assertEqual(found("Che cazzo fai?"), [("cazzo", "strong")])
        self.assertEqual(found("Sei proprio incazzato"), [("incazzato", "strong")])
        self.assertEqual(found("Figlio di puttana"), [("puttana", "strong")])
        self.assertEqual(found("Figlio di troia"), [("figlio di troia", "strong")])
        self.assertEqual(found("Che merda, è tutto rotto"), [("merda", "moderate")])

    def test_milder_groups(self):
        self.assertEqual(found("Porca miseria, che palle"),
                         [("porca miseria", "minced"), ("che palle", "moderate")])
        self.assertEqual(found("Oh mio Dio"), [("oh mio dio", "deity")])
        self.assertEqual(found("Porco Dio!"), [("porco dio", "deity")])
        self.assertEqual(found("Grazie a Dio, sei qui"), [("grazie a dio", "deity")])
        self.assertEqual(found("Che diavolo succede?"), [("che diavolo", "mild")])
        self.assertEqual(found("Vai all'inferno"), [("vai inferno", "mild")])
        self.assertEqual(found("Mannaggia, ho perso le chiavi"), [("mannaggia", "minced")])
        self.assertEqual(found("Stai zitto, idiota"), [("stai zitto", "rude"), ("idiota", "rude")])
        self.assertEqual(found("Sei un cretino"), [("cretino", "rude")])
        self.assertEqual(found("Lui è gay"), [("gay", "samesex")])

    def test_everyday_words_are_left_alone(self):
        for text in ("Il cavallo di Troia entrò in città",
                     "La cazzuola del muratore",
                     "Il finocchio è buono in insalata",
                     "Mamma mia, che caldo",
                     "Il diavolo veste Prada",
                     "La sega del falegname",
                     "Un cavolo e due carote",
                     "Il bambino è rimasto zitto",
                     "La cagna ha avuto i cuccioli",
                     "Dio è amore",
                     "Il tetto della casa"):
            self.assertEqual(found(text), [], text)

    def test_only_the_groups_that_are_ticked(self):
        self.assertEqual(found("Cazzo, che idiota", cl.GROUPS["rude"]), [("idiota", "rude")])
        self.assertEqual(found("Dio mio, che merda", cl.GROUPS["swearing"]),
                         [("merda", "moderate")])

    def test_only_listed_words_may_be_muted_alone(self):
        self.assertTrue(cl.listed_word("cazzo"))
        self.assertTrue(cl.listed_word("Oh mio Dio"))
        self.assertTrue(cl.listed_word("preservativo"))
        self.assertFalse(cl.listed_word("Grafi"))
        self.assertFalse(cl.listed_word("casa"))

    def test_masked_in_the_review(self):
        self.assertEqual(cl.mask("cazzo"), "c****")


class FilesAndTheList(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(dir=support.SANDBOX))
        self.video = self.dir / "Film.mkv"
        self.video.write_bytes(b"")
        self.addCleanup(cl.use_language, "en")

    def test_the_videos_own_language(self):
        (self.dir / "Film.en.srt").write_text(SRT.replace("{}", "English line"), encoding="utf8")
        (self.dir / "Film.de.srt").write_text(SRT.replace("{}", "Deutsche Zeile"), encoding="utf8")
        (self.dir / "Film.ita.srt").write_text(SRT.replace("{}", "Riga italiana"), encoding="utf8")
        for lang, word in (("de", "Deutsche"), ("it", "italiana")):
            cues, where = engine.find_subtitles(self.video, {"subs": []}, self.dir, lang)
            self.assertIn(word, cues[0]["text"], lang)

    def test_saved_files_the_note_and_the_lookup(self):
        for lang, name in (("de", "German"), ("it", "Italian")):
            cl.use_language(lang)
            self.assertEqual(engine._lang_file("transcript.json"), f"transcript_{lang}.json")
            self.assertIn(f"in {name}", cvlang.reader_note(lang))
            try:
                import babelfish  # noqa: F401
            except ImportError:
                continue
            self.assertEqual(str(engine._sub_language()), lang)

    def test_sound_track_and_auto(self):
        self.assertEqual(cvlang.tag_language("ger"), ("de", None))
        self.assertEqual(cvlang.tag_language("ita"), ("it", None))
        self.assertEqual(cvlang.CHOICES["de"], "German")
        self.assertTrue(cvlang.needs_model("it"))

    def test_built_like_the_others(self):
        for code in ("de", "it"):
            self.assertEqual(set(cvlang.WORDS[code]), set(cvlang.ORDER) | {"sex"})
            for table in (cvlang.PHRASES, cvlang.NOT_NEXT, cvlang.NOT_BEFORE, cvlang.TAGS,
                          cvlang.FILE_TAGS, cvlang.SUB_LANG):
                self.assertIn(code, table)
            for group, phrases in cvlang.PHRASES[code].items():
                for ph in phrases:              # written as norm() leaves them
                    self.assertEqual(tuple(cvlang.norm(w, code) for w in ph), ph, ph)

    def test_each_language_keeps_to_its_own_list(self):
        cl.use_language("de")
        self.assertEqual(found("Vaffanculo, cazzo, mierda"), [])
        cl.use_language("it")
        self.assertEqual(found("Scheiße, Arschloch, putain"), [])


if __name__ == "__main__":
    unittest.main()
