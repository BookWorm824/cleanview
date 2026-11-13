"""Only what's about the video on the review page (1.18.82; the owner, 2026-11-13: "in the after
report that is visible in clean view after cleaning a video, you are able to see the qwen
version and timers and such. i dont care if that in the report to send to you, but not visbible
to all. just keep things relative to the video,; the scenes cut, words muted etc.").

Then, asked whether they should stay in the report file beside the clean copy: "i only want you
to know what is being used"; and told a report file would then no longer say the version or
the times: "i want you to know pertinent information of the report. if you need to put some
things back on the report for you is good" (1.18.83). So notes about how the scan went are off
the review page; they stay in the saved review, in "Send what we refined", and are the last
lines of the report file, under a heading that says who they're for."""
import json
import tempfile
import unittest
import tkinter as tk
from pathlib import Path

import support
import test_timing as T
import cleanview as engine
from test_ui import ui

TECHNICAL = [
    "Checked with: listening to the dialogue, sound check, nudity check, picture AI, AI helper.",
    "The AI helper used qwen3-vl:8b-instruct for the picture and qwen3:8b for the dialogue "
    "(CleanView 1.18.82).",
    "Voices: 102 speakers told apart; man/woman/child guessed for 1007 of 1362 lines.",
    "The AI helper took a closer look at 12 scene(s): 3 kept, 9 dropped.",
    "Nudity check: 2 false alarm(s) dropped, 1 scene(s) only implied nudity (listed as implied).",
    "Dialogue was checked with Claude.",
    "Claude looked through the whole picture (3020 stills): it confirmed 1 scene(s), ruled out "
    "0 false alarm(s) and found 0 the other checks missed.",
    "ChatGPT looked through the whole picture (700 stills): it confirmed 2 scene(s).",
    "Took 14 min: listening 1.8, picture scan 4.3, reading the dialogue 6.0 (minutes).",
    "Took under a minute: closer look 0.1, voices 0.2 (minutes).",
]
ABOUT_THE_VIDEO = [
    "No subtitles: none were found online.",
    "Subtitles were found online but didn't match this video (22% of words lined up), so they "
    "weren't used.",
    "The subtitles leave out some of the talking (from 0:59:10), so what was heard is used there.",
    "The picture AI isn't installed, so kissing, gore, smoking and the like weren't looked for.",
    "No AI read the dialogue, so the dialogue choices (jokes, bullying, magic talk and the "
    "like) were only checked against a short list of phrases.",
    "The AI helper wasn't running, so scenes weren't double-checked and the dialogue wasn't read.",
    "Claude couldn't read the dialogue this time: it isn't signed in.",
    "Claude couldn't look at the picture this time (timed out).",
    "Voices couldn't be told apart this time (out of memory).",
    "Loud music: 2 stretch(es) of hard rock, metal or rap with nobody talking will be turned down.",
    "Muted just the word in 3 line(s) the word list found (sexual references).",
    "Claude reviewed everything: 7 found item(s) look fine in context and were unticked.",
    "Cleaned as a Spanish video, with the Spanish word lists.",
    "You usually keep Kiss scenes in this show, so they start unticked.",
]


def mixed():
    """The notes as a scan leaves them: the two kinds in among each other."""
    out = []
    for i in range(max(len(TECHNICAL), len(ABOUT_THE_VIDEO))):
        out += TECHNICAL[i:i + 1] + ABOUT_THE_VIDEO[i:i + 1]
    return out


