# ClipForge AI — Project Status

_Last updated: 2026-11-20_

## What we are building
A free, local AI video clipper: video in → transcript → best moments → vertical clips with animated word-timed captions → watermark-free MP4 export. No paid services; Gemini is optional with the user's own key.

## Stack
Next.js 15 / React 19 / TypeScript / Tailwind (frontend) · FastAPI + SQLite (backend) · FFmpeg (needs libass: `brew install ffmpeg-full`) · faster-whisper · OpenCV · optional Gemini / Ollama.
Run: `./start.sh` → http://localhost:3000 (API on 127.0.0.1:8000).

## Achieved and tested (against real generated videos)
- Upload (streamed, real progress) → probe → 720p proxy → transcription (word timestamps) → clip suggestions with 6-part score
- Re-analysis with new length range; manual clips; start/end editing; word/timing correction
- Captions: 10 presets, full customization, ASS rendering (highlight/pop/reveal/fade/karaoke), hook + ending overlays, emoji overlays, SRT export
- Layouts: smart face-following crop, center, blur background, colour fill, split-screen; zoom effects
- Enhancements: brightness/contrast/saturation/sharpness, fades, loudness normalize, denoise, stabilize, user music/SFX
- Export: H.264/H.265, 720p–4K (capped honestly by source), fps cap, per-export notes, SRT, thumbnails (Pillow), social text, ZIP
- Live stream recording (start/pause/resume/stop) tested over UDP; page URLs (YouTube/Twitch…) refused
- YouTube URL: metadata + public captions only (tested with a real URL); no video download
- Gemini key handling (masked, chmod 600, header-only, not logged); AI output validation + fallback tested with simulated responses
- UI pages: Dashboard, Create, Projects, project workspace/editor, Library, Subtitle Styles, AI Settings, Video Settings, About — browser-tested with Playwright

## Added 2026-11-20: URL-only automatic clips
- YouTube tab has an ownership/permission checkbox. When ticked: moments are found from captions (or temporary audio download if none), and on render only that clip's time range is downloaded with yt-dlp, transcribed, rendered, then deleted (`services/ytdl.py`, `pipeline.render_job` segment mode).
- Tested: the segment → transcribe → render → delete logic, with the download step replaced by a local file cut. **Not tested: the real yt-dlp download from YouTube** (needs a video the owner may use; yt-dlp on Python 3.9 is pinned to an older release).
- Live preview in URL-only mode: opening a clip downloads a small 480p copy of just that segment (cached under `preview/`), re-transcribes it for exact caption timing, and shows it in the editor; it is deleted when the clip is exported. Tested with a fake download only.
- Known limits: no thumbnail frames for URL-only projects.

## Added 2026-11-20: facecam + content layout
- "Smart (auto)": if a small face overlay near an edge/corner is detected (streamer facecam), export stacks face on top and full gameplay/screen below (share slider, fit-with-blur or fill, optional blur of the facecam inside the lower content). Vlogs (large central face) keep the face-follow crop. Explicit options: "Facecam + content", "Face-follow crop".
- Tested on a synthetic gameplay+facecam video (export + browser preview). Not yet tried on the real GTA project.
- Backend now runs on Python 3.12 (needed for current yt-dlp); `av<17` pinned for faster-whisper.

## Not yet verified / known gaps
- Real YouTube segment/audio download end to end
- Gemini with a real key and Ollama with a real model (only simulated)
- Hindi transcription accuracy and Devanagari caption rendering on real Hindi audio
- Active-speaker switching on real speech (only static two-face test)
- Emoji overlay render on an exported clip; Hook/Ending and Social tabs not exercised in browser
- MediaPipe not integrated (OpenCV Haar only); no hardware (VideoToolbox) encode option
- Next steps: real-world test with a talking-head video, polish UI edge cases, optional MediaPipe, tests/CI

## Notes
- Servers are stopped after testing; start with `./start.sh`.
- Data lives in `data/` (git-ignored). Fonts are downloaded by `scripts/fetch_fonts.sh`.
