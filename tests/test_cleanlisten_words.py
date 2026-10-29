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
    "orgasm"}
CV_ONLY = {"thank god", "thank the lord", "praise the lord"}   # CleanView mutes these as God's name (an AI can
#                         rule them sincere); CleanListen leaves them to its strict religion filter

# Things CleanView has that CleanListen still needs. When one is fixed there, the test
# says so: take it off this list.
# (Empty: CleanListen took CleanView 1.17.0-1.17.1's words, 2026-10-29.)
WAITING_ON_CLEANLISTEN = {   # CleanView 1.17.6 'suck', sent 2026-10-29
    'He sucks at math', 'It sucks the juice out', 'Life sucks', 'Suck', 'That really sucks',
    'That sucked', 'What a sucky day', 'You sucker!', 'sucked', 'sucks', 'sucky', 'you sucker'}


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


def explained(words, cv_spans, cl_spans):
    """True if the only differences are the ones made on purpose."""
    a = {k for i, j, _ in cv_spans for k in range(i, j)}
    b = {k for i, j, _ in cl_spans for k in range(i, j)}
    extra_cl = [(i, j) for i, j, cat in cl_spans if not set(range(i, j)) <= a]
    extra_cv = [(i, j) for i, j, cat in cv_spans if not set(range(i, j)) <= b]
    for i, j in extra_cl:
        if " ".join(words[i:j]) not in CL_ONLY_SEXUAL:
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
