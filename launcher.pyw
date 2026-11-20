"""CleanView launcher: checks GitHub for a newer version, updates the
program files if there is one, then opens the app. If the check fails
(offline, GitHub down) the app simply opens as-is."""
import json
import os
import runpy
import sys
import tempfile
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
try:                    # {"repo": "...", "branch": "main"}; a missing or broken file
    CONFIG = json.loads((HERE / "update.json").read_text())   # mustn't stop CleanView opening
    CONFIG["repo"]          # (CleanListen 1.14.3: a fresh install had none)
except Exception:
    CONFIG = {"repo": "BookWorm824/cleanview", "branch": "main"}
RAW = f"https://raw.githubusercontent.com/{CONFIG['repo']}/{CONFIG.get('branch', 'main')}/"


def _ver(s):
    return tuple(int(x) for x in str(s).split(".") if x.isdigit())


# ---------- CleanView's own name in Task Manager ----------
# Task Manager names a program by its .exe's description, so CleanView showed as "Python"
# (the tester, 2026-11-03). CleanView.exe is a copy of the venv's base pythonw.exe in
# venv\CleanView, with python312.dll beside it and its description and icon changed; it
# finds the venv through venv\pyvenv.cfg one folder up, like Scripts\pythonw.exe does.
# (Not in Scripts: sherpa-onnx put an onnxruntime.dll there, which an .exe in that folder
# would load first.) CleanView-work.exe, from python.exe, runs the picture scan and pip.
# The changed .exe has no signature, so Smart App Control would block it: it's only made
# while that's off, and only used once a test run of it has worked.
APP_NAME = "CleanView"
OWN_EXE = APP_NAME + ".exe"
WORK_EXE = APP_NAME + "-work.exe"
OWN_BUILD = 1          # raise to make every copy again


def _smart_app_control_off():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"SYSTEM\CurrentControlSet\Control\CI\Policy") as k:
            return winreg.QueryValueEx(k, "VerifiedAndReputablePolicyState")[0] == 0
    except FileNotFoundError:
        return True        # Windows without Smart App Control
    except OSError:
        return False


def _unsign(path):
    """Drop the signature (now wrong) from the end of an .exe."""
    import struct
    data = bytearray(path.read_bytes())
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    opt = pe + 24
    dirs = opt + (112 if struct.unpack_from("<H", data, opt)[0] == 0x20B else 96)
    at, size = struct.unpack_from("<II", data, dirs + 4 * 8)
    if size and at + size <= len(data):
        del data[at:]
        struct.pack_into("<II", data, dirs + 4 * 8, 0, 0)
        path.write_bytes(bytes(data))


def _version_info(name):
    """A VS_VERSIONINFO resource whose description and product name are `name`."""
    import struct

    def pad(b):
        return b + b"\0" * (-len(b) % 4)

    def block(key, value=b"", children=(), text=True, value_len=None):
        body = pad(struct.pack("<HHH", 0, 0, 0) + (key + "\0").encode("utf-16-le"))
        body = pad(body + value) if children else body + value
        body += b"".join(pad(c) for c in children)
        if value_len is None:
            value_len = len(value) // 2 if text else len(value)
        return struct.pack("<HHH", len(body), value_len, int(text)) + body[6:]

    def string(key, val):
        return block(key, (val + "\0").encode("utf-16-le"))

    fixed = struct.pack("<13I", 0xFEEF04BD, 0x10000, 0x10000, 0, 0x10000, 0, 0x3F, 0,
                        0x40004, 1, 0, 0, 0)
    table = block("040904B0", children=[string(k, v) for k, v in (
        ("CompanyName", name), ("FileDescription", name), ("FileVersion", "1.0.0.0"),
        ("InternalName", name), ("OriginalFilename", name + ".exe"),
        ("ProductName", name), ("ProductVersion", "1.0.0.0"))])
    var = block("VarFileInfo", children=[
        block("Translation", struct.pack("<HH", 0x0409, 0x04B0), text=False)])
    return block("VS_VERSION_INFO", fixed, [block("StringFileInfo", children=[table]), var],
                 text=False)


