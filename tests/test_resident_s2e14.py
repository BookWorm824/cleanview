"""The Resident S2E14, Stupid Things in the Name of Sex (1.18.176, 2026-11-27, adults, Claude,
made on 1.18.158; the owner: "also did not get all innuendos"). Went through: the "VD" jokes
for Valentine's Day, the naughty candy hearts, "Think of England." (offered, unticked), and the
"technical malfunction" of Chet's car. "think of England" and "VD" are on the sexual list for
every show; the rest is taught for the-resident, each matching only its own line in the
159,785 past lines here."""
import json
import unittest
from pathlib import Path

import support  # noqa: F401  (must come first)
import cleanview as engine
import cleanview_learn as learn

SHARED = json.loads((Path(engine.__file__).parent / "shared_learned.json").read_text("utf8"))


class Episode14(unittest.TestCase):
    def test_on_the_list(self):
        sx = engine.LINE_WORDS["sexref"]
        for t, w in (("Think of England. What?", "Think of England"),
                     ("Just lie back and think of England.", "lie back and think of England"),
                     ("Happy VD, boss-man.", "VD"),
                     ('of spending "VD" with a scalpel in my hand,', "VD")):
            self.assertEqual([m.group(0) for m in sx.finditer(t)], [w], t)
        for t in ("a DVD player", "the VDOT office", "England is lovely in May",
                  "We flew back to England."):
            self.assertEqual(list(sx.finditer(t)), [], t)

    def test_taught_for_the_show(self):
        sh = SHARED["shows"]["the-resident"]
        for t in ('"Wink, wink." High literature indeed.', "I ordered some special ones online.",
                  "Um, I think HR would discourage me from reading these out loud.",
                  'of spending "VD" with a scalpel in my hand,',
                  "Well, to be fair, you did have a slight technical malfunction",
                  "when you hit the emergency brake."):
            self.assertEqual(sh["muted_for"].get(learn.norm(t)), "sexref", t)


if __name__ == "__main__":
    unittest.main()
