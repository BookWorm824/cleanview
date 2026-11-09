"""The nudity found is looked at together with the other scenes, while the picture model is
loaded (the owner, 2026-11-09: "it seems to spend a lot of time stuck on 'checking nudity'.
but when it showed the results there wasnt any nudity. why is that?"). It used to come after
the dialogue model had taken the picture model's place, so the picture model was loaded again
just for that. Same model, same 4 stills, same question: the same results."""
import ast
import inspect
import unittest

import support  # noqa: F401  (sets up the sandbox first)
import cleanview as engine

NUDE = [{"s": 10.0 * n, "e": 10.0 * n + 5, "kind": ["Nudity"], "why": "skin seen", "sure": True}
        for n in range(4)]
VERDICTS = [{"level": "shown", "what": "bare back and bottom"},
            {"level": "implied", "what": "under a sheet"},
            {"level": "none"}, {"error": "model not running"}]


def answer(checks):
    for c, v in zip(checks, VERDICTS):
        c["verdict"] = dict(v)


class SameResults(unittest.TestCase):

    def test_looked_at_first_or_later_is_the_same(self):
        for implied in (True, False):
            with self.subTest(implied=implied):
                o = engine.full_opts({"nudity": True, "implied": implied})
                notes_later = []
                later = engine.check_nudity([dict(n) for n in NUDE], o, answer, notes_later)
                checks = engine.nudity_checks(NUDE)
                answer(checks)                   # with the other scenes, earlier
                notes_first = []
                first = engine.check_nudity([dict(n) for n in NUDE], o, None, notes_first,
                                            checks=checks)
                self.assertEqual(first, later)
                self.assertEqual(notes_first, notes_later)

    def test_the_same_stills(self):
        (c,) = engine.nudity_checks([{"s": 10.0, "e": 15.0}])
        self.assertEqual(c["cat"], "nudity")
        self.assertEqual(c["frames"], [11.0, 12.0, 13.0, 14.0])


class InTheSameGo(unittest.TestCase):

    def setUp(self):
        self.src = inspect.getsource(engine.analyze)

    def test_added_to_the_closer_look(self):
        self.assertIn('todo = sorted(cands, key=lambda c: -c["peak"])[:150] + nude_checks',
                      self.src)
        # looked at before the dialogue is read
        self.assertLess(self.src.index("+ nude_checks"), self.src.index("ai.dialogue_lines("))

    def test_not_looked_at_twice(self):
        i = self.src.index("if nude_checks:")
        self.assertIn("check_nudity(nude_first, o, None, notes, checks=nude_checks)",
                      self.src[i:i + 200])

    def test_still_checked_without_the_picture_ai(self):
        # no picture AI installed: the AI on this PC still looks at the nudity, on its own
        self.assertIn('say(at("end", 0.65), "Taking a closer look at the nudity found…")',
                      self.src)

    def test_cands_still_only_the_picture_ais(self):
        tree = ast.parse(inspect.getsource(engine.analyze))
        made = [n for n in ast.walk(tree) if isinstance(n, ast.Assign)
                for t in n.targets if isinstance(t, ast.Name) and t.id == "cands"]
        self.assertEqual(len(made), 2)


if __name__ == "__main__":
    unittest.main()