def _rename_exe(path, name, icon):
    """Give an .exe the description `name` and the icons from the .ico file `icon`."""
    import ctypes
    import struct
    from ctypes import wintypes
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.LoadLibraryExW.restype = wintypes.HMODULE
    k32.LoadLibraryExW.argtypes = (wintypes.LPCWSTR, wintypes.HANDLE, wintypes.DWORD)
    k32.FreeLibrary.argtypes = (wintypes.HMODULE,)
    k32.BeginUpdateResourceW.restype = wintypes.HANDLE
    k32.BeginUpdateResourceW.argtypes = (wintypes.LPCWSTR, wintypes.BOOL)
    k32.UpdateResourceW.argtypes = (wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                    wintypes.WORD, ctypes.c_void_p, wintypes.DWORD)
    k32.EndUpdateResourceW.argtypes = (wintypes.HANDLE, wintypes.BOOL)
    names_cb = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMODULE, ctypes.c_void_p,
                                  ctypes.c_void_p, ctypes.c_void_p)
    langs_cb = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMODULE, ctypes.c_void_p,
                                  ctypes.c_void_p, wintypes.WORD, ctypes.c_void_p)
    k32.EnumResourceNamesW.argtypes = (wintypes.HMODULE, ctypes.c_void_p, names_cb,
                                       ctypes.c_void_p)
    k32.EnumResourceLanguagesW.argtypes = (wintypes.HMODULE, ctypes.c_void_p, ctypes.c_void_p,
                                           langs_cb, ctypes.c_void_p)
    RT_ICON, RT_GROUP_ICON, RT_VERSION = 3, 14, 16

    def res_id(p):        # a number, or a name (kept as a string)
        return p if p < 0x10000 else ctypes.wstring_at(p)

    def as_arg(v, keep):
        if isinstance(v, int):
            return ctypes.c_void_p(v)
        buf = ctypes.create_unicode_buffer(v)
        keep.append(buf)
        return ctypes.cast(buf, ctypes.c_void_p)

    old = []              # (type, name, language) of every icon and version resource
    mod = k32.LoadLibraryExW(str(path), None, 0x2)      # LOAD_LIBRARY_AS_DATAFILE
    if not mod:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        for rt in (RT_ICON, RT_GROUP_ICON, RT_VERSION):
            found = []
            k32.EnumResourceNamesW(mod, rt, names_cb(
                lambda m, t, n, p: found.append(res_id(n)) or True), None)
            for n in found:
                keep = []
                k32.EnumResourceLanguagesW(mod, rt, as_arg(n, keep), langs_cb(
                    lambda m, t, nn, lang, p, n=n: old.append((rt, n, lang)) or True), None)
    finally:
        k32.FreeLibrary(mod)

    ico = Path(icon).read_bytes()
    count = struct.unpack_from("<H", ico, 4)[0]
    images, group = [], struct.pack("<HHH", 0, 1, count)
    for i in range(count):
        w, h, colors, _, planes, bits, size, at = struct.unpack_from("<BBBBHHII", ico, 6 + 16 * i)
        images.append(ico[at:at + size])
        group += struct.pack("<BBBBHHIH", w, h, colors, 0, planes, bits, size, i + 1)
    new = [(RT_ICON, i + 1, img) for i, img in enumerate(images)]
    new += [(RT_GROUP_ICON, 1, group), (RT_VERSION, 1, _version_info(name))]

    h = k32.BeginUpdateResourceW(str(path), False)
    if not h:
        raise ctypes.WinError(ctypes.get_last_error())
    keep = []
    try:
        for rt, n, lang in old:
            if not k32.UpdateResourceW(h, rt, as_arg(n, keep), lang, None, 0):
                raise ctypes.WinError(ctypes.get_last_error())
        for rt, n, data in new:
            buf = ctypes.create_string_buffer(data, len(data))
            keep.append(buf)
            if not k32.UpdateResourceW(h, rt, n, 0x0409, buf, len(data)):
                raise ctypes.WinError(ctypes.get_last_error())
    except BaseException:
        k32.EndUpdateResourceW(h, True)
        raise
    if not k32.EndUpdateResourceW(h, False):
        raise ctypes.WinError(ctypes.get_last_error())


def _icon_mark(icon):
    import hashlib
    return hashlib.sha1(Path(icon).read_bytes()).hexdigest()[:12]


def _new_icon_on_exes(folder, icon):
    """A new cleanview.ico (1.18.107, the slight 3D look: the owner, 2026-11-15, "fix new logo
    in app screen and on desktops"): give the .exes made before it the new icon, once. Each is
    changed as a copy that then takes its place, so one in use (or a failure) leaves it as it
    was, to be tried again next time."""
    mark = folder / "icon.txt"
    try:
        h = _icon_mark(icon)
        if mark.read_text(encoding="utf8").strip() == h:
            return
    except OSError:
        pass
    try:
        for exe in (OWN_EXE, WORK_EXE):
            tmp = folder / (exe + ".new")
            import shutil
            shutil.copy2(folder / exe, tmp)
            try:
                _rename_exe(tmp, APP_NAME, icon)
                os.replace(tmp, folder / exe)
            finally:
                tmp.unlink(missing_ok=True)
        mark.write_text(h, encoding="utf8")
    except Exception:
        pass


