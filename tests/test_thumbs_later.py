"""Pictures for a cut the chat adds are made in the background (1.18.104; the owner's
"CleanView stopped responding" note, 2026-11-14: asked to end a kiss cut 5 seconds sooner, the
chat added the shorter cut and its three blurred pictures were made on the window's thread;
on her .wmv that took 40 s and the window stopped answering). The same for scenes the AI's
"Review everything" adds."""
import struct
import time
import unittest
import zlib
import tkinter as tk
from pathlib import Path

import support
from test_ui import ui

engine = ui.engine
SLOW = 4.0


def tiny_png(w=18, h=12):
    def chunk(kind, data):
        return (struct.pack(">I", len(data)) + kind + data +
                struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff))
    rows = b"".join(bytes([0]) + bytes([128, 128, 128]) * w for _ in range(h))
    return (bytes([137]) + b"PNG\r\n" + bytes([26]) + b"\n" +
            chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) +
            chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


def slow_thumbs(made):
    def make(path, scenes, work):
        time.sleep(SLOW)
        d = Path(work) / "thumbs"
        d.mkdir(exist_ok=True)
        for sc in scenes:
            out = d / f"{sc['id']}_0.png"
            out.write_bytes(tiny_png())            # (no Tk off the window's thread)
            sc["thumbs"] = [str(out)]
            made.append(sc["id"])
    return make


def spin(app, secs):
    end = time.time() + secs
    while time.time() < end:
        app.update()
        time.sleep(0.02)


class ThumbsLater(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.saved = (ui.App._check_update, ui.App._check_every_ai, ui.cc.status, ui.cc.who,
                     engine.make_thumbs)
        ui.App._check_update = lambda self, manual=False: None
        ui.App._check_every_ai = lambda self: None
        ui.cc.status = lambda p=None: "ready" if p in (None, "claude") else "missing"
        ui.cc.who = lambda p=None: ""
        try:
            cls.app = ui.App()
        except tk.TclError as ex:
            cls.restore()
            raise unittest.SkipTest(f"no screen to draw on ({ex})")

    @classmethod
    def restore(cls):
        (ui.App._check_update, ui.App._check_every_ai, ui.cc.status, ui.cc.who,
         engine.make_thumbs) = cls.saved

    @classmethod
    def tearDownClass(cls):
        try:
            cls.app.destroy()
        except tk.TclError:
            pass
        cls.restore()

    def setUp(self):
        self.made = []
        engine.make_thumbs = slow_thumbs(self.made)
        support.write_review()
        app = self.app
        self.assertTrue(app._resume())
        app.ai_state = {"claude": "ready"}
        app.show_review(tab=2)
        for _ in range(100):
            app.update()
            time.sleep(0.02)
            if getattr(app, "chat_log", None):
                break
        self.job = [j for j in app.jobs if j["analysis"]][0]
        for sc in self.job["analysis"]["scenes"]:
            sc["thumbs"] = []                     # the scenes found have theirs already

    def pictures_on(self, sc):
        mid, _ = self.app._thumb_spots[id(sc)]
        return [w for w in mid.winfo_children() if isinstance(w, tk.Label) and w.cget("image")]

    def test_a_chat_cut_doesnt_wait_for_its_pictures(self):
        app, job = self.app, self.job
        items, _ = ui.cc.candidates(job["analysis"])
        sid = next(i for i, (k, x) in items.items() if k == "scene" and x["s"] == 30.0)
        acts = {"untick": [sid], "cut_times": [{"from": "0:30", "to": "0:35", "why": "shortened"}]}
        began = time.time()
        app._chat_reply(job, "I shortened it.", acts, items, None)
        self.assertLess(time.time() - began, SLOW, "the window waited for the pictures")
        new = next(sc for sc in job["analysis"]["scenes"] if sc.get("added"))
        self.assertEqual(new["thumbs"], [], "being made")
        self.assertEqual(self.pictures_on(new), [])
        spin(app, SLOW + 1.5)
        self.assertEqual(self.made, [new["id"]], "only the new cut's, once")
        self.assertEqual(len(new["thumbs"]), 1)
        self.assertEqual(len(self.pictures_on(new)), 1, "put on its card when ready")
        old = next(sc for sc in job["analysis"]["scenes"] if sc["s"] == 30.0 and not sc.get("added"))
        self.assertFalse(old["cut"], "the chat's untick held")

    def test_the_engine_still_makes_them_when_asked(self):
        st = self.job["analysis"]
        engine.apply_chat(st, {}, {"cut_times": [{"from": "0:50", "to": "0:52", "why": "x"}]})
        self.assertEqual(self.made, [], "left to the window")
        engine.apply_chat(st, {}, {"cut_times": [{"from": "0:55", "to": "0:57", "why": "y"}]},
                          self.job["work"])
        self.assertEqual(len(self.made), 2, "with work: both new cuts, as before")


if __name__ == "__main__":
    unittest.main()
