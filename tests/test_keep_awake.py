"""The PC stays awake while videos are watched, listened to or saved (2026-11-09: a CleanRead
book paused nine hours overnight when Windows went to sleep; the owner: "add it. to clean view
also"). Idle sleep only (ES_SYSTEM_REQUIRED, not the display), set and cleared on the same
thread, also when something goes wrong."""
import inspect
import importlib.machinery
import importlib.util
import sys
import unittest

import support
import cleanview as engine


class KeepAwake(unittest.TestCase):

    def test_set_then_cleared(self):
        calls = []
        with engine.keep_awake(calls.append):
            self.assertEqual(calls, [0x80000001])        # continuous + system required
        self.assertEqual(calls, [0x80000001, 0x80000000])

    def test_cleared_after_an_error(self):
        calls = []
        with self.assertRaises(ValueError):
            with engine.keep_awake(calls.append):
                raise ValueError("a video failed")
        self.assertEqual(calls[-1], 0x80000000)

    def test_never_the_display(self):
        calls = []
        with engine.keep_awake(calls.append):
            pass
        self.assertFalse(any(c & 0x00000002 for c in calls))   # ES_DISPLAY_REQUIRED

    def test_a_setter_that_fails_is_harmless(self):
        def broken(flags):
            raise OSError("not allowed")
        with engine.keep_awake(broken):
            pass

    @unittest.skipUnless(sys.platform == "win32", "Windows only")
    def test_the_real_call(self):
        with engine.keep_awake():
            pass

    def test_watching_and_saving_keep_it_awake(self):
        loader = importlib.machinery.SourceFileLoader("cv_ui_awake", str(support.ROOT / "CleanView.pyw"))
        ui = importlib.util.module_from_spec(importlib.util.spec_from_loader("cv_ui_awake", loader))
        loader.exec_module(ui)
        for name in ("_analyze_thread", "_render_thread"):
            with self.subTest(name):
                self.assertIn("engine.keep_awake()", inspect.getsource(getattr(ui.App, name)))


if __name__ == "__main__":
    unittest.main()
