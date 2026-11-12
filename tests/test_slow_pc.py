"""On a PC without a graphics card the AI helper runs on the processor, 7-8 times slower, so
each question gets SLOW_TIMES as long (1.18.65, 2026-11-12; the owner: "everything would
work on a computer with no dedicated gpu right?", then "Yes, build it")."""
import unittest
from unittest import mock

import support  # noqa: F401  (sets up the sandbox first)
import cleanview_ai as ai


class TimeLimits(unittest.TestCase):
    def setUp(self):
        self.asked = []
        for p in (mock.patch.object(ai, "_chat_now", lambda payload, model, timeout:
                                    self.asked.append(timeout) or {"ok": True}),
                  mock.patch.object(ai, "_saved_answer", lambda key: None),
                  mock.patch.object(ai, "_save_answer", lambda key, answer: None),
                  mock.patch.dict(ai._card_share, clear=True)):
            p.start()
            self.addCleanup(p.stop)

    def ask(self, share, model="text-model"):
        with mock.patch.object(ai, "on_card_share", lambda m: share):
            ai.chat("question", schema={"type": "object"}, timeout=240, model=model)
        return self.asked[-1]

    def test_on_the_graphics_card(self):
        self.assertEqual(self.ask(0.92), 240)
        self.assertEqual(self.ask(0.5, "vision-model"), 240)      # Lauren's laptop: 50%

    def test_on_the_processor(self):
        self.assertEqual(self.ask(0.0), 240 * ai.SLOW_TIMES)
        self.assertEqual(self.ask(0.3, "other"), 240 * ai.SLOW_TIMES)

    def test_not_loaded_yet(self):
        # the first question also loads the model: the longer limit, then what it found
        self.assertEqual(self.ask(None), 240 * ai.SLOW_TIMES)
        self.assertEqual(self.ask(0.9), 240)
        self.assertEqual(self.ask(None), 240)     # remembered once known

    def test_each_model_on_its_own(self):
        self.assertEqual(self.ask(0.9, "text-model"), 240)
        self.assertEqual(self.ask(0.1, "vision-model"), 240 * ai.SLOW_TIMES)
        self.assertEqual(self.ask(None, "text-model"), 240)

    def test_no_ollama_to_ask(self):
        with mock.patch.object(ai, "_api", side_effect=OSError("no Ollama")):
            self.assertIsNone(ai.on_card_share("text-model"))
            self.assertEqual(ai.time_factor("text-model"), ai.SLOW_TIMES)


if __name__ == "__main__":
    unittest.main()
