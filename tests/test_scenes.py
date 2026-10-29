"""How picture finds become scenes: the local AI's "can't see clearly" check
(cleanview_ai.second_look) and merging scenes (cleanview.merge_scenes)."""
import unittest

import support  # noqa: F401  (sets up the sandbox first)
import cleanview as engine
import cleanview_ai as ai

SETTINGS = {"violence": True, "disturbing": True, "graphic": True, "gore": True,
            "kiss_os": "all", "kiss_ss": "all", "sex": True, "samesex": True, "oppsex": True}


def look(cat, *answers):
    """second_look on one candidate per answer, with the local AI's answers made up."""
    it = iter(answers)
    saved, ai.chat = ai.chat, lambda *a, **k: next(it)
    try:
        cands = [{"cat": cat, "s": 10.0 * n, "e": 10.0 * n + 5} for n in range(len(answers))]
        ai.second_look(cands, lambda c: ["a frame"])
        return cands
    finally:
        ai.chat = saved


class NudityCheck(unittest.TestCase):
    """The AI on this PC's closer look at nudity. Up to 1.14.2 analyze() built this list
    under the same name as the picture AI's finds, so an episode with possible nudity
    crashed with KeyError: 'nudity' (The Resident S01E07) and lost its other finds."""

    nude = [{"s": 10.0 * n, "e": 10.0 * n + 5, "kind": ["Nudity"], "why": "skin seen",
             "sure": True} for n in range(4)]

    def check(self, implied=True):
        verdicts = [{"level": "shown", "what": "bare back and bottom"},
                    {"level": "implied", "what": "under a sheet"},
                    {"level": "none"}, {"error": "model not running"}]

        def look(checks):
            self.assertEqual([c["cat"] for c in checks], ["nudity"] * 4)
            for c, v in zip(checks, verdicts):
                c["verdict"] = v
        notes = []
        kept = engine.check_nudity(self.nude, engine.full_opts({"nudity": True,
                                                                "implied": implied}),
                                   look, notes)
        return kept, notes

    def test_shown_implied_and_false_alarms(self):
        kept, notes = self.check()
        self.assertEqual([k["kind"] for k in kept], [["Nudity"], ["Implied nudity"], ["Nudity"]])
        self.assertIn("bare back and bottom", kept[0]["why"])
        self.assertIn("1 false alarm(s) dropped, 1 scene(s) only implied nudity", notes[0])

    def test_implied_dropped_when_not_ticked(self):
        kept, notes = self.check(implied=False)
        self.assertEqual(len(kept), 2, "shown, and the one that couldn't be checked")
        self.assertIn("implied nudity isn't ticked", notes[0])

    def test_picture_ai_finds_are_never_replaced(self):
        import ast
        import inspect
        tree = ast.parse(inspect.getsource(engine.analyze))
        made = [n for n in ast.walk(tree) if isinstance(n, ast.Assign)
                for t in n.targets if isinstance(t, ast.Name) and t.id == "cands"]
        self.assertEqual(len(made), 2, "only the picture AI's own two (empty, then found)")

    def test_picture_scenes_skip_nothing_known(self):
        cands = [{"cat": "fight", "s": 1.0, "e": 5.0, "verdict": {"keep": True, "level": "fight"}}]
        scenes = engine.decide_picture_scenes(cands, engine.full_opts(SETTINGS), True)
        self.assertEqual(scenes[0]["kind"], ["Violence"])


class UnclearCheck(unittest.TestCase):

    def test_dark_things_in_the_picture_are_fine(self):
        for see in ("A woman with dark hair kisses a man passionately",
                    "Two men in dark suits are punching each other",
                    "A man is shot in a dark parking garage; blood on the ground",
                    "A woman who can't get away"):
            with self.subTest(see=see):
                self.assertIsNone(ai.UNCLEAR.search(see))

    def test_frames_that_really_are_unclear(self):
        for see in ("The frames are too dark to see anything", "The image is blurry",
                    "It is hard to tell what is happening", "The picture is very dark"):
            with self.subTest(see=see):
                self.assertIsNotNone(ai.UNCLEAR.search(see))

    def test_model_is_asked_whether_it_can_see(self):
        seen = {}

        def fake(prompt, images, schema, **k):
            seen.update(prompt=prompt, schema=schema)
            return {"see": "two bears wrestling", "violent": True, "kind": "combat", "clear": True}
        saved, ai.chat = ai.chat, fake
        try:
            ai.second_look([{"cat": "fight", "s": 0, "e": 5}], lambda c: ["a frame"])
        finally:
            ai.chat = saved
        self.assertIn("clear", seen["schema"]["required"])
        self.assertIn("\"clear\"", seen["prompt"])
        self.assertNotIn("clear", ai.LOOK["fight"][1]["required"], "the shared schema is untouched")

    def test_scenes(self):
        cands = look("fight",
                     {"see": "A man in a dark parking garage is punched", "violent": True,
                      "kind": "combat"},                                          # no "clear"
                     {"see": "Too dark", "violent": True, "kind": "combat", "clear": False},
                     {"see": "Two men talking", "violent": False, "kind": "none", "clear": True})
        scenes = engine.decide_picture_scenes(cands, SETTINGS, True)
        self.assertEqual(len(scenes), 2, "the real false alarm is still dropped")
        self.assertTrue(scenes[0]["sure"], "a fight in a dark garage is kept, ticked")
        self.assertFalse(scenes[1]["sure"], "a too-dark one is offered unticked, not thrown away")
        self.assertIn("hard to see", scenes[1]["why"])


