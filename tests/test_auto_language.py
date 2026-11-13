"""Auto: CleanView works out the language of the video (1.18.89; the owner, 2026-11-13: "we
have a tab now to check different languages, but what if the person doesn't know it, would it
be possible to have an "auto" tab", then "do auto clean").

The sound track's own label is read first. With none, a short sample is listened to with the
model for other languages and the language is told from its everyday little words. English
stays the choice the page starts with.

The last tests hear the listening model's own Spanish, French, English and German samples,
and only run when CLEANVIEW_TEST_MULTI names the real model's folder."""
import json
import os
import subprocess
import tempfile
import unittest
import tkinter as tk
from pathlib import Path
from unittest import mock

import support
import cvcore as cl
import cvlang
import cleanview as engine

SAID = {
    "en": "Well I think that you should know what they said about the house when we were "
          "there, because it was not what I wanted at all",
    "es": "Pero no sé qué es lo que quieres de mí, porque yo ya te dije que no tengo nada "
          "para ti y eso es todo lo que hay",
    "fr": "Je ne sais pas ce que vous voulez dire, mais nous avons tout fait pour que ce "
          "soit bien et il est très content",
    "pt": "Eu não sei o que você quer de mim, porque já disse que não tenho nada para você "
          "e isso é tudo que tem aqui",
    "ru": "Я не знаю, что ты хочешь от меня, потому что я уже сказал тебе, что у меня "
          "ничего нет для тебя",
}
OTHERS = {
    "German": "Ich weiß nicht, was du von mir willst, aber wir haben das nicht gemacht und "
              "es ist auch nicht so gut für mich",
    "Italian": "Io non so che cosa vuoi da me, perché ho già detto che non ho niente per te "
               "e questo è tutto quello che ho",
    "Ukrainian": "Я не знаю, що ти хочеш від мене, тому що я вже сказав тобі, що у мене "
                 "нічого немає для тебе і її",
}


class TellingByTheWords(unittest.TestCase):
    def test_each_language_cleanview_cleans(self):
        for code, text in SAID.items():
            self.assertEqual(cvlang.which_language(text.split()), (code, None), code)

    def test_a_language_it_doesnt_clean_yet_is_named(self):
        for name, text in OTHERS.items():
            self.assertEqual(cvlang.which_language(text.split()), ("other", name), name)

    def test_too_little_to_tell(self):
        self.assertEqual(cvlang.which_language("Hello there, Castle.".split()), (None, None))
        self.assertEqual(cvlang.which_language([]), (None, None))
        # a few words are only enough when they're very clearly one language
        self.assertEqual(cvlang.which_language(
            "Alles hat ein Ende, nur die Wurst hat zwei.".split()), ("other", "German"))
        self.assertEqual(cvlang.which_language(
            "Castle and Beckett chased Esposito downtown.".split()), (None, None))

    def test_spanish_and_portuguese_are_told_apart(self):
        # they share "que", "por", "tu", "no", "para"; what the model heard of its own sample,
        # with and without the accents
        es = "No preguntes qué puede hacer tu país por ti, pregunta qué puedes hacer tú por tu país."
        self.assertEqual(cvlang.which_language(es.split()), ("es", None))
        self.assertEqual(cvlang.which_language(
            "No preguntes que puede hacer tu pais por ti pregunta que puedes hacer tu por tu "
            "pais".split()), ("es", None))
        pt = "Não perguntes o que o teu país pode fazer por ti, pergunta o que tu podes fazer pelo teu país."
        self.assertEqual(cvlang.which_language(pt.split()), ("pt", None))
        self.assertEqual(cvlang.which_language(
            "Nao perguntes o que o teu pais pode fazer por ti pergunta o que tu podes fazer "
            "pelo teu pais".split()), ("pt", None))

    def test_words_that_are_no_languages_little_words(self):
        names = "Castle Beckett Esposito Ryan Montgomery Alexis Martha Lanie Gates " * 3
        self.assertEqual(cvlang.which_language(names.split()), (None, None))

    def test_as_the_listening_model_writes_them(self):
        heard = [w.strip(",.") for w in SAID["es"].split()]           # one word at a time
        self.assertEqual(cvlang.which_language(heard), ("es", None))


