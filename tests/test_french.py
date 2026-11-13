"""French (1.18.81; the owner, 2026-11-13: "French next"), built like Spanish (test_spanish.py):
its own word lists in the same groups, French subtitles and sound track, and the listening
model for other languages. French joins short words on with an apostrophe ("l'idiot", "t'es",
"j'm'en fous"), so those come off before a word is matched.

The last test hears real French, and only runs when CLEANVIEW_TEST_MULTI names a folder with
the real listening model for other languages."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import support
import cvcore as cl
import cvlang
import cleanview as engine
from test_spanish import SRT, found


class French(unittest.TestCase):
    def setUp(self):
        cl.use_language("fr")
        self.addCleanup(cl.use_language, "en")

    def test_words_as_the_lists_have_them(self):
        self.assertEqual(cl.norm("Enculé !"), "encule")
        self.assertEqual(cl.norm("Ça"), "ca")
        self.assertEqual(cl.norm("l'idiot,"), "idiot")
        self.assertEqual(cl.norm("qu'il"), "il")
        self.assertEqual(cl.norm("j'm'en"), "en")
        self.assertEqual(cl.norm("aujourd'hui"), "aujourd'hui")       # not a joined-on word
        self.assertEqual(cl.norm("Tais-toi !"), "taistoi")
        self.assertEqual(cl.norm("sœur"), "sœur")

    def test_swearing_is_found(self):
        self.assertEqual(found("Putain, c'est quoi ce bordel ?", cl.GROUPS["swearing"]),
                         [("putain", "strong")])
        self.assertEqual(found("Putain, c'est quoi ce bordel ?"),
                         [("putain", "strong"), ("bordel", "mild")])
        self.assertEqual(found("Merde, t'es vraiment con"), [("merde", "moderate"), ("con", "moderate")])
        self.assertEqual(found("Espèce d'enculé, va te faire foutre !"),
                         [("encule", "strong"), ("foutre", "strong")])
        self.assertEqual(found("Quel connard, ce fils de pute"),
                         [("connard", "strong"), ("pute", "strong")])
        self.assertEqual(found("Tu me fais chier avec tes conneries"),
                         [("chier", "moderate"), ("conneries", "moderate")])
        self.assertEqual(found("J'm'en fous de tout ça"), [("en fous", "moderate")])
        self.assertEqual(found("Je m'en fous complètement"), [("en fous", "moderate")])
        self.assertEqual(found("Arrête de m'emmerder, salaud"),
                         [("emmerder", "moderate"), ("salaud", "strong")])
        self.assertEqual(found("Nique ta mère"), [("nique", "strong")])

    def test_quebec(self):
        self.assertEqual(found("Tabarnak, mon char est brisé, câlisse !"),
                         [("tabarnak", "strong"), ("calisse", "strong")])
        self.assertEqual(found("Crisse que c'est beau, maudit"),
                         [("crisse", "strong"), ("maudit", "mild")])

    def test_milder_groups(self):
        self.assertEqual(found("Zut alors, j'ai oublié mes clés"), [("zut", "minced")])
        self.assertEqual(found("Oh mince, il pleut"), [("oh mince", "minced")])
        self.assertEqual(found("Nom d'un chien !"), [("nom un chien", "minced")])
        self.assertEqual(found("Sacrebleu !"), [("sacrebleu", "minced")])
        self.assertEqual(found("Oh mon Dieu, regarde !"), [("oh mon dieu", "deity")])
        self.assertEqual(found("Nom de Dieu de bordel"), [("nom de dieu", "deity"), ("bordel", "mild")])
        self.assertEqual(found("Va au diable !"), [("va au diable", "mild")])
        self.assertEqual(found("Tais-toi, espèce d'idiot"), [("taistoi", "rude"), ("idiot", "rude")])
        self.assertEqual(found("Ferme-la, crétin"), [("fermela", "rude"), ("cretin", "rude")])
        self.assertEqual(found("Ta gueule, t'es débile"), [("ta gueule", "rude"), ("debile", "rude")])
        self.assertEqual(found("Il paraît qu'il est gay"), [("gay", "samesex")])

    def test_everyday_words_are_left_alone(self):
        for text in ("Elle lui a donné un baiser sur la joue",
                     "Les enfants sont allés à la ferme voir la vache",
                     "On a fait un pique-nique au bord du lac",
                     "On a fait un pique nique au bord du lac",
                     "Homo sapiens est apparu en Afrique",
                     "Elle est mince et très grande",
                     "Le chien remue la queue, il est fou de joie",
                     "La chatte dort sur le canapé",
                     "J'ai mangé de la purée avec une andouille",
                     "Il joue de la flûte au conservatoire",
                     "Quel calvaire, ce voyage sacré",
                     "Tout s'est mis en branle ce matin",
                     "Dieu vous bénisse, mes enfants",
                     "Le bouffon du roi amusait la cour",
                     "Un chili con carne, s'il vous plaît"):
            self.assertEqual(found(text), [], text)

    def test_only_the_groups_that_are_ticked(self):
        self.assertEqual(found("Putain, quel idiot", cl.GROUPS["rude"]), [("idiot", "rude")])
        self.assertEqual(found("Mon Dieu, quelle merde", cl.GROUPS["swearing"]),
                         [("merde", "moderate")])

    def test_only_listed_words_may_be_muted_alone(self):
        self.assertTrue(cl.listed_word("putain"))
        self.assertTrue(cl.listed_word("l'enculé"))
        self.assertTrue(cl.listed_word("Mon Dieu"))
        self.assertTrue(cl.listed_word("Tais-toi"))
        self.assertFalse(cl.listed_word("Grafi"))
        self.assertFalse(cl.listed_word("maison"))
        self.assertFalse(cl.listed_word("idiot", cats=cl.GROUPS["swearing"]))

    def test_her_own_words_always(self):
        self.assertEqual(found("Quelle horreur, c'est dégoûtant", [], [("degoutant",)]),
                         [("degoutant", "mine")])

    def test_masked_in_the_review(self):
        self.assertEqual(cl.mask("enculé"), "e*****")

    def test_spanish_and_french_keep_their_own_lists(self):
        self.assertEqual(found("Eres un cabrón de mierda"), [])
        cl.use_language("es")
        self.assertEqual(found("Putain, quel connard"), [])


class FrenchFiles(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(dir=support.SANDBOX))
        self.video = self.dir / "Film.mkv"
        self.video.write_bytes(b"")
        (self.dir / "Film.en.srt").write_text(SRT.replace("{}", "English line"), encoding="utf8")
        (self.dir / "Film.fr.srt").write_text(SRT.replace("{}", "Ligne en français"),
                                              encoding="utf8")

    def test_the_videos_own_language(self):
        cues, where = engine.find_subtitles(self.video, {"subs": []}, self.dir, "fr")
        self.assertEqual(where, "subtitles from Film.fr.srt")
        self.assertIn("français", cues[0]["text"])
        (self.dir / "Film.fr.srt").unlink()
        self.assertEqual(engine.find_subtitles(self.video, {"subs": []}, self.dir, "fr"), ([], ""))

    def test_saved_files_and_the_online_lookup(self):
        cl.use_language("fr")
        self.addCleanup(cl.use_language, "en")
        self.assertEqual(engine._lang_file("transcript.json"), "transcript_fr.json")
        self.assertIn("in French", cvlang.reader_note("fr"))
        try:
            import babelfish  # noqa: F401
        except ImportError:
            self.skipTest("the subtitle finder isn't installed here")
        self.assertEqual(str(engine._sub_language()), "fr")

    @unittest.skipUnless(support.FFMPEG, "needs ffmpeg")
    def test_the_french_sound_track_is_the_one_heard(self):
        out = self.dir / "two_tracks.mkv"
        subprocess.run([support.FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i",
                        "color=c=gray:s=160x120:d=1", "-f", "lavfi", "-i",
                        "sine=frequency=300:duration=1", "-f", "lavfi", "-i",
                        "sine=frequency=600:duration=1", "-map", "0:v", "-map", "1:a", "-map",
                        "2:a", "-metadata:s:a:0", "language=eng", "-metadata:s:a:1",
                        "language=fre", "-disposition:a:0", "default", "-shortest", str(out)],
                       check=True)
        self.assertEqual(engine.probe(out)["audio"]["index"], 1)
        self.assertEqual(engine.probe(out, "fr")["audio"]["index"], 2)

    def test_on_the_start_pages_list(self):
        self.assertEqual(list(cvlang.LANGS.items()),
                         [("en", "English"), ("es", "Spanish"), ("fr", "French")])
        for code in cvlang.LANGS:               # every language has all its pieces
            self.assertIn(code, cvlang.TAGS)
            self.assertIn(code, cvlang.FILE_TAGS)
            self.assertIn(code, cvlang.SUB_LANG)
            if code != "en":
                self.assertEqual(set(cvlang.WORDS[code]), set(cvlang.ORDER) | {"sex"})
                for table in (cvlang.PHRASES, cvlang.NOT_NEXT, cvlang.NOT_BEFORE):
                    self.assertIn(code, table)
                for group, phrases in cvlang.PHRASES[code].items():
                    for ph in phrases:          # written as norm() leaves them
                        self.assertEqual(tuple(cvlang.norm(w, code) for w in ph), ph, ph)


REAL = os.environ.get("CLEANVIEW_TEST_MULTI")


@unittest.skipUnless(REAL and support.FFMPEG and (Path(REAL) / "test_wavs" / "fr.wav").exists(),
                     "set CLEANVIEW_TEST_MULTI to the real model's folder to hear real French")
class RealFrench(unittest.TestCase):
    def test_a_french_video_from_listening_to_the_word_list(self):
        work = Path(tempfile.mkdtemp(dir=support.SANDBOX))
        video = work / "extrait.mkv"
        subprocess.run([support.FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i",
                        "color=c=gray:s=160x120:r=5", "-i", str(Path(REAL) / "test_wavs" / "fr.wav"),
                        "-shortest", "-c:v", "libx264", "-c:a", "aac", str(video)], check=True)
        cl.use_language("fr")
        rec = cl.load_recognizer(REAL, 4)
        heard = engine.transcribe(str(video), engine.probe(str(video), "fr"), rec)
        del rec
        self.assertGreater(len(heard), 5)
        # a long plain word it heard (no hyphen or apostrophe), as one of her own words
        pick = max((w["t"].strip(".,!?") for w in heard if w["t"].strip(".,!?").isalpha()),
                   key=len)
        cl.use_language("en")
        with mock.patch.dict(os.environ, {"CLEANVIEW_MULTI_MODEL": REAL}):
            st = engine.analyze(str(video), str(work / "w"), groups=("swearing",),
                                opts={"language": "fr", "ai": False, "autosubs": False,
                                      "mywords": [pick], "nudity": False, "sex": False,
                                      "violence": False, "gore": False, "graphic": False,
                                      "disturbing": False})
        cl.use_language("en")
        self.assertEqual(st["scan"]["language"], "fr")
        self.assertTrue((work / "w" / "transcript_fr.json").exists())
        self.assertTrue(any("Cleaned as a French video" in n for n in st["notes"]))
        mine = [m for m in st["mutes"] if m["cat"] == "mine"]
        self.assertTrue(mine, (pick, st["mutes"]))
        self.assertEqual(mine[0]["raw"], cvlang.norm(pick, "fr"))


if __name__ == "__main__":
    unittest.main()
