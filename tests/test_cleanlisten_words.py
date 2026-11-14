"""CleanView, CleanListen and CleanRead mute the same words. CleanRead uses CleanListen's word
lists (`import cleanlisten`), and CleanView has its own copy (cvcore.py), so this runs every
quoted phrase in both repos' tests through both and lists where they differ. A new word,
phrase or guard in one has to go into the other too (see CLAUDE.md).

Needs the CleanListen repo next to this one (Downloads\\cleanlisten, or CLEANLISTEN_REPO);
skips without it. Both get CleanView's normalised words, so this checks the lists, not
reading the text (CleanListen reads bleeped words differently: see WAITING_ON_CLEANLISTEN)."""
import importlib.util
import os
import re
import unittest
from pathlib import Path

import support
import cvcore as cv

CL_REPO = Path(os.environ.get("CLEANLISTEN_REPO") or support.ROOT.parents[1] / "cleanlisten")

# Different on purpose, and why.
SLANG_WORDS = {"stones", "balls", "nuts", "pair", "set", "cojones", "cajones", "cahones", "jewels",
               # fruit and vegetables for body parts ("check out those melons")
               "melons", "cantaloupes", "watermelons", "grapefruits", "coconuts", "honeydews",
               "cherry", "grapes", "plums", "berries", "beans", "walnuts", "franks", "frank",
               "veg", "banana", "cucumber", "zucchini", "eggplant", "carrot", "pickle", "peach",
               "buns",
               # other slang for body parts ("check out those jugs", "kicked in the junk")
               "jugs", "hooters", "knockers", "bazongas", "bazooms", "bazoombas", "rack",
               "cock", "cocks", "junk", "package", "crown"}
CL_ONLY_SEXUAL = {     # CleanListen mutes these words; CleanView removes such talk as lines
    "sex", "sexual", "porn", "made love", "one night stand", "slept with her", "arousal",
    "orgasm", "thanks for the quickie", "penis", "penises", "private parts",
    "sexy",            # in LINE_WORDS["sexref"] here (CleanListen 1.17.22's tests have it)
    # a person, not the tool (the owner, 2026-11-13): LINE_WORDS["sexref"] here, with the
    # same guard (cleanview.stripper_tool)
    "stripper", "strippers", "stripper's",
    # "pole" right after "stripper" (the owner, 2026-11-13): LINE_WORDS["sexref"] here
    "stripper pole", "stripper poles", "stripper's pole", "stripper's poles", "strippers pole",
    "strippers poles",
    # the owner's hard rule (2026-11-13): always removed. Here they're line-list words
    # (LINE_WORDS "crude" and "sexref", hard_rule_words), not cvcore words
    "fart", "farts", "farted", "farting", "condom", "condoms", "semen",
    # explicit detail in findings (the owner, 2026-11-13): CleanListen mutes these words;
    # here they make the whole line a sexual reference (cleanview.EXPLICIT_FINDING, TEARING)
    "vaginal", "vaginally", "anal", "anally", "penile", "hymen", "labia", "vulva", "sodomy",
    "sodomize", "sodomized", "sodomise", "sodomised", "tearing", "forced penetration",
    "signs of penetration", "evidence of penetration", "penetration",
    "bondage", "safe word", "safe words", "safeword", "safewords",
    # CleanView 1.18.69 has these in LINE_WORDS["sexref"] (just the words, in lines), not cvcore
    "skinny dip", "skinny dips", "skinny dipped", "skinny dipping", "skinny-dip",
    "skinny-dips", "skinny-dipped", "skinny-dipping", "skinnydip", "skinnydipping",
    "chastity belt", "chastity belts", "naked photo", "naked photos", "naked picture",
    "naked pictures", "naked pic", "naked pics", "naked selfie", "naked selfies"}
CV_ONLY = {"thank god", "thank the lord", "praise the lord"}   # CleanView mutes these as God's name (an AI can
#                         rule them sincere); CleanListen leaves them to its strict religion filter

# Things CleanView has that CleanListen still needs. When one is fixed there, the test
# says so: take it off this list.
# (Empty: CleanListen 1.13.1 has CleanView 1.18.10's words, 2026-11-03.)
# CleanListen 1.13.5 has CleanView 1.18.11's words (dickens, Camp Dick, sod, God knows best...)
# CleanListen 1.14.2 has CleanView 1.18.13's prayer guards (Wings of a Dream)
# CleanListen 1.17.7 has CleanView 1.18.30-1.18.39's words (West Side Story slurs, nympho,
# private parts, bondage, safe word), 2026-11-09
# (the short list of Spanish swear words on the English lists, 1.18.86, waited here until
# CleanListen 1.17.32 had it, the same day)
# CleanView 1.18.93's "blasted" / "blast it" (the owner, 2026-11-14): built in CleanListen,
# to be released there as 1.17.37
WAITING_ON_CLEANLISTEN = {"Blast and damnation", "Blast it, the horse has thrown a shoe",
                          "Get that blasted dog out of my kitchen", "lather and blasted brat"}


