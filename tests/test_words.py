"""Swear words getting through: words missing from the lists, swears bleeped in
subtitles ("f***ing"), phrases ("shut up", "screw you"), and a subtitle word
dropped because another word was muted close by."""
import unittest

import support  # noqa: F401  (sets up the sandbox first)
import cleanview as engine
import cvcore as cl

EVERY_GROUP = list(cl.CATS)


def found(text, cats=EVERY_GROUP):
    """The words of `text` that would be muted, with their list."""
    words = [cl.norm(w) for w in text.split()]
    words = [w for w in words if w]
    return [(" ".join(words[i:j]), cat) for i, j, cat in cl.find_language(words, cats)]


class MissingWords(unittest.TestCase):

    def test_now_found(self):
        for word, cat in [("goddammit", "mild"), ("godammit", "mild"), ("sonofabitch", "moderate"),
                          ("sonuvabitch", "moderate"), ("asshat", "moderate"),
                          ("asskicking", "moderate"), ("dangit", "minced"), ("omigod", "deity"),
                          ("ohmygod", "deity"), ("craphole", "mild"), ("bullcrap", "mild"),
                          ("goshdarn", "minced"), ("jeeze", "minced"), ("frick", "minced")]:
            with self.subTest(word=word):
                self.assertIn(cat, [c for _, c in found(word, [cat])])
                self.assertTrue(cl.listed_word(word))

    def test_with_punctuation_and_capitals(self):
        self.assertEqual(found("Goddammit, Castle!"), [("goddammit", "mild")])

    def test_innocent_words_still_left_alone(self):
        for text in ("a glass of water", "the class assistant", "hello shell", "scrap metal",
                     "Gruffi and Grammi", "a dangerous road"):
            with self.subTest(text=text):
                self.assertEqual(found(text), [])


class BleepedSubtitles(unittest.TestCase):

    def test_bleeps_read_as_the_word(self):
        for bleeped, word in [("f***", "fuck"), ("F***ing", "fucking"), ("f**king", "fucking"),
                              ("s**t", "shit"), ("s***", "shit"), ("bulls**t", "bullshit"),
                              ("a**hole", "asshole"), ("b****", "bitch"), ("d*mn", "damn"),
                              ("h***", "hell"), ("G*d", "god"), ("motherf***er", "motherfucker"),
                              ("f--k", "fuck"), ("#@$%", "fuck"), ("f***!", "fuck")]:
            with self.subTest(bleeped=bleeped):
                self.assertEqual(cl.norm(bleeped), word)

    def test_ordinary_text_untouched(self):
        for text, same in [("#1", "1"), ("x-ray", "xray"), ("well--", "well"), ("$5", "5"),
                           ("*", ""), ("hello", "hello"), ("Hey!", "hey")]:
            with self.subTest(text=text):
                self.assertEqual(cl.norm(text), same)

    def test_found_in_a_subtitle_line(self):
        self.assertEqual(found("What the f*** is that?", ["strong"]), [("what the fuck", "strong")])
        self.assertEqual(found("That's bulls**t.", ["moderate"]), [("bullshit", "moderate")])


class Phrases(unittest.TestCase):

    def test_ai_may_mute_phrases_on_the_lists(self):
        for phrase in ("shut up", "Shut up!", "screw you", "you suck", "shut your mouth",
                       "oh my god", "oh shut up"):
            with self.subTest(phrase=phrase):
                self.assertTrue(cl.listed_word(phrase))

    def test_names_and_ordinary_words_still_not_listed(self):
        for word in ("Grafi", "Gruffi", "nice day", "shut", "screw"):
            with self.subTest(word=word):
                self.assertFalse(cl.listed_word(word))

    def test_screw_you_is_mild_language(self):
        self.assertEqual(found("oh screw you", ["mild"]), [("screw you", "mild")])
        self.assertEqual(found("oh screw you", ["moderate"]), [("screw you", "moderate")])

    def test_not_rude_when_its_about_doing_something(self):
        for text, cats in [("shut it down now", ["rude"]), ("screw it in tightly", ["mild"]),
                           ("screw them on to the wall", ["mild"]), ("shut it off", ["rude"])]:
            with self.subTest(text=text):
                self.assertEqual(found(text, cats), [])

    def test_still_rude(self):
        self.assertEqual(found("just shut it", ["rude"]), [("shut it", "rude")])
        self.assertEqual(found("shut up", ["rude"]), [("shut up", "rude")])
        self.assertEqual(found("screw it let's go", ["mild"]), [("screw it", "mild")])


