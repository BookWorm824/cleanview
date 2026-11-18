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


# File Explorer drags with OLE (DoDragDrop). WM_DROPFILES alone wasn't enough (1.18.119; the
# owner: "the drag and drop doesnt work", though the window had WS_EX_ACCEPTFILES): a drop is
# over one of Tk's many child windows (a frame, a label), and only a drop target registered with
# RegisterDragDrop is looked for up the chain of parents, so one on the window's inside covers
# every widget. This is that drop target, a small COM object made with ctypes.
CF_HDROP, DVASPECT_CONTENT, TYMED_HGLOBAL = 15, 1, 1
DROPEFFECT_NONE, DROPEFFECT_COPY = 0, 1
S_OK, E_NOINTERFACE = 0, 0x80004002
OLE_REGISTERED = []          # the windows a drop target was registered on (for the tests)


def _ole():
    import ctypes
    from ctypes import wintypes

    class GUID(ctypes.Structure):
        _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                    ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]

    class FORMATETC(ctypes.Structure):
        _fields_ = [("cfFormat", wintypes.WORD), ("ptd", ctypes.c_void_p),
                    ("dwAspect", wintypes.DWORD), ("lindex", wintypes.LONG),
                    ("tymed", wintypes.DWORD)]

    class STGMEDIUM(ctypes.Structure):
        _fields_ = [("tymed", wintypes.DWORD), ("hGlobal", ctypes.c_void_p),
                    ("pUnkForRelease", ctypes.c_void_p)]

    ole32 = ctypes.WinDLL("ole32")
    ole32.OleInitialize.argtypes = [ctypes.c_void_p]
    ole32.OleInitialize.restype = ctypes.c_long
    ole32.RegisterDragDrop.argtypes = [wintypes.HWND, ctypes.c_void_p]
    ole32.RegisterDragDrop.restype = ctypes.c_long
    ole32.ReleaseStgMedium.argtypes = [ctypes.POINTER(STGMEDIUM)]
    return ctypes, wintypes, ole32, GUID, FORMATETC, STGMEDIUM


def _guid(GUID, text):
    import uuid
    u = uuid.UUID(text)
    g = GUID(u.time_low, u.time_mid, u.time_hi_version)
    for k, b in enumerate(u.bytes[8:]):
        g.Data4[k] = b
    return g


