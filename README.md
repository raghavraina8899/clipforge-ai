# ClipForge AI

Free, local AI video clipper. Give it a video you own → it transcribes the speech, finds the most engaging moments,
and exports watermark-free vertical clips with word-timed animated captions, smart face framing and optional enhancements.
Everything runs on your computer: no subscription, no cloud, no paid API required.

## Run it

```bash
./start.sh
```

First run installs everything (Python venv, Node packages, free fonts) and builds the UI. Then open <http://localhost:3000>
(it opens automatically on macOS). `Ctrl+C` stops both servers.

**Prerequisites** (the script checks them and tells you what is missing):

| Need | macOS | Linux |
|---|---|---|
| Python 3.9+ | preinstalled / `brew install python` | `apt install python3 python3-venv` |
| Node.js 18+ | `brew install node` | nodejs.org |
| FFmpeg **with libass** (captions) | `brew install ffmpeg-full` (plain `ffmpeg` has no `subtitles` filter) | `apt install ffmpeg` |

The first transcription downloads the Whisper model once from Hugging Face (small ≈ 480 MB); after that it is offline.
Set `CLIPFORGE_DEV=1 ./start.sh` for development mode (hot reload).

## Workflow

1. **Create New Clips** → upload a video (drag & drop, real upload progress), paste a YouTube URL, or record an authorized live stream.
2. ClipForge probes the file, builds a 720p preview, extracts audio, transcribes (English / Hindi / auto) and scores moments. Every progress bar is measured from the real work.
3. Pick clips (or regenerate with another length: 15–30 / 30–45 / 45–60 / 60–90 / custom), tweak start/end, captions, layout, hook, enhancements.
4. **Render** → H.264/H.265 MP4 + SRT; download per clip or as one ZIP (clips, subtitles, thumbnails, social text).

## What is real, and what the limits are

* **YouTube URLs**: only public metadata (oEmbed) and public captions are read. ClipForge does **not** download YouTube videos or circumvent anything. With captions you get clip suggestions (word timing estimated); to render, attach the file you own (e.g. from YouTube Studio) and it is re-transcribed locally for exact timing.
* **Live streams**: direct stream addresses only (HLS `.m3u8`, RTMP, RTSP, SRT, UDP, plain http) and you must confirm authorization. Platform page URLs (YouTube, Twitch, …) are refused; no DRM/login bypass. Pause stops capture (the paused time is not recorded). Copy-mode recording waits for the stream's next keyframe (up to 20 s).
* **Viral score** = weighted estimate of hook, emotion, information, engagement, standalone context and ending (0–100). It is not a prediction.
* **Analysis**: the built-in analyzer is rule-based and works offline. Optional **Gemini** (your own key) or **Ollama** (local model) improve ranking and copy; their output is validated (timestamps snapped to real sentence boundaries, scores clamped, overlaps removed) and, on any failure or quota error, ClipForge falls back to the built-in analyzer and says so.
* **Gemini quotas**: Google's free tier is rate-limited, with limits that differ by model and can change; see ai.google.dev. The key is stored only in `data/settings.json` (chmod 600), sent only to Google in a header, never returned to the browser or written to logs.
* **Smart crop**: OpenCV Haar face detector + mouth-motion heuristic for the active speaker, smoothed with a dead-zone camera. Works best with front-facing faces; otherwise it falls back to center crop and reports that. (MediaPipe can be added behind `services/vision.py`; it is not required.)
* **Resolution honesty**: a 16:9 → 9:16 crop uses only ~1/3 of the source width. If an export needs upscaling, the result states the factor. 1440p/4K are reduced unless the source really has the pixels; 60 fps is not invented from 30 fps.
* **Emoji** in captions are composited as image overlays (libass cannot render colour emoji); this needs macOS' Apple Color Emoji font and is skipped with a notice elsewhere.
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
data/      SQLite DB, project folders (originals, proxy, transcript.json, exports/), logs, uploaded audio
```

The UI talks to the API at `http://127.0.0.1:8000` (CORS limited to localhost:3000). Large uploads are streamed straight to disk.
Logs: `data/logs/clipforge.log`. To add a caption preset edit `PRESETS` in `backend/app/services/captions.py`; to add an AI provider add a branch in `services/llm.py`.

## Troubleshooting

* *"FFmpeg has no subtitles filter"* → `brew uninstall ffmpeg && brew install ffmpeg-full`.
* *Port in use* → another ClipForge/dev server is running on 8000 or 3000.
* *Transcription fails on first run* → needs internet once to fetch the Whisper model.
* *Hindi captions look wrong* → use Whisper `small` or larger (AI Settings); fonts without Devanagari fall back to a system font.
