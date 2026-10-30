"""What they tell the chat to keep in mind from now on (Jason, 2026-10-30: he explained Aladdin
was different and the chat said it couldn't change what it looks for). The chat now keeps it
as a note, for that movie or show, or for everything, and later checks follow it. Also the
review page's way back to the start page without saving."""
import unittest

import support  # noqa: F401  (sets up the sandbox first)
import cleanview as engine
import cleanview_claude as cc
import cleanview_learn as learn


class Notes(unittest.TestCase):

    def setUp(self):
        for f in learn.DIR.glob("*.json"):
            f.unlink()

    def test_a_movie_note_is_for_that_movie(self):
        self.assertTrue(learn.add_note("_movies@kids", "The Genie's magic is fine.", "Aladdin (1992)"))
        self.assertEqual(learn.notes("_movies@kids", "Aladdin (1992)"), ["The Genie's magic is fine."])
        self.assertEqual(learn.notes("_movies@kids", "Frozen (2013)"), [])

    def test_a_show_note_is_for_every_episode(self):
        learn.add_note("gummi-bears@kids", "Cartoon bonks on the head are fine.", "Gummi Bears")
        self.assertEqual(learn.notes("gummi-bears@kids", "anything"),
                         ["Cartoon bonks on the head are fine."])
        self.assertEqual(learn.notes("castle", "Castle"), [])

    def test_a_note_for_everything_is_for_that_age(self):
        learn.add_note("_movies@kids", "Never mute 'gosh'.", "Aladdin (1992)", everywhere=True)
        self.assertEqual(learn.notes("castle@kids", "Castle"), ["Never mute 'gosh'."])
        self.assertEqual(learn.notes("_movies@kids", "Frozen (2013)"), ["Never mute 'gosh'."])
        self.assertEqual(learn.notes("castle", "Castle"), [])    # what she watches herself

    def test_said_twice_kept_once(self):
        self.assertTrue(learn.add_note("castle", "Slapstick is fine."))
        self.assertFalse(learn.add_note("castle", "slapstick is fine."))
        self.assertEqual(len(learn.notes("castle")), 1)

    def test_every_later_check_is_told(self):
        learn.add_note("_movies@kids", "The Genie's magic is fine.", "Aladdin (1992)")
        ex = learn.examples("_movies@kids", title="Aladdin (1992)")
        self.assertEqual(ex["notes"], ["The Genie's magic is fine."])
        self.assertIn("The Genie's magic is fine.", cc._examples(ex))   # dialogue + final review
        self.assertEqual(engine.title_name(r"D:\Movies\Aladdin (1992).mkv"), "Aladdin (1992)")


class Chat(unittest.TestCase):

    def setUp(self):
        self.asked = []
        self.real = cc.ask

        def ask(prompt, schema, stdin_text="", system=None, session=None, keep=False, **k):
            self.asked.append((prompt, schema))
            return {"reply": "OK, I'll keep the Genie's magic from now on.", "tick": [],
                    "untick": [], "mute_lines": [], "mute_words": [], "cut_scenes": [],
                    "cut_times": [],
                    "remember": [{"note": "The Genie's magic is fine.", "for": "this"},
                                 {"note": "  ", "for": "everything"}]}, "s1"
        cc.ask = ask

    def tearDown(self):
        cc.ask = self.real

    def test_the_chat_can_keep_what_they_explain(self):
        self.assertIn("remember", cc.CHAT_SCHEMA["required"])
        self.assertIn("CAN learn", cc.CHAT_HOW)
        st = {"dialogue": [{"s": 0, "e": 2, "text": "Phenomenal cosmic powers!"}],
              "scenes": [], "lines": [], "mutes": []}
        reply, acts, items, sid = cc.chat("It's Aladdin, the magic is fine", st,
                                          notes=["Never mute 'gosh'."])
        self.assertEqual(acts["remember"], [("The Genie's magic is fine.", False)])
        self.assertIn("Never mute 'gosh'.", self.asked[0][0])   # it's told the earlier ones


class Lessons(unittest.TestCase):
    """Jason (1.18.1): told it the couple in bed were only talking, the chat unticked the
    scene but kept no lesson, and the picture check had cut it for "two people in bed"."""

    def test_a_correction_is_a_lesson(self):
        self.assertIn("whenever they correct a call", cc.CHAT_HOW)
        self.assertIn("not a sex scene", cc.CHAT_HOW)

    def test_two_people_in_bed_talking_is_not_a_sex_scene(self):
        self.assertIn("in bed talking", cc.PIC_RULES)
        self.assertIn("is NOT a sex scene", cc.PIC_RULES)

    def test_picture_checks_follow_the_lessons(self):
        import inspect
        src = inspect.getsource(engine.look_at_picture)
        self.assertIn("learn.notes(learned_key(path, o)", src)
        self.assertEqual(engine.learned_key(r"D:\Movies\Aladdin (1992).mkv", {"profile": "kids"}),
                         "_movies@kids")


class CountedOnce(unittest.TestCase):

    def setUp(self):
        for f in learn.DIR.glob("*.json"):
            f.unlink()

    def test_leaving_and_coming_back_counts_each_choice_once(self):
        sc = {"kind": ["Sex scene"], "_shown": True}
        w = {"word": "damn", "_shown": False}
        for _ in range(3):                         # back to start, pick up, back again...
            learn.record("castle", [], [], [], [sc], [False], [], [w], [True])
        d = learn.load("castle")
        self.assertEqual(d["scenes"]["Sex scene"], {"cut": 0, "kept": 1})
        self.assertEqual(d["words"]["damn"], {"muted": 1, "kept": 0})
        learn.record("castle", [], [], [], [sc], [True], [], [w], [True])   # she changed it
        d = learn.load("castle")
        self.assertEqual(d["scenes"]["Sex scene"], {"cut": 1, "kept": 0})


class BackToStart(unittest.TestCase):

    def test_back_to_start_keeps_the_review(self):
        from test_ui import Window, ui
        Window.setUpClass()
        try:
            app = Window.app
            support.write_review()
            self.assertTrue(app._resume())
            app.update()
            texts = [w.cget("text") for w in app.footer.winfo_children()
                     if isinstance(w, ui.ttk.Button)]
            self.assertIn("\u25c0 Back to start", texts)
            app._forget_session()
            learned = []
            real = ui.learn.record
            ui.learn.record = lambda key, *a: learned.append(key)
            try:
                app._back_to_start()
            finally:
                ui.learn.record = real
            app.update()
            self.assertEqual(app.page_name, "setup")
            self.assertTrue(app.SESSION.exists(), "Pick up where I left off opens it again")
            self.assertTrue(learned, "her ticks are learned without saving a copy")
        finally:
            Window.tearDownClass()

    def test_the_videos_name_is_on_the_review_page(self):
        """Jason: after cleaning you don't know which movie it was."""
        from test_ui import Window, ui
        Window.setUpClass()
        try:
            app = Window.app
            support.write_review()
            self.assertTrue(app._resume())
            app.update()
            texts = [w.cget("text") for w in app.page.winfo_children()
                     if isinstance(w, ui.tk.Label)]
            self.assertIn("Sample Show S01E01", texts)
        finally:
            Window.tearDownClass()

    def test_questions_chime(self):
        from test_ui import ui
        import inspect
        src = inspect.getsource(ui.App._send_in)
        self.assertLess(src.index("chime()"), src.index("askyesno"))


if __name__ == "__main__":
    unittest.main()