class DropTarget:
    """An IDropTarget for File Explorer's drags: shows the copy cursor over the window when
    files are dragged in, and hands their paths to on_files when dropped (inside Windows'
    message, so on_files must not touch Tk)."""

    def __init__(self, on_files, on_hover=None):
        ctypes, wintypes, ole32, GUID, FORMATETC, STGMEDIUM = _ole()
        self._c, self._ole32 = ctypes, ole32
        self._FORMATETC, self._STGMEDIUM = FORMATETC, STGMEDIUM
        self.on_files = on_files
        # files held over the window (True) or not any more (False), to show it's ready to
        # take them (1.18.134); called inside Windows' message, so it must not touch Tk
        self.on_hover = on_hover
        self._effect = DROPEFFECT_NONE
        HRESULT, ULONG = ctypes.c_long, wintypes.ULONG
        PDWORD = ctypes.POINTER(wintypes.DWORD)
        # a POINTL is passed by value: 8 bytes, the same as one 64-bit number
        T = ctypes.WINFUNCTYPE
        self._unknown = (_guid(GUID, "00000000-0000-0000-C000-000000000046"),
                         _guid(GUID, "00000122-0000-0000-C000-000000000046"))
        self._fns = [
            T(HRESULT, ctypes.c_void_p, ctypes.POINTER(GUID),
              ctypes.POINTER(ctypes.c_void_p))(self._query),
            T(ULONG, ctypes.c_void_p)(lambda this: 1),                       # AddRef
            T(ULONG, ctypes.c_void_p)(lambda this: 1),                       # Release
            T(HRESULT, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.c_uint64,
              PDWORD)(self._enter),
            T(HRESULT, ctypes.c_void_p, wintypes.DWORD, ctypes.c_uint64, PDWORD)(self._over),
            T(HRESULT, ctypes.c_void_p)(self._leave),
            T(HRESULT, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.c_uint64,
              PDWORD)(self._drop)]
        self._vtbl = (ctypes.c_void_p * len(self._fns))(
            *[ctypes.cast(f, ctypes.c_void_p) for f in self._fns])
        self._obj = (ctypes.c_void_p * 1)(ctypes.addressof(self._vtbl))
        self.pointer = ctypes.addressof(self._obj)        # the IDropTarget* handed to Windows

    def _same(self, a, b):
        c = self._c
        return c.string_at(c.addressof(a), 16) == c.string_at(c.addressof(b), 16)

    def _query(self, this, riid, ppv):
        if any(self._same(riid.contents, g) for g in self._unknown):
            ppv[0] = this
            return S_OK
        ppv[0] = None
        return E_NOINTERFACE

    def _format(self):
        return self._FORMATETC(CF_HDROP, None, DVASPECT_CONTENT, -1, TYMED_HGLOBAL)

    def _call(self, obj, index, restype, *args):
        """Method number index of the COM object obj (an IDataObject)."""
        c = self._c
        vtbl = c.cast(c.c_void_p(obj), c.POINTER(c.POINTER(c.c_void_p)))[0]
        fn = c.WINFUNCTYPE(restype, c.c_void_p, *[type(a) for a in args])(vtbl[index])
        return fn(obj, *args)

    def has_files(self, data):
        c = self._c
        try:   # IDataObject::QueryGetData is method 5
            return self._call(data, 5, c.c_long, c.pointer(self._format())) == S_OK
        except Exception:
            return False

    def paths(self, data):
        """The file paths in an IDataObject (CF_HDROP)."""
        c = self._c
        medium = self._STGMEDIUM()
        # IDataObject::GetData is method 3
        if self._call(data, 3, c.c_long, c.pointer(self._format()), c.pointer(medium)) != S_OK:
            return []
        try:
            return dropped_paths(medium.hGlobal)
        finally:
            self._ole32.ReleaseStgMedium(c.byref(medium))

    def _enter(self, this, data, keys, pt, effect):
        try:
            self._effect = DROPEFFECT_COPY if data and self.has_files(data) else DROPEFFECT_NONE
        except Exception:
            self._effect = DROPEFFECT_NONE
        if effect:
            effect[0] = self._effect
        if self._effect == DROPEFFECT_COPY:
            self._hover(True)
        return S_OK

    def _hover(self, on):
        if self.on_hover:
            try:
                self.on_hover(on)
            except Exception:
                pass

    def _over(self, this, keys, pt, effect):
        if effect:
            effect[0] = self._effect
        return S_OK

    def _leave(self, this):
        self._effect = DROPEFFECT_NONE
        self._hover(False)
        return S_OK

    def _drop(self, this, data, keys, pt, effect):
        got = []
        try:
            got = self.paths(data) if data else []
        except Exception:
            got = []
        if effect:
            effect[0] = DROPEFFECT_COPY if got else DROPEFFECT_NONE
        self._effect = DROPEFFECT_NONE
        self._hover(False)
        if got:
            try:
                self.on_files(got)
            except Exception:
                pass
        return S_OK


def ole_drops(handles, on_files, on_hover=None):
    """Register one DropTarget on each window. The thread must be the window's (Tk's)."""
    try:
        ctypes, wintypes, ole32, *_ = _ole()
        ole32.OleInitialize(None)          # S_OK, or S_FALSE when it was already
        target = DropTarget(on_files, on_hover)
        ok = False
        for hwnd in handles:
            if ole32.RegisterDragDrop(hwnd, target.pointer) == S_OK:
                OLE_REGISTERED.append(hwnd)
                ok = True
        if ok:
            _kept.append(target)
        return target if ok else None
    except Exception:
        return None


def accept_drops(win, on_files, on_hover=None):
    """Let `win` (a Tk or Toplevel, already made) take files dropped on it. True when it can.
    on_hover(True/False): files are held over it, or not any more (File Explorer's drags)."""
    if os.name != "nt":
        return False
    try:
        win.update_idletasks()
        ctypes, user32, shell32, proc_type = _api()
        done = ole_drops(window_handles(win), on_files, on_hover) is not None
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