class FromCleanListen(unittest.TestCase):
    """Words and guards CleanListen had that CleanView didn't (tests/test_cleanlisten_words.py
    keeps the two in step)."""

    def test_caught(self):
        for text, phrase, cat in [
                ("He was jerking off.", "jerking off", "moderate"),
                ("Go rub one out.", "rub one out", "moderate"),
                ("Stop wanking.", "wanking", "moderate"), ("What a jerkoff.", "jerkoff", "moderate"),
                ("What the eff, man.", "what the eff", "moderate"),
                ("What the fudge!", "what the fudge", "minced"),
                ("It's cold enough to freeze my nuts off.", "freeze my nuts off", "moderate"),
                ("That took brass balls.", "brass balls", "moderate"),
                ("They found the body, cut his balls off.", "cut his balls off", "moderate"),
                ("She kicked him right in the nuts.", "kicked him right in the nuts", "moderate")]:
            with self.subTest(text=text):
                self.assertEqual(found(text, [cat]), [(phrase, cat)])

    def test_everyday_uses_left_alone(self):
        for text in ("He grew some stones in his kidney.", "She grew a pair of tomato plants.",
                     "He jerked off the road.", "He was deaf and dumb.", "a dumb waiter",
                     "It was a crash test dummy.", "Don't fool around.", "an April fool",
                     "She was shut up in the attic.", "Cigarette butts were everywhere.",
                     "He jerks the door open.", "Her damning evidence and his damnation."):
            with self.subTest(text=text):
                self.assertEqual(found(text), [])

    def test_still_rude_or_swearing(self):
        self.assertEqual(found("Shut up, you fool", ["rude"]), [("shut up", "rude"), ("fool", "rude")])
        self.assertEqual(found("damn it", ["mild"]), [("damn", "mild")])
        self.assertEqual(found("he's a jerk", ["rude"]), [("jerk", "rude")])


class FromCleanListenToo(unittest.TestCase):
    """Two false alarms CleanListen found in CleanView's lists."""

    def test_got_some_nuts_in_my_bag(self):
        for text in ("I've got some nuts in my bag.", "You got some stones for the garden?",
                     "She's got some balls from the gym"):
            with self.subTest(text=text):
                self.assertEqual(found(text), [])
        self.assertEqual(found("You've got some stones, kid", ["moderate"]),
                         [("you've got some stones", "moderate")])

    def test_stars_alone_arent_a_word(self):
        for token in ("***", "****", "$$$", "@@@", "* * *"):
            with self.subTest(token=token):
                self.assertEqual(cl.norm(token), "")
        self.assertEqual(cl.norm("#@$%"), "fuck", "a grawlix still is")
        self.assertEqual(cl.norm("f***ing"), "fucking")


class Retarded(unittest.TestCase):
    """"Retarded" was already muted; these other forms got through."""

    def test_every_form_muted(self):
        for text, word in [("you're so retarded", "retarded"), ("what a retard", "retard"),
                           ("bunch of retards", "retards"), ("hey retardo", "retardo"),
                           ("that's so retarted", "retarted"), ("he's a tard", "tard"),
                           ("stupid libtards", "libtards"),
                           ("that's re tarded", "re tarded")]:
            with self.subTest(text=text):
                self.assertEqual(found(text, ["moderate"]), [(word, "moderate")])

    def test_everyday_words_left_alone(self):
        for text in ("don't be tardy", "a pink leotard", "hot dog with mustard",
                     "vanilla custard", "fire retardant", "retard the spread",
                     "it slows the retardation of", "re the tax form"):
            with self.subTest(text=text):
                self.assertEqual(found(text), [])


