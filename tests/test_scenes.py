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


if __name__ == "__main__":
    unittest.main()
