"""CleanView — a simple window for cleaning up movies and TV episodes you own."""
import base64
import copy
import hashlib
import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
import traceback
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cleanview as engine  # noqa: E402
import cleanview_claude as cc  # noqa: E402
import cleanview_learn as learn  # noqa: E402
import videoqueue as VQ  # noqa: E402  (several videos at once)
import cvlook as look  # noqa: E402  (the drawn look: cards, switches, pill buttons)

APP_DATA = Path(os.environ.get("LOCALAPPDATA") or Path.home() / ".local" / "share") / "CleanView"
BG, CARD, INK, MUTED, ACCENT, ACCENT_DK, LINE = (
    "#F6F3EE", "#FFFFFF", "#23211F", "#6D6862", "#2F6F62", "#24574D", "#E3DED6")
BUTTON_EDGE = "#B9AFA2"
# the step-by-step look (1.18.77): the list of steps, tints, soft panels, quieter words
SIDE, TINT, SOFT, FAINT = "#EFEAE2", "#EAF2EF", "#FBFAF7", "#A39C93"
HEAD = "Segoe UI Semibold" if os.name == "nt" else "DejaVu Sans"
# Light and dark (1.18.78; the owner, 2026-11-13: "how hard would it be to add a dark mode",
# "yes it should be optional", "just light dark button option. no windows choice"). Every
# colour the window uses has a name here and a value for each look; `use_theme` sets the
# module's names (BG, CARD, ...) and the drawn pieces' colours, so code that builds a page
# always reads the look in use. Never write a colour as a literal in a page: name it here.
LIGHT = dict(
    BG="#F6F3EE", CARD="#FFFFFF", INK="#23211F", MUTED="#6D6862", ACCENT="#2F6F62",
    ACCENT_DK="#24574D", LINE="#E3DED6", BUTTON_EDGE="#B9AFA2", SIDE="#EFEAE2", TINT="#EAF2EF",
    SOFT="#FBFAF7", FAINT="#A39C93",
    NOTE="#FFF4EC", NOTE_EDGE="#EBCDB8", NOTE_INK="#C2581F",     # a note box, its edge, its heading
    DISABLED="#A9C2BC", GREY="#ECE7E0", GREY_HOVER="#E0D9CF", TROUGH="#E6E1DA",
    PLAIN_DIM="#F4F1EC", PLAIN_EDGE="#D9D2C7", RING="#CFC6B8", SOFT_EDGE="#DCD4C7",
    WARN="#B5523B", WORD_BG="#F3E3DF", WORD_INK="#8A3B2E", SHADE="#FAF8F5",
    SAY_REMOVE="#8E2B2B", SAY_FINE="#2E7D4F", SAY_WORD="#A0663A",
    PIECES=dict(off="#D8D1C6", some="#8FB5AC", tick_off="#FFFFFF", tick_edge="#9C958B",
                dim_fill="#F1EEEA", dim_edge="#CFC9C1", dim_on="#A9C2BC", bar="#D3CBC0",
                bar_hover="#B7AEA2"))
DARK = dict(
    BG="#1B1C1E", CARD="#27292C", INK="#ECE9E4", MUTED="#A39E96", ACCENT="#3F9482",
    ACCENT_DK="#4FA896", LINE="#3A3D41", BUTTON_EDGE="#4C4F54", SIDE="#141517", TINT="#20332E",
    SOFT="#202225", FAINT="#7C7872",
    # not brown in the dark look (she didn't like it round "Pick up where I left off")
    NOTE="#20332E", NOTE_EDGE="#33574E", NOTE_INK="#8FD3C2",
    DISABLED="#33504A", GREY="#303236", GREY_HOVER="#3B3E43", TROUGH="#35383C",
    PLAIN_DIM="#2B2D31", PLAIN_EDGE="#4C4F54", RING="#585B61", SOFT_EDGE="#46494E",
    WARN="#F28D76", WORD_BG="#4C2B27", WORD_INK="#F2AA9A", SHADE="#2B2D31",
    SAY_REMOVE="#F0907E", SAY_FINE="#72C691", SAY_WORD="#E3A784",
    PIECES=dict(off="#4C4F54", some="#35675C", tick_off="#27292C", tick_edge="#7A7E85",
                dim_fill="#2B2D31", dim_edge="#4C4F54", dim_on="#33504A", bar="#4C4F54",
                bar_hover="#63676E"))
THEME = "light"


def use_theme(name):
    """Light or dark: sets every colour name in this module and the drawn pieces' colours.
    Pages built after this are in that look."""
    global THEME
    THEME = "dark" if name == "dark" else "light"
    pal = DARK if THEME == "dark" else LIGHT
    globals().update({k: v for k, v in pal.items() if k != "PIECES"})
    look.use(bg=BG, card=CARD, ink=INK, muted=MUTED, accent=ACCENT, accent_dk=ACCENT_DK,
             line=LINE, side=SIDE, tint=TINT, soft=SOFT, faint=FAINT, disabled=DISABLED,
             **pal["PIECES"])


use_theme("light")
NEXT_TO_VIDEO = "A “Clean” folder next to the video"
CHIP = {"Nudity": "#B5523B", "Implied": "#C47A5A", "Graphic": "#9A4A2A", "Disturbing": "#5E3A6E", "Sex": "#9A3E66", "Intimate": "#9A3E66", "Kiss": "#B0457A",
        "Violence": "#7A5A1E", "Gore": "#8E2B2B", "Medical": "#7A4A4A", "Smoking": "#5D6470", "Drinking": "#5D6470",
        "Drugs": "#5D6470", "Immodest": "#A0663A", "Sexual": "#9A3E66", "Sleeping": "#9A3E66",
        "Same-sex": "#6B4E9B", "Unmarried": "#6B4E9B", "Crude": "#7A6A2E",
        "Bullying": "#8A4B2E", "Coroner": "#6D5A4E", "Disrespect": "#8A4B2E", "Religious": "#3F5F7F", "Rock": "#4F5560", "Rap": "#4F5560",
        "Christmas": "#2E6B45", "Halloween": "#B4621E", "Birthday": "#8C5AA8",
        "Valentine's": "#B23A5A", "Rude": "#8A4B2E", "Easter": "#6E8B2E",
        "Dark": "#4A2E5E", "Magic": "#5A4FA0", "St.": "#2E7D4F", "Vampires": "#6B2238"}


CHIP["Found"] = CHIP["Claude"] = CHIP["ChatGPT"] = CHIP["Gemini"] = "#C2581F"


# ---------- who you're filtering for: each has its own ticks, remembered separately ----------
PROFILES = [("young", "Young kids"), ("kids", "Kids"), ("teens", "Teens"), ("adults", "Adults")]
FILTER_KEYS = ["swearing", "mild", "deity", "minced", "samesexwords", "rude", "sexref", "crude",
               "forensic",
               "bullying", "disrespect", "nudity", "implied", "sex", "immodest", "casual", "kiss_os", "kiss_ss",
               "samesex", "oppsex", "violence", "graphic", "gore", "medical", "disturbing",
               "smoking",
               "drinking", "drugs", "religion", "loudmusic", "holidays", "birthday",
               "gestures", "darkmagic", "magic", "vampires"]
# "holidays" is one box for Christmas, Halloween, Valentine's, Easter and St. Patrick's Day
# (cleanview.HOLIDAYS); these were separate boxes before 1.17.1
HOLIDAYS = ("holidays", "birthday")
OLD_HOLIDAY_BOXES = ("christmas", "halloween", "valentine", "easter")
MAGIC = ("darkmagic", "magic", "vampires")
_ALL = {k: True for k in FILTER_KEYS}
_ALL.update(kiss_os="all", kiss_ss="all", religion=False,     # these two: only if she ticks them
            loudmusic=False)
# holidays and magic are taken out for the kids' ages only
NO_HOLIDAYS = dict.fromkeys(HOLIDAYS + MAGIC, False)
PRESETS = {
    "young": dict(_ALL),
    "kids": dict(_ALL, kiss_os="passionate"),
    "teens": dict(_ALL, rude=False, minced=False, crude=False, kiss_os="passionate",
                  implied=False, **NO_HOLIDAYS),
    "adults": dict(swearing=True, mild=True, deity=True, minced=False, samesexwords=True,
                   rude=False, sexref=True, crude=False, bullying=False, disrespect=False,
                   forensic=False,
                   nudity=True,
                   implied=False, sex=True, immodest=False, casual=True, kiss_os="passionate",
                   kiss_ss="passionate", samesex=False, oppsex=False, violence=True,
                   graphic=True, gore=True, medical=False, disturbing=True, smoking=False,
                   drinking=False,
                   drugs=True, religion=False, loudmusic=False, gestures=True,
                   **NO_HOLIDAYS),
}


def one_holidays_box(ticks):
    """Saved ticks from before the holidays were one box: ticked if any of them was."""
    ticks = dict(ticks)
    old = [ticks.pop(k) for k in OLD_HOLIDAY_BOXES if k in ticks]
    if old and "holidays" not in ticks:
        ticks["holidays"] = any(old)
    return ticks


def chip_color(label):
    return CHIP.get(label.split(" ")[0], "#2F6F62")


TEXT_SIZES = {"Normal": 1.0, "Larger": 1.15, "Largest": 1.3}
_text_scale = 1.0          # the chosen one, set as the window opens


def chime():
    """The Windows "information" sound, so a question is heard like the other boxes
    (a question box is silent on Windows; Jason missed the "Send it in now?" one)."""
    try:
        import winsound
        winsound.MessageBeep(winsound.MB_ICONASTERISK)
    except Exception:
        pass


def wrap_width(px):
    """A width for wrapping text that grows with the chosen text size."""
    return round(px * _text_scale)


AI_NAME = "Claude"      # whichever online AI did the review (Claude, ChatGPT or Gemini)
CLAUDE_SAYS = {"remove": ("mute the whole line", "SAY_REMOVE"),      # (the colours by name:
               "not an issue": ("not an issue", "SAY_FINE"),           # light or dark)
               "just the word": ("mute just the word", "SAY_WORD"),
               "can't tell": ("can't tell", "MUTED")}


def claude_note(item, on=None):
    c = item.get("claude")
    if not c:
        return None, None
    head, col = CLAUDE_SAYS.get(c.get("decision"), ("", "MUTED"))
    col = globals()[col]
    if c.get("decision") == "remove" and not item.get("text"):     # a scene or a word
        head = "cut" if "kind" in item else "mute"
    head = AI_NAME + ": " + head
    if c.get("word"):
        head += " " + ", ".join(f"\u201c{w.strip()}\u201d" for w in re.split(r"[|,]", c["word"])
                               if w.strip()) + " (the rest of the line stays)"
    text = head + (" \u2014 " + c["why"] if c.get("why") else "")
    if (item.get("by_you") or item.get("learned")) and on is not None and \
            c.get("decision") in ("remove", "not an issue", "just the word") and \
            on != (c["decision"] == "remove"):
        text += "  (you chose otherwise, so it stays as you set it)"
    return text, col
FONT = "Segoe UI" if os.name == "nt" else "DejaVu Sans"


def natural_key(p):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", Path(p).name)]


def fmt_len(sec):
    h, m = int(sec // 3600), int(sec % 3600 // 60)
    return f"{h} hr {m} min" if h else f"{m} min"


def logo_png(px=128):
    """CleanView's logo as PNG bytes, the size nearest px, taken from cleanview.ico (its
    pictures are PNGs, which tk can show). None if it can't be read."""
    import struct
    try:
        d = (Path(__file__).resolve().parent / "cleanview.ico").read_bytes()
        found = []
        for i in range(struct.unpack("<H", d[4:6])[0]):
            w, _, _, _, _, _, size, off = struct.unpack("<BBBBHHII", d[6 + 16 * i:22 + 16 * i])
            if d[off:off + 4] == b"\x89PNG":
                found.append((abs((w or 256) - px), d[off:off + size]))
        return min(found)[1] if found else None
    except (OSError, struct.error):
        return None


def fmt_bytes(n):
    """1.4 GB, 650 MB."""
    gb = n / 1024 ** 3
    return f"{gb:.1f} GB" if gb >= 1 else f"{max(1, round(n / 1024 ** 2))} MB"


def room_needed(n):
    """What a clean copy of about n bytes needs free: a tenth more, and 200 MB to spare."""
    return int(n * 1.1) + 200 * 1024 ** 2


def open_path(p):
    if os.name == "nt":
        os.startfile(p)  # noqa
    elif sys.platform == "darwin":
        subprocess.Popen(["open", p])
    else:
        subprocess.Popen(["xdg-open", p])


ERROR_FILE = APP_DATA / "cleanview_last_error.txt"


def _ai_status(p):
    """(provider, 'missing'/'signed_out'/'ready', whose account) for the start page.
    Slow (runs the AI's program), so called in a thread."""
    st = cc.status(p)
    return p, st, (cc.who(p) if st == "ready" else "")


def plain_error(ex):
    """What went wrong, in everyday words. The technical part is kept out of
    sight, in cleanview_last_error.txt (save_details)."""
    return VQ.plain_error(ex)        # (the workers say it the same way)


# Noticing a freeze (Jason, 2026-11-03: CleanView stopped responding during a movie and
# didn't say why). If the window doesn't answer for STALL_SECS, what every part of
# CleanView was doing is written to PROBLEM_NOTE; a hard crash is written by faulthandler
# to CRASH_LOG. Next time she's asked whether to send it in (_offer_problem_note).
PROBLEM_NOTE = APP_DATA / "stopped_last_time.txt"
CRASH_LOG = APP_DATA / "crash_log.txt"
STALL_SECS = 20


def _memory_note():
    """How much memory CleanView uses and the PC has free, for a note about a freeze."""
    try:
        import ctypes
        from ctypes import wintypes

        class Mem(ctypes.Structure):
            _fields_ = [("size", wintypes.DWORD), ("load", wintypes.DWORD)] + [
                (n, ctypes.c_ulonglong) for n in ("total", "free", "page_total", "page_free",
                                                   "virt_total", "virt_free", "ext_free")]

        class Proc(ctypes.Structure):
            _fields_ = [("size", wintypes.DWORD), ("faults", wintypes.DWORD)] + [
                (n, ctypes.c_size_t) for n in ("peak_ws", "ws", "qpp", "qp", "qnpp", "qnp",
                                               "pf", "peak_pf")]
        k32, psapi = ctypes.WinDLL("kernel32"), ctypes.WinDLL("psapi")
        k32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = (wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD)
        m, p = Mem(), Proc()
        m.size, p.size = ctypes.sizeof(m), ctypes.sizeof(p)
        if not (k32.GlobalMemoryStatusEx(ctypes.byref(m)) and
                psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(p), p.size)):
            return ""
        gb = 1024 ** 3
        return (f"Memory: CleanView uses {p.ws / gb:.1f} GB (at most {p.peak_ws / gb:.1f}); "
                f"the PC has {m.free / gb:.1f} of {m.total / gb:.1f} GB free.")
    except Exception:
        return ""


def _add_problem_note(text):
    try:
        APP_DATA.mkdir(parents=True, exist_ok=True)
        with open(PROBLEM_NOTE, "a", encoding="utf8") as f:
            f.write(text.replace(str(Path.home()), "~").rstrip() + "\n\n")
    except OSError:
        pass


def _app_version():
    try:
        return json.loads((Path(__file__).resolve().parent / "version.json").read_text())["version"]
    except Exception:
        return "?"


def save_details(text):
    """Keep the technical details of a problem, for whoever helps her."""
    try:
        APP_DATA.mkdir(parents=True, exist_ok=True)
        ERROR_FILE.write_text(text, encoding="utf8")
    except OSError:
        pass


def short(name, n=60):
    return name if len(name) <= n else name[:n - 1] + "…"


ICON = Path(__file__).resolve().parent / "cleanview.ico"
NO_INTERNET_ASK = ("There's no internet connection, so CleanView can't look for subtitles "
                   "online.\n\nVideos that have their own subtitles will still use them.\n\n"
                   "Clean without looking online?")
UPDATED_SHOWN_SECS = 3      # how long "CleanView was updated to version ..." stays up
ICON_AGAIN = (0.5, 3.0)       # seconds after the window is made that its logo is set again