class WhatThe(unittest.TestCase):
    """"What the ****": muting only the swear still says what it was, so "what the" goes too."""

    def test_lead_in_muted_with_the_swear(self):
        for text, cats, phrase, cat in [
                ("What the hell is that?", ["mild"], "what the hell", "mild"),
                ("What the f*** is that?", ["strong"], "what the fuck", "strong"),
                ("what the heck", ["minced"], "what the heck", "minced"),
                ("Who the hell are you", ["mild"], "who the hell", "mild"),
                ("Where the hell were you", ["mild"], "where the hell", "mild"),
                ("why the hell not", ["mild"], "why the hell", "mild"),
                ("How the hell did he", ["mild"], "how the hell", "mild"),
                ("What in the hell", ["mild"], "what in the hell", "mild")]:
            with self.subTest(text=text):
                self.assertEqual(found(text, cats), [(phrase, cat)])
        self.assertEqual(found("what the bloody hell", ["mild"]),        # all four words
                         [("what the bloody", "mild"), ("hell", "mild")])

    def test_only_with_a_swear(self):
        for text in ("What the doctor said", "who the man is", "what the heck",
                     "What in the world"):
            with self.subTest(text=text):
                self.assertEqual(found(text, ["mild"]), [])

    def test_other_swears_keep_their_own_words(self):
        self.assertEqual(found("get the hell out", ["mild"]), [("hell", "mild")])
        self.assertEqual(found("go to hell", ["mild"]), [("hell", "mild")])
        self.assertEqual(found("damn what the hell", ["mild"]),
                         [("damn", "mild"), ("what the hell", "mild")])

    def test_her_own_words_too(self):
        words = ["what", "the", "frak"]
        self.assertEqual(cl.find_language(words, [], mine=[("frak",)]), [(0, 3, "mine")])


class ChainAndSheesh(unittest.TestCase):
    """"Yanked your chain" is mild language; "sheesh" is a minced "Jesus"."""

    def test_chain_phrase_muted(self):
        for text, phrase in [("Relax, I yanked your chain", "yanked your chain"),
                             ("He's just yanking my chain.", "yanking my chain"),
                             ("Quit pulling her chain", "pulling her chain"),
                             ("she jerked his chain again", "jerked his chain")]:
            with self.subTest(text=text):
                self.assertEqual(found(text, ["mild"]), [(phrase, "mild")])
        self.assertEqual(found("I yanked your chain", ["moderate"]),
                         [("yanked your chain", "moderate")])

    def test_everyday_chains_left_alone(self):
        for text in ("Yank the chain to flush", "He pulled the chain on the light",
                     "my bike chain broke", "a chain of stores", "the dog's chain",
                     "yanked the door open"):
            with self.subTest(text=text):
                self.assertEqual(found(text), [])

    def test_sheesh(self):
        self.assertEqual(found("Sheesh, what a day", ["minced"]), [("sheesh", "minced")])
        self.assertTrue(cl.listed_word("sheesh"))
        self.assertTrue(cl.listed_word("yanking your chain"))
        self.assertFalse(cl.listed_word("chain"))


class SlangForPrivateParts(unittest.TestCase):
    """"Grow some stones": stones, balls and nuts are only slang in these phrases."""

    def test_whole_phrase_muted(self):
        for text, phrase in [("Grow some stones, Castle.", "grow some stones"),
                             ("You need to grow a pair.", "grow a pair"),
                             ("He finally grew some balls", "grew some balls"),
                             ("Nobody has the balls to say it", "has the balls to"),
                             ("She kicked him in the nuts", "kicked him in the nuts"),
                             ("You've got some stones, kid", "you've got some stones"),
                             ("That's ballsy", "ballsy"), ("Show some cojones", "cojones")]:
            with self.subTest(text=text):
                self.assertEqual(found(text, ["moderate"]), [(phrase, "moderate")])

    def test_everyday_stones_balls_and_nuts_left_alone(self):
        for text in ("I got some stones for the garden", "Grab the tennis balls",
                     "a bag of mixed nuts", "Kidney stones hurt", "We grow some tomatoes",
                     "the stones in the wall", "He's nuts", "Rolling Stones concert",
                     "a pair of shoes", "grow up"):
            with self.subTest(text=text):
                self.assertEqual(found(text), [])

    def test_ai_may_mute_the_phrase_but_not_the_plain_word(self):
        self.assertTrue(cl.listed_word("grow some stones"))
        self.assertFalse(cl.listed_word("stones"))

    def test_reviewer_is_told(self):
        self.assertIn("grow some stones", engine.wanted_text({}, ["swearing"]))


