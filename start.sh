#!/usr/bin/env bash
# HookHunt - one command to set up (first run) and start everything:  ./start.sh
set -euo pipefail
cd "$(dirname "$0")"
say() { printf "\033[1;35m[hookhunt]\033[0m %s\n" "$*"; }
die() { printf "\033[1;31m[hookhunt] %s\033[0m\n" "$*" >&2; exit 1; }

# prefer a recent Python: current yt-dlp (YouTube downloads) needs 3.10+
PY=""
for c in python3.13 python3.12 python3.11 python3.10 python3; do command -v "$c" >/dev/null 2>&1 && { PY="$c"; break; }; done
[ -n "$PY" ] || die "Python 3.9+ is required (3.12 recommended: brew install python@3.12)."
command -v node >/dev/null && command -v npm >/dev/null || die "Node.js 18+ is required (https://nodejs.org)."
if ! command -v ffmpeg >/dev/null; then
  die "FFmpeg is missing. Install it with a build that includes libass (captions), e.g.:  brew install ffmpeg-full   (macOS)  |  sudo apt install ffmpeg  (Linux)"
fi
FILTERS=$(ffmpeg -hide_banner -filters 2>/dev/null || true)
grep -qE "[[:space:]]subtitles[[:space:]]" <<<"$FILTERS" || die "Your FFmpeg has no 'subtitles' filter (libass). On macOS: brew uninstall ffmpeg && brew install ffmpeg-full"

# macOS syncs Desktop/Documents to iCloud. Bulky generated folders get the ".nosync" suffix (iCloud skips them) behind a symlink.
nosync() {
  local p="$1"
  [ "$(uname)" = "Darwin" ] || return 0
  case "$PWD" in "$HOME/Desktop"*|"$HOME/Documents"*|*"/com~apple~CloudDocs"*) ;; *) return 0 ;; esac
  [ -L "$p" ] && return 0
  if [ -d "$p" ]; then mv "$p" "$p.nosync"; else mkdir -p "$p.nosync"; fi
  ln -s "$(basename "$p").nosync" "$p"
}

# ---- backend
want_minor=$("$PY" -c 'import sys;print(sys.version_info[1])')
if [ -x backend/.venv/bin/python ]; then
  have_minor=$(backend/.venv/bin/python -c 'import sys;print(sys.version_info[1])')
  if [ "$have_minor" -lt 10 ] && [ "$want_minor" -ge 10 ]; then say "Upgrading the Python environment to $($PY --version)…"; rm -rf backend/.venv backend/.venv.nosync; fi
fi
if [ ! -x backend/.venv/bin/python ]; then nosync backend/.venv; say "Creating Python environment ($($PY --version))…"; "$PY" -m venv backend/.venv; fi
REQ_HASH=$(cat backend/requirements.txt backend/constraints.txt | shasum | cut -d' ' -f1)
if [ ! -f backend/.venv/.req_hash ] || [ "$(cat backend/.venv/.req_hash)" != "$REQ_HASH" ]; then
  say "Installing backend dependencies (first run takes a few minutes)…"
  backend/.venv/bin/pip install -q --upgrade pip
  backend/.venv/bin/pip install -q -r backend/requirements.txt
  echo "$REQ_HASH" > backend/.venv/.req_hash
fi
if ! ls backend/fonts/*.ttf >/dev/null 2>&1; then say "Downloading free open-source caption fonts…"; ./scripts/fetch_fonts.sh || true; fi

# ---- frontend
cd frontend
[ -d node_modules ] || { nosync node_modules; say "Installing frontend dependencies…"; npm install --no-audit --no-fund --loglevel=error; }
if [ "${HOOKHUNT_DEV:-${CLIPFORGE_DEV:-0}}" = "1" ]; then FRONT="npm run dev"; else
  if [ ! -f .next.nosync/BUILD_ID ] || [ -n "$(find app components lib package.json tailwind.config.ts -newer .next.nosync/BUILD_ID -print -quit)" ]; then say "Building the interface…"; npm run build >/dev/null; fi
  FRONT="npm run start"
fi
cd ..

for port in 8000 3000; do lsof -ti tcp:$port -sTCP:LISTEN >/dev/null 2>&1 && die "Port $port is already in use. Stop the other program (or an earlier HookHunt) first."; done

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
