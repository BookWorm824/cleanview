"""The owner's Christy pilot report (1.18.133, 2026-11-18, adults, the AI helper, made on 1.18.129;
the owner: "Yes, fix them"). Creed's pet raccoon was muted as a slur, "regardless of sex" (boys
and girls) as sexual, and Miss Alice's "Thank God and seek faith." as God's name; "God, it's
just the way things is." went through (no subtitles lined up); "Christy - Pilot" was looked up
as a movie."""
import unittest

import support  # noqa: F401  (must come first)
import cvcore as cl
import cleanview as engine


def listed(text):
    words = [cl.norm(t) for t in text.split()]
    return cl.find_language(words, list(cl.CATS), [])


class TheRaccoon(unittest.TestCase):
    def test_scalawag(self):
        self.assertEqual(listed("Coons wash every natural blessed thing before they eat it."), [])
        self.assertEqual(listed(
            "Sleeps with me every night. Oh, he be clean. They be the best pets. Creed, we have "
            "to have a talk about Scalawag in school. You see, he is such a specially fine coon "
            "that I'm afraid the others will watch him and not do their lessons."), [])
        self.assertEqual(listed("We treed a coon down by the creek."), [])

    def test_still_the_slur(self):
        self.assertTrue(listed("Coons are trying to get into school."))     # Forest Gump
        self.assertTrue(listed("Get away from my pets, you coon."))
        self.assertTrue(listed("That dirty coon took the job."))


class BoysAndGirls(unittest.TestCase):
    def test_regardless_of_sex(self):
        sexref = engine.LINE_WORDS["sexref"]
        for line in ("I have to see each grade together regardless of sex.",
                     "Children of either sex", "sorted by age and sex", "sex and age"):
            self.assertIsNone(sexref.search(line), line)
        self.assertIsNotNone(sexref.search("They had sex."))


class Prayer(unittest.TestCase):
    def test_thank_god_and_seek_faith(self):
        self.assertEqual(listed("Thank God and seek faith."), [])
        self.assertEqual(listed("Thank the Lord and pray for rain."), [])
        self.assertTrue(listed("Thank God you're here."))
        self.assertTrue(listed("Oh, thank God and the Marines."))


class HeardGod(unittest.TestCase):
    def heard(self, text, gap_at=None):
        asr, t = [], 0.0
        for k, w in enumerate(text.split()):
            if gap_at is not None and k == gap_at:
                t += 2.0
            asr.append({"t": w, "s": t, "e": t + 0.3, "n": cl.norm(w)})
            t += 0.4
        return asr

    def test_a_lone_god_said_as_an_oath(self):
        asr = self.heard("No, it's like the feuding, Miss Christie. God, it's just the way "
                         "things is.")
        got = engine.heard_bare_god(asr, [])
        self.assertEqual([m["raw"] for m in got], ["god"])
        self.assertEqual(got[0]["cat"], "deity")
        self.assertEqual(got[0]["src"], "audio")

    def test_not_prayer_or_phrases(self):
        for text in ("God, please help us.", "Thank God.", "I believe in God.",
                     "Oh, God.", "God bless you."):
            self.assertEqual(engine.heard_bare_god(self.heard(text), []), [], text)

    def test_not_twice(self):
        asr = self.heard("God, I hate waiting.")
        self.assertEqual(engine.heard_bare_god(asr, [{"at": 0}]), [])


class ThePilot(unittest.TestCase):
    def test_pilot_is_season_1_episode_1(self):
        self.assertEqual(engine.guess_title("Christy - Pilot.m4v"), ("Christy", 1, 1))
        self.assertEqual(engine.guess_title("Lost - Pilot (Part 1).mkv"), ("Lost", 1, 1))

    def test_not_a_pilot(self):
        self.assertEqual(engine.guess_title("Top Gun - Pilot's Cut.mp4")[1], None)
        self.assertEqual(engine.guess_title("The Pilot.mp4")[1], None)


if __name__ == "__main__":
    unittest.main()