class MoreOfTheSame(unittest.TestCase):
    """Words and phrases like the ones already on the lists (2026-10-28 review)."""

    def test_minced_oaths(self):
        for text, phrase in [("Golly, that's big", "golly"), ("Jeepers!", "jeepers"),
                             ("Crikey, mate", "crikey"), ("Blimey", "blimey"),
                             ("Cripes almighty", "cripes"), ("Well, doggone it", "doggone"),
                             ("Tarnation!", "tarnation"), ("Oh, crud.", "crud"),
                             ("Good grief!", "good grief"), ("Good heavens!", "good heavens"),
                             ("Oh my goodness!", "oh my goodness"),
                             ("Thank goodness you're here", "thank goodness"),
                             ("For Pete's sake", "for pete's sake"),
                             ("For crying out loud!", "for crying out loud"),
                             ("Holy cow!", "holy cow"), ("Holy moly", "holy moly"),
                             ("Holy molly!", "holy molly"), ("Holy smokes", "holy smokes"),
                             ("Gee whiz", "gee whiz"), ("Jeepers creepers", "jeepers creepers"),
                             ("You son of a gun!", "son of a gun"), ("Oh, fudge.", "oh fudge"),
                             ("Oh shoot, I forgot", "oh shoot"),
                             ("Goodness gracious me", "goodness gracious"),
                             ("Gee, thanks", "gee"), ("Gee, Mom!", "gee"),
                             ("You don't know squat", "squat"),
                             ("It doesn't mean squat", "squat"),
                             ("He didn't do squat all day", "squat"),
                             ("That's not worth squat", "squat"),
                             ("You got jack squat", "jack squat"),
                             ("Diddly squat", "diddly squat"), ("diddlysquat", "diddlysquat")]:
            with self.subTest(text=text):
                self.assertEqual(found(text, ["minced"]), [(phrase, "minced")])

    def test_exercise_squats_and_horses_left_alone(self):
        for text in ("Do ten squats", "Squat down low", "Can you do squat jumps?",
                     "He did a squat", "squatters moved in", "a squat little teapot",
                     "Gee up, horse!", "Sit squat on the floor"):
            with self.subTest(text=text):
                self.assertEqual(found(text), [])

    def test_gods_name(self):
        for text, phrase in [("Oh my Lord, look at that", "oh my lord"),
                             ("Lord have mercy", "lord have mercy"),
                             ("I swear to God", "swear to god"),
                             ("God forbid", "god forbid"),
                             ("What in God's name?", "in god's name"),
                             ("Lord knows I tried", "lord knows")]:
            with self.subTest(text=text):
                self.assertEqual(found(text, ["deity"]), [(phrase, "deity")])

    def test_rude_words_kids_copy(self):
        for text, phrase in [("You wimp!", "wimp"), ("What a weirdo", "weirdo"),
                             ("Don't be a crybaby", "crybaby"), ("You big sissy", "sissy"),
                             ("You twit", "twit"), ("Stop it, you brat", "brat"),
                             ("You imbecile!", "imbecile"), ("scaredy-cat", "scaredycat"),
                             ("I hate you!", "i hate you"), ("Talk to the hand", "talk to the hand"),
                             ("Shut your pie hole", "shut your pie hole"),
                             ("Shut your big mouth", "shut your big mouth"),
                             ("Buzz off!", "buzz off"), ("Eat my shorts", "eat my shorts")]:
            with self.subTest(text=text):
                self.assertEqual(found(text, ["rude"]), [(phrase, "rude")])

    def test_mild_and_moderate(self):
        for text, phrase, cat in [("We're screwed", "we're screwed", "mild"),
                                  ("Up yours!", "up yours", "mild"),
                                  ("That was craptastic", "craptastic", "mild"),
                                  ("Dayum", "dayum", "mild"), ("She's a floozy", "floozy", "mild"),
                                  ("Can't be arsed", "arsed", "moderate"),
                                  ("Check out those jugs", "check out those jugs", "moderate"),
                                  ("Nice rack", "nice rack", "moderate"),
                                  ("Kicked him in the junk", "kicked him in the junk", "moderate"),
                                  ("suck my cock", "my cock", "moderate")]:
            with self.subTest(text=text):
                self.assertEqual(found(text, [cat]), [(phrase, cat)])
        self.assertEqual(found("lesbos", ["samesex"]), [("lesbos", "samesex")])

    def test_everyday_uses_left_alone(self):
        for text in ("The shelf is screwed to the wall", "I screwed up the order",
                     "The lid was screwed on tight", "a rack of lamb", "the spice rack",
                     "The cock crowed at dawn", "Cock the gun", "a cock and bull story",
                     "Throw it in the junk pile", "Your package arrived",
                     "Army brats move a lot", "The Twits by Roald Dahl", "Wimpy ate a burger",
                     "Get that bug off me", "Holy water", "the Holy Bible", "a holy man",
                     "Good night", "My goodwill",
                     "a big jug of milk", "I hate yogurt", "Golf is fun"):
            with self.subTest(text=text):
                self.assertEqual(found(text), [])


