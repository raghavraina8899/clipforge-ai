#!/usr/bin/env bash
# ClipForge AI - one command to set up (first run) and start everything:  ./start.sh
set -euo pipefail
cd "$(dirname "$0")"
say() { printf "\033[1;35m[clipforge]\033[0m %s\n" "$*"; }
die() { printf "\033[1;31m[clipforge] %s\033[0m\n" "$*" >&2; exit 1; }

command -v python3 >/dev/null || die "Python 3.9+ is required."
command -v node >/dev/null && command -v npm >/dev/null || die "Node.js 18+ is required (https://nodejs.org)."
if ! command -v ffmpeg >/dev/null; then
  die "FFmpeg is missing. Install it with a build that includes libass (captions), e.g.:  brew install ffmpeg-full   (macOS)  |  sudo apt install ffmpeg  (Linux)"
fi
FILTERS=$(ffmpeg -hide_banner -filters 2>/dev/null || true)
grep -qE "[[:space:]]subtitles[[:space:]]" <<<"$FILTERS" || die "Your FFmpeg has no 'subtitles' filter (libass). On macOS: brew uninstall ffmpeg && brew install ffmpeg-full"

# ---- backend
if [ ! -x backend/.venv/bin/python ]; then say "Creating Python environment…"; python3 -m venv backend/.venv; fi
REQ_HASH=$(shasum backend/requirements.txt | cut -d' ' -f1)
if [ ! -f backend/.venv/.req_hash ] || [ "$(cat backend/.venv/.req_hash)" != "$REQ_HASH" ]; then
  say "Installing backend dependencies (first run takes a few minutes)…"
  backend/.venv/bin/pip install -q --upgrade pip
  backend/.venv/bin/pip install -q -r backend/requirements.txt
  echo "$REQ_HASH" > backend/.venv/.req_hash
fi
if ! ls backend/fonts/*.ttf >/dev/null 2>&1; then say "Downloading free open-source caption fonts…"; ./scripts/fetch_fonts.sh || true; fi

# ---- frontend
cd frontend
[ -d node_modules ] || { say "Installing frontend dependencies…"; npm install --no-audit --no-fund --loglevel=error; }
if [ "${CLIPFORGE_DEV:-0}" = "1" ]; then FRONT="npm run dev"; else
  if [ ! -f .next/BUILD_ID ] || [ -n "$(find app components lib package.json tailwind.config.ts -newer .next/BUILD_ID -print -quit)" ]; then say "Building the interface…"; npm run build >/dev/null; fi
  FRONT="npm run start"
fi
cd ..

for port in 8000 3000; do lsof -ti tcp:$port >/dev/null 2>&1 && die "Port $port is already in use. Stop the other program (or an earlier ClipForge) first."; done

pids=()
cleanup() { say "Stopping…"; for p in "${pids[@]}"; do kill "$p" 2>/dev/null || true; done; wait 2>/dev/null || true; }
trap cleanup EXIT INT TERM

say "Starting backend on http://127.0.0.1:8000"
(cd backend && exec .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --log-level warning) & pids+=($!)
say "Starting interface on http://localhost:3000"
(cd frontend && exec $FRONT) >/dev/null 2>&1 & pids+=($!)

for _ in $(seq 1 60); do curl -fs http://127.0.0.1:8000/api/system >/dev/null 2>&1 && break; sleep 1; done
say "Ready →  http://localhost:3000   (Ctrl+C to stop)"
command -v open >/dev/null && open http://localhost:3000 || true
wait
