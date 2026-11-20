"""The Shawshank Redemption on Adults (1.18.116; a report from another PC, adults, made on
1.18.113; the owner: "Lines, not the scene"). The tester's lessons for the film (1.18.27) were under
Teens, which Adults doesn't use, so Bogs' threat and the rest went through; they're taught for
every age now, each only with its filter ticked."""
import unittest

import support  # noqa: F401  (must come first)
import cleanview_learn as learn

SEXREF = ["Now... I'm gonna open my fly...",
          "and you're gonna swallow what I give you to swallow.",
          "Then you're gonna swallow Rooster's.",
          "Anything you put in my mouth, you're gonna lose.",
          "Bogs didn't put anything in Andy's mouth...",
          "Playing cards with naked ladies on them. You name it.",
          "The Sisters have taken quite a liking to you.",
          "And when it comes back... Clean as a virgin's honey pot, huh?",
          "in early 1947, for murdering his wife and the fella she was banging."]
CASUAL = ["He caught his wife in bed with some golf pro."]
FINE = ["You broke his nose, he ought to have something to show for it.",
        "Rita Hayworth herself.", "Bogs spent a week in the hole.",
        "My wife used to say I'm a hard man to know."]


def found(key, on):
    dialogue = [{"s": i * 3.0, "e": i * 3.0 + 2, "text": t}
                for i, t in enumerate(SEXREF + CASUAL + FINE)]
    added, _ = learn.apply(key, dialogue, [], [], [], on=on)
    return [a["text"] for a in added]


class Shawshank(unittest.TestCase):
    def test_adults_with_the_filters(self):
        self.assertEqual(found("_movies@adults", {"sexref", "casual"}), SEXREF + CASUAL)

    def test_every_age_below_too(self):
        for age in ("teens", "kids", "young"):
            got = found(f"_movies@{age}", {"sexref", "casual"})
            self.assertEqual([t for t in got if t in SEXREF + CASUAL], SEXREF + CASUAL, age)
            self.assertFalse(set(got) & set(FINE), age)

    def test_only_with_its_filter(self):
        self.assertEqual(found("_movies@adults", {"casual"}), CASUAL)
        self.assertEqual(found("_movies@adults", set()), [])


if __name__ == "__main__":
    unittest.main()