class Bull(unittest.TestCase):
    """"That's bull" is short for bullshit (mild language); a real bull is left alone."""

    def test_bull_muted(self):
        for text in ("That's bull!", "That is bull and you know it", "What a load of bull",
                     "This is total bull", "Cut the bull, Castle", "It's all bull",
                     "You're full of bull", "a bunch of bull", "That's complete bull",
                     "no more bull", "thats bull"):
            with self.subTest(text=text):
                self.assertEqual(found(text, ["mild"]), [("bull", "mild")])
        self.assertEqual(found("That's bull", ["moderate"]), [("bull", "moderate")])

    def test_bullshit_heard_as_two_words(self):
        self.assertEqual(found("that's bull shit", ["mild", "moderate"]),
                         [("bull", "mild"), ("shit", "moderate")])
        self.assertEqual(found("total bull crap", ["mild"]), [("bull", "mild"), ("crap", "mild")])

    def test_real_bulls_left_alone(self):
        for text in ("The bull charged at him", "That's bull riding for you",
                     "That's a bull, not a cow", "a bull market", "It's a pit bull",
                     "like a bull in a china shop", "take the bull by the horns",
                     "the Chicago Bulls", "That's bull terrier hair", "a bull's eye",
                     "is that bull dangerous", "Sitting Bull", "a red bull"):
            with self.subTest(text=text):
                self.assertEqual(found(text), [])

    def test_ai_may_mute_it_said_that_way(self):
        self.assertTrue(cl.listed_word("that's bull"))
        self.assertFalse(cl.listed_word("bull"))


class FruitAndVegetables(unittest.TestCase):
    """Fruit and vegetables used for body parts ("check out those melons"), only in these
    phrases: real melons, cherries and bananas are left alone."""

    def test_whole_phrase_muted(self):
        for text, phrase in [
                ("Check out those melons!", "check out those melons"),
                ("Nice pair of cantaloupes", "nice pair of cantaloupes"),
                ("He was staring at her coconuts", "staring at her coconuts"),
                ("Look at them big melons", "look at them big melons"),
                ("Her huge melons", "her huge melons"),
                ("You popped her cherry?", "popped her cherry"),
                ("I lost my cherry at prom", "lost my cherry"),
                ("She kneed him in the grapes", "kneed him in the grapes"),
                ("Kicked me right in the plums", "kicked me right in the plums"),
                ("hit him in the franks and beans", "hit him in the franks and beans"),
                ("He zipped his franks and beans", "zipped his franks and beans"),
                ("freezing my grapes off out here", "freezing my grapes off"),
                ("Is that a banana in your pocket?", "is that a banana in your pocket"),
                ("a cucumber in his pants", "cucumber in his pants"),
                ("Look at her tight buns", "her tight buns"),
                ("his juicy peach", "his juicy peach")]:
            with self.subTest(text=text):
                self.assertEqual(found(text, ["moderate"]), [(phrase, "moderate")])

    def test_real_fruit_left_alone(self):
        for text in ("These melons are ripe", "Check out these melons, only a dollar",
                     "a slice of watermelon", "grapefruit for breakfast", "cherry pie",
                     "She lost her cherry pie recipe", "the cherry on top", "a bunch of grapes",
                     "We grew plums and beans", "pass the franks and beans",
                     "meat and two veg for dinner", "I kept a carrot in my pocket for the horse",
                     "a banana in my lunchbox", "a juicy peach", "hot cross buns",
                     "She wore her hair in buns", "climbing for coconuts",
                     "popped a cherry tomato in her mouth", "a big pair of shoes"):
            with self.subTest(text=text):
                self.assertEqual(found(text), [])

    def test_ai_may_mute_the_phrase_but_not_the_fruit(self):
        self.assertTrue(cl.listed_word("check out those melons"))
        for word in ("melons", "cherry", "banana", "plums"):
            self.assertFalse(cl.listed_word(word))

    def test_reviewer_is_told(self):
        self.assertIn("those melons", engine.wanted_text({}, ["swearing"]))


