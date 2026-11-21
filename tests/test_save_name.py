"""This app shows "CleanView Save" wherever people read its name (1.18.157; the owner: "Yes,
everywhere", so CleanView Play can be shown as "CleanView"): messages, the opening box, Task
Manager and the shortcut. Folders, files and the update seal stay "CleanView"."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import support  # noqa: F401  (must come first)

import cleanview as engine
import cleanview_learn as learn
import launcher as lm


class Names(unittest.TestCase):
    def test_shown_and_kept(self):
        self.assertEqual(lm.SHOWN, "CleanView Save")
        self.assertEqual(lm.APP_NAME, "CleanView")             # the seal and the folder
        self.assertEqual(lm.SEAL_FOR, "CleanView update\n")
        self.assertEqual(lm.SHORTCUT, "CleanView Save.lnk")
        self.assertEqual(lm.OLD_SHORTCUT, "CleanView.lnk")

    def test_the_report_and_notes(self):
        self.assertIn("CleanView Save", engine.TECHNICAL_HEAD)
        self.assertEqual(engine.LINE_LABEL["shared"], "CleanView Save learned")
        st = {"notes": ["The AI helper used x for the picture (CleanView 1.18.150)."],
              "scan": {"app_version": "1.18.150"}}
        # a review made before the rename isn't given its version twice
        self.assertEqual(sum("1.18.150" in n for n in engine.technical_notes(st)), 1)

    def test_a_lesson_by_either_name(self):
        self.assertTrue(learn.same_lesson("CleanView learned this scene",
                                          "CleanView Save learned this scene"))
        self.assertFalse(learn.same_lesson("you kept this scene before",
                                           "CleanView Save learned this scene"))

    def test_task_manager_name_given_again(self):
        # the mark the .exes are checked against changes with the name, so they're redone once
        with tempfile.TemporaryDirectory() as d:
            ico = Path(d) / "x.ico"
            ico.write_bytes(b"icon")
            self.assertTrue(lm._icon_mark(ico).endswith(" CleanView Save"))


@unittest.skipUnless(os.name == "nt", "Windows shortcuts")
class Shortcut(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(dir=support.SANDBOX))
        self.here = self.dir / "app"
        self.here.mkdir()
        self.places, self.named = lm.NAME_PLACES, lm.SHORTCUT_NAMED
        lm.NAME_PLACES = "@('" + str(self.dir / "desk").replace("'", "''") + "')"
        lm.SHORTCUT_NAMED = self.dir / "shortcut_named.txt"
        (self.dir / "desk").mkdir()

    def tearDown(self):
        lm.NAME_PLACES, lm.SHORTCUT_NAMED = self.places, self.named

    def make(self, name, launcher):
        p = self.dir / "desk" / name
        script = ("$s = New-Object -ComObject WScript.Shell; "
                  f"$l = $s.CreateShortcut('{p}'); $l.TargetPath = 'C:\\Windows\\notepad.exe'; "
                  f"$l.Arguments = '\"{launcher}\"'; $l.Save()")
        subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                       check=True, capture_output=True, creationflags=0x08000000)
        return p

    def test_ours_renamed_others_left(self):
        self.make("CleanView.lnk", self.here / "launcher.pyw")
        self.assertTrue(lm.name_shortcuts(self.here))
        names = sorted(p.name for p in (self.dir / "desk").iterdir())
        self.assertEqual(names, ["CleanView Save.lnk"])
        self.assertFalse(lm.name_shortcuts(self.here))           # once
        # another app's "CleanView" (Play, shown as CleanView) isn't touched
        lm.SHORTCUT_NAMED.unlink()
        self.make("CleanView.lnk", self.dir / "play" / "launcher.pyw")
        lm.name_shortcuts(self.here)
        self.assertEqual(sorted(p.name for p in (self.dir / "desk").iterdir()),
                         ["CleanView Save.lnk", "CleanView.lnk"])

    def test_old_one_goes_when_new_is_there(self):
        self.make("CleanView.lnk", self.here / "launcher.pyw")
        self.make("CleanView Save.lnk", self.here / "launcher.pyw")
        lm.name_shortcuts(self.here)
        self.assertEqual([p.name for p in (self.dir / "desk").iterdir()], ["CleanView Save.lnk"])


if __name__ == "__main__":
    unittest.main()
