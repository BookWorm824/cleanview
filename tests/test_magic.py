"""Dark magic (witchcraft, wizards, curses, the occult, fortune telling), magic (spells,
wands, potions, fairies), and vampires and werewolves: heard (lines muted, whole
conversations) and seen (scenes cut, by the AI on this PC and by Claude/ChatGPT). Ticked for
Young kids and Kids only."""
import unittest

import support  # noqa: F401  (sets up the sandbox first)
import cleanview as engine
import cleanview_ai as ai
import cleanview_claude as cc

MAGIC = ("darkmagic", "magic", "vampires")
ON = engine.full_opts(dict.fromkeys(MAGIC, True))


def dialogue(*texts, gap=3.0):
    return [{"s": k * gap, "e": k * gap + 2.0, "text": t} for k, t in enumerate(texts)]


def flagged(lines, opts=ON):
    out, _ = engine.find_lines(lines, opts, have_ai=False)
    return {l["idx"]: [t for t in l["types"] if t in MAGIC] for l in out}


class Heard(unittest.TestCase):

    def test_off_unless_ticked(self):
        for k in MAGIC:
            self.assertFalse(engine.DEFAULTS[k])
        self.assertEqual(flagged(dialogue("The wizard cast a spell."), engine.full_opts()), {})

    def test_found_without_any_ai(self):
        for text, kind in [("That's witchcraft!", "darkmagic"),
                           ("She put a curse on the village.", "darkmagic"),
                           ("Get out the Ouija board.", "darkmagic"),
                           ("The fortune teller read my palm.", "darkmagic"),
                           ("He'll summon the dead.", "darkmagic"),
                           ("The wizard is coming!", "darkmagic"),   # Lauren: dark magic
                           ("Wizards and sorcerers", "darkmagic"),
                           ("She cast a spell on the king.", "magic"),
                           ("A vampire bit him!", "vampires"),
                           ("Count Dracula's castle", "vampires"),
                           ("He turns into a werewolf at night.", "vampires"),
                           ("Beware the werewolves.", "vampires"),
                           ("Wave your magic wand.", "magic"),
                           ("Drink the potion.", "magic"),
                           ("Bibbidi-bobbidi-boo!", "magic"),
                           ("We need more Gummiberry juice.", "magic"),
                           ("The castle is enchanted.", "magic")]:
            with self.subTest(text=text):
                self.assertEqual(flagged(dialogue(text)), {0: [kind]})

    def test_everyday_words_left_alone(self):
        for text in ("It was pure magic.", "Say the magic word.", "How do you spell cat?",
                     "Curse this traffic!", "What am I, psychic?", "She's a wizard with numbers.",
                     "A hex key and some screws.", "Magic Johnson scored again.",
                     "The spirits were high.", "Vampire bats live in caves.",
                     "A wolf howled at the moon.", "The wolves ran by."):
            with self.subTest(text=text):
                self.assertEqual(flagged(dialogue(text)), {})

    def test_whole_conversation(self):
        lines = dialogue("Zummi, can you cast a spell?", "I'll try.", "Stand back!",
                         "Abracadabra!", "Now, lunch.")
        self.assertEqual(sorted(flagged(lines)), [0, 1, 2, 3])

    def test_every_reader_knows_them(self):
        for k in MAGIC:
            self.assertIn(k, ai.LINE_TYPES)
            self.assertIn(k, ai.LINE_NAMES)
            self.assertIn(k, cc.TYPE_TEXT)
            self.assertIn(k, engine.LINE_LABEL)
            self.assertIn(k, cc.WHOLE_LINE_TYPES)
            self.assertIn(k, engine.WHOLE_CONVERSATIONS)
        text = engine.wanted_text(ON, [])
        self.assertIn("witchcraft", text)
        self.assertIn("magic wands", text)
        self.assertIn("stage magic tricks", ai.LINE_TYPES["magic"])
        self.assertIn("werewolves", text)
        self.assertIn("wizards", ai.LINE_TYPES["darkmagic"])
        self.assertIn("wizards", cc.TYPE_TEXT["darkmagic"])


class Seen(unittest.TestCase):

    def test_picture_ai_looks_for_them_when_ticked(self):
        self.assertEqual([c for c in engine.needs(ON)["clip"] if c in MAGIC], list(MAGIC))
        self.assertEqual([c for c in engine.needs({})["clip"] if c in MAGIC], [])
        for k in MAGIC:
            self.assertIn(k, ai.CLIP_CATS)
            self.assertIn(k, ai.THRESH)
            self.assertIn(k, ai.MIN_FRAMES)
            self.assertIn(k, ai.LOOK)
            self.assertIn(k, engine.CAT_LABEL)

    def test_double_checked_by_the_ai_on_this_pc(self):
        cands = [{"cat": "magic", "s": 10, "e": 14}, {"cat": "darkmagic", "s": 40, "e": 44},
                 {"cat": "magic", "s": 60, "e": 64}]
        answers = iter([{"see": "A wizard waves a glowing wand", "yes": True, "clear": True},
                        {"see": "A witch stirs a cauldron and chants a curse", "yes": True,
                         "clear": True},
                        {"see": "A magician pulls a rabbit from a hat", "yes": False,
                         "clear": True}])
        saved, ai.chat = ai.chat, lambda *a, **k: next(answers)
        try:
            ai.second_look(cands, lambda c: ["a frame"])
        finally:
            ai.chat = saved
        scenes = engine.decide_picture_scenes(cands, ON, True)
        self.assertEqual([(s["kind"], s["s"]) for s in scenes],
                         [(["Magic"], 10), (["Dark magic"], 40)])

    def test_claude_looks_for_them_when_ticked(self):
        text = engine.picture_wanted(ON)
        self.assertIn("dark magic (", text)
        self.assertIn("magic (", text)
        self.assertIn("dark magic", cc.PIC_KINDS)
        self.assertIn("magic", cc.PIC_KINDS)
        self.assertIn("vampires", cc.PIC_KINDS)
        self.assertIn("werewolf", text)
        self.assertEqual(engine._pic_wanted({"what": "vampires"}, ON), "Vampires and werewolves")
        self.assertIsNone(engine._pic_wanted({"what": "vampires"}, engine.full_opts()))
        self.assertEqual(engine._pic_wanted({"what": "dark magic"}, ON), "Dark magic")
        self.assertEqual(engine._pic_wanted({"what": "magic"}, ON), "Magic")
        self.assertIsNone(engine._pic_wanted({"what": "dark magic"}, engine.full_opts()))
        self.assertIsNone(engine._pic_wanted({"what": "magic"}, engine.full_opts()))
        self.assertNotIn("dark magic", engine.picture_wanted(engine.full_opts()))


class WholeLines(unittest.TestCase):
    """Claude's review never narrows a magic line down to one word."""

    def test_review(self):
        st = support.sample_review()
        st["lines"][0]["types"] = ["magic"]
        saved = cc.ask
        cc.ask = lambda *a, **k: ({
            "decisions": [{"id": "L1", "decision": "just the word", "word": "spell",
                           "why": "mentions a spell"}],
            "missed_lines": [], "missed_scenes": [], "summary": ""}, None)
        try:
            items, decisions, missed, _, _ = cc.review(st, "- magic")
        finally:
            cc.ask = saved
        self.assertEqual(decisions["L1"][0], "remove")


if __name__ == "__main__":
    unittest.main()
