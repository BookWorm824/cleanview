"""The logo's slight 3D look (1.18.107; the owner, 2026-11-15: "its kinda flat looking. I think
it needs to have a slight 3d look", picked mockup "E · All of it", then "fix new logo in app
screen and on desktops"). cleanview.ico is made by tools/icon_3d.py from
tools/cleanview_flat.ico; the launcher gives CleanView.exe the new icon and points this
install's shortcuts at a copy named by its contents, so Windows draws the new one."""
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

import support  # noqa: F401  (must come first)
from test_own_exe import ROOT, load_launcher

spec = importlib.util.spec_from_file_location("icon_3d", ROOT / "tools" / "icon_3d.py")
icon_3d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(icon_3d)

WIN = os.name == "nt"
FLAT, NEW = ROOT / "tools" / "cleanview_flat.ico", ROOT / "cleanview.ico"


def ps(script):
    return subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                          capture_output=True, text=True, timeout=60, creationflags=0x08000000,
                          stdin=subprocess.DEVNULL, check=True).stdout.strip()


def q(s):
    return "'" + str(s).replace("'", "''") + "'"


def make_shortcut(lnk, arguments, icon):
    ps(f"$l = (New-Object -ComObject WScript.Shell).CreateShortcut({q(lnk)}); "
       f"$l.TargetPath = {q(sys.executable)}; $l.Arguments = {q(arguments)}; "
       f"$l.IconLocation = {q(icon)}; $l.Save()")


def icon_of(lnk):
    return ps(f"(New-Object -ComObject WScript.Shell).CreateShortcut({q(lnk)}).IconLocation")


class TheIcon(unittest.TestCase):
    def test_made_from_the_flat_one(self):
        new = icon_3d.read_ico(NEW)
        self.assertEqual(sorted(new), list(icon_3d.SIZES))
        made = icon_3d.three_d(icon_3d.png_rgba(icon_3d.read_ico(FLAT)[256]))
        self.assertTrue(np.array_equal(icon_3d.png_rgba(new[256]), made))

    def test_lighter_at_the_top_and_the_picture_kept(self):
        flat = icon_3d.png_rgba(icon_3d.read_ico(FLAT)[256]).astype(int)
        new = icon_3d.png_rgba(icon_3d.read_ico(NEW)[256]).astype(int)
        self.assertTrue(np.array_equal(flat[..., 3], new[..., 3]))     # the same shape
        self.assertGreater(new[30, 128, :3].sum(), flat[30, 128, :3].sum())    # top lighter
        self.assertLess(new[230, 128, :3].sum(), flat[230, 128, :3].sum())     # bottom darker
        white = flat[..., :3].min(axis=2) > 240
        self.assertGreater(new[white][:, :3].min(), 200)               # the picture still white


@unittest.skipUnless(WIN and sys.prefix != sys.base_prefix
                     and (Path(sys.prefix) / "pyvenv.cfg").exists(),
                     "needs Windows and the app's venv")