class ShortForms(unittest.TestCase):
    """D-bag, SOB and ball buster. "sob" is also a real word, so it only counts written
    as an abbreviation (capitals or dots) or spelled out."""

    def test_caught(self):
        for text, phrase in [("You SOB!", "sonofabitch"), ("You S.O.B.", "sonofabitch"),
                             ("those SOBs", "sonofabitch"), ("you s o b", "s o b"),
                             ("What a D-bag.", "douchebag"), ("Those d-bags", "douchebag"),
                             ("Total dbag", "douchebag"), ("You d bag", "d bag"),
                             ("She's a ball buster", "ball buster"),
                             ("ball-buster", "ballbuster"), ("ballbusting boss", "ballbusting"),
                             ("Quit busting my balls", "busting my balls")]:
            with self.subTest(text=text):
                self.assertEqual(found(text, ["moderate"]), [(phrase, "moderate")])

    def test_everyday_words_left_alone(self):
        for text in ("She let out a sob.", "It's a sob story", "He sobbed", "a bag of chips",
                     "D. Bagwell", "the ball bounced", "bust a move"):
            with self.subTest(text=text):
                self.assertEqual(found(text), [])

    def test_ai_may_mute_them(self):
        for word in ("D-bag", "SOB", "ball buster"):
            self.assertTrue(cl.listed_word(word))
        self.assertFalse(cl.listed_word("sob"))

    def test_shown_masked(self):
        self.assertEqual(cl.mask("S.O.B."), "S**")
        self.assertEqual(cl.mask("D-bag"), "D***")


class MoreCrudeSlang(unittest.TestCase):
    """Crude slang heard in TV and films, and the everyday uses of the same words."""

    def test_caught(self):
        for text, word, cat in [
                ("You A-hole", "ahole", "moderate"), ("What the f-ing hell", "what the fing", "strong"),
                ("WTF is this", "wtf", "strong"), ("eff you", "eff you", "moderate"),
                ("you mofo", "mofo", "strong"), ("Don't be a pussy", "pussy", "moderate"),
                ("He got a boner", "boner", "moderate"), ("nice boobs", "boobs", "moderate"),
                ("huge knockers", "knockers", "moderate"), ("She's horny", "horny", "moderate"),
                ("a couple of hookers", "hookers", "moderate"), ("total MILF", "milf", "moderate"),
                ("you cockblocked me", "cockblocked", "moderate"),
                ("what a dickwad", "dickwad", "moderate"), ("numbnuts", "numbnuts", "moderate"),
                ("you tosser", "tosser", "moderate"), ("feckin' eejit", "feckin", "moderate"),
                ("that's retarded", "retarded", "moderate"), ("biatch", "biatch", "moderate"),
                ("shat himself", "shat", "moderate"), ("in the crapper", "crapper", "mild"),
                ("you turd", "turd", "mild"), ("brazen hussy", "hussy", "mild"),
                ("frakking toasters", "frakking", "minced"),
                ("Jesus H. Christ", "jesus h christ", "deity"),
                ("Mother of God", "mother of god", "deity")]:
            with self.subTest(text=text):
                self.assertEqual(found(text, [cat]), [(word, cat)])

    def test_slurs(self):
        for word in ("wetback", "towelhead", "raghead"):
            with self.subTest(word=word):
                self.assertEqual(found(f"you {word}", ["strong"]), [(word, "strong")])

    def test_everyday_uses_left_alone(self):
        for text in ("a pussy cat", "Pussy willow", "Dick Grayson", "Moby Dick",
                     "summa cum laude", "General Hooker", "the dickens", "Charles Dickens",
                     "a hole in the wall", "fire retardant", "retard the spread",
                     "keep your pecker up", "the boob tube", "a horny toad",
                     "brass door knockers", "fudging the numbers", "shatter",
                     "hellas", "turducken", "a pecking order"):
            with self.subTest(text=text):
                self.assertEqual(found(text), [])


