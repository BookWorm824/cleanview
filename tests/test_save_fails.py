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


class NoRoom(unittest.TestCase):
    """A save that fails for lack of room says so (1.18.87; the owner, 2026-11-13: "i was saving
    a file before and i didnt have enough storage but didn't know cause it only failed but
    didn't say why")."""

    def test_what_counts_as_a_full_drive(self):
        self.assertTrue(ui.no_room(OSError(28, "No space left on device: av_interleaved_write")))
        full = OSError(28, "There is not enough space on the disk")
        full.winerror = 112
        self.assertTrue(ui.no_room(full))
        self.assertFalse(ui.no_room(RuntimeError("Couldn't save the clean copy of x.mp4")))
        self.assertFalse(ui.no_room(PermissionError(13, "Permission denied")))

    def test_what_she_can_put_right_herself(self):
        self.assertTrue(ui.her_fix(OSError(28, "No space left on device")))
        self.assertTrue(ui.her_fix(PermissionError(13, "Permission denied")))
        self.assertTrue(ui.her_fix(RuntimeError(
            "The drive the clean copy goes to can't hold a file this big (it only takes files "
            "up to 4 GB). Save it to another drive:\nlibx264: File too large")))
        self.assertTrue(ui.her_fix(RuntimeError(
            "CleanView wasn't allowed to write the clean copy there. It may be open in a video "
            "player:\nlibx264: Permission denied")))
        self.assertFalse(ui.her_fix(RuntimeError("Couldn't save the clean copy of x.mp4:\n...")))
        self.assertFalse(ui.her_fix(KeyError("lines")))

    def test_says_where_how_much_is_free_and_what_to_do(self):
        win = types.SimpleNamespace(_save_folder=lambda: "E:/Movies/Clean")
        with mock.patch.object(ui.engine, "free_space", lambda folder: 350 * 1024 ** 2):
            said = ui.App._no_room_said(win)
        self.assertIn("There isn't enough room on the drive", said)
        self.assertIn("Movies", said)
        self.assertIn("Only 350 MB is free there.", said)
        self.assertIn("Change", said)
        with mock.patch.object(ui.engine, "free_space", lambda folder: None):     # can't tell
            self.assertNotIn("is free there", ui.App._no_room_said(win))

    def save(self, error):
        """The saving step with a save that fails this way: (what she's told, what's kept to
        send in)."""
        out = []
        win = types.SimpleNamespace(
            jobs=[{"video": r"D:\Shows\Castle S01E01.mp4", "analysis": {"x": 1}, "work": "w",
                   "cuts": [], "lines": [], "words": None, "quiet": None}],
            outdir="E:/Clean", cancel_flag=False, run=0, _save_failures=["an older one"],
            q=types.SimpleNamespace(put=out.append), _no_room_said=lambda: "No room. Do this.")

        def fails(*a, **k):
            raise error
        with mock.patch.object(ui.engine, "render", fails), \
                mock.patch.object(ui, "save_details", lambda text: None):
            ui.App._render_now(win, 0)
        failed = next(m[2][2] for m in out if m[2][0] == "rendered")
        return failed, win._save_failures

    def test_a_full_drive_is_told_plainly_and_not_sent_in(self):
        failed, to_send = self.save(OSError(28, "No space left on device: writing trailer"))
        self.assertEqual(failed, ["Castle S01E01.mp4: No room. Do this."])
        self.assertEqual(to_send, [])                     # nothing to offer to send

    def test_a_file_open_in_a_player_is_told_and_not_sent_in(self):
        locked = PermissionError(13, "Permission denied")
        failed, to_send = self.save(locked)
        self.assertIn("open in another program", failed[0])
        self.assertEqual(to_send, [])

    def test_an_unexpected_failure_is_still_offered(self):
        failed, to_send = self.save(RuntimeError("Couldn't save the clean copy of Castle "
                                                 "S01E01.mp4:\nlibx264: Error while decoding"))
        self.assertIn("Couldn't save the clean copy", failed[0])
        self.assertEqual(len(to_send), 1)
        self.assertIn("Error while decoding", to_send[0])

    def test_with_nothing_to_send_shes_only_told(self):
        said, asked = [], []
        win = types.SimpleNamespace(_save_failures=[])
        with mock.patch.object(ui.learn, "send_url", lambda: "https://example.invalid"), \
                mock.patch.object(ui.messagebox, "showwarning",
                                  lambda t, m, **k: said.append(m)), \
                mock.patch.object(ui.messagebox, "askyesno",
                                  lambda *a, **k: asked.append(a) or True):
            ui.App._tell_save_failed(win, "The clean copy couldn't be saved:\n\nx.mp4: No room.")
        self.assertEqual(len(said), 1)
        self.assertEqual(asked, [])


if __name__ == "__main__":
    unittest.main()
