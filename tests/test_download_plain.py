"""A download of an AI helper that breaks off (1.18.165; the owner's screenshot: "Couldn't
download the picture helper: max retries exceeded: read tcp [2603:...]: wsarecv: An existing
connection was forcibly closed by the remote host."): said in plain words, and tried again."""
import unittest

import support  # noqa: F401  (must come first)
import cleanview_ai as ai

RAW = ("max retries exceeded: read tcp [2603:900b:b800:7560:2810:d426:b598:30b1]:54187->"
       "[2606:4700::1]:443: wsarecv: An existing connection was forcibly closed by the remote "
       "host.")


class Plain(unittest.TestCase):
    def test_no_jargon(self):
        msg = ai.plain_download_error("the picture helper", RAW)
        self.assertIn("internet connection dropped", msg)
        for jargon in ("tcp", "wsarecv", "2603", "retries"):
            self.assertNotIn(jargon, msg)

    def test_tried_again(self):
        calls, waits = [], []
        real_pull, real_sleep = ai.pull_model, ai.time.sleep

        def pull(name, say, label):
            calls.append(name)
            if len(calls) < 3:
                raise RuntimeError(ai.plain_download_error(label, RAW))
        ai.pull_model, ai.time.sleep = pull, waits.append
        try:
            ai.pull_with_retries("m", lambda f, m: None, "the picture helper")
        finally:
            ai.pull_model, ai.time.sleep = real_pull, real_sleep
        self.assertEqual(len(calls), 3)
        self.assertEqual(waits, list(ai.PULL_WAITS))

    def test_other_trouble_not_retried(self):
        calls = []
        real = ai.pull_model

        def pull(name, say, label):
            calls.append(name)
            raise RuntimeError("model not found")
        ai.pull_model = pull
        try:
            with self.assertRaises(RuntimeError):
                ai.pull_with_retries("m", lambda f, m: None, "the picture helper")
        finally:
            ai.pull_model = real
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
