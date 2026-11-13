"""Other languages, Spanish first (1.18.80; the owner, 2026-11-13: "is it possible to add
additional language capabilities ... like if i wanted to scan a movie in spanish", then "i
would do the easier group of languages").

English stays exactly as it was (its own listening model and word lists). Picking Spanish on
step 1 uses Spanish word lists, looks for Spanish subtitles and the Spanish sound track, tells
the AI readers the dialogue is in Spanish, and listens with a model that's downloaded once.

Nothing here uses the internet: the model "download" comes from a little server in the test.
The last test hears real Spanish, and only runs when CLEANVIEW_TEST_MULTI names a folder with
the real listening model for other languages."""
import http.server
import io
import json
import os
import subprocess
import tarfile
import tempfile
import threading
import unittest
import tkinter as tk
from pathlib import Path
from unittest import mock

import support
import cvcore as cl
import cvlang
import cleanview as engine
import cleanview_ai as ai
import cleanview_claude as cc

ALL = list(cl.CATS)
SWEARING = [c for g in ("swearing", "mild", "deity", "minced", "samesexwords", "rude")
            for c in cl.GROUPS[g]]


def found(text, cats=ALL, mine=()):
    words = [w for w in (cl.norm(t) for t in text.split()) if w]
    return [(" ".join(words[i:j]), cat) for i, j, cat in cl.find_language(words, cats, mine)]


class Spanish(unittest.TestCase):
    def setUp(self):
        cl.use_language("es")
        self.addCleanup(cl.use_language, "en")

    def test_words_as_the_lists_have_them(self):
        self.assertEqual(cl.norm("¡Cabrón!"), "cabron")
        self.assertEqual(cl.norm("Cállate,"), "callate")
        self.assertEqual(cl.norm("año"), "año")            # a year, never without its ñ
        self.assertEqual(cl.norm("vergüenza."), "verguenza")
        self.assertEqual(cl.norm("¿Qué?"), "que")

    def test_swearing_is_found(self):
        self.assertEqual(found("Eres un cabrón de mierda"),
                         [("cabron", "strong"), ("mierda", "moderate")])
        self.assertEqual(found("¡Vete a la mierda, hijo de puta!"),
                         [("mierda", "moderate"), ("puta", "strong")])
        self.assertEqual(found("No me jodas, tío"), [("jodas", "strong")])
        self.assertEqual(found("¿Qué chingados haces, pendejo?"),
                         [("chingados", "strong"), ("pendejo", "moderate")])
        self.assertEqual(found("Ese hijo de perra me robó"), [("hijo de perra", "strong")])
        self.assertEqual(found("¡Joder, qué coño pasa!"), [("joder", "strong"), ("coño", "strong")])
        self.assertEqual(found("Me cago en todo"), [("cago", "moderate")])
        self.assertEqual(found("Es un gilipollas"), [("gilipollas", "moderate")])
        self.assertEqual(found("el pinche carro no arranca"), [("pinche", "moderate")])

    def test_milder_groups(self):
        self.assertEqual(found("¡Maldita sea!"), [("maldita sea", "mild")])
        self.assertEqual(found("¿Qué diablos fue eso?"), [("que diablos", "mild")])
        self.assertEqual(found("¡Rayos! Se me olvidó"), [("rayos", "minced")])
        self.assertEqual(found("¡Caramba, qué susto!"), [("caramba", "minced")])
        self.assertEqual(found("¡Ay, Dios mío!"), [("ay dios mio", "deity")])
        self.assertEqual(found("Por Dios, cállate"), [("por dios", "deity"), ("callate", "rude")])
        self.assertEqual(found("No seas tonto, cierra la boca"),
                         [("tonto", "rude"), ("cierra la boca", "rude")])
        self.assertEqual(found("Dicen que es gay"), [("gay", "samesex")])

    def test_everyday_words_are_left_alone(self):
        for text in ("Me dio un folleto con mucha vergüenza",
                     "Comimos pollo y encontré una concha en la playa",
                     "Mi perra se llama Luna y tiene diez años",
                     "Jesús vive en Madrid con su madre",
                     "Le hicieron rayos X en el hospital",
                     "Los rayos de sol entraban por la ventana",
                     "Voy a coger el tren de las ocho",
                     "Los huevos están fritos y el follaje es verde",
                     "Gracias por la ayuda, señor",
                     "Dios te bendiga, hijo",
                     "El infierno de Dante es un libro famoso"):
            self.assertEqual(found(text), [], text)

    def test_only_the_groups_that_are_ticked(self):
        rude_only = cl.GROUPS["rude"]
        self.assertEqual(found("Cabrón, eres tonto", rude_only), [("tonto", "rude")])
        self.assertEqual(found("¡Dios mío, qué mierda!", cl.GROUPS["swearing"]),
                         [("mierda", "moderate")])
        self.assertEqual(found("¡Dios mío, qué mierda!", []), [])

    def test_her_own_words_always(self):
        mine = [("que", "asco"), ("porqueria",)]
        self.assertEqual(found("¡Qué asco de porquería!", [], mine),
                         [("que asco", "mine"), ("porqueria", "mine")])

    def test_only_listed_words_may_be_muted_alone(self):
        self.assertTrue(cl.listed_word("mierda"))
        self.assertTrue(cl.listed_word("Dios mío"))
        self.assertTrue(cl.listed_word("¡Cabrón!"))
        self.assertTrue(cl.listed_word("sexo"))
        self.assertFalse(cl.listed_word("Grafi"))             # a misheard name
        self.assertFalse(cl.listed_word("mesa"))
        self.assertFalse(cl.listed_word("tonto", cats=cl.GROUPS["swearing"]))
        self.assertTrue(cl.listed_word("tonto", cats=cl.GROUPS["rude"]))

    def test_masked_in_the_review(self):
        self.assertEqual(cl.mask("mierda"), "m*****")
        self.assertEqual(cl.mask("cabrón"), "c*****")

    def test_english_swears_are_not_looked_for_in_spanish(self):
        # "negro" (black) and "Morón" (a town) are everyday Spanish
        self.assertEqual(found("El gato negro vive en Morón"), [])

    def test_saved_files_are_kept_apart(self):
        self.assertEqual(engine._lang_file("transcript.json"), "transcript_es.json")
        self.assertEqual(engine._lang_file("downloaded.srt"), "downloaded_es.srt")