def load_cleanlisten():
    spec = importlib.util.spec_from_file_location("cleanlisten_for_test",
                                                  CL_REPO / "cleanlisten.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def phrases():
    out = set()
    for f in [support.ROOT / "tests" / "test_words.py", *sorted((CL_REPO / "tests").glob("test_*.py"))]:
        out |= set(re.findall(r'"([^"\\\n]{2,80})"', f.read_text(encoding="utf8")))
    return sorted(out)


def in_line_list(words):
    """The words CleanView's short line list (LINE_WORDS, sexual references and sleeping
    around) finds in this sentence: CleanListen mutes such talk as words, CleanView in lines
    (1.18.95: "sleeping with her", "his lover", "sexiest"; CleanListen 1.17.37 has them in
    SEXUAL_PHRASES)."""
    import cleanview as engine
    text = " ".join(words)
    starts = [m.start() for m in re.finditer(r"\S+", text)]
    out = set()
    for k in ("sexref", "casual"):
        for m in engine.LINE_WORDS[k].finditer(text):
            out |= {n for n, s in enumerate(starts) if m.start() <= s < m.end()}
    return out


def explained(words, cv_spans, cl_spans):
    """True if the only differences are the ones made on purpose."""
    a = {k for i, j, _ in cv_spans for k in range(i, j)}
    b = {k for i, j, _ in cl_spans for k in range(i, j)}
    extra_cl = [(i, j) for i, j, cat in cl_spans if not set(range(i, j)) <= a]
    extra_cv = [(i, j) for i, j, cat in cv_spans if not set(range(i, j)) <= b]
    lines = in_line_list(words) if extra_cl else set()
    for i, j in extra_cl:
        # CleanListen may mute a little more of the same talk ("slept with her best friend",
        # where the line list's hit is "slept with"): a hit inside its span explains it
        if " ".join(words[i:j]) not in CL_ONLY_SEXUAL and not set(range(i, j)) & lines:
            return False
    for i, j in extra_cv:
        cl_inside = {k for k in b if i <= k < j}
        if " ".join(words[i:j]) in CV_ONLY:
            continue
        # body slang: CleanView mutes the whole phrase, CleanListen just the slang word
        if cl_inside and all(words[k] in SLANG_WORDS for k in cl_inside):
            continue
        return False
    return True


class LineListExplains(unittest.TestCase):
    """CleanListen muting words that CleanView's line list finds is on purpose."""

    def spans(self, text, *found):
        words = [w for w in (cv.norm(t) for t in text.split()) if w]
        out = []
        for f in found:
            f = f.split()
            i = next(n for n in range(len(words)) if words[n:n + len(f)] == f)
            out.append((i, i + len(f), "sexual"))
        return words, out

    def test_explained(self):
        for text, cl in (("Fine. But I'm not sleeping with her.", "sleeping with her"),
                         ("He was one of my lovers.", "lovers"),
                         ("That is the sexiest thing", "sexiest"),
                         ("she's been sleeping with a married man", "with a married man"),
                         ("Whispers are he's sleeping with his intern.",
                          "sleeping with his intern"),
                         # CleanListen's span a little longer than the line list's hit
                         ("She slept with her best friend", "slept with her best friend"),
                         ("sleeping with their secretaries", "sleeping with their secretaries")):
            words, spans = self.spans(text, cl)
            self.assertTrue(explained(words, [], spans), text)

    def test_not_explained(self):
        words, spans = self.spans("she was sleeping with her teddy bear", "sleeping with her")
        self.assertFalse(explained(words, [], spans))
        words, spans = self.spans("a lover of fine wine", "lover")
        self.assertFalse(explained(words, [], spans))


@unittest.skipUnless((CL_REPO / "cleanlisten.py").exists(), "needs the CleanListen repo")
class SameWordsInEveryApp(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.cl = load_cleanlisten()

    def compare(self, text):
        words = [w for w in (cv.norm(t) for t in text.split()) if w]
        cv_spans = cv.find_language(words, [c for c in cv.CATS if c != "samesex"])
        cl_cats = list(self.cl.CATS) + list(getattr(self.cl, "KID_CATS", {}))
        cl_spans = self.cl.find_language(words, cl_cats, lead_in_too=True)
        return words, cv_spans, cl_spans

    def test_same_words_muted(self):
        differ, fixed = [], []
        for text in phrases():
            words, cv_spans, cl_spans = self.compare(text)
            ok = explained(words, cv_spans, cl_spans)
            if not ok and text not in WAITING_ON_CLEANLISTEN:
                differ.append(f"{text!r}: CleanView {[' '.join(words[i:j]) for i, j, _ in cv_spans]}"
                              f", CleanListen {[' '.join(words[i:j]) for i, j, _ in cl_spans]}")
            elif ok and text in WAITING_ON_CLEANLISTEN:
                fixed.append(text)
        self.assertEqual(differ, [], "add these to the other app (or list why they differ)")
        self.assertEqual(fixed, [], "CleanListen has these now: take them off "
                                    "WAITING_ON_CLEANLISTEN")


if __name__ == "__main__":
    unittest.main()
