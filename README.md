# ClipForge AI

Free, local AI video clipper. Give it a video you own → it transcribes the speech, finds the most engaging moments,
and exports watermark-free vertical clips with word-timed animated captions, smart face framing and optional enhancements.
Everything runs on your computer: no subscription, no cloud, no paid API required.

## Quick start (copy and paste)

### Mac (easiest)
Open the **Terminal** app and run these three lines, one at a time:

```bash
git clone https://github.com/raghavraina8899/clipforge-ai.git
cd clipforge-ai
./setup-mac.sh
```

`setup-mac.sh` installs whatever is missing (Homebrew, Python, Node, FFmpeg), then starts the app and opens
**http://localhost:3000** in your browser. The first run takes several minutes (downloads). Nothing else to configure.

**Next time**, just open Terminal and run:

```bash
cd clipforge-ai
./start.sh
```

Leave that Terminal window open while you use the app. Press `Ctrl+C` in it to stop.

> No `git`? Run `xcode-select --install` once, or use the green **Code → Download ZIP** button on GitHub, unzip it, then `cd` into the folder.

### Linux (Ubuntu/Debian)
```bash
sudo apt update && sudo apt install -y git python3 python3-venv nodejs npm ffmpeg curl
git clone https://github.com/raghavraina8899/clipforge-ai.git
cd clipforge-ai
./start.sh
```
(Node 18+ and Python 3.10+ are needed; if `apt` gives older versions use nodejs.org / `deadsnakes`.)

### Windows
Not supported directly. Install **WSL** (Ubuntu) and follow the Linux steps inside it, then open http://localhost:3000 in your Windows browser.

### What to expect
* Everything runs on your computer. No account, no API key, no subscription.
* The first time you process a video, a speech model (~480 MB) downloads once; after that it works offline (except YouTube-URL mode).
* Your videos and projects stay on your computer, outside the app folder: `~/Library/Application Support/ClipForge` on a Mac (`~/.local/share/clipforge` on Linux), so iCloud/Dropbox never uploads them. Set `CLIPFORGE_DATA=/some/folder` to change it.
* If something fails the app shows the reason; see Troubleshooting below. Logs: `<data folder>/logs/clipforge.log`.

## Run it (details)

`./start.sh` checks prerequisites, installs Python/Node packages and fonts on first run, builds the interface and starts both servers.

**Prerequisites** (`setup-mac.sh` handles these on a Mac):

| Need | macOS | Linux |
|---|---|---|
| Python 3.10+ (3.12 recommended) | `brew install python@3.12` | `apt install python3 python3-venv` |
| Node.js 18+ | `brew install node` | nodejs.org |
| FFmpeg **with libass** (captions) | `brew install ffmpeg-full` (plain `ffmpeg` has no `subtitles` filter) | `apt install ffmpeg` |

Set `CLIPFORGE_DEV=1 ./start.sh` for development mode (hot reload).

## Workflow

1. **Create New Clips** → upload a video (drag & drop, real upload progress), paste a YouTube URL, or record an authorized live stream.
2. ClipForge probes the file, builds a 720p preview, extracts audio, transcribes (English / Hindi / auto) and scores moments. Every progress bar is measured from the real work.
3. Pick clips (or regenerate with another length: 15–30 / 30–45 / 45–60 / 60–90 / custom), tweak start/end, captions, layout, hook, enhancements.
4. **Render** → H.264/H.265 MP4 + SRT; download per clip or as one ZIP (clips, subtitles, thumbnails, social text).

## What is real, and what the limits are

