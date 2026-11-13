"""Portuguese and Russian (1.18.88; the owner, 2026-11-13: "can do both portuguise and russian
now"), built like Spanish and French (test_spanish.py, test_french.py): each has its own word
lists in the same groups, its subtitles and sound track, and the listening model for other
languages. Russian is the first language in another alphabet, so the places that only knew
English letters are checked too.

No Portuguese or Russian speech has been heard here: the listening model's samples are
Spanish, French, German and English only."""
import tempfile
import unittest
from pathlib import Path

import support
import cvcore as cl
import cvlang
import cleanview as engine
import cleanview_ai as ai
import cleanview_learn as learn
from test_spanish import SRT, found


class Portuguese(unittest.TestCase):
    def setUp(self):
        cl.use_language("pt")
        self.addCleanup(cl.use_language, "en")

    def test_words_as_the_lists_have_them(self):
        self.assertEqual(cl.norm("Não!"), "nao")
        self.assertEqual(cl.norm("cuzão,"), "cuzao")
        self.assertEqual(cl.norm("Foda-se!"), "fodase")
        self.assertEqual(cl.norm("céu"), "ceu")

    def test_swearing_is_found(self):
        self.assertEqual(found("Vai se foder, seu filho da puta!"),
                         [("foder", "strong"), ("puta", "strong")])
        self.assertEqual(found("Que merda é essa, porra?"),
                         [("merda", "moderate"), ("porra", "moderate")])
        self.assertEqual(found("Foda-se, caralho"), [("fodase", "strong"), ("caralho", "strong")])
        self.assertEqual(found("Vai tomar no cu"), [("cu", "moderate")])
        self.assertEqual(found("Seu cuzão arrombado"),
                         [("cuzao", "moderate"), ("arrombado", "strong")])
        self.assertEqual(found("Que bosta de carro"), [("bosta", "moderate")])

    def test_milder_groups(self):
        self.assertEqual(found("Meu Deus do céu!"), [("meu deus do ceu", "deity")])
        self.assertEqual(found("Nossa Senhora, que susto"), [("nossa senhora", "deity")])
        self.assertEqual(found("Que droga, perdi as chaves"), [("que droga", "mild")])
        self.assertEqual(found("Caramba, que susto"), [("caramba", "minced")])
        self.assertEqual(found("Cala a boca, idiota"), [("cala a boca", "rude"), ("idiota", "rude")])
        self.assertEqual(found("Não seja bobo"), [("bobo", "rude")])
        self.assertEqual(found("Ele é gay"), [("gay", "samesex")])

    def test_everyday_words_are_left_alone(self):
        for text in ("O puto brinca com um pau na bicha do pão",
                     "A abelha pica e o veado corre",
                     "Os raios X do hospital ficaram prontos",
                     "A droga foi apreendida pela polícia",
                     "A nossa casa fica perto do fogo",
                     "O burro e a cadela dormem no celeiro",
                     "Ele toca corno inglês na orquestra",
                     "Graças ao professor, o computador funciona",
                     "Deus te abençoe, meu filho"):
            self.assertEqual(found(text), [], text)

    def test_only_the_groups_that_are_ticked(self):
        self.assertEqual(found("Porra, que idiota", cl.GROUPS["rude"]), [("idiota", "rude")])
        self.assertEqual(found("Meu Deus, que merda", cl.GROUPS["swearing"]),
                         [("merda", "moderate")])

    def test_only_listed_words_may_be_muted_alone(self):
        self.assertTrue(cl.listed_word("caralho"))
        self.assertTrue(cl.listed_word("Meu Deus"))
        self.assertTrue(cl.listed_word("Foda-se"))
        self.assertFalse(cl.listed_word("Grafi"))
        self.assertFalse(cl.listed_word("casa"))

    def test_masked_in_the_review(self):
        self.assertEqual(cl.mask("caralho"), "c******")