def make_own_exe(folder=None, base=None, icon=None):
    """CleanView.exe (and CleanView-work.exe) in `folder` (venv\\CleanView), made once and
    tried out. Returns its path, or None to keep using pythonw.exe."""
    import shutil
    import subprocess
    if os.name != "nt" or (folder is None and sys.prefix == sys.base_prefix):
        return None
    folder = Path(folder or Path(sys.prefix) / APP_NAME)
    base = Path(base or sys.base_prefix)
    icon = Path(icon or HERE / "cleanview.ico")
    try:
        st = (base / "pythonw.exe").stat()
        stamp = f"{OWN_BUILD} {base} {st.st_size} {int(st.st_mtime)}"
    except OSError:
        return None
    done, failed = folder / "made.txt", folder / "failed.txt"
    for f in (done, failed):
        try:
            if f.read_text(encoding="utf8").splitlines()[0] == stamp:
                if f is done:
                    _new_icon_on_exes(folder, icon)
                return folder / OWN_EXE if f is done else None
        except (OSError, IndexError):
            pass
    try:
        shutil.rmtree(folder, ignore_errors=True)
        folder.mkdir(parents=True, exist_ok=True)
        for dll in base.glob("*.dll"):          # python312.dll, python3.dll, vcruntime140...
            shutil.copy2(dll, folder / dll.name)
        for src, dst in (("pythonw.exe", OWN_EXE), ("python.exe", WORK_EXE)):
            shutil.copy2(base / src, folder / dst)
            _unsign(folder / dst)
            _rename_exe(folder / dst, APP_NAME, icon)
        out = folder / "tried.txt"
        for exe in (OWN_EXE, WORK_EXE):
            out.unlink(missing_ok=True)
            subprocess.run([str(folder / exe), "-c",
                            "import sys, tkinter; open(sys.argv[1], 'w').write(sys.prefix)",
                            str(out)], timeout=120, creationflags=0x08000000,
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
            if Path(out.read_text(encoding="utf8")).resolve() != folder.parent.resolve():
                raise RuntimeError(f"{exe} used {out.read_text(encoding='utf8')}")
        out.unlink(missing_ok=True)
        done.write_text(stamp, encoding="utf8")
        try:
            (folder / "icon.txt").write_text(_icon_mark(icon), encoding="utf8")
        except OSError:
            pass
        return folder / OWN_EXE
    except Exception as ex:
        try:
            folder.mkdir(parents=True, exist_ok=True)
            failed.write_text(f"{stamp}\n{type(ex).__name__}: {ex}", encoding="utf8")
        except OSError:
            pass
        return None


def as_own_exe():
    """Start this launcher again as CleanView.exe. True if that started."""
    import subprocess
    if (os.name != "nt" or Path(sys.executable).name.lower() == OWN_EXE.lower()
            or not _smart_app_control_off()):
        return False
    exe = make_own_exe()
    if not exe:
        return False
    try:
        subprocess.Popen([str(exe), str(Path(__file__).resolve())] + sys.argv[1:],
                         cwd=str(HERE))
        return True
    except OSError as ex:      # blocked after all: don't try again
        try:
            (exe.parent / "failed.txt").write_text(
                (exe.parent / "made.txt").read_text(encoding="utf8") + f"\n{ex}",
                encoding="utf8")
        except OSError:
            pass
        return False


# ---------- one CleanView at a time, and a window straight away ----------
# The owner, 2026-11-12: "it can take several second and gives no indication it is opening. so
# i click again and get multiple windows open. I only want there to be a single instance".
# The part started from the Start menu (clicked) shows "Opening CleanView..." at once and
# starts CleanView itself as its own process (run_app, "--app"); that one holds ONE_NAME for
# as long as it runs. A click while it's open, or while it's opening (OPENING_NAME), brings
# that window forward instead. "Update now" starts a new one while the old one closes: it
# waits for the old one to let go (RESTART_WAIT).
APP_PART = "--app"
ONE_NAME = os.environ.get("CLEANVIEW_ONE_NAME") or "Local\\CleanView-open"
OPENING_NAME = ONE_NAME + "-opening"
RESTART_WAIT = 90
SPLASH_MOST = 180             # seconds; the window says "Opening" at most this long
# ... and "Updating" as long as the update takes: it gives up by itself after UPDATE_MOST and
# CleanView opens as it is (the owner, 2026-11-17: after an update the box "just sits", closed
# and clicked again "the cursor has a blue spinner", "if its just giving it more time it needs
# to update lets fix the initial little box to let people know to wait")
UPDATING_MOST = 600
UPDATE_MOST = 120             # seconds for all of an update's files, else it waits for next time
UPDATE_AT_ONCE = 6            # files fetched at a time
UPDATING = "Updating"         # how the opening note starts while an update is fetched
APP_DATA = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / APP_NAME
OPENING_NOTE = APP_DATA / "opening.txt"     # what the opening window says (run_app writes it)
PID_FILE = APP_DATA / "open_pid.txt"         # which process is CleanView, to bring it forward
_held = []                    # mutexes this process holds until it ends


def _restarting():
    # "Update now" starts CleanView again with these set (CLEANVIEW_UPDATED since 1.10)
    return bool(os.environ.get("CLEANVIEW_RESTART") or os.environ.get("CLEANVIEW_UPDATED"))


def _kernel32():
    import ctypes
    from ctypes import wintypes
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.CreateMutexW.restype = wintypes.HANDLE
    k.CreateMutexW.argtypes = (ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR)
    k.OpenMutexW.restype = wintypes.HANDLE
    k.OpenMutexW.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR)
    k.WaitForSingleObject.restype = wintypes.DWORD
    k.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    k.CloseHandle.argtypes = (wintypes.HANDLE,)
    return k


