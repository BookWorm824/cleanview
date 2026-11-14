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
  `Go.TButton` (Pick up where I left off, Set up and sign in; Choose files… is a fifth
  bigger, `Choose.TButton`); the grey
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
- Lauren's Castle S1E5 report (1.18.51, 2026-11-09, adults, the AI helper): "affair" went
  through in four lines. The short list only had "having/had an affair" and "an affair with";
  `LINE_WORDS["casual"]` now also has "the/an/his/her/their/love/secret... affair" (one affair:
  not "Internal Affairs", "none of your affair", "quite an affair", "the affair of ...";
  `LIST_WORD_TRIM` cuts each to "affair"). And in two lines learned to mute whole she unticked
  the line, which left the word playing: `list_words_only` now also mutes the list's words
  inside lines muted whole (learned, an AI, other filters), so unticking the line keeps the
  word muted (she chose "Just the word" in S1E2). Her learned file (2026-11-09) was gone over:
  its movie lines were from reports already checked (the rest were short filler, never
  taught) and its chat notes are hers; taught from it: two Castle lines (a coroner's "could
  have been a rape", "webcamming"), two for teens ("then we slept together", "in it for the
  sex") and a Castle note on "conquests". Not taught: "Sex like these are designed..." (heard
  for "Sites"), the affair lines she wants as just the word. Her one more miss, a coroner's
  "it wasn't a sexual assault", isn't on any list.