class EnglishAsBefore(unittest.TestCase):
    def test_english_is_the_language_unless_told(self):
        self.assertEqual(cvlang.LANG, "en")
        self.assertEqual(engine.DEFAULTS["language"], "en")
        self.assertEqual(cl.use_language("klingon"), "en")
        self.assertEqual(cl.use_language(None), "en")

    def test_english_words_found_as_before(self):
        self.assertEqual(found("Well damn it, you stupid idiot"),
                         [("damn", "mild"), ("stupid", "rude"), ("idiot", "rude")])
        self.assertEqual(cl.norm("Cabrón!"), "cabrn")        # English leaves accents out
        self.assertEqual(found("Eres un cabrón, joder"), [])
        self.assertEqual(cl.mask("damn"), "d***")
        self.assertEqual(engine._lang_file("transcript.json"), "transcript.json")

    def test_going_back_to_english(self):
        cl.use_language("es")
        self.assertEqual(found("¡Joder!"), [("joder", "strong")])
        cl.use_language("en")
        self.assertEqual(found("¡Joder!"), [])


class Readers(unittest.TestCase):
    """The AI that reads the dialogue is told what language it's reading."""

    def tearDown(self):
        cl.use_language("en")

    def test_the_note(self):
        self.assertEqual(cvlang.reader_note("en"), "")
        note = cvlang.reader_note("es")
        self.assertIn("in Spanish", note)
        self.assertIn("never translated", note)

    def asked_of_the_helper(self, images=None):
        seen = {}

        def now(payload, model, timeout):
            seen["text"] = payload["messages"][0]["content"]
            return {}
        with mock.patch.object(ai, "_chat_now", now), \
                mock.patch.object(ai, "_saved_answer", lambda key: None), \
                mock.patch.object(ai, "_save_answer", lambda key, answer: None), \
                mock.patch.object(ai, "time_factor", lambda model: 1):
            ai.chat("Which lines fit?", images=images)
        return seen["text"]

    def test_the_ai_helper(self):
        self.assertEqual(self.asked_of_the_helper(), "Which lines fit?")
        cl.use_language("es")
        self.assertIn("The dialogue is in Spanish", self.asked_of_the_helper())
        # a question about a picture isn't about the dialogue
        self.assertEqual(self.asked_of_the_helper(images=["abc"]), "Which lines fit?")

    def asked_of_claude(self, system):
        seen = {}

        def now(prompt, schema, stdin_text, system, *rest):
            seen["system"] = system
            return {}, None
        with mock.patch.object(cc, "_ask_now", now), \
                mock.patch.object(cc, "_saved_answer", lambda key: None), \
                mock.patch.object(cc, "_save_answer", lambda key, answer: None):
            cc.ask("Read these", {}, "1: Hola", system=system)
        return seen["system"]

    def test_claude_chatgpt_and_gemini(self):
        self.assertEqual(self.asked_of_claude(cc.SYSTEM), cc.SYSTEM)
        cl.use_language("es")
        self.assertIn("The dialogue is in Spanish", self.asked_of_claude(cc.SYSTEM))
        self.assertEqual(self.asked_of_claude(cc.PIC_SYSTEM), cc.PIC_SYSTEM)   # pictures: as before


