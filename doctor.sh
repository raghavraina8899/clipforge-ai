#!/usr/bin/env bash
# Checks this computer for the usual reasons Frameflow does not work, and prints how to fix each.  ./doctor.sh
cd "$(dirname "$0")/backend" || exit 1
if [ -x .venv/bin/python ]; then exec .venv/bin/python -m app.doctor; fi
echo "The Python environment is not set up yet. Run ./start.sh (or ./setup-mac.sh on a Mac) first."
command -v ffmpeg >/dev/null && echo "ffmpeg: found" || echo "ffmpeg: MISSING (Mac: brew install ffmpeg-full)"
command -v node >/dev/null && echo "node: found" || echo "node: MISSING (Mac: brew install node)"