class Russian(unittest.TestCase):
    def setUp(self):
        cl.use_language("ru")
        self.addCleanup(cl.use_language, "en")

    def test_words_as_the_lists_have_them(self):
        self.assertEqual(cl.norm("Чёрт!"), "черт")           # ё as е
        self.assertEqual(cl.norm("«Блин»,"), "блин")
        self.assertEqual(cl.norm("Ёлки-палки"), "елкипалки")
        self.assertEqual(cl.norm("мой"), "мой")              # й stays й
        self.assertEqual(cl.norm("БОЖЕ"), "боже")

    def test_swearing_is_found(self):
        self.assertEqual(found("Иди на хуй, мудак!"), [("хуй", "strong"), ("мудак", "strong")])
        self.assertEqual(found("Блядь, какого чёрта?"),
                         [("блядь", "strong"), ("какого черта", "mild")])
        self.assertEqual(found("Ёб твою мать"), [("еб", "strong"), ("твою мать", "moderate")])
        self.assertEqual(found("Заебал уже, сука"), [("заебал", "strong"), ("сука", "moderate")])
        self.assertEqual(found("Пиздец какой-то"), [("пиздец", "strong")])
        self.assertEqual(found("Говно вопрос"), [("говно", "moderate")])
        self.assertEqual(found("Пошёл в жопу, сволочь"),
                         [("жопу", "moderate"), ("сволочь", "moderate")])
        self.assertEqual(found("Охуеть можно"), [("охуеть", "strong")])

    def test_milder_groups(self):
        self.assertEqual(found("Чёрт возьми!"), [("черт возьми", "mild")])
        self.assertEqual(found("Блин, я забыл ключи"), [("блин", "minced")])
        self.assertEqual(found("Это полная фигня"), [("фигня", "minced")])
        self.assertEqual(found("Ёлки-палки, опять"), [("елкипалки", "minced")])
        self.assertEqual(found("О боже мой!"), [("о боже мой", "deity")])
        self.assertEqual(found("Слава богу, успели"), [("слава богу", "deity")])
        self.assertEqual(found("Господи, что это?"), [("господи", "deity")])
        self.assertEqual(found("Заткнись, дурак"), [("заткнись", "rude"), ("дурак", "rude")])
        self.assertEqual(found("Он гей"), [("гей", "samesex")])

    def test_everyday_words_are_left_alone(self):
        for text in ("Хуже не будет, худой хулиган",
                     "Небо, хлеб, ребёнок, учебник и мебель",
                     "Спасибо тебе и себе",
                     "Вкусный блин со сметаной",
                     "Бабушка испекла блин",
                     "Какая хорошая черта характера",
                     "Херсон и херувим",
                     "Гейзер и гейм",
                     "Ёлки зелёные стоят",
                     "Голубой шарик летит в небо",
                     "Козёл и семеро козлят",
                     "Мы потребовали ссылку на погреб",
                     "Бог есть любовь",
                     "Трах-тибидох, сказал старик"):
            self.assertEqual(found(text), [], text)

    def test_only_the_groups_that_are_ticked(self):
        self.assertEqual(found("Блядь, ты дурак", cl.GROUPS["rude"]), [("дурак", "rude")])
        self.assertEqual(found("Боже мой, какое говно", cl.GROUPS["swearing"]),
                         [("говно", "moderate")])

    def test_only_listed_words_may_be_muted_alone(self):
        self.assertTrue(cl.listed_word("хуй"))
        self.assertTrue(cl.listed_word("Чёрт возьми"))
        self.assertTrue(cl.listed_word("секс"))
        self.assertFalse(cl.listed_word("Груффи"))
        self.assertFalse(cl.listed_word("дом"))
        self.assertFalse(cl.listed_word("дурак", cats=cl.GROUPS["swearing"]))

    def test_masked_in_the_review(self):
        self.assertEqual(cl.mask("говно"), "г****")

    def test_her_own_words_always(self):
        self.assertEqual(found("Какая гадость эта заливная рыба", [], [("заливная", "рыба")]),
                         [("заливная рыба", "mine")])


