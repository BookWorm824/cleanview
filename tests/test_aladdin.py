"""Lauren's Aladdin report (1.18.98, 2026-11-14, kids, the AI helper, made on 1.18.94). The
four "hell"s muted were all the Genie saying "Al" ("Al, you won", "Al, you little genius",
"Al, you're not gonna find another girl", "Me, too, Al"): the subtitles there say "Al", but
"hell" and "Al" don't sound alike enough for `sounds_alike`, and "Al," starting a sentence
wasn't taken for a name. A word the subtitles write as a name mid-sentence somewhere is a name
wherever they write it."""
import unittest

import support  # noqa: F401  (sets up the sandbox first)
import cvcore as cl
import cleanview as engine


def check(cue_texts, heard):
    """Mutes for every listed word heard, run past the subtitles as analyze does."""
    cues = [{"s": i * 3.0, "e": i * 3.0 + 2.5, "text": t} for i, t in enumerate(cue_texts)]
    sw, sw_cue = [], []
    for ci, c in enumerate(cues):
        for w in engine.spoken_words(c["text"]):
            if cl.norm(w):
                sw.append(w)
                sw_cue.append(ci)
    sn = [cl.norm(w) for w in sw]
    asr_n = [cl.norm(w) for w in heard.split()]
    mutes = [{"src": "audio", "at": i, "cat": cat, "raw": " ".join(asr_n[i:j])}
             for i, j, cat in cl.find_language(asr_n, list(cl.CATS))]
    names = {k for k in range(len(sw)) if engine.name_in_subtitles(sw, sw_cue, cues, k)}
    engine.subtitle_word_there(mutes, cl.align(sn, asr_n), sw, sn, asr_n, names)
    return mutes


class AlNotHell(unittest.TestCase):
    def test_al_heard_as_hell(self):
        mutes = check(["Al, you won. Because of you.", "Me, too, Al."],
                      "hell you won because of you me too hell")
        self.assertEqual(len(mutes), 2)
        for m in mutes:
            self.assertTrue(m.get("keep"), m)          # offered unticked: misheard
            self.assertEqual(cl.norm(m["sub"]), "al")

    def test_a_real_hell_still_muted(self):
        for cue, heard in ((["What the hell is that?"], "what the hell is that"),
                           (["Go to hell, Al."], "go to hell al"),
                           (["Al, what the hell?"], "al what the hell")):
            mutes = check(cue, heard)
            self.assertTrue(mutes, cue)
            self.assertFalse(any(m.get("keep") for m in mutes), cue)

    def test_an_ordinary_word_only_noted(self):
        mutes = check(["Yes, we won. Thank you, Al."], "hell we won thank you al")
        self.assertEqual(len(mutes), 1)
        self.assertEqual(cl.norm(mutes[0]["sub"]), "yes")
        self.assertFalse(mutes[0].get("keep"))


class Taught(unittest.TestCase):
    """Her "teach but leave only for kid setting not teen": muted for Kids (and so Young
    kids), not Teens or Adults, each only with its filter."""
    LINES = {"It's not every day you see a horse with two rear ends.": "crude",
             "You were born a street rat, you'll die a street rat, and only your fleas will "
             "mourn you.": "bullying"}

    def test_kids_only(self):
        import cleanview_learn as learn
        for text, kind in self.LINES.items():
            line = learn.norm(text)
            for key in ("_movies@kids", "_movies@young"):
                muted = learn._sh(key, "muted")
                self.assertIn(line, muted, key)
                self.assertIn(line, learn._for_filters(key, muted, {kind}), key)
                self.assertNotIn(line, learn._for_filters(key, muted, {"sexref"}), key)
            for key in ("_movies@teens", "_movies@adults", "_movies"):
                self.assertNotIn(line, learn._sh(key, "muted"), key)


if __name__ == "__main__":
    unittest.main()