* **YouTube URLs**: by default only public metadata and captions are read (text suggestions). If you tick "I own this video or have permission to use it", ClipForge works from the URL alone. Recommended: **download the full video once** (one request), then everything runs locally on the real file (previews, thumbnails, fast exports). The download is deleted automatically once all selected clips are exported (or use "Delete downloaded video"); exports are kept. The alternative "fetch each clip separately" uses less disk but makes many requests (more likely to hit YouTube's bot check). Public videos only (no cookies/logins/DRM bypass). Downloading videos you don't own may break YouTube's terms. yt-dlp can break when YouTube changes: `backend/.venv/bin/pip install -U 'yt-dlp[default]'`.
* **Series mode** (Create page → "Series of parts"): cuts the whole video, or a start/stop range, into consecutive parts of your chosen length (Part 1/N, Part 2/N…), each ending at a sentence break, with a "Part N" label shown at the start. It does not pick cliffhangers; adjust any part's end time in its editor.
* **Live streams**: direct stream addresses only (HLS `.m3u8`, RTMP, RTSP, SRT, UDP, plain http) and you must confirm authorization. Platform page URLs (YouTube, Twitch, …) are refused; no DRM/login bypass. Pause stops capture (the paused time is not recorded). Copy-mode recording waits for the stream's next keyframe (up to 20 s).
* **Viral score** = weighted estimate of hook, emotion, information, engagement, standalone context and ending (0–100). It is not a prediction.
* **Analysis**: the built-in analyzer is rule-based and works offline. Optional **Gemini** (your own key) or **Ollama** (local model) improve ranking and copy; their output is validated (timestamps snapped to real sentence boundaries, scores clamped, overlaps removed) and, on any failure or quota error, ClipForge falls back to the built-in analyzer and says so.
* **Gemini quotas**: Google's free tier is rate-limited, with limits that differ by model and can change; see ai.google.dev. The key is stored only in `settings.json` in the data folder (chmod 600), sent only to Google in a header, never returned to the browser or written to logs.
* **Smart crop**: OpenCV Haar face detector + mouth-motion heuristic for the active speaker, smoothed with a dead-zone camera. Works best with front-facing faces; otherwise it falls back to center crop and reports that. (MediaPipe can be added behind `services/vision.py`; it is not required.)
* **Resolution honesty**: a 16:9 → 9:16 crop uses only ~1/3 of the source width. If an export needs upscaling, the result states the factor. 1440p/4K are reduced unless the source really has the pixels; 60 fps is not invented from 30 fps.
* **Emoji** in captions are composited as image overlays (libass cannot render colour emoji); this needs macOS' Apple Color Emoji font and is skipped with a notice elsewhere.
* **Hindi / Hinglish**: the *Spoken language* option tells Whisper what to listen for. *Hindi* gives Devanagari captions; *Hinglish* gives Hindi in English letters (a Hinglish prompt plus a built-in romanizer, so output is natural but can differ from how you'd spell it; fix words in the Captions tab). Projects already transcribed in Devanagari have a one-click convert button.
* **Music / SFX** are never added automatically; only files you upload.
* Only process content you own or are permitted to use.

## Architecture

```
frontend/  Next.js 15 + React 19 + TypeScript + Tailwind, shadcn-style UI primitives, lucide icons
backend/   FastAPI (Python)
  app/routers/api.py      REST API (projects, clips, settings, jobs, downloads)
  app/jobs.py             background job runner (thread pool, persisted real progress, cancel)
  app/pipeline.py         ingest → proxy → transcribe → analyze → clips; render job; thumbnails
  app/services/           ffmpeg · transcribe (faster-whisper) · analyze · llm (Gemini/Ollama) ·
                          captions (ASS/SRT + presets) · vision (OpenCV) · render (filter graph) · social · sources (YouTube/live)
(data folder)  SQLite DB, project folders (originals, proxy, transcript.json, exports/), logs, uploaded audio
```

The UI talks to the API at `http://127.0.0.1:8000` (CORS limited to localhost:3000). Large uploads are streamed straight to disk.
Logs: `<data folder>/logs/clipforge.log`. To add a caption preset edit `PRESETS` in `backend/app/services/captions.py`; to add an AI provider add a branch in `services/llm.py`.

## Troubleshooting

**First, run the system check.** In the app: *About → Run system check* (it lists what is wrong and how to fix it, and has a *Copy diagnostic report* button to send to whoever helps you). If the app will not even start: `./doctor.sh` in the project folder.

* *"FFmpeg has no subtitles filter"* → `brew uninstall ffmpeg && brew install ffmpeg-full`.
* *Port in use* → another ClipForge/dev server is running on 8000 or 3000. Close the other Terminal window running it, or restart your Mac.
* *"permission denied" running a script* → run `chmod +x setup-mac.sh start.sh scripts/fetch_fonts.sh` once.
* *Page says it cannot connect* → the Terminal running `./start.sh` was closed; start it again.
* *Transcription fails on first run* → needs internet once to fetch the Whisper model.
* *Hindi captions look wrong* → use Whisper `small` or larger (AI Settings); fonts without Devanagari fall back to a system font.
