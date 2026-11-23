"""Words written in the picture (1.18.165; the owner, of a Tomb Raider walkthrough: "it also has
the words written on the bottom (not CC)...CleanView needs to be able to blur that", "there
doesn't need to be a tickbox to blur the bad words..that needs to be automatic if the bad words
filter is turned on"). Read by Windows' own text reader, blurred where a listed word is written,
and a caption's swear the listening missed is muted."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

import numpy as np

import support
import cleanview as engine
import cvcore as cl
import cvocr

FONT = "C\\:/Windows/Fonts/arial.ttf"


def make_video(out, secs=8):
    """A video with "Lara, what the shit was that?" written low down from 2 s to 5 s, and
    "Welcome home" written high up the whole time."""
    vf = (f"drawtext=fontfile='{FONT}':text='Lara, what the shit was that?':fontsize=36:"
          f"fontcolor=white:borderw=2:bordercolor=black:x=(w-text_w)/2:y=h-80:"
          f"enable='between(t,2,5)',"
          f"drawtext=fontfile='{FONT}':text='Welcome home':fontsize=36:fontcolor=white:"
          f"borderw=2:bordercolor=black:x=40:y=40")
    subprocess.run([support.FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i",
                    f"color=c=0x305070:size=1280x720:rate=25:duration={secs}", "-f", "lavfi",
                    "-i", f"sine=frequency=440:duration={secs}:sample_rate=48000", "-vf", vf,
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
                    str(out)], check=True, capture_output=True)


CATS = list(cl.CATS)


@unittest.skipUnless(support.FFMPEG and cvocr.ready(), "Windows' text reader isn't here")
class ReadAndBlur(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = Path(tempfile.mkdtemp(dir=support.SANDBOX))
        cls.video = cls.dir / "walkthrough.mp4"
        make_video(cls.video)
        cls.info = engine.probe(cls.video)
        cls.work = cls.dir / "work"
        cls.work.mkdir()
        cls.screen = engine.screen_scan(cls.video, cls.info, cls.work)
        cls.blurs = engine.screen_blurs(cls.screen, CATS, [], [1280, 720])

    def test_read_and_kept(self):
        self.assertTrue(self.screen["frames"])
        self.assertTrue((self.work / "screen.json").exists())
        again = engine.screen_scan(self.video, self.info, self.work)     # kept: not read again
        self.assertEqual(again, json.loads((self.work / "screen.json").read_text("utf8")))

    def test_just_the_bad_word_blurred_while_its_there(self):
        self.assertEqual([b["raw"] for b in self.blurs], ["what the shit"])  # as muted
        b = self.blurs[0]
        self.assertTrue(b["caption"])
        self.assertLessEqual(b["s"], 2.0)
        self.assertGreaterEqual(b["e"], 5.0)
        self.assertLess(b["e"], 6.5)
        self.assertGreater(b["y"], 600)                 # low down, where it's written
        self.assertLess(b["w"], 300)                    # the phrase, not the whole line
        self.assertIn(cl.mask("shit"), b["word"])

    def test_word_ticks_decide(self):
        self.assertEqual(engine.screen_blurs(self.screen, ["mild"], [], [1280, 720]), [])
        self.assertEqual(engine.screen_blurs(self.screen, [], [], [1280, 720]), [])
        mine = engine.my_words({"mywords": ["welcome home"]})
        self.assertEqual([b["raw"] for b in engine.screen_blurs(self.screen, [], mine,
                                                                 [1280, 720])], ["welcome home"])

    def test_blurred_in_the_clean_copy(self):
        st = {"path": str(self.video), "info": self.info, "duration": self.info["duration"],
              "groups": ["swearing"], "mutes": [], "scenes": [], "lines": [], "cues": [],
              "notes": [], "quiet": [], "blurs": self.blurs}
        (self.work / "analysis.json").write_text(json.dumps(st))
        res = engine.render(self.work, self.dir / "Clean", [], encoders=[engine.ENCODERS[-1]],
                            log=lambda m: None)
        self.assertIn("blurred", (self.dir / "Clean" / "Reports" /
                                  "walkthrough - CleanView report.txt").read_text("utf8"))
        b = self.blurs[0]

        def frame(path, t):
            raw = subprocess.run([support.FFMPEG, "-v", "error", "-ss", str(t), "-i", str(path),
                                  "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                                 capture_output=True, check=True).stdout
            return np.frombuffer(raw, np.uint8).reshape(720, 1280).astype(int)
        before, after = frame(self.video, 3.5), frame(res["out"], 3.5)
        box = (slice(b["y"], b["y"] + b["h"]), slice(b["x"], b["x"] + b["w"]))
        self.assertGreater(np.abs(before[box] - after[box]).mean(), 8, "the word is blurred")
        self.assertLess(np.abs(before[:500] - after[:500]).mean(), 3, "the rest is as it was")
        self.assertLess(np.abs(frame(self.video, 7.0)[box] - frame(res["out"], 7.0)[box]).mean(),
                        3, "not blurred once it's gone")


class SeenNotHeard(unittest.TestCase):
    BLUR = {"s": 10.0, "e": 13.0, "raw": "shit", "word": "s***", "cat": "moderate",
            "caption": True}

    def heard(self, *words):
        return [{"t": w, "n": cl.norm(w), "s": s, "e": s + 0.3} for w, s in words]

    def test_heard_wrong_is_muted(self):
        got = engine.screen_mutes([self.BLUR], [], self.heard(("what", 10.5), ("ship", 11.0)))
        self.assertEqual([(m["s"], m["src"], m.get("keep")) for m in got], [(11.0, "screen", None)])

    def test_muted_already(self):
        mute = {"s": 11.0, "e": 11.3}
        self.assertEqual(engine.screen_mutes([self.BLUR], [mute], self.heard(("ship", 11.0))), [])

    def test_not_heard_offered_unticked(self):
        got = engine.screen_mutes([self.BLUR], [], self.heard(("hello", 11.0)))
        self.assertTrue(got[0]["keep"])
        self.assertEqual(got[0]["why"], engine.SEEN_NOT_HEARD)

    def test_a_sign_isnt_said(self):
        sign = dict(self.BLUR, caption=False)
        self.assertEqual(engine.screen_mutes([sign], [], self.heard(("ship", 11.0))), [])


class OlderScans(unittest.TestCase):
    def test_scanned_again_for_words_on_screen(self):
        work = Path(tempfile.mkdtemp(dir=support.SANDBOX))
        video = work / "v.mp4"
        video.write_bytes(b"x")
        st = {"path": str(video), "opts": dict(engine.DEFAULTS), "groups": ["swearing"],
              "dialogue": [{"s": 0, "e": 1, "text": "hi"}], "lines": []}
        (work / "analysis.json").write_text(json.dumps(st))
        self.assertIsNone(engine.saved_scan(work, video, dict(engine.DEFAULTS), ["swearing"]))
        st["blurs"] = []
        (work / "analysis.json").write_text(json.dumps(st))
        self.assertIsNotNone(engine.saved_scan(work, video, dict(engine.DEFAULTS), ["swearing"]))


if __name__ == "__main__":
    unittest.main()
