"""A stand-in for cleanview.analyze, for the video workers in the tests (videoqueue.py loads
it when CLEANVIEW_ENGINE=fake_engine). What it does depends on the video's name:
"bad" fails with a message, "crash" ends the process without a word, "slow" runs until it's
asked to stop; anything else takes a moment and writes an analysis (opts["sample"]: a file
to copy as the analysis). Each run writes when it started and ended to <work>/times.json."""
import json
import os
import shutil
import time
from pathlib import Path


class VideoError(Exception):
    pass


def analyze(path, workdir, groups=(), opts=None, progress=None, log=None, cancel=None,
            threads=None, **kw):
    opts = opts or {}
    name = Path(path).name
    work = Path(workdir)
    t0 = time.time()
    progress(0.1, f"Listening to {name}")
    if "crash" in name:
        os._exit(3)
    if "bad" in name:
        raise RuntimeError("Couldn't read the sound in this video.\nffmpeg said: no stream")
    if "unreadable" in name:
        raise VideoError("This file isn't a video CleanView can read.")
    end = time.time() + (60 if "slow" in name else float(opts.get("secs", 0.8)))
    while time.time() < end:
        if cancel and cancel():
            raise KeyboardInterrupt
        time.sleep(0.05)
    progress(0.9, "Almost done")
    (work / "times.json").write_text(json.dumps({"start": t0, "end": time.time(),
                                                 "threads": threads}))
    if opts.get("sample"):
        shutil.copy(opts["sample"], work / "analysis.json")
    else:
        (work / "analysis.json").write_text(json.dumps({"video": name, "groups": list(groups)}))
    return json.loads((work / "analysis.json").read_text())
