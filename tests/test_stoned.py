""""stoned" is drug talk, the Drugs section's "Drug talk and slang" box (1.18.137; the owner,
in the CleanStream chat: "Yes, add it everywhere"). Just the word is muted, as for the other short lists; a stoning
(Bible stories, history) or pitted fruit is left alone. No AI reads for it: the Drug use box is
a picture filter."""
import unittest

import support  # noqa: F401  (must come first)
import cleanview as engine

DRUGS = engine.LINE_WORDS["drugtalk"]


def opts(**on):
    o = engine.full_opts(on)
    for k in engine.LINE_KINDS:
        o[k] = on.get(k, False)
    return o


class Stoned(unittest.TestCase):
    def test_high(self):
        for line in ("He was stoned.", "We got so stoned last night.", "You look stoned, man.",
                     "Are you stoned right now?"):
            self.assertIsNotNone(DRUGS.search(line), line)

    def test_a_stoning_or_fruit(self):
        for line in ("They stoned him at the gate.", "Stephen was stoned to death.",
                     "He shall surely be stoned.", "The prophets were stoned by the people.",
                     "a jar of stoned olives", "They stoned the house with rocks."):
            self.assertIsNone(DRUGS.search(line), line)

    def test_just_the_word_with_drug_talk_ticked(self):
        lines = [{"s": 1.0, "e": 2.0, "text": "He was stoned."},
                 {"s": 3.0, "e": 4.0, "text": "Stephen was stoned to death."}]
        out, how = engine.find_lines(lines, opts(drugtalk=True), False)
        self.assertEqual([(l["idx"], l["types"], l.get("words")) for l in out],
                         [(0, ["drugtalk"], ["stoned"])])
        self.assertEqual(engine.LINE_LABEL["drugtalk"], "Drug talk")

    def test_not_with_drug_talk_off(self):
        lines = [{"s": 1.0, "e": 2.0, "text": "He was stoned."}]
        self.assertEqual(engine.find_lines(lines, opts(drugtalk=False), False)[0], [])

    def test_with_other_filters_too(self):
        lines = [{"s": 1.0, "e": 2.0, "text": "He was stoned."},
                 {"s": 3.0, "e": 4.0, "text": "They had sex."}]
        out, _ = engine.find_lines(lines, opts(drugtalk=True, sexref=True), False)
        self.assertEqual(sorted(t for l in out for t in l["types"]), ["drugtalk", "sexref"])

    def test_percocet_and_roofies(self):
        # the owner, in the Play chat: "out these under drugs", "perkaset", "roofie", "roofies"
        for line in ("He popped a Percocet.", "She was roofied at the bar.",
                     "Someone slipped her a roofie.", "Roofies...date rape drug."):
            self.assertIsNotNone(DRUGS.search(line), line)
        self.assertIsNone(DRUGS.search("They were roofing the house."))

    def test_percocet_only_misused(self):
        # her answer, relayed by the Play chat: "only misusing"
        for line in ("He's been popping Percocets all week.", "She got hooked on Percocet.",
                     "He was selling perkasets out of his car.", "You high on Percocet?",
                     "He bought some Percocet off the street."):
            self.assertIsNotNone(DRUGS.search(line), line)
        for line in ("The doctor prescribed Percocet after the surgery.",
                     "Take one Percocet every six hours for the pain.",
                     "Her prescription for Percocet is at the pharmacy.", "Percocet, 5 mg."):
            self.assertIsNone(DRUGS.search(line), line)

    def test_no_ai_asked(self):
        self.assertNotIn("drugtalk", engine.LINE_KINDS)
        self.assertIn("drugtalk", engine.LIST_ONLY_KINDS)


if __name__ == "__main__":
    unittest.main()
