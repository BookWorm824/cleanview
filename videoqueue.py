"""Several videos at once (Lauren, 2026-11-04: "have it where it can run multiple").

When several videos are cleaned together (a season of episodes), each one is watched and
listened to (cleanview.analyze) in its own worker process, up to "Videos at once" at a time
(2 by default). A worker that crashes or gets stuck never takes the window down, and the
videos running together share the PC's cores. Review and saving work as before.

The window side is Workers (starts and stops the workers and hands back what they send).
The worker side is main(), run as:

    CleanView.exe videoqueue.py <work folder>/queue_task.json

It sends one JSON object per line on stdout: {"p": 0.42, "m": "Listening…"} for progress,
then {"done": true} (the analysis is in <work>/analysis.json), {"stopped": true} or
{"error": "<in plain words>", "raw": "...", "video_error": bool, "details": "<traceback>"}.
Its stop file (written by the window for Cancel or closing), or the window going away,
stops it after the bit it's on; the steps already done are kept for next time.
"""
import faulthandler
import importlib
import json
import os
import re
import subprocess
import sys
import threading
import time
import traceback
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent

AT_ONCE_CHOICES = (1, 2, 3, 4)
DEFAULT_AT_ONCE = 2


def default_at_once(total_gb=None):
    """2 at a time, or 1 on a PC with less than 12 GB of memory: each video loads its own
    speech and picture models (about 2 GB)."""
    gb = total_gb if total_gb is not None else memory_gb()
    return 1 if gb and gb < 12 else DEFAULT_AT_ONCE


def memory_gb():
    """The PC's memory in GB, or 0 when it can't be told."""
    try:
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes

            class Mem(ctypes.Structure):
                _fields_ = [("size", wintypes.DWORD), ("load", wintypes.DWORD)] + [
                    (n, ctypes.c_ulonglong) for n in ("total", "free", "page_total",
                                                       "page_free", "virt_total",
                                                       "virt_free", "ext_free")]
            m = Mem()
            m.size = ctypes.sizeof(m)
            if ctypes.WinDLL("kernel32").GlobalMemoryStatusEx(ctypes.byref(m)):
                return m.total / 1024 ** 3
            return 0
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1024 ** 3
    except Exception:
        return 0