def model_archive(files=cvlang.MODEL_FILES):
    """A small stand-in for the model's download: its files in a folder, plus a read-me."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:bz2") as tf:
        for name in tuple(files) + ("README.md",):
            data = f"made-up {name}".encode()
            info = tarfile.TarInfo(f"{cvlang.MODEL_NAME}/{name}")
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    return buf.getvalue()


class Serve:
    """A web server on this PC only, handing out one body."""

    def __init__(self, body):
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/model.tar.bz2"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


class TheModel(unittest.TestCase):
    """The listening model for other languages: only for people who pick one, downloaded once."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(dir=support.SANDBOX)) / "the-model"
        patch = mock.patch.dict(os.environ, {"CLEANVIEW_MULTI_MODEL": str(self.dir)})
        patch.start()
        self.addCleanup(patch.stop)

    def test_english_never_needs_it(self):
        self.assertFalse(cvlang.model_ready())
        self.assertNotIn("listening model for other languages",
                         engine.tools_missing({"language": "en"}))
        self.assertIn("listening model for other languages",
                      engine.tools_missing({"language": "es"}))

    def test_downloaded_once_and_put_in_place(self):
        said = []
        web = Serve(model_archive())
        self.addCleanup(web.close)
        cvlang.install_model(lambda f, m: said.append((f, m)), url=web.url)
        self.assertTrue(cvlang.model_ready())
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()), sorted(cvlang.MODEL_FILES))
        self.assertEqual([p.name for p in self.dir.parent.iterdir()], ["the-model"])   # no leftovers
        self.assertIn("one time", said[0][1])
        self.assertEqual(said[-1][0], 1.0)
        self.assertEqual([f for f, _ in said], sorted(f for f, _ in said))    # only forward
        self.assertNotIn("listening model for other languages",
                         engine.tools_missing({"language": "es"}))

    def test_a_download_that_looks_wrong(self):
        for body in (b"this is not an archive", model_archive(cvlang.MODEL_FILES[:2])):
            web = Serve(body)
            with self.assertRaises(RuntimeError) as err:
                cvlang.install_model(url=web.url)
            web.close()
            self.assertIn("looked wrong. Try again.", str(err.exception))
            self.assertFalse(cvlang.model_ready())
            self.assertEqual([p.name for p in self.dir.parent.iterdir() if p.name != "the-model"],
                             [])

    def test_no_internet(self):
        with self.assertRaises(RuntimeError) as err:
            cvlang.install_model(url="http://127.0.0.1:9/model.tar.bz2")
        self.assertIn("Check your internet connection", str(err.exception))
        self.assertFalse(cvlang.model_ready())

    def test_a_spanish_video_without_it_says_so(self):
        work = Path(tempfile.mkdtemp(dir=support.SANDBOX))
        info = {"duration": 5.0, "audio": {"index": 1, "channels": 2}, "subs": [], "video": {}}
        with mock.patch.object(engine, "probe", lambda path, language="en": info), \
                mock.patch.object(engine, "fetch_subtitles",
                                  lambda *a, **k: ([], "", None, "")):
            with self.assertRaises(RuntimeError) as err:
                engine.analyze(str(work / "pelicula.mkv"), str(work), groups=("swearing",),
                               opts={"language": "es", "ai": False, "autosubs": False,
                                     "nudity": False, "sex": False, "violence": False,
                                     "gore": False, "graphic": False, "disturbing": False})
        cl.use_language("en")
        self.assertIn("The listening model for Spanish isn't on this PC yet", str(err.exception))


SRT = "\n".join(f"{i}\n00:00:{i:02d},000 --> 00:00:{i:02d},900\n{{}} {i}\n" for i in range(1, 9))


class Subtitles(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(dir=support.SANDBOX))
        self.video = self.dir / "Pelicula.mkv"
        self.video.write_bytes(b"")
        (self.dir / "Pelicula.en.srt").write_text(SRT.replace("{}", "English line"), encoding="utf8")
        (self.dir / "Pelicula.es.srt").write_text(SRT.replace("{}", "Línea en español"), encoding="utf8")
        self.info = {"subs": []}

    def test_the_videos_own_language(self):
        cues, where = engine.find_subtitles(self.video, self.info, self.dir, "es")
        self.assertEqual(where, "subtitles from Pelicula.es.srt")
        self.assertIn("español", cues[0]["text"])
        cues, where = engine.find_subtitles(self.video, self.info, self.dir)
        self.assertEqual(where, "subtitles from Pelicula.en.srt")

    def test_english_subtitles_are_not_a_spanish_videos_words(self):
        (self.dir / "Pelicula.es.srt").unlink()
        self.assertEqual(engine.find_subtitles(self.video, self.info, self.dir, "es"), ([], ""))

    def test_looked_up_online_in_that_language(self):
        try:
            import babelfish  # noqa: F401
        except ImportError:
            self.skipTest("the subtitle finder isn't installed here")
        self.assertEqual(str(engine._sub_language()), "en")
        cl.use_language("es")
        self.addCleanup(cl.use_language, "en")
        self.assertEqual(str(engine._sub_language()), "es")

    @unittest.skipUnless(support.FFMPEG, "needs ffmpeg")
    def test_the_spanish_sound_track_is_the_one_heard(self):
        out = self.dir / "two_tracks.mkv"
        subprocess.run([support.FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i",
                        "color=c=gray:s=160x120:d=1", "-f", "lavfi", "-i",
                        "sine=frequency=300:duration=1", "-f", "lavfi", "-i",
                        "sine=frequency=600:duration=1", "-map", "0:v", "-map", "1:a", "-map",
                        "2:a", "-metadata:s:a:0", "language=eng", "-metadata:s:a:1",
                        "language=spa", "-disposition:a:0", "default", "-shortest", str(out)],
                       check=True)
        self.assertEqual(engine.probe(out)["audio"]["index"], 1)           # English, as before
        self.assertEqual(engine.probe(out, "es")["audio"]["index"], 2)