def hold(name, wait=0.0):
    """Take the named lock for as long as this process runs. False if another process has
    it (after waiting up to `wait` seconds for it to be let go). Not knowing never stops
    CleanView opening."""
    if os.name != "nt":
        return True
    try:
        k = _kernel32()
        h = k.CreateMutexW(None, False, name)
        if not h:
            return True
        got = k.WaitForSingleObject(h, int(wait * 1000))
        if got in (0, 0x80):          # ours, or let go by a process that ended
            _held.append(h)
            return True
        k.CloseHandle(h)
        return False
    except Exception:
        return True


def exists(name):
    """Does some process hold (or wait on) the named lock?"""
    if os.name != "nt":
        return False
    try:
        k = _kernel32()
        h = k.OpenMutexW(0x00100000, False, name)        # SYNCHRONIZE
        if h:
            k.CloseHandle(h)
            return True
    except Exception:
        pass
    return False


def family(pid):
    """A process and every process it started, and they started (a venv's pythonw.exe starts
    the real Python as its own process, which then owns the window)."""
    import ctypes
    from ctypes import wintypes

    class Entry(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                    ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.c_void_p),
                    ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                    ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", ctypes.c_long),
                    ("dwFlags", wintypes.DWORD), ("szExeFile", ctypes.c_wchar * 260)]
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    k.CreateToolhelp32Snapshot.argtypes = (wintypes.DWORD, wintypes.DWORD)
    k.Process32FirstW.argtypes = k.Process32NextW.argtypes = (wintypes.HANDLE, ctypes.c_void_p)
    k.CloseHandle.argtypes = (wintypes.HANDLE,)
    snap = k.CreateToolhelp32Snapshot(0x2, 0)              # TH32CS_SNAPPROCESS
    parents = {}
    if snap and snap != ctypes.c_void_p(-1).value:
        e = Entry()
        e.dwSize = ctypes.sizeof(Entry)
        ok = k.Process32FirstW(snap, ctypes.byref(e))
        while ok:
            parents[e.th32ProcessID] = e.th32ParentProcessID
            ok = k.Process32NextW(snap, ctypes.byref(e))
        k.CloseHandle(snap)
    out, grew = {pid}, True
    while grew:
        more = {c for c, par in parents.items() if par in out and c not in out and c != par}
        grew = bool(more)
        out |= more
    return out


def windows_of(pid=None, title=None):
    """The visible top-level windows of a process and the ones it started (or, with title,
    of any other process whose Tk window's title starts with it)."""
    if os.name != "nt":
        return []
    import ctypes
    from ctypes import wintypes
    u = ctypes.WinDLL("user32", use_last_error=True)
    found = []
    each = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    pids = family(pid) if pid is not None else set()

    def look(hwnd, _):
        if not u.IsWindowVisible(hwnd):
            return True
        owner = wintypes.DWORD()
        u.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value in pids:
            found.append(hwnd)
        elif title is not None and owner.value != os.getpid():
            cls = ctypes.create_unicode_buffer(64)
            u.GetClassNameW(hwnd, cls, 64)
            text = ctypes.create_unicode_buffer(256)
            u.GetWindowTextW(hwnd, text, 256)
            if cls.value == "TkTopLevel" and text.value.startswith(title):
                found.append(hwnd)
        return True
    u.EnumWindows(each(look), 0)
    return found


def bring_forward():
    """Bring the CleanView that's already open (or opening) to the front. True if found."""
    if os.name != "nt":
        return False
    import ctypes
    u = ctypes.WinDLL("user32", use_last_error=True)
    try:
        pid = int(PID_FILE.read_text(encoding="utf8").strip())
    except (OSError, ValueError):
        pid = None
    wins = (windows_of(pid) if pid else []) or windows_of(title=APP_NAME)
    for hwnd in wins[:1]:
        if u.IsIconic(hwnd):
            u.ShowWindow(hwnd, 9)                          # SW_RESTORE
        u.SetForegroundWindow(hwnd)
        return True
    return False


