"""The language she picked, checked against what was heard (1.18.91, 2026-11-13; the owner
tried Monsters University set to Spanish "to see what it did": the model for other languages
heard its English word for word, the Spanish lists found nothing in it and 10 English words
went through, the Spanish subtitles found online didn't line up, and nothing said so. Asked
whether to switch or only warn, she chose "switch and say so").

Picked another language than English, what was heard is told the way Auto tells it; when it's
clearly another language CleanView cleans, it's cleaned as that one (English listened to again
with English's own model, the subtitles looked for again in that language), and a note says so.
A language CleanView doesn't clean is only said. Picked English, nothing changes."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import support
import test_timing as T

import cvcore as cl
import cvlang
import cleanview as engine
import cleanview_ai as ai

OPTS = {"nudity": False, "sexref": False, "samesex": False, "violence": False, "sex": False,
        "gore": False, "graphic": False, "disturbing": False, "medical": False,
        "loudmusic": False, "ai": False, "autosubs": True, "look": False}
ENGLISH = ("Well I think you should know what they said about the house when we were there, "
           "because it was not what I wanted at all. Damn it, Mike, you are such a jerk.")
SPANISH = ("Pero no sé qué es lo que quieres de mí, porque yo ya te dije que no tengo nada "
           "para ti y eso es todo lo que hay, joder.")
GERMAN = ("Ich weiß nicht, was du von mir willst, aber wir haben das nicht gemacht und es ist "
          "auch nicht so gut für mich.")


def words(text, start=1.0):
    return [{"t": w, "s": start + 0.4 * k, "e": start + 0.3 + 0.4 * k}
            for k, w in enumerate(text.split())]


@T.needs_ffmpeg
class ThePickedLanguageChecked(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.video = support.SANDBOX / "Switch Movie (2013).mp4"
        if not cls.video.exists():
            T.ffmpeg("-f", "lavfi", "-i", "testsrc=size=64x48:rate=10:duration=40", "-f",
                     "lavfi", "-i", "sine=frequency=300:duration=40", "-c:v", "libx264",
                     "-c:a", "aac", "-shortest", cls.video)

    def tearDown(self):
        cl.use_language("en")

    def run_analyze(self, picked, heard_other, heard_english=ENGLISH, work=None):
        """heard_other: what the model for other languages hears; heard_english: English's
        own model. Returns (analysis, which models listened, subtitle languages asked)."""
        work = Path(work or tempfile.mkdtemp(dir=support.SANDBOX))
        listened, subs_for = [], []

        def load(model_dir, threads=None):
            listened.append("other" if Path(model_dir) == self.multi else "english")
            return listened[-1]

        def transcribe(path, info, rec, progress=None, cancel=None, **k):
            if progress:
                progress(1.0)
            return words(heard_other if rec == "other" else heard_english)

        def subtitles(path, info, work, o, log=print):
            subs_for.append((o.get("language"), cvlang.LANG))
            return [], "", None, "none online"
        self.multi = support.SANDBOX / "multi-model"
        self.multi.mkdir(exist_ok=True)
        with mock.patch.object(cvlang, "model_ready", lambda: True), \
                mock.patch.object(cvlang, "model_dir", lambda: self.multi), \
                mock.patch.object(ai, "clip_ready", lambda: False), \
                mock.patch.object(engine, "load_listeners", load), \
                mock.patch.object(engine, "transcribe", transcribe), \
                mock.patch.object(engine, "fetch_subtitles", subtitles), \
                mock.patch.object(engine, "find_voices", lambda *a, **k: []), \
                mock.patch.object(engine, "make_thumbs", lambda *a, **k: None):
            engine.analyze(str(self.video), str(work), groups=["swearing", "mild", "rude"],
                           opts=dict(OPTS, language=picked), log=lambda m: None)
        st = json.loads((work / "analysis.json").read_text())
        return st, listened, subs_for, work

    def test_spanish_picked_english_heard_is_cleaned_as_english(self):
        st, listened, subs_for, work = self.run_analyze("es", ENGLISH)
        self.assertEqual(st["opts"]["language"], "en")
        self.assertEqual(st["opts"]["language_switched"], "es")
        self.assertEqual(st["scan"]["language"], "en")
        # heard with the model for other languages, then again with English's own
        self.assertEqual(listened, ["other", "english"])
        self.assertTrue((work / "transcript_es.json").exists())
        self.assertTrue((work / "transcript.json").exists())
        # the English lists found the English words
        self.assertEqual({m["raw"] for m in st["mutes"]}, {"damn", "jerk"})
        self.assertIn("You picked Spanish, but this video is in English (from what was heard), "
                      "so it was cleaned as English.", st["notes"])
        self.assertFalse(any("Cleaned as a Spanish video" in n for n in st["notes"]))
        # the subtitles were looked for again, in English, once the Spanish look had ended
        self.assertEqual(subs_for, [("es", "es"), ("en", "en")])

    def test_the_note_is_about_the_video_not_technical(self):
        st, *_ = self.run_analyze("es", ENGLISH)
        note = next(n for n in st["notes"] if n.startswith("You picked"))
        self.assertFalse(engine.technical(note))
        self.assertIn(note, engine.video_notes(st))

    def test_cleaned_again_it_uses_what_was_heard_before(self):
        work = Path(tempfile.mkdtemp(dir=support.SANDBOX))
        self.run_analyze("es", ENGLISH, work=work)
        st, listened, _, _ = self.run_analyze("es", ENGLISH, work=work)
        self.assertEqual(listened, [])               # both transcripts were kept
        self.assertEqual(st["opts"]["language"], "en")
        self.assertEqual({m["raw"] for m in st["mutes"]}, {"damn", "jerk"})

    def test_french_picked_spanish_heard_is_cleaned_as_spanish(self):
        st, listened, subs_for, work = self.run_analyze("fr", SPANISH)
        self.assertEqual(st["opts"]["language"], "es")
        self.assertEqual(listened, ["other"])        # the same model hears Spanish best
        self.assertTrue((work / "transcript_fr.json").exists())
        self.assertFalse((work / "transcript_es.json").exists())
        self.assertEqual([m["raw"] for m in st["mutes"]], ["joder"])
        self.assertIn("You picked French, but this video is in Spanish (from what was heard), "
                      "so it was cleaned as Spanish.", st["notes"])
        self.assertIn("Cleaned as a Spanish video, with the Spanish word lists.", st["notes"])
        self.assertEqual(subs_for, [("fr", "fr"), ("es", "es")])

    def test_the_right_language_picked_changes_nothing(self):
        st, listened, subs_for, _ = self.run_analyze("es", SPANISH)
        self.assertEqual(st["opts"]["language"], "es")
        self.assertNotIn("language_switched", st["opts"])
        self.assertEqual(listened, ["other"])
        self.assertEqual(subs_for, [("es", "es")])
        self.assertFalse(any(n.startswith("You picked") for n in st["notes"]))

    def test_a_language_cleanview_doesnt_clean_is_only_said(self):
        st, listened, subs_for, _ = self.run_analyze("es", GERMAN)
        self.assertEqual(st["opts"]["language"], "es")
        self.assertEqual(listened, ["other"])
        self.assertIn("This sounds like German, which CleanView doesn't clean yet, so only the "
                      "Spanish word lists you picked were used.", st["notes"])

    def test_too_little_heard_to_tell_changes_nothing(self):
        st, *_ = self.run_analyze("es", "okay yes")
        self.assertEqual(st["opts"]["language"], "es")
        self.assertFalse(any(n.startswith(("You picked", "This sounds like"))
                             for n in st["notes"]))

    def test_english_picked_is_never_checked(self):
        # English's own model hears everything as English, so there's nothing to tell by
        st, listened, subs_for, _ = self.run_analyze("en", SPANISH, heard_english=ENGLISH)
        self.assertEqual(st["opts"]["language"], "en")
        self.assertEqual(listened, ["english"])
        self.assertEqual(subs_for, [("en", "en")])


if __name__ == "__main__":
    unittest.main()