class StartPage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from test_ui import ui
        cls.ui = ui
        cls.real = (ui.App._check_update, ui.App._check_every_ai)
        ui.App._check_update = lambda self, manual=False: None
        ui.App._check_every_ai = lambda self: None
        try:
            cls.app = ui.App()
        except tk.TclError as ex:
            ui.App._check_update, ui.App._check_every_ai = cls.real
            raise unittest.SkipTest(f"no screen to draw on ({ex})")
        cls.app.update()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.app.destroy()
        except tk.TclError:
            pass
        cls.ui.App._check_update, cls.ui.App._check_every_ai = cls.real
        cl.use_language("en")

    def test_english_unless_she_picks_another(self):
        self.assertEqual(self.app.opts["language"].get(), "en")
        self.assertEqual(self.app._current_opts()["language"], "en")

    def test_her_choice_is_used_and_remembered(self):
        self.app.opts["language"].set("es")
        self.assertEqual(self.app._current_opts()["language"], "es")
        self.app._save_settings()
        self.assertEqual(self.app._load_settings()["language"], "es")
        self.app.show_setup()
        self.app.update()
        self.assertEqual(self.app.opts["language"].get(), "es")
        self.app.opts["language"].set("en")
        self.app._save_settings()

    def test_a_language_this_version_doesnt_know(self):
        settings = self.app._load_settings()
        settings["language"] = "klingon"
        (support.APP_DATA / "cleanview_settings.json").write_text(json.dumps(settings))
        self.app.show_setup()
        self.app.update()
        self.assertEqual(self.app.opts["language"].get(), "en")


REAL = os.environ.get("CLEANVIEW_TEST_MULTI")


@unittest.skipUnless(REAL and support.FFMPEG and (Path(REAL) / "test_wavs" / "es.wav").exists(),
                     "set CLEANVIEW_TEST_MULTI to the real model's folder to hear real Spanish")
class RealSpanish(unittest.TestCase):
    def test_a_spanish_video_from_listening_to_the_word_list(self):
        work = Path(tempfile.mkdtemp(dir=support.SANDBOX))
        video = work / "muestra.mkv"
        subprocess.run([support.FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i",
                        "color=c=gray:s=160x120:r=5", "-i", str(Path(REAL) / "test_wavs" / "es.wav"),
                        "-shortest", "-c:v", "libx264", "-c:a", "aac", str(video)], check=True)
        cl.use_language("es")
        rec = cl.load_recognizer(REAL, 4)
        heard = engine.transcribe(str(video), engine.probe(str(video), "es"), rec)
        del rec
        self.assertGreater(len(heard), 5)
        pick = max((w["t"] for w in heard), key=len)          # a long word it heard, as her own
        cl.use_language("en")
        with mock.patch.dict(os.environ, {"CLEANVIEW_MULTI_MODEL": REAL}):
            st = engine.analyze(str(video), str(work / "w"), groups=("swearing",),
                                opts={"language": "es", "ai": False, "autosubs": False,
                                      "mywords": [pick], "nudity": False, "sex": False,
                                      "violence": False, "gore": False, "graphic": False,
                                      "disturbing": False})
        cl.use_language("en")
        self.assertEqual(st["scan"]["language"], "es")
        self.assertTrue((work / "w" / "transcript_es.json").exists())
        self.assertFalse((work / "w" / "transcript.json").exists())
        self.assertTrue(any("Cleaned as a Spanish video" in n for n in st["notes"]))
        mine = [m for m in st["mutes"] if m["cat"] == "mine"]
        self.assertTrue(mine, st["mutes"])
        self.assertEqual(mine[0]["raw"], cvlang.norm(pick, "es"))


if __name__ == "__main__":
    unittest.main()