def threads_each(at_once, cpus=None):
    """Speech-recognition threads for each video, so the ones running together share the
    PC's cores (one video uses at most 8)."""
    cpus = cpus or os.cpu_count() or 2
    return max(2, min(8, cpus // max(1, at_once)))


_PLAIN_KINDS = {"RuntimeError", "VideoError", "ClaudeError", "GptError", "GeminiError"}

# Running out of memory, as the speech recognizer ("bad allocation"), Python, ffmpeg and
# Windows (WinError 1455, 1450, 8) say it (CleanListen 1.14.4-1.14.5, 2026-11-04). More
# videos at once is the likeliest cause, so that's the first thing to try.
OUT_OF_MEMORY = ("This computer ran out of memory. Set \u201cVideos at once\u201d to 1, close "
                 "other programs, and try again.")
_MEMORY_WORDS = ("bad allocation", "bad_alloc", "memoryerror", "out of memory",
                 "not enough memory", "failed to allocate", "unable to allocate",
                 "cannot allocate memory", "paging file is too small",
                 "insufficient system resources", "not enough storage is available")
_MEMORY_WINERRORS = {8, 14, 1450, 1453, 1455}


def memory_trouble(text):
    """Does this error message (or a worker's log) say memory ran out?"""
    t = str(text or "").lower()
    return any(w in t for w in _MEMORY_WORDS)


def plain_error(ex):
    """What went wrong, in everyday words. The technical part is kept out of sight."""
    win = getattr(ex, "winerror", None)
    if (isinstance(ex, MemoryError) or win in _MEMORY_WINERRORS
            or memory_trouble(f"{type(ex).__name__}: {ex}")):
        return OUT_OF_MEMORY
    if isinstance(ex, PermissionError) or win in (32, 33):
        return ("A file CleanView needs is open in another program (maybe a video player). "
                "Close it and try again.")
    if isinstance(ex, OSError) and (win == 112 or ex.errno == 28):
        return "The drive is full. Free up some space and try again."
    text = str(ex).strip()
    if text and _PLAIN_KINDS & {c.__name__ for c in type(ex).__mro__}:
        # CleanView's own messages say it plainly first, then add the technical part
        first = re.split(r":?\s*\n", text, maxsplit=1)[0].strip()
        first = first[:1].upper() + first[1:]
        return first if first.endswith((".", "!", "?")) else first + "."
    return "Something unexpected went wrong."


# ---------------------------------------------------------------------------
# The window side
# ---------------------------------------------------------------------------
def _no_window():
    return getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0


def kill_tree(proc):
    """Stop a worker and everything it started (ffmpeg, the picture scan, Claude...)."""
    if proc.poll() is not None:
        return
    if os.name == "nt":
        try:
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True,
                           creationflags=_no_window(), timeout=15)
        except Exception:
            pass
    try:
        proc.kill()
    except Exception:
        pass


class Workers:
    """One worker process per video being worked on. on_message(key, dict) is called (on a
    reading thread) for every line a worker sends, and once with {"exit": code} at the end."""

    def __init__(self, on_message, python=None, env=None):
        self.on_message = on_message
        self.python = python or sys.executable
        self.env = env or {}
        self.procs = {}
        self._lock = threading.Lock()

    def start(self, key, spec):
        """spec: video, work, groups, opts, threads. Written to the video's work folder."""
        wd = Path(spec["work"])
        wd.mkdir(parents=True, exist_ok=True)
        # "stop" is a file, not a line on the worker's input: on Windows a thread waiting to
        # read a pipe stops other DLLs loading (CleanListen's workers froze importing numpy)
        stop_file = wd / f"queue.stop.{uuid.uuid4().hex[:8]}"
        spec = dict(spec, work=str(wd), stop_file=str(stop_file), parent=os.getpid())
        spec_path = wd / "queue_task.json"
        spec_path.write_text(json.dumps(spec, indent=1), encoding="utf8")
        err = open(wd / "worker_log.txt", "w", encoding="utf8", errors="replace")
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1", **self.env)
        try:
            proc = subprocess.Popen([self.python, str(HERE / "videoqueue.py"), str(spec_path)],
                                    cwd=str(HERE), stdin=subprocess.DEVNULL,
                                    stdout=subprocess.PIPE, stderr=err, env=env,
                                    creationflags=_no_window())
        finally:
            err.close()
        proc.stop_file = stop_file
        with self._lock:
            self.procs[key] = proc
        threading.Thread(target=self._read, args=(key, proc), daemon=True,
                         name=f"video worker {key}").start()
        return proc

    def _read(self, key, proc):
        for raw in proc.stdout:
            line = raw.decode("utf8", "replace").strip()
            if not line.startswith("{"):
                continue
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            self.on_message(key, msg)
        proc.stdout.close()
        code = proc.wait()
        try:
            proc.stop_file.unlink()
        except OSError:
            pass
        with self._lock:
            if self.procs.get(key) is proc:
                del self.procs[key]
        self.on_message(key, {"exit": code})

    def running(self):
        with self._lock:
            return [k for k, p in self.procs.items() if p.poll() is None]

    def stop_all(self, wait=8.0):
        """Ask every worker to stop (each finishes the bit it's on), wait a little, then make
        sure (Cancel, or the window closing)."""
        with self._lock:
            procs = list(self.procs.values())
        for p in procs:
            try:
                p.stop_file.write_text("stop")
            except OSError:
                pass
        end = time.monotonic() + wait
        for p in procs:
            try:
                p.wait(timeout=max(0.1, end - time.monotonic()))
            except subprocess.TimeoutExpired:
                pass
        for p in procs:
            kill_tree(p)


# ---------------------------------------------------------------------------
# The worker side
# ---------------------------------------------------------------------------
_out_lock = threading.Lock()


def send(**msg):
    with _out_lock:
        sys.stdout.write(json.dumps(msg) + "\n")
        sys.stdout.flush()


def window_gone(pid):
    """Has the window that started this worker closed (or crashed)?"""
    if not pid:
        return False
    if os.name != "nt":
        try:
            os.kill(pid, 0)
            return False
        except OSError:
            return True
    import ctypes
    k32 = ctypes.WinDLL("kernel32")
    k32.OpenProcess.restype = ctypes.c_void_p
    h = k32.OpenProcess(0x00100000, False, int(pid))       # SYNCHRONIZE
    if not h:
        return True
    try:
        return k32.WaitForSingleObject(ctypes.c_void_p(h), 0) == 0   # it has ended
    finally:
        k32.CloseHandle(ctypes.c_void_p(h))


def watch_for_stop(stop, stop_file, parent):
    def run():
        while not stop.is_set():
            try:
                if (stop_file and os.path.exists(stop_file)) or window_gone(parent):
                    stop.set()
                    return
            except Exception:
                pass
            time.sleep(0.5)
    threading.Thread(target=run, daemon=True).start()


def lock_video(work, stop, say):
    """One worker per video at a time: one from a Cancel just before may still be finishing.
    Wait for it, so two never write the same files."""
    fh = open(Path(work) / "queue.lock", "a+b")
    if os.name != "nt":
        return fh
    import msvcrt
    told = False
    while True:
        try:
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            return fh
        except OSError:
            if stop.is_set():
                raise KeyboardInterrupt
            if not told:
                say(0.0, "Waiting for the last run of this video to stop…")
                told = True
            time.sleep(0.5)


def main(spec_path):
    spec = json.loads(Path(spec_path).read_text(encoding="utf8"))
    work = Path(spec["work"])
    try:
        faulthandler.enable()          # a hard crash goes to worker_log.txt (stderr)
    except Exception:
        pass
    stop = threading.Event()
    watch_for_stop(stop, spec.get("stop_file"), spec.get("parent"))
    say = lambda f, m: send(p=round(float(f), 4), m=str(m))
    try:
        lock = lock_video(work, stop, say)
        # (CLEANVIEW_ENGINE: the tests use a stand-in engine)
        engine = importlib.import_module(os.environ.get("CLEANVIEW_ENGINE") or "cleanview")
        engine.analyze(spec["video"], str(work), groups=spec["groups"], opts=spec["opts"],
                       progress=say, log=lambda m: None, cancel=stop.is_set,
                       threads=spec.get("threads"))
        lock.close()
        send(done=True)
    except KeyboardInterrupt:
        send(stopped=True)
    except Exception as ex:
        details = traceback.format_exc()
        try:
            (work / "last_error.txt").write_text(details, encoding="utf8")
        except OSError:
            pass
        send(error=plain_error(ex), raw=str(ex) or ex.__class__.__name__,
             video_error=type(ex).__name__ == "VideoError", details=details)


if __name__ == "__main__":
    sys.path.insert(0, str(HERE))
    main(sys.argv[1])
