"""CleanView — a simple window for cleaning up movies and TV episodes you own."""
import hashlib
import json
import os
import queue
import re
import subprocess
import sys
import threading
import tkinter as tk
import traceback
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cleanview as engine  # noqa: E402
import cleanview_claude as cc  # noqa: E402
import cleanview_learn as learn  # noqa: E402

APP_DATA = Path(os.environ.get("LOCALAPPDATA") or Path.home() / ".local" / "share") / "CleanView"
BG, CARD, INK, MUTED, ACCENT, ACCENT_DK, LINE = (
    "#F6F3EE", "#FFFFFF", "#23211F", "#6D6862", "#2F6F62", "#24574D", "#E3DED6")
CHIP = {"Nudity": "#B5523B", "Sex": "#9A3E66", "Intimate": "#9A3E66", "Kiss": "#B0457A",
        "Violence": "#7A5A1E", "Gore": "#8E2B2B", "Smoking": "#5D6470", "Drinking": "#5D6470",
        "Drugs": "#5D6470", "Immodest": "#A0663A", "Sexual": "#9A3E66", "Sleeping": "#9A3E66",
        "Same-sex": "#6B4E9B", "Unmarried": "#6B4E9B", "Crude": "#7A6A2E",
        "Bullying": "#8A4B2E"}


CHIP["Found"] = CHIP["Claude"] = "#C2581F"


def chip_color(label):
    return CHIP.get(label.split(" ")[0], "#2F6F62")


CLAUDE_SAYS = {"remove": ("Claude: remove", "#8E2B2B"),
               "not an issue": ("Claude: not an issue", "#2E7D4F"),
               "can't tell": ("Claude: can't tell", "#6D6862")}


def claude_note(item, on=None):
    c = item.get("claude")
    if not c:
        return None, None
    head, col = CLAUDE_SAYS.get(c.get("decision"), ("Claude", "#6D6862"))
    text = head + (" \u2014 " + c["why"] if c.get("why") else "")
    if (item.get("by_you") or item.get("learned")) and on is not None and \
            c.get("decision") in ("remove", "not an issue") and on != (c["decision"] == "remove"):
        text += "  (you chose otherwise, so it stays as you set it)"
    return text, col
FONT = "Segoe UI" if os.name == "nt" else "DejaVu Sans"


def natural_key(p):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", Path(p).name)]


