"""The little cleaner on the cleaning screen's logo (1.18.109; the owner, 2026-11-15: "a little
cleaner man that roams around the logo with a broom while cleaning", picked "B · bigger" "with
d movement": a tenth of the logo's height, wandering over the logo and sweeping)."""
import datetime
import json
import math
import random
import time
import tkinter as tk
import unittest

import numpy as np

import support  # noqa: F401  (must come first)
import test_ui

import cvsweeper as sw

ui = test_ui.ui
RED = np.array(sw.CAP)


def logo_back(n=384, bg="#F6F3EE"):
    return sw.backdrop(ui._shrink(ui._logo_rgba(), n), bg)


class Walking(unittest.TestCase):
    def test_a_tenth_of_the_logo(self):
        self.assertEqual(sw.SIZE, 0.1)
        self.assertAlmostEqual(sw.Walker(384).h, 38.4)

    def test_stays_on_the_logo_and_sweeps(self):
        w = sw.Walker(384, random.Random(1))
        x0, x1, y0, y1 = w.bounds()
        states, faces, puffs = set(), set(), 0
        for _ in range(sw.FPS * 180):                      # three minutes
            w.step(1 / sw.FPS)
            self.assertTrue(x0 - 1e-6 <= w.x <= x1 + 1e-6 and y0 - 1e-6 <= w.y <= y1 + 1e-6)
            bx0, by0, bx1, by1 = w.box()
            self.assertTrue(0 <= bx0 < bx1 <= 384 and 0 <= by0 < by1 <= 384)
            states.add(w.state)
            faces.add(w.face)
            puffs = max(puffs, len(w.puffs))
            self.assertTrue(all(a < sw.PUFF_LIFE for _, _, a in w.puffs))
        self.assertEqual(states, {"walk", "sweep"})
        self.assertEqual(faces, {1, -1})
        self.assertGreater(puffs, 0)

    def test_walks_at_his_own_pace(self):
        w = sw.Walker(384, random.Random(2))
        w.tx, w.ty = w.x + 300, w.y                         # far away, straight right
        w.step(1.0)
        self.assertAlmostEqual(w.x - 384 * 0.42, sw.SPEED * w.h, places=6)

    def test_smaller_logo_smaller_walk(self):
        w = sw.Walker(384, random.Random(3))
        for _ in range(100):
            w.step(0.05)
        x, y = w.x, w.y
        w.resize(192)
        self.assertAlmostEqual(w.x, x / 2)
        self.assertAlmostEqual(w.y, y / 2)
        self.assertAlmostEqual(w.h, 19.2)


class LifelikeWalk(unittest.TestCase):
    """1.18.110: "can we make the cleaner walk a little more realistic. and make him pause with
    the cleaninig", "When I press Pause"."""

    def test_a_foot_on_the_ground_stays_put(self):
        w = sw.Walker(384, random.Random(6))
        w.tx, w.ty = w.x + 300, w.y                         # a long walk to the right
        for _ in range(20):                                 # past any easing in
            w.step(1 / sw.FPS)
        planted = []
        for _ in range(60):
            w.step(1 / sw.FPS)
            fx, fy = w.shown["near"]
            planted.append((fy == 0.0, w.x + fx * w.h))
        runs, run = [], []
        for down, where in planted:
            if down:
                run.append(where)
            elif run:
                runs.append(run)
                run = []
        self.assertGreater(len(runs), 1)
        for run in runs:
            self.assertLess(max(run) - min(run), 0.5)       # under half a pixel: no sliding

    def test_knees_bend_and_feet_take_turns(self):
        ps = [sw.walking(i / 20) for i in range(20)]
        self.assertTrue(any(p["near"][1] < 0 for p in ps) and any(p["far"][1] < 0 for p in ps))
        self.assertFalse(any(p["near"][1] < 0 and p["far"][1] < 0 for p in ps))   # one at a time
        kx, ky = sw._knee(0, -sw.HIP * 38, 0, 0, sw.LEG * 38)
        self.assertGreater(kx, 0)                           # bent forward
        self.assertTrue(-sw.HIP * 38 < ky < 0)

    def test_poses_ease_into_each_other(self):
        w = sw.Walker(384, random.Random(7))
        w.step(0.05)
        before = w.shown["near"]
        w.paused = True
        w.step(0.05)
        self.assertNotEqual(w.shown["near"], sw.leaning(w.t)["near"])     # on its way
        for _ in range(10):
            w.step(0.05)
        self.assertEqual(w.shown, sw.leaning(w.t))
        self.assertNotEqual(before, w.shown["near"])

    def test_paused_he_stays_and_leans_on_his_broom(self):
        w = sw.Walker(384, random.Random(8))
        for _ in range(sw.FPS * 6):
            w.step(1 / sw.FPS)
        w.paused = True
        w.step(1 / sw.FPS)
        where, state = (w.x, w.y), w.state
        made = len(w.puffs)
        for _ in range(sw.FPS * 5):
            w.step(1 / sw.FPS)
            self.assertLessEqual(len(w.puffs), made)        # no new dust
        self.assertEqual((w.x, w.y, w.state), where + (state,))
        self.assertEqual((w.shown["head"], w.shown["grip"]),
                         (sw.leaning(0)["head"], sw.leaning(0)["grip"]))
        w.paused = False
        for _ in range(sw.FPS * 8):
            w.step(1 / sw.FPS)
        self.assertNotEqual((w.x, w.y), where)              # carries on after Resume


