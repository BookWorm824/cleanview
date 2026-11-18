"""She picks which Claude model CleanView uses (1.18.130; the owner, 2026-11-18: "I need to be
able to select what model I use (fable should NEVER be a default)"). Sonnet, Opus or Haiku, on
the start page under "Who reads the dialogue" when Claude is picked; Sonnet unless she picks
another; anything else (an old setting, Fable) is Sonnet. The model goes to `claude --model`,
is remembered, and reaches the scan."""
import json
import types
import unittest
import tkinter as tk

import support  # noqa: F401  (must come first)
import test_ui

ui = test_ui.ui
cc = ui.cc
engine = ui.engine
look = ui.look


class Models(unittest.TestCase):
    def setUp(self):
        self.was = cc.MODEL

    def tearDown(self):
        cc.MODEL = self.was

    def test_the_choices(self):
        self.assertEqual([k for k, _ in cc.MODELS], ["sonnet", "opus", "haiku"])
        self.assertEqual(cc.DEFAULT_MODEL, "sonnet")
        self.assertNotIn("fable", " ".join(k + n for k, n in cc.MODELS).lower())

    def test_never_fable(self):
        for m in ("fable", "Fable", "claude-fable-5-2", "", None, "gpt-5", "best"):
            self.assertEqual(cc.pick_model(m), "sonnet", m)
            self.assertEqual(cc.set_model(m), "sonnet", m)
        self.assertEqual(cc.pick_model(" Opus "), "opus")
        self.assertEqual(cc.model_name("haiku"), "Haiku")

    def test_sent_to_claude(self):
        got = []

        def run(cmd, **kw):
            got.append(cmd)
            return types.SimpleNamespace(returncode=0, stderr="", stdout=json.dumps(
                {"structured_output": {"ok": True}, "session_id": "s"}))
        saved = cc.subprocess.run, cc.find_claude, cc.PROVIDER
        cc.subprocess.run, cc.find_claude = run, lambda: "claude"
        cc.use("claude")
        try:
            for m in ("opus", "haiku", "fable"):
                cc.set_model(m)
                cc._ask_now("hi", {"type": "object"})
                cmd = got[-1]
                self.assertEqual(cmd[cmd.index("--model") + 1], cc.pick_model(m))
        finally:
            cc.subprocess.run, cc.find_claude, _ = saved
            cc.use(saved[2])


class OnTheStartPage(unittest.TestCase):
    def setUp(self):
        self.saved = ui.App._check_update, ui.App._check_every_ai, ui.App.check_claude, cc.MODEL
        ui.App._check_update = lambda self, manual=False: None
        ui.App._check_every_ai = lambda self: None
        ui.App.check_claude = lambda self, provider=None: None

    def tearDown(self):
        ui.App._check_update, ui.App._check_every_ai, ui.App.check_claude, cc.MODEL = self.saved

    def app(self):
        try:
            return ui.App()
        except tk.TclError as ex:
            raise unittest.SkipTest(f"no screen to draw on ({ex})")

    def test_picker(self):
        app = self.app()
        try:
            o = app.opts
            self.assertEqual(o["claude_model"].get(), "sonnet")
            pickers = []

            def walk(w):
                for c in w.winfo_children():
                    if isinstance(c, look.Segmented) and c.var is o["claude_model"]:
                        pickers.append(c)
                    walk(c)
            walk(app)
            self.assertEqual(len(pickers), 1)
            self.assertEqual([k for k, _ in pickers[0].options], ["sonnet", "opus", "haiku"])

            o["reader"].set("local")
            app.update()
            self.assertEqual(app.model_row.winfo_manager(), "")       # only for Claude
            o["reader"].set("claude")
            app.update()
            self.assertEqual(app.model_row.winfo_manager(), "pack")
            o["reader"].set("chatgpt")
            app.update()
            self.assertEqual(app.model_row.winfo_manager(), "")
            o["reader"].set("claude")
            app.update()

            o["claude_model"].set("opus")
            self.assertEqual(cc.MODEL, "opus")
            self.assertEqual(app._current_opts()["claude_model"], "opus")
            self.assertEqual(app._step_summary(3), "Claude (Opus)")
            app._save_settings()
            self.assertEqual(app._load_settings()["claude_model"], "opus")
        finally:
            app.destroy()

        cc.MODEL = "sonnet"
        app = self.app()                                   # remembered next time
        try:
            self.assertEqual(app.opts["claude_model"].get(), "opus")
            self.assertEqual(cc.MODEL, "opus")
            app.opts["claude_model"].set("sonnet")
            app._save_settings()
        finally:
            app.destroy()

    def test_old_setting_is_sonnet(self):
        app = self.app()
        try:
            app.opts["reader"].set("local")
            app._save_settings()
            path = ui.APP_DATA / "cleanview_settings.json"
            d = json.loads(path.read_text())
            d["claude_model"] = "fable"
            path.write_text(json.dumps(d))
        finally:
            app.destroy()
        app = self.app()
        try:
            self.assertEqual(app.opts["claude_model"].get(), "sonnet")
            self.assertEqual(cc.MODEL, "sonnet")
        finally:
            app.destroy()


class InTheScan(unittest.TestCase):
    def test_scan_uses_her_pick(self):
        src = open(engine.__file__, encoding="utf8").read()
        self.assertEqual(src.count('cc.set_model(o.get("claude_model"))'), 2)
        # not one of the choices that make a saved scan "different"
        self.assertNotIn("claude_model", engine.DEFAULTS)


if __name__ == "__main__":
    unittest.main()
