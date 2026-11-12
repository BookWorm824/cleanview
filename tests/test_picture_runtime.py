"""The picture checkers' runtime, onnxruntime 1.24.4: about a fifth faster than 1.31.0 with the
same scores, words, sounds and voices (1.18.67, 2026-11-12; the owner: "Yes, build it"). Older
installs switch once on "Getting ready"; a switch that won't load puts the old one back."""
import unittest
from unittest import mock

import support
import cleanview as engine


class R:
    def __init__(self, code=0, out=""):
        self.returncode, self.stdout, self.stderr = code, out, ""


class Switch(unittest.TestCase):
    def setUp(self):
        self.mark = support.SANDBOX / "picture_runtime_test.txt"
        self.mark.unlink(missing_ok=True)
        self.have = {"v": "1.31.0"}
        self.ran = []
        for p in (mock.patch.object(engine, "_ort_mark", lambda: self.mark),
                  mock.patch.object(engine, "_ort_installed", lambda: self.have["v"]),
                  mock.patch.object(engine, "_venv_python", lambda: "py")):
            p.start()
            self.addCleanup(p.stop)

    def fake_run(self, pip_ok=True, loads=True):
        def run(cmd, **kw):
            self.ran.append(cmd)
            if "pip" in cmd:
                if not pip_ok:
                    return R(1)
                self.have["v"] = cmd[-1].split("==")[1]
                return R(0)
            return R(0 if loads else 1, self.have["v"] if loads else "")
        return mock.patch.object(engine.cl, "run", run)

    def test_wanted(self):
        self.assertTrue(engine.ort_switch_wanted())
        self.have["v"] = engine.ORT_VERSION
        self.assertFalse(engine.ort_switch_wanted())
        self.have["v"] = None                       # not installed: the first install pins it
        self.assertFalse(engine.ort_switch_wanted())

    def test_switched(self):
        with self.fake_run():
            self.assertTrue(engine.switch_ort(lambda m: None))
        self.assertEqual(self.have["v"], engine.ORT_VERSION)
        self.assertEqual(self.mark.read_text().strip(), "done")
        pip = [c for c in self.ran if "pip" in c][0]
        self.assertIn("--no-deps", pip)             # nothing else installed is touched
        self.assertFalse(engine.ort_switch_wanted())

    def test_wont_load_puts_the_old_one_back(self):
        with self.fake_run(loads=False):
            self.assertFalse(engine.switch_ort(lambda m: None))
        self.assertEqual(self.have["v"], "1.31.0")
        self.assertEqual(self.mark.read_text().strip(), "failed 1")
        self.assertTrue(engine.ort_switch_wanted())  # tried again next time

    def test_gives_up_after_three(self):
        with self.fake_run(pip_ok=False):
            for _ in range(engine.ORT_TRIES):
                self.assertFalse(engine.switch_ort(lambda m: None))
        self.assertEqual(self.mark.read_text().strip(), f"failed {engine.ORT_TRIES}")
        self.assertFalse(engine.ort_switch_wanted())

    def test_on_getting_ready_when_the_picture_is_checked(self):
        with mock.patch.object(engine, "nudity_model", lambda: "x"), \
                mock.patch.object(engine.importlib.util, "find_spec", lambda n: object()), \
                mock.patch.object(engine.ai, "clip_ready", lambda: True), \
                mock.patch.object(engine.ai, "speakers_ready", lambda: True):
            self.assertIn("faster picture checker",
                          engine.tools_missing(dict(nudity=True, ai=False, autosubs=False)))
            self.assertNotIn("faster picture checker", engine.tools_missing(dict(
                nudity=False, sex=False, implied=False, gore=False, graphic=False,
                medical=False, violence=False, disturbing=False, kiss_os="off",
                kiss_ss="off", drugs=False, gestures=False, ai=False, autosubs=False)))

    def test_new_installs_get_it(self):
        src = (support.ROOT / "cleanview.py").read_text(encoding="utf8")
        self.assertIn('[f"onnxruntime=={ORT_VERSION}"]', src)
        ps = (support.ROOT / "installer" / "install.ps1").read_text(encoding="utf8")
        self.assertIn(f"onnxruntime=={engine.ORT_VERSION}", ps)


if __name__ == "__main__":
    unittest.main()
