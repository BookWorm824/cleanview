"""Lauren's Person of Interest reports (2026-11-08, Claude, adults): S02E07 on 1.18.32 found the
two wives hugging and holding hands; S02E11-E22 on 1.18.28 were right except one line she
unticked through the chat. That chat kept a note for everything she cleans ("a line that just
mentions someone's wife, family or kids ... is not a problem line"), which mustn't unmute a
same-sex couple's "wife" lines, so a built-in note says what it means."""
import json
import unittest

import support
import cleanview_learn as learn


class LessonsBuiltIn(unittest.TestCase):

    def setUp(self):
        self.d = json.loads((support.ROOT / "shared_learned.json").read_text(encoding="utf8"))
        self.show = self.d["shows"]["person-of-interest"]

    def test_lines_taught(self):
        for line, kind in (("i got a date with a sock", "sexref"),
                           ("there was a stripper pole in that thing", "sexref"),
                           ("lips taste like the chocolate mints", "sexref"),
                           ("mom left because you cheated on her", "casual")):
            with self.subTest(line):
                key = next(k for k in self.show["muted"] if line in k)
                self.assertEqual(self.show["muted_for"][key], kind)
                self.assertGreaterEqual(len(key.split()), 5)

    def test_her_untick_is_a_false_alarm(self):
        self.assertIn(learn.norm("'Your lovely wife and two little girls'"), self.show["kept"])

    def test_same_sex_wife_lines_still_count(self):
        notes = learn.notes("person-of-interest@adults", "Person of Interest")
        self.assertTrue(any("a woman's wife or a man's husband" in n and "still a problem line" in n
                            for n in notes))


if __name__ == "__main__":
    unittest.main()
