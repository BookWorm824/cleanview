"""Jason, 2026-11-07: Snow White wouldn't save, four times at about the same spot, and all
he saw was "Couldn't save the clean copy". Now:
1. after every usual way fails, one careful try (past damaged bits, more room between the
   streams, no subtitles) before giving up;
2. a full drive, a 4 GB drive and a locked file are said plainly;
3. otherwise every way's error is kept, and he's offered to send it in."""
import json
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

import support
import test_timing as T
import test_ui

import cleanview as engine
import cvcore as cl
import videoqueue as VQ

ui = test_ui.ui
real_popen = cl.popen


def failing_popen(message, careful_works=True):
    """ffmpeg that fails with `message` (the careful try works if careful_works)."""
    def popen(cmd, **kw):
        if careful_works and "-err_detect" in cmd:
            return real_popen(cmd, **kw)
        return subprocess.Popen([sys.executable, "-c",
                                 f"import sys; sys.stderr.write({message!r}); sys.exit(1)"], **kw)
    return popen


@T.needs_ffmpeg
class CarefulLastTry(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.video = support.SANDBOX / "Snow White {1937}.mp4"
        if not cls.video.exists():
            T.ffmpeg("-f", "lavfi", "-i", "testsrc=size=64x48:rate=10:duration=8", "-f", "lavfi",
                     "-i", "sine=frequency=440:duration=8", "-c:v", "libx264", "-c:a", "aac",
                     "-shortest", cls.video)

    def render(self, popen):
        work = Path(tempfile.mkdtemp(dir=support.SANDBOX))
        info = engine.probe(self.video)
        st = {"path": str(self.video), "info": info, "duration": info["duration"],
              "groups": [], "mutes": [], "scenes": [], "lines": [], "notes": [],
              "cues": [{"s": 1.0, "e": 2.0, "text": "Hello there."}]}
        (work / "analysis.json").write_text(json.dumps(st))
        cuts = [{"s": 3.0, "e": 4.0, "kind": ["Dark magic"], "why": "made up", "cut": True}]
        with mock.patch.object(cl, "popen", popen):
            return engine.render(work, work / "Clean", cuts, lines=[], words=[],
                                 encoders=[("h264_nvenc", []), engine.ENCODERS[-1]],
                                 log=lambda m: None)

    def test_careful_try_saves_it(self):
        res = self.render(failing_popen("Error while decoding stream #0:0"))
        self.assertTrue(Path(res["out"]).exists())
        rep = (Path(res["folder"]) / "Reports" / "Snow White {1937} - CleanView report.txt")
        self.assertIn("careful way", rep.read_text("utf8"))
        r = subprocess.run([support.FFMPEG, "-hide_banner", "-i", res["out"]],
                           capture_output=True, text=True)
        self.assertIn("Video:", r.stderr)
        self.assertNotIn("Subtitle:", r.stderr)       # the careful way leaves them out

    def test_every_error_is_kept(self):
        with self.assertRaises(RuntimeError) as cm:
            self.render(failing_popen("Error while decoding stream #0:0", careful_works=False))
        msg = str(cm.exception)
        self.assertIn("h264_nvenc:", msg)
        self.assertIn("careful libx264:", msg)
        self.assertEqual(VQ.plain_error(cm.exception),
                         "Couldn't save the clean copy of Snow White {1937}.mp4.")

    def test_full_drive(self):
        with self.assertRaises(OSError) as cm:
            self.render(failing_popen("av_interleaved_write_frame(): No space left on device"))
        self.assertTrue(VQ.plain_error(cm.exception).startswith("The drive is full"))

    def test_four_gb_drive(self):
        with self.assertRaises(RuntimeError) as cm:
            self.render(failing_popen("Error writing trailer: File too large"))
        self.assertIn("up to 4 GB", VQ.plain_error(cm.exception))


class SaveTrouble(unittest.TestCase):
    def test_reasons(self):
        self.assertEqual(engine.save_trouble("Error: No space left on device"), "full")
        self.assertIn("4 GB", engine.save_trouble("File too large"))
        self.assertIn("video player", engine.save_trouble("x.mp4: Permission denied"))
        self.assertIsNone(engine.save_trouble("Error while decoding stream #0:0"))


class OfferToSendIt(unittest.TestCase):
    def window(self):
        sent = []
        win = types.SimpleNamespace(
            _save_failures=[r"D:\Movies\Snow White {1937}.mp4" + "\n\nRuntimeError: Couldn't "
                            "save the clean copy:\nh264_nvenc: Error while decoding"],
            q=types.SimpleNamespace(put=lambda m: m[1]() if m[0] == "call" else None),
            _send_by_hand=lambda path, text: sent.append(("by hand", path)))
        return win, sent

    def test_sends_the_error(self):
        win, _ = self.window()
        got = []
        with mock.patch.object(ui.learn, "send_url", lambda: "https://example.invalid"), \
                mock.patch.object(ui.learn, "send", lambda p, kind: got.append(
                    (kind, json.loads(Path(p).read_text("utf8"))))), \
                mock.patch.object(ui, "chime", lambda: None), \
                mock.patch.object(ui.messagebox, "askyesno", lambda *a, **k: True), \
                mock.patch.object(ui.messagebox, "showinfo", lambda *a, **k: None), \
                mock.patch.object(ui.threading, "Thread",
                                  lambda target, daemon: types.SimpleNamespace(start=target)):
            ui.App._tell_save_failed(win, "The clean copy couldn't be saved.")
        (kind, note), = got
        self.assertEqual(kind, "problem")
        self.assertEqual(note["what"], "couldn't save the clean copy")
        self.assertIn("Error while decoding", note["note"])

    def test_no_inbox_just_says_it(self):
        win, _ = self.window()
        said = []
        with mock.patch.object(ui.learn, "send_url", lambda: ""), \
                mock.patch.object(ui.messagebox, "showwarning",
                                  lambda t, m, **k: said.append(m)):
            ui.App._tell_save_failed(win, "The clean copy couldn't be saved.")
        self.assertEqual(said, ["The clean copy couldn't be saved."])


if __name__ == "__main__":
    unittest.main()