def fmt_len(sec):
    h, m = int(sec // 3600), int(sec % 3600 // 60)
    return f"{h} hr {m} min" if h else f"{m} min"


def open_path(p):
    if os.name == "nt":
        os.startfile(p)  # noqa
    elif sys.platform == "darwin":
        subprocess.Popen(["open", p])
    else:
        subprocess.Popen(["xdg-open", p])


def short(name, n=60):
    return name if len(name) <= n else name[:n - 1] + "…"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CleanView")
        scale = max(1.0, self.winfo_fpixels("1i") / 96.0)
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w = min(int(860 * scale), sw - 40)
        h = min(int(800 * scale), sh - 90)
        self.geometry(f"{w}x{h}+{max(0, (sw - w) // 2)}+{max(0, (sh - h) // 2 - 20)}")
        self.minsize(min(w, int(660 * scale)), min(h, int(500 * scale)))
        self.configure(bg=BG)
        try:
            self.iconbitmap(str(Path(__file__).resolve().parent / "cleanview.ico"))
        except Exception:
            pass
        self.q = queue.Queue()
        self.cancel_flag = False
        self.videos, self.outdir, self.jobs = [], None, []
        self._imgs = []
        self._style()
        self.page = None
        self.show_setup()
        self.after(100, self._poll)

    # ---------- look ----------
    def _style(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure(".", background=BG, foreground=INK, font=(FONT, 10))
        s.configure("TCheckbutton", background=CARD, font=(FONT, 10))
        s.configure("Card.TRadiobutton", background=CARD, font=(FONT, 10))
        s.map("Card.TRadiobutton", background=[("active", CARD)])
        s.configure("TNotebook", background=BG, borderwidth=0)
        s.configure("TNotebook.Tab", padding=(16, 6), font=(FONT, 10))
        s.configure("Treeview", rowheight=24, font=(FONT, 9))
        s.map("TCheckbutton", background=[("active", CARD)])
        s.configure("Accent.TButton", background=ACCENT, foreground="white",
                    font=(FONT, 12, "bold"), padding=(22, 10), borderwidth=0)
        s.map("Accent.TButton", background=[("active", ACCENT_DK), ("disabled", "#A9C2BC")])
        s.configure("Plain.TButton", background="#ECE7E0", foreground=INK, padding=(14, 6),
                    borderwidth=0, font=(FONT, 10))
        s.map("Plain.TButton", background=[("active", "#E0D9CF")])
        s.configure("Small.TButton", background="#ECE7E0", foreground=INK, padding=(10, 3),
                    borderwidth=0, font=(FONT, 9))
        s.map("Small.TButton", background=[("active", "#E0D9CF")])
        s.configure("Green.Horizontal.TProgressbar", troughcolor="#E6E1DA",
                    background=ACCENT, bordercolor="#E6E1DA", lightcolor=ACCENT, darkcolor=ACCENT)

    def _new_page(self, title, subtitle=""):
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.unbind_all(seq)
        if self.page:
            self.page.destroy()
        self._imgs = []
        self.page = tk.Frame(self, bg=BG)
        self.page.pack(fill="both", expand=True, padx=28, pady=(20, 16))
        self.footer = tk.Frame(self.page, bg=BG)
        self.footer.pack(side="bottom", fill="x", pady=(12, 0))
        tk.Label(self.page, text=title, bg=BG, fg=INK, font=(FONT, 20, "bold")).pack(anchor="w")
        if subtitle:
            tk.Label(self.page, text=subtitle, bg=BG, fg=MUTED, font=(FONT, 11),
                     wraplength=740, justify="left").pack(anchor="w", pady=(2, 12))
        return self.page

    def _scroll_area(self, parent):
        wrap = tk.Frame(parent, bg=BG)
        wrap.pack(fill="both", expand=True)
        canvas = tk.Canvas(wrap, bg=BG, highlightthickness=0)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=BG)
        win = canvas.create_window((0, 0), window=inner, anchor="nw")

        def refresh(_=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
            needs = inner.winfo_reqheight() > canvas.winfo_height() + 2
            if needs and not sb.winfo_ismapped():
                sb.pack(side="right", fill="y", before=canvas)
            elif not needs and sb.winfo_ismapped():
                sb.pack_forget()

        inner.bind("<Configure>", refresh)
        canvas.bind("<Configure>", lambda e: (canvas.itemconfigure(win, width=e.width), refresh()))
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)

        def wheel(delta):
            if inner.winfo_reqheight() > canvas.winfo_height():
                canvas.yview_scroll(delta, "units")

        self.bind_all("<MouseWheel>", lambda e: wheel(int(-e.delta / 120)))
        self.bind_all("<Button-4>", lambda e: wheel(-2))
        self.bind_all("<Button-5>", lambda e: wheel(2))
        return inner

    def _card(self, parent, step, heading, note=""):
        outer = tk.Frame(parent, bg=LINE)
        outer.pack(fill="x", pady=6)
        c = tk.Frame(outer, bg=CARD, padx=16, pady=12)
        c.pack(fill="x", padx=1, pady=1)
        top = tk.Frame(c, bg=CARD)
        top.pack(fill="x")
        tk.Label(top, text=step, bg=ACCENT, fg="white", font=(FONT, 10, "bold"),
                 width=2).pack(side="left", padx=(0, 10))
        tk.Label(top, text=heading, bg=CARD, fg=INK, font=(FONT, 12, "bold")).pack(side="left")
        if note:
            tk.Label(top, text=note, bg=CARD, fg=MUTED, font=(FONT, 9)).pack(side="left", padx=8)
        body = tk.Frame(c, bg=CARD)
        body.pack(fill="x", pady=(8, 0), padx=(32, 0))
        return body

    # ---------- page 1: setup ----------
    def show_setup(self):
        p = self._new_page("CleanView", "Clean up a movie or TV episodes you own: mute bad "
                           "language and cut out nudity, sex scenes and violence.")
        upd = os.environ.pop("CLEANVIEW_UPDATED", None)
        if upd:
            tk.Label(p, text="\u2713 " + upd,
                     bg="#E3EFEC", fg=ACCENT_DK, font=(FONT, 10), padx=10, pady=6,
                     anchor="w").pack(fill="x", pady=(0, 8))
        try:
            ver = json.loads((Path(__file__).resolve().parent / "version.json").read_text())["version"]
            self.title(f"CleanView {ver}")
        except Exception:
            pass
        self.start_btn = ttk.Button(self.footer, text="Start cleaning", style="Accent.TButton",
                                    command=self.start, state="disabled")
        self.start_btn.pack(side="right")
        body = self._scroll_area(p)

        self.opts = {}
        b1 = self._card(body, "1", "Movie or episodes")
        row = tk.Frame(b1, bg=CARD)
        row.pack(fill="x")
        ttk.Button(row, text="Choose files…", style="Plain.TButton",
                   command=self.pick_files).pack(side="left")
        ttk.Button(row, text="Choose a folder of episodes…", style="Plain.TButton",
                   command=self.pick_folder).pack(side="left", padx=(8, 0))
        self.vid_lbl = tk.Label(b1, text="Nothing chosen yet", bg=CARD, fg=MUTED,
                                font=(FONT, 10), wraplength=640, justify="left")
        self.vid_lbl.pack(anchor="w", pady=(8, 0))
        v = tk.BooleanVar(value=self._load_settings().get("autosubs", True))
        self.opts["autosubs"] = v
        ttk.Checkbutton(b1, text="Find subtitles online for videos that don't have any",
                        variable=v).pack(anchor="w", pady=(8, 0))
        tk.Label(b1, text="Recommended: subtitles give the exact words, who's talking and "
                 "descriptions like [kissing], which makes every check more accurate.", bg=CARD,
                 fg=MUTED, font=(FONT, 9), wraplength=640, justify="left").pack(anchor="w",
                                                                             padx=(22, 0))
        tk.Label(b1, text="Works with DRM-free files: DVD and Blu-ray rips, home videos and "
                 "downloads without copy protection. If the movie has subtitles, they're used "
                 "to catch extra words and get cleaned too.", bg=CARD, fg=MUTED, font=(FONT, 9),
                 wraplength=640, justify="left").pack(anchor="w", pady=(6, 0))

        b2 = self._card(body, "2", "What to remove")
        saved = self._load_settings()

        def section(title):
            tk.Label(b2, text=title, bg=CARD, fg=ACCENT_DK, font=(FONT, 10, "bold")).pack(
                anchor="w", pady=(8, 2))
            g = tk.Frame(b2, bg=CARD)
            g.pack(fill="x")
            return g

        def checks(grid, items, cols=2):
            for n, (key, label, on) in enumerate(items):
                v = tk.BooleanVar(value=saved.get(key, on))
                self.opts[key] = v
                ttk.Checkbutton(grid, text=label, variable=v).grid(
                    row=n // cols, column=n % cols, sticky="w", padx=(0, 26), pady=1)

        checks(section("Language"), [
            ("swearing", "Swearing  (f-word, s-word, b-word\u2026)", True),
            ("mild", "Mild words  (damn, hell, crap)", True),
            ("deity", "God's name used as a swear", True),
            ("minced", "Soft substitutes  (gosh, heck, freaking)", False),
            ("samesexwords", "Words about same-sex relationships  (gay, lesbian\u2026)", True),
            ("sexref", "Sexual references and innuendo", True),
            ("crude", "Crude humor  (bathroom and gross-out jokes)", False),
            ("bullying", "Bullying and mocking", False)])
        checks(section("Sex and nudity"), [
            ("nudity", "Nudity", True),
            ("sex", "Sex scenes", True),
            ("immodest", "Immodest clothing  (swimsuits, underwear)", False),
            ("casual", "Sleeping around  (casual sex, affairs)", True)])
        g = section("Kissing and relationships")
        levels = {"Keep": "off", "Cut passionate kisses": "passionate", "Cut all kisses": "all"}
        self.level_names = {v: k for k, v in levels.items()}
        self.level_values = levels
        for row, (key, label, default) in enumerate([("kiss_os", "Man & woman kissing", "passionate"),
                                                     ("kiss_ss", "Same-sex kissing", "passionate")]):
            tk.Label(g, text=label, bg=CARD, fg=INK, font=(FONT, 10)).grid(
                row=row, column=0, sticky="w", padx=(0, 12), pady=2)
            v = tk.StringVar(value=self.level_names[saved.get(key, default)])
            self.opts[key] = v
            ttk.Combobox(g, textvariable=v, values=list(levels), state="readonly",
                         width=22).grid(row=row, column=1, sticky="w", pady=2)
        g2 = tk.Frame(b2, bg=CARD)
        g2.pack(fill="x", pady=(4, 0))
        checks(g2, [("samesex", "Same-sex relationships  (flirting, talk and intimate scenes)", False),
                    ("oppsex", "Unmarried couples living or sleeping together", False)], cols=1)
        checks(section("Violence"), [
            ("violence", "Violence  (shootings, fights, attacks)", True),
            ("gore", "Graphic gore  (blood, wounds, bodies)", True)])
        checks(section("Other"), [
            ("smoking", "Smoking", False), ("drinking", "Drinking alcohol", False),
            ("drugs", "Drug use", True)], cols=3)
        tk.Label(b2, text="Swear words are muted automatically. Everything else is listed for "
                 "you to check before anything is muted or cut.", bg=CARD, fg=MUTED,
                 font=(FONT, 9), wraplength=640, justify="left").pack(anchor="w", pady=(10, 0))

        b25 = self._card(body, "3", "AI helper", "recommended")
        v = tk.BooleanVar(value=saved.get("ai", True))
        self.opts["ai"] = v
        ttk.Checkbutton(b25, text="Use the AI helper to double-check scenes and read the dialogue",
                        variable=v).pack(anchor="w")
        tk.Label(b25, text="Runs on your own PC, nothing is uploaded. The first time, it downloads "
                 "Ollama and two AI models (about 11 GB, one time only). Without it, kissing and "
                 "dialogue checks are rougher.", bg=CARD, fg=MUTED, font=(FONT, 9),
                 wraplength=640, justify="left").pack(anchor="w", pady=(4, 0))
        tk.Label(b25, text="Who reads the dialogue", bg=CARD, fg=ACCENT_DK,
                 font=(FONT, 10, "bold")).pack(anchor="w", pady=(10, 2))
        v = tk.StringVar(value=saved.get("reader", "local"))
        self.opts["reader"] = v
        ttk.Radiobutton(b25, text="The AI on this PC", value="local", variable=v,
                        style="Card.TRadiobutton").pack(anchor="w")
        ttk.Radiobutton(b25, text="Claude  (more accurate; uses your Claude plan)", value="claude",
                        variable=v, style="Card.TRadiobutton").pack(anchor="w")
        crow = tk.Frame(b25, bg=CARD)
        crow.pack(fill="x", padx=(22, 0), pady=(2, 0))
        self.claude_lbl = tk.Label(crow, text="Checking Claude\u2026", bg=CARD, fg=MUTED,
                                   font=(FONT, 9), wraplength=430, justify="left")
        self.claude_lbl.pack(side="left")
        self.claude_btn = ttk.Button(crow, text="Set up Claude", style="Small.TButton",
                                     command=self.setup_claude)
        tk.Label(b25, text="Only the words that are said are sent to Claude, never the video or "
                 "sound. It also adds an \u201cAsk Claude\u201d chat to the review page.", bg=CARD,
                 fg=MUTED, font=(FONT, 9), wraplength=640, justify="left").pack(anchor="w",
                                                                             padx=(22, 0))
        self.check_claude()

        b3 = self._card(body, "4", "Save to")
        row = tk.Frame(b3, bg=CARD)
        row.pack(fill="x")
        ttk.Button(row, text="Change…", style="Plain.TButton",
                   command=self.pick_out).pack(side="right")
        self.out_lbl = tk.Label(row, text="A “Clean” folder next to the video", bg=CARD,
                                fg=MUTED, font=(FONT, 10), wraplength=500, justify="left")
        self.out_lbl.pack(side="left")
        tk.Label(b3, text="Your original files are never changed.", bg=CARD, fg=MUTED,
                 font=(FONT, 9)).pack(anchor="w", pady=(6, 0))
        self._refresh_labels()

    # ---------- Claude ----------
    def check_claude(self):
        def go():
            self.q.put(("claude_status", cc.status()))
        threading.Thread(target=go, daemon=True).start()

    def _show_claude_status(self, st):
        self.claude_state = st
        lbl = getattr(self, "claude_lbl", None)
        if lbl is None or not lbl.winfo_exists():
            return
        text = {"ready": "\u2713 Claude is set up and signed in.",
                "signed_out": "Claude is installed but not signed in yet.",
                "missing": "Claude isn't set up on this PC yet (one time, a few minutes)."}[st]
        lbl.config(text=text, fg=ACCENT_DK if st == "ready" else MUTED)
        if st == "ready":
            self.claude_btn.pack_forget()
        else:
            self.claude_btn.config(text="Sign in to Claude" if st == "signed_out" else "Set up Claude",
                                   state="normal")
            self.claude_btn.pack(side="left", padx=(10, 0))

    def setup_claude(self):
        self.claude_btn.config(state="disabled")
        self.claude_lbl.config(text="Setting up Claude\u2026 (this can take a few minutes)")

        def go():
            try:
                if not cc.find_claude():
                    cc.install_claude()
                if not cc.signed_in():
                    cc.open_sign_in()
                    self.q.put(("claude_wait",))
                    for _ in range(180):          # wait up to 6 minutes for the sign-in
                        import time
                        time.sleep(2)
                        if cc.signed_in():
                            break
                self.q.put(("claude_status", cc.status()))
            except Exception as ex:
                self.q.put(("warn", f"Claude couldn't be set up: {ex}"))
                self.q.put(("claude_status", cc.status()))
        threading.Thread(target=go, daemon=True).start()

    def _load_settings(self):
        try:
            return json.loads((APP_DATA / "cleanview_settings.json").read_text())
        except Exception:
            return {}

    def _current_opts(self):
        o = {}
        for k, v in self.opts.items():
            val = v.get()
            o[k] = self.level_values.get(val, val) if isinstance(val, str) else bool(val)
        return o

    def _refresh_labels(self):
        if self.videos:
            dur = sum(engine.cl.probe_duration(v) for v in self.videos)
            first = short(Path(self.videos[0]).name, 70)
            extra = f"  … and {len(self.videos) - 1} more" if len(self.videos) > 1 else ""
            folder = os.path.normpath(str(Path(self.videos[0]).parent))
            n = len(self.videos)
            self.vid_lbl.config(text=f"{n} video{'s' if n != 1 else ''} · {fmt_len(dur)}   in  "
                                f"{folder}\n{first}{extra}", fg=INK)
            self.start_btn.config(state="normal")
            if not self.outdir:
                self.out_lbl.config(text=os.path.normpath(str(Path(self.videos[0]).parent / "Clean")),
                                    fg=INK)
        if self.outdir:
            self.out_lbl.config(text=os.path.normpath(self.outdir), fg=INK)

    def pick_files(self):
        exts = " ".join("*" + e for e in engine.VIDEO_EXTS)
        files = filedialog.askopenfilenames(title="Choose the movie or episodes",
                                            filetypes=[("Videos", exts), ("All files", "*.*")])
        if files:
            self.videos = sorted(files, key=natural_key)
            self.outdir = None
            self._refresh_labels()

    def pick_folder(self):
        d = filedialog.askdirectory(title="Choose the folder with the episodes in it")
        if not d:
            return
        folder = Path(d)
        files = [f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in engine.VIDEO_EXTS
                 and "(Clean)" not in f.name]
        if not files:
            files = [f for sub in folder.iterdir() if sub.is_dir() and sub.name.lower() != "clean"
                     for f in sub.iterdir() if f.is_file() and f.suffix.lower() in engine.VIDEO_EXTS]
        if not files:
            messagebox.showinfo("CleanView", "No video files (MP4, MKV…) were found in that folder.")
            return
        self.videos = sorted((str(f) for f in files), key=natural_key)
        self.outdir = None
        self._refresh_labels()

    def pick_out(self):
        d = filedialog.askdirectory(title="Where should the clean copies go?")
        if d:
            self.outdir = d
            self._refresh_labels()

    # ---------- page 2: working ----------
    def start(self):
        o = self._current_opts()
        if o.get("reader") == "claude" and getattr(self, "claude_state", "ready") != "ready":
            if not messagebox.askyesno("CleanView", "Claude isn't set up yet, so the AI on this "
                                       "PC will read the dialogue this time.\n\nGo ahead?"):
                return
            o["reader"] = "local"
        word_groups = ("swearing", "mild", "deity", "minced", "samesexwords")
        self.groups = [g for g in word_groups if o.get(g)]
        self.scan_opts = {k: v for k, v in o.items() if k not in word_groups}
        if not self.groups and not any(v not in (False, "off") for k, v in self.scan_opts.items()
                                       if k != "ai"):
            messagebox.showinfo("CleanView", "Tick at least one thing to remove.")
            return
        try:
            APP_DATA.mkdir(parents=True, exist_ok=True)
            (APP_DATA / "cleanview_settings.json").write_text(json.dumps(o))
        except Exception:
            pass
        if not self.outdir:
            self.outdir = str(Path(self.videos[0]).parent / "Clean")
        self.jobs = []
        for v in self.videos:
            key = hashlib.sha1(f"{v}:{os.path.getsize(v)}".encode()).hexdigest()[:16]
            self.jobs.append({"video": v, "work": APP_DATA / "views" / key, "analysis": None,
                              "error": None})
        self.cancel_flag = False
        self.show_working("Watching and listening…")
        threading.Thread(target=self._analyze_thread, daemon=True).start()

    def show_working(self, title):
        dur = sum(engine.cl.probe_duration(j["video"]) for j in self.jobs)
        n = len(self.jobs)
        what = f"These {n} videos are" if n > 1 else "This video is"
        p = self._new_page(title, f"{what} {fmt_len(dur)} long. You can "
                           "leave this running and come back — if you close the window, it "
                           "picks up where it left off next time.")
        box = tk.Frame(p, bg=BG)
        box.pack(fill="x", pady=30)
        self.which = tk.Label(box, text="", bg=BG, fg=MUTED, font=(FONT, 10))
        self.which.pack(anchor="w", pady=(0, 6))
        self.pb = ttk.Progressbar(box, style="Green.Horizontal.TProgressbar", maximum=1000,
                                  length=640)
        self.pb.pack(fill="x")
        self.status = tk.Label(box, text="Starting…", bg=BG, fg=INK, font=(FONT, 12))
        self.status.pack(anchor="w", pady=(12, 0))
        self.cancel_btn = ttk.Button(self.footer, text="Cancel", style="Plain.TButton",
                                     command=self.cancel)
        self.cancel_btn.pack(side="right")

    def cancel(self):
        self.cancel_flag = True
        self.status.config(text="Stopping…")

    def _analyze_thread(self):
        try:
            if engine.tools_missing(self.scan_opts):
                self.q.put(("which", "Getting ready (one time only)"))
                try:
                    engine.install_tools(self.scan_opts,
                                         progress=lambda f, m: self.q.put(("progress", f, m, "")))
                except Exception as ex:
                    # carry on with whatever did install; the review page says what was skipped
                    self.q.put(("warn", "Some of the checking tools couldn't be set up, so this "
                                "run uses the ones that are ready.\n\n" + str(ex)[:400]))
            n = len(self.jobs)
            for k, j in enumerate(self.jobs):
                self.q.put(("which", (f"Video {k + 1} of {n}:  " if n > 1 else "") +
                            short(Path(j["video"]).name, 80)))
                try:
                    j["analysis"] = engine.analyze(
                        j["video"], j["work"], groups=self.groups, opts=self.scan_opts,
                        progress=lambda f, m, k=k: self.q.put(("progress", (k + f) / n, m, "")),
                        log=lambda m: None, cancel=lambda: self.cancel_flag)
                except engine.VideoError as ex:
                    j["error"] = str(ex)
            self.q.put(("analyzed",))
        except KeyboardInterrupt:
            self.q.put(("cancelled",))
        except Exception as ex:
            self.q.put(("error", str(ex), traceback.format_exc()))

    def _render_thread(self):
        try:
            todo = [j for j in self.jobs if j["analysis"]]
            encs = None
            if any(j["cuts"] for j in todo):
                self.q.put(("progress", 0.0, "Checking the fastest way to save video…", ""))
                encs = engine.working_encoders()
            results = []
            for k, j in enumerate(todo):
                self.q.put(("which", (f"Video {k + 1} of {len(todo)}:  " if len(todo) > 1 else "")
                            + short(Path(j["video"]).name, 80)))
                results.append(engine.render(
                    j["work"], self.outdir, j["cuts"], encoders=encs, lines=j.get("lines", []), words=j.get("words"),
                    progress=lambda f, m, k=k: self.q.put(("progress", (k + f) / len(todo), m, "")),
                    log=lambda m: None, cancel=lambda: self.cancel_flag))
            self.q.put(("rendered", results))
        except KeyboardInterrupt:
            self.q.put(("cancelled",))
        except Exception as ex:
            self.q.put(("error", str(ex), traceback.format_exc()))

    def _poll(self):
        try:
            while True:
                msg = self.q.get_nowait()
                kind = msg[0]
                alive = getattr(self, "pb", None) is not None and self.pb.winfo_exists()
                if kind == "progress" and alive:
                    self.pb["value"] = int(max(0.0, min(1.0, msg[1])) * 1000)
                    self.status.config(text=msg[2])
                elif kind == "which" and alive:
                    self.which.config(text=msg[1])
                elif kind == "analyzed":
                    self.after_analyze()
                elif kind == "rendered":
                    self.show_done(msg[1])
                elif kind == "cancelled":
                    self.show_setup()
                elif kind == "preview_ready":
                    open_path(msg[1])
                elif kind == "claude_status":
                    self._show_claude_status(msg[1])
                elif kind == "claude_wait":
                    lbl = getattr(self, "claude_lbl", None)
                    if lbl is not None and lbl.winfo_exists():
                        lbl.config(text="Finish signing in in the browser window that opened. "
                                   "This will update by itself when you're done.")
                elif kind == "chat_reply":
                    self._chat_reply(*msg[1:])
                elif kind == "reviewed":
                    self._reviewed(*msg[1:])
                elif kind == "warn":
                    messagebox.showwarning("CleanView", msg[1])
                elif kind == "preview_error":
                    messagebox.showerror("CleanView", msg[1])
                elif kind == "error":
                    try:
                        APP_DATA.mkdir(parents=True, exist_ok=True)
                        (APP_DATA / "cleanview_last_error.txt").write_text(msg[2], encoding="utf8")
                    except Exception:
                        pass
                    messagebox.showerror("CleanView ran into a problem", msg[1])
                    self.show_setup()
        except queue.Empty:
            pass
        self.after(150, self._poll)

    def after_analyze(self):
        bad = [j for j in self.jobs if j["error"]]
        if bad:
            messagebox.showwarning("CleanView", "These couldn't be cleaned and will be skipped:\n\n" +
                                   "\n\n".join(j["error"] for j in bad))
        good = [j for j in self.jobs if j["analysis"]]
        if not good:
            self.show_setup()
            return
        self.show_review()   # always: so every mute and cut can be seen and unticked

    # ---------- page 3: review ----------
    def show_review(self):
        good = [j for j in self.jobs if j["analysis"]]
        n = sum(len(j["analysis"]["scenes"]) for j in good)
        nl = sum(len(j["analysis"].get("lines", [])) for j in good)
        nw = sum(len(j["analysis"]["mutes"]) for j in good)
        parts = []
        if n:
            parts.append(f"{n} scene{'s' if n != 1 else ''}")
        if nl:
            parts.append(f"{nl} line{'s' if nl != 1 else ''}")
        if nw:
            parts.append(f"{nw} word{'s' if nw != 1 else ''}")
        title = (", ".join(parts[:-1]) + " and " + parts[-1] if len(parts) > 1 else
                 parts[0] if parts else "Nothing found") + (" to check" if parts else "")
        p = self._new_page(title,
                           "Checked scenes will be cut and checked words and lines muted. Untick "
                           "anything you want to keep, and use \u201cAll dialogue\u201d or "
                           "\u201cAsk Claude\u201d to add anything it missed.")
        self.scene_vars, self.line_vars, self.word_vars = [], [], []
        self.dlg_vars = {}          # (job index, dialogue line index) -> BooleanVar
        self.found_frames = {}
        multi = len(good) > 1
        nb = ttk.Notebook(p)
        nb.pack(fill="both", expand=True)
        t_found = tk.Frame(nb, bg=BG)
        t_dlg = tk.Frame(nb, bg=BG)
        t_chat = tk.Frame(nb, bg=BG)
        nb.add(t_found, text="  Found  ")
        nb.add(t_dlg, text="  All dialogue  ")
        nb.add(t_chat, text="  Ask Claude  ")

        # Found
        add = tk.Frame(t_found, bg=BG)
        add.pack(fill="x", pady=(8, 4))
        tk.Label(add, text="Missed a scene? Cut from", bg=BG, fg=INK, font=(FONT, 10)).pack(side="left")
        self.add_from = ttk.Entry(add, width=9)
        self.add_from.pack(side="left", padx=4)
        tk.Label(add, text="to", bg=BG, fg=INK, font=(FONT, 10)).pack(side="left")
        self.add_to = ttk.Entry(add, width=9)
        self.add_to.pack(side="left", padx=4)
        if multi:
            self.add_job = ttk.Combobox(add, values=[short(Path(j["video"]).name, 28) for j in good],
                                        state="readonly", width=24)
            self.add_job.current(0)
            self.add_job.pack(side="left", padx=4)
        ttk.Button(add, text="Add", style="Small.TButton", command=self._add_scene_typed).pack(
            side="left", padx=4)
        tk.Label(add, text="(times like 12:30 or 1:02:15)", bg=BG, fg=MUTED, font=(FONT, 9)).pack(
            side="left", padx=4)
        inner = self._scroll_area(t_found)
        for ji, j in enumerate(good):
            st = j["analysis"]
            j["_ji"] = ji
            if multi:
                tk.Label(inner, text=Path(j["video"]).name, bg=BG, fg=INK,
                         font=(FONT, 12, "bold"), anchor="w").pack(fill="x", padx=8, pady=(14, 0))
            if st.get("claude_summary"):
                box = tk.Frame(inner, bg="#FFF4EC", padx=12, pady=8, highlightbackground="#E9C9B3",
                               highlightthickness=1)
                box.pack(fill="x", padx=8, pady=(8, 4))
                tk.Label(box, text="Claude's review", bg="#FFF4EC", fg="#C2581F",
                         font=(FONT, 10, "bold"), anchor="w").pack(fill="x")
                tk.Label(box, text=st["claude_summary"], bg="#FFF4EC", fg=INK, font=(FONT, 10),
                         wraplength=700, justify="left", anchor="w").pack(fill="x")
                cnt = st.get("claude_counts") or {}
                if cnt.get("dropped") or cnt.get("added"):
                    tk.Label(box, text=f"Unticked {cnt.get('dropped', 0)} false alarm(s) and added "
                             f"{cnt.get('added', 0)} missed item(s). Anything you change yourself "
                             "stays the way you set it.", bg="#FFF4EC", fg=MUTED, font=(FONT, 9),
                             wraplength=700, justify="left", anchor="w").pack(fill="x", pady=(2, 0))
            for note in st.get("notes", []):
                tk.Label(inner, text="\u2139 " + note, bg=BG, fg=MUTED, font=(FONT, 9),
                         wraplength=720, justify="left", anchor="w").pack(fill="x", padx=8)
            holder = tk.Frame(inner, bg=BG)
            holder.pack(fill="x")
            self.found_frames[ji] = holder
            if not st["scenes"]:
                tk.Label(holder, text="No scenes were found to cut in this one.", bg=BG,
                         fg=INK, font=(FONT, 10), anchor="w").pack(fill="x", padx=8, pady=(6, 0))
            for sc in st["scenes"]:
                self._scene_card(holder, j, sc)
            if st.get("lines"):
                self._lines_card(inner, j, st["lines"])
            if st.get("mutes"):
                self._words_card(inner, j, st["mutes"])

        self._dialogue_tab(t_dlg, good)
        self._chat_tab(t_chat, good)
        ttk.Button(self.footer, text="Save clean copies" if multi else "Save clean copy",
                   style="Accent.TButton", command=self._save_from_review).pack(side="right")

    # --- adding scenes yourself
    @staticmethod
    def _parse_time(t):
        t = t.strip()
        if not t:
            return None
        try:
            parts = [float(x) for x in t.split(":")]
        except ValueError:
            return None
        sec = 0.0
        for x in parts:
            sec = sec * 60 + x
        return sec

    def _add_scene(self, job, s, e, why, kind="Added by you", said=None):
        st = job["analysis"]
        if said is None:
            said = " ".join(l["text"] for l in st.get("dialogue", []) if s - 0.5 <= l["s"] <= e)
        sc = {"s": round(s, 2), "e": round(e, 2), "kind": [kind], "why": why, "cut": True,
              "said": said[:400], "thumbs": [], "added": True}
        holder = self.found_frames.get(job["_ji"])
        if holder is not None:
            self._scene_card(holder, job, sc, top=True)
        return sc

    def _add_scene_typed(self):
        good = [j for j in self.jobs if j["analysis"]]
        job = good[self.add_job.current()] if hasattr(self, "add_job") and len(good) > 1 else good[0]
        s, e = self._parse_time(self.add_from.get()), self._parse_time(self.add_to.get())
        dur = job["analysis"].get("duration", 1e9)
        if s is None or e is None or e <= s or s > dur:
            messagebox.showinfo("CleanView", "Type a start and end time, like 12:30 and 13:05.")
            return
        self._add_scene(job, s, min(e, dur), "you added this")
        self.add_from.delete(0, "end")
        self.add_to.delete(0, "end")

    # --- every line of dialogue
    def _dlg_var(self, ji, i):
        v = self.dlg_vars.get((ji, i))
        if v is None:
            v = tk.BooleanVar(value=False)
            self.dlg_vars[(ji, i)] = v
        return v

    def _dialogue_tab(self, tab, good):
        top = tk.Frame(tab, bg=BG)
        top.pack(fill="x", pady=(8, 6))
        self.dlg_job = ttk.Combobox(top, values=[short(Path(j["video"]).name, 40) for j in good],
                                    state="readonly", width=36)
        self.dlg_job.current(0)
        if len(good) > 1:
            self.dlg_job.pack(side="left", padx=(0, 8))
        tk.Label(top, text="Search", bg=BG, fg=INK, font=(FONT, 10)).pack(side="left")
        self.dlg_search = ttk.Entry(top, width=30)
        self.dlg_search.pack(side="left", padx=6)
        ttk.Button(top, text="Cut the selected lines as a scene", style="Small.TButton",
                   command=self._cut_selected).pack(side="right")
        tk.Label(tab, text="Click a line to mute it (\u2714). Select several with Ctrl or Shift and "
                 "use the button to cut that stretch instead.", bg=BG, fg=MUTED,
                 font=(FONT, 9)).pack(anchor="w")
        box = tk.Frame(tab, bg=BG)
        box.pack(fill="both", expand=True, pady=(4, 0))
        tv = ttk.Treeview(box, columns=("mute", "time", "who", "line"), show="headings",
                          selectmode="extended")
        for col, w, txt in (("mute", 50, "Mute"), ("time", 70, "Time"), ("who", 120, "Who"),
                            ("line", 560, "Line")):
            tv.heading(col, text=txt)
            tv.column(col, width=w, anchor="w", stretch=(col == "line"))
        sb = ttk.Scrollbar(box, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        tv.pack(side="left", fill="both", expand=True)
        self.dlg_tv = tv
        # flagged lines share their tick box with the Found tab
        for v, j, l in self.line_vars:
            if "idx" in l:
                self.dlg_vars[(j["_ji"], l["idx"])] = v
        for (ji, i), v in self.dlg_vars.items():
            v.trace_add("write", lambda *_: self._fill_dialogue())
        tv.bind("<ButtonRelease-1>", self._dlg_click)
        self.dlg_search.bind("<KeyRelease>", lambda e: self._fill_dialogue())
        self.dlg_job.bind("<<ComboboxSelected>>", lambda e: self._fill_dialogue())
        self._fill_dialogue()

    def _dlg_job(self):
        good = [j for j in self.jobs if j["analysis"]]
        return good[max(0, self.dlg_job.current())]

    def _fill_dialogue(self):
        tv = getattr(self, "dlg_tv", None)
        if tv is None or not tv.winfo_exists():
            return
        job = self._dlg_job()
        st = job["analysis"]
        q = self.dlg_search.get().strip().lower()
        voices = st.get("voices") or []
        y = tv.yview()[0]
        tv.delete(*tv.get_children())
        for i, l in enumerate(st.get("dialogue", [])):
            if q and q not in l["text"].lower():
                continue
            v = self.dlg_vars.get((job["_ji"], i))
            who = l.get("who") or (voices[i].get("spk") if i < len(voices) and voices[i] else "")
            tv.insert("", "end", iid=str(i), values=("\u2714" if v is not None and v.get() else "",
                                                     engine.cl.fmt_t(l["s"]), who, l["text"]))
        tv.yview_moveto(y)

    def _dlg_click(self, ev):
        tv = self.dlg_tv
        if tv.identify_region(ev.x, ev.y) != "cell" or (ev.state & 0x0005):
            return       # header click, or Ctrl/Shift selection
        row = tv.identify_row(ev.y)
        if not row:
            return
        job = self._dlg_job()
        v = self._dlg_var(job["_ji"], int(row))
        v.set(not v.get())
        if len(v.trace_info()) == 0:
            v.trace_add("write", lambda *_: self._fill_dialogue())
            self._fill_dialogue()

    def _cut_selected(self):
        rows = [int(r) for r in self.dlg_tv.selection()]
        if not rows:
            messagebox.showinfo("CleanView", "Select the lines first (click, then Shift-click).")
            return
        job = self._dlg_job()
        d = job["analysis"]["dialogue"]
        a, b = min(rows), max(rows)
        self._add_scene(job, max(0.0, d[a]["s"] - 0.5), d[b]["e"] + 0.5, "you picked these lines",
                        said=" ".join(l["text"] for l in d[a:b + 1]))
        messagebox.showinfo("CleanView", f"Added a scene to cut from {engine.cl.fmt_t(d[a]['s'])} "
                            f"to {engine.cl.fmt_t(d[b]['e'])}. It's at the top of the Found tab.")

    # --- Claude: review everything, and chat
    def _chat_tab(self, tab, good):
        if not hasattr(self, "chat_sessions"):
            self.chat_sessions, self.chat_history = {}, []
        top = tk.Frame(tab, bg=BG)
        top.pack(fill="x", pady=(8, 6))
        self.chat_job = ttk.Combobox(top, values=[short(Path(j["video"]).name, 40) for j in good],
                                     state="readonly", width=36)
        self.chat_job.current(min(getattr(self, "_chat_ji", 0), len(good) - 1))
        if len(good) > 1:
            self.chat_job.pack(side="left")
        state = getattr(self, "claude_state", None) or cc.status()
        if state != "ready":
            msg = ("Claude isn't set up yet. Go back to the start page and use \u201cSet up "
                   "Claude\u201d under AI helper, then run this again." if state == "missing" else
                   "Claude isn't signed in yet. Use \u201cSign in to Claude\u201d on the start page.")
            tk.Label(tab, text=msg, bg=BG, fg=INK, font=(FONT, 10), wraplength=700,
                     justify="left").pack(anchor="w", pady=20)
            return
        self.review_btn = ttk.Button(top, text="Review everything again", style="Accent.TButton",
                                     command=self._rereview)
        self.review_btn.pack(side="right")
        tk.Label(tab, text="\u201cReview everything again\u201d has Claude look over every scene, "
                 "line and word on the Found tab (including what you've added or unticked) "
                 "together with the whole dialogue, and decide what really needs removing, what's "
                 "a false alarm and what was missed. Your own changes are never undone.",
                 bg=BG, fg=MUTED, font=(FONT, 9), wraplength=720, justify="left").pack(anchor="w")
        tk.Label(tab, text="You can also ask about this episode below, e.g. \u201cIs there any "
                 "flirting between two men?\u201d or \u201cWhy did you keep the scene at 12:30?\u201d",
                 bg=BG, fg=MUTED, font=(FONT, 9), wraplength=720,
                 justify="left").pack(anchor="w", pady=(4, 0))
        log = tk.Text(tab, wrap="word", height=14, font=(FONT, 10), bg=CARD, fg=INK, relief="flat",
                      padx=10, pady=8, highlightbackground=LINE, highlightthickness=1)
        log.pack(fill="both", expand=True, pady=(6, 6))
        log.tag_configure("you", foreground=ACCENT_DK, font=(FONT, 10, "bold"))
        log.tag_configure("claude", foreground=INK)
        log.tag_configure("note", foreground=MUTED, font=(FONT, 9))
        for text, tag in self.chat_history:
            log.insert("end", text + "\n", tag)
        log.configure(state="disabled")
        log.see("end")
        self.chat_log = log
        row = tk.Frame(tab, bg=BG)
        row.pack(fill="x")
        self.chat_entry = ttk.Entry(row)
        self.chat_entry.pack(side="left", fill="x", expand=True)
        self.chat_entry.bind("<Return>", lambda e: self._chat_send())
        self.chat_btn = ttk.Button(row, text="Ask", style="Small.TButton", command=self._chat_send)
        self.chat_btn.pack(side="left", padx=(6, 0))

    def _sync_job(self, job):
        """Copy the ticks on screen (and anything added) back into the analysis,
        marking what was changed by hand so Claude never undoes it."""
        st = job["analysis"]
        for v, j, sc in self.scene_vars:
            if j is not job:
                continue
            sc["cut"] = v.get()
            if sc.get("added") or v.get() != sc.get("_shown", v.get()):
                sc["by_you"] = True
            if sc not in st["scenes"]:
                sc["id"] = max([x.get("id", 0) for x in st["scenes"]] + [0]) + 1
                st["scenes"].append(sc)
        st["scenes"].sort(key=lambda sc: sc["s"])
        for v, j, l in self.line_vars:
            if j is job:
                l["mute"] = v.get()
                if v.get() != l.get("_shown", v.get()):
                    l["by_you"] = True
        for v, j, m in self.word_vars:
            if j is job:
                m["keep"] = not v.get()
                if v.get() != m.get("_shown", v.get()):
                    m["by_you"] = True
        have = {l.get("idx") for l in st["lines"]}
        d = st.get("dialogue", [])
        for (ji, i), v in self.dlg_vars.items():
            if ji == job["_ji"] and v.get() and i not in have and i < len(d):
                st["lines"].append({"s": d[i]["s"], "e": d[i]["e"], "text": d[i]["text"],
                                    "plain": d[i]["text"], "types": ["added"], "mute": True,
                                    "idx": i, "by_you": True})
        st["lines"].sort(key=lambda l: l["s"])
        for n, l in enumerate(st["lines"], 1):
            l["id"] = n

    def _rereview(self):
        good = [j for j in self.jobs if j["analysis"]]
        job = good[max(0, self.chat_job.current())]
        self._chat_ji = max(0, self.chat_job.current())
        for j in good:
            self._sync_job(j)
        self.review_btn.config(state="disabled")
        self.chat_btn.config(state="disabled")
        self._log("Claude is reviewing everything that was found, with the whole dialogue. "
                  "This can take a minute or two\u2026", "note")

        def go():
            try:
                engine.claude_review(job["analysis"], job["work"])
                self.q.put(("reviewed", job, None))
            except Exception as ex:
                self.q.put(("reviewed", job, str(ex)))
        threading.Thread(target=go, daemon=True).start()

    def _reviewed(self, job, err):
        if err:
            if getattr(self, "chat_log", None) is not None and self.chat_log.winfo_exists():
                self.review_btn.config(state="normal")
                self.chat_btn.config(state="normal")
                self._log("\u26a0 " + err, "note")
            return
        st = job["analysis"]
        cnt = st.get("claude_counts") or {}
        self._log("Claude's review: " + (st.get("claude_summary") or "done."))
        self._log(f"Unticked {cnt.get('dropped', 0)} false alarm(s), added {cnt.get('added', 0)} "
                  "missed item(s). The Found tab is updated.", "note")
        self.show_review()

    def _log(self, text, tag="claude"):
        self.chat_history.append((text, tag))
        log = self.chat_log
        log.configure(state="normal")
        log.insert("end", text + "\n", tag)
        log.configure(state="disabled")
        log.see("end")

    def _chat_send(self):
        qtext = self.chat_entry.get().strip()
        if not qtext:
            return
        good = [j for j in self.jobs if j["analysis"]]
        job = good[max(0, self.chat_job.current())]
        self.chat_entry.delete(0, "end")
        self.chat_btn.config(state="disabled")
        self._log("You: " + qtext, "you")
        self._log("Claude is reading the dialogue\u2026", "note")
        st = job["analysis"]
        self._sync_job(job)
        flagged = cc.candidates(st, with_review=True)[1]
        if st.get("claude_summary"):
            flagged += "\n\nYour earlier review said: " + st["claude_summary"]
        if self.chat_sessions.get(job["_ji"]):      # follow-up: send what changed since
            qtext_send = ("(What's on the list now:\n" + flagged + ")\n\n" + qtext)
        else:
            qtext_send = qtext

        def go():
            try:
                reply, mute, scenes, sid = cc.chat(qtext_send, st.get("dialogue", []),
                                                   st.get("voices"), flagged,
                                                   self.chat_sessions.get(job["_ji"]))
                self.chat_sessions[job["_ji"]] = sid
                self.q.put(("chat_reply", job, reply, mute, scenes, None))
            except Exception as ex:
                self.q.put(("chat_reply", job, "", [], [], str(ex)))
        threading.Thread(target=go, daemon=True).start()

    def _chat_reply(self, job, reply, mute, scenes, err):
        if not getattr(self, "chat_log", None) or not self.chat_log.winfo_exists():
            return
        self.chat_btn.config(state="normal")
        if err:
            self._log("\u26a0 " + err, "note")
            return
        log = self.chat_log
        log.configure(state="normal")
        rng = log.tag_ranges("note")
        if rng:                                   # drop the "reading…" note
            last = (rng[-2], rng[-1])
            if "reading the dialogue" in log.get(*last):
                log.delete(*last)
                self.chat_history = [h for h in self.chat_history
                                     if "reading the dialogue" not in h[0]]
        log.configure(state="disabled")
        self._log("Claude: " + reply)
        if not mute and not scenes:
            return
        d = job["analysis"]["dialogue"]
        bits = []
        if mute:
            bits.append(f"mute {len(mute)} line{'s' if len(mute) != 1 else ''} (" +
                        ", ".join(engine.cl.fmt_t(d[i]["s"]) for i in mute[:6]) +
                        ("\u2026" if len(mute) > 6 else "") + ")")
        if scenes:
            bits.append("cut " + ", ".join(f"{engine.cl.fmt_t(d[c['from']]['s'])}\u2013"
                                           f"{engine.cl.fmt_t(d[c['to']]['e'])}" for c in scenes))
        log = self.chat_log
        log.configure(state="normal")
        log.insert("end", "Suggested: " + "; ".join(bits) + "   ", "note")
        btn = ttk.Button(log, text="Add these to the list", style="Small.TButton")

        def apply():
            for i in mute:
                self._dlg_var(job["_ji"], i).set(True)
            for c in scenes:
                self._add_scene(job, max(0.0, d[c["from"]]["s"] - 0.5), d[c["to"]]["e"] + 0.5,
                                c["why"] or "Claude found this", kind="Suggested by Claude",
                                said=" ".join(l["text"] for l in d[c["from"]:c["to"] + 1]))
            self._fill_dialogue()
            btn.config(text="\u2713 Added", state="disabled")
        btn.config(command=apply)
        log.window_create("end", window=btn)
        log.insert("end", "\n")
        log.configure(state="disabled")
        log.see("end")

    def _words_card(self, parent, job, mutes):
        card = tk.Frame(parent, bg=CARD, padx=14, pady=10, highlightbackground=LINE,
                        highlightthickness=1)
        card.pack(fill="x", padx=8, pady=6)
        tk.Label(card, text="Words to mute", bg=CARD, fg=INK, font=(FONT, 11, "bold")).pack(anchor="w")
        grid = tk.Frame(card, bg=CARD)
        grid.pack(fill="x", pady=(4, 0))
        for n, m in enumerate(mutes):
            v = tk.BooleanVar(value=not m.get("keep"))
            m["_shown"] = v.get()
            self.word_vars.append((v, job, m))
            cell = tk.Frame(grid, bg=CARD)
            cell.grid(row=n // 3, column=n % 3, sticky="nw", padx=(0, 24), pady=1)
            ttk.Checkbutton(cell, text=engine.cl.fmt_t(m["s"]), variable=v).pack(side="left",
                                                                               anchor="n")
            tk.Label(cell, text=m["word"], bg=CARD, fg=INK, font=(FONT, 10, "bold")).pack(
                side="left", padx=(6, 0), anchor="n")
            note, col = claude_note(m, v.get())
            if note and m["claude"]["decision"] != "remove":
                tk.Label(cell, text=note, bg=CARD, fg=col, font=(FONT, 8), wraplength=150,
                         justify="left").pack(side="left", padx=(6, 0), anchor="n")

    def _lines_card(self, parent, job, lines):
        card = tk.Frame(parent, bg=CARD, padx=14, pady=10, highlightbackground=LINE,
                        highlightthickness=1)
        card.pack(fill="x", padx=8, pady=6)
        tk.Label(card, text="Lines to mute", bg=CARD, fg=INK, font=(FONT, 11, "bold")).pack(anchor="w")
        for l in lines:
            row = tk.Frame(card, bg=CARD)
            row.pack(fill="x", pady=2)
            v = tk.BooleanVar(value=l.get("mute", True))
            l["_shown"] = v.get()
            self.line_vars.append((v, job, l))
            ttk.Checkbutton(row, text=engine.cl.fmt_t(l["s"]), variable=v).pack(side="left", anchor="n")
            for t in l["types"]:
                name = engine.LINE_LABEL.get(t, t)
                tk.Label(row, text=name, bg=chip_color(name), fg="white", font=(FONT, 8, "bold"),
                         padx=6).pack(side="left", padx=(8, 0), anchor="n")
            txt = l["text"] if len(l["text"]) < 160 else l["text"][:157] + "\u2026"
            if l.get("learned"):
                txt += f"   ({l['learned']})"
            col_ = tk.Frame(row, bg=CARD)
            col_.pack(side="left", padx=(8, 0), fill="x")
            tk.Label(col_, text=txt, bg=CARD, fg=MUTED, font=(FONT, 9), wraplength=440,
                     justify="left", anchor="w").pack(fill="x")
            note, col = claude_note(l, v.get())
            if note:
                tk.Label(col_, text=note, bg=CARD, fg=col, font=(FONT, 8), wraplength=440,
                         justify="left", anchor="w").pack(fill="x")

    def _scene_card(self, parent, job, sc, top=False):
        card = tk.Frame(parent, bg=CARD, padx=14, pady=10, highlightbackground=LINE,
                        highlightthickness=1)
        kids = parent.pack_slaves()
        if top and kids:
            card.pack(fill="x", padx=8, pady=6, before=kids[0])
        else:
            card.pack(fill="x", padx=8, pady=6)
        top_row = tk.Frame(card, bg=CARD)
        top_row.pack(fill="x")
        v = tk.BooleanVar(value=sc.get("cut", True))
        sc["_shown"] = v.get()
        self.scene_vars.append((v, job, sc))
        secs = sc["e"] - sc["s"]
        length = f"{secs / 60:.1f} min" if secs >= 60 else f"{secs:.0f} sec"
        ttk.Checkbutton(top_row, text=f"Cut   ·   {engine.cl.fmt_t(sc['s'])}   ·   {length}",
                        variable=v).pack(side="left")
        for k in sc["kind"]:
            tk.Label(top_row, text=k, bg=chip_color(k), fg="white", font=(FONT, 9, "bold"),
                     padx=8, pady=1).pack(side="left", padx=(10, 0))
        ttk.Button(top_row, text="Preview ▸", style="Small.TButton",
                   command=lambda: self.preview(job, sc)).pack(side="right")
        mid = tk.Frame(card, bg=CARD)
        mid.pack(fill="x", pady=(8, 0))
        for t in sc.get("thumbs", [])[:3]:
            try:
                img = tk.PhotoImage(file=t)
            except tk.TclError:
                continue
            self._imgs.append(img)
            tk.Label(mid, image=img, bg=CARD, borderwidth=0).pack(side="left", padx=(0, 6))
        text = tk.Frame(mid, bg=CARD)
        text.pack(side="left", fill="both", expand=True, padx=(6, 0))
        if sc.get("why"):
            tk.Label(text, text="Found: " + sc["why"], bg=CARD, fg=INK, font=(FONT, 9),
                     wraplength=210, justify="left", anchor="w").pack(fill="x")
        said = sc.get("said") or "(no talking)"
        tk.Label(text, text="Said: " + (said if len(said) < 220 else said[:217] + "…"),
                 bg=CARD, fg=MUTED, font=(FONT, 9), wraplength=210, justify="left",
                 anchor="w").pack(fill="x", pady=(4, 0))
        note, col = claude_note(sc, v.get())
        if note:
            tk.Label(text, text=note, bg=CARD, fg=col, font=(FONT, 9, "bold"), wraplength=210,
                     justify="left", anchor="w").pack(fill="x", pady=(4, 0))

    def preview(self, job, sc):
        def go():
            try:
                self.q.put(("preview_ready", engine.make_preview(job["video"], sc["s"], sc["e"],
                                                                 job["work"])))
            except Exception as ex:
                self.q.put(("preview_error", str(ex)))
        threading.Thread(target=go, daemon=True).start()

    def _save_from_review(self):
        for j in self.jobs:
            j["cuts"], j["lines"], j["words"] = [], [], []
        for v, j, m in self.word_vars:
            if v.get():
                j["words"].append(m)
        for v, j, sc in self.scene_vars:
            if v.get():
                j["cuts"].append(sc)
        for v, j, l in self.line_vars:
            if v.get():
                j["lines"].append(l)
        good = [j for j in self.jobs if j["analysis"]]
        flagged = {(j["_ji"], l["idx"]) for _, j, l in self.line_vars if "idx" in l}
        for j in good:
            d = j["analysis"].get("dialogue", [])
            extra = [d[i] for (ji, i), v in self.dlg_vars.items()
                     if ji == j["_ji"] and v.get() and (ji, i) not in flagged and i < len(d)]
            j["lines"] += [{"s": l["s"], "e": l["e"], "text": l["text"], "plain": l["text"],
                            "types": ["added"], "mute": True} for l in extra]
            j["lines"].sort(key=lambda l: l["s"])
            try:           # remember these choices for next time
                mine = [(v, l) for v, jj, l in self.line_vars if jj is j]
                scs = [(v, sc) for v, jj, sc in self.scene_vars if jj is j]
                wds = [(v, m) for v, jj, m in self.word_vars if jj is j]
                learn.record(j["analysis"].get("show", "_movies"),
                             [l for _, l in mine], [v.get() for v, _ in mine], extra,
                             [sc for _, sc in scs if not sc.get("added")],
                             [v.get() for v, sc in scs if not sc.get("added")],
                             [sc for v, sc in scs if sc.get("added") and v.get()],
                             [m for _, m in wds], [v.get() for v, _ in wds])
            except Exception:
                pass
        self.save()

    def save(self):
        self.cancel_flag = False
        self.show_working("Saving the clean copy…")
        threading.Thread(target=self._render_thread, daemon=True).start()

    # ---------- page 4: done ----------
    def show_done(self, results):
        multi = len(results) > 1
        p = self._new_page("All done!", f"Your clean cop{'ies are' if multi else 'y is'} ready.")
        stats = tk.Frame(p, bg=BG)
        stats.pack(fill="x", pady=20)
        cm = sum(r["cut_minutes"] for r in results)
        removed = (f"{cm:.0f}", "minutes removed") if cm >= 1 else (f"{cm * 60:.0f}", "seconds removed")
        for big, small in [(str(sum(r["mutes"] for r in results)), "words & lines muted"),
                           (str(sum(r["cuts"] for r in results)), "scenes cut"), removed]:
            box = tk.Frame(stats, bg=CARD, padx=24, pady=14, highlightbackground=LINE,
                           highlightthickness=1)
            box.pack(side="left", padx=(0, 12))
            tk.Label(box, text=big, bg=CARD, fg=ACCENT, font=(FONT, 26, "bold")).pack()
            tk.Label(box, text=small, bg=CARD, fg=MUTED, font=(FONT, 10)).pack()
        tk.Label(p, text=f"Saved in:  {os.path.normpath(results[0]['folder'])}", bg=BG, fg=INK,
                 font=(FONT, 10), wraplength=740, justify="left").pack(anchor="w", pady=(4, 4))
        tk.Label(p, text="Each clean copy has “(Clean)” in its name, with a report "
                 "beside it listing everything that was muted or cut.", bg=BG, fg=MUTED,
                 font=(FONT, 10), wraplength=740, justify="left").pack(anchor="w", pady=(0, 16))
        row = tk.Frame(p, bg=BG)
        row.pack(anchor="w")
        ttk.Button(row, text="Open folder", style="Accent.TButton",
                   command=lambda: open_path(results[0]["folder"])).pack(side="left")
        if not multi:
            ttk.Button(row, text="Play it", style="Plain.TButton",
                       command=lambda: open_path(results[0]["out"])).pack(side="left", padx=12)
        ttk.Button(self.footer, text="Clean another", style="Plain.TButton",
                   command=self.reset).pack(side="right")

    def reset(self):
        self.videos, self.outdir, self.jobs = [], None, []
        self.show_setup()


if __name__ == "__main__":
    App().mainloop()
