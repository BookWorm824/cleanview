# CleanView

Cleans up movies and TV episodes you own, on Windows. Everything runs on your own computer;
nothing is uploaded. CleanView is a separate app from CleanListen (the audiobook cleaner):
its own install, its own folder, its own updates.

- Mutes the same language list, listening to the dialogue channel of surround-sound movies,
  and uses the movie's subtitles (a matching .srt or a text track inside the file) to catch
  extra words. Writes cleaned subtitles into the clean copy.
- Filters you can switch on or off: sexual references, nudity, sex scenes, immodest clothing,
  sleeping around, man & woman kissing and same-sex kissing (keep / cut passionate / cut all),
  same-sex relationships, unmarried couples living or sleeping together, crude humor, bullying,
  violence, graphic gore, smoking, drinking and drug use. Your choices are remembered.
- How it finds things:
  - NudeNet checks the picture twice a second for nudity.
  - CLIP (OpenAI's free image model) checks it once a second for kissing, couples in bed,
    gore, fights, weapons, smoking, drinking, drugs and revealing clothes, so scenes are
    caught even when they're silent.
  - A sound model listens for gunfire, explosions, screaming and blows.
  - The optional AI helper runs two models through Ollama on your PC: qwen2.5vl:7b double-checks
    each scene the picture model found (it must describe what it sees, and says no when the
    frames are too dark or unclear), and qwen2.5:7b reads the dialogue for sexual references, sleeping around,
    relationship talk, crude humor and bullying. A line is only flagged when the model quotes
    the words that fit and a second, stricter question about that line agrees.
- Dark or murky frames are ignored, and a scene needs several seconds of strong hits. Scenes
  the AI helper didn't confirm are listed unticked.
- Scenes are cut; flagged dialogue lines and swear words are muted. Everything is listed
  first (scenes with blurred stills and a Preview button, then lines, then every swear word),
  and only what you leave ticked is changed.
- Pick a folder of episodes to clean a whole season in one go.
- Saves "(Clean)" copies plus a report of every mute and cut. Originals are never changed.
  Uses an NVIDIA, Intel or AMD graphics card to save faster when one is available.

Works with DRM-free video (DVD and Blu-ray rips, home videos). Copy-protected purchases
from iTunes, Vudu, Movies Anywhere and streaming services can't be used. 4K HDR files come
out with flatter colours after a cut. The AI checks are good but not perfect, which is why
everything is shown to you before it's cut.

One-time downloads: the picture and sound checkers (about 250 MB) the first time CleanView
looks for scenes, and Ollama plus its two AI models (about 11 GB) if the AI helper is on.

## Installing

Download CleanView-Setup.zip, extract it, and double-click "Install CleanView.bat". If
CleanListen is already installed, setup reuses copies of its speech model and video tools
to save downloading them again.

The installed app checks this repository for updates each time it opens.
