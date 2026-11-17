"""A clean copy cleaned again replaces itself, not "(Clean) (Clean)" (1.18.117; the owner,
2026-11-16: "if a cleaned folder is reopened, saving it again creates a clean clean file. if it
already marked clean can overwrite it", "but don't overwright the original")."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import support
import test_timing as T

import cleanview as engine


class Names(unittest.TestCase):
    def test_marks_come_off(self):
        for stem, base in (("Castle S1E2 (Clean)", "Castle S1E2"),
                           ("Castle S1E2 (Clean) (Clean)", "Castle S1E2"),
                           ("Movie (clean)", "Movie"), ("Castle S1E2", "Castle S1E2"),
                           ("Clean Slate", "Clean Slate"), ("Mr. Clean", "Mr. Clean")):
            self.assertEqual(engine.clean_stem(stem), base, stem)

    def test_where_it_goes(self):
        tv = Path("D:/TV")
        self.assertEqual(engine.clean_folder(tv / "Castle S1E2.mp4"), tv / "Clean")
        self.assertEqual(engine.clean_folder(tv / "Clean" / "Castle S1E2 (Clean).mp4"),
                         tv / "Clean")


@T.needs_ffmpeg
class SavedAgain(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(dir=support.SANDBOX))
        self.original = self.root / "Show S01E01.mp4"
        T.ffmpeg("-f", "lavfi", "-i", "testsrc=size=64x48:rate=10:duration=12", "-f", "lavfi",
                 "-i", "sine=frequency=440:duration=12", "-c:v", "libx264", "-c:a", "aac",
                 "-shortest", self.original)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def render(self, video, cut):
        work = Path(tempfile.mkdtemp(dir=self.root))
        info = engine.probe(video)
        st = {"path": str(video), "info": info, "duration": info["duration"],
              "groups": [], "mutes": [], "scenes": [], "lines": [], "notes": [], "cues": []}
        (work / "analysis.json").write_text(json.dumps(st))
        return engine.render(work, str(engine.clean_folder(video)), [cut],
                             encoders=[engine.ENCODERS[-1]], log=lambda m: None)

    def test_replaces_itself_and_leaves_the_original(self):
        before = self.original.read_bytes()
        first = Path(self.render(self.original, {"s": 2.0, "e": 4.0})["out"])
        self.assertEqual(first, self.root / "Clean" / "Show S01E01 (Clean).mp4")
        second = Path(self.render(first, {"s": 5.0, "e": 7.0})["out"])
        self.assertEqual(second, first)                               # the same file, replaced
        self.assertAlmostEqual(engine.probe(second)["duration"], 8.0, delta=0.6)
        files = sorted(p.name for p in (self.root / "Clean").iterdir())
        self.assertEqual(files, ["Reports", "Show S01E01 (Clean).mp4"])
        self.assertEqual(sorted(p.name for p in (self.root / "Clean" / "Reports").iterdir()),
                         ["Show S01E01 - CleanView report.txt"])
        self.assertEqual(self.original.read_bytes(), before)         # never written to


class ForestGumpCleanCopy(unittest.TestCase):
    """The other PC scanned "Forest Gump (Clean).mp4" on 1.18.114 and none of the four taught
    scenes were cut (the owner: "forest gump was scanned again. i dont think it caught those 4
    scene"): its name didn't match the film's, and two scenes end on lines whose swear words
    the clean copy's subtitles blank out ("— —, son.")."""
    LINES = [(2118.0, "I took the bus up to Memphis to see her perform in that show."),
             (2208.0, "Forrest, let me down!"),
             (3724.0, "I'd kind of like to see that."),
             (3740.0, "— —, son."),
             (4815.0, "Happy New Year, Lieutenant Dan!"),
             (4883.0, "You —. —. You freak."),
             (4890.0, "No, no.")]

    def test_the_same_film(self):
        self.assertEqual(engine.title_name("D:/Movies/Forest Gump (Clean).mp4"), "Forest Gump")
        self.assertEqual(engine.guess_title("D:/TV/Castle S1E2 (Clean).mp4"), ("Castle", 1, 2))

    def test_the_scenes_found(self):
        import cleanview_learn as learn
        dialogue = [{"s": s, "e": s + 2.0, "text": t} for s, t in self.LINES]
        got = learn.title_scenes("_movies", engine.title_name("Forest Gump (Clean).mp4"),
                                 dialogue, {"nudity", "sex", "sexref"})
        self.assertEqual([(g["s"], g["e"], g["kind"]) for g in got],
                         [(2120.0, 2210.5, ["Nudity"]), (3726.0, 3742.5, ["Nudity"]),
                          (4817.0, 4885.5, ["Sex scene"])])

    def test_a_taught_line_with_its_swear_word_blanked(self):
        import cleanview_learn as learn
        dialogue = [{"s": 1.0, "e": 3.0, "text": "Hey, Gump, get a load of the — on her!"},
                    {"s": 5.0, "e": 7.0, "text": "Get a load of the — on that car."}]
        added, _ = learn.apply("_movies@adults", dialogue, [], [], [], on={"sexref"})
        self.assertEqual([a["text"] for a in added], [dialogue[0]["text"]])

    def test_a_blanked_word_stands_for_one_word(self):
        import cleanview_learn as learn
        self.assertTrue(learn._masked_fits("— —, son.", "god damn son"))
        self.assertFalse(learn._masked_fits("—, son.", "god damn son"))
        self.assertFalse(learn._masked_fits("— —", "god damn"))     # nothing to go by
        self.assertFalse(learn._masked_fits("Come on, son.", "god damn son"))


if __name__ == "__main__":
    unittest.main()
