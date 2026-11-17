"""Files dropped on a window from File Explorer (1.18.115; the owner, 2026-11-16: "can you add
drag and drop option", "drag and drop a movie file in").

Tk can't take a drop by itself, and the add-ons that can (tkdnd) bring a compiled part of their
own, which Smart App Control may block. Windows' own way needs nothing: the window says it takes
files (DragAcceptFiles) and Windows sends it WM_DROPFILES with the paths. The window's message
handler is wrapped (SetWindowLongPtrW) so that one message is seen first; every other message
goes on to Tk's own handler as before.

`on_files(paths)` is called right inside that message, while Tk is in the middle of its own
work, so it must not touch Tk: put the paths on a queue the window reads (CleanView's `self.q`).
Any error in it is swallowed, so a drop can never take the window down.
"""
import os

WM_DROPFILES = 0x0233
GWLP_WNDPROC = -4

_kept = []          # the wrapped handlers, kept alive as long as the program runs


def _api():
    import ctypes
    from ctypes import wintypes
    # their own copies, so the argument types set here don't change anyone else's
    user32, shell32 = ctypes.WinDLL("user32"), ctypes.WinDLL("shell32")
    LRESULT = ctypes.c_ssize_t
    proc_type = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM,
                                   wintypes.LPARAM)
    user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
    user32.SetWindowLongPtrW.restype = ctypes.c_void_p
    user32.CallWindowProcW.argtypes = [ctypes.c_void_p, wintypes.HWND, wintypes.UINT,
                                       wintypes.WPARAM, wintypes.LPARAM]
    user32.CallWindowProcW.restype = LRESULT
    shell32.DragAcceptFiles.argtypes = [wintypes.HWND, wintypes.BOOL]
    shell32.DragQueryFileW.argtypes = [ctypes.c_void_p, wintypes.UINT, wintypes.LPWSTR,
                                       wintypes.UINT]
    shell32.DragQueryFileW.restype = wintypes.UINT
    shell32.DragFinish.argtypes = [ctypes.c_void_p]
    return ctypes, user32, shell32, proc_type


def dropped_paths(hdrop):
    """The paths in a drop (WM_DROPFILES's wParam)."""
    ctypes, _, shell32, _ = _api()
    paths = []
    count = shell32.DragQueryFileW(hdrop, 0xFFFFFFFF, None, 0)
    for i in range(count):
        n = shell32.DragQueryFileW(hdrop, i, None, 0)
        buf = ctypes.create_unicode_buffer(n + 1)
        shell32.DragQueryFileW(hdrop, i, buf, n + 1)
        if buf.value:
            paths.append(buf.value)
    return paths


def window_handles(win):
    """The Windows handles of a Tk window: its frame (title bar and edges) and the inside,
    which holds every widget. Both take drops, so a drop anywhere on it is seen."""
    handles = []
    try:
        handles.append(int(win.wm_frame(), 16))
    except Exception:
        pass
    try:
        handles.append(int(win.winfo_id()))
    except Exception:
        pass
    return [h for i, h in enumerate(handles) if h and h not in handles[:i]]


def accept_drops(win, on_files):
    """Let `win` (a Tk or Toplevel, already made) take files dropped on it. True when it can."""
    if os.name != "nt":
        return False
    try:
        win.update_idletasks()
        ctypes, user32, shell32, proc_type = _api()
        done = False
        for hwnd in window_handles(win):
            old = {}

            def proc(h, msg, wparam, lparam, old=old):
                if msg == WM_DROPFILES:
                    try:
                        paths = dropped_paths(wparam)
                    except Exception:
                        paths = []
                    try:
                        shell32.DragFinish(wparam)
                    except Exception:
                        pass
                    if paths:
                        try:
                            on_files(paths)
                        except Exception:
                            pass
                    return 0
                return user32.CallWindowProcW(old["proc"], h, msg, wparam, lparam)

            cb = proc_type(proc)
            prev = user32.SetWindowLongPtrW(hwnd, GWLP_WNDPROC, ctypes.cast(cb, ctypes.c_void_p))
            if not prev:
                continue
            old["proc"] = prev
            _kept.append(cb)
            shell32.DragAcceptFiles(hwnd, True)
            done = True
        return done
    except Exception:
        return False


def send_drop(hwnd, paths):
    """Post a drop of `paths` to a window, the way File Explorer does (for the tests)."""
    import ctypes
    from ctypes import wintypes
    kernel32, user32 = ctypes.WinDLL("kernel32"), ctypes.WinDLL("user32")
    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM,
                                    wintypes.LPARAM]

    class DROPFILES(ctypes.Structure):
        _fields_ = [("pFiles", wintypes.DWORD), ("x", wintypes.LONG), ("y", wintypes.LONG),
                    ("fNC", wintypes.BOOL), ("fWide", wintypes.BOOL)]
    names = ("\0".join(paths) + "\0\0").encode("utf-16-le")
    size = ctypes.sizeof(DROPFILES) + len(names)
    mem = kernel32.GlobalAlloc(0x0042, size)          # GHND: movable, zeroed
    p = kernel32.GlobalLock(mem)
    head = DROPFILES(ctypes.sizeof(DROPFILES), 0, 0, False, True)
    ctypes.memmove(p, ctypes.byref(head), ctypes.sizeof(DROPFILES))
    ctypes.memmove(p + ctypes.sizeof(DROPFILES), names, len(names))
    kernel32.GlobalUnlock(mem)
    return bool(user32.PostMessageW(hwnd, WM_DROPFILES, mem, 0))
