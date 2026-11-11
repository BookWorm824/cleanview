"""The closer look's picture model (1.18.56, 2026-11-11; the owner: "Yes, build it"): qwen3-vl's
instruct build first (the plain tag is the thinking build, which thinks even when told not to:
~16 s a look and some past the 4-minute limit), downloaded once on "Getting ready" where only
the older ones are installed, and the gore question as a checklist whose ticks CleanView turns
into Gore / Graphic / nothing (the instruct build called open surgery "blood" when asked for a
level)."""
import unittest
from unittest import mock

import support  # noqa: F401  (sets up the sandbox first)
import cleanview as engine
import cleanview_ai as ai


class WhichModel(unittest.TestCase):
    def test_instruct_first_then_the_older_ones(self):
        self.assertEqual(ai.VISION_MODELS[-3:],
                         ["qwen3-vl:8b-instruct", "qwen3-vl:8b", "qwen2.5vl:7b"])

    def pick(self, have):
        with mock.patch.object(ai, "_installed", lambda: set(have)), \
                mock.patch.object(ai, "VISION_MODEL", ai.VISION_MODEL):
            ok = ai.choose_models()
            return ok, ai.VISION_MODEL

    def test_uses_instruct_when_its_there(self):
        self.assertEqual(self.pick({"qwen3-vl:8b-instruct", "qwen3-vl:8b", "qwen3:8b"}),
                         (True, "qwen3-vl:8b-instruct"))

    def test_the_old_one_until_the_new_one_is_downloaded(self):
        self.assertEqual(self.pick({"qwen3-vl:8b", "qwen3:8b"}), (True, "qwen3-vl:8b"))

    def test_getting_ready_downloads_it_once(self):
        have = {"qwen3-vl:8b", "qwen3:8b"}
        o = engine.full_opts({"kiss_os": "all", "ai": True})
        with mock.patch.object(ai, "_installed", lambda: have), \
                mock.patch.object(ai, "ollama_running", lambda: True), \
                mock.patch.object(ai, "clip_ready", lambda: True), \
                mock.patch.object(engine, "nudity_model", lambda: "x"), \
                mock.patch.object(engine, "_upgrade_tried", lambda: False):
            self.assertIn("newer AI models", engine.tools_missing(o))
        with mock.patch.object(ai, "_installed", lambda: have), \
                mock.patch.object(ai, "ollama_running", lambda: True), \
                mock.patch.object(ai, "clip_ready", lambda: True), \
                mock.patch.object(engine, "nudity_model", lambda: "x"), \
                mock.patch.object(engine, "_upgrade_tried", lambda: True):
            self.assertNotIn("newer AI models", engine.tools_missing(o))   # tried: not again
        pulled = []
        with mock.patch.object(ai, "_installed", lambda: have), \
                mock.patch.object(ai, "start_ollama", lambda wait=60: True), \
                mock.patch.object(ai, "pull_model",
                                  lambda m, progress=None, label="": (pulled.append(m),
                                                                     have.add(m))):
            ai.ensure_ai()
        self.assertEqual(pulled, ["qwen3-vl:8b-instruct"])               # only the new one
        self.assertEqual(ai.VISION_MODEL, "qwen3-vl:8b-instruct")


class GoreChecklist(unittest.TestCase):
    def test_what_it_ticks_decides_the_level(self):
        L = ai.gore_level
        self.assertEqual(L({"visible": ["blood", "open surgery with the inside of the body "
                                                 "showing"]}), "gore")
        for inside in ("organs or entrails", "brain", "bone showing",
                       "a severed or mangled body part"):
            self.assertEqual(L({"visible": [inside]}), "gore", inside)
        self.assertEqual(L({"visible": ["blood"]}), "graphic")
        self.assertEqual(L({"visible": ["a bloody wound or cut", "stitches or a closed scar"]}),
                         "graphic")
        for nothing in (["a bruise, rash or red mark"], ["stitches or a closed scar"],
                        ["none of these"], []):
            self.assertEqual(L({"visible": nothing}), "none", nothing)
        self.assertEqual(L({"level": "insides"}), "gore")                # an older answer form
        self.assertEqual(L({"level": "blood"}), "graphic")
        self.assertEqual(L({}), "none")

    def test_the_closer_look_asks_the_checklist(self):
        asked = []

        def fake_chat(prompt, images=None, schema=None, **k):
            asked.append((prompt, schema))
            return {"see": "an open chest in surgery",
                    "visible": ["blood", "open surgery with the inside of the body showing"],
                    "clear": True}
        c = {"cat": "gore", "frames": [1.0, 2.0]}
        with mock.patch.object(ai, "chat", fake_chat):
            ai.second_look([c], lambda c: ["frame"])
        prompt, schema = asked[0]
        self.assertIn("Tick every one that is there", prompt)
        self.assertIn("A bruise, rash or red skin is not blood", prompt)
        self.assertEqual(schema["properties"]["visible"]["items"]["enum"], ai.GORE_SEEN)
        self.assertEqual(schema["required"], ["see", "visible", "clear"])
        self.assertEqual(c["verdict"]["level"], "gore")
        self.assertTrue(c["verdict"]["keep"])

    def test_a_rash_is_dropped(self):
        c = {"cat": "gore", "frames": [1.0]}
        with mock.patch.object(ai, "chat", lambda *a, **k: {
                "see": "a red rash on a neck", "visible": ["a bruise, rash or red mark"],
                "clear": True}):
            ai.second_look([c], lambda c: ["frame"])
        self.assertEqual(c["verdict"]["level"], "none")
        self.assertFalse(c["verdict"]["keep"])


if __name__ == "__main__":
    unittest.main()