class WhichNotes(unittest.TestCase):
    def test_how_the_scan_went_is_technical(self):
        for note in TECHNICAL:
            self.assertTrue(engine.technical(note), note)

    def test_what_it_means_for_the_video_is_not(self):
        for note in ABOUT_THE_VIDEO:
            self.assertFalse(engine.technical(note), note)

    def test_the_real_notes_a_scan_writes(self):
        self.assertTrue(engine.technical(engine.took_note({"listening": 1.8, "picture scan": 4.3})))
        self.assertTrue(engine.technical(engine.took_note({"voices": 0.2})))

    def test_the_videos_notes_in_order(self):
        st = {"notes": mixed()}
        self.assertEqual(engine.video_notes(st), ABOUT_THE_VIDEO)
        self.assertEqual(len(st["notes"]), len(TECHNICAL) + len(ABOUT_THE_VIDEO))   # all kept
        self.assertEqual(engine.video_notes({}), [])
        self.assertEqual(engine.video_notes({"notes": None}), [])

    def test_sent_in_with_what_we_refined(self):
        import cleanview_learn as learn
        st = support.sample_review()
        st["notes"] = mixed()
        st["scan"] = {"app_version": "1.18.82", "models": {"pictures": "qwen3-vl:8b-instruct"}}
        sent = json.loads(learn.export_refined([st], dest_dir=support.SANDBOX).read_text("utf8"))
        self.assertEqual(sent["videos"][0]["notes"], mixed())
        self.assertEqual(sent["videos"][0]["scan"]["models"]["pictures"], "qwen3-vl:8b-instruct")

    def test_the_report_files_last_lines(self):
        lines = engine.technical_notes({"notes": mixed()})
        self.assertEqual(lines[:2], ["", engine.TECHNICAL_HEAD])
        self.assertEqual(lines[2:], ["  " + n for n in TECHNICAL])
        self.assertEqual(engine.technical_notes({"notes": ABOUT_THE_VIDEO}), [])    # no heading
        # the version, also when no AI helper ran to say it; not said twice
        no_ai = {"notes": [TECHNICAL[0], TECHNICAL[-1]], "scan": {"app_version": "1.18.83"}}
        self.assertEqual(engine.technical_notes(no_ai)[2], "  CleanView 1.18.83.")
        with_ai = {"notes": TECHNICAL[:2], "scan": {"app_version": "1.18.82"}}
        self.assertEqual(len(engine.technical_notes(with_ai)), 4)

    @T.needs_ffmpeg
    def test_last_in_the_report_file_beside_the_clean_copy(self):
        video = support.SANDBOX / "Plain Notes Show S01E01.mp4"
        if not video.exists():
            T.ffmpeg("-f", "lavfi", "-i", "testsrc=size=64x48:rate=10:duration=6", "-f", "lavfi",
                     "-i", "sine=frequency=440:duration=6", "-c:v", "libx264", "-c:a", "aac",
                     "-shortest", video)
        work = Path(tempfile.mkdtemp(dir=support.SANDBOX))
        info = engine.probe(video)
        st = {"path": str(video), "info": info, "duration": info["duration"], "groups": [],
              "mutes": [], "scenes": [], "lines": [], "notes": mixed(), "cues": []}
        (work / "analysis.json").write_text(json.dumps(st))
        res = engine.render(work, work / "Clean", [], lines=[], words=[],
                            encoders=[engine.ENCODERS[-1]], log=lambda m: None)
        rep = (Path(res["folder"]) / "Reports" /
               "Plain Notes Show S01E01 - CleanView report.txt").read_text("utf8")
        top, _, last = rep.partition(engine.TECHNICAL_HEAD)
        for note in ABOUT_THE_VIDEO:
            self.assertIn(engine.plain_ai(note), top)
        for note in TECHNICAL:
            self.assertNotIn(note, top)             # not among what's about the video
            self.assertIn(note, last)               # the last lines, under their heading
        self.assertEqual(last.strip().splitlines()[-1].strip(), TECHNICAL[-1])
        self.assertIn("muted", top)                 # the summary and the list come first
        self.assertEqual(json.loads((work / "analysis.json").read_text())["notes"], mixed())


class ReviewPage(unittest.TestCase):
    def test_only_whats_about_the_video(self):
        real = (ui.App._check_update, ui.App._check_every_ai)
        ui.App._check_update = lambda self, manual=False: None
        ui.App._check_every_ai = lambda self: None
        try:
            app = ui.App()
        except tk.TclError as ex:
            self.skipTest(f"no screen to draw on ({ex})")
        finally:
            ui.App._check_update, ui.App._check_every_ai = real
        try:
            st = support.sample_review()
            st["notes"] = mixed()
            app.jobs = [{"video": st["path"], "work": support.write_review(), "analysis": st,
                         "error": None, "cuts": [], "lines": [], "words": []}]
            app.videos = [st["path"]]
            app.show_review()
            app.update()

            def texts(w):
                out = [w.cget("text")] if isinstance(w, tk.Label) else []
                for c in w.winfo_children():
                    out += texts(c)
                return out
            shown = "\n".join(str(t) for t in texts(app))
            for note in ABOUT_THE_VIDEO:            # (said as "the AI" since 1.18.86)
                self.assertIn(engine.plain_ai(note), shown)
            for note in TECHNICAL:
                self.assertNotIn(note, shown)
                self.assertNotIn(engine.plain_ai(note), shown)
            for word in ("qwen", "Took ", "stills)", "speakers told apart"):
                self.assertNotIn(word, shown)
            self.assertEqual(len(app.jobs[0]["analysis"]["notes"]), len(mixed()))     # still kept
        finally:
            app.destroy()


if __name__ == "__main__":
    unittest.main()
