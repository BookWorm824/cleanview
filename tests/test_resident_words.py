"""Words she ticked and short lines she'd muted (1.18.172, 2026-11-25; her reports of The
Resident S04E01-E07 and S05E01-E23, read by Claude, and Pollyanna, Young kids, the AI helper;
the owner: "Words and short lines").

Words: "bat eater" and "Kung Flu" (S04E01) and "pansy-ass" (S05E14) are slurs, "numbnut"
(S05E20) is "numbnuts" said once, and the maid's names for Pollyanna ("Miss Smarty-Pants",
"Miss Goody Two-Shoes", "little Miss Know-It-All", "Old Blabbermouth Tarbell") are rude words
kids copy. Short lines: 112 of the 400 lines she'd muted in The Resident were 5-6 everyday words
muted as part of a conversation ("I like the sound of that", "You have something you want to
say,", "Why didn't you tell me?"), then muted in every later episode."""
import json
import unittest

import support  # noqa: F401  (must come first)
import cvcore as cl
import cleanview_learn as learn

ALL = ["strong", "moderate", "slurs", "mild", "rude", "sexwords", "crudewords", "deity", "minced",
       "samesex"]


def found(text, groups=ALL):
    w = [cl.norm(x) for x in text.split()]
    return [(" ".join(w[a:b]), c) for a, b, c in cl.find_language(w, list(groups))]


class Words(unittest.TestCase):

    def test_pandemic_slurs(self):
        self.assertEqual(found("This morning a total stranger called me a bat eater."),
                         [("bat eater", "slurs")])
        self.assertEqual(found('The "China Virus," the "Kung Flu."'), [("kung flu", "slurs")])
        self.assertEqual(found("He does kung fu."), [])
        self.assertEqual(found("a cricket bat eaten by termites"), [])
        self.assertEqual(found("called me a bat eater.", ["slurs"]), [("bat eater", "slurs")])
        self.assertEqual(found("called me a bat eater.", ["moderate"]), [])

    def test_pansy(self):
        self.assertEqual(found("Those pansy-ass keyboard crusaders"), [("pansyass", "slurs")])
        for line in ("You pansy!", "Don't be such a pansy.", "a bunch of pansies"):
            self.assertEqual([c for _, c in found(line)], ["slurs"], line)
        for line in ("She planted pansies in the window box.",
                     "a pot of purple pansies on the porch",
                     "Pansies and violets bloom in the spring."):
            self.assertEqual(found(line), [], line)

    def test_numbnut(self):
        self.assertEqual(found("this numbnut moving in on my block"), [("numbnut", "moderate")])
        self.assertEqual(found("numbnuts"), [("numbnuts", "moderate")])

    def test_names_for_a_child(self):
        for line, got in (("All right, Miss Smarty-Pants.", "smartypants"),
                          ("smarty pants", "smarty pants"),
                          ("Here it comes-- Miss Goody Two-Shoes...", "goody twoshoes"),
                          ("goody two shoes", "goody two shoes"),
                          ("little Miss Know-It-All.", "knowitall"),
                          ("Old Blabbermouth Tarbell will see to that.", "blabbermouth")):
            self.assertEqual(found(line), [(got, "rude")], line)
        for line in ("You know it all went wrong.", "I know it all by heart."):
            self.assertEqual(found(line), [], line)
        self.assertEqual(found("Miss Smarty-Pants", ["strong", "moderate", "mild"]), [])


class ShortLinesStayInTheirVideo(unittest.TestCase):
    KEY = "short-lines-test"

    def setUp(self):
        self.addCleanup(lambda: (support.APP_DATA / "learned" / f"{self.KEY}.json").unlink(
            missing_ok=True))

    def mute(self, text, video):
        learn.record(self.KEY, [{"text": text, "s": 1.0, "e": 2.0, "_shown": False}], [True],
                     [], [], [], [], [], [], video=video)

    def comes_back(self, text, video):
        added, _ = learn.apply(self.KEY, [{"s": 5.0, "e": 6.0, "text": text}], [], [], [],
                               video=video)
        return bool(added)

    def test_short_line_only_in_its_own_video(self):
        self.mute("I like the sound of that.", "The Resident_S05E11_Her Heart.mp4")
        self.assertTrue(self.comes_back("I like the sound of that.",
                                        "D:/TV/The Resident_S05E11_Her Heart.mp4"))
        self.assertFalse(self.comes_back("I like the sound of that.",
                                         "The Resident_S05E12_Now You See Me.mp4"))
        self.assertFalse(self.comes_back("I like the sound of that.", None))

    def test_seven_words_or_more_everywhere(self):
        self.mute("Are you trying to seduce me right now?", "The Resident_S04E02.mp4")
        self.assertTrue(self.comes_back("Are you trying to seduce me right now?",
                                        "The Resident_S05E01.mp4"))

    def test_taught_lines_still_everywhere(self):
        with open(support.ROOT / "shared_learned.json", encoding="utf-8") as f:
            shared = json.load(f)["shows"]["criminal-minds"]
        self.assertIn("let me see you struggle", shared["muted"])
        added, _ = learn.apply("criminal-minds@adults",
                               [{"s": 1.0, "e": 2.0, "text": "Let me see you struggle."}],
                               [], [], [], on={"sexref"}, video="Criminal Minds - 3-4.m4v")
        self.assertEqual(len(added), 1)

    def test_old_learned_short_lines_stop(self):
        # learned before 1.18.172: no video kept for it, so it isn't muted again anywhere
        path = support.APP_DATA / "learned" / f"{self.KEY}.json"
        path.write_text(json.dumps({"muted": ["and the results are in"], "v2": True, "v3": True}),
                        encoding="utf8")
        self.assertFalse(self.comes_back("And the results are in.",
                                         "The Resident_S05E03.mp4"))

    def test_kept_short_lines_are_trimmed(self):
        for n in range(learn.VIDEO_LINES_KEEP + 5):
            self.mute("I like the sound of that.", f"Episode {n}.mp4")
        d = learn.load(self.KEY)
        self.assertEqual(len(d["video_lines"]), learn.VIDEO_LINES_KEEP)
        self.assertIn(learn.video_key("Episode 304.mp4"), d["video_lines"])
        self.assertNotIn(learn.video_key("Episode 0.mp4"), d["video_lines"])


if __name__ == "__main__":
    unittest.main()