def opening(text):
    """What the "Opening CleanView..." window says now."""
    try:
        APP_DATA.mkdir(parents=True, exist_ok=True)
        OPENING_NOTE.write_text(text, encoding="utf8")
    except OSError:
        pass


def start_app():
    """Start CleanView as its own process: as CleanView.exe where it can be (its name in Task
    Manager), else this Python. None if neither started."""
    import subprocess
    exe = None
    try:
        if (os.name == "nt" and Path(sys.executable).name.lower() != OWN_EXE.lower()
                and _smart_app_control_off()):
            exe = make_own_exe()
    except Exception:          # never block the app over its name
        exe = None
    for prog in ([str(exe)] if exe else []) + [sys.executable]:
        try:
            return subprocess.Popen([prog, str(Path(__file__).resolve()), APP_PART]
                                    + sys.argv[1:], cwd=str(HERE))
        except OSError as ex:
            if exe and prog == str(exe):     # blocked after all: don't try it again
                try:
                    (exe.parent / "failed.txt").write_text(
                        (exe.parent / "made.txt").read_text(encoding="utf8") + f"\n{ex}",
                        encoding="utf8")
                except OSError:
                    pass
    return None


class Running:
    """A process already started (by an earlier click), for `splash`: its pid and whether it
    has ended (poll() None while it runs, as subprocess.Popen's)."""

    def __init__(self, pid):
        self.pid = pid

    def poll(self):
        if os.name != "nt":
            return None
        try:
            import ctypes
            from ctypes import wintypes
            k = ctypes.WinDLL("kernel32", use_last_error=True)
            k.OpenProcess.restype = wintypes.HANDLE
            h = k.OpenProcess(0x1000, False, int(self.pid))   # PROCESS_QUERY_LIMITED_INFORMATION
            if not h:
                return 1
            code = wintypes.DWORD()
            ok = k.GetExitCodeProcess(h, ctypes.byref(code))
            k.CloseHandle(h)
            return None if ok and code.value == 259 else (code.value or 1)   # 259: STILL_ACTIVE
        except Exception:
            return 1


def still_opening():
    """The CleanView an earlier click started, while it hasn't got its window up yet (still
    updating or opening), as a `Running`; else None."""
    try:
        pid = int(PID_FILE.read_text(encoding="utf8").strip())
    except (OSError, ValueError):
        return None
    proc = Running(pid)
    if proc.poll() is not None or pid == os.getpid():
        return None
    return proc


def splash(child, most=SPLASH_MOST):
    """A small "Opening CleanView..." window until CleanView's own window is up (or it has
    stopped, or `most` seconds; while an update is fetched, `UPDATING_MOST`). The update says
    how far it's got ("Updating CleanView to 1.18.128... (5 of 21)") and that it opens by
    itself."""
    import time
    import tkinter as tk
    from tkinter import ttk
    root = tk.Tk()
    root.title(APP_NAME)
    try:                # the logo for every window of this program, and for this one
        root.iconbitmap(default=str(HERE / "cleanview.ico"))
        root.iconbitmap(str(HERE / "cleanview.ico"))
    except Exception:
        pass
    root.configure(bg="#FFFFFF")
    root.resizable(False, False)
    title = tk.StringVar(value=f"Opening {APP_NAME}\u2026")
    tk.Label(root, textvariable=title, bg="#FFFFFF", fg="#23211F",
             font=("Segoe UI", 14, "bold")).pack(padx=40, pady=(22, 4))
    said = tk.StringVar(value="This can take a few seconds.")
    tk.Label(root, textvariable=said, bg="#FFFFFF", fg="#6D6862",
             font=("Segoe UI", 10)).pack(padx=40)
    wait = tk.StringVar(value="")
    tk.Label(root, textvariable=wait, bg="#FFFFFF", fg="#2F6F62",
             font=("Segoe UI", 10, "bold"), wraplength=320).pack(padx=40, pady=(6, 0))
    bar = ttk.Progressbar(root, mode="indeterminate", length=260)
    bar.pack(padx=40, pady=(12, 22))
    bar.start(12)
    root.update_idletasks()
    w, h = root.winfo_reqwidth(), root.winfo_reqheight()
    root.geometry(f"+{(root.winfo_screenwidth() - w) // 2}+"
                  f"{(root.winfo_screenheight() - h) // 2 - 40}")
    start = time.time()
    try:                       # CleanView's window may come to the front itself
        import ctypes
        for p in family(child.pid):
            ctypes.WinDLL("user32").AllowSetForegroundWindow(p)
    except Exception:
        pass

    def check():
        wins = windows_of(child.pid)
        if wins:                # its window is up: hand it the front, then go
            try:
                import ctypes
                ctypes.WinDLL("user32").SetForegroundWindow(wins[0])
            except Exception:
                pass
        try:
            text = OPENING_NOTE.read_text(encoding="utf8").strip()
        except OSError:
            text = ""
        updating = text.startswith(UPDATING)
        if child.poll() is not None or wins or \
                time.time() - start > (UPDATING_MOST if updating else most):
            bar.stop()
            root.destroy()
            return
        if text and text != said.get():
            said.set(text)
            title.set(f"{UPDATING} {APP_NAME}\u2026" if updating else f"Opening {APP_NAME}\u2026")
            wait.set(f"Please wait: {APP_NAME} opens by itself when it's done." if updating
                     else "")
        root.after(200, check)
    root.after(200, check)
    root.mainloop()