class AnotherAlphabet(unittest.TestCase):
    """What only knew English letters."""

    def setUp(self):
        self.addCleanup(cl.use_language, "en")

    def test_an_ais_quoted_words_are_found_in_a_russian_line(self):
        self.assertEqual(ai._letters("Hello, World!"), "hello world")        # English as before
        cl.use_language("ru")
        self.assertEqual(ai._letters("«Давай переспим», — сказал он."), "давай переспим сказал он")
        self.assertIn(ai._letters("давай переспим"), ai._letters("— Давай переспим, а?"))
        self.assertEqual(ai._letters("Ещё чёрт"), "еще черт")

    def test_a_russian_line_is_learned_as_itself(self):
        self.assertEqual(learn.norm("Well, DAMN it!"), "well damn it")         # English as before
        cl.use_language("ru")
        self.assertEqual(learn.norm("Давай переспим, а?"), "давай переспим а")
        self.assertNotEqual(learn.norm("Привет, как дела?"), learn.norm("Пока, до завтра!"))
        cl.use_language("es")
        self.assertEqual(learn.norm("¿Qué coño haces?"), "qué coño haces")

    def test_a_video_named_in_cyrillic_has_a_name(self):
        self.assertEqual(engine.guess_title("D:/Кино/Брат 2 (2000).mkv")[0], "Брат 2 (2000)")
        self.assertEqual(engine.guess_title("D:/Кино/Кухня S02E05.mkv"), ("Кухня", 2, 5))
        self.assertIsNone(engine.guess_title("D:/Кино/1234.mkv"))
        self.assertEqual(engine.guess_title("D:/Shows/Castle S02E05.mkv"), ("Castle", 2, 5))


class FilesAndTheList(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(dir=support.SANDBOX))
        self.video = self.dir / "Filme.mkv"
        self.video.write_bytes(b"")
        self.addCleanup(cl.use_language, "en")

    def test_the_videos_own_language(self):
        (self.dir / "Filme.en.srt").write_text(SRT.replace("{}", "English line"), encoding="utf8")
        (self.dir / "Filme.pt-br.srt").write_text(SRT.replace("{}", "Linha em português"),
                                                  encoding="utf8")
        (self.dir / "Filme.ru.srt").write_text(SRT.replace("{}", "Строка по-русски"),
                                               encoding="utf8")
        for lang, word in (("pt", "português"), ("ru", "по-русски")):
            cues, where = engine.find_subtitles(self.video, {"subs": []}, self.dir, lang)
            self.assertIn(word, cues[0]["text"], lang)

    def test_saved_files_the_note_and_the_lookup(self):
        for lang, name, sub in (("pt", "Portuguese", "pt"), ("ru", "Russian", "ru")):
            cl.use_language(lang)
            self.assertEqual(engine._lang_file("transcript.json"), f"transcript_{lang}.json")
            self.assertIn(f"in {name}", cvlang.reader_note(lang))
            try:
                import babelfish  # noqa: F401
            except ImportError:
                continue
            self.assertEqual(str(engine._sub_language()), sub)

    def test_sound_track_tags(self):
        self.assertIn("por", cvlang.TAGS["pt"])
        self.assertIn("rus", cvlang.TAGS["ru"])

    def test_on_the_start_pages_list(self):
        self.assertEqual(list(cvlang.LANGS.values()),
                         ["English", "Spanish", "French", "Portuguese", "Russian"])
        for code in ("pt", "ru"):
            self.assertEqual(set(cvlang.WORDS[code]), set(cvlang.ORDER) | {"sex"})
            for table in (cvlang.PHRASES, cvlang.NOT_NEXT, cvlang.NOT_BEFORE, cvlang.TAGS,
                          cvlang.FILE_TAGS, cvlang.SUB_LANG):
                self.assertIn(code, table)
            for group, phrases in cvlang.PHRASES[code].items():
                for ph in phrases:              # written as norm() leaves them
                    self.assertEqual(tuple(cvlang.norm(w, code) for w in ph), ph, ph)

    def test_each_language_keeps_to_its_own_list(self):
        cl.use_language("pt")
        self.assertEqual(found("Иди на хуй, cabrón, putain"), [])
        cl.use_language("ru")
        self.assertEqual(found("Vai se foder, merda"), [])


if __name__ == "__main__":
    unittest.main()
