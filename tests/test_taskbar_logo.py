"""The logo in the taskbar (1.18.111; the owner, 2026-11-16, on another computer: "the logo on the
windows bar when it is open was a pic of a random file symbol thing", "not the green
picture"). CleanView's window has its own taskbar name, so Windows shows the logo the window
carries rather than the icon of the program it runs under."""
import os
import tkinter as tk
import unittest

import support  # noqa: F401  (must come first)
import test_ui

ui = test_ui.ui


def process_taskbar_id():
    import ctypes
    from ctypes import wintypes
    out = wintypes.LPWSTR()
    shell = ctypes.windll.shell32
    if shell.GetCurrentProcessExplicitAppUserModelID(ctypes.byref(out)) != 0:
        return None
    try:
        return out.value
    finally:
        ctypes.windll.ole32.CoTaskMemFree(out)


def green_in_icon(hwnd, big=True):
    """How much of the window's taskbar (big) or title bar (small) icon is green."""
    import ctypes
    from ctypes import wintypes
    user, gdi = ctypes.windll.user32, ctypes.windll.gdi32
    user.SendMessageW.restype = wintypes.HANDLE
    user.SendMessageW.argtypes = [wintypes.HWND, ctypes.c_uint, wintypes.WPARAM, wintypes.LPARAM]
    icon = user.SendMessageW(hwnd, 0x7F, 1 if big else 0, 96)          # WM_GETICON
    if not icon:
        return 0.0
    n = 32 if big else 16
    hdc = user.GetDC(None)
    mdc = gdi.CreateCompatibleDC(hdc)
    bmp = gdi.CreateCompatibleBitmap(hdc, n, n)
    old = gdi.SelectObject(mdc, bmp)
    try:
        gdi.PatBlt(mdc, 0, 0, n, n, 0x00FF0062)                         # white
        user.DrawIconEx(mdc, 0, 0, wintypes.HANDLE(icon), n, n, 0, None, 3)
        green = sum(1 for y in range(n) for x in range(n)
                    if (lambda c: (c >> 8 & 255) > (c & 255) + 30)(gdi.GetPixel(mdc, x, y)))
        return green / (n * n)
    finally:
        gdi.SelectObject(mdc, old)
        gdi.DeleteObject(bmp)
        gdi.DeleteDC(mdc)
        user.ReleaseDC(None, hdc)


@unittest.skipUnless(os.name == "nt", "Windows only")
class TaskbarLogo(unittest.TestCase):
    def test_own_name_and_the_logo_on_the_window(self):
        saved = ui.App._check_update, ui.App._check_every_ai
        ui.App._check_update = lambda self, manual=False: None
        ui.App._check_every_ai = lambda self: None
        try:
            try:
                app = ui.App()
            except tk.TclError as ex:
                self.skipTest(f"no screen to draw on ({ex})")
            try:
                app.update()
                self.assertEqual(process_taskbar_id(), ui.TASKBAR_ID)
                hwnd = int(app.wm_frame(), 16)
                self.assertGreater(green_in_icon(hwnd, big=True), 0.4)    # the green logo
                self.assertGreater(green_in_icon(hwnd, big=False), 0.4)
            finally:
                app.destroy()
        finally:
            ui.App._check_update, ui.App._check_every_ai = saved

    def test_set_before_the_window(self):
        src = (support.ROOT / "CleanView.pyw").read_text(encoding="utf8")
        init = src[src.index("class App(tk.Tk):"):]
        self.assertLess(init.index("own_taskbar_id()"), init.index("super().__init__()"))
        self.assertTrue(ui.own_taskbar_id())


if __name__ == "__main__":
    unittest.main()
