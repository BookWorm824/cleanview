"""Sending "what CleanView learned" files to the CleanView inbox (cleanview_learn.send),
so nobody has to attach them in a chat. A little web server on this PC stands in for the
Google script: like Google, it answers the POST with a redirect to where the reply is."""
import json
import os
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import support
import cleanview_learn as learn


class Inbox(BaseHTTPRequestHandler):
    got, answer = [], {"ok": True}

    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        Inbox.got.append((self.headers["Content-Type"], json.loads(body)))
        self.send_response(302)                       # Google's way: the reply is elsewhere
        self.send_header("Location", "/reply")
        self.end_headers()

    def do_GET(self):
        out = json.dumps(Inbox.answer).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *a):
        pass


def start_inbox():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Inbox)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_port}/exec"


class Send(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.server, cls.url = start_inbox()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        Inbox.got.clear()
        Inbox.answer = {"ok": True}
        self.file = support.SANDBOX / "CleanView learned 2026-10-28.json"
        self.file.write_text(json.dumps({"date": "2026-10-28", "shows": {"castle": {}}}),
                             encoding="utf8")
        os.environ["CLEANVIEW_INBOX"] = self.url

    def tearDown(self):
        os.environ.pop("CLEANVIEW_INBOX", None)

    def test_sent_as_the_inbox_expects(self):
        learn.send(self.file, "learned")
        (kind, msg), = Inbox.got
        self.assertEqual(kind, "application/json")
        self.assertEqual(msg, {"app": "CleanView", "kind": "learned",
                               "name": "CleanView learned 2026-10-28.json",
                               "data": {"date": "2026-10-28", "shows": {"castle": {}}}})

    def test_inbox_saying_no_is_an_error(self):
        Inbox.answer = {"ok": False, "why": "not from CleanView or CleanListen"}
        with self.assertRaisesRegex(RuntimeError, "didn't take it"):
            learn.send(self.file, "learned")

    def test_no_inbox_yet(self):
        os.environ.pop("CLEANVIEW_INBOX")
        if learn.SEND_URL:
            self.skipTest("the inbox's address is built in")
        with self.assertRaisesRegex(RuntimeError, "isn't set up yet"):
            learn.send(self.file, "learned")

    def test_no_internet(self):
        os.environ["CLEANVIEW_INBOX"] = "http://127.0.0.1:9/exec"     # nothing listens there
        with self.assertRaises(OSError):
            learn.send(self.file, "learned")

    def test_too_big_is_not_sent(self):
        self.file.write_text(json.dumps({"x": "a" * learn.MAX_SEND}), encoding="utf8")
        with self.assertRaisesRegex(RuntimeError, "too big"):
            learn.send(self.file, "learned")
        self.assertEqual(Inbox.got, [])


if __name__ == "__main__":
    unittest.main()
