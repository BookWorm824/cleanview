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
  only applies as the window is built, so changing it restarts CleanView. Give fonts in
  points (`(FONT, 10)`) and wrap widths through `wrap_width(px)` so both follow it.
  Never give a local variable the name of a module helper a function calls (1.11.7 named a
  box `wrap` in a function calling `wrap()`, and the review page failed to open);
  `test_ui.NoHiddenNames` checks for this. Tick boxes
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
  post the file to the CleanView inbox, a Google Apps Script web app in the owner's Google
  account (`tools/cleanview_inbox.gs`, setup in `tools/README-inbox.txt`; its address is
  `cleanview_learn.SEND_URL`, and CleanListen uses the same one). Files land in the Drive
  folder "CleanView learned"; merge them with `tools/merge_learned.py`. No internet or "not
  now": the old "saved here, attach it" message. Tests point `CLEANVIEW_INBOX` at nothing
  (`support.NO_INBOX`) so they never send to the real one.
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
   hits, dark frames ignored), then the local vision model double-checks each scene.
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
  copy (stupid, dumb, idiot, shut up...). "screw you" and "crap" count as language.
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
  Crime scenes are Graphic, not Gore.
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
- An AI may only mute a single word on its own if it is on a word list (`cvcore.listed_word`);
  otherwise it is offered unticked. Speech recognition mishears character names ("Grafi" for
  Gruffi) and those must never be muted.
- Slurs (`cvcore.NEVER_FINE`: "retarded" and its forms, racial slurs) are never "fine
  here": an AI's "not an issue" on one is ignored (`apply_review`), and it's never
  learned or shared as fine. The review is also told where each word came from ("heard
  in the sound" is really said, even when the subtitles leave it out). From Radio, where
  Claude unticked "severely retarded" and swears missing from the subtitles.
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