class FromTheReports(unittest.TestCase):
    """Words missed in the reports sent in (The Resident, Seabiscuit, Ever After, Pride and
    Prejudice, National Treasure; 2026-10-29)."""

    def test_now_found(self):
        for text, phrase, cat in [("Grow some cajones", "grow some cajones", "moderate"),
                                  ("He's got cahones", "cahones", "moderate"),
                                  ("You still get screwed", "get screwed", "mild"),
                                  ("We got screwed!", "got screwed", "mild"),
                                  ("Verdammt!", "verdammt", "mild"), ("Merde!", "merde", "moderate"),
                                  ("So help me God", "so help me god", "deity"),
                                  ("Praise the Lord!", "praise the lord", "deity"),
                                  ("Holy Lord!", "holy lord", "deity"),
                                  ("What the devil?", "what the devil", "minced"),
                                  ("What the dickens is that?", "what the dickens", "minced"),
                                  ("For God's sakes!", "for god's sakes", "deity"),
                                  ("For Christ's sakes", "for christ's sakes", "deity"),
                                  ("Morning, dum-dum.", "dumdum", "rude"),
                                  ("Fathead.", "fathead", "rude")]:
            with self.subTest(text=text):
                self.assertEqual(found(text, [cat]), [(phrase, cat)])

    def test_everyday_uses_left_alone(self):
        for text in ("The lid got screwed on tight", "It got screwed to the wall",
                     "Get screwed in properly", "The devil is in the details",
                     "Holy water", "the dickens novel", "He played the devil",
                     "loaded with dum-dum bullets"):
            with self.subTest(text=text):
                self.assertEqual(found(text), [])


class Suck(unittest.TestCase):
    """"Suck" meaning "is bad" is a rude word kids copy (Lauren, 2026-10-29); sucking
    something is left alone."""

    def test_found(self):
        for text, phrase in [("That really sucks", "sucks"), ("Life sucks", "sucks"),
                             ("He sucks at math", "sucks"), ("That sucked", "sucked"),
                             ("What a sucky day", "sucky"), ("You sucker!", "you sucker"),
                             ("You suck", "you suck"), ("This sucks big time", "this sucks"),
                             ("Man, that sucks.", "that sucks"), ("Sucks to be you", "sucks to be you")]:
            with self.subTest(text=text):
                self.assertEqual(found(text, ["rude"]), [(phrase, "rude")])
        self.assertTrue(cl.listed_word("sucks"))

    def test_everyday_uses_left_alone(self):
        for text in ("Suck it up", "Suck on a lollipop", "The vacuum sucks up dirt",
                     "Sucking his thumb", "The baby sucked", "Sucked into the whirlpool",
                     "A lollipop sucker", "Sucker punch", "He is a sucker for romance",
                     "It sucks the juice out", "The straw sucks"):
            with self.subTest(text=text):
                self.assertEqual(found(text), [])


class SubtitleWordsNearOtherMutes(unittest.TestCase):
    """'what the hell, damn it': listening caught "damn", the subtitles add "hell"
    half a second earlier. That's another word, not the same one twice."""

    damn = {"s": 1.5, "e": 1.8, "raw": "damn"}

    def test_another_word_close_by_is_added(self):
        self.assertFalse(engine.already_muted([self.damn], "hell", 1.0, 1.3))

    def test_the_same_word_is_not_added_twice(self):
        self.assertTrue(engine.already_muted([self.damn], "damn", 1.6, 1.9))

    def test_a_word_already_inside_a_mute_is_not_added(self):
        self.assertTrue(engine.already_muted([self.damn], "dang", 1.52, 1.78))

    def test_a_word_said_twice_is_muted_twice(self):
        """Listening caught one "bitch", the subtitles have two ("Bitty bitch! Bitty
        bitch!", The Blind Side; a repeated lyric, A Walk to Remember)."""
        heard = {"s": 1.5, "e": 1.8, "raw": "bitch"}
        mutes, used = [heard], set()
        self.assertTrue(engine.already_muted(mutes, "bitch", 1.6, 1.9, used))   # that one
        self.assertFalse(engine.already_muted(mutes, "bitch", 1.7, 2.0, used))  # the repeat
        s, e = engine.after_same_word(mutes, "bitch", 1.7, 2.0)
        self.assertAlmostEqual(s, 1.85)
        self.assertAlmostEqual(e, 2.15)