class MergeScenes(unittest.TestCase):

    def merged(self, *sure):
        return engine.merge_scenes([{"s": 10.0 * n, "e": 10.0 * n + 9, "kind": ["Violence"],
                                     "why": "", "sure": s} for n, s in enumerate(sure)])

    def test_one_sure_part_keeps_it_ticked(self):
        self.assertTrue(self.merged(True, False)[0]["sure"])
        self.assertTrue(self.merged(False, True)[0]["sure"])

    def test_all_unsure_stays_unsure(self):
        self.assertFalse(self.merged(False, False)[0]["sure"])

    def test_merges_into_one(self):
        m = self.merged(True, False, True)
        self.assertEqual((len(m), m[0]["s"], m[0]["e"]), (1, 0.0, 29.0))


class SexScenesFromSubtitles(unittest.TestCase):
    """[panting] and [moaning] are also running, fear and pain (The Resident: a woman
    fleeing, a patient held down, a scared boy were cut as sex scenes)."""

    def scenes(self, tag, skin=()):
        cues = [{"s": 100.0, "e": 102.0, "text": f"[{tag}]"}]
        return engine.sex_scenes(None, cues, [], [], list(skin), [])

    def test_clear_descriptions_count(self):
        for tag in ("sexual moaning", "bed creaking", "orgasmic cry", "making love"):
            with self.subTest(tag=tag):
                self.assertEqual(len(self.scenes(tag)), 1)

    def test_panting_and_moaning_need_bare_skin(self):
        for tag in ("panting", "moaning", "both panting"):
            with self.subTest(tag=tag):
                self.assertEqual(self.scenes(tag), [])
                self.assertEqual(len(self.scenes(tag, skin=[104.0])), 1)

    def test_pain_and_fear_never(self):
        for tag in ("moaning in pain", "panting, running", "groaning", "scared panting"):
            with self.subTest(tag=tag):
                self.assertEqual(self.scenes(tag, skin=[101.0]), [])


class SexTalk(unittest.TestCase):
    """The dialogue scorer for sex scenes (Pride and Prejudice: three polite "it's a
    pleasure" made a sex scene)."""

    def test_polite_and_gender_uses_dont_count(self):
        words = "it is a pleasure such a pleasure my pleasure the fair sex your sex".split()
        self.assertEqual(engine.cl.sex_score(words), 0)

    def test_explicit_talk_still_does(self):
        self.assertGreater(engine.cl.sex_score("naked sex pleasure".split()), 0)


class OneCloserLook(unittest.TestCase):
    """With Claude looking at the picture, the AI on this PC doesn't take a closer look at
    the same scenes first ("taking a closer look" seemed to run twice, as slowly: Jason)."""

    def test_only_one_closer_look(self):
        claude = engine.full_opts({"reader": "claude", "look": True})
        self.assertEqual(engine.closer_looks(claude, True, True), (False, True))
        local = engine.full_opts({"reader": "local"})
        self.assertEqual(engine.closer_looks(local, True, True), (True, False))
        no_pictures = engine.full_opts({"reader": "claude", "look": False})
        self.assertEqual(engine.closer_looks(no_pictures, True, True), (True, False))
        self.assertEqual(engine.closer_looks(local, False, True), (False, False))

    def test_unchecked_scenes_start_unticked(self):
        cands = [{"cat": "smoking", "s": 10.0, "e": 15.0}]
        scenes = engine.decide_picture_scenes(cands, engine.full_opts({"smoking": True}), True)
        self.assertEqual(len(scenes), 1)
        self.assertFalse(scenes[0].get("sure", True))


if __name__ == "__main__":
    unittest.main()
