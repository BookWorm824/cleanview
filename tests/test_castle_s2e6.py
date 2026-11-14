"""Lauren's Castle S2E6 report (1.18.95, 2026-11-14, adults, the AI helper, made on 1.18.92; the
owner: "yes teach", then "1 and 2" to catching them the first time). Every listed word was
muted; six lines that fit her filters went through: Crow and Daemon (two men) as a couple,
Vixen's "lovers", and three bits of innuendo.

1. The short no-AI list: "sleeping with her/him/me...", "my/his/her lover(s)", "sexy/sexiest".
2. Who's a man and who's a woman is worked out from the whole dialogue before it's read, and
   the readers are told. Trying it showed the AI helper's conversation check had found "Daemon
   fell in love with Crow" (two men) and thrown it away: its quote ran into the next subtitle
   line."""
import inspect
import unittest
from unittest import mock

import support  # noqa: F401  (sets up the sandbox first)
import cleanview as engine
import cleanview_ai as ai
import cleanview_learn as learn

TAUGHT = {"Daemon fell in love with Crow and his art": "samesex",
          "He was Crow's boyfriend, not mine.": "samesex",
          "He was one of my lovers.": "casual",
          "Fine. But I'm not sleeping with her.": "sexref",
          "Just because I've seen your tat, doesn't mean I'm gonna show you my...": "sexref",
          "Also, you might wonder what happened to your pants.": "sexref"}


def finds(kind, text):
    return [engine.LIST_WORD_TRIM.sub("", m.group(0)) for m in engine.LINE_WORDS[kind].finditer(text)]


def lines_of(texts, gap=1.0):
    return [{"s": i * 3.0, "e": i * 3.0 + gap, "text": t} for i, t in enumerate(texts)]


class Taught(unittest.TestCase):
    def test_built_in_with_their_filter(self):
        muted = learn._sh("castle", "muted")
        kinds = learn.shared()["shows"]["castle"]["muted_for"]
        for text, kind in TAUGHT.items():
            line = learn.norm(text)
            self.assertIn(line, muted, text)
            self.assertEqual(kinds.get(line), kind, text)
            # only muted when that filter is ticked
            self.assertIn(line, learn._for_filters("castle", muted, {kind}), text)
            self.assertNotIn(line, learn._for_filters("castle", muted, {"crude"}), text)

    def test_each_has_five_words_or_more(self):
        for text in TAUGHT:
            self.assertGreaterEqual(len(learn.norm(text).split()), learn.LEARNED_SHORTEST, text)


class ShortList(unittest.TestCase):
    def test_sleeping_with(self):
        for text, said in (("Fine. But I'm not sleeping with her.", "sleeping with her"),
                           ("I'm sleeping with her now", "sleeping with her"),
                           ("But not because she was sleeping with him.", "sleeping with him"),
                           ("HE WAS SLEEPING WITH ME.", "SLEEPING WITH ME"),
                           ("Whispers are he's sleeping with his intern.",
                            "sleeping with his intern"),
                           ("she's been sleeping with a married man", "sleeping with a married man"),
                           ("So, you're sleeping with Jude now?", "sleeping with"),
                           # the plurals (1.18.96, from CleanListen's check)
                           ("sleeping with their secretaries", "sleeping with their secretaries"),
                           ("men sleeping with their wives", "sleeping with their wives"),
                           ("sleeping with her bosses", "sleeping with her bosses"),
                           ("sleeping with my exes", "sleeping with my exes")):
            self.assertEqual(finds("casual", text), [said], text)

    def test_sleeping_with_left_alone(self):
        for text in ("she was sleeping with her teddy bear", "sleeping with the fishes",
                     "we were sleeping with the window open", "sleeping with one eye open",
                     "sleeping with her blanket again"):
            self.assertEqual(finds("casual", text), [], text)

    def test_lovers_just_the_word(self):
        self.assertEqual(finds("casual", "He was one of my lovers."), ["lovers"])
        self.assertEqual(finds("casual", "OR HE AND HIS LOVER KILL MELANIE"), ["LOVER"])
        for text in ("a lover of fine wine", "animal lovers across the country",
                     "Probably a food lover like me", "Hey, lover.", "Lover boy"):
            self.assertEqual(finds("casual", text), [], text)

    def test_sexy(self):
        self.assertEqual(finds("sexref", "That is the sexiest thing I ever heard you say."),
                         ["sexiest"])
        self.assertEqual(finds("sexref", "Yeah, well, I was going for sexy."), ["sexy"])
        self.assertEqual(finds("sexref", "a sexier look"), ["sexier"])
        self.assertEqual(finds("sexref", "the Essex coast"), [])

    def test_still_found_before(self):
        self.assertEqual(finds("casual", "He cheated on her"), ["cheated on her"])
        self.assertEqual(finds("casual", "having an affair with him"), ["affair"])


