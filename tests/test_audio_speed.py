"""The listening and the sound check, faster with the same results (the owner, 2026-11-09:
"lets do the audio now", then "Just 1 and 3"): two listeners take turns on the 30-second parts
when the PC has the threads and memory, and the sound check runs during the listening."""
import inspect
import threading
import time
import types
import unittest
from unittest import mock

import numpy as np

import support  # noqa: F401  (sets up the sandbox first)
import cleanview as engine

SR = engine.SR


class FakeRecognizer:
    """Hears one word per part, named after the part, a little slowly."""

    def __init__(self, name):
        self.name, self.used, self.busy = name, 0, threading.Lock()

    def create_stream(self):
        return types.SimpleNamespace(seg=None, result=None,
                                     accept_waveform=lambda sr, seg: None)

    def decode_stream(self, s):
        assert self.busy.acquire(blocking=False), "one part at a time per listener"
        try:
            time.sleep(0.05)
            self.used += 1
            s.result = types.SimpleNamespace(tokens=[" word"], timestamps=[5.0], durations=[0.3])
        finally:
            self.busy.release()


def parts(n=9):
    return [(k * 28.0, np.zeros(int(SR * 30)), k == n - 1) for k in range(n)]


def hear(recs, n=9):
    info = {"audio": {"channels": 2}}
    seen = []
    with mock.patch.object(engine, "_stream_chunks", lambda *a, **k: iter(parts(n))), \
            mock.patch.object(engine, "_audio_cmd", lambda *a: []):
        words = engine.transcribe("v.mp4", info, recs, seen.append)
    return words, seen


class TwoListeners(unittest.TestCase):

    def test_same_words_in_the_same_order(self):
        one, _ = hear(FakeRecognizer("a"))
        two, _ = hear([FakeRecognizer("a"), FakeRecognizer("b")])
        self.assertEqual(one, two)
        self.assertEqual([w["s"] for w in two], [k * 28.0 + 5.0 for k in range(9)])

    def test_both_take_turns(self):
        a, b = FakeRecognizer("a"), FakeRecognizer("b")
        hear([a, b])
        self.assertEqual(a.used + b.used, 9)
        self.assertGreater(min(a.used, b.used), 0)

    def test_progress_in_order(self):
        _, seen = hear([FakeRecognizer("a"), FakeRecognizer("b")])
        self.assertEqual(seen, sorted(seen))
        self.assertEqual(len(seen), 9)

    def test_only_with_room(self):
        self.assertEqual(engine.how_many_listeners(8, 8.0), (2, 4))
        self.assertEqual(engine.how_many_listeners(7, 8.0), (2, 3))
        self.assertEqual(engine.how_many_listeners(5, 8.0), (1, 5))     # few threads
        self.assertEqual(engine.how_many_listeners(8, 2.0), (1, 8))     # little memory
        self.assertEqual(engine.how_many_listeners(None, 8.0), (1, 1))

    def test_free_memory_is_told(self):
        self.assertGreaterEqual(engine.available_memory_gb(), 0)


class SoundCheckMeanwhile(unittest.TestCase):

    def test_started_before_the_listening(self):
        src = inspect.getsource(engine.analyze)
        self.assertLess(src.index("snd_job = in_background(check_sounds)"),
                        src.index("asr = transcribe("))
        self.assertIn("load_tagger(2)", src)
        self.assertLess(src.index("asr = transcribe("), src.index("wait_for(snd_job"))

    def test_on_its_own_when_the_words_were_heard_before(self):
        src = inspect.getsource(engine.analyze)
        self.assertIn("if snd is None and not tfile.exists():", src)
        self.assertIn("snd = sound_scan(path, info, tagger, p_snd, cancel)", src)


if __name__ == "__main__":
    unittest.main()
