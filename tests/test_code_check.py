"""Bugs found when the owner asked, 2026-11-13: "also look through the rest of the code for
errors". Each test failed before its fix.

- A word said twice (in one line, or in two lines close together) got one mute, and both lines
  were unticked as "just the word", so the second was heard.
- Asked to mute "affair", the longer "Affairs" earlier in the line was muted instead.
- A video picked up the subtitles of another whose name starts the same ("Cars 2.srt").
- The chat's stretches to look at: one inside another shrank the longer one.
- A shorter learned line further down the candidates was never tried.
- A conversation over 30 lines: the next part started with one stray earlier line and skipped
  the two before it, instead of starting 2 lines back.
- A scene's preview was kept by its start only, so a cut made longer showed the old clip."""
import unittest

import support
import cleanview as engine
import cleanview_ai as ai
import cleanview_claude as cc
import cleanview_learn as learn


def state(lines, **opts):
    """A made-up analysis: each line heard word by word, half a second a word, lines a
    third of a second apart."""
    dialogue, asr, t = [], [], 10.0
    for text in lines:
        words = text.split()
        dialogue.append({"s": t, "e": t + 0.5 * len(words), "text": text, "plain": text})
        for k, w in enumerate(words):
            asr.append([w, t + 0.5 * k, t + 0.5 * k + 0.4])
        t += 0.5 * len(words) + 0.3
    return {"path": "nowhere.mp4", "dialogue": dialogue, "asr": asr, "mutes": [], "lines": [],
            "scenes": [], "opts": engine.full_opts(opts)}


class SaidTwice(unittest.TestCase):

    def test_two_lines_close_together(self):
        st = state(["Was it about sex?", "It's always about sex."], sexref=True)
        st["lines"] = [dict(l, types=["sexref"], mute=True, words=["sex"], idx=i)
                       for i, l in enumerate(st["dialogue"])]
        self.assertEqual(engine.list_words_only(st), 2)
        self.assertEqual(len(st["mutes"]), 2, "one for each time it's said")
        self.assertAlmostEqual(st["mutes"][0]["s"], 11.5, delta=0.6)
        self.assertAlmostEqual(st["mutes"][1]["s"], 13.8, delta=0.6)

    def test_twice_in_one_line(self):
        st = state(["Condoms here and condoms there."], sexref=True)
        self.assertEqual(engine.hard_rule_words(st), 2)
        self.assertEqual(len(st["mutes"]), 2)
        self.assertLess(st["mutes"][0]["e"], st["mutes"][1]["s"] + 0.01)

    def test_twice_in_one_line_when_it_wasnt_heard(self):
        st = state(["Condoms here and condoms there."], sexref=True)
        st["asr"] = []                              # only the subtitles have the words
        engine.hard_rule_words(st)
        self.assertEqual(len(st["mutes"]), 2)
        self.assertLess(st["mutes"][0]["s"], st["mutes"][1]["s"])

    def test_done_again_makes_no_more(self):
        st = state(["Condoms here and condoms there."], sexref=True)
        engine.hard_rule_words(st)
        engine.hard_rule_words(st)
        self.assertEqual(len(st["mutes"]), 2)

    def test_one_word_alone_is_as_before(self):
        st = state(["He was having an affair."])
        a = engine.word_mute(st, st["dialogue"][0], "affair", "you asked")
        b = engine.word_mute(st, st["dialogue"][0], "affair", "you asked")
        self.assertIs(a, b)                         # no "used": the one already there


class TheWordItself(unittest.TestCase):

    def test_not_the_longer_word_before_it(self):
        st = state(["Internal Affairs thinks he was having an affair."])
        m = engine.word_mute(st, st["dialogue"][0], "affair", "you asked")
        self.assertAlmostEqual(m["s"], 13.5, delta=0.6)     # the 8th word, not the 2nd

    def test_hello_isnt_hell(self):
        st = state(["Hello? What the hell is going on?"])
        m = engine.word_mute(st, st["dialogue"][0], "hell", "you asked")
        self.assertAlmostEqual(m["s"], 11.5, delta=0.6)     # the 4th word

    def test_a_longer_word_still_found_when_its_all_there_is(self):
        st = state(["Those were his affairs."])
        m = engine.word_mute(st, st["dialogue"][0], "affair", "you asked")
        self.assertAlmostEqual(m["s"], 11.5, delta=0.6)