LAUNCHER_CHANGED = False      # the update brought a new launcher.pyw

# ---------- The owner's seal on every update (1.18.147) ----------
# The code is public and every copy updates by itself, so whoever got into the GitHub account
# could have sent anything to everyone (the owner, 2026-11-19: "how safe is the code ... could
# someone use another ai chat to change it?", then "yes" to signed updates). Each release's
# version.json lists every file's SHA-256 ("sha256") and version.sig holds an Ed25519
# signature of version.json's exact bytes, made with the secret key kept only on the owner's
# PC and in her Google Drive (tools/sign_release.py). An update is installed only when the
# signature fits PUBLIC_KEY and every file it downloads has the hash listed; anything else is
# refused and CleanView opens as it is. Ed25519 is written out here (RFC 8032) because the
# updater can't install packages, and the launcher must never fail to open CleanView.
PUBLIC_KEY = bytes.fromhex("8cf7d7b15dc080a415e1d6d799ea5e5e7f5201d273ec6b4fca6f9504ed878cb5")
SEAL_FOR = APP_NAME + " update\n"        # signed in front of version.json: one app's seal
SIG_NAME = "version.sig"                 # isn't another's

_P = 2 ** 255 - 19
_L = 2 ** 252 + 27742317777372353535851937790883648493
_D = -121665 * pow(121666, _P - 2, _P) % _P
_SQRT_M1 = pow(2, (_P - 1) // 4, _P)


def _ed_add(a, b):
    x = (a[1] - a[0]) * (b[1] - b[0]) % _P
    y = (a[1] + a[0]) * (b[1] + b[0]) % _P
    c = 2 * a[3] * b[3] * _D % _P
    d = 2 * a[2] * b[2] % _P
    e, f, g, h = y - x, d - c, d + c, y + x
    return (e * f % _P, g * h % _P, f * g % _P, e * h % _P)


def _ed_mul(s, pt):
    out = (0, 1, 1, 0)
    while s > 0:
        if s & 1:
            out = _ed_add(out, pt)
        pt = _ed_add(pt, pt)
        s >>= 1
    return out


def _ed_x(y, sign):
    if y >= _P:
        return None
    x2 = (y * y - 1) * pow(_D * y * y + 1, _P - 2, _P) % _P
    if x2 == 0:
        return None if sign else 0
    x = pow(x2, (_P + 3) // 8, _P)
    if (x * x - x2) % _P:
        x = x * _SQRT_M1 % _P
    if (x * x - x2) % _P:
        return None
    if (x & 1) != sign:
        x = _P - x
    return x


def _ed_point(b):
    if len(b) != 32:
        return None
    y = int.from_bytes(b, "little")
    sign, y = y >> 255, y & ((1 << 255) - 1)
    x = _ed_x(y, sign)
    return None if x is None else (x, y, 1, x * y % _P)


def _ed_bytes(pt):
    zi = pow(pt[2], _P - 2, _P)
    x, y = pt[0] * zi % _P, pt[1] * zi % _P
    return (y | ((x & 1) << 255)).to_bytes(32, "little")


_GY = 4 * pow(5, _P - 2, _P) % _P
_G = (_ed_x(_GY, 0), _GY, 1, _ed_x(_GY, 0) * _GY % _P)


def _ed_hash(*parts):
    import hashlib
    return int.from_bytes(hashlib.sha512(b"".join(parts)).digest(), "little") % _L


def ed25519_ok(public, message, sig):
    """True when sig (64 bytes) is public's Ed25519 signature of message."""
    if len(public) != 32 or len(sig) != 64:
        return False
    a, r = _ed_point(public), _ed_point(sig[:32])
    s = int.from_bytes(sig[32:], "little")
    if a is None or r is None or s >= _L:
        return False
    h = _ed_hash(sig[:32], public, message)
    left, right = _ed_mul(s, _G), _ed_add(r, _ed_mul(h, a))
    return (left[0] * right[2] - right[0] * left[2]) % _P == 0 and \
        (left[1] * right[2] - right[1] * left[2]) % _P == 0


class NotSealed(ValueError):
    """An update without the owner's seal, or a file that isn't the one it lists."""


def sealed(data, sig_text, public=None):
    """version.json's bytes, checked against version.sig's text: its JSON, or NotSealed."""
    try:
        sig = bytes.fromhex(sig_text.strip())
    except (ValueError, AttributeError):
        raise NotSealed("the update has no seal")
    if not ed25519_ok(public or PUBLIC_KEY, SEAL_FOR.encode("utf8") + data, sig):
        raise NotSealed("the update's seal doesn't match, so it wasn't installed")
    remote = json.loads(data.decode("utf8"))
    hashes = remote.get("sha256")
    if not isinstance(hashes, dict) or any(n not in hashes for n in remote["files"]):
        raise NotSealed("the update doesn't list every file's fingerprint")
    return remote


def remote_version(timeout=4):
    """The newest version.json on GitHub, only once its seal is checked (else NotSealed).
    Just after a release GitHub can still send the old version.sig for a few minutes: that
    fails and is tried again next time."""
    with urllib.request.urlopen(RAW + "version.json", timeout=timeout) as r:
        data = r.read()
    with urllib.request.urlopen(RAW + SIG_NAME, timeout=timeout) as r:
        sig = r.read().decode("ascii", "replace")
    return sealed(data, sig)


def file_matches(name, data, remote):
    import hashlib
    if hashlib.sha256(data).hexdigest() != str(remote["sha256"].get(name, "")).lower():
        raise NotSealed(f"{name} isn't the file this update lists, so it wasn't installed")


def update():
    local = json.loads((HERE / "version.json").read_text())
    remote = remote_version()
    if _ver(remote["version"]) <= _ver(local["version"]):
        return None
    names = list(remote["files"])
    for name in names:
        if "/" in name or "\\" in name or name.startswith("."):
            raise ValueError(f"unexpected file name {name}")
    ver = remote["version"]
    opening(f"{UPDATING} {APP_NAME} to {ver}\u2026 (0 of {len(names)})")
    # download everything first, check it, and only then swap files in; several at a time,
    # each tried twice, and all of it within UPDATE_MOST (one after the other, a slow
    # connection to GitHub could keep the opening box waiting for minutes)
    import concurrent.futures
    import time

    def fetch(name):
        for attempt in (1, 2):
            try:
                with urllib.request.urlopen(RAW + name, timeout=20) as r:
                    data = r.read()
                break
            except Exception:
                if attempt == 2:
                    raise
        file_matches(name, data, remote)  # the very file the sealed version.json lists
        if name.endswith((".py", ".pyw")):
            compile(data, name, "exec")  # refuse a broken download
        return data
    staged = {}
    pool = concurrent.futures.ThreadPoolExecutor(UPDATE_AT_ONCE)
    try:
        jobs = {pool.submit(fetch, n): n for n in names}
        end = time.time() + UPDATE_MOST
        for job in concurrent.futures.as_completed(jobs, timeout=max(1, end - time.time())):
            staged[jobs[job]] = job.result()
            opening(f"{UPDATING} {APP_NAME} to {ver}\u2026 ({len(staged)} of {len(names)})")
    except concurrent.futures.TimeoutError:
        raise TimeoutError(f"the update took over {UPDATE_MOST} s; it's tried again next time")
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    if "CleanView.pyw" not in staged and not (HERE / "CleanView.pyw").exists():
        raise ValueError("update is missing CleanView.pyw")
    global LAUNCHER_CHANGED
    old = HERE / "launcher.pyw"
    LAUNCHER_CHANGED = "launcher.pyw" in staged and (
        not old.exists() or old.read_bytes() != staged["launcher.pyw"])
    for name, data in staged.items():
        fd, tmp = tempfile.mkstemp(dir=HERE)
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, HERE / name)
    (HERE / "version.json").write_text(json.dumps(remote, indent=1))
    return remote["version"]


ICON_SHOWN = APP_DATA / "icon_shown.txt"     # which cleanview.ico the shortcuts were told about
SHORTCUT_PLACES = r"""@([Environment]::GetFolderPath('Desktop'),
  [Environment]::GetFolderPath('Programs'),
  (Join-Path $env:APPDATA 'Microsoft\Internet Explorer\Quick Launch\User Pinned\TaskBar'),
  (Join-Path $env:APPDATA 'Microsoft\Internet Explorer\Quick Launch\User Pinned\StartMenu'))"""


def new_icon_on_shortcuts(here=None):
    """A new cleanview.ico (1.18.107, the slight 3D look; the owner: "fix new logo in app screen
    and on desktops"). Windows keeps a picture of a shortcut's icon by the icon file's name, so
    the CleanView shortcuts (desktop, Start menu, pinned to the taskbar) kept showing the old
    one. Once each time the icon changes: a copy named by its contents (cleanview-<mark>.ico),
    this install's shortcuts pointed at it, and Windows told to draw icons again. Only
    shortcuts that start this folder's launcher.pyw are changed. True when it was done."""
    import shutil
    import subprocess
    here = Path(here or HERE)
    icon = here / "cleanview.ico"
    if os.name != "nt" or not icon.exists():
        return False
    try:
        mark = _icon_mark(icon)
        if ICON_SHOWN.read_text(encoding="utf8").strip() == mark:
            return False
    except OSError:
        pass
    shown = here / f"cleanview-{mark}.ico"
    try:
        shutil.copy2(icon, shown)
        q = lambda s: "'" + str(s).replace("'", "''") + "'"     # noqa: E731
        script = (f"$ws = New-Object -ComObject WScript.Shell\n"
                  f"foreach ($d in {SHORTCUT_PLACES}) {{\n"
                  f"  if (-not $d) {{ continue }}\n"
                  f"  $p = Join-Path $d {q(APP_NAME + '.lnk')}\n"
                  f"  if (Test-Path -LiteralPath $p) {{\n"
                  f"    $l = $ws.CreateShortcut($p)\n"
                  f"    if ($l.Arguments.Contains({q(here / 'launcher.pyw')})) {{\n"
                  f"      $l.IconLocation = {q(shown)} + ',0'; $l.Save(); Write-Output $p }}\n"
                  f"  }}\n}}\n")
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                           capture_output=True, text=True, timeout=60, creationflags=0x08000000,
                           stdin=subprocess.DEVNULL)
        if r.returncode:
            raise RuntimeError(r.stderr.strip()[:300])
        changed = [p.strip() for p in r.stdout.splitlines() if p.strip()]
        if changed:
            import ctypes
            sh = ctypes.windll.shell32
            for p in changed:
                sh.SHChangeNotify(0x2000, 0x0005, ctypes.c_wchar_p(p), None)   # it changed
            sh.SHChangeNotify(0x08000000, 0, None, None)                 # icons drawn again
        for old in here.glob("cleanview-*.ico"):
            if old != shown or not changed:
                old.unlink(missing_ok=True)
        APP_DATA.mkdir(parents=True, exist_ok=True)
        ICON_SHOWN.write_text(mark, encoding="utf8")
        return True
    except Exception as ex:
        try:
            (APP_DATA / "shortcut_icon_problem.txt").write_text(str(ex), encoding="utf8")
        except OSError:
            pass
        return False


