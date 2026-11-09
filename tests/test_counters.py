"""Long steps count under the progress bar ("Taking a closer look at the scenes found · 14 of
150"), so a step that takes a while doesn't look frozen (the owner, 2026-11-09, after CleanRead's
"AI is double-checking what it found…" sat unchanged: "is it frozen?", then "can we add the same
change to clean read, clean view als?"; CleanListen/CleanRead 1.17.10)."""
import inspect
import threading
import unittest
from unittest import mock

import support  # noqa: F401  (sets up the sandbox first)
import cleanview as engine
import cleanview_ai as ai
import cleanview_claude as cc


class Counted(unittest.TestCase):

    def test_the_wording(self):
        seen = []
        ai.counted(lambda f, n="": seen.append(n), 0.0, 14, 14, 150)
        ai.counted(lambda f, n="": seen.append(n), 0.0, 21, 40, 95)
        cc.counted(lambda f, n="": seen.append(n), 0.0, 1, 240, 1400, "stills")
        self.assertEqual(seen, ["14 of 150", "21–40 of 95", "stills 1–240 of 1,400"])

    def test_a_progress_that_only_takes_how_far(self):
        seen = []
        ai.counted(seen.append, 0.5, 1, 1, 2)
        ai.counted(None, 0.5, 1, 1, 2)
        self.assertEqual(seen, [0.5])

    def test_said_after_the_step(self):
        self.assertEqual(engine.also("3 of 40"), " · 3 of 40")
        self.assertEqual(engine.also(""), "")


def calls():
    seen = []
    return seen, lambda f, n="": seen.append(n)


class LocalAI(unittest.TestCase):

    def test_closer_look_at_each_scene(self):
        seen, progress = calls()
        with mock.patch.object(ai, "chat", lambda *a, **k: {"yes": False}):
            ai.second_look([{"cat": "smoking", "s": 10.0 * n, "e": 10.0 * n + 5}
                            for n in range(3)], lambda c: ["a frame"], progress)
        self.assertEqual([n for n in seen if n], ["1 of 3", "2 of 3", "3 of 3"])

    def test_reading_the_dialogue(self):
        lines = [{"s": float(k), "e": k + 0.9, "text": f"line number {k} here"} for k in range(50)]
        seen, progress = calls()
        with mock.patch.object(ai, "chat", lambda *a, **k: {"flags": []}):
            ai.classify_dialogue(lines, ["sexref"], progress)
        self.assertEqual([n for n in seen if n],
                         ["lines 1–25 of 50", "lines 22–46 of 50", "lines 43–50 of 50"])

    def test_the_double_check(self):
        lines = [{"s": float(k), "e": k + 0.9, "text": f"we had sex number {k}"} for k in range(3)]
        answers = iter([{"flags": [{"line": k + 1, "type": "sexref", "words": "we had sex"}
                                   for k in range(3)]}] + [{"fits": True}] * 3)
        seen, progress = calls()
        with mock.patch.object(ai, "chat", lambda *a, **k: next(answers)):
            ai.classify_dialogue(lines, ["sexref"], progress)
        self.assertEqual([n for n in seen if n][-3:],
                         ["double-checking 1 of 3", "double-checking 2 of 3",
                          "double-checking 3 of 3"])

    def test_waiting_for_it_in_the_background(self):
        go = threading.Event()

        def work(progress):
            progress(0.5, "75 of 150")
            go.wait(2)
        job = engine.in_background(work)
        waited = []
        threading.Timer(0.3, go.set).start()
        engine.wait_for(job, lambda f, n="": waited.append((f, n)))
        self.assertIn((0.5, "75 of 150"), waited)


class Cloud(unittest.TestCase):

    def test_stills_looked_through(self):
        seen, progress = calls()
        with mock.patch.object(cc, "ask", lambda *a, **k: ({"found": []}, None)):
            cc.picture_review([(f"s{k}.jpg", 40.0 * k) for k in range(15)], "fights",
                              progress=progress)
        self.assertEqual(seen, ["stills 1–240 of 300", "stills 241–300 of 300"])

    def test_scenes_checked(self):
        seen, progress = calls()
        with mock.patch.object(cc, "ask", lambda *a, **k: ({"decisions": [], "scenes": []}, None)):
            cc.verify_scenes([(k, "Violence", "fight", f"{k}.jpg") for k in range(12)], "fights",
                             progress=progress)
            cc.scene_bounds([(k, "Violence", f"{k}.jpg") for k in range(9)], progress=progress)
        self.assertEqual(seen, ["1–10 of 12", "11–12 of 12", "1–8 of 9", "9 of 9"])

    def test_the_messages_say_it(self):
        for f in (engine.look_at_picture, engine.refine_bounds, engine.analyze):
            with self.subTest(f.__name__):
                self.assertIn("also(n)", inspect.getsource(f))
                self.assertNotIn("lambda f: say(", inspect.getsource(f))


if __name__ == "__main__":
    unittest.main()
