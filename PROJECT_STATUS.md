# HookHunt — Project Status

_Last updated: 2026-11-20_

## What it is
A free, local AI video clipper. Give it a video you own (upload, YouTube link, or an authorized live stream) and it transcribes the speech, finds the best moments (or cuts the whole story into Part 1, Part 2…), and exports watermark-free vertical clips with word-timed animated captions. Everything runs on the user's computer; no paid service is required (Gemini / Ollama are optional).

## Stack and layout
- **Frontend:** Next.js 15, React 19, TypeScript, Tailwind (own shadcn-style components).
- **Backend:** FastAPI + SQLite, FFmpeg (needs libass), faster-whisper / MLX Whisper, OpenCV, yt-dlp, Pillow.
- **Run:** `./start.sh` (Mac first-time setup: `./setup-mac.sh`). UI http://localhost:3000, API http://127.0.0.1:8000. Python 3.10+ (3.12 recommended).
- **Data** lives outside the repo: `~/Library/Application Support/HookHunt` (Linux `~/.local/share/hookhunt`), override with `HOOKHUNT_DATA`. venv, node_modules and the build use `.nosync` folders so iCloud does not sync them.
- `backend/app/`: `routers/api.py` (REST), `jobs.py` (scheduler), `pipeline.py` (import → transcribe → analyze → clips, render jobs), `storage.py`, `doctor.py`, `services/` (ffmpeg, transcribe, engine, analyze, captions, render, vision, tighten, brand, waveform, hinglish, social, sources, ytdl, llm, settings_store).
- `backend/tests/` (tests), `backend/constraints.txt` (library version limits), `.github/workflows/tests.yml` (CI), `scripts/` (fonts), `doctor.sh`, `setup-mac.sh`.

## Features (all built; how each was verified)
| Area | What exists | Verification |
|---|---|---|
| Input | Upload (streamed, real progress), YouTube link, authorized live stream (start/pause/resume/stop) | Upload, live (UDP) and link parsing in tests/manual; real YouTube partly (see gaps) |
| YouTube | Metadata + public captions by default. With an ownership tick: full video downloaded once (or per-clip segments), auto-deleted after export; time range read from `?t=` / `start=` / `end=` | Logic + stand-in downloads tested; segment previews/exports verified by the user on real videos |
| Analysis | Built-in rule-based moment finder with 6-part score; optional Gemini / Ollama (validated, falls back); Series mode (Part i/N, optional range) | Unit tests + simulated AI answers |
| Transcription | Auto-picked engine: Apple GPU (MLX) ≈ 24–27× real time on an M4, NVIDIA CUDA, else batched CPU ≈ 12–15×; VAD skips silence; English, Hindi, Hinglish (Hindi in English letters) | Measured on this Mac; CUDA path untested |
| Captions | 10 presets + full customization, word highlight/pop/reveal/fade/karaoke, hook + ending, emoji overlays (macOS), show/hide, hide-by-time-range, SRT | Real renders in tests |
| Framing | Smart face crop, center, blur, fill, split-screen, streamer facecam + content (overlay detected and cropped out), zoom | Synthetic videos + user check on real stream |
| Enhance | Colour, sharpness, fades, loudness, denoise, stabilize, user music/SFX | Real renders |
| Tighten | Optional pause + filler-word cutting (frame-exact, sound/picture in sync, captions/SRT follow, preview skips cuts); off by default | End to end with real transcription |
| Brand kit | Per-channel logo, intro/outro (video or image), caption style, default kit | Real renders (durations, sync, logo present/absent) |
| Export | H.264/H.265, honest resolution/fps limits with notes, thumbnails, social text, one-folder ZIP bundle + optional cleanup after download | Real renders + API tests |
| Management | Projects, clip library, Storage page (per-item sizes, select/delete), cancel everywhere, retry, System check (`./doctor.sh` + step-by-step UI + copyable report) | Tests + browser checks |
| UI | Dark glass design, 3D tilt cards, splash + page loaders, animated cube/film-to-MP4 export loader, consistent full-width layouts | Browser checks |

## Quality gates
- `cd backend && .venv/bin/python -m pytest -m "not slow"` → **75 tests**, ~25 s (logic, scheduler, API, storage safety, real FFmpeg renders). `-m slow` → real upload + transcription (1 test).
- GitHub Actions runs the fast tests on Linux and macOS plus a type check and build of the frontend on every push; the last run was green.
- Working rules for this repo: no AI/Claude attribution in commits or files; check `jobs` (no queued/running) before restarting the app; run the tests before pushing.

## Groundwork present but not finished
- **Timeline editor:** the API side exists (`tighten.manual` = manual cut ranges that the renderer and `/clips/{id}/tighten-plan` honour; `GET /api/clips/{id}/waveform` returns audio peaks). **There is no timeline user interface yet.**

## Known gaps / not verified
- Real YouTube downloads depend on YouTube accepting the network: home connections get "confirm you're not a bot" blocks (a phone hotspot worked). Full-video and audio-only modes were not run against real YouTube after the last fixes. yt-dlp must be kept current (`pip install -U 'yt-dlp[default]'`).
- Gemini and Ollama were never tried with a real key / model (only simulated answers).
- NVIDIA/CUDA transcription is written but untested (no NVIDIA machine).
- Windows is not supported yet (bash scripts, symlinks, Mac-only emoji font). Plan: cross-platform Python launcher + GitHub Windows runner. Linux is covered by CI for tests only.
- Hindi/Hinglish accuracy checked only with a synthetic voice; active-speaker switching only with a static two-face test.
- Emoji captions need macOS' Apple Color Emoji font.
- Speech models often omit "um"/"uh", so filler-word cutting only catches fillers that were transcribed (pause cutting always works).

## Backlog (ideas, not started)
Timeline editor UI · join clips into a compilation · auto-zoom on emphasis · translated captions · jobs page · desktop notifications · better face detector (MediaPipe-class) · desktop installer · Windows support · browser-login option for YouTube downloads (opt-in, account risk) · uploading straight to YouTube/Instagram (not advised).

## History (2026-11-20, one long build session)
Built the full app (upload → transcription → clips → captions → export) → YouTube URL mode with temporary downloads → facecam layout → series mode → Hinglish → caption hide/range → bundle download + cleanup → storage manager → HookHunt rename and redesign → system check → cancel/scheduler fixes → faster transcription (auto engine) → tests + locked versions + CI → tighten → brand kit → waveform/manual-cut groundwork. Decisions and measurements are in the commit messages.
