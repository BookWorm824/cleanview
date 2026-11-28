"""Two of the owner's Bones episodes (S01E03, S01E08; 1.18.174, 2026-11-27) never saved: every
way (h264_amf, libx264, the careful way) stopped moving 2 s in. The picture was fine; ffmpeg's
AAC encoder froze on their opening sound. Builds from late 2026 (this PC's: 2026-10-22) made a
new method, "nmr", the default, and it hangs for good on that sound; the old "twoloop" saves
each whole episode's sound in under two minutes. Every AAC CleanView writes says twoloop."""
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import support
import test_timing as T

import cleanview as engine
import cvcore as cl

REPO = Path(__file__).resolve().parent.parent
real_popen = cl.popen


class EveryAac(unittest.TestCase):
    def test_no_plain_aac_in_shipped_code(self):
        for name in json.loads((REPO / "version.json").read_text("utf8"))["files"]:
            if not name.endswith((".py", ".pyw")):
                continue
            text = (REPO / name).read_text("utf8")
            for m in re.finditer(r'"-c:a",\s*"aac"', text):
                line = text[:m.start()].count("\n") + 1
                self.assertIn("AAC = ", text.splitlines()[line - 1], f"{name}:{line}")
        self.assertEqual(cl.AAC, ["-c:a", "aac", "-aac_coder", "twoloop"])


@T.needs_ffmpeg
class SaveSaysTwoloop(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.video = support.SANDBOX / "Bones S01E03 aac.mp4"
        if not cls.video.exists():
            T.ffmpeg("-f", "lavfi", "-i", "testsrc=size=64x48:rate=10:duration=8", "-f", "lavfi",
                     "-i", "sine=frequency=440:duration=8", "-c:v", "libx264", "-c:a", "aac",
                     "-shortest", cls.video)

    def render(self, cuts, careful=False):
        cmds = []

        def popen(cmd, **kw):
            cmds.append(list(cmd))
            if careful and "-err_detect" not in cmd:      # every encoder fails: the careful way
                cmd = [c if c != str(cmd[-1]) else str(cmd[-1]) + ".x/none.mp4" for c in cmd]
            return real_popen(cmd, **kw)
        work = Path(tempfile.mkdtemp(dir=support.SANDBOX))
        info = engine.probe(self.video)
        st = {"path": str(self.video), "info": info, "duration": info["duration"],
              "groups": [], "scenes": [], "lines": [], "notes": [],
              "mutes": [{"s": 2.0, "e": 2.5, "word": "porn", "src": "audio"}], "cues": []}
        (work / "analysis.json").write_text(json.dumps(st))
        with mock.patch.object(cl, "popen", popen):
            res = engine.render(work, work / "Clean", cuts, lines=[], words=None,
                                encoders=[engine.ENCODERS[-1]], log=lambda m: None)
        self.assertTrue(Path(res["out"]).exists())
        saves = [c for c in cmds if any(str(c[-1]).endswith(x) for x in (".mp4", ".mkv"))]
        self.assertTrue(saves)
        for c in saves:
            i = c.index("-c:a")
            self.assertEqual(c[i:i + 4], cl.AAC, c)
        return saves

    def test_copy_with_mutes(self):
        self.render([])

    def test_with_a_cut(self):
        self.render([{"s": 3.0, "e": 4.0, "cut": True}])

    def test_the_careful_way(self):
        saves = self.render([{"s": 3.0, "e": 4.0, "cut": True}], careful=True)
        self.assertTrue(any("-err_detect" in c for c in saves))


if __name__ == "__main__":
    unittest.main()
