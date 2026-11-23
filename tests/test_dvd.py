"""A DVD's own folder (1.18.164; the owner, with a VIDEO_TS folder chosen: the menus failed with
"has no sound in it" and the movie came out as four pieces; "Yes, build it", "will it combine
the parts"). Its menus and short titles are left out, and the movie's pieces are joined into one
video, cleaned as one movie, its clean copy beside the DVD's folder."""
import subprocess
import tempfile
import time
import tkinter as tk
import unittest
from pathlib import Path

import support
import cleanview as engine


def make_dvd(root, name="My Movie"):
    """A made-up DVD folder: menus with no sound, a short trailer, and a 12-second movie
    split into three pieces at byte boundaries, as a disc splits it."""
    ts = Path(root) / name / "VIDEO_TS"
    ts.mkdir(parents=True)
    ff = support.FFMPEG

    def ps(out, secs, sound=True):
        cmd = [ff, "-v", "error", "-y", "-f", "lavfi", "-i",
               f"testsrc=size=320x240:rate=25:duration={secs}"]
        if sound:
            cmd += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={secs}:sample_rate=48000",
                    "-c:a", "mp2"]
        cmd += ["-c:v", "mpeg2video", "-f", "vob", str(out)]
        subprocess.run(cmd, check=True, capture_output=True)
    ps(ts / "VIDEO_TS.VOB", 2, sound=False)
    ps(ts / "VTS_01_0.VOB", 2, sound=False)
    ps(ts / "VTS_01_1.VOB", 3)
    ps(ts / "VTS_02_0.VOB", 2, sound=False)
    movie = Path(root) / "whole.vob"
    ps(movie, 12)
    data = movie.read_bytes()
    third = len(data) // 3
    for k, (a, b) in enumerate(((0, third), (third, 2 * third), (2 * third, len(data))), 1):
        (ts / f"VTS_02_{k}.VOB").write_bytes(data[a:b])
    (ts / "VIDEO_TS.IFO").write_bytes(b"")
    return ts


class Base(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(dir=support.SANDBOX))
        self.saved_dir = engine.DVD_DIR
        engine.DVD_DIR = self.root / "dvd"

    def tearDown(self):
        engine.DVD_DIR = self.saved_dir


class Splitting(Base):
    def test_menus_and_trailer_left_out(self):
        ts = self.root / "Film" / "VIDEO_TS"
        ts.mkdir(parents=True)
        for name, size in (("VIDEO_TS.VOB", 10), ("VTS_01_0.VOB", 10), ("VTS_01_1.VOB", 50),
                           ("VTS_02_0.VOB", 10), ("VTS_02_1.VOB", 100), ("VTS_02_2.VOB", 100),
                           ("VTS_02_10.VOB", 0)):
            (ts / name).write_bytes(b"x" * size)
        chosen = [str(p) for p in ts.iterdir()] + [str(self.root / "Other.mp4")]
        others, dvds = engine.dvd_split(chosen)
        self.assertEqual(others, [str(self.root / "Other.mp4")])
        self.assertEqual(len(dvds), 1)
        self.assertEqual(dvds[0]["name"], "Film")
        self.assertEqual([Path(p).name for p in dvds[0]["parts"]], ["VTS_02_1.VOB", "VTS_02_2.VOB"])

    def test_pieces_found_when_only_one_was_chosen(self):
        ts = self.root / "Film" / "VIDEO_TS"
        ts.mkdir(parents=True)
        for k in (1, 2, 3):
            (ts / f"VTS_01_{k}.VOB").write_bytes(b"x" * 100)
        _, dvds = engine.dvd_split([str(ts / "VTS_01_2.VOB")])
        self.assertEqual(len(dvds[0]["parts"]), 3)

    def test_only_menus(self):
        ts = self.root / "Film" / "VIDEO_TS"
        ts.mkdir(parents=True)
        (ts / "VIDEO_TS.VOB").write_bytes(b"x")
        self.assertEqual(engine.dvd_split([str(ts / "VIDEO_TS.VOB")]), ([], []))

    def test_a_loose_vob_is_an_ordinary_video(self):
        self.assertEqual(engine.dvd_split(["C:/x/home movie.vob"]), (["C:/x/home movie.vob"], []))


@unittest.skipUnless(support.FFMPEG, "no ffmpeg here")
class Joining(Base):
    def test_joined_into_one_movie_saved_beside_the_dvd(self):
        ts = make_dvd(self.root)
        others, dvds = engine.dvd_split([str(p) for p in ts.glob("*.VOB")])
        movie = engine.join_dvd(dvds[0])
        self.assertEqual(movie.name, "My Movie.mkv")
        self.assertAlmostEqual(engine.cl.probe_duration(movie), 12, delta=0.6)
        info = engine.probe(movie)
        self.assertTrue(info["audio"])
        self.assertTrue(engine.dvd_ready(dvds[0]))
        self.assertEqual(engine.clean_folder(movie), self.root / "My Movie" / "Clean")
        self.assertEqual(engine.dvd_source(movie), ts)
        self.assertIsNone(engine.dvd_source(self.root / "whole.vob"))
        again = engine.join_dvd(dvds[0])            # ready: not joined again
        self.assertEqual(again, movie)

    def test_no_room(self):
        ts = make_dvd(self.root)
        _, dvds = engine.dvd_split([str(p) for p in ts.glob("*.VOB")])
        real = engine.shutil.disk_usage
        engine.shutil.disk_usage = lambda p: type("U", (), {"free": 1000})()
        try:
            with self.assertRaises(engine.VideoError) as cm:
                engine.join_dvd(dvds[0])
        finally:
            engine.shutil.disk_usage = real
        self.assertIn("isn't room", str(cm.exception))


@unittest.skipUnless(support.FFMPEG, "no ffmpeg here")
class StartPage(Base):
    def setUp(self):
        super().setUp()
        import test_ui
        self.ui = ui = test_ui.ui
        self.saved = ui.App._check_update, ui.App._check_every_ai
        ui.App._check_update = lambda self, manual=False: None
        ui.App._check_every_ai = lambda self: None
        try:
            self.app = ui.App()
        except tk.TclError as ex:
            ui.App._check_update, ui.App._check_every_ai = self.saved
            raise unittest.SkipTest(f"no screen to draw on ({ex})")
        self.app.update()

    def tearDown(self):
        try:
            self.app.destroy()
        finally:
            self.ui.App._check_update, self.ui.App._check_every_ai = self.saved
            super().tearDown()

    def test_dropped_dvd_folder_is_one_movie(self):
        ts = make_dvd(self.root)
        a = self.app
        a._dropped([str(ts.parent)])
        self.assertEqual(len(a.videos), 1)
        self.assertTrue(a.videos[0].endswith("My Movie.mkv"))
        a.start()                                   # still joining: it says to wait
        end = time.time() + 60
        while a._dvd_joining and time.time() < end:
            a.update()
            time.sleep(0.05)
        self.assertEqual(a._dvd_joining, {})
        self.assertTrue(Path(a.videos[0]).exists())
        self.assertIn("1 video", a.vid_lbl.cget("text"))
        self.assertIn("My Movie", a.vid_lbl.cget("text"))


if __name__ == "__main__":
    unittest.main()