class OwnSubtitles(unittest.TestCase):

    def setUp(self):
        self.folder = support.SANDBOX / "subtitle names"
        self.folder.mkdir(exist_ok=True)
        for f in self.folder.iterdir():
            f.unlink()

    def srt(self, name, word):
        cues = "".join(f"{n}\n00:00:{n:02d},000 --> 00:00:{n:02d},900\n{word} line {n}\n\n"
                       for n in range(1, 9))
        (self.folder / name).write_text(cues, encoding="utf8")

    def found(self, video):
        (self.folder / video).write_bytes(b"")
        return engine.find_subtitles(self.folder / video, {"subs": []}, self.folder)

    def test_not_the_sequels(self):
        self.srt("Cars 2.srt", "sequel")
        self.assertEqual(self.found("Cars.mkv"), ([], ""))

    def test_its_own_wins(self):
        self.srt("Cars.srt", "first")
        self.srt("Cars 2.en.srt", "sequel")
        cues, said = self.found("Cars.mkv")
        self.assertIn("first", cues[0]["text"])
        self.assertIn("Cars.srt", said)

    def test_its_own_with_a_language(self):
        self.srt("Show S01E1.en.srt", "one")
        self.srt("Show S01E10.srt", "ten")
        cues, said = self.found("Show S01E1.mkv")
        self.assertIn("one", cues[0]["text"])


class SmallOnes(unittest.TestCase):

    def test_a_stretch_inside_another_keeps_the_longer(self):
        asked = [{"from": "0:00", "to": "10:00"}, {"from": "1:40", "to": "3:20"}]
        self.assertEqual(cc.look_spans(asked), [(0.0, 600.0)])
        asked = [{"from": "0:00", "to": "2:00"}, {"from": "1:40", "to": "3:20"}]
        self.assertEqual(cc.look_spans(asked), [(0.0, 200.0)])           # overlapping: as before

    def test_a_shorter_lesson_further_on_is_still_tried(self):
        long_one = ("the quick brown fox jumps over the lazy dog and then runs far away across "
                    "the wide green field toward the old red barn where the farmer keeps his "
                    "many sheep and goats")
        short = "no no no i said no way jose"
        heard = "the fox and the dog over the field no no no i said no way jose"
        find = learn.LearnedLines([long_one, short])
        self.assertEqual(find.match(learn.norm(heard)), learn.norm(short))

    def test_a_long_conversation_starts_two_lines_back(self):
        lines = [{"s": float(i), "e": i + 0.9, "text": f"line {i}"} for i in range(70)]
        convs = ai.conversations(lines)
        self.assertEqual(convs[0], list(range(30)))
        self.assertEqual(convs[1][:4], [28, 29, 30, 31])
        self.assertEqual(sorted(set(i for c in convs for i in c)), list(range(70)), "none skipped")
        for c in convs:
            self.assertEqual(c, list(range(c[0], c[-1] + 1)), "no holes")

    def test_a_preview_is_kept_by_its_start_and_end(self):
        made = []

        class Done:
            returncode = 0
        saved, engine.cl.run = engine.cl.run, lambda cmd, **k: (made.append(cmd[-1]), Done())[1]
        try:
            a = engine.make_preview("video.mp4", 100.0, 110.0, support.SANDBOX)
            b = engine.make_preview("video.mp4", 100.0, 125.0, support.SANDBOX)
        finally:
            engine.cl.run = saved
        self.assertNotEqual(a, b)
        self.assertEqual(len(made), 2)


if __name__ == "__main__":
    unittest.main()
