# CleanView: project brief

CleanView is a Windows desktop app that makes family-friendly copies of movies and TV episodes
the user owns: it **mutes** bad language and problem dialogue and **cuts** scenes (violence,
nudity, sex, etc.), in the spirit of VidAngel, but on local DRM-free files (DVD/Blu-ray rips).
Originals are never changed; it writes a "(Clean)" copy plus a report.

It is a sister app to **CleanListen** (an audiobook cleaner, separate repo). The two must stay
separate programs (separate install, folder, settings, updates) so both can run at once. They
share ideas and some code lineage (`cvcore.py` started as CleanListen's core).

## Who uses it

- The owner, Lauren: not a programmer. She runs it on her Windows PC, cleans whole seasons of
  kids' shows (e.g. *Adventures of the Gummi Bears*) and adult shows (*Castle*, *Blue Bloods*),
  checks the result, and reports back with the report file or a screenshot.
- Her sister and others: may have **no Claude and no ChatGPT**, so everything must work fully
  offline with the local models. Claude/ChatGPT are optional upgrades.
- All UI text must be plain, short, everyday language. No jargon, no stack traces in the UI.
- Text size (Normal / Larger / Largest, start page) works through `tk scaling`, which Tk
  applies as each part of the window is built, so changing it builds the start page again
  in the same window, redraws the tick boxes and grows the window (`_set_text_size`,
  `_fit_window`). It used to restart CleanView, which on a slow PC looked like it had shut
  down (Jason, 2026-10-29). Give fonts in
  points (`(FONT, 10)`) and wrap widths through `wrap_width(px)` so both follow it.
  Never give a local variable the name of a module helper a function calls (1.11.7 named a
  box `wrap` in a function calling `wrap()`, and the review page failed to open);
  `test_ui.NoHiddenNames` checks for this. "◀ Back to start" on the review page
  (Jason, 2026-10-30: he only wanted to check a movie, not save it) keeps the review, so
  "Pick up where I left off" opens it again, and her ticks are learned then too
  (`_learn_choices`; `learn.record` counts each choice once however often she leaves and
  comes back, `_learned_as`). The video's name is shown big at the top of the review page.
  Every question box chimes (`chime()`; Windows' question boxes are silent). Tick boxes
  are drawn images (`_tick_boxes`), since the theme's own show an ✗.
- Buttons: each page's main step is the big green `Accent.TButton`, bottom right (Start
  cleaning, Save clean copy, Clean another); first steps are the smaller green
  `Go.TButton` (Choose files…, Pick up where I left off, Set up and sign in); the grey
  `Plain`/`Small` ones have an edge so they read as buttons. Main buttons are never
  greyed out: pressed too early they say what to do first (Jason missed a grey "Clean
  another").
- Slow things (reading video lengths, Claude) run in a thread and come back to the
  window through `self.q` (`("call", fn)` runs fn on the window's thread).

## How it runs

- Python 3.12 + tkinter. Installed per-user into `%LOCALAPPDATA%\CleanView` with its own venv by
  `installer/install.ps1` (run from `installer/Install CleanView.bat`, no admin rights). The
  installer copies CleanListen's speech model and ffmpeg if present, to save downloading them.
- Start Menu shortcut runs `launcher.pyw`, which checks GitHub for updates and then runs
  `CleanView.pyw`.
- User data lives in `%LOCALAPPDATA%\CleanView` (`APP_DATA` in the code): settings, learned
  choices, Claude findings, saved Claude/ChatGPT answers (`answers\`), the saved
  in-progress review.
- Sending what it learned: "Send what CleanView learned…" and "Send what we refined…"
  (on the review page, before saving, and on the done page) post the file to the CleanView inbox, a Google Apps Script web app in the owner's Google
  account (`tools/cleanview_inbox.gs`, setup in `tools/README-inbox.txt`; its address is
  `cleanview_learn.SEND_URL`, and CleanListen uses the same one). Files land in the Drive
  folder "CleanView learned"; merge them with `tools/merge_learned.py`. No internet or "not
  now": the old "saved here, attach it" message. Tests point `CLEANVIEW_INBOX` at nothing
  (`support.NO_INBOX`) so they never send to the real one.
- Reports sent in are checked before anything is learned from them (Lauren, 2026-10-29):
  every flag is judged against the filters that were on, and the dialogue is read for
  anything missed. Her own unticks of things that do fit a filter are her choice, not a
  wrong flag, and are never taught as fine. Only the checked results are merged into
  `shared_learned.json` (a "CleanView reviewed" file through `merge_learned.py`): lines
  that are a problem on their own, with the filter they're for (`muted_for`, so they're only
  muted, or shown as examples, when that filter is ticked: `learn.apply(on=...)`), flagged
  lines that fit no filter, and listed words that were fine in context. Short everyday lines
  that were only muted as part of a conversation are never taught. Reports gone over are
  then deleted from the Drive folder, so they aren't gone over twice. Every untick is
  looked at (Lauren 2026-10-30): one that was flagged wrongly is taught as a false alarm;
  one that does fit a filter is her preference and isn't. Lessons that are about judging
  (a scene, a show's names) can ship as built-in notes: `"notes"` in `shared_learned.json`
  (general, or per show; `{"text", "title"}` for one movie), which `learn.notes` adds
  first and `merge_learned.py` carries. A word only "fine" because its group was off,
  or a line fine in one movie but usually innuendo elsewhere, is never taught as fine.
  Nor is a line with a listed word or phrase in it, or a strong or moderate swear "fine in
  context" (those were misheard, which the subtitle check handles); same-sex lines that only
  say "wife" or "husband" aren't taught, and taught muted lines have 5+ words (November
  reports: 13 reports, 36 videos).
- A word heard in the sound where the subtitles have a different, ordinary word or a name
  at that spot is noted for the review (`subtitle_word_there`, `m["sub"]`: "dick" where
  they have "Nic"); one the subtitles only leave out or soften isn't.
- The chat can learn (Jason, 2026-10-30: told "it's Aladdin", it said it couldn't change
  what it looks for). When they explain how something should be judged from now on, its
  answer's `remember` list is kept as notes (`learn.add_note`/`learn.notes`): for that movie
  (by title), every episode of that show, or everything they clean (`_all@profile`). Notes
  go to the dialogue readers (local and cloud), the final review and the chat
  (`examples()["notes"]`, `cc.told`), the cloud picture checks (`look_at_picture`), and
  are in "Send what CleanView learned". The chat keeps a lesson whenever it's corrected
  (1.18.2: told "they're just talking in bed", it unticked the scene but kept nothing).
  Sex scenes are judged by what's happening and the context, not the bed or the clothes
  (Lauren 2026-10-30: two people only talking in bed isn't one, but a sex scene can be
  people sitting with their clothes on), including oral sex and touching private parts
  (`PIC_RULES`, `picture_wanted`, local `LOOK["bed"]`, `sexref`). The picture checks get
  what's said and the subtitles' sounds with each sheet and scene (`heard_between`,
  `picture_review(context=)`, `CONTEXT_HOW`); the old wanted text "a couple in bed" made
  it cut every couple in bed.
- The chat (and "Ask ... about this") is offered whenever Claude, ChatGPT or Gemini is set
  up, even when the AI on this PC read the dialogue (Jason, 2026-11-04: he cleaned with the
  local AI and couldn't tell Claude what it got wrong, to teach it). `_check_every_ai` checks
  all three in the background when cleaning starts and when the review opens without one;
  `_pick_review_ai` takes the first that's ready (Claude first); `_offer_chat` builds the
  review page again once one turns out to be. What the chat is told to remember goes to the
  local reader too (`learn.notes`), and to the local picture check (`second_look(notes=)`,
  `family_said`), so his corrections about scenes teach CleanView without Claude too.
- Learned lines under 5 words (`learn.LEARNED_SHORTEST`) are never muted again just
  because they were learned: a muted conversation is learned line by line, and "What do
  you think?" was then muted in every later episode (The Resident).
- Task Manager says "CleanView", not "Python" (Jason, 2026-11-03): `launcher.pyw` starts
  itself again as `venv\CleanView\CleanView.exe`, a copy of the base `pythonw.exe` with
  CleanView's description and icon (`make_own_exe`, `_rename_exe`); `CleanView-work.exe`
  (from `python.exe`) runs the picture scan and pip (`cleanview._venv_python`). It finds
  the venv through `venv\pyvenv.cfg` one folder up. Not in `Scripts`: sherpa-onnx put an
  `onnxruntime.dll` there, which an .exe in that folder would load first. The changed .exe
  has no signature, so it's only made while Smart App Control is off, only used after a
  test run of it worked, and never tried again once it failed (`failed.txt`); otherwise
  plain pythonw.exe, as before. CleanListen and CleanRead want the same.
- Several videos at once (Lauren, 2026-11-04, after CleanListen's book queue): when a
  season is cleaned, each video is watched and listened to in its own worker process
  (`videoqueue.py`, started by `App._run_workers` on the analyze thread), 2 at a time by
  default (1 on a PC with under 12 GB of memory, `default_at_once`; each worker loads its
  own speech and picture models), 1-4 with "Videos at once" on the working page (saved as
  `at_once` in the settings; the next video to start follows it). Speech threads are
  shared out (`threads_each`). Each video's own progress shows beside its name; "Stop
  after the ones being done now" lets the running ones finish. A worker that crashes only
  loses its own video ("stopped working on this video unexpectedly", its log in
  `<work>/worker_log.txt`); Cancel or closing the window writes each worker's stop file,
  and a worker whose window has gone stops by itself. Ollama is started once by the
  window, not by each worker. Review and saving work as before (one review page for all).
  The worker reads `analysis.json` from the work folder, so the review gets the same JSON
  a resumed review does. Tests run the workers with a stand-in engine
  (`CLEANVIEW_ENGINE=fake_engine`, `tests/fake_engine.py`).
- Low memory (CleanListen 1.14.4-1.14.5, 2026-11-04: "bad allocation", "[WinError 1455] The
  paging file is too small"): `cvcore.run`/`popen` wait 5, 15 and 30 s and try again when
  Windows can't start a program for lack of memory (`LOW_MEMORY_ERRORS`); `analyze` calls
  `cleanview_ai.free_memory()` once the AI helper's part is done (Ollama `keep_alive: 0` for
  the loaded models, instead of holding several GB for 5 minutes); `videoqueue.plain_error`
  (and a worker whose log says so) shows `OUT_OF_MEMORY` ("Set 'Videos at once' to 1...").
- The window stays quick to answer (CleanListen 1.15.1, 2026-11-05: a book took all 6 cores
  and the window looked frozen): `threads_each` leaves one core free, the video workers start
  below normal priority (`videoqueue.BELOW_NORMAL`, inherited by what they start), and so does
  everything started through `cvcore.run`/`popen` (`_NOWIN`), including ffmpeg making the clean
  copy from the window's process.
- Ollama only while CleanView, CleanListen or CleanRead are open (Lauren, 2026-11-05; it held
  ~4 GB all day): `ollama_care.py` is CleanListen's (1.15.2), with `videoqueue.py` added to
  `CLEAN_APPS`; keep the two copies the same. The installed copy (`_installed_copy`) calls
  `autostart_off()` on every opening (removes `Startup\Ollama.lnk`, which Ollama's updates put
  back) and `stop_later()` after `mainloop()` (a detached helper stops Ollama once no app or
  worker is running and no model is loaded; if it can't tell, Ollama is left alone).
  `launcher.pyw` falls back to `BookWorm824/cleanview` when `update.json` is missing or broken.
- A freeze or a crash is written down (Jason, 2026-11-03: it stopped responding during a
  movie and didn't say why). If the window doesn't answer for 20 s (`STALL_SECS`), what
  every thread was doing, the step and memory go in `stopped_last_time.txt`; a hard crash
  is caught by faulthandler (`crash_log.txt`). Next start she's asked whether to send it
  in (kind "problem", to the same inbox). `_poll` handles at most 500 messages a go and
  only the newest progress, so a flood of them can't keep the window busy.
- Times: everything counts from 0 = the start of the file, the clock ffmpeg's filters use in
  `render()` (not the file's own start time, which can be 10 s or more on .ts/.vob rips).
  Sound is always read through `_mono()` (or `snap_edges(audio=...)`), which pads a late
  start with silence so the sound and the picture share that clock.

### Auto-update (important when changing files)

`launcher.pyw` reads `version.json` from `raw.githubusercontent.com/BookWorm824/cleanview/main`.
If its `version` is higher (compared as int tuples, so 1.10.0 > 1.9.3) it downloads every
name in its `"files"` list, compiles each `.py/.pyw` to reject a broken download, then swaps
them in. Rules that follow from this:

- **Every release must bump `version` in `version.json`.**
- **A new module must be added to the `"files"` list**, or installed copies never get it.
- File names must be flat (no folders): the launcher refuses names with `/`.
- New pip dependencies are NOT installed by the updater. Install them at runtime the way
  `install_tools()` in `cleanview.py` does (one-time, with a progress message), and also add
  them to `installer/install.ps1` for new installs.
- The app also checks for updates every 30 minutes and on F5 ("Update now" keeps the review
  in progress: it saves the session to `last_review.json` and reopens it after restart).

## Files

| File | What it does |
|---|---|
| `CleanView.pyw` | The tkinter UI (~1,950 lines). Start page (pick files/folder, filters, "Filtering for" age profiles, who reads the dialogue), progress, the review page (Found / All dialogue / Ask Claude tabs), done page. Update bar, session save/resume. |
| `cleanview.py` | The engine (~2,450 lines). `analyze()` finds everything and returns a JSON-able state dict; `render()` writes the clean copy and report with ffmpeg. Also picture/sound scanning, scene building, subtitle download and syncing, Claude/ChatGPT picture review, applying AI reviews and chat edits. |
| `cvcore.py` | Speech recognition (sherpa-onnx, NeMo Parakeet TDT 0.6B int8), word lists and `find_language()`, timing helpers, `snap_edges()` (move mute edges into silence), ffmpeg helpers. |
| `cleanview_ai.py` | Local AI: CLIP (ViT-B/32 ONNX) picture categories, NudeNet, audio tagging, speaker separation (pyannote segmentation + TitaNet via sherpa-onnx), and the Ollama helper (`qwen3-vl:8b` checks scenes, `qwen3:8b` reads dialogue; falls back to qwen2.5). |
| `cleanview_claude.py` | Claude through the **Claude Code CLI** (`claude -p --json-schema ...`, uses the user's Claude plan, no API key). Dialogue reading, the final "review everything" pass, the chat, picture review from contact sheets. Also the provider switch (`use("claude"/"chatgpt")`). |
| `cleanview_gpt.py` | ChatGPT through the **Codex CLI** (`codex exec ... --output-schema`), same interface as the Claude path. Strict JSON schemas (all properties required). |
| `cleanview_gemini.py` | Gemini through Google's **Gemini CLI** (`gemini -p ... -o json`, signed in with a Google account, no API key), same interface. Installed with npm (needs Node.js 20+). The CLI can't take a schema, so the shape is described in the prompt and the reply is checked (asked again once). The prompt goes in through stdin; pictures are copied into an empty work folder and named with `@picture1.jpg` on the command line. Chats are kept by CleanView (`APP_DATA\gemini\chats`), not the CLI. Provider key `"gemini"` (`cc.OTHERS`). |
| `cleanview_accounts.py` | Each person's own Claude, ChatGPT or Gemini sign-in inside CleanView ("Use a different account" / "Sign out" on the start page). Claude Code, Codex and the Gemini CLI keep their sign-in in a folder (`CLAUDE_CONFIG_DIR`, `CODEX_HOME`, `GEMINI_CLI_HOME`); CleanView's own is `APP_DATA\accounts\<ai>\<n>`, so the PC's own sign-in is never signed out or changed. A new sign-in goes in a new folder and is only used once it worked (`keep()`). With none, the PC's sign-in is used. |
| `cleanview_learn.py` | Learning from the user's choices per show (`learned/<show>.json`, key `show@profile`), Claude findings log (`claude_findings.csv`), exports ("Save what we refined…", "Send what CleanView learned…"). |
| `videoqueue.py` | Several videos at once: each video is watched and listened to (`analyze`) in its own worker process, "Videos at once" at a time. `Workers` (the window side) and `main()` (the worker, run as `CleanView.exe videoqueue.py <work>/queue_task.json`, one JSON line per message). Also `plain_error`, used by the window too. |
| `ollama_care.py` | Ollama only while the apps are open: out of Windows startup, stopped after the last one closes (same file as CleanListen's, plus `videoqueue.py` in `CLEAN_APPS`). Standard library only. |
| `shared_learned.json` | Built-in knowledge merged from users' exports; shipped with every update. Merged with `tools/merge_learned.py`. |
| `launcher.pyw`, `update.json` | Auto-updater (above). |
| `installer/` | `install.ps1`, `Install CleanView.bat`, `READ ME FIRST.txt`. Zipped by hand as `CleanView-Setup.zip`. |
| `tests/` | The test suite (see **Tests** below). Not shipped by the updater. |

## Tests

Run from the repo folder with the app's own Python (it has the packages the app imports):

```
"%LOCALAPPDATA%\CleanView\venv\Scripts\python.exe" -m unittest discover -s tests -v
```

(In PowerShell: `& "$env:LOCALAPPDATA\CleanView\venv\Scripts\python.exe" -m unittest discover -s tests -v`.)

- Plain `unittest`, nothing extra to install. Takes a few seconds; no models, ffmpeg,
  Ollama, Claude or internet needed.
- `tests/support.py` is imported first by every test file: it points `LOCALAPPDATA` at a
  throwaway folder **before** any app module is imported, so real settings, learned files and
  reviews are never touched, and it makes small made-up sample data (an old-style learned
  file, a sample review). Don't use anyone's real videos, learned files or reviews in tests.
- `test_learning.py`: learning only counts her own choices, the one-time clean-up of old
  learned files, hints vs her own choices in `apply_review`.
- `test_scenes.py`: the local AI's "can't see clearly" check and `merge_scenes`.
- `test_ui.py`: plain error messages, and the real window on the sample review (message boxes
  are faked): tick boxes, text size, the working page's list and time left, start-page
  ticks kept on close, "Review everything again" keeping ticks made meanwhile. A CleanView
  window flashes up briefly; these skip where there's no screen.
- `test_words.py`: word lists, bleeped subtitles (`unbleep`), phrases in `listed_word` and
  `find_language`, and subtitle words near other mutes (`already_muted`).
- `test_timing.py`: makes tiny videos with ffmpeg and cleans them with the real `render()`
  (a .ts whose clock starts at 10 s, an MKV whose sound starts 1 s late), and checks
  `snap_edges` on made-up sound. Uses the installed app's ffmpeg if none is on PATH;
  skips if there's none.
- `test_accounts.py`: signing in to another Claude/ChatGPT/Gemini account (a fake `claude`), and that the PC's own sign-in is used again after signing out.
- `test_own_exe.py`: CleanView.exe's description and icon, made once, not with Smart App
  Control on, and a failed try not used again.
- `test_freeze.py`: the freeze and crash notes, sending one in, and `_poll` under a flood.
- `test_reports_nov.py`: lessons from the November reports (long prompts through stdin,
  sound-only and talk-only scenes, misheard swears, names in the subtitles, a bare "God!").
- `test_reports_nov3.py`: the 2026-11-03 reports (subtitles that stop halfway, shorter and
  split scene cuts, a kept kind joined to another, "dickens", the launcher after an update).
- `test_at_once.py`: several videos at once in real worker processes with a stand-in
  engine: two run together, a third waits, a failure is said plainly and a crash only
  loses its own video, "Stop after", Cancel.
- `test_low_memory.py`: ffmpeg waits for memory, the AI helper lets go of its models,
  running out said plainly (also from a worker that crashed), the launcher without
  `update.json`.
- `test_answers.py`: saved Claude/ChatGPT answers (the asking itself is faked), and that
  contact sheets come out byte-for-byte the same each run.
- When fixing a bug, add a test that fails before the fix, and run the suite before every
  release.

## Pipeline (what `analyze()` does)

1. **Listen**: transcribe the dialogue channel (center channel on surround) to word timings
   (`st["asr"]`). Find words on the lists (`cvcore.find_language`).
2. **Subtitles**: use a matching `.srt` or embedded text track; otherwise download with
   `subliminal` (hearing-impaired first, title parsed from file/folder names by
   `guess_title()`), then re-time them to the heard words (`sync_cues`). Subtitles add names,
   missed words and sound descriptions.
3. **Sound**: audio tagger (CED mini, AudioSet labels) for gunfire, explosions, screams,
   blows, and, if "Turn down hard rock, metal and rap" is ticked, those music styles.
   `loud_music()` turns them into stretches with nobody talking (`st["quiet"]`), which
   `render()` plays at a quarter volume (`MUSIC_LEVEL`) with half-second fades. The tagger
   is unsure of music styles in a TV mix (a real rock song at the end of Castle S01E01
   scored 0.1-0.2), hence the low `ROCK_MIN`/`RAP_MIN` and needing 3+ windows to agree.
   Words heard while the tagger hardly hears speech are lyrics, not talking.
4. **Picture**: NudeNet twice a second, CLIP once a second for kissing, gore, fights, weapons,
   smoking, drinking, drugs, revealing clothes. Hits become scenes (several seconds of strong
   hits, dark frames ignored), then the local vision model double-checks each scene. With
   Claude/ChatGPT/Gemini it does that in the background while they read the dialogue
   (`closer_looks`, `in_background`/`wait_for`), so both AIs look but it doesn't take
   twice as long (Lauren 2026-10-29; one after the other looked like the same slow step
   twice to Jason). The local text model isn't used then, so the two never share the GPU.
5. **Voices**: speaker separation and a man/woman/child guess for each line.
6. **Dialogue filters** (sexual references, sleeping around, same-sex relationships and
   flirting, crude humor, bullying, religious conversations, rude words...): read by the
   local text model, or by Claude/ChatGPT if chosen, plus a short list of hard-to-mistake
   phrases (`LINE_WORDS`) that works with no AI. A line is flagged only if the model quotes
   the words that fit. A new one needs: `LINE_KINDS`/`DEFAULTS`/`LINE_WORDS`/`LINE_LABEL`/
   `OPT_TEXT` (cleanview.py), `LINE_TYPES`/`LINE_NAMES` (cleanview_ai.py), `TYPE_TEXT`
   (cleanview_claude.py), and `FILTER_KEYS`/`PRESETS`/a tick box/`CHIP` (CleanView.pyw).
7. **Cloud picture review** (if Claude/ChatGPT and "look at the picture" are on): contact
   sheets of the whole video (a still every 2 s, 20 per sheet) find missed scenes; 6 sharper
   stills per found scene confirm, relabel or rule it out (violence levels below); scene
   edges are refined with 30-still "bounds" sheets and snapped to shot changes.
8. **Final review** (cloud only): Claude/ChatGPT sees every found scene, line and word plus the
   whole numbered dialogue, settings and past choices, and returns remove / "just the word" /
   not an issue / can't tell, plus missed lines and scenes (`apply_review`).
9. The user reviews everything in the UI (all ticked items are what will be changed), can
   chat to change things live, then `render()` cuts scenes and mutes with ffmpeg (GPU encoder
   when available), and writes `Clean/<name> (Clean).<ext>` and
   `Clean/Reports/<name> - CleanView report.txt` (times shown in original and clean-copy time).

## Filters and the user's standards

- Profiles under "Filtering for": Young kids / Kids / Teens / Adults. Each has a standard set of
  ticks (`PRESETS` in `CleanView.pyw`), remembers her own changes, and learns separately
  (e.g. bullying filtered for kids, not for herself).
- Language groups: swearing, mild, God's name, minced oaths, same-sex words, rude words kids
  copy (stupid, dumb, idiot, shut up, "that sucks"...). "screw you" and "crap" count as
  language. "Suck" meaning "is bad" counts wherever it's said (`cvcore.suck_swear`,
  Lauren 2026-10-29); sucking something (a lollipop, a thumb, "suck it up") doesn't.
- "Jesus" and "Christ" said with reverence aren't muted as swears ("the love of Christ",
  "Jesus told us", "the gospel of Jesus Christ"); oaths still are ("Jesus!", "Christ, that
  hurt", "oh my Jesus"): `cvcore.reverent` (Lauren, from Jason's report on At Every Turn;
  the same rule in CleanListen 1.10.0).
- "What the" / "who the" / "what in the" just before a muted word is muted with it
  ("what the hell" goes whole; `cvcore.with_lead_in`), since it says what the word was.
- Her own words and phrases (start page box, one per line, every age; `opts["mywords"]`,
  read by `my_words()`): whole words and whole phrases, always muted, category "mine";
  passed as `mine` to `cvcore.find_language`/`listed_word` everywhere the lists are used
  (listening, subtitles, flagged-line masking, `apply_review`, the clean copy's subtitles).
- Slang that's only slang in a phrase ("grow some stones", "has the balls to") is matched
  as phrases (`cvcore.BODY_SLANG`), never the plain word. A listed word that's innocent next
  to a certain word ("pussy cat", "Moby Dick", "summa cum laude") is guarded with
  `INNOCENT_NEXT`/`INNOCENT_PREV`. Abbreviations that are also real words only count written
  as abbreviations (`ABBREVIATIONS`: "SOB"/"S.O.B." yes, a crying "sob" no). When adding a
  word, add its everyday uses to the tests too.
- Violence follows **VidAngel's levels**: Violence (non-graphic fighting, including cartoon
  slapstick); Graphic (blood and wounds, crime-scene bodies with blood); Gore (insides on the
  outside); Disturbing (violence outside combat: torture, execution, cruelty to the helpless).
  Crime scenes are Graphic, not Gore. Blood and injuries from an accident (a car crash, a
  fall) are Disturbing, never Violence or Graphic (Lauren 2026-10-30, The Blind Side). A
  killing that happens off screen but is clearly heard (Bambi's mother) is Violence.
- Sex drugs are sexual references (Lauren, 2026-11-04): Viagra, Cialis, "the little blue
  pill", erectile dysfunction, aphrodisiacs ("Spanish fly"), drugging someone for sex. In the
  word list (`LINE_WORDS["sexref"]`, only hard-to-mistake names) and in both readers'
  descriptions (`cleanview_claude.TYPE_TEXT`, `cleanview_ai.LINE_TYPES`).
- Nudity (actually shown) is separate from Implied nudity (sheets, towels, bare backs).
- Kissing: man & woman and same-sex, each keep / cut passionate / cut all.
- When one word is the only problem in a line, mute just the word, not the whole line. But
  jokes or innuendo mean the whole line goes.
- Holidays and birthdays: one "Holidays" tick box (option `holidays`, Lauren 2026-10-29)
  for Christmas, Halloween, Valentine's Day, Easter and St. Patrick's Day: `full_opts()`
  turns on each of `cleanview.HOLIDAYS`, which stay separate kinds inside (labels, AI
  definitions, picture categories). Old saved per-holiday ticks become the one box
  (`one_holidays_box` in CleanView.pyw). Thanksgiving is fine. Candles on a birthday cake
  are their own box. Ticked for Young kids and Kids, not Teens or Adults.
  For birthdays only the candles count (Lauren, 2026-10-29: parties, cake and "happy
  birthday" are fine), so it's just the candle lines, not whole conversations. The "Magic"
  section ("Magic and monsters") works the same way: Dark magic (witchcraft, wizards and
  witches doing magic, curses, the occult, seances, fortune telling; wizards are dark magic,
  Lauren 2026-10-29), Magic (spells, wands, potions, fairies; not stage tricks) and
  Vampires and werewolves (`vampires`; not vampire bats or ordinary wolves), `MAGIC` in
  cleanview.py and CleanView.pyw, also ticked for Young kids and Kids only.
  Each is both a dialogue filter (whole conversations, whole lines) and a picture category
  (CLIP descriptions + local vision check in cleanview_ai.py, `PIC_KINDS`/`PIC_TEXT`/
  `PIC_LABEL` for Claude's picture review). A picture category needs `CLIP_CATS`, `THRESH`,
  `MIN_FRAMES` and `LOOK` (cleanview_ai.py), `CAT_LABEL` and the list in `needs()`
  (cleanview.py); old saved picture scans without it are redone once when it's ticked.
- Religious conversations (off for every age unless ticked): any talk about God, faith,
  prayer, church, the Bible or any religion, including sincere prayer; whole conversations
  (`fill_conversations` joins lines found close together) and always whole lines
  (`WHOLE_LINE_TYPES`). God's name said as a swear stays the separate "deity" word group.
- Disrespect (`disrespect`, Lauren 2026-10-30): kids being bratty, talking back to, mocking
  or disobeying their parents and other grown-ups. A dialogue filter (whole lines, not
  whole conversations), ticked for Young kids, Kids and Teens. It's still flagged when the
  child learns their lesson later, but Claude/ChatGPT/Gemini say so in the line's "why"
  and the review's summary (or that they got away with it): `TYPE_TEXT` and `review()`.
- An AI may only mute a single word on its own if it is on the list of a word group that's
  ticked (`cvcore.listed_word(cats=)`, `_words_listed(groups=)`; 13 Going on 30 had
  "butts" muted with rude words off);
  otherwise it is offered unticked. Speech recognition mishears character names ("Grafi" for
  Gruffi) and those must never be muted.
- Slurs (`cvcore.NEVER_FINE`: "retarded" and its forms, racial slurs) are never "fine
  here": an AI's "not an issue" on one is ignored (`apply_review`), and it's never
  learned or shared as fine. The review is also told where each word came from ("heard
  in the sound" is really said, even when the subtitles leave it out). From Radio, where
  Claude unticked "severely retarded" and swears missing from the subtitles.
- A word said twice with only one heard is muted twice: each heard word stands for one
  subtitle word (`already_muted(used=)`, `after_same_word`), from "Bitty bitch!" twice and
  repeated song lines.
- A swear heard in the sound where the subtitles have a different word that sounds alike
  ("bitch"/Finch, Mitch; "fucking"/"bugging out"; Person of Interest, G.I. Joe) is offered
  unticked, with "Maybe misheard: the subtitles have ..." (`sounds_alike`). A mild word or
  minced oath written with a capital mid-sentence in the subtitles is a name or a title and
  isn't muted ("Cynthia Dern" 12 times in Castle, "Hell Hath No Fury": `name_in_subtitles`).
  A bare "God!", "God." on its own or "God," starting a sentence is an oath (`bare_god`)
  unless a prayer follows ("God, please help us").
- Sound alone isn't enough for a scene: one built only from screams, shouts or crashes is
  offered unticked (`SOFT_VIOLENCE_SOUNDS`; 17 such in Toy Story 4); gunfire, explosions,
  blows or subtitles that describe violence still cut. A "Sex scene" from explicit talk
  alone is offered unticked too (`TALK_ONLY`: the lines are muted on their own; a coroner's
  findings in Castle), and needs two different explicit words (`sex_score`: "thrust" said
  over and over in Chicken Run's flying talk).
- Subtitles that leave out a minute or more of talking (only "CD1" of a two-part
  download: Julie & Julia's stopped at 0:59 of 2 hours) are filled in from what was heard
  (`cleanview_ai.dialogue_lines`, `SUBTITLE_GAP`; lines marked `heard`), with a note in the
  review. Before, nothing said after that was read, and the chat couldn't see it.
- Scene cuts are as short as the trouble (Lauren 2026-11-03: "a shorter cut for all found
  scenes in general... that way you can tell more what is happening"; a 6½-minute cut of
  The Little Mermaid's ending). The bounds sheet now asks for the parts where the trouble
  is on screen (`scene_bounds` returns parts) and `refine_bounds` can shrink a cut or split
  it in pieces (the phone ringing and the cat after Julie & Julia's sex scene stay in). A
  fight runs from the first blow to the last, with a wider edge (`FIGHT_KINDS`), and a cut
  of 20 s or less (`SHORT_SCENE`) is only ever made longer, since a brief hit can fall
  between stills.
- "You usually keep these" only keeps a scene when she usually keeps every kind in it (a
  drinking scene joined to a sex scene left the sex scene in; `learn.apply`).
- Picture rules (`PIC_RULES`, local `LOOK`): cooking isn't violence (boiling lobsters, a
  small kitchen cut), nor is a comic fake injury in a parody; someone alone in a bath with
  only their shoulders showing, or a postcard of a couple's shoulders, isn't implied
  nudity; a mermaid's seashell top or a cartoon's swimwear isn't immodest (drawn
  characters are judged more lightly). "dickens" said as an oath is a minced oath ("how
  the dickens", "scared the dickens out of", "hurts like the dickens"), never Charles
  Dickens. From the CleanRead reports, the same in every app: "Camp Dick" (a WWI army
  camp), "a tiny prick of black", "a strip of sod", "God knows best" and "Lord, help me to
  trust" (a prayer) aren't swears (`INNOCENT_PREV`, `KNOWS_NOT_OATH`, `HELP_NOT_OATH`).
  Prayers Lauren kept in Wings of a Dream (2026-11-04) aren't oaths either (`prayer()`):
  "Oh God. Help me know what to do", "Please, please, dear Jesus", "Had I let Jesus
  illuminate my path", "that I call You my God" / "You are my God", "Please, dear God".
  "Oh Lord Jesus." she left marked, and "Oh God, help me, I'm going to be sick" or "Look at
  you! My God" are still oaths.
- Long prompts go to the Claude CLI through stdin (`LONG_ARGS`): Windows refused the final
  review's command line ("WinError 206", Clue). With no AI reading the dialogue, the review
  says plainly that the dialogue choices were only checked against a short list (Enchanted).
- No captions on clean copies (the subtitle track is included but not default; no sidecar
  .srt).
- She always reviews before anything is cut, and her own ticks are never undone by an AI.

## Known weak spots / ideas worth improving

These are where results have been wrong in real use. Improvements here matter most.

1. **Scene edges.** Cuts often start late or end a few seconds early (e.g. a fight's last
   blow survives). Current fix: bounds sheets + snapping to shot changes. Could use better
   shot/scene segmentation, audio cues, or padding by scene type.
2. **Picture-only scenes when there is no Claude/ChatGPT.** The local CLIP + NudeNet + qwen3-vl
   path misses or over-flags a lot (e.g. implied vs actual nudity, crime scenes as gore,
   cartoon fights). The cloud picture review is much better. Better local models or smarter
   thresholds would help users without Claude.
3. **Run-to-run consistency.** The cloud model isn't deterministic, so the same episode gave
   different cut lists each run. Since 1.11.6 every one-off question to Claude/ChatGPT is
   saved in `APP_DATA\answers` (keyed by provider, model, prompt, input, schema and the
   pictures' bytes; newest 3,000 kept), so the same question gets the same answer. Chats are
   never reused, and "Review everything again" asks afresh (`fresh=True`). Anything that
   changes the question (her past choices, settings, different local finds) still asks again.
4. **Subtitles.** Downloads depend on `subliminal` and on parsing show/season/episode from file
   names. Windows Smart App Control blocked chardet's compiled (`__mypyc`) parts; the app now
   switches chardet/charset-normalizer to their pure-Python wheels (`subtitle_finder_loads`).
   Watch for other blocked compiled packages.
5. **Size of the code.** `cleanview.py` and `CleanView.pyw` are large single files with lots of
   shared mutable dict state (`st`). Refactoring is welcome but the update rules above apply
   (flat file names, add new files to `version.json`).
6. **Tests.** `tests/` covers learning, `apply_review` hints, the local "unclear" check,
   scene merging, the main UI fixes, word lists, mute timing and `render` on tiny videos,
   and saved answers. Still missing: `word_mute`, `sync_cues`, the picture scans, and
   `guess_title` on real file names. Earlier testing also used fake `claude`/`codex`
   scripts on PATH that return canned JSON.
7. **Speed.** A 22-minute episode takes a long time with every check on (speech, picture,
   voices, local AI, then cloud picture review of ~700 stills). Batching, skipping work that
   isn't needed for the chosen filters, and reusing results between runs could help.
8. **CleanListen parity.** Features added here (age profiles, rude words, word-only mutes,
   live chat edits, exports) are wanted in CleanListen too.

## Words and filters in every app (Lauren's rule, 2026-10-28)

Every change to words, phrases, guards or filters goes into all three apps: CleanView
(this repo, `cvcore.py` + `web/words.js`), CleanListen and CleanRead (both in
`BookWorm824/cleanlisten`, on this PC at `Downloads\cleanlisten`; CleanRead uses
CleanListen's lists through `import cleanlisten`, but some things are off for it, e.g. the
"what the" lead-in, so check it too). Make the change here, then pass it to the CleanListen
session (or do it there) with the exact patterns, guards and everyday uses to test.
`tests/test_cleanlisten_words.py` runs every quoted phrase in both repos' tests through both
word finders and fails on any difference that isn't listed as on purpose (`SLANG_WORDS`,
`CL_ONLY_SEXUAL`, `CV_ONLY`) or as waiting for CleanListen (`WAITING_ON_CLEANLISTEN`; it
fails again when one is fixed there, so the list stays true). New filter tick boxes count
too: a filter added here is wanted in CleanListen and CleanRead.

## Releasing

1. Make the change, run the tests, bump `version` in `version.json` (and add any new file to
   `"files"`).
2. Commit as `BookWorm824 <morganscorner93@gmail.com>` and push to `main`. Installed copies
   pick it up within a few minutes (the raw GitHub CDN can lag ~5 minutes).
3. Tell Lauren in one or two plain sentences what changed and to press F5 / "Update now".
4. The installer zip is only rebuilt for new installs (e.g. for her sister).
