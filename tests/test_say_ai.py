"""CleanView says "AI", not "Claude" (1.18.86; the owner, 2026-11-13: "Not in the Claud, chat,
gemini section, but everywhere else in clean view, instead of saying "claude" say "Ai"").

Step 3, where one of Claude, ChatGPT and Gemini is chosen and set up, still names them. Which
one helped is still kept with the review and sent in; only what the window and the report say
is changed. Older reviews, saved with the name in their notes and labels, are shown the new
way too."""
import unittest
import tkinter as tk

import support
import cleanview as engine
from test_ui import ui

NAMES = ("Claude", "ChatGPT", "Gemini")


class OldWordsShownTheNewWay(unittest.TestCase):
    def test_at_the_start_of_a_note(self):
        P = engine.plain_ai
        self.assertEqual(P("Claude reviewed everything: 7 found item(s) look fine in context."),
                         "The AI reviewed everything: 7 found item(s) look fine in context.")
        self.assertEqual(P("ChatGPT couldn't read the dialogue this time: it isn't signed in."),
                         "The AI couldn't read the dialogue this time: it isn't signed in.")
        self.assertEqual(P("Gemini's final review didn't work this time (timed out)."),
                         "The AI's final review didn't work this time (timed out).")

    def test_in_a_label(self):
        P = engine.plain_ai
        self.assertEqual(P("Found by Claude"), "Found by AI")
        self.assertEqual(P("Seen by ChatGPT"), "Seen by AI")
        self.assertEqual(P("Asked Gemini"), "Asked AI")
        self.assertEqual(P("fight seen (widened by Claude)"), "fight seen (widened by AI)")

    def test_everything_else_is_left_as_it_is(self):
        P = engine.plain_ai
        for text in ("Gore", "Same-sex romance · two men", "No subtitles: none were found online.",
                     "The AI reviewed everything: nothing changed.",
                     "Muted just the word in 3 line(s) the word list found.",
                     "Claudette waved from the Gemini capsule."):
            self.assertEqual(P(text), text)

    def test_the_steps_are_still_told_apart(self):
        S = engine.scan_step
        self.assertEqual(S("The AI is reading the dialogue…"), "reading the dialogue")
        self.assertEqual(S("The AI is reviewing everything that was found…"), "final review")
        self.assertEqual(S("The AI is looking through the whole picture · 2 min left"),
                         "looking through the picture")
        self.assertEqual(S("Claude is reading the dialogue…"), "reading the dialogue")    # older
        self.assertTrue(engine.technical(
            "The AI looked through the whole picture (3020 stills): it confirmed 1 scene(s)."))

    def test_the_engines_own_words(self):
        self.assertEqual(engine.LINE_LABEL["claude"], "Found by AI")
        self.assertEqual(engine.THE_AI, "The AI")


class TheWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.real = (ui.App._check_update, ui.App._check_every_ai, ui.App._pick_review_ai,
                    ui.cc.status)
        ui.App._check_update = lambda self, manual=False: None
        ui.App._check_every_ai = lambda self: None
        ui.cc.status = lambda p=None: "ready"
        try:
            cls.app = ui.App()
        except tk.TclError as ex:
            cls.put_back()
            raise unittest.SkipTest(f"no screen to draw on ({ex})")
        cls.app.update()

    @classmethod
    def put_back(cls):
        (ui.App._check_update, ui.App._check_every_ai, ui.App._pick_review_ai,
         ui.cc.status) = cls.real

    @classmethod
    def tearDownClass(cls):
        try:
            cls.app.destroy()
        except tk.TclError:
            pass
        cls.put_back()

    def texts(self, w=None):
        w = w or self.app
        out = []
        if isinstance(w, (tk.Label, tk.Button)) or w.winfo_class() in ("TButton", "TCheckbutton"):
            out.append(str(w.cget("text")))
        if isinstance(w, tk.Canvas):
            out += [str(w.itemcget(i, "text")) for i in w.find_all() if w.type(i) == "text"]
        for c in w.winfo_children():
            out += self.texts(c)
        return out

    def review(self, provider):
        """The sample review as an older version saved it, with that AI's name all through."""
        name = ui.cc.NAMES[provider]
        ui.App._pick_review_ai = lambda self, good: provider
        st = support.sample_review()
        st["reviewer"] = name
        st["claude_summary"] = "Everything on the lists needed muting."
        st["notes"] = [f"{name} reviewed everything: 1 found item(s) look fine in context.",
                       f"{name} couldn't look at the picture this time (timed out).",
                       "No subtitles: none were found online."]
        st["scenes"][0].update(kind=[f"Seen by {name}"],
                               why="Claude kisses Marie on the balcony",       # a character
                               claude={"decision": "remove", "why": "a long kiss"})
        st["scenes"][1]["kind"] = [f"Found by {name}"]
        st["lines"][0]["types"] = ["claude"]
        st["dialogue"][0]["text"] = "Claude, wait for me!"
        app = self.app
        app.jobs = [{"video": st["path"], "work": support.write_review(), "analysis": st,
                     "error": None, "cuts": [], "lines": [], "words": []}]
        app.videos = [st["path"]]
        app.chat_history, app.chat_sessions = [], {}
        app.ai_state = {provider: "ready"}
        app.show_review()
        app.update()
        return self.texts(), [app._nb.tab(i, "text").strip() for i in range(3)]

    def test_the_review_page_says_ai(self):
        for provider in ui.cc.NAMES:
            with self.subTest(provider):
                said, tabs = self.review(provider)
                everything = "\n".join(said)
                self.assertEqual(tabs[2], "Ask AI")
                self.assertIn("The AI's review", said)
                self.assertIn("Found by AI", said)
                self.assertIn("Seen by AI", said)
                self.assertIn("Ask AI about this…", said)
                self.assertIn("The AI reviewed everything: 1 found item(s) look fine in context.",
                              everything)
                self.assertIn("The AI couldn't look at the picture this time (timed out).",
                              everything)
                self.assertIn("AI: cut — a long kiss", everything)
                self.assertIn("The AI's findings on this video", said)
                # the film's own Claude is still Claude
                self.assertIn("Claude kisses Marie on the balcony", everything)
                everything = everything.replace("Claude kisses Marie on the balcony", "")
                for name in NAMES:
                    self.assertNotIn(name, everything, f"{name} is still named")

    def test_which_one_it_was_is_still_kept(self):
        self.review("chatgpt")
        st = self.app.jobs[0]["analysis"]
        self.assertEqual(st["reviewer"], "ChatGPT")
        self.assertIn("ChatGPT reviewed everything", st["notes"][0])        # as it was saved

    def test_the_ai_helper_step_still_names_them(self):
        self.app.show_setup()
        self.app._go_step(3)
        self.app.update()
        said = "\n".join(self.texts())
        for name in NAMES:
            self.assertIn(name, said)


if __name__ == "__main__":
    unittest.main()
