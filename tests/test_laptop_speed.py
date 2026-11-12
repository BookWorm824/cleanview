"""Each conversation's flirting check asks a quick yes or no first, with the very same words,
and only asks for the details on a yes (1.18.68; the owner: "is there any other places to
check efficiency", then "1"). The full answer form made the AI helper write 45-170 words for
every conversation, slow when its model is only partly on the graphics card (Lauren's laptop:
16 of 40 minutes)."""
import unittest
from unittest import mock

import support  # noqa: F401  (sets up the sandbox first)
import cleanview_ai as ai

LINES = [{"s": 10.0, "e": 12.0, "text": "Want to grab dinner sometime?"},
         {"s": 12.5, "e": 14.0, "text": "I'd like that."},
         {"s": 40.0, "e": 42.0, "text": "The labs came back."},
         {"s": 42.5, "e": 44.0, "text": "Order another scan."}]


class QuickFirst(unittest.TestCase):
    def setUp(self):
        self.asked = []

        def chat(prompt, *a, schema=None, **k):
            props = (schema or {}).get("properties", {})
            kind = "quick" if list(props) == ["romance"] else "full" if "quote" in props \
                else "confirm"
            dinner = "dinner" in prompt
            self.asked.append((kind, dinner, prompt))
            if kind == "quick":
                return {"romance": dinner}
            if kind == "full":
                return {"romance": True, "between": "a man and a woman", "lines": [1],
                        "quote": "grab dinner", "what": "He asks her out."}
            return {"romance": True, "between": "a man and a woman"}
        p = mock.patch.object(ai, "chat", chat)
        p.start()
        self.addCleanup(p.stop)

    def test_details_only_on_a_yes(self):
        (f,) = ai.romance_scenes(LINES, None)
        self.assertEqual(f["between"], "mf")
        kinds = [(k, d) for k, d, _ in self.asked]
        self.assertEqual(kinds, [("quick", True), ("full", True), ("confirm", True),
                                 ("quick", False)])

    def test_the_same_words(self):
        ai.romance_scenes(LINES, None)
        quick, full = self.asked[0][2], self.asked[1][2]
        self.assertEqual(quick, full)

    def test_a_short_answer_form(self):
        self.assertEqual(ai.QUICK_YES["required"], ["romance"])


if __name__ == "__main__":
    unittest.main()