class PushBroomAndDetail(unittest.TestCase):
    """1.18.111: "can he have a push broom style. and can you make him a little more hd?"."""

    def test_pushes_it_along_in_front(self):
        for p in [sw.walking(i / 10) for i in range(10)] + [sw.sweeping(i / 10) for i in range(10)]:
            hx, bottom, top, grip, far = sw._broom(p, 38)
            self.assertGreater(hx, 0.4 * 38)                     # in front of him
            self.assertGreater(bottom[0], top[0])                # handle up and back to him
            self.assertLess(top[1], grip[1])
            for shoulder, hand in (((0.03, -0.71), grip), ((-0.04, -0.72), far)):
                sx, sy = sw._from_upper(shoulder[0] * 38, shoulder[1] * 38, p, 38)
                self.assertLess(math.hypot(hand[0] - sx, hand[1] - sy), 2 * sw.ARM * 38 * 1.1)

    def test_push_strokes_and_dust_out_in_front(self):
        heads = [sw.sweeping(t / 20)["head"] for t in range(40)]
        self.assertGreater(max(heads) - min(heads), 0.2)         # out and back
        w = sw.Walker(384, random.Random(9))
        for _ in range(sw.FPS * 60):
            w.step(1 / sw.FPS)
            for x, y, age in w.puffs:
                if age == 0:
                    self.assertGreater((x - w.x) * w.face, 0.6 * w.h)    # ahead of the broom

    def test_paused_the_broom_stands_up(self):
        hx, bottom, top, grip, far = sw._broom(sw.leaning(0), 38)
        self.assertLess(abs(top[0] - bottom[0]), abs(top[1] - bottom[1]) * 0.3)

    def test_more_detail(self):
        pic = sw.draw(np.full((60, 90, 3), 210, np.uint8), 30, 52, 38, sw.walking(0.25))
        near = lambda colour, tol=40: (np.abs(pic.astype(int) - colour).sum(axis=2) < tol).any()
        for colour in (sw.SHIRT, sw.OVERALLS, sw.SKIN, sw.BRASS, sw.EYE_WHITE, sw.HANDLE,
                       sw.BRISTLES, sw.HAIR):
            self.assertTrue(near(np.array(colour)), colour)
        self.assertTrue((pic.sum(axis=2) < 200).any())           # a dark outline
        sleeve = sw.draw(np.full((60, 90, 3), 210, np.uint8), 30, 52, 38, sw.walking(0.25))
        self.assertTrue(np.array_equal(pic, sleeve))             # the same every time


class Drawing(unittest.TestCase):
    def test_drawn_on_the_logo_and_nothing_else_changed(self):
        back = logo_back()
        w = sw.Walker(384, random.Random(4))
        x0, y0, pic = w.picture(back)
        under = back[y0:y0 + pic.shape[0], x0:x0 + pic.shape[1]]
        changed = np.abs(pic.astype(int) - under).max(axis=2) > 3
        self.assertTrue(changed.any())
        self.assertFalse(changed[0].any() or changed[:, 0].any() or changed[:, -1].any())
        rows = np.nonzero(changed.any(axis=1))[0]
        self.assertLess(abs((rows[-1] - rows[0]) - w.h), w.h * 0.3)     # about his height
        cap = np.array(w.wear["cap"][1])                                 # this week's cap
        self.assertTrue((np.abs(pic.astype(int) - cap).sum(axis=2) < 30).any())

    def test_faces_both_ways(self):
        a = sw.draw(np.full((60, 60, 3), 200, np.uint8), 30, 50, 38, face=1)
        b = sw.draw(np.full((60, 60, 3), 200, np.uint8), 30, 50, 38, face=-1)
        self.assertTrue(np.array_equal(a[:, 1:], b[:, :0:-1]) or
                        np.abs(a[:, ::-1].astype(int) - b).mean() < 3)

    def test_quick(self):
        back = logo_back()
        w = sw.Walker(384, random.Random(5))
        t = time.perf_counter()
        for _ in range(40):
            w.step(1 / sw.FPS)
            w.picture(back)
        self.assertLess((time.perf_counter() - t) / 40, 0.02)    # ~2 ms here


