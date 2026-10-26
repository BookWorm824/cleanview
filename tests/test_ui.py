"""The window (CleanView.pyw), driven on the made-up sample review. Message
boxes are replaced so nothing waits for a click; a CleanView window may flash
up for a moment while these run. Skipped where there's no screen to draw on."""
import importlib.machinery
import importlib.util
import json
import tkinter as tk
import types
import unittest

import support

_loader = importlib.machinery.SourceFileLoader("cleanview_ui", str(support.ROOT / "CleanView.pyw"))
ui = importlib.util.module_from_spec(importlib.util.spec_from_loader("cleanview_ui", _loader))
_loader.exec_module(ui)

UNTICKED, TICKED = "☐", "☑"


class PlainErrors(unittest.TestCase):

    def test_technical_detail_left_out(self):
        ex = RuntimeError("Couldn't save the clean copy of x.mp4:\n[mp4 @ 0x1] Error opening")
        self.assertEqual(ui.plain_error(ex), "Couldn't save the clean copy of x.mp4.")

    def test_starts_with_a_capital(self):
        self.assertEqual(ui.plain_error(RuntimeError("couldn't read the sound")),
                         "Couldn't read the sound.")

    def test_file_in_use(self):
        self.assertIn("open in another program", ui.plain_error(PermissionError(13, "denied")))

    def test_drive_full(self):
        self.assertTrue(ui.plain_error(OSError(28, "No space")).startswith("The drive is full"))

    def test_python_errors_not_shown(self):
        self.assertEqual(ui.plain_error(KeyError("scenes")), "Something unexpected went wrong.")

    def test_claude_and_chatgpt_messages_kept(self):
        for ex in (ui.cc.ClaudeError("Claude took too long to answer. Try again."),
                   ui.cc.gpt.GptError("ChatGPT took too long to answer. Try again.")):
            self.assertEqual(ui.plain_error(ex), str(ex))


class Window(unittest.TestCase):
    """One window for all these tests, opened on the sample review."""

    @classmethod
    def setUpClass(cls):
        cls.said, cls.answer = [], {"yes": False}
        mb = ui.messagebox
        cls.saved_mb = {k: getattr(mb, k) for k in ("showwarning", "showerror", "showinfo", "askyesno")}
        mb.showwarning = lambda t, m, **k: cls.said.append(("warn", m))
        mb.showerror = lambda t, m, **k: cls.said.append(("error", m))
        mb.showinfo = lambda t, m, **k: cls.said.append(("info", m))
        mb.askyesno = lambda t, m, **k: cls.said.append(("ask", m)) or cls.answer["yes"]
        ui.App._check_update = lambda self, manual=False: None     # no looking online
        cls.work = support.write_review()
        try:
            cls.app = ui.App()
        except tk.TclError as ex:
            raise unittest.SkipTest(f"no screen to draw on ({ex})")
        cls.app.update()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.app.destroy()
        except tk.TclError:
            pass
        for k, f in cls.saved_mb.items():
            setattr(ui.messagebox, k, f)

    def setUp(self):
        self.said.clear()
        self.answer["yes"] = False
        support.write_review()
        self.assertTrue(self.app._resume(), "the sample review opens")
        self.app.update()

    # --- a bad message mustn't stop the window updating
    def test_bad_message_reported_and_polling_goes_on(self):
        app = self.app
        before = set(app.tk.call("after", "info"))
        app.q.put(("rendered",))                    # missing parts: fails inside the handler
        app.q.put(("which", "still handled"))
        app._poll()
        self.assertTrue(any("still running" in m for _, m in self.said))
        self.assertTrue(ui.ERROR_FILE.exists(), "details saved to a file")
        self.assertTrue(set(app.tk.call("after", "info")) - before, "polling carries on")

    # --- saving a whole season
    def result(self):
        return {"cut_minutes": 1.0, "mutes": 3, "cuts": 1, "folder": str(support.SANDBOX),
                "out": str(support.SANDBOX)}

    def test_nothing_saved_goes_back_to_review(self):
        self.app._rendered([], ["Episode 4.mp4: The drive is full."])
        self.assertEqual(self.app.page_name, "review")
        self.assertIn("try again", self.said[-1][1])

    def test_some_saved_keeps_review_for_the_rest(self):
        self.app._rendered([self.result()], ["Episode 5.mp4: Something unexpected went wrong."])
        self.assertEqual(self.app.page_name, "done")
        self.assertTrue(self.app.SESSION.exists())

    def test_all_saved_forgets_review(self):
        self.app._rendered([self.result()], [])
        self.assertEqual(self.app.page_name, "done")
        self.assertFalse(self.app.SESSION.exists())
        self.assertEqual(self.said, [])

    # --- All dialogue tab
    def dialogue_tab(self):
        self.app.show_review(tab=1)
        self.app.update()
        return self.app.dlg_tv

    def click(self, tv, row, col):
        tv.see(row)
        self.app.update()
        x, y, w, h = tv.bbox(row, col)
        self.app._dlg_click(types.SimpleNamespace(x=x + w // 2, y=y + h // 2, state=0))
        self.app.update()

    def test_only_the_mute_box_mutes(self):
        tv = self.dialogue_tab()
        self.assertEqual(tv.set("1", "mute"), UNTICKED)
        self.click(tv, "1", "#4")
        self.assertEqual(tv.set("1", "mute"), UNTICKED, "clicking the words only picks the line")
        self.click(tv, "1", "#1")
        self.assertEqual(tv.set("1", "mute"), TICKED)
        self.assertIn("muted", tv.item("1", "tags"))
        self.click(tv, "1", "#1")
        self.assertEqual(tv.set("1", "mute"), UNTICKED)

    def test_flagged_lines_show_ticked(self):
        tv = self.dialogue_tab()
        self.assertEqual(tv.set("7", "mute"), TICKED)

    def test_space_mutes_the_picked_lines(self):
        tv = self.dialogue_tab()
        tv.selection_set(["2", "3"])
        self.app._dlg_space()
        self.app.update()
        self.assertEqual((tv.set("2", "mute"), tv.set("3", "mute")), (TICKED, TICKED))
        self.assertEqual(set(tv.selection()), {"2", "3"}, "the picked lines stay picked")

    def test_mute_word_needs_one_line(self):
        tv = self.dialogue_tab()
        tv.selection_set([])
        self.app._mute_word_selected()
        self.assertEqual(self.said[-1], ("info", "Click one line first, then try again."))

    # --- closing while busy
    def test_closing_while_working_asks_first(self):
        app = self.app
        app.page_name = "working"
        app.cancel_flag = False
        app._on_close()
        app.update()
        self.assertEqual(self.said[-1][0], "ask")
        self.assertTrue(app.winfo_exists())
        self.assertFalse(app.cancel_flag)
        saved, app.destroy = app.destroy, lambda: None     # keep the window for the other tests
        try:
            self.answer["yes"] = True
            app._on_close()
            self.assertTrue(app.cancel_flag, "closing anyway stops the work first")
        finally:
            app.destroy = saved
            app.cancel_flag = False

    def test_closing_the_review_saves_it(self):
        self.app.SESSION.unlink()
        saved, self.app.destroy = self.app.destroy, lambda: None
        try:
            self.app._on_close()
        finally:
            self.app.destroy = saved
        self.assertTrue(json.loads(self.app.SESSION.read_text("utf8"))["jobs"])


if __name__ == "__main__":
    unittest.main()
