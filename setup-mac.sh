#!/usr/bin/env bash
# One-command setup for macOS: installs what is missing (via Homebrew), then starts ClipForge.
#   ./setup-mac.sh           install anything missing, then start the app
#   ./setup-mac.sh --check   only report what is missing
set -uo pipefail
cd "$(dirname "$0")"
say() { printf "\033[1;35m[setup]\033[0m %s\n" "$*"; }
die() { printf "\033[1;31m[setup] %s\033[0m\n" "$*" >&2; exit 1; }
CHECK=0; [ "${1:-}" = "--check" ] && CHECK=1

[ "$(uname)" = "Darwin" ] || die "This script is for macOS. On Linux see README.md (Quick start)."
if ! command -v brew >/dev/null 2>&1; then
  [ $CHECK = 1 ] && die "Homebrew is missing. Install it from https://brew.sh then run this again."
  say "Homebrew (the Mac package installer) is needed. Installing it - you may be asked for your Mac password."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" || die "Homebrew install failed."
  eval "$(/opt/homebrew/bin/brew shellenv 2>/dev/null || /usr/local/bin/brew shellenv)"
fi

missing=()
command -v python3.12 >/dev/null 2>&1 || command -v python3.13 >/dev/null 2>&1 || command -v python3.11 >/dev/null 2>&1 || command -v python3.10 >/dev/null 2>&1 || missing+=("python@3.12")
command -v node >/dev/null 2>&1 || missing+=("node")
need_ffmpeg_full=0
if ! command -v ffmpeg >/dev/null 2>&1; then need_ffmpeg_full=1
else
  FILTERS=$(ffmpeg -hide_banner -filters 2>/dev/null || true)
  grep -qE "[[:space:]]subtitles[[:space:]]" <<<"$FILTERS" || need_ffmpeg_full=1
fi

if [ ${#missing[@]} -eq 0 ] && [ $need_ffmpeg_full = 0 ]; then say "Everything needed is already installed."
elif [ $CHECK = 1 ]; then
  [ ${#missing[@]} -gt 0 ] && say "Missing: ${missing[*]}"; [ $need_ffmpeg_full = 1 ] && say "Missing: ffmpeg-full (FFmpeg with caption support)"
  exit 1
else
  [ ${#missing[@]} -gt 0 ] && { say "Installing: ${missing[*]}"; brew install "${missing[@]}" || die "brew install failed."; }
  if [ $need_ffmpeg_full = 1 ]; then
    if brew list --formula ffmpeg >/dev/null 2>&1; then
      say "Your FFmpeg has no caption support. Replacing it with ffmpeg-full (same tool, more features)."
      brew uninstall ffmpeg || die "Could not remove the old ffmpeg."
    fi
    say "Installing ffmpeg-full (large download, a few minutes)…"; brew install ffmpeg-full || die "ffmpeg-full install failed."
  fi
fi
[ $CHECK = 1 ] && { say "All good."; exit 0; }
say "Starting ClipForge. First run downloads Python packages, fonts and (when you first transcribe) the speech model."
exec ./start.sh
