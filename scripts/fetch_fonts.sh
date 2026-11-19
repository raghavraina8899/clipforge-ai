#!/usr/bin/env bash
# Downloads free (SIL OFL) fonts from the google/fonts repository into backend/fonts. Optional: system fonts work without it.
set -u
mkdir -p "$(dirname "$0")/../backend/fonts" && cd "$(dirname "$0")/../backend/fonts"
base="https://raw.githubusercontent.com/google/fonts/main/ofl"
get() { [ -s "$2" ] && return 0; curl -fsSL --max-time 60 "$base/$1/$2" -o "$2.tmp" && mv "$2.tmp" "$2" && echo "  ok $2" || { rm -f "$2.tmp"; echo "  skipped $2 (download failed)"; }; }
get poppins Poppins-Regular.ttf; get poppins Poppins-Bold.ttf; get poppins Poppins-ExtraBold.ttf; get poppins Poppins-Black.ttf
get anton Anton-Regular.ttf; get bebasneue BebasNeue-Regular.ttf; get bangers Bangers-Regular.ttf
get archivoblack ArchivoBlack-Regular.ttf
