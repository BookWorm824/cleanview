# CleanView

Cleans up movies and TV episodes you own, on Windows. Everything runs on your own computer;
nothing is uploaded. CleanView is a separate app from CleanListen (the audiobook cleaner):
its own install, its own folder, its own updates.

- Mutes the same language list, listening to the dialogue channel of surround-sound movies,
  and uses the movie's subtitles (a matching .srt or a text track inside the file) to catch
  extra words. Writes cleaned subtitles into the clean copy.
- Filters you can switch on or off: sexual references, nudity (private parts shown), implied
  nudity (under sheets, in towels, bare backs), sex scenes, immodest clothing,
  sleeping around, man & woman kissing and same-sex kissing (keep / cut passionate / cut all),
  same-sex relationships (including flirting), words about same-sex relationships, unmarried
  couples living or sleeping together, crude humor, bullying,
  violence, graphic gore, smoking, drinking and drug use. Your choices are remembered.
- How it finds things:
  - NudeNet checks the picture twice a second for nudity.
  - CLIP (OpenAI's free image model) checks it once a second for kissing, couples in bed,
    gore, fights, weapons, smoking, drinking, drugs and revealing clothes, so scenes are
    caught even when they're silent.
  - A sound model listens for gunfire, explosions, screaming and blows.
  - The optional AI helper runs two models through Ollama on your PC: qwen3-vl:8b double-checks
    each scene the picture model found (it must describe what it sees, and says no when the
    frames are too dark or unclear), and qwen3:8b reads the dialogue for sexual references, sleeping around,
    relationship talk, crude humor and bullying. A line is only flagged when the model quotes
    the words that fit and a second, stricter question about that line agrees. It is told
    who says each line: names from the subtitles, speaker numbers from a speaker separator
    (pyannote segmentation + TitaNet voice matching via sherpa-onnx), and a man/woman/child
    guess from the sound model's speech classes. For same-sex relationships it also reads
    each whole conversation to catch flirting. If a newer model can't be downloaded or run,
    the older qwen2.5 models are used.
- Videos with no subtitles get them from the internet (subliminal; hearing-impaired ones
  first). Show and episode are read from the file and folder names, and the downloaded
  subtitles are re-timed to the words actually heard; ones that don't match are not used.
- Dark or murky frames are ignored, and a scene needs several seconds of strong hits. Scenes
  the AI helper didn't confirm are listed unticked.
- Scenes are cut; flagged dialogue lines and swear words are muted. Everything is listed
  first (scenes with blurred stills and a Preview button, then lines, then every swear word),
  and only what you leave ticked is changed.
- Pick a folder of episodes to clean a whole season in one go.
- Saves "(Clean)" copies plus a report of every mute and cut. Originals are never changed.
  Cleaned subtitles are inside the copy but off unless you turn them on in your player.
- Updates: a bar appears when a new version is ready ("Update now (keeps your place)"), or press
  F5 / "Check for updates". Your review, with everything found and every tick, is saved and
  reopened after the update. Closing CleanView mid-review saves it too ("Pick up where I left
  off" on the start page).
  Uses an NVIDIA, Intel or AMD graphics card to save faster when one is available.

Works with DRM-free video (DVD and Blu-ray rips, home videos). Copy-protected purchases
from iTunes, Vudu, Movies Anywhere and streaming services can't be used. 4K HDR files come
out with flatter colours after a cut. The AI checks are good but not perfect, which is why
everything is shown to you before it's cut.

One-time downloads: the picture and sound checkers (about 250 MB) the first time CleanView
looks for scenes, and Ollama plus its two AI models (about 11 GB) if the AI helper is on.

## Fixing and teaching it

- The review page has three tabs. **Found** lists every scene, line and word it will cut or
  mute, and lets you add a scene by typing a start and end time. **All dialogue** lists every
  line with a search box: click a line to mute it, or select several and cut them as a scene.
  **Ask Claude** is a chat about the episode (see below).
- CleanView remembers your choices per show (and in one file for movies) in
  %LOCALAPPDATA%\CleanView\learned. Lines you muted are muted again when they come back,
  lines you left alone start unticked, scene types and words you always keep start unticked,
  and your past choices are shown to the dialogue readers as examples.
- Claude's calls teach the AI on your PC the same way: lines Claude said to remove or that
  were fine become examples for it (your own choices always come first), and a word Claude
  said was fine in a phrase ("dinner at Hell's Kitchen") starts unticked when that phrase
  comes back. Every Claude finding is also kept in
  %LOCALAPPDATA%\CleanView\claude_findings.csv, which opens in Excel ("Claude's findings"
  button on the Ask Claude tab).
- "Send what CleanView learned…" on the start page saves everything it has learned into one
  file. Send that file in and it gets merged into shared_learned.json, which comes with every
  CleanView update, so every copy starts with it, including people without Claude or ChatGPT.
  Your own choices always win over the shared ones.

## Claude or ChatGPT (optional)

Everything works without them: the AI on your PC reads the dialogue, for free, and nothing
leaves your PC. If you have Claude or ChatGPT, it's more accurate.

Choose "Claude" under "Who reads the dialogue" and CleanView sets up Claude Code
(Anthropic's own program) and has you sign in with your Claude account once. It then uses
your Claude plan (Pro, Max, Team or Enterprise; usage counts toward the same limits as the
Claude app) with no API key. Choose "ChatGPT" and it sets up Codex (OpenAI's own program) the
same way, using your ChatGPT plan (Plus, Pro, Business...) with no API key. Everything below
works the same with either one.

With "Let Claude look at the picture too" (on by default), CleanView also sends still pictures:
one every 2 seconds, small, 20 to a sheet. Claude looks through the whole video, confirms or
rules out each scene the picture and sound checks found (with 6 sharper stills of each), and
adds scenes they missed. This is much better at scenes than the checks on your PC, and uses
more of your plan (roughly a long chat's worth per episode). Sound is never sent. Claude reads the episode's dialogue for the dialogue filters,
including flirting and romance across a whole conversation.

Claude then does a final review of the whole episode: it looks over everything the other
checks found (every scene, line and word) together with the full dialogue, your settings and
your past choices, and decides in context what really needs removing, what's a false alarm
(unticked, with the reason shown) and what was missed (added as "Found by Claude"). When a
line's only problem is one word ("one sweet-ass deal"), it mutes just that word and keeps the
rest of the line. Its
summary is shown at the top of the Found tab. On the Ask Claude tab, "Review everything
again" re-runs that review after you've made changes; anything you set yourself is never
undone. You can also chat about the episode and add what Claude suggests to the list. Only
the words that are said are sent, never the video or sound.

## Installing

Download CleanView-Setup.zip, extract it, and double-click "Install CleanView.bat". If
CleanListen is already installed, setup reuses copies of its speech model and video tools
to save downloading them again.

The installed app checks this repository for updates each time it opens.
