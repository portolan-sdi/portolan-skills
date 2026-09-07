#!/usr/bin/env bash
# Render one collection's thumbnail and run Gate 1.
# Usage: render_one.sh COLL_DIR BBOX [FORMAT] [SIZE] [QUALITY]
# Writes to the path the collection's thumbnail asset already points at.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
COLL_DIR="$1"          # collection directory
BBOX="$2"              # framed bbox from frame.py
FORMAT="${3:-}"        # default: the asset's current type
SIZE="${4:-1024}"
QUALITY="${5:-90}"
PORT="${PORT:-13579}"
WORK="${WORK:-/tmp/portolan-thumbs}"
USE_BASEMAP="${USE_BASEMAP:-true}"
BASEMAP_OPACITY="${BASEMAP_OPACITY:-0.55}"
# Do NOT write ${BASEMAP_URL:-https://.../{z}/{x}/{y}.png}. Bash ends the
# expansion at the first } and silently truncates the template to {z.
: "${BASEMAP_URL:=}"
[ -n "$BASEMAP_URL" ] || \
    BASEMAP_URL='https://basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png'
mkdir -p "$WORK"

# Portable size and hash: GNU stat/sha256sum on Linux, BSD stat/shasum on macOS.
fsize() { stat -c%s "$1" 2>/dev/null || stat -f%z "$1"; }
fhash() {
    if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1"
    else shasum -a 256 "$1"; fi | cut -d' ' -f1
}

META=$(python3 "$HERE/read_collection.py" "$COLL_DIR")
field() { printf '%s' "$META" | python3 -c "import json,sys; print(json.load(sys.stdin)['$1'])"; }
STYLE=$(field style)
PMTILES=$(field pmtiles)
OUT=$(field thumbnail)
[ -n "$FORMAT" ] || FORMAT=$(field thumbnail_type | sed 's#^image/##')

python3 "$HERE/buildstyle.py" "$STYLE" "$PMTILES" \
    "$USE_BASEMAP" "$BASEMAP_URL" "$BASEMAP_OPACITY" "$WORK"

render() {  # style-file bbox size outfile ext quality
    curl -s -X POST \
        "http://localhost:$PORT/clip.$5?bbox=$2&size=$3&quality=$6" \
        -H "Content-Type: application/json" \
        -d "{\"style\": $(cat "$1")}" \
        -o "$4" -w "%{http_code}"
}

MAIN=$(render "$WORK/render-style.json" "$BBOX" "$SIZE" "$OUT" "$FORMAT" "$QUALITY")
render "$WORK/probe-style.json" "$BBOX" 256 "$WORK/probe.png" png 100 > /dev/null
render "$WORK/blank-style.json" "$BBOX" 256 "$WORK/blank.png" png 100 > /dev/null

if [ "$MAIN" != "200" ]; then
    echo "FAIL http=$MAIN $(head -c 120 "$OUT")"
    rm -f "$OUT"
    exit 1
fi

PH=$(fhash "$WORK/probe.png"); BH=$(fhash "$WORK/blank.png")
PS=$(fsize "$WORK/probe.png"); BS=$(fsize "$WORK/blank.png")

if   [ "$PH" = "$BH" ];                     then GATE1="FAIL-empty"
elif [ "$PS" -lt $(( BS * 115 / 100 )) ];   then GATE1="WARN-sparse"
else                                             GATE1="PASS"; fi

echo "gate1=$GATE1 probe=$PS blank=$BS bytes=$(fsize "$OUT") out=$OUT"