class WhosWho(unittest.TestCase):
    DIALOGUE = ["Do you know somebody named Matthew Freeman?", "Who? Crow.",
                "Crow? Sure, why? Is he in some kind of trouble?",
                "We found him in a cemetery.", "But I didn't kill him. He was one of my lovers.",
                "Daemon. Daemon fell in love with Crow and his art",
                "and talked him into writing a graphic novel.", "Daemon have a last name?",
                "I don't know his real name.", "He was Crow's boyfriend, not mine.",
                "Okay. Thank you, Vixen."]

    def test_the_names_in_love_talk(self):
        names = ai.who_candidates(lines_of(self.DIALOGUE))
        self.assertIn("Crow", names)
        self.assertIn("Daemon", names)
        self.assertNotIn("Okay", names)
        self.assertNotIn("Thank", names)

    def test_nothing_to_ask(self):
        asked = []
        with mock.patch.object(ai, "chat", lambda *a, **k: asked.append(a) or {}):
            self.assertEqual(ai.who_is_who(lines_of(["Pass the salt, Bob.", "Here you go."])), {})
        self.assertEqual(asked, [])

    def test_only_what_the_dialogue_shows(self):
        def chat(prompt, schema=None, timeout=None):
            self.assertIn("Crow", prompt)
            return {"people": [
                {"name": "Crow", "is": "man", "words": "Is he in some kind of trouble"},
                {"name": "Daemon", "is": "man", "words": "I don't know his real name"},
                {"name": "Matthew", "is": "woman", "words": "she was lovely"},    # not said
                {"name": "Vixen", "is": "unknown", "words": ""},
                {"name": "Nobody", "is": "man", "words": "Is he in some kind of trouble"}]}
        with mock.patch.object(ai, "chat", chat):
            people = ai.who_is_who(lines_of(self.DIALOGUE))
        self.assertEqual(people, {"Crow": "man", "Daemon": "man"})
        note = ai.who_note(people)
        self.assertIn("Crow is a man; Daemon is a man", note)
        self.assertTrue(engine.technical(note))
        self.assertEqual(ai.who_note({}), "")

    def test_a_failed_question_changes_nothing(self):
        def chat(*a, **k):
            raise RuntimeError("Ollama isn't answering")
        with mock.patch.object(ai, "chat", chat):
            self.assertEqual(ai.who_is_who(lines_of(self.DIALOGUE)), {})

    def test_english_only(self):
        with mock.patch.object(ai.cvlang, "LANG", "es"):
            self.assertEqual(ai.who_is_who(lines_of(self.DIALOGUE)), {})

    def test_analyze_tells_the_readers(self):
        src = inspect.getsource(engine.analyze)
        self.assertIn("ai.who_is_who(lines, genders, cancel)", src)
        a = src.index("ai.who_is_who(")
        self.assertLess(a, src.index("line_mutes, line_how = find_lines("))
        self.assertLess(a, src.index("flirts = ai.romance_scenes("))
        self.assertIn("notes.append(ai.who_note(people))", src)
        self.assertIn("examples, unread, people)", src)        # to the line reader
        self.assertIn("notes=told, people=people)", src)       # and each conversation

    def test_told_beside_the_lines(self):
        people = {"Crow": "man", "Daemon": "man", "Elizabeth": "woman"}
        said = ai.who_here(people, "Daemon fell in love with Crow and his art")
        self.assertIn("Crow is a man", said)
        self.assertIn("Daemon is a man", said)
        self.assertNotIn("Elizabeth", said)          # only those named there
        self.assertEqual(ai.who_here(people, "Nobody named here."), "")
        self.assertEqual(ai.who_here({}, "Crow"), "")
        prompts = []

        def chat(prompt, schema=None, timeout=None):
            prompts.append(prompt)
            return {"flags": []} if "flags" in (schema or {}).get("properties", {}) else {}
        with mock.patch.object(ai, "chat", chat):
            ai.classify_dialogue(lines_of(self.DIALOGUE), ["samesex"], people=people)
            ai.romance_scenes(lines_of(self.DIALOGUE), None, people=people)
        self.assertTrue(prompts)
        self.assertTrue(all("From the rest of the dialogue: " in p for p in prompts))


class QuoteOverTwoLines(unittest.TestCase):
    def test_kept(self):
        lines = lines_of(["You said he was seeing someone else?",
                          "Daemon. Daemon fell in love with Crow and his art",
                          "and talked him into writing a graphic novel.", "That's why he's dead."])

        def chat(prompt, schema=None, timeout=None):
            props = (schema or {}).get("properties", {})
            if "quote" in props:
                return {"romance": True, "between": "two men", "lines": [2, 3],
                        "quote": "Daemon fell in love with Crow and his art and talked him into "
                                 "writing a graphic novel.", "what": "Daemon loved Crow"}
            if "between" in props:
                return {"romance": True, "between": "two men"}
            return {"romance": True}
        with mock.patch.object(ai, "chat", chat):
            found = ai.romance_scenes(lines, None)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["between"], "mm")

    def test_words_not_said_still_thrown_away(self):
        lines = lines_of(["Hello there.", "How was the game?", "We won."])

        def chat(prompt, schema=None, timeout=None):
            props = (schema or {}).get("properties", {})
            if "quote" in props:
                return {"romance": True, "between": "two men", "lines": [1],
                        "quote": "I love you so much", "what": "a guess"}
            return {"romance": True, "between": "two men"}
        with mock.patch.object(ai, "chat", chat):
            self.assertEqual(ai.romance_scenes(lines, None), [])


if __name__ == "__main__":
    unittest.main()