def set_icon(win, path=None, again=ICON_AGAIN):
    """CleanView's logo on a window and on its button in the taskbar, not Tk's own feather
    (the owner, 2026-11-13: "sometimes the logo for clean view down in the start bar of the
    computer becomes a big feather. i noticed it after doing the recent update but it has
    done it before"). It couldn't be made to happen here, so this covers each way it could:
    the logo is made the one every window of CleanView gets (the "Ask" box had none), it's
    set on this window, and it's set again once the window is up, in case the first time
    came too early or the file had only just been written by an update. If it can't be set,
    why is kept in icon_problem.txt (APP_DATA), to read if she sees the feather again.
    Returns whether the first try worked."""
    path = str(path or ICON)

    def put():
        try:
            if not win.winfo_exists():
                return True
            win.iconbitmap(default=path)
            win.iconbitmap(path)
            return True
        except Exception as ex:
            try:
                APP_DATA.mkdir(parents=True, exist_ok=True)
                with open(APP_DATA / "icon_problem.txt", "a", encoding="utf8") as f:
                    f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {engine.app_version()} "
                            f"{type(ex).__name__}: {ex}\n")
            except Exception:
                pass
            return False
    ok = put()
    for secs in again:
        try:
            win.after(int(secs * 1000), put)
        except Exception:
            pass
    return ok


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CleanView")
        # bigger text if she chose it: Tk sizes text as each part of the window is built,
        # so this comes first (and changing it builds the page again, see _set_text_size)
        self._base_scaling = float(self.tk.call("tk", "scaling"))
        self.text_size = self._load_settings().get("text_size")
        if self.text_size not in TEXT_SIZES:
            self.text_size = "Normal"
        global _text_scale
        _text_scale = TEXT_SIZES[self.text_size]
        self.tk.call("tk", "scaling", self._base_scaling * _text_scale)
        self._fit_window()
        self.theme = "dark" if self._load_settings().get("theme") == "dark" else "light"
        use_theme(self.theme)
        self.configure(bg=BG)
        self.after(80, self._title_bar)
        set_icon(self)
        self.q = queue.Queue()
        self.cancel_flag = False
        self.videos, self.outdir, self.jobs = [], None, []
        self._imgs = []
        self._style()
        self.page = None
        self.page_name = None
        self.upd_bar = None
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        if not (os.environ.pop("CLEANVIEW_RESUME", None) and self._resume()):
            self.show_setup()
        self._poll_id = self.after(100, self._poll)
        self._watch_for_freezes()
        self._offer_id = self.after(2500, self._offer_problem_note)
        self.after(4000, self._check_update)
        self.bind_all("<F5>", lambda e: self._check_update(manual=True))

    def _fit_window(self, grow_only=False):
        """Size the window for the text size, centred on the screen. grow_only: after a
        text size change, never smaller than she has made it (and left alone maximised)."""
        scale = max(1.0, self.winfo_fpixels("1i") / 96.0)
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w = min(int(940 * scale), sw - 40)       # the list of steps down the left (1.18.77)
        h = min(int(800 * scale), sh - 90)
        self.minsize(min(w, int(660 * scale)), min(h, int(500 * scale)))
        if grow_only:
            if self.state() == "zoomed":
                return
            w, h = max(w, self.winfo_width()), max(h, self.winfo_height())
        self.geometry(f"{w}x{h}+{max(0, (sw - w) // 2)}+{max(0, (sh - h) // 2 - 20)}")

    # ---------- updating without losing your place ----------
    SESSION = APP_DATA / "last_review.json"

    def _launcher(self):
        import importlib.machinery
        import importlib.util
        path = Path(__file__).resolve().parent / "launcher.pyw"
        loader = importlib.machinery.SourceFileLoader("cv_launcher", str(path))
        spec = importlib.util.spec_from_loader("cv_launcher", loader)
        mod = importlib.util.module_from_spec(spec)
        loader.exec_module(mod)
        return mod

    def _check_update(self, manual=False):
        """Look for a newer version now and every 30 minutes; show a button if there is one.
        manual: the person asked (F5 or the button), so say so if there's nothing new."""
        def go():
            try:
                import urllib.request
                lm = self._launcher()
                local = json.loads((lm.HERE / "version.json").read_text())
                with urllib.request.urlopen(lm.RAW + "version.json", timeout=6) as r:
                    remote = json.loads(r.read().decode("utf8"))
                if lm._ver(remote["version"]) > lm._ver(local["version"]):
                    self.q.put(("update_ready", remote["version"]))
                elif manual:
                    self.q.put(("update_none", local["version"]))
            except Exception:
                if manual:
                    self.q.put(("update_none", None))
        threading.Thread(target=go, daemon=True).start()
        if not manual:
            self.after(30 * 60 * 1000, self._check_update)

    def _show_update_bar(self, ver):
        if self.upd_bar is not None and self.upd_bar.winfo_exists():
            self.upd_lbl.config(text=f"A new version of CleanView ({ver}) is ready.")
            return
        bar = tk.Frame(self, bg=TINT)
        bar.pack(side="top", fill="x", before=self.page)
        self.upd_lbl = tk.Label(bar, text=f"A new version of CleanView ({ver}) is ready.",
                                bg=TINT, fg=ACCENT_DK, font=(FONT, 10), padx=12, pady=6)
        self.upd_lbl.pack(side="left")
        self.upd_btn = ttk.Button(bar, text="Update now (keeps your place)", style="Small.TButton",
                                  command=self.update_now)
        self.upd_btn.pack(side="right", padx=10, pady=4)
        self.upd_bar = bar

    def _save_session(self):
        """Save the review exactly as it is: everything found and every tick."""
        if self.page_name != "review":
            return False
        good = [j for j in self.jobs if j["analysis"]]
        if not good:
            return False
        for j in good:
            try:
                self._sync_job(j)
            except Exception:
                pass
            try:
                (Path(j["work"]) / "analysis.json").write_text(json.dumps(j["analysis"], indent=1))
            except OSError:
                pass
        sess = {"saved": time.strftime("%Y-%m-%d %H:%M"), "outdir": self.outdir,
                "jobs": [{"video": j["video"], "work": str(j["work"])} for j in good],
                "show_fine": getattr(self, "show_fine", False),
                "chat": getattr(self, "chat_history", [])[-60:]}
        try:
            APP_DATA.mkdir(parents=True, exist_ok=True)
            self.SESSION.write_text(json.dumps(sess, indent=1), encoding="utf8")
            return True
        except OSError:
            return False

    def _resume(self, sess=None):
        """Open the last review again. Returns True if it could."""
        try:
            sess = sess or json.loads(self.SESSION.read_text("utf8"))
            jobs = []
            for j in sess["jobs"]:
                a = json.loads((Path(j["work"]) / "analysis.json").read_text())
                jobs.append({"video": j["video"], "work": Path(j["work"]), "analysis": a,
                             "error": None, "cuts": [], "lines": [], "words": []})
        except Exception:
            return False
        if not jobs:
            return False
        self.jobs = jobs
        engine.cl.use_language((jobs[0]["analysis"].get("opts") or {}).get("language"))
        self.videos = [j["video"] for j in jobs]
        self.outdir = sess.get("outdir")
        self.show_fine = sess.get("show_fine", False)
        self.chat_history = [tuple(x) for x in sess.get("chat", [])]
        self.chat_sessions = {}
        self.show_review()
        return True

    def _forget_session(self):
        try:
            self.SESSION.unlink()
        except OSError:
            pass

    def _on_close(self):
        if self.page_name == "review":
            self._save_session()        # closing by accident never loses the review
        elif self.page_name == "setup":
            self._save_settings()       # nor the ticks just changed on the start page
        elif self.page_name == "working":
            chime()
            if not messagebox.askyesno(
                    "CleanView is still working",
                    "If you close CleanView now, this stops. Starting the same videos again "
                    "later skips the steps that are already done.\n\nClose anyway?",
                    icon="warning", default="no", parent=self):
                return
            engine.PAUSE.resume()         # frozen helpers couldn't stop
            self.cancel_flag = True       # lets the saving step stop and tidy up first
            self.after(1500, self.destroy)
            return
        self.destroy()

    def _problem(self, plain, details=None):
        """Say what went wrong in plain words; the details go in a file instead."""
        if details:
            save_details(details)
        if messagebox.askyesno("CleanView ran into a problem",
                               plain + ("\n\nThe details are saved in a file, for anyone helping "
                                        "you. Open that file now?" if details else ""),
                               icon="error", default="no", parent=self) and details:
            try:
                open_path(str(ERROR_FILE))
            except OSError:
                pass

    def update_now(self):
        if self.upd_bar is None or not self.upd_bar.winfo_exists():
            self._show_update_bar("")
        if self.page_name == "working":
            messagebox.showinfo("CleanView", "CleanView is busy right now. Update when it's "
                                "finished (the button will still be here).")
            return
        self._save_settings()           # the start page's ticks, changed since it opened
        self._save_session()
        self.upd_btn.config(state="disabled")
        self.upd_lbl.config(text="Updating\u2026")

        def go():
            try:
                new = self._launcher().update()
                self.q.put(("update_done", new, None))
            except Exception as ex:
                self.q.put(("update_done", None, str(ex)))
        threading.Thread(target=go, daemon=True).start()

    def _update_done(self, new, err):
        if err:
            self.upd_lbl.config(text="The update didn't download. Try again in a bit.")
            self.upd_btn.config(state="normal")
            return
        env = dict(os.environ)
        env["CLEANVIEW_UPDATED"] = f"CleanView was updated to version {new}." if new else \
            "CleanView is up to date."
        if self.page_name == "review":
            env["CLEANVIEW_RESUME"] = "1"
        launcher = Path(__file__).resolve().parent / "launcher.pyw"
        subprocess.Popen([sys.executable, str(launcher)], env=env,
                         cwd=str(launcher.parent))
        self.destroy()

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
        s.configure("Treeview", rowheight=round(self.winfo_fpixels("18p")), font=(FONT, 9))
        s.map("TCheckbutton", background=[("active", CARD)])
        s.configure("Bg.TCheckbutton", background=BG, font=(FONT, 10))
        s.map("Bg.TCheckbutton", background=[("active", BG)])
        # the AI helper's tick box, one size bigger so it stands out (1.18.76)
        s.configure("Big.TCheckbutton", background=CARD, font=(FONT, 11))
        s.map("Big.TCheckbutton", background=[("active", CARD)])
        self._tick_boxes(s)
        s.configure("Accent.TButton", background=ACCENT, foreground="white",
                    font=(FONT, 12, "bold"), padding=(22, 10), borderwidth=0)
        s.map("Accent.TButton", background=[("active", ACCENT_DK), ("disabled", DISABLED)])
        # Each page's main step is the big green button, bottom right (Start cleaning, Save
        # clean copy, Clean another); a first step is a smaller green one (Choose files…).
        # Grey ones have an edge, so they read as buttons, not part of the page.
        s.configure("Go.TButton", background=ACCENT, foreground="white",
                    font=(FONT, 11, "bold"), padding=(16, 7), borderwidth=0)
        s.map("Go.TButton", background=[("active", ACCENT_DK), ("disabled", DISABLED)])
        # Choose files, a fifth bigger than the other first steps (1.18.75)
        s.configure("Choose.TButton", background=ACCENT, foreground="white",
                    font=(FONT, 13, "bold"), padding=(20, 9), borderwidth=0)
        s.map("Choose.TButton", background=[("active", ACCENT_DK), ("disabled", DISABLED)])
        edge = {"bordercolor": BUTTON_EDGE, "lightcolor": GREY, "darkcolor": GREY}
        s.configure("Plain.TButton", background=GREY, foreground=INK, padding=(14, 6),
                    borderwidth=1, font=(FONT, 10), **edge)
        s.map("Plain.TButton", background=[("active", GREY_HOVER)])
        s.configure("Small.TButton", background=GREY, foreground=INK, padding=(10, 3),
                    borderwidth=1, font=(FONT, 9), **edge)
        s.map("Small.TButton", background=[("active", GREY_HOVER)])
        s.configure("Green.Horizontal.TProgressbar", troughcolor=TROUGH,
                    background=ACCENT, bordercolor=TROUGH, lightcolor=ACCENT, darkcolor=ACCENT)
        # The drawn look for the ttk widgets too (1.18.77): rounded buttons (green ones
        # filled, the others white with a soft edge), tabs as pills, thin scroll bars, a
        # rounded progress bar, and white fields that turn green at the edge when typed in.
        green = (ACCENT, ACCENT_DK, DISABLED, None, "#FFFFFF")
        white = (CARD, TINT, PLAIN_DIM, PLAIN_EDGE, FAINT)
        look.round_buttons(self, {"Accent.TButton": green, "Go.TButton": green,
                                  "Choose.TButton": green, "Plain.TButton": white,
                                  "Small.TButton": white})
        look.style_scrollbars(self, s)
        look.style_tabs(self, s)
        look.style_progress(self, s, "Green.Horizontal.TProgressbar", bg=CARD)
        look.style_fields(s)
        look.style_dropdown(self, s)        # "Round.TCombobox": the language list (1.18.85)
        for what, colour in (("background", CARD), ("foreground", INK),
                             ("selectBackground", TINT), ("selectForeground", INK)):
            self.option_add(f"*TCombobox*Listbox.{what}", colour)
        self.option_add("*Text.insertBackground", INK)
        s.configure("Treeview", background=CARD, fieldbackground=CARD, bordercolor=LINE,
                    lightcolor=CARD, darkcolor=CARD, borderwidth=1)
        s.configure("Treeview.Heading", background=SIDE, foreground=MUTED, relief="flat",
                    font=(HEAD, 9), padding=(6, 4))
        s.map("Treeview.Heading", background=[("active", SIDE)])
        s.map("Treeview", background=[("selected", TINT)], foreground=[("selected", INK)])

    def _tick_boxes(self, s):
        """Tick boxes that show a tick when ticked. The theme's own show an ✗, which
        reads as "no" (so a ticked "Swearing" looked like swearing was left in)."""
        # Drawn smooth and rounded (cvlook, 1.18.77) into the same images each time (a new
        # text size redraws them): the theme can't be given a second "Tick.indicator".
        first = not hasattr(self, "_ticks")
        self._ticks = look.tick_images(self, None if first else self._ticks)
        t = self._ticks
        if not first:
            return
        s.element_create("Tick.indicator", "image", t["off"],
                         ("selected", "disabled", t["on_dim"]), ("disabled", t["off_dim"]),
                         ("selected", t["on"]), sticky="")
        s.layout("TCheckbutton", [("Checkbutton.padding", {"sticky": "nswe", "children": [
            ("Tick.indicator", {"side": "left", "sticky": ""}),
            ("Checkbutton.focus", {"side": "left", "sticky": "w", "children": [
                ("Checkbutton.label", {"sticky": "nswe"})]})]})])

    def _new_page(self, title, subtitle="", name=""):
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.unbind_all(seq)
        if self.page:
            self.page.destroy()
        self._imgs = []
        X = self._px
        self.page = tk.Frame(self, bg=BG)
        self.page.pack(fill="both", expand=True, padx=X(36), pady=(X(24), X(16)))
        self.footer = tk.Frame(self.page, bg=BG)
        self.footer.pack(side="bottom", fill="x", pady=(X(10), 0))
        tk.Frame(self.footer, bg=LINE, height=1).pack(side="top", fill="x", pady=(0, X(12)))
        if name:                # which video this is (Jason: "you don't know what you've cleaned")
            tk.Label(self.page, text=name, bg=BG, fg=ACCENT, font=(HEAD, 11),
                     wraplength=wrap_width(860), justify="left").pack(anchor="w", pady=(0, X(2)))
        tk.Label(self.page, text=title, bg=BG, fg=INK, font=(HEAD, 21)).pack(anchor="w")
        if subtitle:
            tk.Label(self.page, text=subtitle, bg=BG, fg=MUTED, font=(FONT, 10),
                     wraplength=wrap_width(760), justify="left").pack(anchor="w",
                                                                      pady=(X(4), X(14)))
        return self.page

    def _round_card(self, parent, before=None, fill=None, edge=None, pad=(16, 12)):
        """A rounded card on a scrolling page (a scene, the lines, the words); returns the
        frame to put things in."""
        card = look.Card(parent, fill=fill or CARD, edge=LINE if edge is None else edge,
                         radius=12, pad=pad)
        if before is not None:
            card.pack(fill="x", padx=self._px(8), pady=self._px(6), before=before)
        else:
            card.pack(fill="x", padx=self._px(8), pady=self._px(6))
        return card.body

    def _scroll_to(self, w):
        """Scroll the page w is on (a _scroll_area) so w can be seen (on the start page,
        showing its step first)."""
        step = w
        while step is not None and getattr(step, "_step_no", None) is None:
            step = step.master
        if step is not None and step._step_no != getattr(self, "_setup_step", 1):
            self._go_step(step._step_no)
        inner = w                       # the scroll area's own frame (a look.Card is a
        while inner is not None and getattr(inner, "_canvas", None) is None:    # canvas too)
            inner = inner.master
        if inner is None:
            return
        canvas = inner._canvas
        self.update_idletasks()
        h = inner.winfo_height()
        if h > 0:
            canvas.yview_moveto(max(0.0, (w.winfo_rooty() - inner.winfo_rooty() - 120) / h))

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
        inner._canvas = canvas
        return inner

    # ---------- page 1: setup, one step at a time ----------
    # The owner, 2026-11-12: "the ui also feels clunky and dated, can you make it feel classy
    # (all of them)", then chose "B, step by step" of two mock-ups: a list of the four steps
    # down the left (each saying what's chosen), one step at a time on the right, Back and
    # Next, and Start cleaning always there (her choices are remembered, so once the videos
    # are chosen she can start). Drawn pieces are in cvlook.py (1.18.77).
    STEPS = [("Movie or episodes", "Choose what to clean. Your original files are never changed."),
             ("What to remove", "Swear words are muted automatically. Everything else is listed "
                                "for you to check before anything is muted or cut."),
             ("AI helper", "It double-checks the scenes and reads the dialogue. Recommended."),
             ("Save to", "Where the clean copies go.")]

    def _px(self, n):
        return look.px(self, n)

    def _go_step(self, n):
        """Show step n (1-4) of the start page, and only that step."""
        n = max(1, min(len(self.STEPS), n))
        self._setup_step = n
        panes = getattr(self, "_panes", None)
        if not panes or not panes[0].winfo_exists():
            return
        for i, pane in enumerate(panes, 1):
            if i == n:
                pane.pack(fill="x")
            else:
                pane.pack_forget()
        title, sub = self.STEPS[n - 1]
        self._step_tag.config(text=f"STEP {n} OF {len(self.STEPS)}")
        self._step_title.config(text=title)
        self._step_sub.config(text=sub)
        canvas = getattr(self._panes_inner, "_canvas", None)
        if canvas is not None:
            canvas.yview_moveto(0)
        if n > 1:
            self.back_btn.pack(side="left")
        else:
            self.back_btn.pack_forget()
        if n < len(self.STEPS):
            self.next_btn.config(text=f"Next: {self.STEPS[n][0]}")
            self.next_btn.pack(side="right", padx=(0, self._px(10)))
        else:
            self.next_btn.pack_forget()
        self._show_steps()

    def _step_summary(self, n):
        """What's chosen in step n, in a few words, for the list on the left."""
        if n == 1:
            k = len(self.videos)
            return ("Nothing chosen yet" if not k else
                    "1 video chosen" if k == 1 else f"{k} videos chosen")
        if n == 2:
            return dict(PROFILES).get(getattr(self, "profile", ""), "")
        if n == 3:
            o = getattr(self, "opts", {})
            r = o["reader"].get() if "reader" in o else "local"
            if r in cc.NAMES:
                return cc.name(r)
            return "This PC" if o.get("ai") is None or o["ai"].get() else "Off"
        if self.outdir:
            p = Path(self.outdir)
            return p.name or str(p)
        return "Next to the videos"

    def _show_steps(self):
        rows = getattr(self, "_step_rows", None)
        if not rows or not rows[0][0].winfo_exists():
            return
        now = getattr(self, "_setup_step", 1)
        for i, (card, badge, name, summary) in enumerate(rows, 1):
            current = i == now
            card.recolour(fill=CARD if current else SIDE, edge=LINE if current else "")
            done = i == 1 and bool(self.videos)
            if done:
                badge.set(icon="check", text=None, fill=ACCENT, fg="#FFFFFF", edge=None)
            else:
                badge.set(icon=None, text=str(i), fill=card.fill,
                          fg=ACCENT if current else MUTED, edge=ACCENT if current else RING)
            name.config(fg=INK if current else MUTED)
            summary.config(text=short(self._step_summary(i), 28))

    def _text_size_menu(self, widget):
        m = tk.Menu(self, tearoff=0)
        for name in TEXT_SIZES:
            m.add_command(label=("✓ " if name == self.text_size else "    ") + name,
                          command=lambda n=name: self._set_text_size(n))
        m.tk_popup(widget.winfo_rootx(), widget.winfo_rooty() - self._px(90))

    def _set_theme(self, name):
        """Light or dark, from the button under the steps: the start page is built again in
        that look (as a new text size does), keeping the videos chosen and every tick."""
        name = "dark" if name == "dark" else "light"
        if name == self.theme:
            return
        self.theme = name
        self._save_settings()               # the ticks, which the page is built from
        use_theme(name)
        self.configure(bg=BG)
        self._style()                       # the ttk styles and tick boxes in that look
        bar = self.upd_bar
        if bar is not None and bar.winfo_exists():      # "a new version is ready"
            for w in [bar] + [c for c in bar.winfo_children() if isinstance(c, tk.Label)]:
                w.configure(bg=TINT)
            self.upd_lbl.configure(fg=ACCENT_DK)
        self._title_bar()
        self.show_setup()

    def _title_bar(self):
        """The window's own title bar dark with the dark look (Windows 10 and 11). Where
        Windows can't, nothing happens."""
        try:
            import ctypes
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            on = ctypes.c_int(1 if self.theme == "dark" else 0)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(on), 4)
            # the bar is only drawn again when the frame changes: say it has
            ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0027)
        except Exception:
            pass

    def show_setup(self):
        self.page_name = "setup"
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.unbind_all(seq)
        if self.page:
            self.page.destroy()
        self._imgs = []
        X = self._px
        p = self.page = tk.Frame(self, bg=BG)
        p.pack(fill="both", expand=True)
        try:
            ver = json.loads((Path(__file__).resolve().parent / "version.json").read_text())["version"]
            self.title(f"CleanView {ver}")
        except Exception:
            pass

        # ----- the list of steps, down the left
        side = tk.Frame(p, bg=SIDE, width=X(236))
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        brand = tk.Frame(side, bg=SIDE)
        brand.pack(fill="x", padx=X(22), pady=(X(26), X(22)))
        logo = None
        png = logo_png(X(40))
        if png:
            try:
                logo = tk.PhotoImage(data=base64.b64encode(png).decode())
                while logo.width() > X(52):
                    logo = logo.subsample(2)
            except tk.TclError:
                logo = None
        if logo is not None:
            self._imgs.append(logo)
            tk.Label(brand, image=logo, bg=SIDE).pack(side="left", padx=(0, X(10)))
        else:
            look.Badge(brand, "video", size=38, fill=ACCENT, fg="#FFFFFF").pack(
                side="left", padx=(0, X(10)))
        tk.Label(brand, text="CleanView", bg=SIDE, fg=INK, font=(HEAD, 15)).pack(side="left")
        self._step_rows = []
        for i, (title, _) in enumerate(self.STEPS, 1):
            card = look.Card(side, fill=SIDE, edge="", radius=12, pad=(12, 9))
            card.pack(fill="x", padx=X(14), pady=X(2))
            row = card.body
            badge = look.Badge(row, None, size=26, circle=True, text=str(i))
            badge.pack(side="left", padx=(0, X(12)))
            words = tk.Frame(row, bg=SIDE)
            words.pack(side="left", fill="x", expand=True)
            name = tk.Label(words, text=title, bg=SIDE, fg=MUTED, font=(HEAD, 10), anchor="w")
            name.pack(anchor="w")
            summary = tk.Label(words, text="", bg=SIDE, fg=FAINT, font=(FONT, 9), anchor="w")
            summary.pack(anchor="w")
            card.clickable(lambda i=i: self._go_step(i))
            self._step_rows.append((card, badge, name, summary))
        extras = tk.Frame(side, bg=SIDE)
        extras.pack(side="bottom", fill="x", padx=X(24), pady=(0, X(22)))
        self.size_link = look.link(extras, f"Text size: {self.text_size}",
                                   lambda: self._text_size_menu(self.size_link), icon="text",
                                   size=9, fg=MUTED, bold=False)
        self.size_link.pack(anchor="w", pady=X(3))
        look.link(extras, "Check for updates", lambda: self._check_update(manual=True),
                  icon="refresh", size=9, fg=MUTED, bold=False).pack(anchor="w", pady=X(3))
        look.link(extras, "Send what CleanView learned…", self.share_learned, icon="send",
                  size=9, fg=MUTED, bold=False).pack(anchor="w", pady=X(3))
        # light or dark (1.18.78)
        self.theme_var = tk.StringVar(value=self.theme)
        look.Segmented(extras, [("light", "Light"), ("dark", "Dark")], self.theme_var,
                       command=lambda: self._set_theme(self.theme_var.get()), size=9,
                       tray=LINE).pack(anchor="w", pady=(X(12), 0))

        # ----- the step itself, on the right
        main = tk.Frame(p, bg=BG)
        main.pack(side="left", fill="both", expand=True, padx=(X(36), X(32)), pady=(X(24), 0))
        self.footer = tk.Frame(main, bg=BG)
        self.footer.pack(side="bottom", fill="x")
        tk.Frame(self.footer, bg=LINE, height=1).pack(fill="x")
        nav = tk.Frame(self.footer, bg=BG)
        nav.pack(fill="x", pady=(X(14), X(18)))
        self.start_btn = look.Pill(nav, "Start cleaning", self.start, after="next", size=12,
                                   pad=(24, 11))
        self.start_btn.pack(side="right")
        self.next_btn = look.Pill(nav, "Next", lambda: self._go_step(self._setup_step + 1),
                                  kind="secondary", after="next", size=11, pad=(20, 10))
        self.back_btn = look.Pill(nav, "Back", lambda: self._go_step(self._setup_step - 1),
                                  kind="quiet", icon="back", size=11, pad=(16, 10))

        upd = os.environ.pop("CLEANVIEW_UPDATED", None)
        if upd:
            # said for a few seconds, then gone (the owner, 2026-11-13: "when it updates clean
            # view it leaves a long bar on the top it should go away after 3 seconds")
            said = self.updated_note = tk.Label(main, text="✓ " + upd, bg=TINT, fg=ACCENT_DK,
                                                font=(FONT, 10), padx=X(12), pady=X(7),
                                                anchor="w")
            said.pack(fill="x", pady=(0, X(12)))
            self.after(int(UPDATED_SHOWN_SECS * 1000),
                       lambda: said.winfo_exists() and said.destroy())
        try:
            sess = json.loads(self.SESSION.read_text("utf8"))
            names = [Path(j["video"]).name for j in sess["jobs"]]
        except Exception:
            sess = None
        if sess and names:
            box = look.Card(main, fill=NOTE, edge=NOTE_EDGE, radius=12, pad=(16, 10))
            box.pack(fill="x", pady=(0, X(14)))
            what = short(names[0], 40) + (f" and {len(names) - 1} more" if len(names) > 1 else "")
            tk.Label(box.body, text=f"Your last review isn't finished: {what}\n(saved "
                     f"{sess['saved']})", bg=NOTE, fg=INK, font=(FONT, 10),
                     justify="left", anchor="w").pack(side="left")

            def pick_up(sess=sess):
                if not self._resume(sess):
                    messagebox.showinfo("CleanView", "That review couldn't be opened (the files "
                                        "may have been moved). Start it again.")
                    self._forget_session()
                    self.show_setup()

            look.Pill(box.body, "Pick up where I left off", pick_up, size=10,
                      pad=(16, 8)).pack(side="right")
            look.Pill(box.body, "Discard", lambda: (self._forget_session(), box.destroy()),
                      kind="quiet", size=10, pad=(12, 8)).pack(side="right", padx=(0, X(6)))
        self._step_tag = tk.Label(main, text="", bg=BG, fg=ACCENT, font=(HEAD, 8), anchor="w")
        self._step_tag.pack(anchor="w")
        self._step_title = tk.Label(main, text="", bg=BG, fg=INK, font=(HEAD, 21), anchor="w")
        self._step_title.pack(anchor="w", pady=(X(2), 0))
        self._step_sub = tk.Label(main, text="", bg=BG, fg=MUTED, font=(FONT, 10), anchor="w",
                                  justify="left", wraplength=wrap_width(540))
        self._step_sub.pack(anchor="w", pady=(X(4), X(16)))
        body = self._panes_inner = self._scroll_area(main)
        self._panes = []

        def pane(n):
            f = tk.Frame(body, bg=BG)
            f._step_no = n
            self._panes.append(f)
            return f

        self.opts = {}
        saved = self._load_settings()

        # ----- step 1: the videos
        p1 = pane(1)
        drop = look.Card(p1, fill=SOFT, edge=SOFT_EDGE, radius=16, pad=(20, 18))
        drop.pack(fill="x", padx=(0, X(4)))
        look.Badge(drop.body, "folder", size=54, icon_size=20).pack(side="left")
        words = tk.Frame(drop.body, bg=SOFT)
        words.pack(side="left", fill="x", expand=True, padx=(X(16), X(12)))
        tk.Label(words, text="Choose a movie or episodes", bg=SOFT, fg=INK, font=(HEAD, 13),
                 anchor="w").pack(anchor="w")
        tk.Label(words, text="For a whole season, open its folder and press Ctrl+A to choose "
                 "every episode.", bg=SOFT, fg=MUTED, font=(FONT, 9), anchor="w",
                 wraplength=wrap_width(260), justify="left").pack(anchor="w", pady=(X(2), 0))
        self.choose_btn = look.Pill(drop.body, "Choose files…", self.pick_files, size=12,
                                    pad=(22, 11))
        self.choose_btn.pack(side="right")
        self.vid_lbl = tk.Label(p1, text="Nothing chosen yet", bg=BG, fg=MUTED, font=(FONT, 10),
                                wraplength=wrap_width(560), justify="left", anchor="w")
        self.vid_lbl.pack(anchor="w", pady=(X(12), 0))
        # Subtitles are always looked for online when a video has none: there was a switch
        # for it here (the owner, 2026-11-13: "that part says look for subtitles with a
        # choice. i think subtitles are important enough that they should be standard"), so
        # it's said in the small print below instead, and _current_opts always asks for them.
        # the language spoken (1.18.80; the owner: "like if i wanted to scan a movie in
        # spanish"): English as always, or another one, with its own word lists
        spoken = look.Card(p1)
        spoken.pack(fill="x", pady=(X(14), 0), padx=(0, X(4)))
        v = tk.StringVar(value=engine.cvlang.known(saved.get("language")))
        self.opts["language"] = v
        words = tk.Frame(spoken.body, bg=CARD)
        words.pack(side="left", fill="x", expand=True, padx=(0, X(12)))
        tk.Label(words, text="Language spoken in the video", bg=CARD, fg=INK, font=(HEAD, 10),
                 anchor="w").pack(anchor="w")
        tk.Label(words, text="For another language CleanView uses that language's own word "
                 "lists. The first time, it gets a listening model for it (one time, about "
                 f"{engine.cvlang.MODEL_MB} MB).", bg=CARD, fg=MUTED, font=(FONT, 9),
                 wraplength=wrap_width(330), justify="left", anchor="w").pack(
                     anchor="w", pady=(X(2), 0))
        # a drop-down list, so more languages don't crowd the page (the owner, 2026-11-13: "as
        # we get more languages, instead of labelling them all on the front page, should we
        # have a a drop down"). It shows the names; the choice kept is the language's code.
        # (its own names for everything: `v`, `names` and the like are used again further down
        # this page, and what's picked here must still mean the language then)
        lang_var, lang_names = v, dict(engine.cvlang.LANGS)
        lang_codes = {name: code for code, name in lang_names.items()}
        lang_shown = tk.StringVar(value=lang_names[lang_var.get()])
        lang_box = self.language_box = ttk.Combobox(
            spoken.body, textvariable=lang_shown, values=list(lang_names.values()),
            state="readonly", width=12, font=(FONT, 10), style="Round.TCombobox")
        lang_box.pack(side="right")

        def lang_picked(_e=None):
            lang_var.set(lang_codes.get(lang_shown.get(), "en"))
            lang_box.selection_clear()
        lang_box.bind("<<ComboboxSelected>>", lang_picked)
        lang_box.bind("<MouseWheel>", lambda e: "break")    # scrolling past mustn't change it
        lang_var.trace_add("write", lambda *_: lang_shown.set(
            lang_names[engine.cvlang.known(lang_var.get())]))
        tk.Label(p1, text="Works with DRM-free files: DVD and Blu-ray rips, home videos and "
                 "downloads without copy protection. Subtitles give the exact words, who's "
                 "talking and descriptions like [kissing], so they're always used: the video's "
                 "own, or ones found online when it has none. They get cleaned too.", bg=BG,
                 fg=FAINT, font=(FONT, 9), wraplength=wrap_width(560),
                 justify="left").pack(anchor="w", pady=(X(16), 0))

        # ----- step 2: what to remove
        p2 = pane(2)
        # the folder she chose to save in, kept when CleanView closes (1.18.76)
        self.save_to = saved.get("save_to") or None
        if not self.outdir:
            self.outdir = self._remembered_folder()
        profiles = saved.get("profiles")
        if profiles is None:            # first time: your old ticks become your "Adults" ticks
            old = {k: saved[k] for k in FILTER_KEYS if k in saved}
            profiles = {"adults": old} if old else {}
        self.profiles = {p: dict(PRESETS[p], **one_holidays_box(profiles.get(p, {})))
                         for p, _ in PROFILES}
        self.profile = saved.get("profile") or ("adults" if profiles.get("adults") else "young")
        cur = self.profiles[self.profile]
        prow = tk.Frame(p2, bg=BG)
        prow.pack(fill="x", padx=(0, X(4)))
        self.profile_var = tk.StringVar(value=self.profile)
        look.Segmented(prow, PROFILES, self.profile_var, command=self._profile_changed).pack(
            side="left")
        look.link(prow, "Reset to standard", self._profile_reset, size=9).pack(side="right")
        tk.Label(p2, text="Each age remembers its own choices, and what CleanView learns from "
                 "them is kept separately for each.", bg=BG, fg=MUTED, font=(FONT, 9),
                 wraplength=wrap_width(560), justify="left").pack(anchor="w", pady=(X(8), 0))
        tiles = tk.Frame(p2, bg=BG)
        tiles.pack(fill="x", pady=(X(10), 0))
        for c in range(3):
            tiles.columnconfigure(c, weight=1, uniform="tiles")
        # A section's boxes open right under its own row of tiles, not under all nine (the
        # owner, 2026-11-13: "id like each one to open right below its chosen option"): the
        # tiles are in rows 0, 2 and 4 of the grid, and this card goes in the row between.
        detail = self._section_detail = look.Card(tiles, radius=14, pad=(18, 14), edge=ACCENT,
                                                  edge_w=2.0)
        dhead = tk.Frame(detail.body, bg=CARD)
        dhead.pack(fill="x", pady=(0, X(8)))
        dname = tk.Label(dhead, text="", bg=CARD, fg=INK, font=(HEAD, 12), anchor="w")
        dname.pack(side="left")
        dbody = tk.Frame(detail.body, bg=CARD)
        dbody.pack(fill="x")

        # Sections by topic, each a tile with a switch that turns all of it on or off, and
        # its boxes shown under the tiles when opened (the owner, 2026-11-12: "a main box for
        # each category to tick all if wanted, but if only some of the subcategories are
        # wanted just those can be ticked. vid angel had a system like that").
        levels = {"Keep": "off", "Cut passionate kisses": "passionate", "Cut all kisses": "all"}
        self.level_names = {v: k for k, v in levels.items()}
        self.level_values = levels
        self._open_sections = set((saved.get("open_sections") or [])[:1])
        self._section_heads = {}
        shows = {}

        def checks(grid, items, cols=2):
            out = []
            for n, (key, label, on) in enumerate(items):
                v = tk.BooleanVar(value=cur.get(key, on))
                self.opts[key] = v
                ttk.Checkbutton(grid, text=label, variable=v).grid(
                    row=n // cols, column=n % cols, sticky="w", padx=(0, X(26)), pady=X(2))
                out.append(v)
            return out

        def kiss_menus(grid):
            out = []
            for row, (key, label, default) in enumerate([("kiss_os", "Man & woman kissing",
                                                          "passionate"),
                                                         ("kiss_ss", "Same-sex kissing",
                                                          "passionate")]):
                tk.Label(grid, text=label, bg=CARD, fg=INK, font=(FONT, 10)).grid(
                    row=row, column=0, sticky="w", padx=(0, X(14)), pady=X(3))
                v = tk.StringVar(value=self.level_names[cur.get(key, default)])
                self.opts[key] = v
                look.Segmented(grid, [("Keep", "Keep"), ("Cut passionate kisses", "Passionate"),
                                      ("Cut all kisses", "All kisses")], v, size=9).grid(
                    row=row, column=1, sticky="w", pady=X(3))
                out.append(v)
            return out

        def own_words(body):
            tk.Label(body, text="Your own words and phrases to mute  (one per line, for every "
                     "age)", bg=CARD, fg=INK, font=(HEAD, 10)).pack(anchor="w", pady=(X(12), X(4)))
            self.mywords_box = tk.Text(body, height=4, font=(FONT, 10), wrap="none",
                                       relief="flat", borderwidth=0, highlightthickness=1,
                                       highlightbackground=LINE, highlightcolor=ACCENT,
                                       bg=SOFT, padx=X(8), pady=X(6))
            self.mywords_box.insert("1.0", "\n".join(saved.get("mywords") or []))
            self.mywords_box.pack(anchor="w", fill="x")
            tk.Label(body, text="Muted wherever they're said, the whole phrase: for example "
                     "“grow some stones”. Whole words only, so “stones” on "
                     "its own wouldn't touch “milestones”. Put other forms on their own "
                     "lines (dork, dorks).", bg=CARD, fg=MUTED, font=(FONT, 9),
                     wraplength=wrap_width(520), justify="left").pack(anchor="w", pady=(X(4), 0))

        def fold_group(title, icon, items, cols=1, menus=False, extra=None):
            """A section: a tile with its icon, its name, a switch for all of it and how many
            are on; its boxes are shown under the tiles when it's opened."""
            n = len(self._section_heads)
            tile = look.Card(tiles, radius=14, pad=(13, 11))
            tile.grid(row=2 * (n // 3), column=n % 3, sticky="nsew", padx=(0, X(10)),
                      pady=(0, X(10)))
            top = tk.Frame(tile.body, bg=CARD)
            top.pack(fill="x")
            badge = look.Badge(top, icon, size=30)
            badge.pack(side="left", anchor="n")
            switch = look.Switch(top)
            switch.pack(side="right", anchor="n", pady=(X(4), 0))
            name = tk.Label(tile.body, text=title, bg=CARD, fg=INK, font=(HEAD, 10), anchor="w",
                            justify="left", wraplength=wrap_width(150), cursor="hand2")
            name.pack(fill="x", pady=(X(8), 0))
            low = tk.Frame(tile.body, bg=CARD)
            low.pack(fill="x", side="bottom", pady=(X(4), 0))
            count = tk.Label(low, text="", bg=CARD, fg=MUTED, font=(FONT, 9))
            count.pack(side="left")
            more = look.link(low, "Choose ›", lambda: flip(), size=9)
            more.pack(side="right")
            body = tk.Frame(dbody, bg=CARD)
            grid = tk.Frame(body, bg=CARD)
            grid.pack(fill="x")
            got = (kiss_menus(grid) if menus else []) + checks(
                tk.Frame(grid, bg=CARD) if menus else grid, items, cols)
            if menus:                                       # the boxes under the two menus
                grid.winfo_children()[-1].grid(row=2, column=0, columnspan=2, sticky="w",
                                               pady=(X(8), 0))
            if extra:
                extra(body)

            def on(v):
                val = v.get()
                return val != "Keep" if isinstance(val, str) else bool(val)

            def refresh(*_):
                if not switch.winfo_exists():
                    return
                k = sum(on(v) for v in got)
                switch.set("on" if k == len(got) else "off" if k == 0 else "some")
                count.config(text=f"{k} of {len(got)} on" if k else "Off")
                badge.set(fill=TINT if k else SIDE, fg=ACCENT if k else FAINT)

            def tick_all(_=None):
                want = not all(on(v) for v in got)
                for v in got:
                    v.set(("Cut all kisses" if want else "Keep") if isinstance(v.get(), str)
                          else want)

            def show(opened):
                if opened:
                    for t, other in shows.items():
                        if t != title:
                            other(False)
                    body.pack(fill="x")
                    dname.config(text=title)
                    detail.grid(row=2 * (n // 3) + 1, column=0, columnspan=3, sticky="ew",
                                padx=(0, X(10)), pady=(0, X(10)))      # under its own row
                    self._open_sections = {title}
                else:
                    body.pack_forget()
                    if title in self._open_sections:
                        self._open_sections.discard(title)
                        detail.grid_forget()
                tile.recolour(edge=ACCENT if opened else LINE, edge_w=2.0 if opened else 1.0)
                more.label.config(text="Hide ‹" if opened else "Choose ›")

            def flip(_=None):
                opening = title not in self._open_sections
                show(opening)
                if opening:                     # its tile and the boxes under it in view
                    self.after(50, lambda: self._scroll_to(tile))
            switch._command = tick_all
            for w in (badge, name):
                look.on_click(w, flip)
            for v in got:
                v.trace_add("write", refresh)
            refresh()
            shows[title] = show
            self._section_heads[title] = (switch, count, tick_all, show)

        fold_group("Bad language", "mute", [
            ("swearing", "Swearing  (f-word, s-word, b-word…)", True),
            ("mild", "Mild words  (damn, hell, crap)", True),
            ("deity", "God's name used as a swear", True),
            ("minced", "Soft substitutes  (gosh, heck, freaking)", False),
            ("rude", "Rude words kids copy  (stupid, dumb, idiot, shut up…)", False),
            ("samesexwords", "Words about same-sex relationships  (gay, lesbian…)", True)],
            extra=own_words)
        fold_group("Sex and nudity", "eye", [
            ("sexref", "Sexual references and innuendo", True),
            ("sex", "Sex scenes", True),
            ("nudity", "Nudity  (private parts shown)", True),
            ("implied", "Implied nudity  (under sheets, in towels, bare backs)", False),
            ("immodest", "Immodest clothing  (swimsuits, underwear, sexy dancing)", False),
            ("gestures", "Rude and sexual gestures  (the middle finger, crude motions)",
             True)])
        fold_group("Romance and relationships", "heart", [
            ("casual", "Sleeping around  (casual sex, affairs)", True),
            ("oppsex", "Unmarried couples living or sleeping together", False),
            ("samesex", "Same-sex relationships  (flirting, talk and intimate scenes)", False)],
            menus=True)
        fold_group("Violence", "warning", [
            ("violence", "Violence  (fights, shootings, attacks)", True),
            ("graphic", "Graphic violence  (blood, bloody wounds)", True),
            ("gore", "Gore  (insides showing: organs, dismemberment)", True),
            ("disturbing", "Disturbing  (torture, executions, cruelty, bloody accidents)", True)])
        fold_group("Medical", "health", [
            ("medical", "Medical scenes  (surgery, autopsies, wounds being treated, needles)",
             True),
            ("forensic", "Coroner and doctor talk  (graphic findings: wounds, autopsies, "
                         "sexual assault)", False)])
        fold_group("Attitude", "smile", [
            ("bullying", "Bullying and mocking", False),
            ("disrespect", "Disrespect  (bratty, talking back, disobeying parents)", False),
            ("crude", "Crude humor  (bathroom and gross-out jokes)", False)])
        fold_group("Smoking, drinking and drugs", "cup", [
            ("smoking", "Smoking", False), ("drinking", "Drinking alcohol", False),
            ("drugs", "Drug use", True)], cols=3)
        fold_group("Faith, holidays and magic", "star", [
            ("religion", "Religious conversations  (prayer, church, faith, the Bible…)",
             False),
            ("holidays", "Holidays  (Christmas, Halloween, Easter, Valentine's Day, "
                         "St. Patrick's Day)", False),
            ("birthday", "Candles on a birthday cake  (parties and cake are fine)", False),
            ("darkmagic", "Dark magic  (witchcraft, wizards, curses, the occult, fortune "
                          "telling)", False),
            ("magic", "Magic  (spells, wands, potions, fairies)", False),
            ("vampires", "Vampires and werewolves", False)])
        fold_group("Music", "music", [
            ("loudmusic", "Turn down hard rock, metal and rap music  (where no one's talking)",
             False)])
        look.link(dhead, "Done", lambda: [s(False) for s in shows.values()], size=9).pack(
            side="right")
        for t in list(self._open_sections):
            if t in shows:
                shows[t](True)

        # ----- step 3: the AI helper
        p3 = pane(3)
        top = look.Card(p3)
        top.pack(fill="x", padx=(0, X(4)))
        v = tk.BooleanVar(value=saved.get("ai", True))
        self.opts["ai"] = v
        look.Switch(top.body, v).pack(side="left", anchor="n", pady=(X(2), 0))
        words = tk.Frame(top.body, bg=CARD)
        words.pack(side="left", fill="x", expand=True, padx=(X(14), 0))
        tk.Label(words, text="Use the AI helper to double-check scenes and read the dialogue",
                 bg=CARD, fg=INK, font=(HEAD, 11), anchor="w", justify="left",
                 wraplength=wrap_width(470)).pack(anchor="w")
        tk.Label(words, text="Runs on your own PC, nothing is uploaded. The first time, it "
                 "downloads Ollama and two AI models (about 11 GB, one time only). Without it, "
                 "kissing and dialogue checks are rougher.", bg=CARD, fg=MUTED, font=(FONT, 9),
                 wraplength=wrap_width(470), justify="left").pack(anchor="w", pady=(X(3), 0))
        tk.Label(p3, text="Who reads the dialogue and checks the scenes", bg=BG, fg=INK,
                 font=(HEAD, 11)).pack(anchor="w", pady=(X(18), X(8)))
        v = tk.StringVar(value=saved.get("reader", "local"))
        self.opts["reader"] = v
        choices = tk.Frame(p3, bg=BG)
        choices.pack(fill="x")
        for c in range(2):
            choices.columnconfigure(c, weight=1, uniform="ai")
        for n, (key, title, sub, icon) in enumerate([
                ("local", "This PC", "Free, nothing leaves your PC", "pc"),
                ("claude", "Claude", "More accurate; uses your Claude premium plan", "spark"),
                ("chatgpt", "ChatGPT", "More accurate; uses your ChatGPT premium plan", "chat"),
                ("gemini", "Gemini", "More accurate; uses your Google account", "cloud")]):
            card = look.OptionCard(choices, key, v, title, sub, icon=icon)
            card.sub.config(wraplength=wrap_width(190))
            card.grid(row=n // 2, column=n % 2, sticky="nsew", padx=(0, X(10)), pady=(0, X(10)))
        status = tk.Frame(p3, bg=BG)
        status.pack(fill="x", pady=(X(4), 0))
        crow = tk.Frame(status, bg=BG)
        crow.pack(fill="x")
        self.claude_lbl = tk.Label(crow, text="", bg=BG, fg=MUTED, font=(FONT, 9),
                                   wraplength=wrap_width(380), justify="left")
        self.claude_lbl.pack(side="left")
        self.claude_btn = look.Pill(crow, "Set up", self.setup_claude, size=10, pad=(16, 8))
        arow = tk.Frame(status, bg=BG)          # someone else's own account
        arow.pack(fill="x")
        self.switch_btn = look.Pill(arow, "Use a different account", self.use_other_account,
                                    kind="secondary", size=9, pad=(14, 6), bold=False)
        self.signout_btn = look.Pill(arow, "Sign out", self.sign_out_account, kind="secondary",
                                     size=9, pad=(14, 6), bold=False)
        lv = tk.BooleanVar(value=saved.get("look", True))
        self.opts["look"] = lv
        self.look_chk = ttk.Checkbutton(status, text="", variable=lv, style="Bg.TCheckbutton")
        self.look_chk.pack(anchor="w", pady=(X(6), 0))
        self.cloud_note = tk.Label(status, text="", bg=BG, fg=MUTED, font=(FONT, 9),
                                   wraplength=wrap_width(560), justify="left")
        self.cloud_note.pack(anchor="w", pady=(X(6), 0))
        lv.trace_add("write", lambda *_: self._reader_changed())
        self.ai_state = getattr(self, "ai_state", {})
        v.trace_add("write", lambda *_: self._reader_changed())
        v.trace_add("write", lambda *_: self._show_steps())
        self.opts["ai"].trace_add("write", lambda *_: self._show_steps())
        self._reader_changed()

        # ----- step 4: where to save
        p4 = pane(4)
        card = look.Card(p4)
        card.pack(fill="x", padx=(0, X(4)))
        row = tk.Frame(card.body, bg=CARD)
        row.pack(fill="x")
        look.Badge(row, "folder", size=40, icon_size=15).pack(side="left", anchor="n")
        words = tk.Frame(row, bg=CARD)
        words.pack(side="left", fill="x", expand=True, padx=(X(14), 0))
        tk.Label(words, text="Clean copies are saved in", bg=CARD, fg=MUTED,
                 font=(FONT, 9)).pack(anchor="w")
        self.out_lbl = tk.Label(words, text=NEXT_TO_VIDEO, bg=CARD, fg=MUTED,
                                font=(HEAD, 10), wraplength=wrap_width(440), justify="left",
                                anchor="w")
        self.out_lbl.pack(anchor="w", pady=(X(2), 0))
        brow = tk.Frame(words, bg=CARD)
        brow.pack(anchor="w", pady=(X(12), 0))
        look.Pill(brow, "Change…", self.pick_out, kind="secondary", size=10,
                  pad=(16, 7)).pack(side="left")
        self.next_to_btn = look.Pill(brow, "Next to the video", self.use_video_folder,
                                     kind="secondary", size=10, pad=(16, 7))
        tk.Label(p4, text="Your original files are never changed.", bg=BG, fg=FAINT,
                 font=(FONT, 9)).pack(anchor="w", pady=(X(14), 0))
        self._refresh_labels()
        self._go_step(getattr(self, "_setup_step", 1))

    def share_learned(self):
        try:
            path = learn.export()
        except Exception as ex:
            messagebox.showerror("CleanView", f"Couldn't save the file. {plain_error(ex)}")
            return
        self._send_in(path, "learned")

    def _send_in(self, path, kind):
        """After saving a "what CleanView learned" file: send it to the CleanView inbox (in
        the background) if she says so. Not set up yet, not now, or it didn't go: say where
        it's saved, to attach in a chat with Claude instead."""
        if not learn.send_url():
            self._send_by_hand(path)
            return
        chime()
        if not messagebox.askyesno(
                "CleanView", "Send it in now?\n\nIt has the lines and words you and the AI "
                "muted or kept, and its notes. No video or sound. Once it's added, every copy "
                "of CleanView gets what it learned with an update.", parent=self):
            self._send_by_hand(path)
            return

        def go():
            try:
                learn.send(path, kind)
                self.q.put(("call", lambda: messagebox.showinfo(
                    "CleanView", "Sent. Thank you! It'll be in every copy of CleanView with an "
                                 "update soon.", parent=self)))
            except Exception as ex:
                save_details(f"Sending {path}\n\n{traceback.format_exc()}")
                why = plain_error(ex)
                self.q.put(("call", lambda: self._send_by_hand(
                    path, f"Couldn't send it ({why[:1].lower() + why[1:].rstrip('.')}). "
                          f"Check the internet connection.\n\n")))
        threading.Thread(target=go, daemon=True).start()

    def _send_by_hand(self, path, first=""):
        if os.name == "nt":
            subprocess.Popen(["explorer", "/select,", str(path)])
        messagebox.showinfo(
            "CleanView",
            f"{first}Saved as \u201c{path.name}\u201d in {path.parent}.\n\n"
            "Attach that file in your chat with Claude and ask for it to be added to CleanView. "
            "Once it's added, every copy of CleanView (yours, and anyone you've shared it with) "
            "gets what it learned with the next update.\n\n"
            "It has the lines and words you and the AI muted or kept, and its notes. No video "
            "or sound.", parent=self)

    # ---------- who you're filtering for ----------
    def _filter_values(self):
        out = {}
        for k in FILTER_KEYS:
            if k in self.opts:
                val = self.opts[k].get()
                out[k] = self.level_values.get(val, val) if isinstance(val, str) else bool(val)
        return out

    def _set_filters(self, vals):
        for k in FILTER_KEYS:
            if k in self.opts and k in vals:
                v = vals[k]
                self.opts[k].set(self.level_names[v] if k in ("kiss_os", "kiss_ss") else bool(v))

    def _profile_changed(self):
        new = self.profile_var.get()
        if new == self.profile:
            return
        self.profiles[self.profile] = self._filter_values()     # keep what you set
        self.profile = new
        self._set_filters(self.profiles[new])
        self._show_steps()

    def _profile_reset(self):
        self.profiles[self.profile] = dict(PRESETS[self.profile])
        self._set_filters(self.profiles[self.profile])

    # ---------- Claude / ChatGPT ----------
    def _cloud(self):
        """The online AI picked under "Who reads the dialogue", or None."""
        r = self.opts["reader"].get() if "reader" in getattr(self, "opts", {}) else None
        return r if r in cc.NAMES else None

    def _reader_changed(self):
        p = self._cloud()
        lbl = getattr(self, "claude_lbl", None)
        if lbl is None or not lbl.winfo_exists():
            return
        if not p:
            lbl.config(text="")
            self.claude_btn.pack_forget()
            self._account_buttons(None, "")
            self.look_chk.pack_forget()
            self.cloud_note.config(text="Want it more accurate? Pick Claude, ChatGPT or Gemini if you "
                                   "have one of them. Everything works without them too.")
            return
        n = cc.name(p)
        self.look_chk.config(text=f"Let {n} look at the picture too  (much better at finding "
                                  f"the right scenes)")
        self.look_chk.pack(anchor="w", padx=(22, 0), pady=(4, 0), before=self.cloud_note)
        if self.opts["look"].get():
            self.cloud_note.config(
                text=f"{n} gets the words that are said, plus still pictures from the video (one "
                     f"every 2 seconds, small), never the sound. It looks through them all, checks "
                     f"each scene the other checks found, and reviews everything. This uses more "
                     f"of your {n} {'allowance' if p == 'gemini' else 'plan'}: roughly a long "
                     f"chat's worth per episode.")
        else:
            self.cloud_note.config(
                text=f"Only the words that are said are sent to {n}, never the video or sound. "
                     f"{n} also reviews everything that was found, and you can chat with it on "
                     f"the review page.")
        if p in self.ai_state:
            self._show_claude_status((p, self.ai_state[p]))
        else:
            lbl.config(text=f"Checking {n}\u2026", fg=MUTED)
            self.claude_btn.pack_forget()
            self._account_buttons(p, "checking")
            self.check_claude(p)

    def check_claude(self, provider=None):
        p = provider or self._cloud()
        if not p:
            return

        def go():
            self.q.put(("claude_status", _ai_status(p)))
        threading.Thread(target=go, daemon=True).start()

    def _check_every_ai(self):
        """Find out in the background which of Claude, ChatGPT and Gemini are set up, so the
        review page can offer the chat even when the AI on this PC read the dialogue."""
        self.ai_state = getattr(self, "ai_state", {})
        asked = self.__dict__.setdefault("_ai_asked", set())
        for p in cc.NAMES:
            if p not in self.ai_state and p not in asked:
                asked.add(p)
                self.check_claude(p)

    def _ai_checking(self):
        return bool(getattr(self, "_ai_asked", set()) - set(getattr(self, "ai_state", {})))

    def _offer_chat(self):
        """One turned out to be set up: build the review page again with the chat."""
        if self.page_name != "review" or getattr(self, "review_ai", None):
            return
        try:
            tab = self._nb.index("current")
        except Exception:
            tab = 0
        self.show_review(tab=tab)

    def _show_claude_status(self, msg):
        p, st, *rest = msg if isinstance(msg, tuple) else ("claude", msg)
        self.ai_state = getattr(self, "ai_state", {})
        self.ai_who = getattr(self, "ai_who", {})
        self.ai_state[p] = st
        if rest:
            self.ai_who[p] = rest[0]
        if p == "claude":
            self.claude_state = st
        if getattr(self, "page_name", "") == "review" and not getattr(self, "review_ai", None) \
                and (st == "ready" or not self._ai_checking()):
            self.after_idle(self._offer_chat)
        lbl = getattr(self, "claude_lbl", None)
        if lbl is None or not lbl.winfo_exists() or self._cloud() != p:
            return
        n = cc.name(p)
        who = self.ai_who.get(p) if st == "ready" else ""
        text = {"ready": f"\u2713 {n} is signed in as {who}." if who else
                         f"\u2713 {n} is set up and signed in.",
                "signed_out": f"{n} is installed, but nobody is signed in yet. Sign in with "
                              f"your own {n} account.",
                "missing": f"{n} isn't set up on this PC yet. Set it up (one time, a few "
                           f"minutes), then sign in with your own {n} account."}[st]
        lbl.config(text=text, fg=ACCENT_DK if st == "ready" else MUTED)
        if st == "ready":
            self.claude_btn.pack_forget()
        else:
            self.claude_btn.config(text=f"Sign in to {n}" if st == "signed_out" else
                                   "Set up and sign in", state="normal")
            self.claude_btn.pack(side="left", padx=(10, 0))
        self._account_buttons(p, st)

    def _account_buttons(self, p, st):
        """"Use a different account" (and "Sign out" of one signed in inside CleanView),
        so each person can use their own Claude, ChatGPT or Gemini account on the same PC."""
        self.switch_btn.pack_forget()
        self.signout_btn.pack_forget()
        if not p or not cc.can_switch(p) or st == "missing":
            return
        own = cc.own_account(p)
        if st == "ready" or own:
            self.switch_btn.config(state="normal")
            self.switch_btn.pack(side="left", pady=(4, 0))
        if own:
            self.signout_btn.config(state="normal")
            self.signout_btn.pack(side="left", padx=(8, 0), pady=(4, 0))

    def use_other_account(self):
        p = self._cloud()
        if not p:
            return
        n = cc.name(p)
        self.switch_btn.config(state="disabled")
        self.signout_btn.config(state="disabled")

        def go():
            import time
            try:
                folder = cc.start_other_account(p)
                self.q.put(("claude_wait", n))
                for _ in range(180):              # wait up to 6 minutes for the sign-in
                    time.sleep(2)
                    if cc.other_account_ready(folder, p):
                        cc.keep_account(folder, p)
                        break
            except Exception as ex:
                self.q.put(("warn", f"Couldn't sign in to another {n} account. {plain_error(ex)}"))
            self.q.put(("claude_status", _ai_status(p)))
        threading.Thread(target=go, daemon=True).start()

    def sign_out_account(self):
        p = self._cloud()
        if not p:
            return
        n = cc.name(p)
        who = getattr(self, "ai_who", {}).get(p) or "this account"
        chime()
        if not messagebox.askyesno(
                "Sign out", f"Sign {who} out of {n} in CleanView?\n\nCleanView will go back to the "
                            f"{n} sign-in this PC had before, if there is one.", parent=self):
            return
        cc.sign_out(p)
        self._account_buttons(p, "checking")
        self.claude_lbl.config(text=f"Checking {n}\u2026", fg=MUTED)
        self.check_claude(p)

    def setup_claude(self):
        p = self._cloud()
        if not p:
            return
        n = cc.name(p)
        self.claude_btn.config(state="disabled")
        self.claude_lbl.config(text=f"Setting up {n}\u2026 (this can take a few minutes)")

        def go():
            import time
            try:
                if not cc.is_installed(p):
                    cc.install(p)
                if not cc.is_signed_in(p):
                    cc.sign_in(p)
                    self.q.put(("claude_wait", n))
                    for _ in range(180):          # wait up to 6 minutes for the sign-in
                        time.sleep(2)
                        if cc.is_signed_in(p):
                            break
                self.q.put(("claude_status", _ai_status(p)))
            except Exception as ex:
                import traceback
                plain, details = f"{n} couldn't be set up. {plain_error(ex)}", (
                    f"Setting up {n}\n\n{ex}\n\n{traceback.format_exc()}")
                self.q.put(("call", lambda: self._problem(plain, details)))
                self.q.put(("claude_status", _ai_status(p)))
        threading.Thread(target=go, daemon=True).start()

    def _load_settings(self):
        try:
            return json.loads((APP_DATA / "cleanview_settings.json").read_text())
        except Exception:
            return {}

    def _save_settings(self):
        """Remember the start page: her ticks for each age, and the other choices. Done
        on Start and when the window closes, so changes aren't lost by closing first."""
        if not getattr(self, "opts", None) or not hasattr(self, "profiles"):
            return
        try:
            self.profiles[self.profile] = self._filter_values()
            keep = {k: v for k, v in self._current_opts().items() if k not in FILTER_KEYS}
            keep.update(open_sections=sorted(getattr(self, "_open_sections", ()) or ()))
            keep.update(save_to=getattr(self, "save_to", None))
            keep.update(theme=getattr(self, "theme", "light"))
            keep.update(profile=self.profile, profiles=self.profiles, text_size=self.text_size,
                        at_once=getattr(self, "at_once", None) or
                        self._load_settings().get("at_once"))
            APP_DATA.mkdir(parents=True, exist_ok=True)
            path = APP_DATA / "cleanview_settings.json"
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(keep))
            os.replace(tmp, path)
        except Exception:
            pass

    def _set_text_size(self, name):
        """Tk sizes text as each part of the window is built, so build the start page
        again at the new size, keeping it as it was (the videos chosen and every tick).
        It used to restart CleanView, which closed the window for a while on a slow PC
        and looked like it had shut down (Jason)."""
        if name == self.text_size or name not in TEXT_SIZES:
            return
        self.text_size = name
        self._save_settings()               # the ticks, which the page is built from
        global _text_scale
        _text_scale = TEXT_SIZES[name]
        self.tk.call("tk", "scaling", self._base_scaling * _text_scale)
        self._style()                       # fonts and tick boxes at the new size
        self._fit_window(grow_only=True)
        self.show_setup()

    def _current_opts(self):
        o = {}
        for k, v in self.opts.items():
            val = v.get()
            o[k] = self.level_values.get(val, val) if isinstance(val, str) else bool(val)
        o["profile"] = getattr(self, "profile", "adults")
        o["mywords"] = self._my_words_typed()
        o["autosubs"] = True        # always (it was a switch on step 1; an old "off" is gone)
        return o

    def _my_words_typed(self):
        """Her own words and phrases from the start page: one per line, no blanks or
        repeats (at most 300 of them, each up to 80 characters)."""
        box = getattr(self, "mywords_box", None)
        if box is None or not box.winfo_exists():
            return self._load_settings().get("mywords") or []
        out = []
        for line in box.get("1.0", "end").splitlines():
            line = " ".join(line.split())[:80]
            if line and line.lower() not in (x.lower() for x in out):
                out.append(line)
        return out[:300]

    def _lengths(self, videos, then):
        """Add up how long the videos are without freezing the window (reading each
        file takes a moment, which adds up for a whole season); then(seconds) after."""
        def go():
            dur = sum(engine.cl.probe_duration(v) for v in videos)
            self.q.put(("call", lambda: then(dur)))
        threading.Thread(target=go, daemon=True).start()

    def _refresh_labels(self):
        if self.videos:
            videos = list(self.videos)
            first = short(Path(videos[0]).name, 70)
            extra = f"  … and {len(videos) - 1} more" if len(videos) > 1 else ""
            folder = os.path.normpath(str(Path(videos[0]).parent))
            n = len(videos)

            def show(length=""):
                if self.videos == videos and self.vid_lbl.winfo_exists():
                    self.vid_lbl.config(text=f"{n} video{'s' if n != 1 else ''}{length}   in  "
                                        f"{folder}\n{first}{extra}", fg=INK)
            show()
            self._lengths(videos, lambda dur: show(f" · {fmt_len(dur)}"))
            self.start_btn.config(state="normal")
            if not self.outdir:
                self.out_lbl.config(text=os.path.normpath(str(Path(self.videos[0]).parent / "Clean")),
                                    fg=INK)
        if self.outdir:
            self.out_lbl.config(text=os.path.normpath(self.outdir), fg=INK)
        elif not self.videos:
            self.out_lbl.config(text=NEXT_TO_VIDEO, fg=MUTED)
        btn = getattr(self, "next_to_btn", None)
        if btn is not None and btn.winfo_exists():
            if getattr(self, "save_to", None) and self.outdir == self.save_to:
                if not btn.winfo_manager():
                    btn.pack(side="left", padx=(self._px(8), 0))
            else:
                btn.pack_forget()
        self._show_steps()

    def _remembered_folder(self):
        """The folder she chose to save in, when it's there now (a USB drive may be
        unplugged: then next to the video this time, and it's kept for next time)."""
        d = getattr(self, "save_to", None)
        return d if d and os.path.isdir(d) else None

    def _remember_save_to(self, d):
        """Keep the save folder in the settings now, from the start page or the review."""
        self.save_to = d or None
        try:
            s = self._load_settings()
            s["save_to"] = self.save_to
            APP_DATA.mkdir(parents=True, exist_ok=True)
            path = APP_DATA / "cleanview_settings.json"
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(s))
            os.replace(tmp, path)
        except Exception:
            pass

    def use_video_folder(self):
        """Back to a "Clean" folder next to each video, and remember that."""
        self.outdir = None
        self._remember_save_to(None)
        if getattr(self, "page_name", "") == "setup":
            self._refresh_labels()

    def pick_files(self):
        exts = " ".join("*" + e for e in engine.VIDEO_EXTS)
        files = filedialog.askopenfilenames(title="Choose the movie or episodes",
                                            filetypes=[("Videos", exts), ("All files", "*.*")])
        if files:
            self.videos = sorted(files, key=natural_key)
            self.outdir = self._remembered_folder()
            self._refresh_labels()

    def pick_out(self):
        d = filedialog.askdirectory(title="Where should the clean copies go?",
                                    initialdir=self.outdir or None)
        if d:
            self.outdir = d
            self._remember_save_to(d)
            self._refresh_labels()

    # ---------- page 2: working ----------
    def start(self):
        if not self.videos:          # the button is always on, so it never looks broken
            messagebox.showinfo("CleanView", "First choose the movie or episodes to clean, "
                                "with Choose files in step 1.", parent=self)
            lbl = getattr(self, "vid_lbl", None)
            if lbl is not None and lbl.winfo_exists():
                self._scroll_to(lbl)
            return
        o = self._current_opts()
        p = o.get("reader")
        state = getattr(self, "ai_state", {}).get(p, "ready") if p in cc.NAMES else "ready"
        if state != "ready":
            n = cc.name(p)
            what = "set up on this PC" if state == "missing" else "signed in"
            chime()
            ans = messagebox.askyesnocancel(
                "CleanView", f"{n} isn't {what} yet.\n\nPress Yes to "
                f"{'set it up and ' if state == 'missing' else ''}sign in with your own {n} "
                f"account now (then press Start cleaning again).\n\nPress No to let the AI on this "
                f"PC read the dialogue this time instead.", parent=self)
            if ans is None:
                return
            if ans:
                self._scroll_to(self.claude_lbl)
                self.setup_claude()
                return
            o["reader"] = "local"
        word_groups = ("swearing", "mild", "deity", "minced", "samesexwords", "rude")
        self.groups = [g for g in word_groups if o.get(g)]
        self.scan_opts = {k: v for k, v in o.items() if k not in word_groups}
        engine.cl.use_language(o.get("language"))      # the word lists the review uses too
        # (only what's to be removed counts: not "who reads the dialogue" and the like)
        if not any(o.get(k) not in (False, "off", None) for k in FILTER_KEYS) and \
                not o.get("mywords"):
            messagebox.showinfo("CleanView", "Tick at least one thing to remove, or type your "
                                "own words to mute.")
            return
        gone = [v for v in self.videos if not os.path.isfile(v)]
        if gone:
            more = f" and {len(gone) - 1} more" if len(gone) > 1 else ""
            messagebox.showinfo("CleanView", f"Can't find {short(Path(gone[0]).name, 60)}{more}. "
                                "It may have been moved, or its drive unplugged. Choose the "
                                "files again.", parent=self)
            return
        # no internet: subtitles can't be looked for online, so say so and ask (the owner,
        # 2026-11-13: "could it pop up a small window saying no internet, cant look up
        # subtitles. want to clean without them?", "with a yes no button")
        self.scan_opts.pop("offline", None)
        if not engine.online():
            chime()
            if not messagebox.askyesno("CleanView", NO_INTERNET_ASK, parent=self):
                return
            self.scan_opts["offline"] = True
        self._save_settings()
        if not self.outdir:
            self.outdir = str(Path(self.videos[0]).parent / "Clean")
        self.jobs = []
        # A new batch starts a new chat, so what was said about the last video isn't sent
        # in with this one's report (Emma's report had Pride and Prejudice's chat).
        self.chat_sessions, self.chat_history = {}, []
        for v in self.videos:
            key = hashlib.sha1(f"{v}:{os.path.getsize(v)}".encode()).hexdigest()[:16]
            self.jobs.append({"video": v, "work": APP_DATA / "views" / key, "analysis": None,
                              "error": None})
        self.cancel_flag = self.stop_after = False
        self.at_once = self._at_once()
        self._check_every_ai()
        self.show_working("Watching and listening…", can_stop=True)
        self._start_work(self._analyze_thread)

    JOB_LOOK = {"wait": ("○", "MUTED"), "now": ("▶", "ACCENT"), "done": ("✓", "ACCENT_DK"),
                "failed": ("!", "WARN"), "skipped": ("–", "MUTED")}      # colours by name

    def show_working(self, title, videos=None, can_stop=False):
        """The progress page. videos: the files being worked on, listed with how each
        is going when there are several. can_stop: offer "Stop after this video" (finish
        the one being worked on, skip the rest, and go on to the review)."""
        self.page_name = "working"
        videos = videos or [j["video"] for j in self.jobs]
        n = len(videos)
        what = f"These {n} videos" if n > 1 else "This video"
        p = self._new_page(title, "You can leave this running and come back. If you have to "
                           "stop, starting the same videos again skips the steps already done.")
        length = tk.Label(p, text=f"{what}…", bg=BG, fg=MUTED, font=(FONT, 10))
        length.pack(anchor="w")
        self._lengths(videos, lambda dur: length.winfo_exists() and length.config(
            text=f"{what} {'are' if n > 1 else 'is'} {fmt_len(dur)} long."))
        doing = look.Card(p, radius=16, pad=(24, 20))
        doing.pack(fill="x", pady=(self._px(16), 0))
        box = doing.body
        self.which = tk.Label(box, text="", bg=CARD, fg=INK, font=(FONT, 15, "bold"),
                              wraplength=wrap_width(720), justify="left")   # the title
        self.which.pack(anchor="w", pady=(0, 10))
        self.pb = ttk.Progressbar(box, style="Green.Horizontal.TProgressbar", maximum=1000,
                                  length=640)
        self.pb.pack(fill="x")
        self.status = tk.Label(box, text="Starting…", bg=CARD, fg=INK, font=(FONT, 12))
        self.status.pack(anchor="w", pady=(14, 0))
        self.overall = tk.Label(box, text="", bg=CARD, fg=ACCENT, font=(HEAD, 11))
        self.overall.pack(anchor="w", pady=(4, 0))
        if n == 1:                      # the logo in the empty space (Jason, 2026-11-07)
            png = logo_png(128)
            try:
                img = tk.PhotoImage(data=base64.b64encode(png).decode()) if png else None
            except tk.TclError:
                img = None
            if img is not None:
                self._imgs.append(img)
                mid = tk.Frame(p, bg=BG)
                mid.pack(fill="both", expand=True)
                self.logo = tk.Label(mid, image=img, bg=BG)
                self.logo.place(relx=0.5, rely=0.45, anchor="center")
        self._work_n, self._work_t0 = n, None
        self.stop_after = False
        self.job_rows, self.job_frames, self.job_notes = [], [], []
        if n > 1 and can_stop:           # how many are worked on at the same time
            top = tk.Frame(p, bg=BG)
            top.pack(fill="x", pady=(20, 0))
            tk.Label(top, text="Videos at once:", bg=BG, fg=INK, font=(FONT, 10)).pack(
                side="left")
            at_var = tk.StringVar(value=str(getattr(self, "at_once", 1)))
            box_n = ttk.Combobox(top, values=[str(c) for c in VQ.AT_ONCE_CHOICES], width=3,
                                 state="readonly", textvariable=at_var, font=(FONT, 10))
            box_n.pack(side="left", padx=(6, 0))
            box_n.bind("<<ComboboxSelected>>", lambda e: self._set_at_once(int(at_var.get())))
            tk.Label(top, text="More at once finishes a season sooner, but each video takes "
                     "longer and the PC is busier. With Claude, ChatGPT or Gemini it also uses "
                     "up your plan's limits faster.", bg=BG, fg=MUTED, font=(FONT, 9),
                     wraplength=wrap_width(520), justify="left").pack(side="left", padx=(12, 0))
        if n > 1:                       # each video, ticked off as it's done
            tk.Label(p, text="Videos", bg=BG, fg=INK, font=(FONT, 11, "bold")).pack(
                anchor="w", pady=(22, 4))
            lst = self._scroll_area(p)
            for v in videos:
                row = tk.Frame(lst, bg=BG)
                row.pack(fill="x", pady=1)
                icon = tk.Label(row, text=self.JOB_LOOK["wait"][0], bg=BG, fg=MUTED,
                                font=(FONT, 10, "bold"), width=2)
                icon.pack(side="left")
                name = tk.Label(row, text=short(Path(v).name, 90), bg=BG, fg=MUTED, font=(FONT, 10),
                                anchor="w")
                name.pack(side="left")
                note = tk.Label(row, text="", bg=BG, fg=MUTED, font=(FONT, 9), anchor="w")
                note.pack(side="left", padx=(12, 0))
                self.job_rows.append((icon, name))
                self.job_frames.append(row)
                self.job_notes.append(note)
        self.cancel_btn = ttk.Button(self.footer, text="Cancel", style="Plain.TButton",
                                     command=self.cancel)
        self.cancel_btn.pack(side="right")
        engine.PAUSE.resume()            # new work never starts paused
        self.pause_btn = ttk.Button(self.footer, text="Pause", style="Plain.TButton",
                                    command=self.toggle_pause)
        self.pause_btn.pack(side="right", padx=(0, 8))
        self.stop_btn = None
        if n > 1 and can_stop:
            self.stop_btn = ttk.Button(self.footer, text=self._stop_label(),
                                       style="Plain.TButton", command=self.toggle_stop_after)
            self.stop_btn.pack(side="right", padx=(0, 8))

    PAUSED_SAID = "Paused \u2014 press Resume to carry on."

    def toggle_pause(self):
        """Pause: CleanView's helpers freeze where they are, so the PC is free for something
        else; Resume carries on from the same spot (the owner, 2026-11-12). The time left
        leaves the paused time out."""
        btn = getattr(self, "pause_btn", None)
        if not engine.PAUSE.on:
            engine.PAUSE.pause()
            self._paused_at = time.time()
            if btn is not None and btn.winfo_exists():
                btn.config(text="Resume")
            if getattr(self, "status", None) is not None and self.status.winfo_exists():
                self.status.config(text=self.PAUSED_SAID)
        else:
            engine.PAUSE.resume()
            if self._work_t0 is not None and getattr(self, "_paused_at", None):
                self._work_t0 += time.time() - self._paused_at
            self._paused_at = None
            if btn is not None and btn.winfo_exists():
                btn.config(text="Pause")
            if getattr(self, "status", None) is not None and self.status.winfo_exists():
                self.status.config(text=getattr(self, "_doing", {}).get("status") or "")

    def toggle_stop_after(self):
        """Finish the video being worked on, then skip the rest and go on to the review
        (pressed again: keep going with all of them)."""
        self.stop_after = not getattr(self, "stop_after", False)
        if self.stop_btn is not None and self.stop_btn.winfo_exists():
            self.stop_btn.config(text="Keep going with all of them" if self.stop_after
                                 else self._stop_label())
        if self.stop_after and getattr(self, "overall", None) is not None and \
                self.overall.winfo_exists():
            now = "this video" if getattr(self, "at_once", 1) == 1 else \
                "the ones being done now"
            self.overall.config(text=f"Stopping after {now}, then on to the review. The "
                                     "rest are skipped; start them again later.")
        elif getattr(self, "overall", None) is not None and self.overall.winfo_exists():
            self.overall.config(text="")

    def _job_state(self, k, state, why=None, details=None):
        """One video in the list: waiting, being worked on, done, couldn't be done (with a
        "What went wrong?" link when there's a reason), or skipped."""
        if state == "now" and self._work_t0 is None:
            self._work_t0 = time.time()          # time left counts from the first video
        rows = getattr(self, "job_rows", [])
        if 0 <= k < len(rows) and rows[k][0].winfo_exists():
            sym, col = self.JOB_LOOK[state]
            col = globals()[col]
            rows[k][0].config(text=sym, fg=col)
            if state != "now":
                self._job_note(k, "")
            rows[k][1].config(fg=INK if state == "now" else col if state == "failed" else MUTED,
                              font=(FONT, 10, "bold") if state == "now" else (FONT, 10))
            if state == "failed" and why:
                link = tk.Label(self.job_frames[k], text="What went wrong?", bg=BG, fg=ACCENT,
                                font=(FONT, 10, "underline"), cursor="hand2")
                link.pack(side="left", padx=(12, 0))
                link.bind("<Button-1>", lambda e: self._problem(why, details))

    def _time_left_for_all(self, frac):
        """"About 1 hr 20 min left for all 13", once there's enough to go on."""
        lbl = getattr(self, "overall", None)
        if self._work_n < 2 or self._work_t0 is None or lbl is None or not lbl.winfo_exists() \
                or getattr(self, "stop_after", False):     # it says it's stopping instead
            return
        el = time.time() - self._work_t0
        if frac < 0.02 or el < 30:
            return
        left = el / frac * (1 - frac)
        lbl.config(text=("Less than a minute" if left < 60 else f"About {fmt_len(left)}")
                   + f" left for all {self._work_n}")

    def cancel(self):
        """Back to the start page at once (the owner, 2026-11-09: "it taking a while to
        actually cancel and go back to home screen"). The work stops by itself at its next
        check, and anything it still sends is dropped (see _start_work)."""
        engine.PAUSE.resume()            # frozen helpers couldn't stop
        self.run = getattr(self, "run", 0) + 1
        self.show_setup()

    def _start_work(self, target):
        """Watching and listening, or saving, as work with its own number. A newer number
        means it was cancelled: it stops at its next check and what it sends is dropped.
        New work waits for the old to finish stopping first, so the two never work on the
        same files (a worker finishing its bit, a half-saved copy being tidied away)."""
        self.run = getattr(self, "run", 0) + 1
        run, before = self.run, getattr(self, "work_thread", None)

        def go():
            if before is not None and before.is_alive():
                self.q.put(("for_run", run, ("progress", 0.0, "Finishing stopping the last "
                                                              "one…", "")))
                before.join()
            if self.run == run:
                target(run)
        self.work_thread = threading.Thread(target=go, daemon=True)
        self.work_thread.start()

    def _analyze_thread(self, run=None):
        with engine.keep_awake():          # the PC doesn't sleep while videos are worked on
            self._analyze_now(getattr(self, "run", 0) if run is None else run)

    def _analyze_now(self, run):
        jobs = self.jobs                   # this run's, even if a new one starts

        def put(msg):
            self.q.put(("for_run", run, msg))
        try:
            if engine.tools_missing(self.scan_opts):
                put(("which", "Getting ready (one time only)"))
                try:
                    engine.install_tools(self.scan_opts,
                                         progress=lambda f, m: put(("progress", f, m, "")))
                except Exception as ex:
                    # carry on with whatever did install; the review page says what was skipped
                    save_details(traceback.format_exc())
                    put(("warn", "Some of the checking tools couldn't be set up, so this "
                                "run uses the ones that are ready.\n\n" + plain_error(ex)))
            self._run_workers(run, jobs)
            put(("analyzed",))
        except KeyboardInterrupt:
            put(("cancelled",))
        except Exception as ex:
            put(("error", plain_error(ex), traceback.format_exc()))

    def _run_workers(self, run=None, jobs=None):
        """Watch and listen to every video, up to "Videos at once" at a time, each in its own
        worker process (videoqueue.py), so a season gets done sooner and one video going
        wrong never stops the rest or the window. Runs on the analyze thread."""
        run = getattr(self, "run", 0) if run is None else run
        jobs = self.jobs if jobs is None else jobs
        n = len(jobs)

        def put(msg):
            self.q.put(("for_run", run, msg))

        def stopped():                     # Cancel, or the window closing
            return self.cancel_flag or getattr(self, "run", 0) != run
        # started once here, so the workers don't each try to start it; in the background
        # (1.18.54: the videos waited up to 20 s for it, and each video only needs it once
        # it has listened; a video that asks before it answers doesn't start a second one)
        if engine.needs(engine.full_opts(self.scan_opts))["ai"]:
            def start_ai():
                try:
                    engine.ai.start_ollama(wait=20)
                except Exception:
                    pass
            threading.Thread(target=start_ai, daemon=True).start()
        events = queue.Queue()
        workers = self.workers = VQ.Workers(lambda k, m: events.put((k, m)))
        frac = [0.0] * n
        todo, running, finished = list(range(n)), set(), set()
        procs = {}                         # each video's worker, frozen while paused

        def which():
            if len(running) == 1:
                k = next(iter(running))
                put(("which", (f"Video {k + 1} of {n}:  " if n > 1 else "") +
                            short(Path(jobs[k]["video"]).stem, 80)))
            elif running:
                put(("which", f"{len(running)} videos at once  ·  "
                                     f"{len(finished)} of {n} done"))

        def failed(k, error, details):
            jobs[k]["error"], jobs[k]["details"] = error, details
            save_details(details)
            put(("job", k, "failed", error, details))

        try:
            while todo or running:
                if stopped():
                    raise KeyboardInterrupt
                if getattr(self, "stop_after", False):     # "Stop after ..."
                    for k in todo:
                        jobs[k]["skipped"] = True
                        put(("job", k, "skipped"))
                    todo = []
                at_once = getattr(self, "at_once", 1)
                started = False
                while todo and len(running) < at_once and not engine.PAUSE.on:
                    k = todo.pop(0)
                    j = jobs[k]
                    try:
                        procs[k] = workers.start(
                            k, {"video": j["video"], "work": str(j["work"]),
                                "groups": self.groups, "opts": self.scan_opts,
                                "threads": VQ.threads_each(min(at_once, n))})
                        engine.PAUSE.track(procs[k])     # frozen while paused
                    except Exception as ex:
                        finished.add(k)
                        frac[k] = 1.0
                        failed(k, f"{Path(j['video']).name}: {plain_error(ex)}",
                               f"{j['video']}\n\n{traceback.format_exc()}")
                        continue
                    running.add(k)
                    started = True
                    put(("job", k, "now"))
                if started:
                    which()
                try:
                    k, msg = events.get(timeout=0.5)
                except queue.Empty:
                    continue
                j = jobs[k]
                if "p" in msg:
                    frac[k] = max(frac[k], max(0.0, min(1.0, float(msg["p"]))))
                    m = str(msg.get("m", ""))
                    if n > 1:
                        put(("jobmsg", k, m))
                    put(("progress", sum(frac) / n, m if len(running) < 2 else
                                f"Working on {len(running)} videos at the same time. How each "
                                f"one is going is in the list below.", ""))
                elif msg.get("done"):
                    try:
                        j["analysis"] = json.loads(
                            (Path(j["work"]) / "analysis.json").read_text())
                        put(("job", k, "done"))
                    except Exception as ex:
                        failed(k, f"{Path(j['video']).name}: {plain_error(ex)}",
                               f"{j['video']}\n\n{traceback.format_exc()}")
                elif "error" in msg:
                    error = (msg.get("raw") or msg["error"]) if msg.get("video_error") else \
                        f"{Path(j['video']).name}: {msg['error']}"
                    failed(k, error, f"{j['video']}\n\n{msg.get('details', '')}")
                elif "exit" in msg:
                    if k in procs:
                        engine.PAUSE.untrack(procs.pop(k))
                    running.discard(k)
                    finished.add(k)
                    frac[k] = 1.0
                    if not (j["analysis"] or j["error"] or stopped()):
                        # it stopped without a word: a hard crash (written to its log)
                        try:
                            log = (Path(j["work"]) / "worker_log.txt").read_text(
                                encoding="utf8", errors="replace")[-4000:]
                        except OSError:
                            log = ""
                        why = (VQ.OUT_OF_MEMORY if VQ.memory_trouble(log) else
                               "CleanView stopped working on this video unexpectedly.")
                        failed(k, f"{Path(j['video']).name}: {why}",
                               f"{j['video']}\n\nThe worker ended (code {msg['exit']}).\n\n{log}")
                    which()
        finally:
            for p in procs.values():
                engine.PAUSE.untrack(p)
            if running:          # Cancel, or something went wrong here: stop the rest
                engine.PAUSE.resume()        # frozen workers couldn't stop
                workers.stop_all()

    def _at_once(self):
        """How many videos are worked on at the same time (the working page's choice)."""
        n = self._load_settings().get("at_once")
        return n if n in VQ.AT_ONCE_CHOICES else VQ.default_at_once()

    def _set_at_once(self, n):
        """Changed on the working page: the next videos to start follow it."""
        self.at_once = n
        try:
            s = self._load_settings()
            s["at_once"] = n
            APP_DATA.mkdir(parents=True, exist_ok=True)
            path = APP_DATA / "cleanview_settings.json"
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(s))
            os.replace(tmp, path)
        except Exception:
            pass
        btn = getattr(self, "stop_btn", None)
        if btn is not None and btn.winfo_exists() and not getattr(self, "stop_after", False):
            btn.config(text=self._stop_label())

    def _stop_label(self):
        return ("Stop after this video" if getattr(self, "at_once", 1) == 1 else
                "Stop after the ones being done now")

    def _job_note(self, k, text):
        """How one video is going, beside its name in the list (several at once)."""
        notes = getattr(self, "job_notes", [])
        if 0 <= k < len(notes) and notes[k].winfo_exists():
            notes[k].config(text=short(text, 70))

    def _render_thread(self, run=None):
        with engine.keep_awake():          # nor while clean copies are saved
            self._render_now(getattr(self, "run", 0) if run is None else run)

    def _render_now(self, run):
        def put(msg):
            self.q.put(("for_run", run, msg))

        def stopped():                     # a half-saved copy is removed (engine.render)
            return self.cancel_flag or getattr(self, "run", 0) != run
        try:
            todo = [j for j in self.jobs if j["analysis"]]
            encs = None
            if any(j["cuts"] for j in todo):
                put(("progress", 0.0, "Checking the fastest way to save video…", ""))
                encs = engine.working_encoders()
            results, failed = [], []
            self._save_failures = []
            for k, j in enumerate(todo):
                put(("which", (f"Video {k + 1} of {len(todo)}:  " if len(todo) > 1 else "")
                            + short(Path(j["video"]).stem, 80)))
                put(("job", k, "now"))
                try:
                    results.append(engine.render(
                        j["work"], self.outdir, j["cuts"], encoders=encs, lines=j.get("lines", []),
                        words=j.get("words"), quiet=j.get("quiet"),
                        progress=lambda f, m, k=k: put(("progress", (k + f) / len(todo), m, "")),
                        log=lambda m: None, cancel=stopped))
                    put(("job", k, "done"))
                except Exception as ex:     # carry on with the other episodes
                    details = f"{j['video']}\n\n{traceback.format_exc()}"
                    save_details(details)
                    self._save_failures.append(details)
                    failed.append(f"{Path(j['video']).name}: {plain_error(ex)}")
                    put(("job", k, "failed", failed[-1], details))
            put(("rendered", results, failed))
        except KeyboardInterrupt:
            put(("cancelled",))
        except Exception as ex:
            put(("error", plain_error(ex), traceback.format_exc()))

    # ---------- noticing a freeze or a crash ----------
    def _watch_for_freezes(self):
        """A beat from the window every second, and a watcher that writes down what every
        part of CleanView was doing if the beats stop for STALL_SECS (and, if they start
        again, how long it was). A crash (in the speech or picture tools, say) is written
        down by faulthandler. A question box doesn't count: the beats go on under it."""
        import faulthandler
        try:
            APP_DATA.mkdir(parents=True, exist_ok=True)
            if CRASH_LOG.exists() and CRASH_LOG.stat().st_size:
                _add_problem_note("CleanView closed suddenly.\n\n"
                                  + CRASH_LOG.read_text(encoding="utf8", errors="replace"))
            self._crash_log = open(CRASH_LOG, "w", encoding="utf8")
            faulthandler.enable(self._crash_log, all_threads=True)
        except Exception:
            pass
        self._doing, self._gone = {}, False
        self._beat = time.monotonic()

        def beat():
            self._beat = time.monotonic()
            self._beat_id = self.after(1000, beat)
        beat()

        def watch():
            woke, stuck = time.monotonic(), None
            while not self._gone:
                time.sleep(5)
                now = time.monotonic()
                if now - woke > 30:          # the PC was asleep, not CleanView
                    self._beat = now
                woke = now
                if stuck is None and now - self._beat > STALL_SECS:
                    stuck = self._beat
                    self._note_freeze(now - stuck)
                elif stuck is not None and self._beat > stuck:
                    _add_problem_note(f"It answered again after about "
                                      f"{int(self._beat - stuck)} seconds.")
                    stuck = None
        threading.Thread(target=watch, daemon=True, name="freeze watcher").start()

    def destroy(self):
        self._gone = True            # stops the watcher, and the crash log is closed
        for name in ("_offer_id", "_beat_id", "_poll_id"):
            try:
                self.after_cancel(getattr(self, name))
            except Exception:
                pass
        try:
            import faulthandler
            faulthandler.disable()
            self._crash_log.close()
        except Exception:
            pass
        super().destroy()

    def _note_freeze(self, secs):
        """Runs on the watcher's thread, so it reads no part of the window."""
        doing = self._doing
        lines = [f"CleanView {_app_version()} stopped answering for {int(secs)} seconds "
                 f"({time.strftime('%Y-%m-%d %H:%M')}).",
                 f"Page: {self.page_name}",
                 f"Doing: {doing.get('which', '')} {doing.get('status', '')}".rstrip(),
                 _memory_note()]
        names = {t.ident: t.name for t in threading.enumerate()}
        for ident, frame in sys._current_frames().items():
            if names.get(ident) == "freeze watcher":
                continue
            lines.append(f"\n--- {names.get(ident, ident)} ---")
            lines.append("".join(traceback.format_stack(frame)[-12:]).rstrip())
        _add_problem_note("\n".join(line for line in lines if line))

    def _offer_problem_note(self):
        """CleanView froze or closed suddenly last time: send in what it was doing?"""
        try:
            text = PROBLEM_NOTE.read_text(encoding="utf8").strip()
            PROBLEM_NOTE.replace(PROBLEM_NOTE.with_name("stopped_before.txt"))
        except OSError:
            return
        if not text:
            return
        what = ("closed suddenly" if text.startswith("CleanView closed suddenly")
                else "stopped responding")
        path = APP_DATA / f"CleanView {what} {time.strftime('%Y-%m-%d %H-%M')}.json"
        try:
            path.write_text(json.dumps({"app": "CleanView", "version": _app_version(),
                                        "what": what, "note": text}, indent=1),
                            encoding="utf8")
        except OSError:
            return
        if not learn.send_url():
            return
        chime()
        if not messagebox.askyesno(
                "CleanView", f"CleanView {what} last time. Sorry about that!\n\nSend a note "
                "about what it was doing, so it can be fixed? It has the step it was on and "
                "the video's name. No video or sound.", parent=self):
            return

        def go():
            try:
                learn.send(path, "problem")
                self.q.put(("call", lambda: messagebox.showinfo(
                    "CleanView", "Sent. Thank you!", parent=self)))
            except Exception as ex:
                save_details(f"Sending {path}\n\n{traceback.format_exc()}")
                why = plain_error(ex)
                self.q.put(("call", lambda: self._send_by_hand(
                    path, f"Couldn't send it ({why[:1].lower() + why[1:].rstrip('.')}). "
                          f"Check the internet connection.\n\n")))
        threading.Thread(target=go, daemon=True).start()

    def _poll(self):
        """Handle what the working threads sent. At most 500 at a time, and only the newest
        progress, so a flood of them can never keep the window from answering."""
        msgs = []
        try:
            while len(msgs) < 500:
                msgs.append(self.q.get_nowait())
        except queue.Empty:
            pass
        def kind(m):
            return m[2][0] if m[0] == "for_run" else m[0]
        newest = max((i for i, m in enumerate(msgs) if kind(m) == "progress"), default=-1)
        try:
            for i, msg in enumerate(msgs):
                if kind(msg) == "progress" and i != newest:
                    continue
                try:
                    self._handle(msg)
                except Exception:      # one bad message must never stop the window updating
                    self._problem("Something unexpected went wrong, but CleanView is still "
                                  "running.", traceback.format_exc())
        finally:
            if not getattr(self, "_gone", False):
                self._poll_id = self.after(150 if len(msgs) < 500 else 10, self._poll)

    def _handle(self, msg):
        if msg[0] == "for_run":                 # from watching and listening, or saving
            if msg[1] != getattr(self, "run", 0):
                return                          # cancelled: already back on the start page
            msg = msg[2]
        kind = msg[0]
        if kind in ("which", "progress"):       # for a note about a freeze
            getattr(self, "_doing", {})["which" if kind == "which" else "status"] = \
                msg[1] if kind == "which" else msg[2]
        alive = getattr(self, "pb", None) is not None and self.pb.winfo_exists()
        if kind == "progress" and alive:
            self.pb["value"] = int(max(0.0, min(1.0, msg[1])) * 1000)
            if not engine.PAUSE.on:
                self.status.config(text=msg[2])
                self._time_left_for_all(msg[1])
        elif kind == "which" and alive:
            self.which.config(text=msg[1])
        elif kind == "job" and alive:
            self._job_state(*msg[1:])
        elif kind == "jobmsg" and alive:
            self._job_note(msg[1], msg[2])
        elif kind == "call":
            msg[1]()
        elif kind in ("analyzed", "rendered", "cancelled", "error") and engine.PAUSE.on:
            engine.PAUSE.resume()
            self._handle(msg)
        elif kind == "analyzed":
            self.after_analyze()
        elif kind == "rendered":
            self._rendered(msg[1], msg[2])
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
        elif kind == "update_ready":
            self._show_update_bar(msg[1])
        elif kind == "update_none":
            messagebox.showinfo("CleanView", f"You have the newest version ({msg[1]})."
                                if msg[1] else "Couldn't check for updates right now. "
                                "Check your internet connection.")
        elif kind == "update_done":
            self._update_done(*msg[1:])
        elif kind == "warn":
            messagebox.showwarning("CleanView", msg[1])
        elif kind == "preview_error":
            messagebox.showerror("CleanView", msg[1])
        elif kind == "error":
            self._problem(msg[1], msg[2])
            self.show_setup()

    def _rendered(self, results, failed):
        """After saving: the done page for what was saved, and a plain word about
        anything that couldn't be. If nothing was saved, back to the review."""
        if not failed:
            self.show_done(results)
            return
        listing = "\n\n".join(failed)
        if not results:
            self._tell_save_failed("The clean copy couldn't be saved:\n\n" + listing +
                                   "\n\nYour review is just as you left it, so you can try again.")
            self.show_review()
            return
        self._tell_save_failed("These couldn't be saved:\n\n" + listing +
                               "\n\nThe others are done. Your review is still saved: use “Pick "
                               "up where I left off” on the start page to try these again.")
        self.show_done(results, keep_review=True)

    def _tell_save_failed(self, text):
        """Say what couldn't be saved, and offer to send in what went wrong (Jason,
        2026-11-07: Snow White failed four times at about the same spot, and nobody
        could see why)."""
        details = "\n\n----------\n\n".join(getattr(self, "_save_failures", []))
        if not details or not learn.send_url():
            messagebox.showwarning("CleanView", text, parent=self)
            return
        chime()
        if not messagebox.askyesno(
                "CleanView", text + "\n\nSend a note about what went wrong, so it can be fixed? "
                "It has the video's name and the error. No video or sound.", parent=self):
            return
        path = APP_DATA / f"CleanView couldn't save {time.strftime('%Y-%m-%d %H-%M')}.json"
        try:
            path.write_text(json.dumps({"app": "CleanView", "version": _app_version(),
                                        "what": "couldn't save the clean copy",
                                        "note": details.replace(str(Path.home()), "~")},
                                       indent=1), encoding="utf8")
        except OSError:
            return

        def go():
            try:
                learn.send(path, "problem")
                self.q.put(("call", lambda: messagebox.showinfo(
                    "CleanView", "Sent. Thank you!", parent=self)))
            except Exception as ex:
                save_details(f"Sending {path}\n\n{traceback.format_exc()}")
                why = plain_error(ex)
                self.q.put(("call", lambda: self._send_by_hand(
                    path, f"Couldn't send it ({why[:1].lower() + why[1:].rstrip('.')}). "
                          f"Check the internet connection.\n\n")))
        threading.Thread(target=go, daemon=True).start()

    def after_analyze(self):
        bad = [j for j in self.jobs if j["error"]]
        if bad:
            details = "\n\n----------\n\n".join(j.get("details") or j["error"] for j in bad)
            self._problem("These couldn't be cleaned and will be skipped:\n\n" +
                          "\n\n".join(j["error"] for j in bad), details)
        good = [j for j in self.jobs if j["analysis"]]
        if not good:
            self.show_setup()
            return
        self.show_review()   # always: so every mute and cut can be seen and unticked
        self._save_session()   # so closing or updating never loses it

    # ---------- page 3: review ----------
    def _pick_review_ai(self, good):
        """Claude, ChatGPT or Gemini for this review page: the one that did the review,
        else the one picked on the start page, else any that's ready, else None."""
        by_name = {v: k for k, v in cc.NAMES.items()}
        for j in good:
            r = by_name.get(j["analysis"].get("reviewer") or "")
            if r:
                return r
        r = self._cloud() if hasattr(self, "opts") else None
        if r:
            return r
        # (Jason, 2026-11-04: with the AI on this PC reading the dialogue there was no chat,
        # so he couldn't tell it what it got wrong) any one that's set up will do
        state = getattr(self, "ai_state", {})
        for p in cc.NAMES:
            if state.get(p) == "ready":
                return p
        return None

    def show_review(self, tab=0):
        global AI_NAME
        keep = None                 # rebuilding after a change: stay where you were
        if self.page_name == "review":
            try:
                keep = (self._found_canvas.canvasy(0), self.dlg_tv.yview()[0])
            except Exception:
                keep = None
        self.page_name = "review"
        good = [j for j in self.jobs if j["analysis"]]
        self.review_ai = self._pick_review_ai(good)
        if not self.review_ai:
            self._check_every_ai()
        AI_NAME = cc.name(self.review_ai)
        if self.review_ai:
            cc.use(self.review_ai)
        self._ai_ok = bool(self.review_ai) and (
            getattr(self, "ai_state", {}).get(self.review_ai) == "ready" or
            any(j["analysis"].get("reviewer") for j in good))
        self.show_fine = getattr(self, "show_fine", False)
        vis = {id(j): self._visible(j["analysis"]) for j in good}
        n = sum(len(vis[id(j)][0]) for j in good)
        nl = sum(len(vis[id(j)][1]) for j in good)
        nw = sum(len(vis[id(j)][2]) for j in good)
        nq = sum(len(j["analysis"].get("quiet") or []) for j in good)
        n_fine = sum(vis[id(j)][3] for j in good)
        parts = []
        if n:
            parts.append(f"{n} scene{'s' if n != 1 else ''}")
        if nl:
            parts.append(f"{nl} line{'s' if nl != 1 else ''}")
        if nw:
            parts.append(f"{nw} word{'s' if nw != 1 else ''}")
        if nq:
            parts.append(f"{nq} loud song{'s' if nq != 1 else ''}")
        title = (", ".join(parts[:-1]) + " and " + parts[-1] if len(parts) > 1 else
                 parts[0] if parts else "Nothing found") + (" to check" if parts else "")
        p = self._new_page(title,
                           "Checked scenes will be cut and checked words and lines muted. Untick "
                           "anything you want to keep, and use \u201cAll dialogue\u201d" +
                           (f" or \u201cAsk {AI_NAME}\u201d" if self.review_ai else "") +
                           " to add anything it missed.",
                           name=short(Path(good[0]["video"]).stem, 70) +
                           (f" and {len(good) - 1} more" if len(good) > 1 else ""))
        self.scene_vars, self.line_vars, self.word_vars, self.quiet_vars = [], [], [], []
        self.dlg_vars = {}          # (job index, dialogue line index) -> BooleanVar
        self.found_frames = {}
        multi = len(good) > 1
        nb = ttk.Notebook(p)
        nb.pack(fill="both", expand=True)
        self._nb = nb
        self.after_idle(lambda: nb.winfo_exists() and nb.select(tab))
        t_found = tk.Frame(nb, bg=BG)
        t_dlg = tk.Frame(nb, bg=BG)
        t_chat = tk.Frame(nb, bg=BG)
        nb.add(t_found, text="  Found  ")
        nb.add(t_dlg, text="  All dialogue  ")
        nb.add(t_chat, text=f"  Ask {AI_NAME if self.review_ai else 'Claude, ChatGPT or Gemini'}  ")

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
        if n_fine or self.show_fine:
            frow = tk.Frame(t_found, bg=BG)
            frow.pack(fill="x", pady=(0, 4))
            self.fine_var = tk.BooleanVar(value=self.show_fine)
            ttk.Checkbutton(frow, text=f"Also show the {n_fine} that {AI_NAME} says are fine "
                            "(they won't be muted or cut)", variable=self.fine_var,
                            command=self._toggle_fine).pack(side="left")
        inner = self._scroll_area(t_found)
        self._found_canvas = inner._canvas
        for ji, j in enumerate(good):
            st = j["analysis"]
            j["_ji"] = ji
            if multi:
                tk.Label(inner, text=Path(j["video"]).name, bg=BG, fg=INK,
                         font=(FONT, 12, "bold"), anchor="w").pack(fill="x", padx=8, pady=(14, 0))
            if st.get("claude_summary"):
                box = self._round_card(inner, fill=NOTE, edge=NOTE_EDGE)
                tk.Label(box, text=f"{st.get('reviewer') or AI_NAME}'s review", bg=NOTE,
                         fg=NOTE_INK,
                         font=(FONT, 10, "bold"), anchor="w").pack(fill="x")
                tk.Label(box, text=st["claude_summary"], bg=NOTE, fg=INK, font=(FONT, 10),
                         wraplength=wrap_width(700), justify="left", anchor="w").pack(fill="x")
                cnt = st.get("claude_counts") or {}
                if cnt.get("dropped") or cnt.get("added") or cnt.get("words"):
                    tk.Label(box, text=f"Unticked {cnt.get('dropped', 0)} false alarm(s) and added "
                             f"{cnt.get('added', 0)} missed item(s)" +
                             (f"; {cnt['words']} line(s) now mute just the bad word"
                              if cnt.get("words") else "") +
                             ". Anything you change yourself stays the way you set it.", bg=NOTE, fg=MUTED, font=(FONT, 9),
                             wraplength=wrap_width(700), justify="left", anchor="w").pack(fill="x", pady=(2, 0))
            for note in engine.video_notes(st):     # not which AI model or how long it took
                tk.Label(inner, text="\u2139 " + note, bg=BG, fg=MUTED, font=(FONT, 9),
                         wraplength=wrap_width(720), justify="left", anchor="w").pack(fill="x", padx=8)
            holder = tk.Frame(inner, bg=BG)
            holder.pack(fill="x")
            self.found_frames[ji] = holder
            scs, lns, wds, _ = vis[id(j)]
            if not scs:
                tk.Label(holder, text="No scenes to check in this one.", bg=BG,
                         fg=INK, font=(FONT, 10), anchor="w").pack(fill="x", padx=8, pady=(6, 0))
            for sc in scs:
                self._scene_card(holder, j, sc)
            if lns:
                self._lines_card(inner, j, lns)
            if wds:
                self._words_card(inner, j, wds)
            if st.get("quiet"):
                self._music_card(inner, j, st["quiet"])

        self._dialogue_tab(t_dlg, good)
        if keep:
            def restore(tries=3):
                c = self._found_canvas
                if not c.winfo_exists():
                    return
                self.update_idletasks()
                c.configure(scrollregion=c.bbox("all"))
                box = c.bbox("all")
                if box and box[3] > 0:
                    c.yview_moveto(keep[0] / box[3])
                try:
                    self.dlg_tv.yview_moveto(keep[1])
                except Exception:
                    pass
                if tries > 1:
                    self.after(60, lambda: restore(tries - 1))
            self.after(20, restore)
        self._chat_tab(t_chat, good)
        # where it saves, on its own row above the buttons (beside them it squeezed "Send
        # what we refined…" until its words were cut off)
        where = tk.Frame(self.footer, bg=BG)
        where.pack(side="top", fill="x", pady=(0, self._px(8)))
        ttk.Button(self.footer, text="Save clean copies" if multi else "Save clean copy",
                   style="Accent.TButton", command=self._save_from_review).pack(side="right")
        # where it goes, how big it'll be and the room there (Jason, 2026-11-07: the drive
        # filled up, and he didn't know he could choose where it saves)
        ttk.Button(where, text="Change…", style="Small.TButton",
                   command=self._change_save_folder).pack(side="right")
        self.space_lbl = tk.Label(where, text="", bg=BG, fg=MUTED, font=(FONT, 9),
                                  justify="right", anchor="e")
        self.space_lbl.pack(side="right", padx=(0, self._px(10)))
        self._show_space()
        for v, _, _ in self.scene_vars:          # a cut ticked or unticked changes the size
            v.trace_add("write", lambda *a: self.after_idle(self._show_space))
        # back to the start page without saving (Jason: just checking what's in it);
        # the review is kept, so "Pick up where I left off" opens it again
        ttk.Button(self.footer, text="\u25c0 Back to start", style="Plain.TButton",
                   command=self._back_to_start).pack(side="left", padx=(0, 8))
        # what was refined, sent in before saving too (Lauren): the ticks as they are now
        ttk.Button(self.footer, text="Send what we refined…", style="Plain.TButton",
                   command=self._send_report_now).pack(side="left")

    def _save_folder(self):
        good = [j for j in self.jobs if j.get("analysis")]
        return self.outdir or (str(Path(good[0]["video"]).parent / "Clean") if good else "")

    def _clean_bytes(self):
        """About how big the clean copies will be, with the scenes ticked now."""
        total = 0
        for j in [j for j in self.jobs if j.get("analysis")]:
            st = j["analysis"]
            cut = sum(sc["e"] - sc["s"] for v, jj, sc in getattr(self, "scene_vars", [])
                      if jj is j and v.get())
            # long muted stretches are cut too (1.18.60), so they count here
            muted = [(m["s"], m["e"]) for v, jj, m in getattr(self, "word_vars", [])
                     if jj is j and v.get()]
            muted += [(l["s"], l["e"]) for v, jj, l in getattr(self, "line_vars", [])
                      if jj is j and v.get()]
            cut += sum(e - s for s, e in engine.long_mutes(engine._merge(muted)))
            v = (st.get("info") or {}).get("video") or {}
            total += engine.clean_size(j["video"], st.get("duration") or 0, cut,
                                       v.get("width"), v.get("height"))
        return total

    def _show_space(self):
        lbl = getattr(self, "space_lbl", None)
        if lbl is None or not lbl.winfo_exists():
            return
        folder = self._save_folder()
        free = engine.free_space(folder) if folder else None
        need = self._clean_bytes()
        path = os.path.normpath(folder)               # the end of it says the most
        path = path if len(path) <= 48 else path[:3] + "…" + path[-44:]
        text = f"Saves to  {path}\nAbout {fmt_bytes(need)}"
        if free is not None:
            text += f"  ·  {fmt_bytes(free)} free there"
        lbl.config(text=text, fg=WARN if free is not None and free < room_needed(need)
                   else MUTED)

    def _change_save_folder(self):
        d = filedialog.askdirectory(title="Where should the clean copies go?",
                                    initialdir=self._save_folder() or None, parent=self)
        if d:
            self.outdir = d
            self._remember_save_to(d)
            self._save_session()
            self._show_space()
        return bool(d)

    def _room_to_save(self):
        """Enough room on the drive? If not, offer to choose somewhere else. False: don't
        save now."""
        while True:
            folder = self._save_folder()
            free, need = engine.free_space(folder), self._clean_bytes()
            if free is None or free >= room_needed(need):
                return True
            chime()
            ans = messagebox.askyesnocancel(
                "CleanView", f"The clean copy needs about {fmt_bytes(need)}, but there's only "
                f"{fmt_bytes(free)} free where it's being saved:\n\n{os.path.normpath(folder)}"
                "\n\nChoose somewhere else to save it?\n\nYes: choose a folder (another drive "
                "works too).\nNo: save it there anyway.\nCancel: go back to the review.",
                parent=self)
            if ans is None:
                return False
            if ans is False:
                return True
            if not self._change_save_folder():
                return False

    def _back_to_start(self):
        self._learn_choices()           # learned without saving a copy too (Jason)
        self._save_session()
        self.reset()

    def _learn_choices(self):
        """Remember her ticks for next time (each choice counts once, however often
        she leaves the review and comes back: learn.record)."""
        flagged = {(j["_ji"], l["idx"]) for _, j, l in self.line_vars if "idx" in l}
        for j in [j for j in self.jobs if j["analysis"]]:
            d = j["analysis"].get("dialogue", [])
            extra = [d[i] for (ji, i), v in self.dlg_vars.items()
                     if ji == j["_ji"] and v.get() and (ji, i) not in flagged and i < len(d)]
            try:
                mine = [(v, l) for v, jj, l in self.line_vars if jj is j]
                scs = [(v, sc) for v, jj, sc in self.scene_vars if jj is j]
                wds = [(v, m) for v, jj, m in self.word_vars if jj is j]
                learn.record(j["analysis"].get("show", "_movies"),
                             [l for _, l in mine], [v.get() for v, _ in mine], extra,
                             [sc for _, sc in scs if not sc.get("added")],
                             [v.get() for v, sc in scs if not sc.get("added")],
                             [sc for v, sc in scs if sc.get("added") and v.get()],
                             [m for _, m in wds], [v.get() for v, _ in wds],
                             video=j["analysis"].get("path"))
            except Exception:
                pass

    # --- hiding what the AI says is fine
    def _visible(self, st):
        """(scenes, lines, words, how many hidden). By default anything the AI
        said is fine (and that's still unticked) is hidden; the rest is shown:
        what it says to remove, what it's unsure of, and what it didn't judge."""
        def fine(it, on):
            return (not self.show_fine and not on and not it.get("by_you")
                    and (it.get("claude") or {}).get("decision") == "not an issue")
        scs = [x for x in st["scenes"] if not fine(x, x.get("cut", True))]
        lns = [x for x in st.get("lines", []) if not fine(x, x.get("mute", True))]
        wds = [x for x in st["mutes"] if not fine(x, not x.get("keep"))]
        hidden = (len(st["scenes"]) - len(scs) + len(st.get("lines", [])) - len(lns)
                  + len(st["mutes"]) - len(wds))
        if self.show_fine:
            hidden = sum(1 for k in ("scenes", "lines", "mutes") for x in st.get(k, [])
                         if (x.get("claude") or {}).get("decision") == "not an issue")
        return scs, lns, wds, hidden

    def _toggle_fine(self):
        for j in self.jobs:
            if j["analysis"]:
                self._sync_job(j)
        self.show_fine = self.fine_var.get()
        self.show_review()

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
        ttk.Button(top, text="Mute a word in it\u2026", style="Small.TButton",
                   command=self._mute_word_selected).pack(side="right", padx=(0, 6))
        if getattr(self, "_ai_ok", False):
            ttk.Button(top, text=f"\U0001F4AC Ask {AI_NAME} about the selected lines",
                       style="Small.TButton", command=self._ask_selected).pack(side="right",
                                                                              padx=(0, 6))
        tk.Label(tab, text="Click the box in the Mute column to mute a line (or pick lines and "
                 "press Space). Click a line to pick it; Ctrl-click or Shift-click picks more, "
                 "to cut them as a scene or ask about them.", bg=BG, fg=MUTED,
                 font=(FONT, 9), wraplength=wrap_width(760), justify="left").pack(anchor="w")
        box = tk.Frame(tab, bg=BG)
        box.pack(fill="both", expand=True, pady=(4, 0))
        tv = ttk.Treeview(box, columns=("mute", "time", "who", "line"), show="headings",
                          selectmode="extended")
        for col, w, txt in (("mute", 50, "Mute"), ("time", 70, "Time"), ("who", 120, "Who"),
                            ("line", 560, "Line")):
            tv.heading(col, text=txt)
            tv.column(col, width=w, anchor="center" if col == "mute" else "w",
                      stretch=(col == "line"))
        tv.tag_configure("muted", background=WORD_BG, foreground=WORD_INK)
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
        tv.bind("<space>", self._dlg_space)
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
        picked = tv.selection()
        tv.delete(*tv.get_children())
        for i, l in enumerate(st.get("dialogue", [])):
            if q and q not in l["text"].lower():
                continue
            v = self.dlg_vars.get((job["_ji"], i))
            who = l.get("who") or (voices[i].get("spk") if i < len(voices) and voices[i] else "")
            on = v is not None and v.get()
            tv.insert("", "end", iid=str(i), values=("\u2611" if on else "\u2610",
                                                     engine.cl.fmt_t(l["s"]), who, l["text"]),
                      tags=("muted",) if on else ())
        tv.selection_set([r for r in picked if tv.exists(r)])
        tv.yview_moveto(y)

    def _dlg_toggle(self, rows):
        job = self._dlg_job()
        for row in rows:
            v = self._dlg_var(job["_ji"], int(row))
            v.set(not v.get())
            if len(v.trace_info()) == 0:
                v.trace_add("write", lambda *_: self._fill_dialogue())
        self._fill_dialogue()

    def _dlg_click(self, ev):
        tv = self.dlg_tv
        if tv.identify_region(ev.x, ev.y) != "cell" or (ev.state & 0x0005):
            return       # header click, or Ctrl/Shift selection
        if tv.identify_column(ev.x) != "#1":
            return       # anywhere but the Mute box just picks the line
        row = tv.identify_row(ev.y)
        if row:
            self._dlg_toggle([row])

    def _dlg_space(self, _ev=None):
        self._dlg_toggle(self.dlg_tv.selection())
        return "break"

    def _mute_word_selected(self):
        rows = [int(r) for r in self.dlg_tv.selection()]
        if len(rows) != 1:
            messagebox.showinfo("CleanView", "Click one line first, then try again.")
            return
        from tkinter import simpledialog
        job = self._dlg_job()
        line = job["analysis"]["dialogue"][rows[0]]
        words = simpledialog.askstring("Mute a word", f"\u201c{line['text'][:200]}\u201d\n\nWhich "
                                       "word or words should be muted? (type them as they're "
                                       "written)", parent=self)
        if not words:
            return
        self._sync_job(job)
        st = job["analysis"]
        done = []
        for w in re.split(r"[,|]", words):
            m = engine.word_mute(st, line, w.strip(), "you added") if w.strip() else None
            if m is not None:
                m["keep"], m["by_you"] = False, True
                done.append(w.strip())
        if not done:
            messagebox.showinfo("CleanView", "Couldn't find that in the line.")
            return
        self._save_session()
        self.show_review(tab=1)

    def _ask_selected(self):
        rows = [int(r) for r in self.dlg_tv.selection()]
        if not rows:
            messagebox.showinfo("CleanView", "Select the lines first (click, then Shift-click).")
            return
        self._ask_about(self._dlg_job(), "lines", rows=rows)

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
        if not hasattr(self, "undo_stack"):
            self.undo_stack = []
        top = tk.Frame(tab, bg=BG)
        top.pack(fill="x", pady=(8, 6))
        self.chat_job = ttk.Combobox(top, values=[short(Path(j["video"]).name, 40) for j in good],
                                     state="readonly", width=36)
        self.chat_job.current(min(getattr(self, "_chat_ji", 0), len(good) - 1))
        if len(good) > 1:
            self.chat_job.pack(side="left")
        p = self.review_ai
        n = cc.name(p)
        state = (getattr(self, "ai_state", {}).get(p) or cc.status(p)) if p else "none"
        if state == "none" and self._ai_checking():
            state = "checking"
        if state != "ready":
            msg = {"checking": "Checking whether Claude, ChatGPT or Gemini is set up on this "
                               "PC\u2026",
                   "none": "This needs Claude, ChatGPT or Gemini. If you have one of them, "
                           "pick it under \u201cWho reads the dialogue\u201d on the start page "
                           "and set it up. After that you can chat with it here even when the "
                           "AI on this PC reads the dialogue. "
                           "Everything else works without them.",
                   "missing": f"{n} isn't set up yet. Go back to the start page and use "
                              f"\u201cSet up {n}\u201d under AI helper, then run this again."}.get(
                state, f"{n} isn't signed in yet. Use \u201cSign in to {n}\u201d on the start page.")
            tk.Label(tab, text=msg, bg=BG, fg=INK, font=(FONT, 10), wraplength=wrap_width(700),
                     justify="left").pack(anchor="w", pady=20)
            return
        self.review_btn = ttk.Button(top, text="Review everything again", style="Accent.TButton",
                                     command=self._rereview)
        self.review_btn.pack(side="right")
        ttk.Button(top, text="\u21b6 Undo last chat change", style="Small.TButton",
                   command=self._undo_chat,
                   state="normal" if self.undo_stack else "disabled").pack(side="right",
                                                                         padx=(0, 8))
        several = sum(1 for j in self.jobs if j.get("analysis")) > 1
        ttk.Button(top, text=f"{n}'s findings on {'these videos' if several else 'this video'}",
                   style="Small.TButton",
                   command=self._open_findings).pack(side="right", padx=(0, 8))
        tk.Label(tab, text=f"\u201cReview everything again\u201d has {n} look over every scene, "
                 "line and word on the Found tab (including what you've added or unticked) "
                 "together with the whole dialogue, and decide what really needs removing, what's "
                 f"a false alarm and what was missed. Your own changes are never undone. {n}'s "
                 "calls are also saved to teach the AI on this PC, and kept in a spreadsheet.",
                 bg=BG, fg=MUTED, font=(FONT, 9), wraplength=wrap_width(720), justify="left").pack(anchor="w")
        tk.Label(tab, text="Ask about this episode or tell it what to change, and the list updates "
                 "right away: \u201cmute every time they talk about the affair\u201d, \u201ckeep "
                 "the kiss at 12:30\u201d, \u201cjust mute the word at 4:10\u201d, \u201ccut 22:15 "
                 "to 23:40\u201d.",
                 bg=BG, fg=MUTED, font=(FONT, 9), wraplength=wrap_width(720),
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

    def _open_findings(self):
        """A spreadsheet of what Claude, ChatGPT or Gemini found in the videos on this review
        page only (Jason, 2026-11-07: it had every movie he'd done, not the one he was on).
        The one with every video is still claude_findings.csv in CleanView's folder."""
        vids = [j["video"] for j in self.jobs if j.get("analysis")]
        if not learn.findings_rows(vids):
            messagebox.showinfo("CleanView", "Nothing saved for this video yet. Findings are "
                                "saved each time Claude, ChatGPT or Gemini reviews a video.")
            return
        for name in ("Findings for this video.csv",       # (a copy still open in Excel is locked)
                     f"Findings for this video {time.strftime('%H%M%S')}.csv"):
            try:
                learn.write_findings(APP_DATA / name, vids)
            except OSError:
                continue
            open_path(str(APP_DATA / name))
            return
        messagebox.showinfo("CleanView", "Couldn't make the spreadsheet. Close Excel and try "
                            "again.")

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
        for v, j, q in getattr(self, "quiet_vars", []):
            if j is job:
                q["lower"] = v.get()
                if v.get() != q.get("_shown", v.get()):
                    q["by_you"] = True
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
        cc.use(self.review_ai)
        self._log(f"{AI_NAME} is reviewing everything that was found, with the whole dialogue. "
                  "This can take a minute or two\u2026", "note")

        copy_ = copy.deepcopy(job["analysis"])    # she can keep ticking while it reads

        def go():
            try:
                self.q.put(("reviewed", job, None, engine.fetch_review(copy_, fresh=True)))
            except Exception as ex:
                save_details(traceback.format_exc())
                self.q.put(("reviewed", job, plain_error(ex), None))
        threading.Thread(target=go, daemon=True).start()

    def _reviewed(self, job, err, res):
        if err:
            if getattr(self, "chat_log", None) is not None and self.chat_log.winfo_exists():
                self.review_btn.config(state="normal")
                self.chat_btn.config(state="normal")
                self._log("\u26a0 " + err, "note")
            return
        if self.page_name != "review":       # she's moved on (saving): leave it be
            return
        st = job["analysis"]
        self._sync_job(job)                  # ticks she changed meanwhile count as hers
        engine.finish_review(st, engine.match_review(st, res), job["work"])
        cnt = st.get("claude_counts") or {}
        self._log(f"{AI_NAME}'s review: " + (st.get("claude_summary") or "done."))
        self.after(200, self._save_session)
        self._log(f"Unticked {cnt.get('dropped', 0)} false alarm(s), added {cnt.get('added', 0)} "
                  "missed item(s)" + (f", {cnt['words']} line(s) now mute just the bad word"
                                      if cnt.get("words") else "") +
                  ". The Found tab is updated.", "note")
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
        self._chat_ji = max(0, self.chat_job.current())
        self.chat_entry.delete(0, "end")
        self._send_chat(good[self._chat_ji], qtext, "You: " + qtext)

    def _send_chat(self, job, question, shown, box=None):
        """Send one message to Claude/ChatGPT; its changes are made when it answers."""
        if getattr(self, "chat_btn", None) is not None and self.chat_btn.winfo_exists():
            self.chat_btn.config(state="disabled")
        self._log(shown, "you")
        cc.use(self.review_ai)
        self._log(f"{AI_NAME} is reading the dialogue\u2026", "note")
        st = job["analysis"]
        self._sync_job(job)

        def go():
            try:
                notes = learn.notes(st.get("show", "_movies"), engine.title_name(st.get("path")))
                reply, acts, items, sid = cc.chat(
                    question, st, self.chat_sessions.get(job["_ji"]), notes,
                    look=lambda a, b: engine.chat_sheets(st.get("path"), job["work"], a, b),
                    say=lambda text: self.q.put(("call", lambda: self._log(text, "note"))))
                self.chat_sessions[job["_ji"]] = sid
                self.q.put(("chat_reply", job, reply, acts, items, None, box))
            except Exception as ex:
                save_details(traceback.format_exc())
                self.q.put(("chat_reply", job, "", {}, {}, plain_error(ex), box))
        threading.Thread(target=go, daemon=True).start()

    # --- the CleanListen way of editing: text you can highlight, ask right under the item
    def _sel_text(self, parent, text, width_chars=95, max_lines=6, bg=None, fg=None):
        """Read-only text you can highlight with the mouse (to point Claude at part of it)."""
        t = tk.Text(parent, wrap="word", width=20, font=(FONT, 10), bg=bg or SHADE,
                    fg=fg or INK, relief="flat",
                    padx=8, pady=4, borderwidth=0, highlightthickness=0,
                    height=max(1, min(max_lines, 1 + len(text) // width_chars)))
        t.insert("1.0", text)
        t.configure(state="disabled")
        return t

    def _fit_text(self, label, box, margin=0):
        """Wrap a label's words to the room its box really has, and again whenever that
        changes. The answer under a scene, line or word was wrapped at a set width; where the
        box was narrower than that (the lines card, a narrower window, bigger text on a small
        screen) the words ran off both sides (the owner, 2026-11-13: "the box that opens on
        the response is clipping off on both left and right. i cant see the full response")."""
        def fit(_e=None):
            try:
                if not (label.winfo_exists() and box.winfo_exists()):
                    return
                room = box.winfo_width() - margin
                if room > 60 and abs(int(str(label.cget("wraplength"))) - room) > 2:
                    label.config(wraplength=room)
            except (tk.TclError, ValueError):
                pass
        box.bind("<Configure>", fit, add="+")
        label.after_idle(fit)

    def _answer_box(self, parent, it):
        if it.get("chat_answer"):
            said = tk.Label(parent, text=f"{AI_NAME}: " + it["chat_answer"], bg=TINT,
                            fg=ACCENT_DK, font=(FONT, 9), wraplength=wrap_width(680),
                            justify="left", padx=8, pady=4, anchor="w")
            said.pack(fill="x", pady=(6, 0))
            self._fit_text(said, said, margin=20)       # its own width, less its padding

    def _ask_link(self, parent, job, kind, it, txt=None, text=None, **pack):
        if not getattr(self, "_ai_ok", False):
            return
        lbl = tk.Label(parent, text=text or f"Ask {AI_NAME} about this\u2026", bg=parent.cget("bg"),
                       fg=ACCENT, font=(FONT, 9, "underline"), cursor="hand2")
        lbl.bind("<Button-1>", lambda e: self._ask_inline(parent if kind != "word" else
                                                          parent.master, job, kind, it, txt, lbl))
        lbl.pack(**pack)

    def _ask_inline(self, holder, job, kind, it, txt, link):
        """A small box right under that scene, line or word: type what you want and the list
        changes as soon as it answers. Highlight part of the text first to point at it."""
        if getattr(link, "_open", False):
            return
        link._open = True
        t = engine.cl.fmt_t
        box = tk.Frame(holder, bg=TINT, padx=8, pady=6)
        box.pack(fill="x", pady=(4, 0))
        hint = "Tip: highlight part of the text above first to point at it. " if txt is not None else ""
        tip = tk.Label(box, text=hint + "e.g. \u201ckeep this\u201d, \u201cjust mute that "
                       "word\u201d, \u201ccut a bit more after it\u201d, \u201cwhy was this "
                       "flagged?\u201d", bg=TINT, fg=MUTED, font=(FONT, 8),
                       wraplength=wrap_width(640), justify="left", anchor="w")
        tip.pack(anchor="w")
        self._fit_text(tip, box, margin=20)             # the box's width, less its padding
        row = tk.Frame(box, bg=TINT)
        row.pack(fill="x", pady=(2, 0))
        entry = ttk.Entry(row)
        entry.pack(side="left", fill="x", expand=True)
        box.reply = tk.Label(box, text="", bg=TINT, fg=ACCENT_DK, font=(FONT, 9),
                             wraplength=wrap_width(640), justify="left", anchor="w")
        self._fit_text(box.reply, box, margin=20)
        box.item = it
        ref = self._item_ref(job, it)
        if kind == "scene":
            focus = (f"They picked {ref or 'a scene'}: the scene from {t(it['s'])} to {t(it['e'])} "
                     f"({', '.join(it.get('kind', []))}).")
            head = f"the scene at {t(it['s'])}"
        elif kind == "line":
            focus = (f"They picked {ref or 'a line'}: the line at {t(it['s'])}, "
                     f"\"{it.get('plain') or it['text']}\"" +
                     (f" (dialogue line {it['idx'] + 1})." if "idx" in it else "."))
            head = f"the line at {t(it['s'])}"
        else:
            focus = (f"They picked {ref or 'a word'}: the word \"{it.get('raw') or it['word']}\" "
                     f"at {t(it['s'])}, after \"{it.get('ctx', '')}\".")
            head = f"the word at {t(it['s'])}"

        def send(_e=None):
            q = entry.get().strip()
            if not q:
                return
            picked = ""
            if txt is not None:
                try:
                    picked = txt.get("sel.first", "sel.last").strip()
                except tk.TclError:
                    picked = ""
            entry.delete(0, "end")
            btn.config(state="disabled")
            box.reply.config(text=f"{AI_NAME} is reading\u2026", fg=MUTED)
            box.reply.pack(anchor="w", pady=(4, 0))
            self._send_chat(job, focus + (f" They highlighted: \"{picked}\"." if picked else "") +
                            f" They say: {q}", f"You (about {head}): {q}", box=box)
        btn = ttk.Button(row, text="Send", style="Small.TButton", command=send)
        btn.pack(side="left", padx=(6, 0))
        box.send_btn = btn
        entry.bind("<Return>", send)
        entry.focus_set()

    # --- ask about one scene, line, word, or the lines picked in All dialogue
    def _item_ref(self, job, it):
        items, _ = cc.candidates(job["analysis"])
        for i, (_, x) in items.items():
            if x is it:
                return i
        return None

    def _ask_about(self, job, kind, it=None, rows=None):
        t = engine.cl.fmt_t
        st = job["analysis"]
        if kind == "scene":
            title = (f"The scene at {t(it['s'])}\u2013{t(it['e'])} ({', '.join(it.get('kind', []))})"
                     f"\nSaid: {(it.get('said') or '(no talking)')[:200]}")
            focus = (f"They picked {self._item_ref(job, it) or 'a scene'}: the scene from "
                     f"{t(it['s'])} to {t(it['e'])} ({', '.join(it.get('kind', []))}).")
        elif kind == "line":
            txt = it.get("plain") or it["text"]
            title = f"The line at {t(it['s'])}:\n\u201c{txt[:220]}\u201d"
            focus = (f"They picked {self._item_ref(job, it) or 'a line'}: the line at "
                     f"{t(it['s'])}, \"{txt}\"" +
                     (f" (dialogue line {it['idx'] + 1})." if "idx" in it else "."))
        elif kind == "word":
            raw = it.get("raw") or it["word"]
            title = f"The word \u201c{it['word']}\u201d at {t(it['s'])}\n\u2026{it.get('ctx', '')}"
            focus = (f"They picked {self._item_ref(job, it) or 'a word'}: the word \"{raw}\" at "
                     f"{t(it['s'])}, after \"{it.get('ctx', '')}\".")
        else:
            d = st["dialogue"]
            a, b = min(rows), max(rows)
            said = " ".join(l["text"] for l in d[a:b + 1])
            title = f"Lines {t(d[a]['s'])}\u2013{t(d[b]['e'])}:\n\u201c{said[:260]}\u201d"
            focus = (f"They picked dialogue lines {a + 1} to {b + 1} ({t(d[a]['s'])} to "
                     f"{t(d[b]['e'])}).")
        win = tk.Toplevel(self)
        win.title(f"Ask {AI_NAME}")
        win.configure(bg=BG)
        win.transient(self)
        win.geometry("+%d+%d" % (self.winfo_rootx() + 120, self.winfo_rooty() + 160))
        tk.Label(win, text=title, bg=BG, fg=INK, font=(FONT, 10), wraplength=wrap_width(520),
                 justify="left").pack(anchor="w", padx=14, pady=(12, 6))
        tk.Label(win, text=f"What should {AI_NAME} do? (e.g. \u201ckeep this\u201d, \u201cjust mute "
                 "the word\u201d, \u201ccut a bit more after it\u201d, \u201cwhy was this flagged?\u201d)",
                 bg=BG, fg=MUTED, font=(FONT, 9), wraplength=wrap_width(520),
                 justify="left").pack(anchor="w", padx=14)
        row = tk.Frame(win, bg=BG)
        row.pack(fill="x", padx=14, pady=8)
        ent = ttk.Entry(row, width=60)
        ent.pack(side="left", fill="x", expand=True)
        ent.focus_set()
        win.reply = tk.Label(win, text="", bg=BG, fg=INK, font=(FONT, 10), wraplength=wrap_width(520),
                             justify="left")
        win.reply.pack(anchor="w", padx=14, pady=(0, 12))

        def send(_=None):
            q = ent.get().strip()
            if not q:
                return
            ent.delete(0, "end")
            win.reply.config(text=f"{AI_NAME} is thinking\u2026", fg=MUTED)
            btn.config(state="disabled")
            head = title.splitlines()[0].rstrip(":")
            self._send_chat(job, f"{focus} They say: {q}",
                            f"You (about {head[:1].lower() + head[1:]}): {q}", box=win)
        btn = ttk.Button(row, text="Send", style="Small.TButton", command=send)
        btn.pack(side="left", padx=(6, 0))
        win.send_btn = btn
        ent.bind("<Return>", send)

    def _chat_reply(self, job, reply, acts, items, err, box=None):
        def to_box(text, fg=INK):
            if box is not None and getattr(box, "item", None) is not None and not err:
                box.item["chat_answer"] = text      # stays on that card
            if box is not None and box.winfo_exists():
                box.reply.config(text=text, fg=fg)
                box.send_btn.config(state="normal")
        if not getattr(self, "chat_log", None) or not self.chat_log.winfo_exists():
            to_box("\u26a0 " + (err or reply), MUTED)
            return
        self.chat_btn.config(state="normal")
        self.chat_history = [h for h in self.chat_history if "reading the dialogue" not in h[0]]
        log = self.chat_log
        log.configure(state="normal")
        rng = log.tag_ranges("note")
        if rng and "reading the dialogue" in log.get(rng[-2], rng[-1]):
            log.delete(rng[-2], rng[-1])          # drop the "reading…" note
        log.configure(state="disabled")
        if err:
            self._log("\u26a0 " + err, "note")
            to_box("\u26a0 " + err, MUTED)
            return
        self._log(f"{AI_NAME}: " + reply)
        st = job["analysis"]
        for note, everywhere in acts.get("remember", []):   # kept for later checks (Jason)
            if learn.add_note(st.get("show", "_movies"), note,
                              engine.title_name(st.get("path")), everywhere):
                self._log("\u2713 CleanView will remember" +
                          (" for everything you clean" if everywhere else "") + ": " + note,
                          "note")
        if not any(acts.get(k) for k in ("tick", "untick", "mute_lines", "mute_words",
                                         "cut_scenes", "cut_times")):
            to_box(reply)
            return
        self._sync_job(job)                       # anything clicked while it was thinking
        snapshot = copy.deepcopy(job["analysis"])
        done = engine.apply_chat(job["analysis"], items, acts, job["work"])
        if done:
            self.undo_stack.append((job, snapshot))
            self._log("\u2713 Changed on the list: " + "; ".join(done) + ".", "note")
        else:
            self._log("Nothing on the list changed.", "note")
        to_box(reply + ("\n\n\u2713 Changed: " + "; ".join(done) + "." if done else ""))
        tab = 2
        try:
            tab = self._nb.index("current") if box is not None else 2
        except Exception:
            pass
        self.show_review(tab=tab)
        self._save_session()

    def _undo_chat(self):
        if not self.undo_stack:
            return
        job, snapshot = self.undo_stack.pop()
        job["analysis"] = snapshot
        self._log("\u21b6 Undid the last change from the chat.", "note")
        self.show_review(tab=2)
        self._save_session()

    def _words_card(self, parent, job, mutes):
        card = self._round_card(parent)
        tk.Label(card, text="Words to mute", bg=CARD, fg=INK, font=(HEAD, 11)).pack(
            anchor="w", pady=(0, 4))
        heard = job["analysis"].get("asr") or []
        for n, m in enumerate(mutes):
            v = tk.BooleanVar(value=not m.get("keep"))
            m["_shown"] = v.get()
            self.word_vars.append((v, job, m))
            wrap = tk.Frame(card, bg=CARD if n % 2 == 0 else SHADE, padx=4, pady=2)
            wrap.pack(fill="x")
            row = tk.Frame(wrap, bg=wrap.cget("bg"))
            row.pack(fill="x")
            rbg = row.cget("bg")
            ttk.Checkbutton(row, text=engine.cl.fmt_t(m["s"]), variable=v).pack(side="left")
            after = " ".join(w[0] for w in heard if m["e"] < w[1] < m["e"] + 4)[:60]
            show = tk.Label(row, text="Show", bg=rbg, fg=ACCENT, font=(FONT, 9, "underline"),
                            cursor="hand2", padx=6)
            show.pack(side="right")
            self._ask_link(row, job, "word", m, text="Ask", side="right", padx=4)
            note, col = claude_note(m, v.get())
            if note and m["claude"]["decision"] != "remove":
                tk.Label(row, text=note, bg=rbg, fg=col, font=(FONT, 8), wraplength=wrap_width(220),
                         justify="left").pack(side="right", padx=4)
            elif m.get("sub") and not note:      # offered unticked: probably misheard
                tk.Label(row, text=f"Maybe misheard: the subtitles have “{m['sub']}” "
                         "here", bg=rbg, fg=MUTED, font=(FONT, 8), wraplength=wrap_width(220),
                         justify="left").pack(side="right", padx=4)
            line = tk.Text(row, wrap="word", width=20, height=1, font=(FONT, 10), bg=rbg,
                           fg=MUTED, relief="flat", borderwidth=0, highlightthickness=0,
                           cursor="arrow")
            line.tag_configure("w", background=WORD_BG, foreground=WORD_INK,
                               font=(FONT, 10, "bold"))

            def fill(t=line, m=m, after=after, revealed=False):
                before = m.get("ctx", "")
                word = (m.get("raw") or m["word"]) if revealed else m["word"]
                t.configure(state="normal")
                t.delete("1.0", "end")
                if before:
                    t.insert("end", "\u2026" + before + " ")
                t.insert("end", f" {word} ", "w")
                if after:
                    t.insert("end", " " + after + "\u2026")
                t.configure(state="disabled", height=1 if len(before) + len(after) < 70 else 2)

            def toggle(_e=None, t=line, lbl=show, fill=fill, state={"on": False}):
                state["on"] = not state["on"]
                fill(t, revealed=state["on"])
                lbl.configure(text="Hide" if state["on"] else "Show")
            show.bind("<Button-1>", toggle)
            fill()
            line.pack(side="left", fill="x", expand=True, padx=(6, 0))
            self._answer_box(wrap, m)

    def _music_card(self, parent, job, quiet):
        """Loud hard rock, metal or rap with nobody talking: ticked ones are turned down."""
        card = self._round_card(parent)
        tk.Label(card, text="Loud music to turn down", bg=CARD, fg=INK,
                 font=(HEAD, 11)).pack(anchor="w")
        tk.Label(card, text="Ticked music plays at a quarter of its volume, only where nobody is "
                 "talking. Use Preview to listen, and untick anything that's fine.", bg=CARD,
                 fg=MUTED, font=(FONT, 9), wraplength=wrap_width(640), justify="left").pack(
            anchor="w", pady=(0, 4))
        for q in quiet:
            row = tk.Frame(card, bg=CARD)
            row.pack(fill="x", pady=2)
            v = tk.BooleanVar(value=q.get("lower", True))
            q["_shown"] = v.get()
            self.quiet_vars.append((v, job, q))
            ttk.Checkbutton(row, text=f"Turn down   ·   {engine.cl.fmt_t(q['s'])}   ·   "
                            f"{q['e'] - q['s']:.0f} sec", variable=v).pack(side="left")
            kind = q.get("kind", "Loud music")
            look.chip(row, kind, chip_color(kind)).pack(side="left", padx=(10, 0))
            ttk.Button(row, text="Preview ▸", style="Small.TButton",
                       command=lambda q=q: self.preview(job, q)).pack(side="right")

    def _lines_card(self, parent, job, lines):
        card = self._round_card(parent)
        tk.Label(card, text="Lines to mute", bg=CARD, fg=INK, font=(HEAD, 11)).pack(
            anchor="w", pady=(0, 4))
        for l in lines:
            row = tk.Frame(card, bg=CARD)
            row.pack(fill="x", pady=2)
            v = tk.BooleanVar(value=l.get("mute", True))
            l["_shown"] = v.get()
            self.line_vars.append((v, job, l))
            ttk.Checkbutton(row, text=engine.cl.fmt_t(l["s"]), variable=v).pack(side="left", anchor="n")
            for t in l["types"]:
                name = f"Found by {AI_NAME}" if t == "claude" else engine.LINE_LABEL.get(t, t)
                look.chip(row, name, chip_color(name)).pack(side="left", padx=(8, 0),
                                                            anchor="n")
            txt = l["text"] if len(l["text"]) < 160 else l["text"][:157] + "\u2026"
            why_ = l.get("learned") or l.get("hint")
            if why_ and "learned" not in l["types"]:     # that chip already says so
                txt += f"   ({why_})"
            col_ = tk.Frame(row, bg=CARD)
            col_.pack(side="left", padx=(8, 0), fill="x", expand=True)
            tw = self._sel_text(col_, txt, width_chars=70, max_lines=4, bg=CARD, fg=MUTED)
            tw.pack(fill="x")
            note, col = claude_note(l, v.get())
            if note:
                tk.Label(col_, text=note, bg=CARD, fg=col, font=(FONT, 8), wraplength=wrap_width(440),
                         justify="left", anchor="w").pack(fill="x", padx=(8, 0))
            self._answer_box(col_, l)
            self._ask_link(col_, job, "line", l, tw, text="Ask", anchor="e")

    def _scene_card(self, parent, job, sc, top=False):
        kids = parent.pack_slaves()
        card = self._round_card(parent, before=kids[0] if top and kids else None)
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
            look.chip(top_row, k, chip_color(k), size=9).pack(side="left", padx=(10, 0))
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
                     wraplength=wrap_width(210), justify="left", anchor="w").pack(fill="x")
        note, col = claude_note(sc, v.get())
        if note:
            tk.Label(text, text=note, bg=CARD, fg=col, font=(FONT, 9, "bold"), wraplength=wrap_width(210),
                     justify="left", anchor="w").pack(fill="x", pady=(4, 0))
        said = sc.get("said") or ""
        txt = None
        if said:
            txt = self._sel_text(card, "Said: " + said, max_lines=5, fg=MUTED)
            txt.pack(fill="x", pady=(6, 0))
        self._answer_box(card, sc)
        self._ask_link(card, job, "scene", sc, txt, anchor="e", pady=(4, 0))

    def preview(self, job, sc):
        def go():
            try:
                self.q.put(("preview_ready", engine.make_preview(job["video"], sc["s"], sc["e"],
                                                                 job["work"])))
            except Exception as ex:
                save_details(traceback.format_exc())
                self.q.put(("preview_error", plain_error(ex)))
        threading.Thread(target=go, daemon=True).start()

    def _save_from_review(self):
        for j in self.jobs:
            j["cuts"], j["lines"], j["words"], j["quiet"] = [], [], [], []
        for v, j, m in self.word_vars:
            if v.get():
                j["words"].append(m)
        for v, j, q in self.quiet_vars:
            if v.get():
                j["quiet"].append(q)
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
        self._learn_choices()           # remember these choices for next time
        for j in good:                  # the final choices, for the "what we refined" export
            try:
                self._sync_job(j)
                (Path(j["work"]) / "analysis.json").write_text(json.dumps(j["analysis"], indent=1))
            except Exception:
                pass
        if not self._room_to_save():
            return
        self.outdir = self._save_folder()
        self.save()

    def save(self):
        self.cancel_flag = False
        todo = [j["video"] for j in self.jobs if j["analysis"]]
        self.show_working("Saving the clean cop" + ("ies…" if len(todo) > 1 else "y…"), todo)
        self._start_work(self._render_thread)

    # ---------- page 4: done ----------
    def show_done(self, results, keep_review=False):
        self.page_name = "done"
        if not keep_review:         # kept when some couldn't be saved, to try them again
            self._forget_session()
        multi = len(results) > 1
        p = self._new_page("All done!", f"Your clean cop{'ies are' if multi else 'y is'} ready.")
        stats = tk.Frame(p, bg=BG)
        stats.pack(fill="x", pady=20)
        cm = sum(r["cut_minutes"] for r in results)
        removed = (f"{cm:.0f}", "minutes removed") if cm >= 1 else (f"{cm * 60:.0f}", "seconds removed")
        for big, small in [(str(sum(r["mutes"] for r in results)), "words & lines muted"),
                           (str(sum(r["cuts"] for r in results)), "scenes cut"), removed]:
            stat = look.Card(stats, radius=16, pad=(18, 14), width=196)
            stat.pack(side="left", padx=(0, self._px(12)))
            tk.Label(stat.body, text=big, bg=CARD, fg=ACCENT, font=(HEAD, 26)).pack()
            tk.Label(stat.body, text=small, bg=CARD, fg=MUTED, font=(FONT, 10)).pack()
        tk.Label(p, text=f"Saved in:  {os.path.normpath(results[0]['folder'])}", bg=BG, fg=INK,
                 font=(FONT, 10), wraplength=wrap_width(740), justify="left").pack(anchor="w", pady=(4, 4))
        tk.Label(p, text="Each clean copy has “(Clean)” in its name. Its report, listing everything "
                 "that was muted or cut, is in the Reports folder inside.", bg=BG, fg=MUTED,
                 font=(FONT, 10), wraplength=wrap_width(740), justify="left").pack(anchor="w", pady=(0, 16))
        row = tk.Frame(p, bg=BG)
        row.pack(anchor="w")
        ttk.Button(row, text="Open folder", style="Go.TButton",
                   command=lambda: open_path(results[0]["folder"])).pack(side="left")
        if not multi:
            ttk.Button(row, text="Play it", style="Plain.TButton",
                       command=lambda: open_path(results[0]["out"])).pack(side="left", padx=12)
        self.again_btn = ttk.Button(self.footer, text="Clean another", style="Accent.TButton",
                                    command=self.reset)
        self.again_btn.pack(side="right")

        # what we refined, to send in so CleanView's built-in knowledge improves
        help_card = look.Card(p, fill=NOTE, edge=NOTE_EDGE, radius=14, pad=(6, 6))
        help_card.pack(fill="x", pady=(self._px(22), 0))
        box = help_card.body
        tk.Label(box, text="Help CleanView get better", bg=NOTE, fg=NOTE_INK,
                 font=(FONT, 10, "bold"), padx=12, pady=(8)).pack(anchor="w")
        tk.Label(box, text="Send in what was refined on this one (what was found, what the AI "
                 "said, what you changed and what you kept). It's added to the knowledge every "
                 "copy of CleanView starts with. No video or sound is in it.",
                 bg=NOTE, fg=INK, font=(FONT, 10), wraplength=wrap_width(700), justify="left",
                 padx=12).pack(anchor="w")
        ttk.Button(box, text="Send what we refined\u2026", style="Small.TButton",
                   command=self.export_refined).pack(anchor="w", padx=12, pady=(6, 10))
        self._done_jobs = [j for j in self.jobs if j["analysis"]]

    def _send_report_now(self):
        """From the review page, before saving: what was found and every tick as it is now."""
        good = [j for j in self.jobs if j["analysis"]]
        for j in good:
            self._sync_job(j)
        self.export_refined(good)

    def export_refined(self, jobs=None):
        if jobs is None:
            jobs = getattr(self, "_done_jobs", [])
        try:
            path = learn.export_refined([j["analysis"] for j in jobs],
                                        getattr(self, "chat_history", []))
        except Exception as ex:
            messagebox.showerror("CleanView", f"Couldn't save the file. {plain_error(ex)}")
            return
        self._send_in(path, "refined")

    def reset(self):
        self.videos, self.outdir, self.jobs = [], None, []
        self._setup_step = 1
        self.show_setup()


def _installed_copy():
    try:
        return Path(__file__).resolve().parent == (APP_DATA / "app").resolve()
    except OSError:
        return False


def _ollama_care(what):
    """Ollama (the AI on this PC) only while CleanView, CleanListen or CleanRead are open
    (Lauren, 2026-11-05): not started with Windows, and stopped once they've all closed. The
    installed copy only, so a test copy never changes the PC."""
    try:
        import ollama_care
        if _installed_copy():
            getattr(ollama_care, what)()
    except Exception:
        pass


if __name__ == "__main__":
    _ollama_care("autostart_off")
    App().mainloop()
    _ollama_care("stop_later")