class OnTheExes(unittest.TestCase):
    def setUp(self):
        self.lm = load_launcher()
        self.tmp = Path(tempfile.mkdtemp(prefix="cv-logo-exe-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        venv = self.tmp / "venv"
        venv.mkdir()
        shutil.copy2(Path(sys.prefix) / "pyvenv.cfg", venv / "pyvenv.cfg")
        self.folder = venv / "CleanView"
        self.assertTrue(self.lm.make_own_exe(self.folder, sys.base_prefix, FLAT))

    def has(self, exe, ico):
        return icon_3d.read_ico(ico)[256] in (self.folder / exe).read_bytes()

    def test_exes_made_before_get_the_new_icon_once(self):
        self.assertTrue(self.has("CleanView.exe", FLAT))
        exe = self.lm.make_own_exe(self.folder, sys.base_prefix, NEW)
        for name in ("CleanView.exe", "CleanView-work.exe"):
            self.assertTrue(self.has(name, NEW), name)
            self.assertFalse(self.has(name, FLAT), name)
        when = exe.stat().st_mtime_ns
        self.lm.make_own_exe(self.folder, sys.base_prefix, NEW)
        self.assertEqual(exe.stat().st_mtime_ns, when)                # not again
        r = subprocess.run([str(self.folder / "CleanView-work.exe"), "-c", "print(6 * 7)"],
                           capture_output=True, text=True, timeout=60,
                           creationflags=0x08000000)
        self.assertEqual(r.stdout.strip(), "42")                       # still runs

    def test_one_in_use_is_left_and_tried_next_time(self):
        with mock.patch.object(self.lm.os, "replace", side_effect=PermissionError("in use")):
            self.lm.make_own_exe(self.folder, sys.base_prefix, NEW)
        self.assertTrue(self.has("CleanView.exe", FLAT))
        self.assertEqual(list(self.folder.glob("*.new")), [])
        self.lm.make_own_exe(self.folder, sys.base_prefix, NEW)
        self.assertTrue(self.has("CleanView.exe", NEW))


@unittest.skipUnless(WIN, "Windows only")
class OnTheShortcuts(unittest.TestCase):
    def setUp(self):
        self.lm = load_launcher()
        self.tmp = Path(tempfile.mkdtemp(prefix="cv-logo-lnk-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.here = self.tmp / "app folder's"
        self.mine, self.other = self.tmp / "desktop", self.tmp / "elsewhere"
        for d in (self.here, self.mine, self.other):
            d.mkdir()
        shutil.copy2(NEW, self.here / "cleanview.ico")
        make_shortcut(self.mine / "CleanView.lnk", f'"{self.here / "launcher.pyw"}"',
                      self.here / "cleanview.ico")
        make_shortcut(self.other / "CleanView.lnk", r'"D:\another\launcher.pyw"',
                      r"D:\another\cleanview.ico")
        places = "@(" + ", ".join(q(d) for d in (self.mine, self.other, self.tmp / "none")) + ")"
        for name, value in (("SHORTCUT_PLACES", places), ("ICON_SHOWN", self.tmp / "shown.txt"),
                            ("APP_DATA", self.tmp)):
            p = mock.patch.object(self.lm, name, value)
            p.start()
            self.addCleanup(p.stop)

    def test_pointed_at_a_copy_named_by_its_contents(self):
        self.assertTrue(self.lm.new_icon_on_shortcuts(self.here))
        mark = self.lm._icon_mark(self.here / "cleanview.ico")
        shown = self.here / f"cleanview-{mark}.ico"
        self.assertEqual(shown.read_bytes(), NEW.read_bytes())
        self.assertEqual(icon_of(self.mine / "CleanView.lnk"), f"{shown},0")
        self.assertEqual(icon_of(self.other / "CleanView.lnk"), r"D:\another\cleanview.ico,0")
        self.assertFalse(self.lm.new_icon_on_shortcuts(self.here))           # once

    def test_again_when_the_icon_changes(self):
        self.lm.new_icon_on_shortcuts(self.here)
        first = list(self.here.glob("cleanview-*.ico"))
        shutil.copy2(FLAT, self.here / "cleanview.ico")
        self.assertTrue(self.lm.new_icon_on_shortcuts(self.here))
        now = list(self.here.glob("cleanview-*.ico"))
        self.assertEqual(len(now), 1)
        self.assertNotEqual(now, first)
        self.assertEqual(icon_of(self.mine / "CleanView.lnk"), f"{now[0]},0")

    def test_no_shortcut_of_its_own_leaves_no_copy(self):
        (self.mine / "CleanView.lnk").unlink()
        self.assertTrue(self.lm.new_icon_on_shortcuts(self.here))
        self.assertEqual(list(self.here.glob("cleanview-*.ico")), [])


if __name__ == "__main__":
    unittest.main()