def run_app():
    """The part that is CleanView: one at a time, look for an update, then open the window."""
    restart = _restarting()
    if not hold(ONE_NAME, wait=RESTART_WAIT if restart else 3):
        bring_forward()                     # two clicks a moment apart: the other one won
        return
    try:
        APP_DATA.mkdir(parents=True, exist_ok=True)
        PID_FILE.write_text(str(os.getpid()), encoding="utf8")
    except OSError:
        pass
    note = new = None
    try:
        new = update()
        if new:
            note = f"CleanView was updated to version {new}."
    except Exception as ex:  # never block the app over an update problem
        try:
            (HERE / "update_error.txt").write_text(str(ex), encoding="utf8")
        except Exception:
            pass
    if note:
        os.environ["CLEANVIEW_UPDATED"] = note
    if new and LAUNCHER_CHANGED:
        # start the new launcher, not this old one already running: what it does differently
        # (its own name in Task Manager, 1.18.9) then works from this start, not the next
        sys.argv = [str(HERE / "launcher.pyw"), APP_PART]
        runpy.run_path(str(HERE / "launcher.pyw"), run_name="__main__")
        return
    opening(f"Opening {APP_NAME}\u2026")
    import threading
    threading.Thread(target=new_icon_on_shortcuts, daemon=True).start()
    sys.argv = [str(HERE / "CleanView.pyw")]
    runpy.run_path(str(HERE / "CleanView.pyw"), run_name="__main__")


def clicked():
    """The part started from the Start menu: if CleanView is already open (or opening), bring
    it forward and stop; otherwise start CleanView and show "Opening CleanView..." until its
    window is up. False: CleanView couldn't be started apart, so run it here as before."""
    if not _restarting() and (exists(ONE_NAME) or not hold(OPENING_NAME)):
        if not bring_forward():
            # no window yet: the one started before is still updating or opening, so say so
            # again instead of only a busy cursor (the owner, 2026-11-17)
            proc = still_opening()
            if proc is not None:
                try:
                    splash(proc)
                except Exception:
                    pass
        return True
    try:
        OPENING_NOTE.unlink(missing_ok=True)
    except OSError:
        pass
    child = start_app()
    if child is None:
        return False
    try:
        splash(child)
    except Exception:          # no window for it: CleanView opens all the same
        pass
    return True


if __name__ == "__main__":
    if APP_PART in sys.argv:
        run_app()
    elif not clicked():
        run_app()
