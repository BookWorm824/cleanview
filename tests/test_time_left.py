"""The time left while a video is checked (1.18.82; the owner, 2026-11-13: "when it says
checking dialogue or reading conversations. the green progress bar works correctly but the timer
doesnt. it said 1 minute remaining and it been working for 20").

The time left used to be worked out from how full the bar was, as if every step filled it at
the same speed. On her laptop the AI helper's reading is an eighth of the bar and most of the
time. Now each step is timed by itself, and the steps to come use how long they took on this
PC last time."""
import json
import unittest

import support
import cleanview as engine

# the bar as analyze lays it out for the AI helper, and how long each step takes on a laptop
BASE = {"asr": (0.0, 0.40), "vis": (0.40, 0.45), "lines": (0.85, 0.12), "end": (0.97, 0.03)}
TAKES = {"asr": 120.0, "vis": 300.0, "lines": 1600.0, "end": 5.0}
WHOLE = sum(TAKES.values())
DUR = 2640.0           # a 44-minute episode


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def run(pace=None, every=5.0):
    """A whole scan on a made-up clock: (seconds in, seconds really left, seconds said)."""
    clock = Clock()
    tl = engine.TimeLeft(DUR, pace, clock)
    tl.base = dict(BASE)
    out, el = [], 0.0
    for step in ("asr", "vis", "lines"):
        b, w = BASE[step]
        n = int(TAKES[step] / every)
        for i in range(n):
            clock.t = 1000.0 + el + i * every
            out.append((step, el + i * every, WHOLE - el - i * every, tl.left(b + w * i / n)))
        el += TAKES[step]
    return tl, out


def old_way(el, frac):
    return el / frac * (1 - frac)


class WhileReading(unittest.TestCase):
    def test_what_she_saw(self):
        # halfway through the reading the old way said about 2 minutes; 13 were left
        el = 120 + 300 + 800
        self.assertLess(old_way(el, 0.85 + 0.06), 150)
        tl, out = run()
        step, at, real, said = next(x for x in out if x[0] == "lines" and x[1] >= el)
        self.assertAlmostEqual(said, real, delta=0.1 * real)

    def test_right_all_through_the_reading(self):
        tl, out = run()
        for step, at, real, said in out:
            if step == "lines" and at >= 120 + 300 + 0.06 * 1600:      # once 5% of it is done
                self.assertAlmostEqual(said, real, delta=max(15, 0.1 * real), msg=at)

    def test_never_a_minute_left_with_many_to_go(self):
        tl, out = run()
        for step, at, real, said in out:
            if step == "lines" and at >= 120 + 300 + 0.06 * 1600 and real > 180:
                self.assertGreater(said, 120, at)

    def test_as_before_in_the_first_step_with_nothing_remembered(self):
        tl, out = run()
        for step, at, real, said in out:
            if step == "asr":
                if at < 20 or at / 120 < 0.05:
                    self.assertIsNone(said)
                else:
                    self.assertAlmostEqual(said, old_way(at, 0.40 * at / 120), delta=1)

    def test_words(self):
        clock = Clock()
        tl = engine.TimeLeft(DUR, None, clock)
        tl.base = dict(BASE)
        self.assertEqual(tl.say(0.0), "estimating time…")
        clock.t += 60
        self.assertEqual(tl.say(0.2), "about 4 min left")       # 60 s for half of 40%: 300 s whole
        clock.t += 59
        self.assertEqual(tl.say(0.399), "about 3 min left")     # the other 60% of the bar
        self.assertEqual(tl.say(1.0), "estimating time…")       # nothing left to time


class Remembered(unittest.TestCase):
    """How long each step took here last time is remembered, so it's right from the start."""

    def pace(self):
        tl, out = run()
        return tl.paces()

    def test_each_steps_speed_is_kept(self):
        pace = self.pace()
        self.assertEqual(set(pace), {"asr", "vis", "lines"})
        for step in pace:
            self.assertAlmostEqual(pace[step] * DUR, TAKES[step], delta=0.06 * TAKES[step])

    def test_right_from_the_first_minute_next_time(self):
        tl, out = run(self.pace())
        for step, at, real, said in out:
            self.assertIsNotNone(said, at)
            self.assertAlmostEqual(said, real, delta=max(30, 0.1 * real), msg=(step, at))

    def test_a_longer_video_takes_longer(self):
        clock = Clock()
        tl = engine.TimeLeft(2 * DUR, self.pace(), clock)
        tl.base = dict(BASE)
        self.assertAlmostEqual(tl.left(0.0), 2 * (WHOLE - TAKES["end"]), delta=0.1 * 2 * WHOLE)

    def test_a_step_named_by_who_reads(self):
        clock = Clock()
        tl = engine.TimeLeft(DUR, {"lines+local": 0.5, "lines+claude": 0.01}, clock)
        tl.base, tl.keys = dict(BASE), {"lines": "lines+claude"}
        clock.t += 420
        self.assertAlmostEqual(tl.left(0.85), 0.01 * DUR + 420 / 0.85 * 0.03, delta=1)

    def test_saved_work_isnt_remembered(self):
        clock = Clock()
        tl = engine.TimeLeft(DUR, None, clock)
        tl.base = dict(BASE)
        tl.left(0.0)
        clock.t += 3                     # the words were heard before: listening took 3 s
        tl.left(0.39)
        tl.left(0.60)                    # the picture step first seen partway through
        clock.t += 200
        tl.left(0.84)
        self.assertEqual(tl.paces(), {})

    def test_kept_between_scans(self):
        self.assertEqual(engine.load_pace(), {})
        engine.save_pace({"asr": 0.05, "lines+local": 0.6})
        self.assertEqual(engine.load_pace(), {"asr": 0.05, "lines+local": 0.6})
        engine.save_pace({"lines+local": 0.2})                 # half old, half new
        self.assertEqual(engine.load_pace(), {"asr": 0.05, "lines+local": 0.4})
        self.assertEqual([p.name for p in engine.PACE_FILE.parent.glob("step_pace*")],
                         ["step_pace.json"])
        engine.PACE_FILE.write_text("not json")
        self.assertEqual(engine.load_pace(), {})
        engine.PACE_FILE.write_text(json.dumps({"asr": "fast", "vis": -1, "lines": 0.3}))
        self.assertEqual(engine.load_pace(), {"lines": 0.3})
        engine.PACE_FILE.unlink()


if __name__ == "__main__":
    unittest.main()
