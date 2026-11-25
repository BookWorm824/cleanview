"""Words are never written out on her screen (1.18.170, 2026-11-25; the owner, with a screenshot
of an AI note that said to mute just the word and wrote it in full: "I NEVER want to see the
words spelled out!! the whole point is not see it"). Nothing here opens a window."""
import unittest

import support  # noqa: F401  (must come first)
import test_ui

ui = test_ui.ui


class HideWords(unittest.TestCase):

    def test_the_ai_note_from_her_screenshot(self):
        line = {"text": "And that f****** yoga instructor.", "s": 1, "e": 2,
                "claude": {"decision": "just the word", "word": "fucking",
                           "why": "Only the swear"}}
        note, _ = ui.claude_note(line, True)
        self.assertNotIn("fucking", note)
        self.assertIn("“f******”", note)          # the quotes kept
        self.assertIn("(the rest of the line stays)", note)
        self.assertIn("Only the swear", note)

    def test_several_words_and_the_why(self):
        line = {"text": "x", "claude": {"decision": "just the word", "word": "shit|damn",
                                        "why": "He says shit and damn, nothing else"}}
        note, _ = ui.claude_note(line, True)
        for w in ("shit", "damn"):
            self.assertNotIn(w, note.lower())
        self.assertIn("s***", note)
        self.assertIn("nothing else", note)

    def test_stops_and_quotes_kept(self):
        self.assertEqual(ui.hide_words("Oh, shit! Is that hell?"), "Oh, s***! Is that h***?")
        self.assertEqual(ui.hide_words("What the hell?"), "W*** t** h***?")   # as the lines show
        self.assertEqual(ui.hide_words('"bitch",'), '"b****",')

    def test_ordinary_words_and_spacing_left(self):
        text = "A shell, a hello\nand Mr. Dickens  at the dam."
        self.assertEqual(ui.hide_words(text), text)

    def test_starred_stays_starred(self):
        self.assertEqual(ui.hide_words("And that f****** yoga instructor."),
                         "And that f****** yoga instructor.")

    def test_nothing_or_not_text(self):
        self.assertEqual(ui.hide_words(""), "")
        self.assertIsNone(ui.hide_words(None))

    def test_answers_and_found_and_dialogue_go_through_it(self):
        with open(ui.__file__, encoding="utf8") as f:
            src = f.read()
        for spot in ('hide_words(it["chat_answer"])', 'hide_words(sc["why"])',
                     'hide_words(l["text"])', "hide_words(m['sub'])",
                     'log.insert("end", hide_words(text)'):
            self.assertIn(spot, src)


if __name__ == "__main__":
    unittest.main()
