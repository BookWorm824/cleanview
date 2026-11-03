"""Noticing a freeze or a crash (Jason, 2026-11-03: CleanView stopped responding during a
movie and didn't say why), and a window that a flood of progress messages can't keep busy."""
import importlib.machinery
import importlib.util
import json
import queue
import types
import unittest
from unittest import mock

import support

_loader = importlib.machinery.SourceFileLoader("cleanview_ui_freeze",
                                               str(support.ROOT / "CleanView.pyw"))
ui = importlib.util.module_from_spec(importlib.util.spec_from_loader(_loader.name, _loader))
_loader.exec_module(ui)


def fake_app(**kw):
    app = types.SimpleNamespace(q=queue.Queue(), handled=[], afters=[], page_name="working",
                                _doing={}, _gone=False, _poll=None, **kw)
    app._handle = app.handled.append
    app.after = lambda ms, fn=None: app.afters.append(ms)
    app._problem = lambda *a: None
    return app


class Poll(unittest.TestCase):
    def test_a_flood_of_progress_cant_keep_the_window_busy(self):
        app = fake_app()
        for i in range(2000):
            app.q.put(("progress", i / 2000, f"step {i}", ""))
        app.q.put(("which", "Video 1 of 1"))
        ui.App._poll(app)
        self.assertEqual(app.handled, [("progress", 499 / 2000, "step 499", "")])
        self.assertEqual(app.afters, [10])            # straight back for the rest

    def test_everything_else_is_handled_in_order(self):
        app = fake_app()
        for m in (("which", "a"), ("progress", 0.1, "x", ""), ("job", 0, "now"),
                  ("progress", 0.2, "y", ""), ("analyzed",)):
            app.q.put(m)
        ui.App._poll(app)
        self.assertEqual([m[0] for m in app.handled], ["which", "job", "progress", "analyzed"])
        self.assertEqual(app.handled[2][2], "y")
        self.assertEqual(app.afters, [150])


class Freeze(unittest.TestCase):
    def setUp(self):
        for f in (ui.PROBLEM_NOTE, ui.CRASH_LOG, ui.PROBLEM_NOTE.with_name("stopped_before.txt")):
            f.unlink(missing_ok=True)

    def test_a_freeze_notes_what_every_part_was_doing(self):
        app = fake_app()
        app._doing.update(which="Video 2 of 3:  Castle S01E02", status="Listening… 40%")
        ui.App._note_freeze(app, 25)
        note = ui.PROBLEM_NOTE.read_text(encoding="utf8")
        self.assertIn("stopped answering for 25 seconds", note)
        self.assertIn("Page: working", note)
        self.assertIn("Doing: Video 2 of 3:  Castle S01E02 Listening… 40%", note)
        self.assertIn("--- MainThread ---", note)
        self.assertIn("test_a_freeze_notes_what_every_part_was_doing", note)

    def test_a_crash_last_time_is_kept_for_sending(self):
        ui.APP_DATA.mkdir(parents=True, exist_ok=True)
        ui.CRASH_LOG.write_text("Windows fatal exception: access violation\n", encoding="utf8")
        app = fake_app()
        with mock.patch.object(ui.threading, "Thread"):
            ui.App._watch_for_freezes(app)
        import faulthandler
        faulthandler.disable()
        app._crash_log.close()
        note = ui.PROBLEM_NOTE.read_text(encoding="utf8")
        self.assertTrue(note.startswith("CleanView closed suddenly."))
        self.assertIn("access violation", note)
        self.assertEqual(ui.CRASH_LOG.read_text(encoding="utf8"), "")   # ready for this time

    def test_sent_in_next_time_if_she_says_yes(self):
        ui.APP_DATA.mkdir(parents=True, exist_ok=True)
        ui.PROBLEM_NOTE.write_text("CleanView 1.18.9 stopped answering for 30 seconds.",
                                   encoding="utf8")
        app = fake_app()
        sent = []
        with mock.patch.object(ui.messagebox, "askyesno", return_value=True) as ask, \
                mock.patch.object(ui.learn, "send", lambda p, k: sent.append((p, k))), \
                mock.patch.object(ui.threading, "Thread",
                                  lambda target, daemon: types.SimpleNamespace(start=target)):
            ui.App._offer_problem_note(app)
        self.assertIn("stopped responding last time", ask.call_args[0][1])
        (path, kind), = sent
        self.assertEqual(kind, "problem")
        data = json.loads(path.read_text(encoding="utf8"))
        self.assertEqual(data["what"], "stopped responding")
        self.assertIn("30 seconds", data["note"])
        self.assertFalse(ui.PROBLEM_NOTE.exists())       # asked once, not every time

    def test_not_asked_when_nothing_happened(self):
        app = fake_app()
        with mock.patch.object(ui.messagebox, "askyesno") as ask:
            ui.App._offer_problem_note(app)
        ask.assert_not_called()


if __name__ == "__main__":
    unittest.main()
