"""A phrase split across two subtitle lines is found (1.18.137; CleanStream 0.4.5 found YouTube's
captions splitting "go down on you" over two lines; the owner: "both", to the same fix here).
Each line is read with the next joined on when it follows closely; each line gets its part."""
import unittest

import support  # noqa: F401  (must come first)
import cleanview as engine


def opts(**on):
    o = engine.full_opts(on)
    for k in engine.LINE_KINDS:
        o[k] = on.get(k, False)
    return o


def lines(*texts, gap=0.5):
    out, t = [], 0.0
    for x in texts:
        out.append({"s": t, "e": t + 1.5, "text": x})
        t += 1.5 + gap
    return out


class SplitPhrases(unittest.TestCase):
    def found(self, ls, **on):
        out, _ = engine.find_lines(ls, opts(**on), False)
        return [(l["idx"], l["types"], l.get("words")) for l in out]

    def test_split_over_two_lines(self):
        self.assertEqual(self.found(lines("Baby, I could go down", "on you right now."),
                                    sexref=True),
                         [(0, ["sexref"], ["go down"]), (1, ["sexref"], ["on you"])])

    def test_guards_still_hold(self):
        self.assertEqual(self.found(lines("Then the sun went down", "on us all."), sexref=True), [])
        self.assertEqual(self.found(lines("She told me to go down", "on your knees."),
                                    sexref=True), [])

    def test_not_lines_far_apart(self):
        self.assertEqual(self.found(lines("I could go down", "on you later", gap=30.0),
                                    sexref=True), [])

    def test_one_line_finds_as_before(self):
        self.assertEqual(self.found(lines("They had sex.", "Then they left."), sexref=True),
                         [(0, ["sexref"], ["sex"])])
        self.assertEqual(self.found(lines("He was", "stoned."), drugtalk=True),
                         [(1, ["drugtalk"], ["stoned"])])

    def test_no_find_twice(self):
        hits = engine.list_hits(lines("We had sex", "and then had sex again."), ["sexref"])
        self.assertEqual(hits, {0: {"sexref": ["had sex"]}, 1: {"sexref": ["had sex"]}})


if __name__ == "__main__":
    unittest.main()
