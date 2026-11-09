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
- Jason's That Thing You Do runs (2026-11-05, 1.18.20): without an AI his chat notes reach
  nothing (word lists, NudeNet and the sound tagger can't read them), so what he chooses has
  to stick by itself: her own choices on a video's scenes are kept per file
  (`learn.record(video=)`, `d["videos"]`, matched by overlap and kind) and win on the next
  scan; a line unticked with a word in it muted is learned as `word_only` and starts that way
  (`learned_word_only`); "Santa" before a place name and "Christmas Island" aren't
  Christmas (`SANTA_PLACES`); subtitles that only say screaming/gasping/a thud are offered
  unticked (`SDH_HARD_VIOLENCE` cuts); the AI helper's flirting check gets the notes and
  its "two men"/"two women" yields to its own sentence naming a man and a woman
  (`_between_checked`).
- His next runs (2026-11-06, 1.18.21): a line kept on an older version and then muted just a
  word of is learned as `word_only` too (the line starts unticked then, not by him: "Jiminy
  Christmas"); a scene set as she chose before loses its "(not double-checked, ...)" and the
  note says "Ticked to cut again" instead of counting it as "left unticked" (`UNSETTLED`);
  an unchecked picture scene says "so only cut if you tick it", which stays true when it's
  ticked. One moan or pant in the subtitles near bare skin is offered, not cut (`ONE_MOAN`;
  The Resident S3: an injured patient, a girl singing in surgery). The "double check" he kept
  asking the chat for is the AI helper's second look, which he has off.
- The title on the progress page (1.18.22, Jason): the video's name without ".m4v", big and
  bold (`self.which`), instead of small grey text. With one video, CleanView's logo sits in
  the empty space below (1.18.23, Jason: "a lot of dead space"; `logo_png` takes the PNG out
  of `cleanview.ico`, so no PIL is needed).
- "Claude's findings on this video" (the Ask tab, 1.18.23, Jason: it had every movie he'd
  done) writes `Findings for this video.csv` with only the videos on the review page
  (`learn.findings_rows(videos)`/`write_findings`); `claude_findings.csv` still has them
  all, newest first.
- A clean copy that won't save (1.18.24, Jason's Snow White, 2026-11-07: four times at
  about the same spot, and nobody could see why; a made-up 83-minute copy with his cuts
  saved fine, so it's his file or PC): after every encoder fails, `render` tries once
  more the careful way (`build(careful=True)`: `-err_detect ignore_err`, `-fflags
  +discardcorrupt+genpts`, `-max_muxing_queue_size 9999`, no subtitles; the report says
  so). `save_trouble` says a full drive, a 4 GB (FAT32) drive or a locked file plainly
  instead; the error keeps every encoder's message, and the window offers to send it in
  (`_tell_save_failed`, kind "problem"). It was a full drive.
- Where it saves and the room there (1.18.25, Jason: "being able to tell it where to save",
  "estimate how many megabytes the clean copy will take... show it in the screen"): beside
  "Save clean copy" the review page says where it saves, about how big it'll be and how much
  is free there (red when it won't fit), with "Change..." (`_show_space`,
  `_change_save_folder`; it follows the cut ticks). `engine.clean_size`: the original's size
  without cuts (copied), with cuts the bigger of that share of it and 0.07 bits a pixel at
  24 fps (made again at a set quality). Saving asks first when there isn't the size plus a
  tenth and 200 MB free (`_room_to_save`, `room_needed`: choose a folder / save anyway /
  back).
- More than 100 mutes (1.18.26, Jason's Shawshank Redemption, 2026-11-07: every way of
  saving failed and it said the PC ran out of memory; Task Manager said 33%). ffmpeg won't
  read more than 100 terms added up in a row in one expression, and says "Cannot allocate
  memory". `_sum` brackets them in groups of 50 (good for about 2,000), and mutes and the
  quieter music get a filter for each 500 (`_mute_filters`, `_chunks`; tested to 20,000).
  The same in `cvcore._ranges`, which CleanListen shares. `videoqueue.memory_trouble`
  doesn't count ffmpeg's filter errors as running out of memory.
- Jason's Shawshank review (1.18.27, 2026-11-07, word lists only, no AI): four of the five
  "gunshot-like bangs" were cell doors, a typewriter, sobbing and a door. The tagger now
  also listens for those (`LOOK_ALIKE_SOUNDS`); in a window where one is heard more clearly
  than the gunfire or hitting (`MISTAKEN_SOUNDS`), it isn't counted. Older sound scans are
  redone once when violence is ticked. "the hardest screw that ever walked a turn" (the
  guard) isn't "screw that" (`screw_noun`: after "-est" words, "any", "no", "another",
  "prison"...). His 0:58:07 untick was Brooks's knife at Heywood's neck: his choice, not a
  false alarm. The Sisters/Bogs lines, the playing cards and "the Sodomites" were taught
  (sexref); "a bag of reefer" has no dialogue filter (drugs is picture-only).
- "queer" meaning strange (1.18.28, from CleanRead's The Boxcar Children report): not a
  same-sex word before "noise", "way", "look", "feeling", "sort", "fish"... or after
  "rather", "very", "looked", "seemed", "feel"... (`INNOCENT_NEXT`/`INNOCENT_PREV`, and in
  `web/words.js`). CleanListen's finder already left these alone; CleanRead offers them
  unticked as "older meaning". "you queer", "he is queer", "a queer couple" still count.
- Gunfire cuts from the first shots to the last (1.18.29, G.I. Joe: Retaliation clips
  Lauren sent, 2026-11-08): quieter shots under the music just before or after found
  gunfire (`EDGE_GUNFIRE`, top sound in `GUNFIRE`, not a look-alike heard better) widen
  that cut; they never make one alone. The shooting at the car started 3 s before the cut.
  Her gunshot training sounds and 2,000 everyday sounds (ESC-50) showed the sound check
  already leaves doors, knocks and typing alone (`test_gunshots.py`).
- Lauren's West Side Story report (1.18.30, 2026-11-08, AI helper, no Claude): "West Side
  Story.m4v" has no year, so every movie of that name scored the same online and the 2021
  remake's subtitles came first (22% lined up, none used: "every last buggin' gang" was
  heard as a swear, and the slurs went unheard). When the first subtitles don't line up,
  the best of each movie (name and year, hearing-impaired first) is tried in turn, up to
  `SUB_TRIES`, once per video (`other_subtitles_tried.txt`; `subtitle_order`,
  `other_subtitles`, `pick_subtitles`); the 1961 film's lined up 89%. Slurs added (strong,
  never fine): spic, Polack, wop, greaseball ("spic and span", "doo wop" and "a wop bop"
  aren't). "gay" beside another happy word ("pretty and witty and gay", "merry and gay") is
  the old word for happy (`gay_happy`). Taught (sexref): "'Cause your ma's hot for me", "Go
  walk the streets like your sister", "How's the action on your mother's side of the
  street"; a title note says the rumble's knife fight, Anita's attack and Tony's shooting.
  The local picture checks found only the last of those (weak spot 2).
- Lauren's Red Eye report (1.18.31, 2026-11-08, word lists only, adults): every mute was
  right; the picture check's nudity, kissing and gesture scenes were false (the film has
  none) but all offered unticked, and left so. Missed: "Well, thanks for the quickie"
  (sexref), now in `LINE_WORDS` (not "quickie" alone: "a quickie divorce" is a line she
  kept). `LINE_WORDS["samesex"]` leaves "gay" beside a happy word alone too, like the word
  lists (`cl.GAY_HAPPY`).
