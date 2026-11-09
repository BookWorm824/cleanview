"""Lessons from the reports sent in from 2026-10-30 to 2026-11-02 (Toy Story 4, Castle,
Person of Interest, Iron Man, Clue, Enchanted, Chicken Run, G.I. Joe, National Treasure 2
and others): what was flagged wrongly or missed, so it isn't again."""
import subprocess
import unittest
from unittest import mock

import support  # noqa: F401  (sets up the sandbox first)

import cleanview as engine
import cleanview_claude as cc
import cvcore as cl


def subtitle_words(lines):
    cues = [{"text": t} for t in lines]
    sw, cue = [], []
    for ci, c in enumerate(cues):
        for w in engine.spoken_words(c["text"]):
            if cl.norm(w):
                sw.append(w)
                cue.append(ci)
    return sw, cue, cues


class LongPrompt(unittest.TestCase):
    """Clue: the final review failed with "[WinError 206] The filename or extension is too
    long": the whole prompt was on the command line."""

    def ask(self, prompt):
        ran = {}

        def run(cmd, input=None, **kw):
            ran.update(cmd=cmd, input=input)
            return subprocess.CompletedProcess(
                cmd, 0, '{"structured_output": {"ok": true}, "session_id": "s"}', "")
        with mock.patch.object(cc, "find_claude", return_value="claude"), \
                mock.patch.object(cc, "PROVIDER", "claude"), \
                mock.patch.object(cc.subprocess, "run", run):
            cc._ask_now(prompt, {"type": "object"}, "the dialogue", system="be brief")
        return ran

    def test_a_long_prompt_goes_in_through_stdin(self):
        prompt = "Review this. " * 4000
        ran = self.ask(prompt)
        self.assertNotIn(prompt, ran["cmd"])
        self.assertLess(sum(len(a) for a in ran["cmd"]), 8000)
        self.assertTrue(ran["input"].startswith(prompt))
        self.assertTrue(ran["input"].endswith("the dialogue"))

    def test_a_short_one_stays_on_the_command_line(self):
        ran = self.ask("Review this.")
        self.assertIn("Review this.", ran["cmd"])
        self.assertEqual(ran["input"], "the dialogue")


class SoundOnlyScenes(unittest.TestCase):
    """Toy Story 4: 17 Violence scenes from gasps and screams alone."""

    def scenes(self, label):
        labels = list(engine.VIOLENCE_SOUNDS)
        row = [0.0] * len(labels)
        row[labels.index(label)] = 0.95
        snd = {"labels": labels, "t": [10.0 + 1.5 * k for k in range(6)], "p": [row] * 6}
        return engine.violence_scenes(snd, [])

    def test_screams_alone_are_offered_unticked(self):
        sc, = self.scenes("Screaming")
        self.assertFalse(sc["sure"])
        self.assertIn("only heard", sc["why"])

    def test_gunfire_still_cuts(self):
        sc, = self.scenes("Gunshot, gunfire")
        self.assertTrue(sc["sure"])

    def test_subtitles_describing_a_fight_still_cut(self):
        labels = list(engine.VIOLENCE_SOUNDS)
        row = [0.0] * len(labels)
        row[labels.index("Screaming")] = 0.95
        snd = {"labels": labels, "t": [10.0 + 1.5 * k for k in range(6)], "p": [row] * 6}
        sc, = engine.violence_scenes(snd, [{"s": 11.0, "e": 15.0, "text": "[gunshot]"}])
        self.assertTrue(sc["sure"])


class TalkIsNotASexScene(unittest.TestCase):
    def test_one_word_said_over_and_over_isnt_explicit(self):
        self.assertEqual(cl.sex_score(["thrust"] * 6), 0)          # Chicken Run's flying talk

    def test_talk_alone_is_offered_unticked(self):
        words = "she had sex and an orgasm and then sex again naked and orgasm and sex".split()
        asr = [{"s": float(k), "e": k + 0.5, "t": w} for k, w in enumerate(words)]
        sc, = engine.sex_scenes(None, [], words, asr, [], [])   # Castle: a coroner's findings
        self.assertFalse(sc["sure"])
        self.assertIn("only talk", sc["why"])


class MisheardSwears(unittest.TestCase):
    """Person of Interest: "Finch" heard as "bitch" three times; National Treasure 2:
    Mitch; G.I. Joe: "bugging out" heard as "fucking"."""

    def mute(self, heard, written):
        asr_n = ["it's", heard, "here"]
        sw = sn = ["it's", written, "here"]
        m = {"src": "audio", "at": 1, "cat": "moderate"}
        engine.subtitle_word_there([m], [0, 1, 2], sw, [cl.norm(w) for w in sn], asr_n)
        return m

    def test_a_sound_alike_word_in_the_subtitles_unticks_it(self):
        for heard, written in (("bitch", "Finch"), ("bitch", "Mitch"), ("dick", "Nic"),
                               ("fucking", "bugging")):
            m = self.mute(heard, written)
            self.assertTrue(m.get("keep"), heard + "/" + written)
            self.assertEqual(m["sub"], written)

    def test_a_different_word_is_only_noted(self):
        m = self.mute("shit", "page")
        self.assertEqual(m["sub"], "page")
        self.assertFalse(m.get("keep"))


class NamesAndBareGod(unittest.TestCase):
    def test_a_capitalised_word_mid_sentence_is_a_name(self):
        sw, cue, cues = subtitle_words(["Detective Dern is here.", "I read Hell Hath No Fury.",
                                        "Go to Hell.", "What the Hell?", "Oh, Heck!",
                                        "Dern it all."])
        names = [sw[k] for k in range(len(sw)) if engine.name_in_subtitles(sw, cue, cues, k)]
        self.assertIn("Dern", names)
        # "Hell" is still the word in a title: she ticks it (Castle S1E1, 2026-11-08)
        self.assertNotIn("Hell", names)
        self.assertNotIn("Hell.", names)
        self.assertNotIn("Hell?", names)
        self.assertNotIn("Heck!", names)
        self.assertEqual(names.count("Dern"), 1)        # not "Dern it all." starting a line

    def test_a_bare_god_said_as_an_oath(self):
        sw, cue, cues = subtitle_words([
            "God!", "God, you need a new name for that.", "God, please help us.",
            "Thank God.", "Oh, God.", "I believe in God.", "God bless you.", "God."])
        said = [(cue[k], sw[k]) for k in range(len(sw)) if engine.bare_god(sw, cue, cues, k)]
        self.assertEqual(said, [(0, "God!"), (1, "God,"), (7, "God.")])


class LineWords(unittest.TestCase):
    def test_gay_meaning_happy_isnt_a_same_sex_line(self):
        self.assertIsNone(engine.LINE_WORDS["samesex"].search("Sing the gay refrain"))
        self.assertIsNotNone(engine.LINE_WORDS["samesex"].search("Her brother is gay."))


if __name__ == "__main__":
    unittest.main()