class TheSoundTracksLabel(unittest.TestCase):
    def test_labels_cleanview_cleans(self):
        for tag, code in (("eng", "en"), ("spa", "es"), ("fre", "fr"), ("fra", "fr"),
                          ("por", "pt"), ("rus", "ru"), ("ENG", "en")):
            self.assertEqual(cvlang.tag_language(tag), (code, None), tag)

    def test_labels_it_doesnt_clean_yet(self):
        self.assertEqual(cvlang.tag_language("ger"), ("other", "German"))
        self.assertEqual(cvlang.tag_language("jpn"), ("other", "Japanese"))

    def test_no_label_to_go_by(self):
        for tag in ("", "und", None, "xx", "mul"):
            self.assertEqual(cvlang.tag_language(tag), (None, None), tag)


class TheChoice(unittest.TestCase):
    def test_english_first_then_auto(self):
        self.assertEqual(list(cvlang.CHOICES.items())[:3],
                         [("en", "English"), ("auto", "Auto"), ("es", "Spanish")])
        self.assertEqual(set(cvlang.CHOICES) - {"auto"}, set(cvlang.LANGS))
        self.assertEqual(engine.DEFAULTS["language"], "en")          # not Auto: it needs the model

    def test_a_saved_choice(self):
        self.assertEqual(cvlang.choice("auto"), "auto")
        self.assertEqual(cvlang.choice("ru"), "ru")
        self.assertEqual(cvlang.choice("klingon"), "en")
        self.assertEqual(cvlang.choice(None), "en")

    def test_auto_needs_the_listening_model_for_other_languages(self):
        self.assertTrue(cvlang.needs_model("auto"))
        self.assertTrue(cvlang.needs_model("fr"))
        self.assertFalse(cvlang.needs_model("en"))
        with mock.patch.dict(os.environ, {"CLEANVIEW_MULTI_MODEL": str(support.SANDBOX / "none")}):
            self.assertIn("listening model for other languages",
                          engine.tools_missing({"language": "auto"}))
            self.assertNotIn("listening model for other languages",
                             engine.tools_missing({"language": "en"}))

    def test_until_its_worked_out_it_counts_as_english(self):
        self.assertEqual(cl.use_language("auto"), "en")


class WorkingItOut(unittest.TestCase):
    def setUp(self):
        self.work = Path(tempfile.mkdtemp(dir=support.SANDBOX))
        self.model = self.work / "model"
        self.model.mkdir()
        for f in cvlang.MODEL_FILES:
            (self.model / f).write_bytes(b"x")
        patch = mock.patch.dict(os.environ, {"CLEANVIEW_MULTI_MODEL": str(self.model)})
        patch.start()
        self.addCleanup(patch.stop)
        self.listened = []

    def tell(self, tag, heard=()):
        def sample(path, info, rec, dur, cancel=None):
            self.listened.append(path)
            return list(heard)
        with mock.patch.object(engine.cl, "load_recognizer", lambda d, t=None: object()), \
                mock.patch.object(engine, "language_sample", sample):
            return engine.tell_language("D:/Films/Film.mkv", {"audio": {"lang": tag}},
                                        self.work, 5400.0)

    def test_the_label_is_enough(self):
        self.assertEqual(self.tell("spa"), ("es", "from the sound track's label"))
        self.assertEqual(self.listened, [])                       # nothing listened to

    def test_no_label_so_it_listens(self):
        self.assertEqual(self.tell("und", SAID["fr"].split()), ("fr", "from what was heard"))
        self.assertEqual(len(self.listened), 1)

    def test_worked_out_once(self):
        self.tell("", SAID["pt"].split())
        self.assertEqual(json.loads((self.work / "language.json").read_text())["language"], "pt")
        self.assertEqual(self.tell("", SAID["en"].split())[0], "pt")     # kept, not asked again
        self.assertEqual(len(self.listened), 1)

    def test_it_cant_tell_so_english(self):
        code, how = self.tell("", "la la la".split())
        self.assertEqual(code, "en")
        self.assertIn("couldn't be told", how)

    def test_a_language_it_doesnt_clean_is_said_plainly(self):
        for tag, heard, name in (("ger", (), "German"), ("", OTHERS["Italian"].split(), "Italian")):
            with self.assertRaises(engine.VideoError) as err:
                self.tell(tag, heard)
            said = str(err.exception)
            self.assertIn(f"Film.mkv is in {name}, which CleanView doesn't clean yet", said)
            self.assertIn("pick a language yourself in step 1", said)
        self.assertFalse((self.work / "language.json").exists())

    def test_no_label_and_no_model_says_what_to_do(self):
        for f in cvlang.MODEL_FILES:
            (self.model / f).unlink()
        with self.assertRaises(RuntimeError) as err:
            self.tell("")
        self.assertIn("Auto needs the listening model", str(err.exception))
        self.assertEqual(self.tell("eng")[0], "en")               # a label needs no model


