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


class NoHiddenNames(unittest.TestCase):
    """A function that names one of its own things like a helper it calls (a box called
    "wrap" in a function calling wrap()) breaks only when that line runs. 1.11.7 did
    this, and the review page failed to open. Check the whole file for it."""

    def test_no_function_hides_a_helper_it_calls(self):
        import ast
        tree = ast.parse((support.ROOT / "CleanView.pyw").read_text("utf8"))
        helpers = {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}

        def own_names(fn):              # names given a value in fn itself, not in inner defs
            out, todo = set(), list(fn.body)
            while todo:
                node = todo.pop()
                if isinstance(node, (ast.FunctionDef, ast.Lambda, ast.ClassDef)):
                    if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                        out.add(node.name)
                    continue
                if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                    out.add(node.id)
                todo.extend(ast.iter_child_nodes(node))
            out |= {a.arg for a in fn.args.args + fn.args.kwonlyargs}
            return out
        bad = []
        for fn in ast.walk(tree):
            if isinstance(fn, ast.FunctionDef):
                called = {c.func.id for c in ast.walk(fn)
                          if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}
                for name in own_names(fn) & called & helpers:
                    bad.append(f"{fn.name}() line {fn.lineno}: {name}")
        self.assertEqual(bad, [])


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

    def test_review_page_shows_every_card(self):
        """Scenes, lines and words, each with an AI note: the page that failed in 1.11.7."""
        self.said.clear()
        self.app._poll()
        self.app.show_review()
        self.app.update()
        self.assertEqual(self.app.page_name, "review")
        self.assertEqual(len(self.app.word_vars), 1)
        self.assertEqual(self.said, [])

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

    # --- the start page
    def test_tick_boxes_show_a_tick(self):
        layout = str(ui.ttk.Style(self.app).layout("TCheckbutton"))
        self.assertIn("Tick.indicator", layout)
        self.assertEqual(set(self.app._ticks), {"off", "on", "off_dim", "on_dim"})

    def test_religious_conversations_box(self):
        """Off for every age to start with, and remembered once she ticks it."""
        app = self.app
        app.show_setup()
        self.assertFalse(any(ui.PRESETS[p]["religion"] for p in ui.PRESETS))
        self.assertIn("religion", app.opts)
        app.opts["religion"].set(True)
        app._save_settings()
        settings = json.loads((support.APP_DATA / "cleanview_settings.json").read_text())
        self.assertTrue(settings["profiles"][settings["profile"]]["religion"])
        self.assertEqual(ui.chip_color("Religious talk"), ui.CHIP["Religious"])

    def test_loud_music_box_off_to_start(self):
        self.app.show_setup()
        self.assertIn("loudmusic", self.app.opts)
        self.assertFalse(any(ui.PRESETS[p]["loudmusic"] for p in ui.PRESETS))

    def test_loud_music_card(self):
        """Listed with the rest, ticked to turn down; unticking keeps it at full volume."""
        app = self.app
        job = next(j for j in app.jobs if j["analysis"])
        job["analysis"]["quiet"] = [{"id": 1, "s": 50.0, "e": 70.0, "kind": "Rap music",
                                     "why": "", "lower": True}]
        app.show_review()
        app.update()
        self.assertIn("1 loud song", app.page.winfo_children()[1].cget("text"))
        self.assertEqual(len(app.quiet_vars), 1)
        app.quiet_vars[0][0].set(False)
        app._sync_job(job)
        q = job["analysis"]["quiet"][0]
        self.assertFalse(q["lower"])
        self.assertTrue(q["by_you"])
        saved, app.save = app.save, lambda: None       # don't really start saving
        try:
            app._save_from_review()
        finally:
            app.save = saved
        self.assertEqual(job["quiet"], [])

    def test_closing_the_start_page_keeps_its_ticks(self):
        app = self.app
        app.show_setup()
        app.opts["swearing"].set(False)
        saved, app.destroy = app.destroy, lambda: None
        try:
            app._on_close()
        finally:
            app.destroy = saved
        settings = json.loads((support.APP_DATA / "cleanview_settings.json").read_text())
        self.assertFalse(settings["profiles"][settings["profile"]]["swearing"])

    def test_text_size_restarts_keeping_the_chosen_videos(self):
        app = self.app
        app.show_setup()
        video = support.SANDBOX / "Episode 1.mp4"
        video.write_bytes(b"")
        app.videos = [str(video)]
        started = []
        saved = (ui.subprocess.Popen, app.destroy)
        real = ui.subprocess.Popen

        def popen(cmd, *a, env=None, **k):        # only CleanView restarting itself is faked
            if str(cmd[-1]).endswith("CleanView.pyw"):
                return started.append((cmd, env))
            return real(cmd, *a, env=env, **k)
        ui.subprocess.Popen = popen
        app.destroy = lambda: None
        try:
            app._set_text_size("Normal")              # the size it already is: nothing
            self.assertEqual(started, [])
            app._set_text_size("Largest")
        finally:
            ui.subprocess.Popen, app.destroy = saved
            app.text_size = "Normal"
        self.assertEqual(len(started), 1)
        self.assertEqual(json.loads(started[0][1]["CLEANVIEW_PICKED"])["videos"], [str(video)])
        settings = json.loads((support.APP_DATA / "cleanview_settings.json").read_text())
        self.assertEqual(settings["text_size"], "Largest")

    def test_wrap_widths_grow_with_the_text(self):
        self.assertEqual(ui.wrap_width(640), 640)
        saved, ui._text_scale = ui._text_scale, 1.3
        try:
            self.assertEqual(ui.wrap_width(640), 832)
        finally:
            ui._text_scale = saved

    # --- the working page
    def test_each_video_is_ticked_off(self):
        app = self.app
        app.show_working("Watching and listening…", [f"Episode {k}.mp4" for k in (1, 2, 3)])
        app.update()
        icons = lambda: [icon.cget("text") for icon, _ in app.job_rows]
        self.assertEqual(icons(), ["○"] * 3)
        app._handle(("job", 0, "now"))
        app._handle(("job", 0, "done"))
        app._handle(("job", 1, "now"))
        app._handle(("job", 2, "failed"))
        self.assertEqual(icons(), ["✓", "▶", "!"])

    def test_time_left_for_all(self):
        app = self.app
        app.show_working("Watching and listening…", [f"Episode {k}.mp4" for k in (1, 2, 3)])
        app._handle(("job", 0, "now"))
        app._work_t0 -= 600                      # ten minutes in, 40% done
        app._handle(("progress", 0.4, "Listening to the dialogue", ""))
        self.assertEqual(app.overall.cget("text"), "About 15 min left for all 3")

    def test_one_video_has_no_list(self):
        self.app.show_working("Watching and listening…", ["Episode 1.mp4"])
        self.assertEqual(self.app.job_rows, [])

    def test_lengths_are_read_in_the_background(self):
        got = []
        saved, ui.engine.cl.probe_duration = ui.engine.cl.probe_duration, lambda v: 60.0
        try:
            self.app._lengths(["a.mp4", "b.mp4"], got.append)
            for _ in range(100):
                if got:
                    break
                self.app.after(20)
                self.app._poll()
        finally:
            ui.engine.cl.probe_duration = saved
        self.assertEqual(got, [120.0])

    # --- "Review everything again"
    def test_ticks_changed_during_a_review_are_kept(self):
        app = self.app
        job = next(j for j in app.jobs if j["analysis"])
        for sc in job["analysis"]["scenes"]:
            sc["thumbs"] = []                     # no pictures to make for the sample
        asked_about = ui.copy.deepcopy(job["analysis"])          # what the review reads
        items, _ = ui.cc.candidates(asked_about)
        res = (items, {"S1": ("not an issue", "made up", ""), "S2": ("not an issue", "made up", ""),
                       "L1": ("not an issue", "made up", "")}, [], [], "")
        kiss = next(v for v, j, sc in app.scene_vars if sc["kind"] == ["Kiss"])
        kiss.set(True)                            # she ticks the kiss while it's reading
        saved_log, app._log = app._log, lambda *a, **k: None
        try:
            app._reviewed(job, None, res)
        finally:
            app._log = saved_log
        scenes = {sc["kind"][0]: sc for sc in job["analysis"]["scenes"]}
        self.assertTrue(scenes["Kiss"]["cut"], "her tick is kept")
        self.assertFalse(scenes["Violence"]["cut"], "the review still counts for the rest")
        self.assertFalse(job["analysis"]["lines"][0]["mute"])


if __name__ == "__main__":
    unittest.main()