class AnOutfitEachWeek(unittest.TestCase):
    """1.18.123 (the owner, 2026-11-17: "one a week i want his clothes colors to be changed",
    "all" of the choices, "they can be random choices from there", "so the outfits look
    different")."""
    MONDAY = datetime.date(2026, 11, 16)

    def weeks(self, n=300):
        return [sw.outfit(self.MONDAY + datetime.timedelta(weeks=i)) for i in range(n)]

    def test_the_same_all_week_and_new_on_monday(self):
        days = [sw.outfit(self.MONDAY + datetime.timedelta(days=i)) for i in range(7)]
        self.assertTrue(all(d == days[0] for d in days))
        self.assertNotEqual(sw.outfit(self.MONDAY + datetime.timedelta(days=7)), days[0])
        self.assertEqual(sw.outfit(datetime.date(2027, 3, 3)), sw.outfit(datetime.date(2027, 3, 3)))

    def test_every_part_changes_each_week(self):
        ws = self.weeks()
        for a, b in zip(ws, ws[1:]):
            for part in ("shirt", "pants", "shoes", "cap"):
                self.assertNotEqual(a[part], b[part], part)

    def test_all_her_choices_come_round(self):
        ws = self.weeks()
        for part, choices in (("shirt", sw.SHIRTS), ("pants", sw.PANTS),
                              ("shoes", sw.SHOES_ALL), ("cap", sw.CAPS)):
            self.assertEqual({w[part] for w in ws}, set(choices), part)
        self.assertEqual((len(sw.SHIRTS), len(sw.PANTS), len(sw.SHOES_ALL), len(sw.CAPS)),
                         (10, 10, 5, 7))

    def test_the_shirt_stands_out_from_the_pants(self):
        for w in self.weeks():
            self.assertGreaterEqual(math.dist(w["shirt"][1], w["pants"][1]), sw.SHIRT_APART)

    def test_quick_years_from_now(self):
        t = time.perf_counter()
        sw.outfit(datetime.date(2036, 11, 17))
        self.assertLess(time.perf_counter() - t, 0.2)

    def test_drawn_in_it(self):
        wear = {"shirt": sw.SHIRTS[1], "pants": sw.PANTS[2], "shoes": sw.SHOES_ALL[2],
                "cap": sw.CAPS[5]}
        pic = sw.draw(np.full((60, 90, 3), 30, np.uint8), 30, 52, 38, sw.walking(0.25), wear=wear)
        near = lambda colour, tol=40: (np.abs(pic.astype(int) - colour).sum(axis=2) < tol).any()
        for part in ("shirt", "pants", "shoes", "cap"):
            self.assertTrue(near(np.array(wear[part][1])), part)
        self.assertFalse(near(np.array(sw.CAP)))                 # not his red cap
        self.assertFalse(near(np.array(sw.OVERALLS)))            # nor his blue overalls

    def test_the_walker_wears_this_weeks(self):
        self.assertEqual(sw.Walker(384).wear, sw.outfit())


class OnTheWorkingPage(unittest.TestCase):
    def test_wanders_while_cleaning_and_stops_with_the_page(self):
        saved = ui.App._check_update, ui.App._check_every_ai, ui.App._lengths
        ui.App._check_update = lambda self, manual=False: None
        ui.App._check_every_ai = lambda self: None
        ui.App._lengths = lambda self, videos, done: None
        try:
            try:
                app = ui.App()
            except tk.TclError as ex:
                self.skipTest(f"no screen to draw on ({ex})")
            try:
                app.jobs = [{"video": r"D:\Movies\That Thing You Do.m4v"}]
                app.show_working("Saving the clean copy…")
                app.update()
                self.assertIsInstance(app.logo, tk.Canvas)
                sweep = app._sweeper
                self.assertTrue(sweep.running)

                def pump(secs):
                    end = time.monotonic() + secs
                    while time.monotonic() < end:
                        app.update()
                        time.sleep(0.01)
                pump(0.5)
                self.assertIsNotNone(sweep.item)
                first = app.logo.coords(sweep.item)
                pump(2.0)
                self.assertNotEqual(app.logo.coords(sweep.item), first)        # he moved
                self.assertEqual(sweep.walker.n, app._logo_size)
                app.geometry("900x600")                                        # less room
                pump(0.5)
                self.assertLess(app._logo_size, 384)
                self.assertEqual(sweep.walker.n, app._logo_size)
                ui.engine.PAUSE.on = True                     # Pause pressed (only the flag)
                try:
                    pump(0.3)
                    self.assertTrue(sweep.walker.paused)
                    still = app.logo.coords(sweep.item)
                    pump(1.0)
                    self.assertEqual(app.logo.coords(sweep.item), still)       # he waits
                finally:
                    ui.engine.PAUSE.on = False
                pump(0.3)
                self.assertFalse(sweep.walker.paused)
                app.logo.destroy()                                             # page gone
                self.assertFalse(sweep.running)
                self.assertIsNone(sweep.next)        # no frame left waiting (it upset others)
                pump(0.3)
                self.assertFalse(sweep.running)
            finally:
                app.destroy()
        finally:
            ui.App._check_update, ui.App._check_every_ai, ui.App._lengths = saved

    def test_shipped(self):
        self.assertIn("cvsweeper.py",
                      json.loads((support.ROOT / "version.json").read_text())["files"])


if __name__ == "__main__":
    unittest.main()