- The chat looks at the picture (1.18.32, Lauren 2026-11-08: told "near the beginning they
  are holding hands", it said it only sees the dialogue and cut a whole 49-second visit;
  told "you are supposed to view photos as well", it said so again). Its answer can ask to
  see stretches (`look_at`, up to 20 minutes, `cc.look_spans`); `cc.see` shows it stills
  every 2 s (`engine.chat_sheets`: the whole video's sheets when the picture was looked
  through, else just that stretch, 12 sheets a request) with what's said then, and its second
  answer makes the changes (cut just the tiles it's in). The chat hears what it saw next turn
  (`st["chat_seen"]`). The picture check could only report two women kissing: "couple
  affection" (holding hands, cuddling, an arm around each other) is asked for whenever the
  same-sex filter is on and becomes "Same-sex affection · two women/men"; a man and a woman
  isn't. Judged by context (Lauren: "hand holding needs to be done by context"): a parent and
  child, friends, comforting at a hospital bed or praying together are fine. Cloud only; the
  local picture check doesn't look for it (weak spot 2).
- Lauren's Person of Interest reports (1.18.33, 2026-11-08, Claude, adults): S02E07 on 1.18.32
  cut the wives hugging (7:02) and holding hands (7:48), found by the picture check; nothing
  changed by her. S02E11-E22 (1.18.28): every listed word muted, Claude's keeps were
  mishearings ("SOP", "shoot", "eye"). Her one untick, "Your lovely wife and two little girls"
  (flagged as romance; Finch reading out someone's details), is taught as a false alarm. Its
  chat kept a note for everything ("a line that just mentions someone's wife, family or kids
  ... is not a problem line"), so a built-in general note says a same-sex couple's "wife" or
  "husband" line still counts. Taught: "I got a date with a sock", "There was a stripper pole
  in that thing", "those lips taste like the chocolate mints" (sexref), "Mom left because you
  cheated on her" (casual).
- Lauren's 50 First Dates report (1.18.34, 2026-11-08, teens, word lists only): "No
  subtitles", so the film's crude jokes went through. The name parser made "50 First
  Dates.m4v" episode 50 of "First Dates"; movies are now looked up as movies (`sub_video`:
  the parser's answer when it says movie, else `subliminal.Movie` with any "(year)"). And
  OpenSubtitles' search finds nothing for a title starting with a number ("50 First Dates",
  "13 Going on 30", "21 Jump Street") but does for "Fifty First Dates" and "Thirteen Going on
  Thirty": when no subtitles of that title turn up, the numbers are spelled out
  (`number_titles`) and only subtitles of the same movie are kept (`_same_title`, not "Fifty
  Shades"). A "none online" remembered by an older version is looked up again
  (`remembered_miss`, `SUB_LOOKUP`). "nympho"/"nymphomaniac" are moderate words (not
  "nymph"); "penis" and "private parts" are in `LINE_WORDS["sexref"]`. Five of the film's
  jokes are taught (sexref). Her two unticked sound scenes ("heavy bangs" in a bar, "gunshot-
  like bangs" at the dock) were false alarms, kept for that file (weak spot 2).
- Lauren's A Walk to Remember report (1.18.35, 2026-11-08, adults, word lists only): every
  listed word muted (the "Damn Shame" song too), prayers and hymns left alone. Taught (sexref):
  "any excuse for you to pull that thing out", "ready to get his freak on", "she might put it
  on a brother". The local picture check found three real kisses (kissing set to "cut all")
  but, not double-checked, offered them unticked, and they stayed so.
- Clean copies of surround videos play on a Roku (1.18.36, 2026-11-08): Lauren's "Til Death"
  (Person of Interest) kept its 5.1 sound as 5.1 AAC, which her Roku can't play itself, so
  Jellyfin converted it while streaming and the Roku kept quitting (Chrome played it; the
  stereo "Critical" played fine). A copy of anything with more than 2 channels now has a
  stereo AAC track first, the default (`STEREO_RATE`), then the surround one, not default,
  named "Stereo" and "Surround 5.1" (`title` and, for MP4, `handler_name`). Both get the same
  mutes and cuts. Copies saved before this keep their 5.1 only; cleaning again fixes them.
- Lauren's I Love Lucy report (1.18.37, 2026-11-08, teens, word lists only): "I Love Lucy 1 -
  Ep. 1.m4v" is now season 1 episode 1 (`guess_title`: "<show> <season> - Ep. <n>"); it was
  looked up as a movie of that name (subtitles 4% lined up) and learned under movies. Her
  DVD's first episode is the unaired pilot, not the aired S01E01, so its online subtitles
  still won't line up (and aren't used). "Let's get Valentine." was muted as Valentine's Day:
  a lone "Valentine" is a name; `LINE_WORDS["valentine"]` wants valentines, valentine's,
  cupid, "valentine day/card/party..." or "my/a/your/his/her/secret valentine".
- Lauren's Castle S1E1 report (1.18.38, 2026-11-08, adults, word lists only): the shared lessons
  had 8 of the episode's lines (from subtitles), but this run read what was heard, worded or
  split a little differently, and only 1 matched exactly. Learned lines to mute now also match
  (`learn.LearnedLines`) when the learned line is all inside a longer one, when the line is
  most (60%) of a learned one, or when a word or two differ (token similarity 0.85); the first
  two only for learned lines of 7+ words (a short everyday line stays exact), and a small piece
  ("You do know I'm wearing a gun?") never. 10 of the episode's lines match now; none wrongly in
  her other reports. She ticked "Hell" in "right out of Hell Hath No Fury" both times it was
  left unticked as a title, so `name_in_subtitles` never takes "Hell" for a name, and the
  shared Castle note says so. Her unticks: a door ram as "gunshot-like bangs" and a "nudity"
  scene that was a dinner invitation (weak spot 2); "Anyone make you their bitch?" just the word.
- "bondage" and "safe word" are sexual references (1.18.39, Lauren 2026-11-08, from Castle's
  "Bondage. My safe word is 'apples.'"): `LINE_WORDS["sexref"]` (no AI needed), not
  bondage as slavery ("house of bondage", "freed from bondage", "sold into bondage", "the
  bondage of sin") or "a safe word to/for ...". CleanListen mutes them as words
  (`CL_ONLY_SEXUAL`).
- Lauren's Castle S1E2 report (1.18.40, 2026-11-09, teens, word lists only): she asked the chat
  to mute just the words, not whole lines (a coroner's "she had sex", "condoms", "affair"), and
  it did, keeping a note for everything she cleans. Its phrase "explain how that works later"
  was squashed into one word by `word_mute` ("explainhowthatworkslater"), not found in what
  was heard, and only 1.2 s around its middle muted. A phrase is now found word by word in what
  was heard (up to 12 words, stopping once it can't match) and muted from its first word to its
  last; placed by its position in the line, it covers all of its words; `raw` keeps the spaces.
  Old squashed words learned before still match.
- The short no-AI list mutes just its words (1.18.41, Lauren 2026-11-09: "Just the word", after
  switching Castle S1E2's 22 lines by hand): a line found only by `LINE_WORDS` for sexual
  references or sleeping around (`LIST_WORDS_ONLY`) gets each word it matched muted
  (`list_words_only`, through `word_mute`; "had sex" -> "sex", "having an affair" -> "affair",
  `LIST_WORD_TRIM`) and starts unticked ("tick to mute the whole line"). Lines an AI flagged,
  other dialogue filters (holidays, magic, religion...), learned or hinted lines, and lines
  where a word can't be placed stay whole. CleanListen already mutes these as words.
- The PC stays awake while videos are watched, listened to or saved (1.18.42, 2026-11-09: a
  CleanRead book paused nine hours overnight when Windows went to sleep; the owner, in the
  CleanListen session: "Yes, add it. to clean view also"; CleanListen/CleanRead 1.17.8 do the
  same). `engine.keep_awake()` calls `SetThreadExecutionState(ES_CONTINUOUS |
  ES_SYSTEM_REQUIRED)` and clears it (`ES_CONTINUOUS`) on the same thread, also on an error;
  `_analyze_thread` (its worker processes run under it) and `_render_thread` hold it. Idle
  sleep only: the screen may turn off, and the lid or power button still sleeps.
- Claude learns from her, not from itself (CleanListen 1.15.3, Blue Ridge, 2026-11-05):
  `learn.examples` (what the dialogue readers and the final review are shown as "they have
  muted / chose NOT to mute") holds only her choices and the shared ones, never
  `claude_muted`/`claude_kept`; `tools/merge_learned.py` no longer puts Claude's verdicts
  in the shared lines either. (Claude's past "fine" is still a hint on the review page.)
- A part of Claude's dialogue reading (500 lines) that fails is asked once more; if it fails
  again its lines go in `unread` and the AI on this PC reads just those (`find_lines`), the
  rest of Claude's reading is kept, and the report says which parts. The first two parts
  both failing still means it isn't working: the error is raised as before.
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
- `test_reports_nov6.py`: Jason's word-only after an old keep, remembered scenes' wording,
  one moan offered, the Resident S3 lessons and the drug store note built in.
- `test_title_big.py`: the progress page's title is the name without the extension, big
  and bold.
- `test_jason_nov7.py`: the findings spreadsheet for just this video, newest first, and
  the logo on the progress page.
- `test_save_fails.py`: the careful last try, plain reasons from ffmpeg's errors, and
  offering to send in what went wrong.
- `test_save_space.py`: the size estimate, the save folder and room on the review page,
  and asking before saving when it won't fit.
- `test_many_mutes.py`: saving with 150 mutes and 120 cuts, the bracketed groups, and
  ffmpeg's "Cannot allocate memory" for a filter not said as running out of memory.
- `test_shawshank.py`: doors, slams, a typewriter and sobbing heard more clearly than
  gunfire aren't gunfire; real gunshots and screams still count; older scans as before.
- `test_gunshots.py`: real gunshot sounds Lauren sent (the tagger's scores in
  `gunshot_sounds.json`, also with noise under them) stay cut as violence, and the G.I. Joe
  clips (`gunfire_clips.json`) are cut from the first shots to the last. Two she sent
  ("cap gun", "chop") aren't found by sound: counting those labels or matching against
  these gunshots cut soda cans, clapping, glass and footsteps among 2,000 everyday sounds
  (ESC-50, tested on this PC only), which also showed no doors, knocks or typing cut.
- `test_chat_looks.py`: the chat asks to see a stretch and cuts what it saw, its stills,
  and same-sex couple affection in the picture, by context.
- `test_person_of_interest.py`: the Person of Interest lessons and the same-sex "wife" note.
- `test_fifty_first_dates.py`: movies looked up as movies, numbers spelled out for the
  subtitle site, an older "none online" asked again, "nympho" and the lines built in.
- `test_walk_to_remember.py`: its lines built in, its prayers left alone.
- `test_stereo.py`: a 5.1 video's clean copy has stereo first (default) and the surround
  second, both muted and cut, in MP4 and MKV; a stereo video keeps one track.
- `test_i_love_lucy.py`: "<show> 1 - Ep. 1" names, and a lone "Valentine" as a name.
- `test_castle_s1.py`: learned lines worded or split differently still muted, a harmless
  piece or a short everyday line not; "Hell" in a title.
- `test_bondage.py`: "bondage" and "safe word" as sexual references, not slavery.
- `test_castle_s1e2.py`: a phrase muted from its first word to its last, heard or placed.
- `test_list_words_only.py`: the no-AI list mutes just its words; what an AI found, other
  filters and learned lines stay whole.
- `test_keep_awake.py`: set and cleared on the same thread (also after an error), never the
  display; watching and saving hold it.
- `test_west_side_story.py`: other subtitles tried when the first don't line up (each
  movie of the name gets a turn, downloads stop once some do), the lines and note built in.
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
  isn't muted ("Cynthia Dern" 12 times in Castle: `name_in_subtitles`), except "Hell", which is
  still the word in a title ("Hell Hath No Fury": she ticks it, `SAID_IN_TITLES`).
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
