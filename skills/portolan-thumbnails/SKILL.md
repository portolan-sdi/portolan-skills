---
name: portolan-thumbnails
description: Generate framed, checked thumbnails from Portolan collections using chiitiler (MapLibre GL Native). Renders the collection's actual styles/default.json server-side with an optional basemap, frames every bbox to the browser card's 3:2 shape, and gates each image on an automated blank probe plus a visual review. Requires Node.js 18+.
---

<!-- freshness: last-verified: 2026-08-12, maps-to: github.com/Kanahiro/chiitiler
     Card geometry from portolan-browser/src/theme/page.scss (350-700 px wide,
     250 px tall, object-fit: scale-down). -->

# Framed Thumbnails with Chiitiler

Render a collection's own `styles/default.json` server-side with
[chiitiler](https://github.com/Kanahiro/chiitiler), frame it to the shape of the
browser card, and check the result before it ships. The rendering half of this is
the easy half. Most bad thumbnails come from the bbox, not the renderer.

**When to use**: any collection whose thumbnail people will actually look at. The
matplotlib thumbnails that `portolan check --fix` writes stay the baseline; this
replaces them with something that matches the portal.

## Requirements

- Node.js 18+ and npm
- Git, to clone chiitiler
- A collection with a `.pmtiles` file and `styles/default.json`
- An agent that can view images. Step 5 is not optional and cannot be automated away.
- DuckDB, optional. Needed only to find a dense subregion in a large collection.

## Why Framing Is the Whole Job

chiitiler's `/clip` endpoint takes four parameters: `url` (or a posted style),
`bbox`, `size`, and `quality`. The output aspect ratio and the zoom both fall out
of the bbox, and `size` sets the longest edge. Every framing decision is therefore
a decision about which bbox to send.

Passing the collection's raw extent produces the failures the St. Louis catalog hit
in August 2026: tall narrow rectangles floating in wide cards, dense parcel layers
rendered so far out that tippecanoe's thinning shows as holes, and six cards in a
row that could be swapped without anyone noticing.

Rewriting the bbox is reframing, not distortion. Nothing gets stretched. The
`conversion-defaults` best practice forbids changing the aspect of the data, which
this does not do; it changes how much context sits around the data.

## Step 1 — Read the Collection

Every signal you need is in `collection.json` and the PMTiles header.

| Signal | Where | Tells you |
|---|---|---|
| `geoparquet:geometry_type` | collection.json | Points and lines need more zoom than polygons |
| `geoparquet:feature_count` | collection.json | The single strongest strategy signal |
| `extent.spatial.bbox[0]` | collection.json | The starting frame |
| thumbnail-role asset `href` | collection.json | Where to write, and in which format |
| `pmtiles:max_zoom` | collection.json, when present | The deepest zoom with complete data |
| `pmtiles:center` | collection.json, when present | tippecanoe's densest-area guess |
| `pmtiles:layers` | collection.json, when present | Ground truth for `source-layer` |

The `pmtiles:*` properties come from newer conversions and are missing from older
catalogs; only 63 of 188 collections in the pergamino-ide test catalog carry them.
Read the PMTiles header instead, which always works.

```bash
python3 /tmp/portolan-thumbs/frame.py \
    --pmtiles publico_arbolado/publico_arbolado.pmtiles
# {"min_zoom": 0, "max_zoom": 13, "center": [-60.578613, -33.888655, 13],
#  "bounds": [-60.638266, -33.923181, -60.512274, -33.860783]}
```

Treat `center` as a hint. tippecanoe sometimes writes the bbox corner rather than a
dense cluster, as it did for two of the six collections checked in August 2026.
Confirm it with a feature count before you build a window around it.

## Step 2 — Choose a Strategy

**A, full extent.** Frame the collection's whole bbox. Right for boundaries,
borders, districts, wards, precincts, neighborhoods, watersheds, city limits, and
anything with a small feature count.

**B, zoomed window.** A 3:2 window at a chosen zoom, centred on a dense cluster.
Right for parcels, buildings, blocks, addresses, service requests, permits, sales,
and trees.

Work through the signals cheapest first. These are defaults, not rules, and you
should override them when the data says otherwise.

| Signal | Default |
|---|---|
| Polygons, `feature_count` <= 50 | A |
| Name matches boundary, border, limit, district, ward, precinct, neighborhood, zone, tract, block group, county, city, watershed, region, and geometry is polygons | A |
| Any geometry, `feature_count` >= 5000 | B |
| Points or lines, `feature_count` >= 1000 | B |
| Anything else | A when `fill` >= 0.4, otherwise B |
| `aspect` outside 2.2:1 after capping | Decide explicitly and record why |

`fill` and `aspect` come from Step 3, so the last two rows mean running `frame.py`
first and then reconsidering.

## Step 3 — Compute the Bbox

Write the helper once per session. Run `mkdir -p /tmp/portolan-thumbs` and save the
following as `/tmp/portolan-thumbs/frame.py`.

```python
#!/usr/bin/env python3
"""Frame a bbox for thumbnail rendering. Prints JSON."""
import argparse, json, math, struct, sys

R = 6378137.0
EARTH_CIRC = 40075016.686
TARGET_ASPECT, MARGIN, MAX_CONTEXT, FRAME_ASPECT_LIMIT = 1.5, 0.05, 2.5, 2.2

def mx(lon): return math.radians(lon) * R
def inv_mx(x): return math.degrees(x / R)
def inv_my(y): return math.degrees(2 * math.atan(math.exp(y / R)) - math.pi / 2)

def my(lat):
    lat = max(min(lat, 85.05112878), -85.05112878)
    return R * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))

def eff_zoom(span_m, size_px): return math.log2(EARTH_CIRC * size_px / (256 * span_m))
def span_for_zoom(z, size_px): return EARTH_CIRC * size_px / (256 * 2 ** z)

def clamp(lo, hi, axis, warnings):
    """Keep the frame inside the Mercator world by shifting, never squashing."""
    half = EARTH_CIRC / 2
    if hi - lo > EARTH_CIRC:
        warnings.append("clamped-%s: frame larger than the world" % axis)
        return -half, half
    shift = (half - hi) if hi > half else ((-half - lo) if lo < -half else 0.0)
    if shift:
        warnings.append("shifted-%s: frame hit the world edge" % axis)
    return lo + shift, hi + shift

def frame(bbox, target=TARGET_ASPECT, margin=MARGIN, max_context=MAX_CONTEXT):
    w, s, e, n = bbox
    warnings = []
    x0, x1, y0, y1 = mx(w), mx(e), my(s), my(n)
    # Degenerate axis (a single point, or a line): floor the span at 1 km.
    for axis, (lo, hi) in (("x", (x0, x1)), ("y", (y0, y1))):
        if hi - lo >= 1.0:
            continue
        c = (lo + hi) / 2
        if axis == "x":
            x0, x1 = c - 500, c + 500
        else:
            y0, y1 = c - 500, c + 500
        warnings.append("degenerate-%s: span floored at 1 km" % axis)
    # Margin first: fractional per axis, so the aspect is unchanged.
    dx, dy = (x1 - x0) * margin, (y1 - y0) * margin
    x0, x1, y0, y1 = x0 - dx, x1 + dx, y0 - dy, y1 + dy
    dataW = W = x1 - x0
    dataH = H = y1 - y0
    if W / H < target:      # too tall, widen
        pad = (min(H * target, dataW * max_context) - W) / 2
        if pad > 0:
            x0, x1 = x0 - pad, x1 + pad
    elif W / H > target:    # too wide, heighten
        pad = (min(W / target, dataH * max_context) - H) / 2
        if pad > 0:
            y0, y1 = y0 - pad, y1 + pad
    x0, x1 = clamp(x0, x1, "x", warnings)
    y0, y1 = clamp(y0, y1, "y", warnings)
    fill = min(dataW / (x1 - x0), dataH / (y1 - y0))
    return (inv_mx(x0), inv_my(y0), inv_mx(x1), inv_my(y1)), fill, warnings

def window(clon, clat, z, size_px, target=TARGET_ASPECT):
    """Strategy B: a target-aspect window at zoom z, centred on (clon, clat)."""
    span = span_for_zoom(z, size_px)
    hw, hh = span / 2, span / (2 * target)
    cx, cy = mx(clon), my(clat)
    return inv_mx(cx - hw), inv_my(cy - hh), inv_mx(cx + hw), inv_my(cy + hh)

def report(bbox, size_px, warnings):
    x0, x1, y0, y1 = mx(bbox[0]), mx(bbox[2]), my(bbox[1]), my(bbox[3])
    aspect = (x1 - x0) / (y1 - y0)
    span = max(x1 - x0, y1 - y0)
    if not 1 / FRAME_ASPECT_LIMIT <= aspect <= FRAME_ASPECT_LIMIT:
        warnings.append("aspect %.2f is outside %.1f:1 after capping — "
                        "full-extent framing failed, decide explicitly"
                        % (aspect, FRAME_ASPECT_LIMIT))
    return {"bbox": ",".join("%.6f" % v for v in bbox), "aspect": round(aspect, 3),
            "zoom": round(eff_zoom(span, size_px), 2), "span_m": round(span, 1),
            "warnings": warnings}

def pmtiles_header(path):
    """Zoom range and centre straight from the PMTiles v3 header."""
    h = open(path, "rb").read(127)
    if h[:7] != b"PMTiles":
        raise SystemExit("%s is not a PMTiles archive" % path)
    bounds = [round(v / 1e7, 6) for v in struct.unpack("<iiii", h[102:118])]
    clon, clat = (round(v / 1e7, 6) for v in struct.unpack("<ii", h[119:127]))
    return {"min_zoom": h[100], "max_zoom": h[101],
            "center": [clon, clat, h[118]], "bounds": bounds}

def glue_negatives(argv):
    """Let --bbox -90,38,... work; argparse would read it as an option."""
    out, i = [], 0
    while i < len(argv):
        if argv[i] in ("--bbox", "--center") and i + 1 < len(argv):
            out.append("%s=%s" % (argv[i], argv[i + 1])); i += 2
        else:
            out.append(argv[i]); i += 1
    return out

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--bbox", help="w,s,e,n in degrees (full-extent framing)")
    p.add_argument("--center", help="lon,lat for a zoomed window")
    p.add_argument("--zoom", type=float, help="zoom for --center windows")
    p.add_argument("--target", type=float, default=TARGET_ASPECT)
    p.add_argument("--margin", type=float, default=MARGIN)
    p.add_argument("--max-context", type=float, default=MAX_CONTEXT)
    p.add_argument("--size", type=int, default=1024)
    p.add_argument("--pmtiles", help="report zoom range and centre, then exit")
    a = p.parse_args(glue_negatives(sys.argv[1:]))

    if a.pmtiles:
        print(json.dumps(pmtiles_header(a.pmtiles))); return
    if a.center:
        if a.zoom is None:
            p.error("--center needs --zoom")
        clon, clat = (float(v) for v in a.center.split(","))
        out = report(window(clon, clat, a.zoom, a.size, a.target), a.size, [])
        out["fill"], out["strategy"] = None, "B"
    else:
        if not a.bbox:
            p.error("pass --bbox, or --center with --zoom")
        bbox, fill, warnings = frame([float(v) for v in a.bbox.split(",")],
                                     a.target, a.margin, a.max_context)
        out = report(bbox, a.size, warnings)
        out["fill"], out["strategy"] = round(fill, 3), "A"
    print(json.dumps(out))

if __name__ == "__main__":
    main()
```

### Constants

| Knob | Default | Why |
|---|---|---|
| `TARGET_ASPECT` | 1.5 | The card is 350-700 px wide and 250 px tall. Exact fill at the narrowest column is 1.4; 3:2 renders 350x233. |
| `MARGIN` | 0.05 | Matches `portolan_cli/viz/thumbnail.py::_frame_bounds`. Fractional per axis, so it adds breathing room without changing the aspect. |
| `MAX_CONTEXT` | 2.5 | The short axis grows to at most 2.5x the data span, keeping data at 40% of the frame or more. |
| `FRAME_ASPECT_LIMIT` | 2.2 | A capped frame still worse than 2.2:1 means full-extent framing failed. |
| `SIZE` | 1024 | Twice the widest realistic card. |
| `BASEMAP_OPACITY` | 0.55 | Holds the basemap back so data reads as the subject. |

### Strategy A

```bash
BBOX=$(python3 -c "
import json
print(','.join(str(v) for v in
    json.load(open('collection.json'))['extent']['spatial']['bbox'][0]))")
python3 /tmp/portolan-thumbs/frame.py --bbox "$BBOX" --size 1024
# {"bbox": "-60.651220,-33.935211,-60.495382,-33.848971", "aspect": 1.5,
#  "zoom": 13.17, "span_m": 17347.9, "warnings": [], "fill": 0.957}
```

Read `fill` and `aspect` before you render. A `fill` near 1 means the data nearly
fills the frame. A `fill` of exactly 0.4 means `MAX_CONTEXT` capped the growth and
the frame never reached 3:2. When the aspect warning fires you have two moves:
force the target and accept the extra context with `--max-context 99`, or switch to
Strategy B. Record which you chose. On the library collection below, forcing 3:2
dropped `fill` from 0.4 to 0.216.

```bash
python3 /tmp/portolan-thumbs/frame.py \
    --bbox -60.83747839,-33.91583683,-60.54717032,-33.88110625 \
    --max-context 99 --size 1024
```

### Strategy B

Pick a zoom, pick a centre, and let `--center` build the window.

```bash
python3 /tmp/portolan-thumbs/frame.py --center -60.581959,-33.893888 \
    --zoom 15 --size 1024
# {"bbox": "-60.603932,-33.906046,-60.559986,-33.881728", "aspect": 1.5,
#  "zoom": 15.0, ... "strategy": "B"}
```

Zoom governs how much ground the window covers. At `SIZE=1024` the longest framed
edge runs 78.3 km at zoom 11, 39.1 at 12, 19.6 at 13, 9.8 at 14, 4.9 at 15, 2.4 at
16, and 1.2 at 17.

Start from the collection's PMTiles `max_zoom` and from the full-extent zoom that
Strategy A reported. Going below `max_zoom` risks tippecanoe's thinning, and going
no deeper than the full-extent zoom produces an overview that looks like Strategy
A. A useful window sits at or above `max_zoom` and at least two levels below the
full-extent zoom. Doubling `SIZE` to 2048 buys one more level of detail at the same
extent; downscale afterwards.

For a dense point layer the failure at low zoom is a blob rather than holes.
Rendering 43,525 street trees at zoom 12 and 13 gave a solid mass with no
structure. Zoom 15 showed the street grid.

### Finding a Dense Cluster

Try `pmtiles:center` or the header centre first, since it costs nothing. When it
turns out to be a bbox corner, or when the collection is large enough to have
several distinct clusters, use DuckDB. GeoParquet 1.1 files carry a `bbox` struct
column, so no spatial extension is needed.

```sql
WITH c AS (
  SELECT (bbox.xmin+bbox.xmax)/2 AS x, (bbox.ymin+bbox.ymax)/2 AS y
  FROM 'publico_arbolado/publico_arbolado.parquet'
), g AS (
  SELECT floor(x/0.0879) gx, floor(y/0.0879) gy, count(*) n FROM c GROUP BY 1,2
), top AS (SELECT gx, gy FROM g ORDER BY n DESC LIMIT 1 OFFSET 0)
SELECT count(*) AS n_in_window, avg(x) AS clon, avg(y) AS clat
FROM c, top
WHERE x BETWEEN (gx-1)*0.0879 AND (gx+2)*0.0879
  AND y BETWEEN (gy-1)*0.0879 AND (gy+2)*0.0879;
```

Set the cell size to `span_for_zoom(z, SIZE) / 111319.49` degrees: 0.176 at zoom 13,
0.088 at 14, 0.044 at 15. `OFFSET` is the variety lever, so raise it to reach the
second- or third-densest cluster and keep two collections off the same
neighborhood. Check the count before you commit; below roughly 100 polygons or
lines, or 200 points, step the zoom down one and try again, up to three times.

A quantile trim on the same centroids, `quantile_cont(x, 0.05)` through
`quantile_cont(x, 0.95)`, is an alternative for a scatter with one distant outlier.
It does little on small collections. Eleven libraries trimmed at the 5th and 95th
percentiles still kept an outlier 25 km out of town, while the densest-cell query
found the cluster of ten.

## Step 4 — Render

### Start the Server

```bash
CHIITILER_DIR=/tmp/chiitiler
if [ ! -d "$CHIITILER_DIR/node_modules" ]; then
    rm -rf "$CHIITILER_DIR"
    git clone --depth 1 \
        https://github.com/Kanahiro/chiitiler "$CHIITILER_DIR"
    cd "$CHIITILER_DIR" && npm install --silent
fi
```

`CHIITILER_PROCESSES=0` turns on multi-process mode, which keeps memory flat across
a large batch. `setsid` and `disown` let the server outlive the shell that started
it, which it has to do whenever you render from a later command.

```bash
cd /tmp/chiitiler
setsid env CHIITILER_PROCESSES=0 npx tsx src/main.ts tile-server \
    --port 13579 --cache memory \
    > /tmp/chiitiler.log 2>&1 < /dev/null &
disown
for i in $(seq 1 40); do
    curl -s -o /dev/null http://localhost:13579/health && break
    sleep 1
done
curl -s -o /dev/null -w "health=%{http_code}\n" http://localhost:13579/health
```

### Build the Styles

Three styles come out of one pass: the image you keep, a probe that answers whether
any data fell inside the frame, and a blank reference to compare the probe against.
Save this as `/tmp/portolan-thumbs/buildstyle.py`.

```python
#!/usr/bin/env python3
"""Build render, probe and blank styles for one collection."""
import json, os, sys

coll_dir, pmtiles_path, use_basemap, basemap_url, basemap_opacity, outdir = sys.argv[1:7]
use_basemap = use_basemap == "true"
basemap_opacity = float(basemap_opacity)

style = json.load(open(os.path.join(coll_dir, "styles", "default.json")))
layers = style.get("layers", [])

h = open(pmtiles_path, "rb").read(127)
MINZ, MAXZ = h[100], h[101]

# Repoint every source at the local PMTiles file and keep the source keys the
# layers already reference. The declared zoom range is what makes MapLibre
# overzoom the deepest stored tile instead of asking for one that isn't there.
def pmtiles_source(src=None):
    return {"type": (src or {}).get("type", "vector"),
            "tiles": ["pmtiles://%s/{z}/{x}/{y}" % pmtiles_path],
            "minzoom": MINZ, "maxzoom": MAXZ}

sources = {k: pmtiles_source(v) for k, v in style.get("sources", {}).items()}
sources = sources or {"data": pmtiles_source()}

white = {"id": "background", "type": "background",
         "paint": {"background-color": "#ffffff"}}

render = dict(style)
render["sources"] = dict(sources)
if use_basemap:
    render["sources"]["basemap"] = {
        "type": "raster", "tiles": [basemap_url], "tileSize": 256}
    # White under the basemap: a failed tile fetch then leaves white rather
    # than transparent, and transparent becomes black in JPEG.
    base_layers = [white,
                   {"id": "basemap", "type": "raster", "source": "basemap",
                    "paint": {"raster-opacity": basemap_opacity}}]
else:
    base_layers = [white]
render["layers"] = base_layers + layers

probe = dict(style)
probe["sources"] = sources
probe["layers"] = [white] + layers

blank = {"version": 8, "sources": {}, "layers": [white]}

for name, doc in (("render", render), ("probe", probe), ("blank", blank)):
    with open(os.path.join(outdir, "%s-style.json" % name), "w") as f:
        json.dump(doc, f)
print("ok")
```

Declaring `minzoom` and `maxzoom` on the vector source is the most important line
here. Without it MapLibre assumes the source goes to zoom 22, asks for a tile the
archive does not contain, and draws nothing, which is what produces an all-basemap
thumbnail. Rendering the pergamino-ide neighborhoods layer, whose tiles stop at
zoom 9, at zoom 13 gave a 1,516-byte blank image without the declaration and a
20,739-byte map with it.

### Render

Save this as `/tmp/portolan-thumbs/render_one.sh`.

```bash
#!/usr/bin/env bash
set -euo pipefail

COLL_DIR="$1"          # absolute collection directory
BBOX="$2"              # framed bbox from frame.py
OUT="$3"               # the existing thumbnail asset's path
FORMAT="${4:-jpeg}"
SIZE="${5:-1024}"
QUALITY="${6:-90}"
PORT="${PORT:-13579}"
WORK="${WORK:-/tmp/portolan-thumbs}"
USE_BASEMAP="${USE_BASEMAP:-true}"
BASEMAP_OPACITY="${BASEMAP_OPACITY:-0.55}"
# Do NOT write ${BASEMAP_URL:-https://.../{z}/{x}/{y}.png}. Bash ends the
# expansion at the first } and silently truncates the template to {z.
: "${BASEMAP_URL:=}"
[ -n "$BASEMAP_URL" ] || \
    BASEMAP_URL='https://basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png'

PMTILES=$(realpath "$(ls "$COLL_DIR"/*.pmtiles | head -1)")

python3 "$WORK/buildstyle.py" "$COLL_DIR" "$PMTILES" \
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

PH=$(sha256sum "$WORK/probe.png" | cut -d' ' -f1)
BH=$(sha256sum "$WORK/blank.png" | cut -d' ' -f1)
PS=$(stat -c%s "$WORK/probe.png"); BS=$(stat -c%s "$WORK/blank.png")

if   [ "$PH" = "$BH" ];                     then GATE1="FAIL-empty"
elif [ "$PS" -lt $(( BS * 115 / 100 )) ];   then GATE1="WARN-sparse"
else                                             GATE1="PASS"; fi

echo "gate1=$GATE1 probe=$PS blank=$BS bytes=$(stat -c%s "$OUT") out=$OUT"
```

Write to the path the collection's thumbnail asset already points at. Read it
rather than assuming an extension:

```bash
OUT=$(python3 -c "
import json
c = json.load(open('collection.json'))
print(next(a['href'] for a in c['assets'].values()
           if 'thumbnail' in (a.get('roles') or [])))")
```

## Step 5 — Check the Result

Two gates. Both run before anything is pushed.

### Gate 1, Automated

`render_one.sh` renders a 256-pixel probe over the same bbox with the collection's
layers on a white background and no basemap, plus a blank reference that is the
white background alone. Identical hashes mean no data landed in the frame. A probe
within 15% of the blank's file size means almost none did. The hashes are
deterministic: three identical renders of the same style and bbox produced
byte-identical PNGs in August 2026.

Gate 1 replaces the old 100-byte file-size check, which passed any image chiitiler
managed to encode, including a uniformly blank one. Keep checking that the file
exists and that the status was 200, since that catches transport failures. A render
error returns 500 with a short text body, and `curl -o` writes that text into your
`.png`.

### Gate 2, Visual

View every image. Six questions; any "no" is a failure.

1. **Data present.** Are features visible, rather than basemap alone? An
   all-basemap, blank, or solid-colour image is a failure, never a valid result.
2. **Data is the subject.** Do features occupy a quarter of the frame or more?
3. **Shape.** Is it landscape and close to 3:2? A tall portrait image fails unless
   you deliberately chose full-extent framing for a boundary layer and said so.
4. **Completeness.** Do continuous fabrics such as parcels and blocks run edge to
   edge without scattered holes? Holes mean the render sits below the archive's
   maximum zoom.
5. **Legibility at card size.** Imagine it at 350x230. Pale fills over a light
   basemap read as flat grey.
6. **Distinctness.** Set beside its siblings, is it recognisable? If two cards
   could be swapped without anyone noticing, change the framing depth or palette.

### Remediation

| Symptom | Fix |
|---|---|
| All basemap, probe empty | Confirm the source declares `minzoom`/`maxzoom`, that `source-layer` matches `pmtiles:layers`, that the source key survived the rewrite, and that the bbox intersects the data |
| All basemap, probe has data | The data is under the basemap or fully transparent. Check layer order and paint opacity |
| Black background | The basemap failed to fetch and transparency became black. Keep a white background layer beneath it, and check the `{z}/{x}/{y}` template survived the shell |
| Thin or portrait image | Framing was skipped, or `MAX_CONTEXT` capped it. Re-run `frame.py`, then either `--max-context 99` or Strategy B |
| Sliver of data in a big frame | `fill` is too low. Switch to Strategy B, or crop with a quantile trim |
| Scattered holes in a continuous fabric | Shrink the window until the render sits at or above `max_zoom`. If it already does, the archive needs retiling |
| Dense points render as one blob | Zoom in. Structure appears when features separate |
| Washed out, flat grey | Lower `BASEMAP_OPACITY`, use a no-labels basemap, or raise the fill opacity in the style |
| Identical to a sibling | Change strategy, raise the `OFFSET` rank, or change the palette |

Retry at most three times per collection, then report what is left and why. Some
collections cannot produce a good thumbnail. A two-point collection is a locator
map and nothing more; say so rather than burning attempts on it.

Legibility problems that survive reframing belong to the style, not to this skill.
The `sourcecoop` skill covers varying default styles.

## Step 6 — Work Through the Catalog

Cards are seen side by side, so judge them as a set. Aim for roughly a third
full-extent and the rest zoomed at varying depths, some at an overview that fills
the box and some deep enough to show real detail. Never put two thumbnails on the
same neighborhood; raise the `OFFSET` rank instead. A portrait boundary layer is
fine as variety when it passes Gate 2.

Keep a record as you go, at `/tmp/portolan-thumbs/framing.tsv`:

```
collection	strategy	bbox	zoom	rank	verdict
publico_arbolado	B	-60.603932,-33.906046,-60.559986,-33.881728	15.0	0	pass
publico_barrios	A	-60.651220,-33.935211,-60.495382,-33.848971	13.17	-	pass
```

It makes the second pass over a failing collection cheap, and it is the evidence
that Gate 2 actually ran.

## Step 7 — Register and Push

The thumbnail asset was registered when the collection was converted, and
`portolan check --fix` will not repoint a stale `href`. Writing
`collection.thumb.png` next to a registered `collection.thumb.jpg` leaves the
catalog pointing at the old image, so write to the existing `href` by default. To
change format deliberately, delete the old file and update the asset's `href` and
`type` together, then push. `versions.json` picks up the new checksums.

```bash
python3 - <<'PY'
import json
c = json.load(open('collection.json'))
for a in c['assets'].values():
    if 'thumbnail' in (a.get('roles') or []):
        a['href'] = './publico_arbolado.thumb.png'
        a['type'] = 'image/png'
json.dump(c, open('collection.json', 'w'), indent=2)
PY
rm -f publico_arbolado.thumb.jpg
portolan push s3://bucket/catalog
```

## Basemap Options

| Style | URL |
|-------|-----|
| Carto Light (default) | `https://basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png` |
| Carto Light, no labels | `https://basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}.png` |
| Carto Dark | `https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png` |
| Carto Voyager | `https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png` |
| OpenStreetMap | `https://tile.openstreetmap.org/{z}/{x}/{y}.png` |
| Stadia Smooth | `https://tiles.stadiamaps.com/tiles/alidade_smooth/{z}/{x}/{y}.png` |

`BASEMAP_OPACITY=0.55` keeps the basemap as context. Raise it when sparse data
needs geographic anchoring, lower it when pale fills are getting lost, and use the
no-labels variant when place names compete with the data. `USE_BASEMAP=false` gives
a plain white background, which renders faster and makes no external requests.

## Output Formats

Portolan core permits `image/png`, `image/jpeg`, and `image/webp`. All three were
confirmed against a running server in August 2026; `gif` returns 400. PNG is
lossless and largest, JPEG is smallest for dense imagery, and WebP compresses best
at the same quality.

The URL path sets the format, so `/clip.webp` and `/clip.jpeg` both work and
`/clip.jpg` is an accepted alias. Whichever you pick has to match the asset's
`type` and the extension in its `href`.

## How It Works

The collection's extent, feature count, thumbnail asset, and PMTiles zoom range
decide a bbox, which `frame.py` reshapes to 3:2. `styles/default.json` is rewritten
in memory with its sources repointed at the local archive through the `pmtiles://`
protocol, the archive's zoom range declared, and a white background under an
optional basemap. chiitiler renders that style through MapLibre GL Native, once for
the image and twice more at 256 pixels for Gate 1.

`styles/default.json` is never modified. The rewritten styles live in
`/tmp/portolan-thumbs/`, and the image lands at the path the thumbnail asset
already points at.

## Troubleshooting

Problems with the image itself are covered by the remediation table in Step 5.
These are the environment failures.

| Issue | Solution |
|-------|----------|
| `npm install` fails | Check `node --version` is 18 or newer |
| Server will not start | Check the port with `lsof -i :13579` and read `/tmp/chiitiler.log` |
| Server dies when the command returns | Start it with `setsid ... & disown` so it outlives the shell |
| Server crashes mid-batch | Set `CHIITILER_PROCESSES=0` for multi-process mode |
| Basemap not loading | Check network access, and check the log for a truncated `{z` in the requested URL, which means the tile template did not survive the shell |
| Render returns 500 | The style is invalid, or a source is unreachable. `/tmp/chiitiler.log` names the cause |
| New thumbnail not showing in the browser | The asset `href` still points at the old file. See Step 7 |
| Very slow rendering | A large bbox or a deep zoom. Reduce `SIZE` |

## Reference

**Zoom and span.** The longest framed edge in metres is
`40075016.686 * size / (256 * 2**z)`. Each zoom level halves it; doubling `SIZE`
holds the span and gains a level of detail.

**Zoom conventions.** `frame.py` reports the standard 256-pixel-tile zoom.
chiitiler computes its MapLibre camera zoom as `log2(size / (512 * bbox_fraction))`
in `src/render/index.ts`, one lower. The number that matters in practice is the
archive's `max_zoom`, and the way to respect it is to declare the source's zoom
range and let MapLibre overzoom.

**Cell size for the density query.** `span_for_zoom(z, SIZE) / 111319.49` degrees:
0.176 at zoom 13, 0.088 at 14, 0.044 at 15.

**Gate 1 thresholds.** Equal sha256 means empty. A probe under 1.15x the blank's
size means sparse.

**Card geometry.** `portolan-browser/src/theme/page.scss` lays the grid out as
`repeat(auto-fill, minmax(350px, 1fr))` with `max-height: 250px` and
`object-fit: scale-down`, so a card image is 350 to about 700 px wide, 250 px tall.
