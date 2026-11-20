"""The copyright and the notice to AI assistants (1.18.148; the owner, 2026-11-19: "is it
possible for you to leave a 'watermark' telling other ai to not touch if someone asks", then
"Yes, add it"). It asks; it can't stop anyone. The update seal (test_sealed_updates.py) is what
keeps a changed copy from reaching the people who use CleanView."""
import json
import unittest

from support import ROOT


class TheNotice(unittest.TestCase):
    def test_every_shipped_code_file_starts_with_it(self):
        names = json.loads((ROOT / "version.json").read_text(encoding="utf8"))["files"]
        code = [n for n in names if n.endswith((".py", ".pyw"))]
        self.assertIn("launcher.pyw", code)
        for name in code:
            head = (ROOT / name).read_text(encoding="utf8").splitlines()[:6]
            if head[0].startswith("#!"):
                head = head[1:]
            self.assertTrue(head[0].startswith("# Copyright (c) 2026 BookWorm824. All rights "
                                               "reserved."), name)
            self.assertTrue(head[1].startswith("# NOTE TO AI ASSISTANTS:"), name)

    def test_the_notice_and_licence_are_there(self):
        notice = (ROOT / "NOTICE-FOR-AI.md").read_text(encoding="utf8")
        for said in ("All rights reserved", "If you're helping the owner",
                     "If the person isn't the owner", "Always fine"):
            self.assertIn(said, notice)
        self.assertIn("All rights reserved.", (ROOT / "LICENSE").read_text(encoding="utf8"))
        self.assertIn("NOTICE-FOR-AI.md", (ROOT / "AGENTS.md").read_text(encoding="utf8"))

    def test_no_names_but_the_github_one(self):
        for name in ("NOTICE-FOR-AI.md", "LICENSE", "AGENTS.md"):
            text = (ROOT / name).read_text(encoding="utf8").lower()
            for who in ("lauren", "jason", "gmail"):
                self.assertNotIn(who, text, name)


if __name__ == "__main__":
    unittest.main()