@unittest.skipUnless(support.FFMPEG, "needs ffmpeg")
class TheMainSoundTrack(unittest.TestCase):
    def test_auto_takes_the_videos_own_main_track(self):
        out = Path(tempfile.mkdtemp(dir=support.SANDBOX)) / "two_tracks.mkv"
        subprocess.run([support.FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i",
                        "color=c=gray:s=160x120:d=1", "-f", "lavfi", "-i",
                        "sine=frequency=300:duration=1", "-f", "lavfi", "-i",
                        "sine=frequency=600:duration=1", "-map", "0:v", "-map", "1:a", "-map",
                        "2:a", "-metadata:s:a:0", "language=spa", "-metadata:s:a:1",
                        "language=eng", "-disposition:a:0", "default", "-disposition:a:1", "0",
                        "-shortest", str(out)], check=True)
        self.assertEqual(engine.probe(out)["audio"]["lang"], "eng")           # English: the dub
        self.assertEqual(engine.probe(out, "auto")["audio"]["lang"], "spa")   # Auto: its own


class StartPage(unittest.TestCase):
    def test_auto_in_the_drop_down(self):
        from test_ui import ui
        real = (ui.App._check_update, ui.App._check_every_ai)
        ui.App._check_update = lambda self, manual=False: None
        ui.App._check_every_ai = lambda self: None
        try:
            app = ui.App()
        except tk.TclError as ex:
            self.skipTest(f"no screen to draw on ({ex})")
        finally:
            ui.App._check_update, ui.App._check_every_ai = real
        try:
            app._go_step(1)
            app.update()
            box = app.language_box
            self.assertEqual(list(box.cget("values"))[:2], ["English", "Auto"])
            self.assertEqual(box.get(), "English")
            box.set("Auto")
            box.event_generate("<<ComboboxSelected>>")
            app.update()
            self.assertEqual(app._current_opts()["language"], "auto")
            app._save_settings()
            app.show_setup()
            app.update()
            self.assertEqual(app.language_box.get(), "Auto")              # remembered
            app.opts["language"].set("en")
            app._save_settings()
        finally:
            app.destroy()
            cl.use_language("en")


REAL = os.environ.get("CLEANVIEW_TEST_MULTI")


@unittest.skipUnless(REAL and support.FFMPEG and (Path(REAL) / "test_wavs" / "es.wav").exists(),
                     "set CLEANVIEW_TEST_MULTI to the real model's folder to hear real speech")
class RealSpeech(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = Path(tempfile.mkdtemp(dir=support.SANDBOX))
        cls.videos = {}
        for code in ("es", "fr", "en", "de"):
            out = cls.dir / f"sample_{code}.mkv"
            subprocess.run([support.FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i",
                            "color=c=gray:s=160x120:r=5", "-i",
                            str(Path(REAL) / "test_wavs" / f"{code}.wav"), "-shortest",
                            "-c:v", "libx264", "-c:a", "aac", str(out)], check=True)
            cls.videos[code] = out

    def tearDown(self):
        cl.use_language("en")

    def tell(self, code):
        video = self.videos[code]
        work = Path(tempfile.mkdtemp(dir=support.SANDBOX))
        info = engine.probe(str(video), "auto")
        with mock.patch.dict(os.environ, {"CLEANVIEW_MULTI_MODEL": REAL}):
            return engine.tell_language(str(video), info, work, info["duration"])

    def test_told_from_what_is_heard(self):
        for code in ("es", "fr", "en"):
            self.assertEqual(self.tell(code), (code, "from what was heard"), code)

    def test_german_is_said_plainly(self):
        with self.assertRaises(engine.VideoError) as err:
            self.tell("de")
        self.assertIn("is in German", str(err.exception))

    def test_a_whole_clean_on_auto(self):
        video = self.videos["es"]
        work = self.dir / "w"
        with mock.patch.dict(os.environ, {"CLEANVIEW_MULTI_MODEL": REAL}):
            st = engine.analyze(str(video), str(work), groups=("swearing",),
                                opts={"language": "auto", "ai": False, "autosubs": False,
                                      "nudity": False, "sex": False, "violence": False,
                                      "gore": False, "graphic": False, "disturbing": False})
        self.assertEqual(st["opts"]["language"], "es")
        self.assertEqual(st["scan"]["language"], "es")
        self.assertTrue((work / "transcript_es.json").exists())
        self.assertIn("Auto took this for Spanish (from what was heard).", st["notes"])
        self.assertEqual(cvlang.LANG, "es")


if __name__ == "__main__":
    unittest.main()
