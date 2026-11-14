"""The time left after Pause (1.18.95; the owner, 2026-11-14: "when coming back from pause it
said like 4.5 hours but only took 30").

Pause freezes the video's worker process from the window, so the worker's clock jumped by the
paused minutes when it was let go, and the step being done looked that much slower (in the time
left, in "Took N min" and in the speeds remembered for next time). `WorkClock` leaves out a gap
its helper thread didn't tick through (frozen, or the PC asleep), and pausing in its own
process."""
import inspect
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

import support
import cleanview as engine


class Wall:
    def __init__(self):
        self.t = 5000.0

    def __call__(self):
        return self.t


def clock(paused=lambda: 0.0):
    wall = Wall()
    return wall, engine.WorkClock(tick=1.0, wall=wall, paused=paused)


def ticking(wall, c, secs):
    for _ in range(int(secs)):
        wall.t += 1.0
        c.note()


class TheClock(unittest.TestCase):
    def test_runs_with_the_wall_clock(self):
        wall, c = clock()
        t0 = c()
        ticking(wall, c, 120)
        self.assertAlmostEqual(c() - t0, 120.0)

    def test_frozen_time_left_out(self):
        wall, c = clock()
        t0 = c()
        ticking(wall, c, 60)
        wall.t += 1800.0                  # frozen half an hour: no ticks
        self.assertAlmostEqual(c() - t0, 60.0, delta=1.0, msg="before the helper notices")
        c.note()
        ticking(wall, c, 30)
        self.assertAlmostEqual(c() - t0, 90.0, delta=1.0)

    def test_a_short_hitch_still_counts(self):
        wall, c = clock()
        t0 = c()
        wall.t += 6.0                     # a busy PC holding the helper back a few seconds
        c.note()
        self.assertAlmostEqual(c() - t0, 6.0)

    def test_pausing_in_this_process_left_out(self):
        paused = {"s": 0.0}
        wall, c = clock(lambda: paused["s"])
        t0 = c()
        ticking(wall, c, 50)
        paused["s"] = 20.0                # this process kept ticking, but was paused
        ticking(wall, c, 20)
        self.assertAlmostEqual(c() - t0, 50.0)

    def test_one_clock_one_helper(self):
        self.assertIs(engine.WORK_CLOCK.start(), engine.WORK_CLOCK.start())
        self.assertTrue(engine.WORK_CLOCK._thread.is_alive())


class TimeLeftAfterPause(unittest.TestCase):
    def test_no_jump_after_a_pause(self):
        """The reading step half done in 15 minutes, paused 4 hours, then let go."""
        wall, c = clock()
        tl = engine.TimeLeft(2640.0, None, c)
        tl.base = {"lines": (0.0, 1.0)}
        said = []
        for i in range(181):              # 0-50% over 15 minutes
            ticking(wall, c, 5)
            said.append(tl.left(i / 360))
        before = said[-1]
        wall.t += 4 * 3600.0              # frozen while paused
        after = tl.left(181 / 360)
        self.assertLess(after, before * 1.1)
        self.assertLess(after, 20 * 60)
        self.assertNotIn("hr", tl.say(181 / 360))

    def test_speeds_remembered_without_the_pause(self):
        wall, c = clock()
        tl = engine.TimeLeft(1000.0, None, c)
        tl.base = {"lines": (0.0, 1.0)}
        for i in range(101):
            ticking(wall, c, 3)
            if i == 50:
                wall.t += 3600.0
            tl.left(i / 100)
        self.assertAlmostEqual(tl.paces()["lines"], 0.3, delta=0.02)

    def test_analyze_uses_it(self):
        src = inspect.getsource(engine.analyze)
        self.assertIn("WORK_CLOCK.start()", src)
        self.assertIn("TimeLeft(dur, load_pace(), clock=clock)", src)
        self.assertNotIn("time.time()", src.split("def say(f, m)")[1].split("say_out")[0])


class AFrozenProcess(unittest.TestCase):
    def test_frozen_for_real(self):
        """A process frozen the way Pause freezes a video's worker."""
        f = Path(tempfile.mkdtemp(dir=support.SANDBOX)) / "clock.txt"
        code = ("import sys, threading, time\n"
                + inspect.getsource(engine.WorkClock)
                + "c = WorkClock(tick=0.05, paused=lambda: 0.0)\nc.GAP = 0.5\nc.start()\n"
                "w0, c0 = time.time(), c()\n"
                "for _ in range(600):\n"
                "    open(sys.argv[1], 'w').write(f'{time.time() - w0} {c() - c0}')\n"
                "    time.sleep(0.05)\n")
        proc = subprocess.Popen([sys.executable, "-c", code, str(f)])
        p = engine.Pausing()
        try:
            p.track(proc)
            end = time.time() + 20
            while not (f.exists() and f.read_text().strip()) and time.time() < end:
                time.sleep(0.05)
            time.sleep(0.5)
            p.pause()
            time.sleep(2.5)
            p.resume()
            time.sleep(0.8)
            wall, work = (float(x) for x in f.read_text().split())
            self.assertGreater(wall - work, 1.8, (wall, work))
            self.assertLess(wall - work, 3.0, (wall, work))
        finally:
            p.resume()
            proc.kill()
            proc.wait()


if __name__ == "__main__":
    unittest.main()
