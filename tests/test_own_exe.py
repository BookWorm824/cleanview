"""CleanView's own name in Task Manager (Jason, 2026-11-03: it showed as "Python").
launcher.pyw makes CleanView.exe, a copy of pythonw.exe with CleanView's description and
icon, and only uses it once a test run worked."""
import ctypes
import importlib.machinery
import importlib.util
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import support  # noqa: F401  (must come first)

import cleanview as engine

ROOT = Path(__file__).resolve().parent.parent


def load_launcher():
    path = ROOT / "launcher.pyw"
    loader = importlib.machinery.SourceFileLoader("cv_launcher_test", str(path))
    mod = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
    loader.exec_module(mod)
    return mod


def description(path):
    v = ctypes.windll.version
    n = v.GetFileVersionInfoSizeW(str(path), None)
    buf = ctypes.create_string_buffer(n)
    v.GetFileVersionInfoW(str(path), 0, n, buf)
    p, size = ctypes.c_wchar_p(), ctypes.c_uint()
    v.VerQueryValueW(buf, r"\StringFileInfo\040904B0\FileDescription", ctypes.byref(p),
                     ctypes.byref(size))
    return p.value


def icon_count(path):
    return ctypes.windll.shell32.ExtractIconExW(str(path), -1, None, None, 0)


@unittest.skipUnless(os.name == "nt" and sys.prefix != sys.base_prefix
                     and (Path(sys.prefix) / "pyvenv.cfg").exists(),
                     "needs Windows and the app's venv")
class OwnExe(unittest.TestCase):
    def setUp(self):
        self.lm = load_launcher()
        self.tmp = Path(tempfile.mkdtemp(prefix="cv-own-exe-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        venv = self.tmp / "venv"
        venv.mkdir()
        shutil.copy2(Path(sys.prefix) / "pyvenv.cfg", venv / "pyvenv.cfg")
        self.folder = venv / "CleanView"

    def make(self):
        return self.lm.make_own_exe(self.folder, sys.base_prefix, ROOT / "cleanview.ico")

    def test_named_cleanview_with_its_icon(self):
        exe = self.make()
        self.assertEqual(exe, self.folder / "CleanView.exe")
        for e in (exe, self.folder / "CleanView-work.exe"):
            self.assertEqual(description(e), "CleanView")
            self.assertEqual(icon_count(e), 1)

    def test_made_once(self):
        exe = self.make()
        when = exe.stat().st_mtime_ns
        self.assertEqual(self.make(), exe)
        self.assertEqual(exe.stat().st_mtime_ns, when)

    def test_a_failed_try_isnt_used_or_tried_again(self):
        with mock.patch.object(self.lm, "_rename_exe", side_effect=OSError("no")):
            self.assertIsNone(self.make())
        self.assertIn("no", (self.folder / "failed.txt").read_text(encoding="utf8"))
        with mock.patch.object(self.lm, "_rename_exe") as again:
            self.assertIsNone(self.make())
            again.assert_not_called()

    def test_not_while_smart_app_control_is_on(self):
        with mock.patch.object(self.lm, "_smart_app_control_off", return_value=False), \
                mock.patch.object(self.lm, "make_own_exe") as make, \
                mock.patch.object(self.lm.sys, "executable", r"C:\venv\Scripts\pythonw.exe"):
            self.assertFalse(self.lm.as_own_exe())
            make.assert_not_called()

    def test_already_cleanview_exe(self):
        with mock.patch.object(self.lm.sys, "executable", str(self.folder / "CleanView.exe")), \
                mock.patch.object(self.lm, "make_own_exe") as make:
            self.assertFalse(self.lm.as_own_exe())
            make.assert_not_called()


@unittest.skipUnless(os.name == "nt", "Windows only")
class WorkExe(unittest.TestCase):
    def test_picture_scan_runs_as_cleanview_work(self):
        tmp = Path(tempfile.mkdtemp(prefix="cv-work-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        (tmp / "CleanView-work.exe").write_bytes(b"")
        with mock.patch.object(engine.sys, "executable", str(tmp / "CleanView.exe")):
            self.assertEqual(engine._venv_python(), str(tmp / "CleanView-work.exe"))


if __name__ == "__main__":
    unittest.main()
