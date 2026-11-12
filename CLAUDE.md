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