- A long muted stretch is cut instead of left silent (1.18.60, 2026-11-12; the owner: "if
  something that is muted, is longer then 4 seconds, go ahead and cut the scene so its not a
  long gap of silence"). `render` joins the ticked mutes (lines and words) across pauses under
  `LONG_MUTE_JOIN` (0.75 s) and cuts each stretch of `LONG_MUTE_SECS` (4) or more that's at
  least `LONG_MUTE_SHARE` (85%) muted (`long_mutes`); words muted one by one with talking
  between them stay muted words (a first try joining across 1 s cut almost all of a test
  video with a word muted every 0.8 s). The report says how many were cut and lists each
  "CUT 6 seconds instead of a long silence (muted lines or words)"; the review page's size
  estimate counts them (`_clean_bytes`). A copy that had only mutes is now made again (not
  copied) when it has one, so saving takes longer. Past reviews on this PC: 218 such
  stretches in 125 videos (1.7 a video, 27.6 minutes in all).
  Also measured then: "Videos at once" with the AI helper on (two 44-minute The Resident
  episodes, from scratch): 2 at once 14.7 min, one after the other 19.2 min, the same closer
  looks; each video is slower at once (13-15 min against 9-10) but both are done sooner, so
  the default of 2 stays.
- The language picked is checked against what was heard (1.18.91, 2026-11-14; the owner
  cleaned Monsters University set to Spanish "to see what it did", then "switch and say so").
  On 1.18.89 the model for other languages heard its English word for word, the Spanish lists
  found nothing (10 English words, "jerk", "fools", "dang"..., went through), Spanish subtitles
  were looked up and didn't line up (1%), the AI helper was told the dialogue was Spanish, and
  nothing said so. Now, picked another language than English (not Auto), `analyze` tells what
  was heard with `cvlang.which_language` right after the listening: when it's clearly another
  language CleanView cleans it's cleaned as that one (`o["language"]`, and
  `o["language_switched"]` the one she picked; English is listened to again with English's own
  model, `en_model`, kept as `transcript.json`; the subtitles are looked for again in that
  language once the first look has ended, since `fetch_subtitles` names its files by
  `cvlang.LANG`), and the note says "You picked Spanish, but this video is in English (from
  what was heard), so it was cleaned as English." A language CleanView doesn't clean is only
  said ("This sounds like German, which CleanView doesn't clean yet, so only the Spanish word
  lists you picked were used."). Picked English it isn't checked: English's model hears every
  language as English. Her review's eight scene cuts (three "Christmas", "St. Patrick's Day",
  "Magic" for the glowing blurchin, four gunfire-like sounds) look like false alarms from the
  local picture and sound checks (weak spot 2); not taught (she didn't untick them).
- Preview opens one player (1.18.91, 2026-11-14; the owner: "it can take a few second to open
  the player, so if you think it not opening you can click preview again and it opens a 2nd
  player. it should only open one"). While the clip is made and for `PREVIEW_OPENING_SECS` (6)
  after it's handed to the player, the button says "Opening…" and Preview (any) does nothing
  (`_previewing`, `_preview_done`, `_preview_text`); a preview that fails says so and can be
  pressed again.
- Nothing a test does shows on her screen (2026-11-14; the owner: "can you keep everything from
  keep popping up while you are making changes? only fully pop when absolutely necessary",
  after the play-only copy's run opened five Notepads: `test_check_failed`'s stand-in answered
  "yes" to "Open that file now?", and CleanView's own suite took the same path).
  `tests/support.py` draws every `tk.Tk`/`tk.Toplevel` see-through (`-alpha 0`, so sizes are
  measured as usual), notes instead of opening files and folders (`support.OPENED`:
  `os.startfile`, explorer, notepad), silences `winsound`, and `support.HIDE` goes first in code
  a test runs in another Python (test_one_window's stand-in windows).
- Lauren's Selena report (1.18.90, 2026-11-13, adults, the AI helper, made on 1.18.86; the
  movie with "some english and spanish in it", cleaned as English). Every listed word muted;
  the Spanish in its subtitles is a few friendly words ("corazón", "mi hijo", "niña") and its
  Spanish songs aren't subtitled, so the short Spanish list (1.18.86) had nothing to catch and
  nothing got through that can be seen. Her three chat corrections are built in as general
  notes for everyone (her "Yes, build them in"; a "CleanView reviewed" file through
  merge_learned.py): a parent and child singing loving words is family, not a romance (13:01,
  Abraham singing with his daughter, cut as "Same-sex romance · two women"); a couple only
  talking in bed isn't an intimate scene (19:19); a performer on stage isn't a sex scene, even
  with a moan in the subtitles (1:55:08). Not fixed: two kisses labelled "Kiss · two women ·
  passionate" (55:29, 1:14:52) look like Selena and Chris; cut anyway under her settings
  (passionate kisses of both kinds), but the picture check's man/woman guess was wrong. It
  took 102 min on her laptop (reading the dialogue 33, each conversation 28, closer look 12,
  voices 10, picture 9, listening 9; 1,740 lines).
- Auto works the language out (1.18.89, 2026-11-13; the owner: "we have a tab now to check
  different languages, but what if the person doesn't know it, would it be possible to have
  an "auto" tab", then "do auto clean"). "Auto" is the second choice in step 1's drop-down
  (`cvlang.CHOICES`, `AUTO`, `choice()`); English is still what the page starts with, because
  Auto needs the listening model for other languages even for an English video
  (`needs_model`). `analyze` on Auto calls `tell_language` right after `probe`, and from
  there on it's as if she had chosen that language (`o["language"]` is the one worked out,
  `o["language_auto"]` how; a note says "Auto took this for Spanish (from what was heard).").
  1. The sound track's own label (`cvlang.tag_language`: eng/spa/fre/por/rus...); on Auto
     `probe` takes the video's own main track, not the English one.
  2. No label: `language_sample` hears 30 s at 20%, 50% and 80% of the video (two more spots
     if under 60 words) with the model for other languages, and `cvlang.which_language`
     tells by each language's everyday words (`LITTLE_WORDS`): accents ignored, a word only
     one language has (`OWN_WORDS`) counts three times, Cyrillic is Russian (Ukrainian by
     its own letters). The model's own Spanish sample was taken for Portuguese until then.
     Under 15 words only a very clear case is told; when it can't tell, English.
  3. A language CleanView has no lists for (a label like ger/jpn, or German or Italian
     heard) is a `VideoError`: "... is in German, which CleanView doesn't clean yet. To clean
     it anyway, pick a language yourself in step 1."
  Kept in `<work>/language.json`. Checked: the model's es/fr/en samples told right and its
  German one refused, a whole clean on Auto of the Spanish one, and the stretches Auto would
  hear in all 146 past reviews here (English): every one English. Not checked: real
  Portuguese or Russian speech, or a film that mixes languages (it gets the one heard most;
  cleaning both in one video is still "the other option later"). Videos cleaned together on
  Auto can differ: `render`, `apply_chat` and `claude_review` set the language of the video
  they work on (`_language_of`); the review page itself uses the first video's.
- Portuguese and Russian (1.18.88, 2026-11-13; the owner: "can do both portuguise and russian
  now"), the last two of the "easier group". `cvlang.PT` (Brazil and Portugal; accents come
  off, a hyphen joins: "foda-se" is "fodase") and `cvlang.RU` (Cyrillic, ё written as е
  through `SAME_LETTER`; accents are NOT taken off, й would become и; built on the few roots
  the swearing uses, e.g. `ху[йяеию][а-я]*`, `[а-я]*пизд[а-я]*`, prefix + `еб...`), each
  with phrases and guards. Left off as mostly innocent, Portuguese: puto (a boy in
  Portugal), pau, pica, bicha (a queue), veado, piranha, cadela, corno, burro, droga, nossa,
  fogo; Russian: козёл, свинья, голубой, зараза, ёлки, черта (a trait; чёрт and its phrases
  are in), and "блин" is guarded as a pancake. Russian is the first language in another
  alphabet, so three places that only knew English letters follow the language now:
  `ai._letters` (an AI's quoted words were never found in a Russian line, so nothing it
  flagged would have counted), `learn.norm` (a Russian line was learned as an empty line) and
  `guess_title` (a video named in Cyrillic had no name to look subtitles up by). Still Latin
  only: `cc._only_word` (an AI's "just the word" in Russian falls back to the whole line) and
  the subtitle title match `_same_title`. Not heard: the listening model's samples are
  Spanish, French, German and English, so no Portuguese or Russian speech has been through
  CleanView here; the lists had no native speaker's check. cvlang.py changed: CleanListen's
  copy must follow.
- The time left doesn't count the wait before a step moves (1.18.88, 2026-11-13; the owner, one
  movie of 1,700 lines on the laptop: "said checking diologue 200-225 of 1700 65 minutes left.
  then it jumped to 250 minutes. is that right?"). `TimeLeft` took a step as begun when the
  step before it said 100% (which is the next step's first mark), and "Telling voices
  apart..." comes before the reading with no count of its own; those minutes were divided by
  the 5% of the reading done when its own speed took over, which is exactly lines 200-225 of
  1,700 with sexual references off. The step's clock now starts when its share first moves.
  Times of an hour and a half or more are said as "about 4 hr 10 min left". The reading's
  parts still aren't equally fast for their share of the bar (first read, second look,
  sexual talk, each conversation), so the figure can drift within the step.
- A video that fails while it's checked offers to send a note (1.18.87, 2026-11-13; the owner:
  "if clean view crashes or has a save issue. is that sent to you someway? is it in any report
  you would get?", and "yes" to adding the one case that wasn't offered). What reaches the
  inbox, always only on her Yes and with internet (kind "problem", the Drive folder "CleanView
  learned"): "CleanView closed suddenly ..." and "CleanView stopped responding ..." (asked at
  the next start, `_offer_problem_note`), "CleanView couldn't save ..." (`_tell_save_failed`),
  and now "CleanView couldn't check ..." (`_tell_check_failed`, from `after_analyze`: the
  error and traceback or worker log of each failed video with the home folder as "~", how many
  failed, and reader / ai / look / language / offline / profile). Not offered when every
  failure is the video's own (`video_error`: copy protection, no sound) or there's no inbox:
  then the old box with the details file. The report file and "Send what we refined" never
  mention problems (a failed video has neither), and nothing is sent by itself.
  A save that fails says why and what to do (the owner: "i was saving a file before and i
  didnt have enough storage but didn't know cause it only failed but didn't say why"; since
  1.18.24-1.18.25 a full drive was said plainly and the room was checked before saving, so
  hers was likely before that or with "save it there anyway"). A full drive (`no_room`) now
  says where, how much is free and to use "Change..." (`_no_room_said`); and for what she
  can put right herself (`her_fix`: full drive, a 4 GB drive, a file open in a player, a
  folder she can't write to) no "send a note?" is asked, only the reason.
- CleanView says "AI", not "Claude" (1.18.86, 2026-11-13; the owner: "Not in the Claud, chat,
  gemini section, but everywhere else in clean view, instead of saying "claude" say "Ai"").
  Step 3 (the AI helper: the cards, the sign-in lines) and the messages that send her there
  ("... isn't signed in yet", "This needs Claude, ChatGPT or Gemini") still name them.
  Everywhere else: the window's `AI_NAME` is "AI" ("Ask AI", "AI: cut - ...", "Ask AI about
  this...", "Found by AI"), sentences say "the AI" ("The AI's review", "that the AI says are
  fine", "The AI is reading the dialogue...", "The AI's findings on this video"); the engine
  writes `THE_AI` in its notes and progress lines ("The AI reviewed everything", "The AI
  couldn't read the dialogue this time", "The AI is looking through the whole picture") and
  the labels "Found by AI", "Seen by AI", "Asked AI", "(widened by the AI)"; the report file
  says "per the AI review". Which one helped is still kept (`st["reviewer"]`, `st["reader"]`,
  the settings) and sent in. Older reviews are shown the new way: `engine.plain_ai(text)`
  changes a name at the start of a note or after by / Asked / per; it's used only on notes
  and labels CleanView wrote itself (a scene's "why" and the dialogue can have a Claude of
  their own). `scan_step` knows both wordings. Not changed: "your chat with Claude" in the
  offline "Send what CleanView learned" message (that's this chat), file and function names
  (`claude_findings.csv`), and the learned counts under the old label names.
- A short list of Spanish swear words is on the English lists (1.18.86, 2026-11-13). The owner
  asked what happens to the Spanish in a mostly English movie (cleaned as English: the Spanish
  lists aren't used, the English model can't hear Spanish, so its swearing gets through), then
  "would loading spanish known swear words into the english filter help without using a
  separate filter?" and "add the short list and we will look at the other option later". In
  `cvcore.MODERATE`: puta/puto(s), hijueputa, pendejo/a(s), cabrón (cabrona, cabrones),
  joder, jodido/a(s), jódete, carajo, gilipollas, chinga/chingar/chingada/chingado/chingón...;
  in `SAMESEX_WORDS`: maricón(es). Only words that mean nothing else in English; "mierda" was
  there already. `norm()` drops an accented letter in English ("cabrón" -> "cabrn"), so each
  pattern takes both spellings. Left off: con, concha, polla (words and names), culo, verga,
  and coño, which `norm()` makes "coo". A stopgap: they're caught where subtitles spell them
  out, rarely from the sound. The real fix, put off by her ("the other option later"), is to
  listen with the model for other languages and use each line's own list; "Auto" (tell the
  language from the sound track's label or a short sample) was discussed too, not decided.
- Subtitles are always looked for (1.18.85, 2026-11-13; the owner, of step 1's "Find subtitles
  online for videos that don't have any" switch: "that part says look for subtitles with a
  choice. i think subtitles are important enough that they should be standard"). The switch is
  gone; `_current_opts` always gives `autosubs` True (a saved "off" from before no longer
  counts), and the small print under step 1 says subtitles are always used, the video's own or
  ones found online. The engine's `autosubs` option stays (tests and the command line use it).
  No internet (the owner: "if there s no internet connected could it pop up a small window
  saying no internet, cant look up subtitles. want to clean without them?", "with a yes no
  button"): Start cleaning asks `engine.online()` (opens and closes a connection to
  `ONLINE_HOSTS`, 1.5 s each, nothing sent; `CLEANVIEW_ONLINE` 1/0 answers without trying, and
  the tests set 1) and, offline, shows `NO_INTERNET_ASK` with Yes and No. No stays on the start
  page; Yes cleans with `opts["offline"]`: `fetch_subtitles` still uses the video's own
  subtitles and ones downloaded before, looks nothing up, remembers no "none online", and the
  note says "No subtitles: there was no internet connection to look for them". Not asked
  about: Claude, ChatGPT and Gemini also need the internet (they say so themselves when they
  can't be reached).
- "stripper" is a person or a tool (1.18.85, 2026-11-13; the owner, in the CleanListen session
  for every app: "read the context. like a paint stripper would be ok. but a person stripper
  isnt. a pole by itself is fine but with stripper it isn't"). `stripper_tool(text, match)`
  leaves a find of `LINE_WORDS["sexref"]` out when it's the tool or chemical: the next word is
  clip(s)/well(s), the word before is asset/weed/tobacco/cotton, or one of `STRIPPER_THINGS`
  (paint, varnish, wallpaper, wire, cable, floor, furniture, chemical, solvent, brush...) is
  among the 3 words before or 5 after; "stripper pole" is never the tool. The same words as
  CleanListen's guard. `LINE_WORDS["sexref"]` is now a `Listed` (its pattern plus that check;
  `search` and `finditer` as before, anything else goes to the pattern): put a context guard
  for a list word there, not in the pattern.
- The answer under an item wraps to the room it has (1.18.85, 2026-11-13; the owner: "in the
  after report. when looking at what was found and you hit ask the box that opens on the
  response is clipping off on both left and right. i cant see the full response"). The Ask box
  under a scene, line or word (`_ask_inline`) wrapped its tip and its answer at a set 640
  pixels (times the text size); in the lines card the box is only about 660 wide in the
  standard window, and narrower in a smaller window or with a second column, so the label was
  squeezed and its words, centred, ran off both sides. `_fit_text(label, box, margin)` sets the
  wrap width from the box's real width and again on every `<Configure>`; the tip, the answer
  and the kept answer (`_answer_box`) use it, and the answer is anchored left.
- "CleanView was updated to version ..." goes away by itself (1.18.84, 2026-11-13; the owner:
  "when it updates clean view it leaves a long bar on the top it should go away after 3
  seconds", "it says updated to version"). The tinted line at the top of the start page after
  an update or "Check for updates" (`CLEANVIEW_UPDATED`; also "CleanView is up to date.") is
  `self.updated_note` and is removed after `UPDATED_SHOWN_SECS` (3).
- Lauren's Castle S2E1 tests (1.18.84, 2026-11-13, adults, laptop, made on 1.18.78; four
  "refined" files in the Drive folder: 16:48 with the AI helper off, 17:23 and 17:27 with it
  on, 17:36 the same after asking Claude; she attached the last one and called it "without the
  ai helper"). Off: 5 min, the short list's words only, and a "Condom shown" at 18:21 (the
  latex glove being dusted inside) offered unticked as not double-checked. On: 29 min (reading
  the dialogue 16.2, each conversation 11.7; dialogue model 63% on the card), the glove
  dropped by the closer look, and four more lines: "spotlights shining up my booty" and "You
  could be wearing a skirt" (she made each just the word), "Try unbuttoning his shirt" (the
  photographer; she unticked it) and "You do remind me a little of Hooch" (a dog; wrong, left
  muted). Fixed: "stripper pole" is muted whole (`LINE_WORDS["sexref"]`
  `strippers?(?: poles?)?`; only "stripper" was, and in the chat she said "if pole ever comes
  after stripper it should be muted, keep pole other instances"); "Sexy. Sexy's not a crime."
  had its second mute put on top of the first (`word_mute`: a possessive is the word said
  again, `cl._base`; a word asked for more often than it's said gets no second mute on top; a
  heard word counts as already muted by its middle, since a mute is a little wider than its
  word). Taught for Castle as fine (her "Yes, teach them"; a "CleanView reviewed" file through
  merge_learned.py): "You do remind me a little of Hooch" and "Try unbuttoning his shirt. Just,
  just the first one right there." Not flagged by either run and put to her, not taught (she
  named none): "Because I don't wanna get paid in singles", "Ever consider becoming a mohel?"
  / "Keep talking and I'll practice on you", "Now excuse me while I change my shorts", "before
  he goes and takes a leak", "That he was cheating?".
- Technical notes are off the review page (1.18.82, 2026-11-13; the owner: "in the after
  report that is visible in clean view after cleaning a video, you are able to see the qwen
  version and timers and such. i dont care if that in the report to send to you, but not
  visbible to all. just keep things relative to the video,; the scenes cut, words muted etc.").
  `engine.technical(note)` (`TECHNICAL_NOTES`): "Checked with: ...", "The AI helper used ...
  (CleanView x)", "Voices: N speakers ...", "The AI helper took a closer look at ...", "Nudity
  check: ...", "Dialogue was checked with ...", "Took N min: ...", "<AI> looked through the
  whole picture (N stills) ...". The review page shows `engine.video_notes(st)` only. They
  stay in the saved review (`st["notes"]`, `st["scan"]`) and in "Send what we refined". The
  report file: 1.18.82 left them out ("i only want you to know what is being used"); told a
  report sent in would then no longer say the version or the times, she said "i want you to
  know pertinent information of the report. if you need to put some things back on the report
  for you is good", so since 1.18.83 they are its last lines, after the list of mutes and
  cuts, under "For CleanView's maker, to look into a problem (how this video was checked):"
  (`technical_notes`, `TECHNICAL_HEAD`; the version first when no AI helper note says it).
  Notes that say something wasn't checked or went wrong (no subtitles, no
  AI read the dialogue, the picture AI isn't installed, an AI couldn't read or look) are about
  the video and still show. A new note about how a scan went belongs in `TECHNICAL_NOTES`.
- The logo, not Tk's feather (1.18.82, 2026-11-13; the owner: "sometimes the logo for clean
  view down in the start bar of the computer becomes a big feather. i noticed it after doing
  the recent update but it has done it before. the logo is correct currently"). Not
  reproduced, cause unknown: the feather is what a Tk window shows when it has no icon of its
  own. Ruled out here: an icon file held by another program (Tk then quietly uses Windows'
  icon for the file, no error), the .ico itself (7 sizes, read fine). `set_icon(win)` now
  makes the logo the default for every window of the app (`iconbitmap(default=)`; the "Ask"
  box had none), sets it on the window, and sets it again 0.5 s and 3 s later (`ICON_AGAIN`);
  a failure is written to `APP_DATA/icon_problem.txt` (time, version, error). The "Opening
  CleanView..." box (launcher.pyw `splash`) sets the default too. If she sees it again: ask
  what she had just done (update, Update now, text size, Light/Dark) and read that file.
- The review page draws again quickly (1.18.82, 2026-11-13; the owner: asking Claude a question
  on the review page, "while claude is working on the answer if you click anywhere else clean
  view says not responding and then the whole screen refreshes. it comes back with a response
  ... i just think it shouldn't do that"). The asking is in a thread; when the answer changes
  the list, `_chat_reply` builds the whole review page again on the window's thread
  (`show_review`), and that took 4-5 s here for a review with 1 scene and 38 words (longer on
  her laptop): the window can't answer meanwhile. Nearly all of it was Tk drawing the rounded
  ttk buttons: it stretches an image element by repeating its middle one copy at a time, and
  the middle was 1 pixel wide (18 buttons: 2.5 s; plain: 0.2 s). `look._corner_img` pictures
  are `STRETCH` (64) pixels wider now and the elements keep their smallest size (`_slim`:
  `width`/`height` on `element_create`), for buttons and tabs; buttons are the same size.
  Rebuilding that page: 3.9 s -> 1.7 s. Still on the window's thread (not changed): the
  rebuild itself (each word row is about 20 ms), and `cc.status()` runs `claude auth status`
  there when the AI's state isn't known yet. cvlook.py changed: CleanListen's copy must follow.
- The time left is right while the dialogue is read (1.18.82, 2026-11-13; the owner: "when it
  says checking dialogue or reading conversations. the green progress bar works correctly but
  the timer doesnt. it said 1 minute remaining and it been working for 20"). It was worked out
  from how full the bar was, as if every step filled it at the same speed; on her laptop the
  AI helper's reading is 12% of the bar and two thirds of the time. `TimeLeft` (analyze's
  `eta`) times the step being done by itself (once 5% of it and 20 s are done), and for the
  steps to come uses how long each took on this PC last time, per second of video
  (`APP_DATA/step_pace.json`, `load_pace`/`save_pace`, half old and half new each scan; keys
  `asr`, `snd`, `vis`/`vis+ai`, `look`, `lines+local`/`lines+claude`..., `pics+...`; a step
  under `PACE_MIN_SECS` or first seen partway was saved work and isn't remembered), else the
  speed the bar moved at before that step. The bar itself is unchanged. Reading the dialogue
  is now the whole of its step when each conversation isn't read after it (`read_part`; it
  stopped at 60%). Not changed: "About ... left for all N" on the working page still goes by
  the bar, and paused time counts as time spent.
- Other languages, Spanish first (1.18.80, 2026-11-13; the owner: "is it possible to add
  additonal language capabilities to clean view? ... like if i wanted to scan a movie in
  spanish", "maybe the 10 most spoken languages", then "i would do the easier group of
  languages": Spanish, French, Portuguese, Russian; Mandarin, Hindi, Arabic, Bengali and Urdu
  need a different, slower model and are for later). Step 1 has "Language spoken in the video"
  (`opts["language"]`, the language's code, kept in the settings; `cvlang.LANGS` is the list),
  since 1.18.85 a drop-down list of the names (`language_box`; the owner: "as we get more
  languages, instead of labelling them all on the front page, should we have a a drop down";
  it was three buttons side by side, and the wheel over it doesn't change it), its box rounded
  like the rest ("yes round them": `look.style_dropdown`, style "Round.TCombobox", in
  cvlook.py, so CleanListen's copy must follow). Names used by its handlers are its own
  (`lang_var`, `lang_names`...): `v` and `names` are reused further down `show_setup`, and a
  handler that closed over them set a different option (caught by its test before release).
  English is untouched: its own listening model and `cvcore`'s word lists. Another language:
  - listens with NeMo Parakeet TDT 0.6B v3 (about 25 European languages; loads with
    `load_recognizer` unchanged), downloaded once on "Getting ready" the first time another
    language is picked (`cvlang.install_model`, 490 MB, `models/<MODEL_NAME>`; `tools_missing`
    "listening model for other languages"). English never needs it. On 15 minutes of The
    Resident its English agreed 90.8% with the English model's words, so English stays on v2.
  - uses that language's word lists in the same groups (`cvlang.ES`, `ES_PHRASES`, the guards
    `ES_NOT_NEXT`/`ES_NOT_BEFORE`): `cvcore.use_language(code)` sets `cvlang.LANG`, and
    `norm()`, `find_language()`, `listed_word()` and `mask()` hand over to cvlang when it isn't
    "en" (accents come off before matching, ñ stays). `analyze` sets it from the options (each
    video's worker is its own process), `render` from the saved options, the window on Start
    and when a review is opened again. Words left off on purpose because the everyday meaning
    is far more common: concha, perra, coger, huevos, capullo, tortillera, infierno, Jesús
    (caught in phrases: "hijo de perra", "la concha de tu madre"). English swear lists aren't
    run on Spanish ("negro", "Morón").
  - takes the sound track and subtitles tagged in that language (`probe(path, language)`,
    `find_subtitles(..., language)`, `cvlang.TAGS`/`FILE_TAGS`; an English .srt beside a Spanish
    video isn't used), looks subtitles up online in it (`_sub_language`), and keeps its saved
    words and downloads apart (`_lang_file`: "transcript_es.json").
  - tells the dialogue readers what they're reading (`cvlang.reader_note`, added in `ai.chat`
    for questions without pictures and to `cc.SYSTEM` in `cc.ask`).
  French (1.18.81; the owner: "French next") is the same again: `cvlang.FR`, `FR_PHRASES`,
  `FR_NOT_NEXT`/`FR_NOT_BEFORE`, France and Quebec (tabarnak, câlisse...). Accents come off,
  and so do the short words French joins on with an apostrophe (`ELIDED`: "l'idiot" is
  "idiot", "j'm'en fous" is "en fous", so "nom d'un chien" is written `("nom", "un",
  "chien")`). Left off as mostly innocent: baiser (a kiss), chatte (a cat), queue, fou/fous,
  mince, punaise, purée, flûte, la vache, la ferme (the farm), calvaire, sacré.
  Not done for other languages yet: the short no-AI phrase lists (`LINE_WORDS`), the hard rule's
  words (only "semen" is the same word), explicit findings, bleeped subtitles, the God/name
  heuristics from subtitles, sound descriptions in subtitles ([moans]) and the web test
  version are English only, so in Spanish the dialogue filters lean on the AI reader. The
  Spanish list was written without a native speaker's check and has only been heard on the
  model's own clean sample (no Spanish swearing to test on here). Adding a language: `LANGS`,
  `TAGS`, `FILE_TAGS`, `SUB_LANG`, its lists in `WORDS`/`PHRASES`/`NOT_NEXT`/`NOT_BEFORE`, and
  `NO_ACCENTS` if accents should come off (not for Russian: й would become и). Word lists
  go to CleanListen and CleanRead too once she has seen them.
- A section's boxes open right under its own row of tiles (1.18.79, 2026-11-13; the owner: "when
  you click more it opens a window below all of the menus. id like each one to open right below
  its chosen option"). The tiles sit in rows 0, 2 and 4 of their grid and the card with the
  boxes (`_section_detail`, edged in green like the chosen tile) goes in the row between, under
  the chosen tile's row; the page scrolls to the tile.
- Light and dark (1.18.78, 2026-11-13; the owner: "how hard would it be to add a dark mode",
  "yes it should be optional", of a sample "i like the look. i dont like the brown around the
  pickup where i left off", and "just light dark button option. no windows choice"). A Light /
  Dark button under the steps on the start page (`theme_var`, `_set_theme`: the page is built
  again in that look, as a new text size does, keeping the videos, the ticks and the step);
  light is the look as it was and the default; the choice is kept as `theme` in the settings
  and read before the window is drawn. Every colour the window uses has a name with a value
  for each look (`LIGHT`, `DARK`; `use_theme(name)` sets the module's names, BG, CARD, INK...,
  and the drawn pieces' colours, `look.use`, `PIECES`): never write a colour into a page, name
  it there (`test_theme` checks; white on green is the one literal left). New names for what
  were one-off colours: `NOTE`/`NOTE_EDGE`/`NOTE_INK` (the note boxes: cream and orange in
  light, green-tinted in dark, not brown), `WARN`, `WORD_BG`/`WORD_INK` (a muted word or
  row), `SHADE`, `DISABLED`, `RING`, `SOFT_EDGE`, `PLAIN_DIM`/`PLAIN_EDGE`, `SAY_*` (what the
  AI said). Colours fixed when the program starts are looked up by name when used
  (`CLAUDE_SAYS`, `JOB_LOOK`; no colour as a default argument). The ttk pieces' pictures are
  drawn again in place for a new look (`look._same_images`: an element can't be made twice).
  The title bar goes dark too where Windows can (`_title_bar`, DwmSetWindowAttribute 20). The
  file chooser and question boxes are Windows' own and follow Windows. Wanted in CleanListen
  and CleanRead with the new look.
- A new look, step by step (1.18.77, 2026-11-13; the owner: "the ui also feels clunky and dated,
  can you make it feel classy (all of them)"; a repaint was "just ... changed colors", so two
  real layouts were mocked up and she chose "B, step by step", then "finish the ui upgrade").
  The start page shows one step at a time (`STEPS`, `_go_step`, `_panes`): the four steps are
  listed down the left, each saying what's chosen (`_step_summary`, `_show_steps`: "3 videos
  chosen", "Young kids", "Claude", "Next to the videos"; step 1 gets a tick once videos are
  chosen), clicking one goes to it, with Back, "Next: ..." and Start cleaning (always there,
  since her choices are remembered) at the bottom, and Text size, Check for updates and Send
  what CleanView learned as quiet links under the list. Step 1: a "Choose a movie or episodes"
  panel and a switch for finding subtitles. Step 2: ages as one rounded choice
  (`look.Segmented`), and each section a tile (`fold_group`): an icon, a switch for all of it
  (on, off, or pale for some), "N of M on" / "Off" and "Choose"; its boxes open under the tiles,
  one section at a time, and the page scrolls to them; the kissing choices are Keep /
  Passionate / All kisses. Step 3: the AI helper's switch and four cards (This PC, Claude,
  ChatGPT, Gemini), the sign-in line under them as before. Step 4: where it saves. Every
  option, tick and saved choice is as before (`self.opts` holds them all whichever step shows).
  The other pages match: what's being done on a card, scenes, lines and words on rounded cards
  (`_round_card`) with the kinds as small chips, tabs as pills, rounded buttons, thin scroll
  bars, a rounded progress bar; the review page's "Saves to ..." line has its own row.
  The drawn pieces are in `cvlook.py` (the same file can serve CleanListen and CleanRead): Tk
  can't smooth edges, so rounded shapes are drawn with numpy as PNGs (Tk reads PNG itself; no
  Pillow) with ordinary Tk text on top: `Card` (only its four corners are pictures), `Pill`,
  `Switch`, `Segmented`, `OptionCard`, `Badge` (Windows' "Segoe MDL2 Assets" icons), `chip`,
  `link`, `tick_images`. A click is a press and a let-go on the same piece (`on_click`). The
  ttk buttons keep their styles (`Accent`, `Go`, `Plain`, `Small`) and are drawn rounded by
  `look.round_buttons`: when one is shown it gets a copy of its style made for the colour
  it sits on ("on_<colour>_<scale>.Accent.TButton"), so test a style with `endswith`.
  `SIDE`, `TINT`, `SOFT`, `FAINT`, `HEAD` (Segoe UI Semibold) join the colours. Give sizes
  through `self._px(n)` (pixels at normal size) so they follow the text size.
- The owner's hard rule (1.18.77, 2026-11-13): "Sometimes i forget reasons for having words
  removed....so these words: Fart, Condom (always falls under sexual reference), Seman (always
  falls under sexual reference) Should always be removed...if I ever say they shouldn't mention
  this was decided on today's date as a hard rule - dont override", then "fart is fine to leave
  under crude humor", "Also add visuals of a condom needs to be removed", and (in the CleanListen
  session) "Detective or coroner lines - condom and semen should still be removed even in this
  instance". If she asks to leave one in: say it's a hard rule set on 2026-11-13, then do as
  she says if she still wants it. `cvcore.ALWAYS_REMOVED` (fart/farts/farted/farting,
  condom/condoms, semen; not farther, condo, seaman) and `always_removed()`; `never_fine()`
  covers them, so an AI's "not an issue" is ignored (`apply_review`, `HARD_RULE_WHY`) and they're
  never learned or shared as fine. `hard_rule_words(st)` (after `list_words_only`) mutes the
  word wherever it's said in the dialogue when its box is ticked (fart: crude humor; condom,
  semen: sexual references), also in a line left alone (learned as fine, case talk with the
  coroner box off) or one she unticks. "semen" joined `LINE_WORDS["sexref"]`; the Castle lesson
  that kept "called Calvin Klein a boring old fart" is gone. A condom in the picture is a
  "Condom shown" scene under the sexual references box: a picture category (`CLIP_CATS`,
  `THRESH` 0.5, `MIN_FRAMES` 1, `LOOK["condom"]`, `CAT_LABEL`, `needs`), and Claude, ChatGPT
  and Gemini get a "condom" kind (`PIC_KINDS`, `PIC_RULES`, `PIC_TEXT["sexref"]`,
  `_pic_wanted`). On Castle S1E2's saved stills (every 2 s) the box of condoms Castle holds up
  at 27:38 scored 0.58 and nothing else in the episode 0.4; of 10,674 stills from nine other
  videos one scored 0.5 or more. The AI helper's closer look said yes to that still and no to
  five others near it (a phone in a hand, a bathroom shelf, a medicine cabinet). Older picture
  scans are done once more (the descriptions changed). CleanListen and CleanRead have the
  words since 1.17.24.
- Explicit detail in findings is always removed (1.18.77, 2026-11-13; the owner, in the
  CleanListen session, for every app: "any explicit talk should be removed from coroner talk
  regardless of medical /coroner - tearing, vaginal bruising etc", and how: "whole line on
  sexual reference"). With sexual references ticked, a line with explicit detail in a
  coroner's, doctor's or detective's findings is muted whole, with the coroner box on or off:
  `EXPLICIT_FINDING` (vaginal, anal, penile, hymen, labia, vulva, sodomy/sodomize, "forced /
  signs of / evidence of penetration") and "tearing" as a finding (`TEARING`: not tearing
  up/down/off/the...; with `TEARING_NEAR`, e.g. sexual, assault, rape, vaginal, penetration,
  within about 30 words before or 10 after, across lines). `explicit_findings(lines)` in
  `find_lines` marks the line `explicit` (never "just the word"); a review's "not an issue"
  or "just the word" on it is ignored (`apply_review`, `EXPLICIT_WHY`), and a built-in or AI
  "fine before" hint doesn't untick it (`explicit_stay`); her own choice still does. Plain
  case talk ("any signs of sexual assault?") still follows the coroner box; `NOT_CASE` tells
  the readers explicit detail always counts. CleanListen and CleanRead have the same words.
- The code check (1.18.77, 2026-11-13; the owner: "also look through the rest of the code for
  errors"; three read-only reviews of every file). Fixed, each with a test in
  `test_code_check.py` or `test_sections.py`: a word said twice (in one line, or two lines close
  together) got one mute and both lines were unticked as "just the word" (`word_mute(used=)`:
  the mutes one pass has already given out; `list_words_only` and `hard_rule_words` pass it);
  asked for "affair", `word_mute` muted the longer "Affairs" earlier in the line (the word
  itself first, then a longer one with it inside); a video took the subtitles of another whose
  name starts the same ("Cars 2.srt" for Cars.mkv: its own are `<name>.srt` or
  `<name>.<lang>.srt`); `look_spans` shrank a stretch that had another inside it;
  `LearnedLines.match` stopped at the first candidate that was too short for its length
  (`continue`, not `break`); a conversation over 30 lines started its next part with one stray
  earlier line and skipped two (`cur[-2:]`, in `conversations` and `romance_scenes`); a
  scene's preview was kept by its start only (now start and end); "Update now" from the start
  page lost ticks just changed; Start cleaning with a chosen video gone did nothing (it says
  so now). Found and NOT changed yet (each needs a decision or testing on real videos):
  1. `look_at_picture`: a cloud find that overlaps a local scene is dropped, its span and kind
     too (a local Kiss at 100-105 s and a cloud "Sex scene" at 90-212 s leave one 5-second Kiss).
  2. Subtitle words joined by punctuation: `norm()` drops it, so "Irish-Italian" and "I
     wish...it were" match `.*shit.*`, and "Well...damn" is missed (`spoken_words` splits on
     spaces only).
  3. Word lists: `darn.*` takes Darnell and darning; "for Christ sake", "I swear to Christ" and
     "And Jesus, it hurt" pass as reverent; "Homo sapiens", "Dick Van Dyke", "ball peen
     hammer", and "SOB STORY" in all-capital subtitles are flagged; `unbleep` fills in "A*" and
     "C#"; "where the idiot went" mutes "where the" too (`with_lead_in` on every category).
  4. The AI helper's dialogue questions that fail are dropped silently, and the report still
     says the dialogue was checked with it.
  5. The stuck-save watch may stop a big save while ffmpeg moves its index to the front (after
     the last progress line) on a slow drive.
  6. `guess_title` gives up on "D2 The Mighty Ducks", "T2 Trainspotting", "Fast Track".
  7. Gemini's answers are only checked at the top level (a wrong shape inside one fails the
     video instead of falling back); a hung `codex.cmd`/`gemini.cmd` can outlast its time limit.
  8. `MORE_THAN_WORD` has `bull\w*` (meant for bully), so a "just the word" for "bullshit"
     becomes the whole line; "- JESUS: Follow me." keeps the speaker label as a word;
     `ollama_care.CLEAN_APPS` never matches an installed window (only its workers).
- The save folder is remembered (1.18.76, 2026-11-12; the owner: "on the save to area, when
  someone selects a folder to save can it be remembered even when clean view closes and
  reopens"). A folder chosen with "Change..." under "Save to" (or on the review page) is kept
  as `save_to` in the settings (`_remember_save_to`, also in `_save_settings`) and used again
  on the start page and when videos are chosen (`_remembered_folder`; one that isn't there now,
  an unplugged drive, is passed over this time but kept). "Next to the video" beside Change
  (shown only then, `next_to_btn`) goes back to a "Clean" folder by each video
  (`use_video_folder`). Also: the Claude and ChatGPT choices say "uses your ... premium plan",
  and "Use the AI helper..." is one size bigger (`Big.TCheckbutton`, 11 pt) so it stands out.
- One bigger "Choose files..." button on the start page (1.18.75, 2026-11-12; the owner: "the
  choose a folder of episodes button doesn't seem to do anything. can we get rid of it and make
  the choose files button about 20% bigger?"). "Choose a folder of episodes..." and `pick_folder`
  are gone; Choose files uses `Choose.TButton` (13 pt bold, padding 20x9, vs Go's 11 pt, 16x7),
  with a hint beside it: open the season's folder and press Ctrl+A to choose every episode.
- The start page's filters in sections by topic, each with a tick-all box, folding away (1.18.74,
  2026-11-12; the owner: "i want to consolidate or make then nicer", "lets make medical anything
  its own category", then "a main box for each category to tick all if wanted, but if only some
  of the subcategories are wanted just those can be ticked. vid angel had a system like that",
  "maybe not as long"). Nine sections (`fold_group`): Bad language (with her own words), Sex and
  nudity (sexual references, gestures, immodest clothing too), Romance and relationships (the
  two kissing menus, sleeping around, unmarried couples, same-sex), Violence, Medical (medical
  scenes, coroner and doctor talk), Attitude (bullying, disrespect, crude humor), Smoking,
  drinking and drugs, Faith, holidays and magic (religion too), Music. Each head is a box drawn
  ticked, empty or with a dash for some (`_ticks["some"]`), the name, "3 of 5 ticked" and
  "Choose which..." / "Hide"; clicking the box ticks every one (or, when all are, unticks them;
  the kissing menus go to "Cut all kisses" / "Keep" and count as ticked unless "Keep"); the
  counts follow every change (variable traces, so changing age or "Reset" updates them). Folded
  by default; the open ones are remembered (`open_sections` in the settings). Same keys, ticks
  and per-age presets as before. `_section_heads` (title -> box, count, tick_all, show) for tests.
- Lauren's Castle S2E5 report (1.18.73, 2026-11-12, adults, the AI helper, made on 1.18.70; the
  owner: "Yes, teach them"): 41 min on her laptop against S2E3's 48 (each conversation 18.0 ->
  12.9 min with 1.18.68's quick question; reading the dialogue 14.4 -> 15.2 with 1.18.70's
  sexual-talk check). The scan record shows `picture_runtime` 1.24.4, but the laptop's picture
  scan didn't get faster (4.9 -> 5.3 min), so something else limits it there (likely reading the
  video). Every listed word muted, "Go get it out of your system" (the agent telling Castle to
  sleep with Beckett) muted. Taught for Castle: "Oh, Rick. You sleeping with her? No." (sexref)
  and "Geez, one night in Ibiza and what do I get, a chapter in Storm Fall?" (casual); "A very
  hot chapter." is under 5 words.
- Coroner and doctor talk is its own filter (1.18.72, 2026-11-12; the owner: "is it possible to
  categorize coroner, medical examiner and dr talk into its own ticked box. so it gives the
  option if wanted to have that included or not?", then "b and yes those ages": all graphic
  findings, not only sexual ones). `forensic`: "Coroner and doctor talk (graphic findings:
  wounds, autopsies, sexual assault)" in the Language section, ticked for Young kids, Kids and
  Teens, not Adults. It covers graphic talk about a body or a victim by a coroner, medical
  examiner, doctor or detective (wounds, blood, organs, cause or time of death, an autopsy) and
  case talk about rape, sexual assault, sex offenders or sexual evidence; not everyday medical
  talk. With it off, that case talk isn't a sexual reference either: `NOT_CASE` in the sexref
  descriptions (`ai.LINE_TYPES`, `cc.TYPE_TEXT`), "sex" before offenders/crimes/trafficking/abuse
  left off `LINE_WORDS["sexref"]`, and the three Castle coroner lessons ("could have been a
  rape", "so you're saying she was raped?") filed under it (`muted_for` "forensic"). Its short
  list (`LINE_WORDS["forensic"]`): sexual assault, sex offenders, rape kit, was/been raped,
  cause/time of death, autopsy, post-mortem, stab/gunshot wounds, GSW, blunt force trauma,
  ligature marks, exit/entry/defensive wounds, lividity, rigor mortis. Tried with the AI helper:
  ticked, Castle S2E3 muted "Cause of death? Stabbing", "I'm putting the time of death", "Any
  signs of sexual assault?", S1E2 the dryer/raped line and the condom evidence, The Resident
  S03E12 "Gunshot wound in the abdomen"; unticked, none of them. The AI helper finds few
  graphic findings beyond the list ("a fatal wound in her back", the bruising and the slap went
  through); a word like "condom" in case talk is still muted as just the word with it off.
- The Castle reports in the Drive folder gone over (1.18.71, 2026-11-12; the owner: "do 1"): S1E3
  and S1E4 (teens), S1E6-E9, S1E2 "(Clean)" and S2E4 (adults), all on the AI helper. Built in for
  Castle: "...arrange a very special date with Tiffany" (Castle booking the escort), her own
  ticks "That better not be porn, and if it is, I want in" and "...the guy who wears that condom
  lives on 15", and the misses "We could always make it strip poker", "You're a married man
  sleeping with her in your own bed", "Only the whole time, he was sleeping with me" (casual), "No
  time for dirty talk, go get changed". Her unticks of lines that fit no filter taught as fine:
  "Someone who was slipping her a little cash" and "What are we playing for?" (two older lessons
  had joined each to the next line, "...partial river view someone who was slipping her a little
  cash" and "what are we playing for pride or clothing", and matched the harmless half: taken
  out; "while he was slipping her something else" stays), "Beat his pants off" (poker), "Lord I
  can't stop myself" (a song) and "between Nikki Heat and the roguishly handsome reporter". Not
  taught: lines under 5 words ("Kind of hot", "The sex is unbelievable", which she muted whole),
  police and coroner talk ("registered sex offenders"). Her unticks of two "same-sex romance"
  scenes (S1E7's opening song, a S1E2 "two women" one) are flirting-check false alarms that line
  lessons can't teach.
- Sexual talk is also looked for a conversation at a time (1.18.70, 2026-11-12; the owner: "yes"
  to looking into why the AI helper missed Castle S2E3's innuendo, then "Yes, build it").
  Replaying that episode's dialogue (with the lessons it had then): `classify_dialogue` reads 25
  lines at a time and is told three times to flag only what it's sure of; it noticed 3 of the
  13 lines she'd have muted and its second look dropped all 3, and it flagged nothing else.
  Softer wording alone caught 2-3. `ai.sexual_talk` (when "sexref" is ticked and the AI on this
  PC reads; `find_lines`, the last quarter of "Reading the dialogue") asks each conversation
  (`conversations`, as the flirting check splits them) a quick yes or no (`SEXUAL_TALK`), then
  which lines with their exact words (checked against the dialogue), then each line on its own
  with the sexref description plus `INNUENDO` ("Count innuendo and double meanings that are
  sexual in this context"). Through `find_lines` (lessons from before 1.18.69): Castle S2E3
  gained "Let's skinny dip", "Take your pants off", both naked-photo lines, "I wanted to taste
  you" (and "That's pretty sick stuff", a false alarm; "he gives you great shots. If you
  don't," borderline); Castle S2E1 gained "Try unbuttoning his shirt", "spotlights shining up
  my booty", "You could be wearing a skirt"; a Gummi Bears episode and The Resident S03E12
  nothing. A line with a word on the short list stays "just the word" ("poking my boobs").
  Asking it per conversation with no line-by-line look caught 7 of the 13 but flagged 30
  innocent lines. Cost: about 2.5 min an episode with the model 61% on the card (laptop-like
  here), 0.3-1 min on the full card.
- Lauren's Castle S2E3 report (1.18.69, 2026-11-12, adults, the AI helper, made on 1.18.67;
  laptop: 48 min, reading 14.4 and each conversation 18.0): every listed word muted, nothing
  marked Drugs, but the AI helper flagged almost none of the episode's sexual talk. The owner:
  "do both but leave coroners talk". Taught for Castle (sexref, a "CleanView reviewed" file
  through merge_learned.py): the opening skinny-dip chase ("If you catch me, you can have me",
  "Take your pants off!"), "Was she the sexy, curvy, / lingerie-type that you could just...", "a
  chastity belt", "Look at naked pictures? If you insist.", "...the only guy that Sierra was
  modeling for", "Because Jenna wouldn't sleep with him", "You give Wyatt what he wants", "give
  Wyatt what he wanted", "code for 'do me'"; not the coroner's "Any signs of sexual assault?" (she
  doesn't want coroners' talk muted), nor "It's not the worst thing in the world" (everyday; it
  would match other episodes), nor the borderline "I wanted to taste you", "got comfortable on the
  couch", "ready to get down to business". Her untick of "called Calvin Klein a boring old fart"
  (flagged as crude humor; an insult) is taught as a false alarm. `LINE_WORDS["sexref"]` adds
  "skinny dip/dipping/dipped" (not "skinny dippers found her", police talk), "chastity belt" and
  "naked photos/pictures/pics/selfies" (not "the naked eye/truth"). The picture scan took 4.9 min
  like the 1.18.60 report's, so whether the laptop had switched runtimes couldn't be told: the
  scan record now says (`pc.picture_runtime`).
- Each conversation's flirting check asks a quick yes or no first (1.18.68, 2026-11-12; the
  owner: "is there any other places to check efficiency", then "1": the AI helper's reading on
  her laptop, 27 of 40 minutes there). The two models never share the card (Ollama swaps the
  picture model out), and the reading questions are small (850-1,000 tokens, so `NUM_CTX` 4096
  would do, but it gained nothing: 34.5 s against 34.9). With the dialogue model 61% on the card
  (`num_gpu` 23, as on her laptop) reading 100 lines took 9 s against 7 s, but each conversation
  35 s against 10 s: the full answer form (lines, quote, "what") made it write 45-170 tokens for
  every conversation, and writing is what's slow off the card. `romance_scenes` now asks the very
  same words with `QUICK_YES` ({"romance": bool}) first and only asks the full question (then the
  confirmation) on a yes. On 270 conversations in 6 episodes (full card) the quick question said
  yes to every one the full one did (2 more maybes, ruled out by the full one); the quick
  questions took ~20 s an episode against 70-95 s. At 61% on the card the whole check went
  225 -> 122, 203 -> 105 and 258 -> 110 s (Castle S1E2's two copies, The Resident S03E12). The
  same-sex finds (what gets cut) were identical; two man-and-woman ones (not cut) differed, one
  each way (the full question now reuses the quick one's work, which nudges numbers off the
  card), while the old way gave the same answers twice.
- The picture checkers run on onnxruntime 1.24.4 (1.18.67, 2026-11-12; the owner: "Yes, build
  it", after the 2 AM check). It scans the picture about a fifth faster than the 1.31.0 installs
  had, with identical results: The Resident S03E12 230 -> 172 s, Castle S1E2 216 -> 176 s,
  Person of Interest "Til Death" 231 -> 194 s, every nudity and picture-AI score the same; the
  listening and sound check gave the same words and scores (sherpa-onnx has its own runtime),
  and the voices (`_separate_fast` uses this one) were identical on all 90 past videos here, at
  the same speed. It was the version, not the DirectML build tried before. `ORT_VERSION`; an
  install with another version switches once on "Getting ready" ("faster picture checker",
  `ort_switch_wanted`, `switch_ort`: `pip install --no-deps onnxruntime==1.24.4` in the venv,
  then a separate process checks it loads, else the old version goes back; the mark
  `models/picture_runtime.txt` says "done" or "failed N", up to `ORT_TRIES` 3). The first
  install of the picture checker and `installer/install.ps1` pin it. Tried on a copy of this
  PC's venv: switched in 9 s, nothing else changed, the 10-minute clip 57 -> 42 s.
- Pause and Resume (1.18.66, 2026-11-12; the owner: "should we have a pause buton next to the
  cancel button when a check is happening", then "when the 2 am task is done yes build it").
  "Pause" sits beside Cancel on the working page (watching and listening, and saving); pressed,
  it says "Resume" and the line says "Paused - press Resume to carry on." (`toggle_pause`,
  `PAUSED_SAID`; progress messages meanwhile don't overwrite it). `engine.PAUSE`
  (`Pausing`) freezes the helper processes it tracks and everything they started
  (`process_family`, `_freeze`: NtSuspendProcess/NtResumeProcess) and lets them go in
  reverse; tracked are each video worker (`_run_workers`, no new worker starts while paused)
  and ffmpeg while saving (`render`'s `attempt`). Ollama is shared and not frozen: it
  finishes the question it's on and the frozen worker reads the answer on Resume. While
  paused the stuck-save watch doesn't count (`seen["moved"]` kept fresh), the save's and the
  window's time left leave the paused time out (`paused_for`, `_work_t0`), and `keep_awake`
  lets the PC sleep (one helper thread asks Windows for it and lets go, `PAUSE.listen`).
  Cancel, closing the window, and work that ends resume first (frozen workers couldn't
  stop), new work never starts paused, and `atexit` resumes anything left frozen. Tried in
  the real window on a 2.5-minute clip: paused while listening, the helpers used 0.00 s of
  processor time in 8 s, then carried on and finished. Wanted in CleanListen, CleanRead and
  ReadAloud too.
- A PC without a graphics card gets longer time limits for the AI helper (1.18.65,
  2026-11-12; the owner: "everything would work on a computer with no dedicated gpu right?",
  then "Yes, build it"). Everything already ran without one (listening, the picture scan and
  voices are on the processor anyway; saving falls back to the processor's encoder), but the
  AI helper on the processor is 7-8 times slower: on this PC with Ollama's `num_gpu` 0 a closer
  look took 76 s instead of 9 s, reading 100 lines 62 s instead of 9 s, checking them for
  flirting 65 s instead of 12 s, with no time limit hit; a slower PC could reach the 4-minute
  limit of a closer look. `ai.chat` now gives each question `SLOW_TIMES` (3) as long when the
  model isn't mostly on the graphics card (`time_factor`: `on_card_share` below `GPU_MOST`,
  remembered per model in `_card_share` once it's loaded; not loaded yet counts as slow, since
  that question also loads it). A Castle episode's AI part would take about 45 minutes there
  instead of 8; The Resident (100+ closer looks) 2-3 hours. Turning the AI helper off is the
  quick way on such a PC.
- One CleanView at a time, with an "Opening CleanView..." box (1.18.64, 2026-11-12; Lauren:
  "it can take several second and gives no indication it is opening. so i click again and get
  multiple windows open. I only want there to be a single instance", "The program can take
  time to open if it needs, but give an indicator box it is opening"). `launcher.pyw` is now
  two parts. The one started from the Start menu (`clicked`) brings an open CleanView forward
  and stops when one holds the lock `ONE_NAME` (or another click is already opening one,
  `OPENING_NAME`); otherwise it starts CleanView as its own process (`start_app`:
  CleanView.exe where it can be, else this Python; `launcher.pyw --app`) and shows a small
  box (`splash`: "Opening CleanView...", a moving bar, and what `opening()` last wrote, e.g.
  "Getting CleanView 1.18.64...") until a window of that process or one it started is up
  (`family`, `windows_of`: a venv's pythonw.exe starts the real Python, which owns the
  window), it stops, or `SPLASH_MOST`. The app part (`run_app`) takes `ONE_NAME` for as long
  as it runs (`hold`, a Windows mutex; a second one 3 s later brings the first forward),
  writes its process number (`PID_FILE`, for `bring_forward`), checks for an update, then
  opens CleanView.pyw as before. "Update now" (CLEANVIEW_UPDATED set) skips the check and
  waits up to `RESTART_WAIT` for the old one to close. Tried for real from a copy: the box at
  0.6 s, CleanView at 1.3 s, two more clicks opened nothing and CleanView came to the front;
  Update now opened the new one 0.9 s after the old one closed. Wanted in CleanListen and
  CleanRead too (each its own lock).
- Medical needles are Medical, drug use stays Drugs (1.18.63, 2026-11-12; the owner: "yes, but
  be sure drugs are separated"). The drug finds (CLIP's "a person injecting drugs" also fires on
  shots and IVs) are looked at with `LOOK["drugs"]` answering "drugs", "medical" (a needle going
  into someone's skin for a medical reason: a shot, a blood draw, an IV being put in, a
  dentist's injection, insulin) or "neither" (an IV bag hanging, vials, blood tubes, pills, a
  lab or pharmacy, a syringe not going into anyone); `v["medical"]`. A medical needle is a
  "Medical" scene (cut with the box on, offered unticked with it off, `NEEDLE_KEPT`); the drug
  finds are looked for whenever Medical is ticked (`needs`), and drug use is only cut with
  Drugs ticked. Claude's `PIC_RULES` put medical needles under "medical", never "drugs", and a
  local "Drugs" scene it calls "medical" is relabelled. On the 52 drug finds in past picture
  scans here: 17 medical (needles going in; a needle into a vial and a held blood tube the
  borderline ones), 35 neither (pharmacies, pills, IV bags, labs); the first wording also
  called IV bags, vials and a pipette medical. Her shows have no real drug use to test the
  other way. `OPT_TEXT` describes Medical (it was missing in 1.18.62) and drugs as illegal.
- Medical is its own filter (1.18.62, 2026-11-12; the owner: "a lot of the 'gore' that gets
  flagged is medical. would it be good to create a separate filter that separate medical from
  other gore", then "autopsies are medical only for adults though. ticked everywhere else").
  "Medical  (surgery, autopsies, wounds being treated)" sits after Gore (`medical`): ticked for
  Young kids, Kids and Teens, not Adults (Gore stays ticked there). Settings from before it
  follow Gore (`full_opts`: `medical` None -> gore or graphic). The AI on this PC's gore look
  also answers "medical" (`MEDICAL_ASK`, `LOOK["gore"]`, `v["medical"]`); blood or insides in a
  medical setting become a "Medical" scene, cut when the box is ticked, and offered unticked
  when it isn't (`MEDICAL_KEPT`: on 23 crime-scene finds from Castle it called 2 medical). On
  the 39 hand-labelled The Resident gore scenes it called 38 medical, and the gore level got 36
  right (33 before). Claude, ChatGPT and Gemini get a "medical" kind and violence level, and
  `PIC_RULES` says blood in a medical setting is medical, never graphic or gore (a crime scene
  with medics there isn't). Passed to CleanListen and CleanRead as a passage filter (graphic
  medical descriptions).
- Lauren's Castle S2E1 report (1.18.61, 2026-11-12, adults, the AI helper, on 1.18.60): two
  wrong flags. "That's a long way to go for a robbery." was muted as the lesson "...for a lube
  job" (8 words shared, `LearnedLines._overlap`), but the joke is in the words that differ: a
  shared stretch no longer counts when both lines go on past it with other words at the same
  end (`_ends_differ`; one word each is a word heard differently; a lesson split across heard
  lines stops at the split). All 238 lesson matches in the 125 past reviews here still match.
  And "Now, that's kind of hot." (Castle to Beckett) was cut as same-sex flirting between "two
  men": the AI helper's reason named Ryan and Beckett, and names don't say who's a woman. When
  it says two men or two women but a man's and a woman's voice are heard in the flirting and
  the lines around it (`ai._voices_mixed`, `"mixed"`), the scene is offered unticked
  (`flirt_scenes`, `VOICES_MIXED`). Her other unticks were hers: the morgue body with its
  organs out (gore), and "fuck" heard in the Russian mobsters' scene (no subtitles there).
  On her laptop the AI helper's reading took 27 of the 40 minutes (63% of qwen3:8b on its card).
- A badly numbered episode still gets its subtitles (1.18.59, 2026-11-11). Lauren's "Castle
  Season 1 - Ep. 3.mp4" is really S01E04 "Hell Hath No Fury" (the councilman and Tiffany), so
  episode 3's subtitles lined up 4% and none were used (her adults report: no subtitles, the
  learned Castle lines carried it). The owner: "yes. also build in if it is say season 2
  episode 5 but says season 3 episode 5. it could be a badly marked season". `other_subtitles`
  now tries, after up to `OWN_TRIES_FOR_EPISODES` (3) of the episode's own, the best subtitles
  of each neighbour (`neighbour_episodes`, `NEIGHBOURS`: episode +1, -1, +2, -2, then the same
  episode in the season before and after; never season or episode 0), and the first that lines
  up is used (`pick_subtitles` stops fetching there), its note saying "(they're for episode
  4, so this file's episode number may be off)" or "... season 2, so this file's season
  number ..." (`neighbour_note`). Videos whose other subtitles were tried before get one more
  go (`other_subtitles_tried.txt` without `NEIGHBOUR_LOOKUP`). Live check with what was heard
  in S01E04 under that name: episode 3's lined up 4%, episode 4's 95% (904 lines).
- Each scan says how it went (1.18.58, 2026-11-11; the owner, after a Forrest Gump report
  didn't say which picture model made it: "yes to adding the name of the version, if you can
  think of any other data that would help in that can add it"). `analyze` keeps `st["scan"]`:
  `app_version`, the AI helper's `models` (pictures, dialogue), `minutes` per step (from the
  progress messages: `scan_step`, `SCAN_STEPS`; "listening", "picture scan", "closer look",
  "voices", "reading the dialogue", ...), the `closer_look` counts (checked, kept, dropped,
  failed) and the `pc` (threads, memory, how much of each AI model sat on the graphics card:
  `ai.on_card_share`, which loads nothing). Notes say it plainly: "The AI helper used
  qwen3-vl:8b-instruct for the picture and qwen3:8b for the dialogue (CleanView 1.18.58).",
  "The AI helper took a closer look at 12 scene(s): 3 kept, 9 dropped.", "Took 14 min:
  listening 1.8, picture scan 4.3, ... (minutes)." (`took_note`, last). "Send what we
  refined" carries `scan` for each video (None for reviews made before).
- A newer AI model that wouldn't download is tried again (1.18.57, 2026-11-11): on Lauren's
  laptop the new picture model's download (6.2 GB) failed on 1.18.56's first try, CleanView
  rightly went on with the old model, but the mark (`_upgrade_mark`) said "tried" and it would
  never try again. Now it says "done" or "failed N" (`_note_upgrade`, `_upgrade_tries`; the old
  "tried" counts as one failure), and "Getting ready" tries again on the next scans up to
  `UPGRADE_TRIES` (3); Ollama picks up a download where it stopped.
- The closer look uses qwen3-vl's instruct build (1.18.56, 2026-11-11; the owner: "Yes, build
  it", and "remember where we are if want to change back": 1.18.55, commit e999b75, is the last
  with the thinking build; going back is a revert, and the old model stays installed on every
  PC). Plain `qwen3-vl:8b` is the thinking build: it ignores `think: false` and silently works
  through each question first (200-1,000 tokens for a ~60-word answer), ~16 s a look on this PC,
  and the same question runs away the same way every time, so `recheck_failed` couldn't save
  those. Side by side on 183 scenes from 46 past videos (The Resident, Person of Interest),
  Lauren's adult settings: instruct ~7 s a look, none failed; thinking 11 failed at the
  4-minute limit (9 of 29 kisses). Instruct was right on all 4 drug disagreements (a drip, a
  blood draw, an injection are not "illegal drugs"), even on kisses, the same on gestures,
  mixed on nudity (it calls a shirtless patient "implied"). On gore it answered "blood" even
  for open surgery when asked for a level, so `LOOK["gore"]` is now a checklist (`GORE_SEEN`:
  blood, a bloody wound, open surgery, organs, brain, bone, a severed or mangled body part, a
  bruise or rash, stitches) and `gore_level` decides: anything inside a body is Gore, blood
  alone Graphic, a bruise, rash or stitches nothing. Scored against 39 gore scenes labelled by
  eye: checklist 33/39 (29 of the 30 clear-cut), thinking 34/39 (28/30), the old question 18/39;
  adding a backstop from its own description didn't help. `VISION_MODELS` starts with
  `qwen3-vl:8b-instruct` (then the thinking build, then qwen2.5vl); existing installs download it
  once on "Getting ready" ("newer AI models", 6.2 GB). The Resident S03E12 with the same saved
  scans: the AI helper's part 19.7 -> 4.3 min; lines, mutes and voices identical; a passionate
  kiss the thinking build had timed out on is now cut, the surgery cut a little more fully, and
  one short kiss it had offered unticked isn't found.
- At most 50 plain terms to a filter (1.18.55, 2026-11-11; from CleanListen 1.17.20, the owner:
  "Yes, add it"). CleanListen's Scarlet (Unabridged), one 7-hour MP3, failed to save with
  "Error when evaluating the expression ... for enable" using the 1.18.26 scheme (500 ranges to a
  filter, bracketed in 50s); neither app could make it fail here, but 50 plainly added up reads
  in any ffmpeg. `_mute_filters`, the quieter music (`_chunks`, `RANGES_PER_FILTER`) and the cuts
  (`_cut_filters`: one select/aselect per 50, which leave the times alone, then one
  setpts/asetpts) are chains of filters; only the time the cuts take out (setpts can't be
  chained) is still bracketed past 50 cuts (`_sum`). The same in `cvcore._range_filters`.
  Save errors shorten ffmpeg's long quoted expressions (`_short_error`), so its reason shows.
- Nothing heavy runs beside the AI helper (1.18.54, 2026-11-10; the owner: "lets get back to
  effieciency", "All four", then "Yes, trim and test"). Whole cleans timed on this PC (16
  threads, 8 GB RTX 5070), Lauren's settings: Castle S1E2 12.5 min (picture scan 4.3, the AI
  helper's reading 3.5, listening 1.8, voices 1.3, closer look 1); The Resident S03E12 24 min,
  16 of them the closer look (~150 scenes). The AI helper (Ollama; its models are only partly
  on the graphics card) slows down badly whenever the processor is busy, so running things
  beside it lost time: reading the dialogue during the picture scan made Castle take 25 min
  (each conversation 2 -> 17 min); telling voices apart during the closer look (1.18.46)
  made its checks time out and be done again (16 min instead of 12); the picture scan during
  the listening was 25 s slower. Kept: the AI helper starts in the background (`start_ai`
  in analyze, waited for after the listening; the window starts it in a thread instead of
  waiting up to 20 s; `ai.ollama_starting` (tasklist) so a second server isn't started),
  the closer look runs on its own and always ends with `recheck_failed` (a scene was left
  "not double-checked" without it), "Finding language" has its own small part of the
  progress bar (`lay_out`, step "lang"; it showed 97% then went back to 79%; language is
  found before the picture now, its notes still after the picture's, `lang_notes`), and
  speaker numbers are the same every run (`line_voices` split a man/woman tie by a set's
  random order: `min(sorted(kinds), ...)`). Every line, mute, scene and note came out the
  same as before in all the runs. The closer look itself is now the slowest step.
- A save that stops moving is stopped and tried another way (1.18.53, 2026-11-10; Lauren, on
  her MSI laptop: Castle S1E2 "(Clean)", a clean copy cleaned again after the update, got stuck
  saving several times and nothing said why; "Yes, add it"). Re-saving clean copies here worked
  every way tried (mutes only, with and without subtitles), so the cause is on that laptop.
  `render`'s `attempt` watches ffmpeg's progress from another thread (a stuck ffmpeg prints
  nothing, so the read loop would wait forever and miss Cancel too): when neither `out_time_us`
  nor `total_size` has grown for `SAVE_STUCK_SECS` (300; not after `progress=end`, while the
  index is moved to the front) it's stopped, the partial copy removed, and the next way tried
  (another encoder, then the careful way). The progress line says "no progress for N min;
  after 5 it tries another way" (each `SAVE_STILL_SAY`). If every way gets stuck, the error
  starts "Saving the clean copy of ... stopped moving at 12:34 of 41:00, every way it was
  tried" (`STUCK_SAID`, `_clock`), with what ffmpeg said, and the window offers to send it in.
- Telling voices apart is faster with the same results (1.18.52, 2026-11-10; the owner: "why
  do we need to tell voices apart?", then "1, 2 and 3"). Speaker separation took 3-4 minutes of
  a 44-minute episode, mostly sherpa-onnx making ~3,800 voice prints one at a time.
  `ai._separate_fast` does sherpa 1.13.8's own pyannote steps (a port of
  `offline-speaker-diarization-pyannote-impl.h`) with the 10-second windows and the voice
  prints several at a time (`speaker_workers`: 4 copies x 2 threads on 16), using sherpa's own
  voice-print maker and grouping, and copying its float32 rounding, MSVC `partial_sort` ties
  (`_top_k`), joining and sorting. Only with sherpa-onnx `PORTED_SHERPA` (the installer doesn't
  pin it); another version, a clip of one window or any error uses sherpa's own, now with 8
  threads on 16 (`speaker_threads`; small PCs as before). The man/woman/child guess runs
  several lines at once on its own tagger copies (`find_voices`: cpus/2, at most 8;
  `line_voices` takes a list). Checked against the speakers saved for all 113 past videos
  (75 hours, 62,809 speech parts): every one identical, 7,872 s in all (about 77 s for a
  44-minute episode, was 186-234 s); The Resident S03E12's 763 guesses 11 s -> 3.5 s, identical.
  Measured and rejected: more threads for sherpa's own (8 = 12 = 15, all the same speakers).
- Dark scenes are brightened and checked, not skipped (1.18.50, 2026-11-09; the owner: "the
  picture scanner skips dark frames, is that going to allow intimate scenes through?", then
  "Yes, build and test"). In 148 saved reviews 42% of the intimate scenes cut were mostly
  `too_dark`, and only Claude saw them. `_visual_scan_here` now stretches a too-dark frame's
  levels (`ai.brighten`: 1st-99th percentile, at most `LIFT_MOST` 4x so noise isn't blown up)
  and checks it when that shows something (contrast >= FLAT_STD); its number goes in
  `pictures.json` `"lifted"` (lum stays the original). `nudity_scenes` and `clip_candidates
  (lifted=)` count lifted frames; the scene is marked `"lifted"` and the AI helper gets its
  stills brightened the same way (`grab_frames(lift=)`, ffmpeg `colorlevels`). Brightened
  frames are noisier, so a dark nudity scene starts unticked ("not double-checked, so only cut
  if you tick it", `DARK_UNCHECKED`) until the AI helper confirms it (`check_nudity`); dark
  kiss/bed finds were already unticked unchecked. Black or featureless frames stay skipped.
  `PICTURE_VERSION` 4, so older scans are done once more. Trial on 63 episodes with saved
  answers: 18 of 22 dark intimate scenes caught (none before without Claude), 19 false alarms
  (Claude listed nothing there; ~1 every 3 episodes). Scores on frames bright as they are are
  identical; the scan takes longer in dark shows (The Resident S03E12, 22% dark: 211 -> 264 s;
  Person of Interest "Til Death", 59% dark: 139 -> 274 s), and the AI helper has more to look
  at (6 -> 9 and 0 -> 5 finds).
- The listening and the sound check are faster with the same results (1.18.49, 2026-11-09;
  the owner: "lets do the audio now", then "Just 1 and 3"). `load_listeners` loads two
  speech recognizers (threads split) when `how_many_listeners`: this video has 6+ threads
  and `available_memory_gb() >= LISTENER_GB` (3; each copy is ~0.7 GB); `transcribe` takes
  one or a list and hears each 30 s part on its own, two at a time, results kept in order.
  The sound check (`sound_scan`, `load_tagger(2)`) runs in the background during the
  listening when both are needed; on its own (old way) when the words were heard before.
  Measured and rejected: more listening threads (12 = 8), several parts in one decode
  (changes the words: 316 became 325), 3 listeners (1.4 GB extra). Not chosen: the picture
  scan during the listening (23% less for the pair on this PC, less with videos at once).
  Old vs new, this PC: 5 min of Curious George, listening 14.6 s -> 10.7 s; whole runs
  (listening, sounds, pictures) The Lamp of Love 26.4 -> 22.7 s, Living for the Light 47.5
  -> 40.8 s, Curious George (87 min) 15 min 49 s -> 12 min 48 s; all 7,871 words and every
  sound score identical.
- The picture scanner is faster with the same scores (1.18.48, 2026-11-09; the owner: "is it
  optimized fully?", then "1, 2 and 3"). `_visual_scan_here` reads frames on the main
  thread, skips those `too_dark` (rounded lum < DARK_MEAN 40 or < FLAT_STD 18, exactly what
  nudity_scenes and clip_candidates leave out; scores stored as 0, left out of the clip
  list), batches the rest for NudeNet, and sends every other one to the picture AI on its
  own thread (bounded queue). `scan_threads`: nudity cpus//4 (max 4), picture AI cpus//2
  (max 8), idle threads don't spin. Measured and rejected: batching CLIP (changes its int8
  scores), more threads (15 took twice as long as 10), hardware video decoding (2x slower),
  a faster resize with the same math (no faster; faster math changes the numbers). Option
  4, NudeNet/CLIP on the graphics card (DirectML), is saved to consider later. Old vs new
  on real videos (this PC, 16 threads):
    - Living for the Light.mp4: 473 frames (13 dark), 34.8 s -> 23.0 s (34% faster); score differences 0/0, same scenes True, same finds True.
    - Whispers in the Willow.mp4: 488 frames (7 dark), 37.3 s -> 24.2 s (35% faster); score differences 0/0, same scenes True, same finds True.
    - The Road to Friendship_ Zoo Adventures: 496 frames (49 dark), 37.2 s -> 21.5 s (42% faster); score differences 0/0, same scenes True, same finds True.
    - 1. Curious George.mp4: 10478 frames (397 dark), 765.4 s -> 482.3 s (37% faster); score differences 0/0, same scenes True, same finds True.
- The AI helper's answers are kept (1.18.47, 2026-11-09; the owner, after CleanListen
  1.17.15 did it for CleanRead: "Yes, add it"). `ai.chat` keys each question by its whole
  Ollama payload (model, words, stills, answer form, settings) and keeps the answer in
  `APP_DATA/ai_answers/<key>.json` (newest `KEEP_ANSWERS` = 20,000, pruned every 200
  saves); `_chat_now` does the asking. A stopped or cancelled run picks up where it left
  off, and the same episode gives the same closer looks and dialogue flags each run (weak
  spot 3, for the local path; Claude/ChatGPT's answers were already kept in `answers`).
  Errors and replies without JSON are never kept. On a spoken test video a second run took
  18 s instead of 54 s with identical results.
- Three checks run while other work goes on (1.18.46, 2026-11-09; the owner: "are there any
  other checks you can see that dont happen simultaneously?", then "yes do all 3. build it so
  that if a gpu isnt available it will still perform all of the double checks"):
  1. `fetch_subtitles` (the .srt/text track, else downloaded before, else a download unless
     none were online last time) starts in the background at the top of analyze() and is
     waited for at "Finding language…". Syncing to what was heard is unchanged.
  2. Claude/ChatGPT's look through the whole picture (`whole_picture`: contact sheets +
     `cc.picture_review`, which now stops between batches on cancel) starts in the
     background once what was heard and the subtitles are in (copies of both), and
     `look_at_picture(..., finds=...)` uses it; returns (finds, stills seen) for the note.
  3. Local only (no cloud reading): when `ai.on_graphics_card()` (loads the picture model
     at `NUM_CTX` like chat(), then /api/ps: `size_vram >= GPU_MOST` (0.5) of `size`; an
     8 GB RTX 5070 holds ~76% of qwen3-vl:8b), voices are told apart in the background
     during the closer look. No graphics card or not knowing: one after the other as before.
     Undone in 1.18.54: it slowed the closer look until its checks timed out.
  Every closer look that ran alongside something (this one, and the one in the background
  while Claude reads) ends with `recheck_failed`: scenes whose check failed (a time limit)
  are looked at again on their own, so every double-check is still done. Checked on this
  PC with a spoken test video: old and new code gave identical scenes, lines, mutes, notes
  and dialogue, local and with a stand-in for Claude.
- The nudity found is double-checked in the same go as the other scenes (1.18.45,
  2026-11-09; the owner: "it seems to spend a lot of time stuck on 'checking nudity'. but
  when it showed the results there wasnt any nudity"). The AI on this PC looked at the
  nudity after reading the dialogue, so the picture model (qwen3-vl) was loaded again just
  for a few false alarms. Now `nudity_checks(nudity_scenes(vis))` join the picture AI's
  candidates in the first closer look (`todo`, also in the background while Claude reads),
  and `check_nudity(..., look=None, checks=...)` uses their verdicts. Same model, stills
  and question. Without the picture AI (no CLIP), the old separate check still runs.
- Cancel goes back to the start page at once (1.18.44, 2026-11-09; the owner, in CleanRead:
  "it taking a while to actually cancel and go back to home screen", then "send this fix to
  clean view and read aloud alos"; CleanListen/CleanRead 1.17.12 do the same). Watching and
  listening, and saving, run through `_start_work(target)`, which gives each its number
  (`self.run`). Every message from that thread is `("for_run", run, msg)`, and `_handle`
  drops it when `run != self.run`. `cancel()` bumps `self.run` and shows the start page
  straight away. The old thread stops at its next check (`stopped()`: `cancel_flag`, which
  closing the window still sets, or a newer run): the workers are told to stop
  (`stop_all`, up to 8 s, now out of sight), and a save's half-written copy is removed
  (`render` writes to a temp file and only renames it when done). New work joins the old
  thread first ("Finishing stopping the last one…"), so two runs never share a work folder
  or output file. `_analyze_now` keeps its own `jobs` list.
- Long steps count under the progress bar (1.18.43, 2026-11-09; the owner, after CleanRead's
  double-check sat unchanged: "is it frozen?", then "can we add the same change to clean read,
  clean view als?"; CleanListen/CleanRead 1.17.10). `counted(progress, f, a, z, total, what)`
  in cleanview_ai and cleanview_claude calls `progress(f, "21–40 of 95")` (falls back to
  `progress(f)`); callers take `lambda f, n="":` and add `also(n)` (" · 21–40 of 95").
  Counted: the local AI's closer look at scenes and nudity, reading the dialogue (lines
  1–25 of 928) and its double-check, each conversation, the cloud's stills (20 per sheet),
  scene checks and scene edges; `in_background`/`wait_for` pass the count on. The cloud's
  dialogue reading and final review are one or two big requests, so they have no count.
- Built-in lessons for an older age count for younger ones (1.18.43, Lauren's Castle S1E3,
  2026-11-09, teens with the local AI: all 191 of the show's lessons were under "castle",
  learned from adults' reports, and a teens run looked only under "castle@teens", so none were
  used and 21 of the episode's lines went through). `learn._age_keys(key, older=True)`: a
  "muted" lookup reads this age's key and every older age's (adults: no "@", or "@adults");
  "kept" and "ok_words" stay with their own age. `LearnedLines` also matches when the two
  lines share a stretch of 8+ words that's 60%+ of the lesson, a word heard differently now
  and then ("Ryder Boy" for "writer boy", a lesson split across two heard lines).
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
| `cleanview_ai.py` | Local AI: CLIP (ViT-B/32 ONNX) picture categories, NudeNet, audio tagging, speaker separation (pyannote segmentation + TitaNet via sherpa-onnx), and the Ollama helper (`qwen3-vl:8b-instruct` checks scenes, then the thinking `qwen3-vl:8b`; `qwen3:8b` reads dialogue; falls back to qwen2.5). |
| `cleanview_claude.py` | Claude through the **Claude Code CLI** (`claude -p --json-schema ...`, uses the user's Claude plan, no API key). Dialogue reading, the final "review everything" pass, the chat, picture review from contact sheets. Also the provider switch (`use("claude"/"chatgpt")`). |
| `cleanview_gpt.py` | ChatGPT through the **Codex CLI** (`codex exec ... --output-schema`), same interface as the Claude path. Strict JSON schemas (all properties required). |
| `cleanview_gemini.py` | Gemini through Google's **Gemini CLI** (`gemini -p ... -o json`, signed in with a Google account, no API key), same interface. Installed with npm (needs Node.js 20+). The CLI can't take a schema, so the shape is described in the prompt and the reply is checked (asked again once). The prompt goes in through stdin; pictures are copied into an empty work folder and named with `@picture1.jpg` on the command line. Chats are kept by CleanView (`APP_DATA\gemini\chats`), not the CLI. Provider key `"gemini"` (`cc.OTHERS`). |
| `cleanview_accounts.py` | Each person's own Claude, ChatGPT or Gemini sign-in inside CleanView ("Use a different account" / "Sign out" on the start page). Claude Code, Codex and the Gemini CLI keep their sign-in in a folder (`CLAUDE_CONFIG_DIR`, `CODEX_HOME`, `GEMINI_CLI_HOME`); CleanView's own is `APP_DATA\accounts\<ai>\<n>`, so the PC's own sign-in is never signed out or changed. A new sign-in goes in a new folder and is only used once it worked (`keep()`). With none, the PC's sign-in is used. |
| `cvlang.py` | Other languages (1.18.80, Spanish first): the list of languages, each one's word lists and guards, the listening model for other languages and its one-time download, and the language being cleaned now (`LANG`). Must not import cvcore. |
| `cvlook.py` | The drawn look (1.18.77): rounded cards, pill buttons, switches, the segmented choice, option cards, icon badges, chips and tick boxes, drawn with numpy as PNGs for Tk, and the ttk buttons, tabs, scroll bars, progress bar and fields in the same look. tkinter and numpy only. |
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
- `test_save_stuck.py`: a stand-in ffmpeg that hangs is stopped and the careful way saves
  it (or, stuck every way, the error says where; with cuts the next encoder is tried); a slow
  but moving save, and the quiet end, aren't stopped; Cancel works while ffmpeg is silent; the
  progress line says it hasn't moved.
- `test_picture_model.py`: the instruct picture model first (the thinking one until it's
  downloaded on "Getting ready"; a failed download tried again up to 3 times, the old "tried"
  mark counting as one, "done" once it worked), and the gore checklist: what it ticks decides
  Gore, Graphic or nothing (a rash is dropped), as asked in the closer look.
- `test_scan_record.py`: progress messages belong to the right steps, the "Took ..." note,
  how much of a loaded model is on the graphics card, and the record in "Send what we refined"
  (none for an older review).
- `test_save_space.py`: the size estimate, the save folder and room on the review page,
  and asking before saving when it won't fit.
- `test_spanish.py`: Spanish words found by group (and everyday look-alikes left alone: folleto,
  vergüenza, concha, perra, Jesús the name, rayos X), only ticked groups, her own words, only
  listed words muted alone; English exactly as before and after switching back; the AI
  readers told the language; the model only needed for another language, downloaded once from
  a stand-in server and put in place, a wrong or failed download leaving nothing; a Spanish
  video without the model says so; the video's own language for .srt files, the sound track
  and the online lookup; the choice on step 1 kept. With `CLEANVIEW_TEST_MULTI` set to the
  real model's folder, real Spanish is heard and one of its words muted.
- `test_french.py`: the same for French: words by group, the joined-on short words taken off,
  everyday look-alikes left alone (un baiser, la ferme, pique-nique, Homo sapiens, elle est
  mince), Quebec's swears, French .srt files and sound track; real French heard with
  `CLEANVIEW_TEST_MULTI`.
- `test_save_fails.py` (NoRoom): a save that fails on a full drive says where, how much is
  free and what to do, and isn't offered for sending; an unexpected failure still is.
- `test_language_switch.py`: Spanish picked and English heard cleaned as English (listened to
  again with English's model, its words muted, the note, subtitles looked for again in English
  after the first look), French picked and Spanish heard, the note not technical, cleaned again
  from what was heard before; the right language, too little heard and English picked change
  nothing; German only said.
- `test_one_preview.py`: Preview pressed twice (or another one meanwhile) opens one player, the
  button says "Opening…" and is back after its seconds; a failed preview says so and can be
  pressed again; the page built again meanwhile.
- `test_selena.py`: the three Selena notes built in and given to every video, the older ones
  still there.
- `test_auto_language.py`: each language told from a sentence of it (also as the model writes
  it, accents or not, Spanish from Portuguese), German, Italian and Ukrainian named as not
  cleaned yet, too little or only names not told; the sound track's labels; English first then
  Auto in the list, Auto needing the model; working it out with stand-ins (the label alone,
  listening when there's none, kept, English when it can't tell, a plain refusal, no model);
  Auto taking the video's own main track; the drop-down; and with `CLEANVIEW_TEST_MULTI` the
  model's real samples and a whole clean on Auto.
- `test_portuguese_russian.py`: each language's swearing by group, everyday look-alikes left
  alone (o puto, a bicha, raios X; хуже, небо, хлеб, блин the pancake, черта, Херсон,
  гейзер), only ticked groups, listed words; an AI's quoted words found in a Russian line, a
  Russian line learned as itself, a Cyrillic file name; each language's .srt files, saved
  files and lookup; every language having all its pieces.
- `test_time_left.py` also: the wait before a step moves isn't counted as its time, no jump
  when its own speed takes over, long times in hours.
- `test_check_failed.py`: a video that failed while checked asks once, with the reason; Yes
  writes the note (no home folder in it) and sends it as a problem, No sends nothing; a
  copy-protected video alone, or no inbox, gets the old box; a send that fails keeps the file
  and says where it is.
- `test_say_ai.py`: older notes and labels shown the new way (a name at the start, after by /
  Asked / per; nothing else touched), the steps still told apart, the review page naming none
  of the three for each of them while a character called Claude keeps his name, which one it
  was still kept, and step 3 still naming them.
- `test_spanish_in_english.py`: the short Spanish list found in English sentences (with and
  without accents, the slur with the same-sex words, only with swearing ticked, an AI may
  mute them alone), and everyday English left alone (coo, con carne, Concha, Mr. Ching).
- `test_no_internet.py`: the check without touching the network (a stand-in socket; the
  setting for tests), nothing looked up offline but the video's own and earlier downloads
  still used and no miss remembered, the note; Start cleaning offline asks, No stays put, Yes
  cleans without looking online, and online nothing is asked.
- `test_sections.py` (Steps): no subtitle switch on step 1, subtitles asked for whatever an
  older settings file says, and the small print saying so.
- `test_ask_box.py`: a long answer under a scene, a line and a word is never wider than its
  box, at each text size, in the standard window and a narrow one, and after the window is made
  narrower; the answer kept on the card too.
- `test_updated_note.py`: the "updated to version" line shows after an update, is gone after
  its seconds (also "up to date"), isn't there without an update, and a page built again
  meanwhile doesn't trip over it.
- `test_castle_s2e1_words.py`: "stripper pole" found and muted from "stripper" to "pole"
  (other poles left alone); a stripper who's a person found, the tool or chemical not (paint,
  wire, wallpaper, asset stripper, stripper clip) and not muted in a line; "Sexy. Sexy's" gets a mute each, heard
  or not, and a word asked for twice but said once gets one; the two Castle false alarms built
  in as fine.
- `test_plain_notes.py`: which notes are technical and which are about the video, the review
  page showing only the video's, a real saved report file with them as its last lines under
  their heading (the version too), the saved review keeping them all, and "Send what we
  refined" carrying them.
- `test_icon.py`: the window and its taskbar button get the logo (Windows says the window has
  an icon), it's set again after the window is up, a try that fails is written down and the
  next one still sets it, a closed window is left alone.
- `test_review_speed.py`: the rounded buttons' and tabs' pictures have a wide middle for Tk to
  repeat, pieces that give their own size keep it, and a button is no bigger for it.
- `test_time_left.py`: a made-up laptop scan (reading the dialogue most of the time, a small
  part of the bar): the time left within a tenth all through the reading, never "a minute"
  with many to go, as before in the first step with nothing remembered; each step's speed
  remembered and used from the first minute next time, scaled by the video's length, by who
  reads; saved work not remembered; the file blended, and a broken one ignored.
- `test_theme.py`: both looks name the same colours, light is the look as it was, dark sets
  every name and the drawn pieces, dark text can be read, the note box isn't brown in dark, no
  colour written into a page; the button changes the look, keeps her choices and step, is
  remembered; every page builds in dark.
- `test_hard_rule.py`: fart, condom and semen always removed (not farther, condo, seaman); the
  word muted wherever it's said with its box ticked, also in a line left alone and in
  detective or coroner lines with that box on or off; no AI or built-in lesson keeps them; a
  condom in the picture looked for with the sexual references box, double-checked, offered
  unticked when it isn't, and asked of Claude, ChatGPT and Gemini.
- `test_explicit_findings.py`: what counts as explicit detail in a finding (not tearing up a
  letter, a bullet that penetrated, plain case talk); the whole line muted with sexual
  references ticked, the coroner box on or off; not undone by an AI or a "fine before" hint,
  still by her own choice.
- `test_code_check.py`: the bugs the code check found (a word said twice, the word itself
  before a longer one, another video's subtitles, a stretch inside another, a shorter lesson
  further on, a long conversation's split, a preview kept by start and end).
- `test_save_folder.py`: the chosen save folder kept after closing and when videos are chosen,
  "Next to the video" going back, a missing folder passed over but kept, other settings not
  losing it, and "Change..." on the review page kept too.
- `test_sections.py`: the nine sections hold every filter, Medical on its own, each tile's
  switch (some -> all -> none, the kissing choices too), the counts after changing age, one
  section open at a time and remembered; the steps (one shown at a time, Next and Back, the
  list saying what's chosen, Start without videos going to step 1, a video that has gone, a
  click needing a press and a let-go on the button).
- `test_coroner_talk.py`: the coroner/doctor filter everywhere a filter needs, per age; its
  short list (not everyday talk); case talk not a sexual reference and left alone with it off,
  whole lines muted with it on; the Castle coroner lessons only with it.
- `test_castle_drive_reports.py`: the Drive folder's Castle lessons built in, her unticks not
  muted (the two joined lessons gone), the innuendo after them still muted, no coroner talk.
- `test_sexual_talk.py`: a conversation's sexual talk found (quick yes, which lines, each
  confirmed), not when the quoted words aren't there or the line-by-line look says no, the
  quiet conversations asked nothing more, innuendo counted; in the reading only with that
  filter and not when Claude reads; a listed word stays just the word.
- `test_castle_s2e3.py`: its lines built in for Castle (not the coroner's or everyday lines),
  the insult a false alarm, skinny dip / chastity belt / naked photos on the short list (not
  skinny dippers, the naked eye), and the scan record's picture runtime.
- `test_laptop_speed.py`: each conversation is asked a quick yes or no first, with the same
  words, and the details and the confirmation only on a yes.
- `test_picture_runtime.py`: the switch wanted (another version installed) and not (already
  1.24.4, or none: the first install pins it), done with --no-deps, put back when it won't
  load, given up after 3 failures; "faster picture checker" on Getting ready only when the
  picture is checked; new installs pinned.
- `test_pause.py`: what pausing freezes and unfreezes (each process's family, in reverse,
  one started while paused at once, finished or untracked ones left alone), paused time
  counted, listeners told; a real counting process stands still while paused and goes on
  after; keep_awake lets go and asks again; a save paused longer than the stuck-save limit
  isn't taken as stuck; the window's button, Resume restoring the line and leaving the pause
  out of the time left, and Cancel/closing/the workers resuming first.
- `test_slow_pc.py`: questions to the AI helper get 3 times as long when its model isn't
  mostly on the graphics card (or isn't loaded yet), the usual limit when it is (50% counts, as
  on Lauren's laptop), each model on its own, and no Ollama to ask counts as slow.
- `test_one_window.py`: the lock (held elsewhere, waited for, held twice by the same
  process), finding a window one process down, what a click does (open, opening, not open,
  Update now, couldn't start apart), the app part (another won; Update now waits longer), and
  the opening box closing when the window is up or the program stops.
- `test_medical.py`: the Medical box per age and for older settings; the AI on this PC's
  "medical" answer turns gore into a Medical scene, cut with the box on, offered with it off,
  violent gore still Gore; Claude's kind and level, wanted only when ticked; a medical needle
  is Medical and drug use stays Drugs (each with its own box), needles looked for with only
  Medical ticked.
- `test_castle_s2e1.py`: a learned line whose ending differs isn't the lesson (the lesson
  itself, a word heard differently and a split line still are); a same-sex flirt with a man's
  and a woman's voice heard there is offered unticked, only men's or unknown voices still cut.
- `test_long_mutes.py`: muted stretches of 4 s or more (joined across short pauses, mostly
  muted) are cut, shorter ones and words muted one by one stay muted; a real save is 5 s
  shorter and the report says why.
- `test_many_mutes.py`: saving with 150 mutes and 120 cuts, and 1,600 mutes and 60 cuts; each
  filter at most 50 plain terms (the cuts' setpts bracketed); long expressions shortened in
  errors; ffmpeg's "Cannot allocate memory" for a filter not said as running out of memory.
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
  filters and learned lines stay whole (a learned line's list words muted too).
- `test_castle_s1e5.py`: "the affair"/"an affair" on the short list (not Internal Affairs,
  "none of your affair", "quite an affair"); a learned line unticked keeps "affair" muted;
  the checked Castle lessons built in.
- `test_keep_awake.py`: set and cleared on the same thread (also after an error), never the
  display; watching and saving hold it.
- `test_audio_speed.py`: two listeners give the same words in the same order and both take
  turns, progress stays in order, two only with 6+ threads and 3 GB free; the sound check
  starts before the listening (on its own when the words were heard before).
- `test_voice_speed.py`: the faster speaker separation gives sherpa's own speakers on
  made-up voices (also 1 worker and 1 thread, and through `separate_speakers`); one window,
  another sherpa version or an error uses sherpa's own; ties picked as MSVC does; several
  tagger copies give the same man/woman/child guesses. Borrows the installed app's speaker
  models when the repo has none; skips without them.
- `test_dark_scenes.py`: a dim frame brightened to its full range (noise at most 4x, black
  stays black); brightened nudity and picture-AI frames count, a dark nudity scene is unticked
  until the AI helper confirms it (and bright ones ticked as before); a real scan of a bright,
  dim and black video brightens the dim part only; the AI helper's stills are brightened too.
- `test_scanner_speed.py`: "too dark" is what the scenes leave out; threads shared; a real
  scan of light-dark-light video skips the dark frames (scores 0, not in the picture AI's
  list), gives each picture-AI score to its own frame, matches one-frame-at-a-time nudity
  scores, stops when the picture AI breaks, and works without it.
- `test_ai_answers.py`: the AI helper is asked once for the same question; other words,
  model or stills ask again; errors and replies without JSON aren't kept; a stopped closer
  look picks up where it left off; the dialogue reading comes out the same each run.
- `test_overlap.py`: a whole analyze() with stand-ins: the AI helper starts while it
  listens, the rest one after the other (with or without a graphics card, the same analysis),
  notes in the same order, the progress bar only goes forward; voices not during the closer
  look and failed checks looked at again; a second Ollama isn't started; a man/woman tie
  numbered the same in runs with different hash seeds.
- `test_at_the_same_time.py`: subtitles fetched (next to the video, downloaded and kept,
  "none online" remembered, off) and started before listening; the whole-picture look done
  early gives the same scenes as done later, stops between batches, starts once heard and
  subtitles are in; "most of the picture model on the graphics card" (and not: none, a
  little, not knowing); scenes that couldn't be checked meanwhile are looked at again.
- `test_nudity_once.py`: the nudity looked at with the other scenes gives the same scenes
  and notes as looking later; it's in the first closer look (before the dialogue), not
  looked at twice, and still checked on its own without the picture AI.
- `test_cancel_at_once.py`: Cancel shows the start page before the work stops, late
  messages from cancelled work are dropped, new work waits for the old to stop, cancelled
  work never starts late, closing still stops a save, and a save cancelled partway leaves no
  copy behind.
- `test_counters.py`: "N of M" from the local AI's closer looks, dialogue reading and
  double-check, the cloud stills, scene checks and scene edges, and through a background job.
- `test_castle_s1e3.py`: older ages' muted lessons used for younger ages (not what they
  keep, filters still apply); the real Castle lessons for a teens run; lines split or heard a
  word differently match, a harmless piece doesn't.
- `test_neighbour_subtitles.py`: neighbouring episodes then seasons, nearest first, never 0;
  the notes; an episode's own other subtitles first, then one from each neighbour (a stand-in
  site), fetching stops once one lines up; a movie has no neighbours; videos tried before get
  one more go.
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
- `tests/support.py` also keeps a run from being lost (1.18.85, 2026-11-13, after two were):
  the collector is off and runs on the main thread after each test, because Tk objects of a
  closed window let go on a worker thread stop Python ("Tcl_AsyncDelete: async handler deleted
  by the wrong thread"); every `tkinter.messagebox` box is a quiet stand-in that answers
  no/OK and is listed in `support.BOXES_SHOWN`, so a box nobody expected can't hold the run
  until someone clicks (the freeze note's "send it in?" at the next start did); and
  `CLEANVIEW_ONLINE` is "1". Scratch scripts that open the real window for a screenshot must
  `import support` first too: one without it saved Dark into this PC's real settings.
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