class FromJasonsReports(unittest.TestCase):
    """Words from the reports sent in on 2026-10-30 (Aladdin, The Blind Side, A Walk to
    Remember), and their everyday uses."""

    def test_now_found(self):
        for text, phrase, cat in [("By Allah, it's true", "by allah", "deity"),
                                  ("Allah forbid", "allah forbid", "deity"),
                                  ("Praise Allah!", "praise allah", "deity"),
                                  ("Lord help that child", "lord help that", "deity"),
                                  ("God help him", "god help him", "deity"),
                                  ("He's PO'd at me", "pissed", "moderate"),
                                  ("That sounds like bull", "bull", "mild")]:
            with self.subTest(text=text):
                self.assertIn((phrase, cat), found(text))

    def test_everyday_uses_left_alone(self):
        for text in ("Po'd better run", "A bull in a field", "Allah is the Arabic word for God",
                     "It sounds like a bull"):
            with self.subTest(text=text):
                self.assertEqual(found(text), [])

    def test_ai_mutes_only_words_from_ticked_groups(self):
        """13 Going on 30: an AI muted "butts" with rude words off."""
        self.assertTrue(cl.listed_word("butts"))
        self.assertFalse(cl.listed_word("butts", cats=["strong", "moderate", "mild", "deity"]))
        self.assertTrue(cl.listed_word("butts", cats=["rude"]))
        self.assertFalse(cl.listed_word("Lord knows", cats=["mild"]))
        self.assertTrue(cl.listed_word("Lord knows", cats=["deity"]))
        self.assertFalse(engine._words_listed("butts", (), ["swearing", "mild", "deity"]))
        self.assertTrue(engine._words_listed("butts", (), ["rude"]))



class FromTheResident(unittest.TestCase):
    """The Resident, season 2 episodes 9-23 (checked 2026-10-30)."""

    def test_now_found(self):
        for text, phrase, cat in [("We would be screwed", "be screwed", "mild"),
                                  ("What in heaven's name", "in heaven's name", "minced"),
                                  ("Oh, hallelujah", "oh hallelujah", "deity")]:
            with self.subTest(text=text):
                self.assertIn((phrase, cat), found(text))

    def test_everyday_uses_left_alone(self):
        for text in ("The shelf was screwed to the wall", "The choir sang hallelujah",
                     "It was screwed shut"):
            with self.subTest(text=text):
                self.assertEqual(found(text), [])

    def test_a_different_word_in_the_subtitles_is_noted(self):
        """"dick" heard where the subtitles have the name "Nic": told to the review.
        A swear the subtitles soften ("darn") or leave out isn't."""
        asr_n = ["hey", "dick", "come", "here", "damn", "it"]
        mutes = [{"src": "audio", "at": 1, "raw": "dick"}, {"src": "audio", "at": 4, "raw": "damn"}]
        sw = ["Hey,", "Nic,", "come", "here.", "Darn", "it."]
        sn = [cl.norm(w) for w in sw]
        engine.subtitle_word_there(mutes, list(range(6)), sw, sn, asr_n)
        self.assertEqual(mutes[0].get("sub"), "Nic,")
        self.assertNotIn("sub", mutes[1])
        import cleanview_claude as cc
        st = {"scenes": [], "lines": [], "mutes": [dict(mutes[0], s=1, e=2, word="d***")]}
        self.assertIn("where the subtitles have 'Nic,'", cc.candidates(st)[1])



class ReverentJesus(unittest.TestCase):
    """"Jesus" and "Christ" said with reverence aren't muted as swears; oaths are
    (Lauren, from Jason's report on At Every Turn; the same in CleanListen 1.10.0)."""

    def test_reverent_left_alone(self):
        for text in ("the love of Christ", "Jesus told us to love one another",
                     "the gospel of Jesus Christ", "Christ is risen", "thank you Jesus",
                     "We follow Jesus", "Jesus loves you"):
            with self.subTest(text=text):
                self.assertEqual(found(text), [])

    def test_oaths_still_muted(self):
        for text, phrase in [("Jesus!", "jesus"), ("Jesus, is that you?", "jesus"),
                             ("Christ, that hurt", "christ"),
                             ("Jesus Christ, what a mess", "jesus christ"),
                             ("Oh my Jesus", "jesus"), ("Sweet Jesus", "sweet jesus"),
                             ("For the love of Christ", "for the love of christ")]:
            with self.subTest(text=text):
                self.assertIn((phrase, "deity"), found(text))


if __name__ == "__main__":
    unittest.main()
