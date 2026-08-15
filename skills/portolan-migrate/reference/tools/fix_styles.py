"""Make every default style loadable, and repair SLD translation defects.

From pergamino-ide-catalog (tools/generate/fix_styles.py). Generalized as a
reference; edit the constants under "What a new catalog must change". It
expects a two-level tree, <root>/<group>/<collection>/styles/default.json.

Three problems in the styles as generated:

1. `sources.data` is `{"type": "vector"}` with no URL, so nothing can resolve
   the tiles. The style carries the publisher's real cartography and renders
   as a flat fallback colour because the source never loads. This is why the
   thumbnails come out monochrome even where a categorical style exists.

2. The source declares no zoom range. MapLibre then assumes the source goes to
   zoom 22, requests a tile the archive does not contain, and draws nothing.

3. The SLD translator emits duplicate `match` keys, so later branches are dead.
   Seen upstream in the idecor-arg catalog too.

Writes the PMTiles path as `pmtiles://../<file>.pmtiles`, matching the spec
reference catalog.
"""

import json
import os
import sys

# --------------------------------------------------------------------------
# What a new catalog must change.
# --------------------------------------------------------------------------

# Highest zoom the PMTiles archives were built to. MapLibre otherwise assumes
# 22 and requests tiles the archive does not contain.
MAXZOOM = 15

# Written next to the catalog root. Lists the collections whose style is a
# single flat colour, which is the list a thumbnail pass has to look at.
FLAT_STYLE_REPORT = "flat-styles.txt"

# --------------------------------------------------------------------------

ROOT = sys.argv[1]


def dedupe_match(expr):
    """Drop duplicate keys from a MapLibre `match` expression."""
    if not (isinstance(expr, list) and expr and expr[0] == "match"):
        return expr, 0
    head, out = expr[:2], []
    body, fallback = expr[2:-1], expr[-1]
    seen, dropped = set(), 0
    for i in range(0, len(body) - 1, 2):
        key, val = body[i], body[i + 1]
        k = json.dumps(key, sort_keys=True)
        if k in seen:
            dropped += 1
            continue
        seen.add(k)
        out += [key, val]
    return head + out + [fallback], dropped


def main():
    fixed = sourced = deduped = 0
    flat, driven = [], []
    for group in sorted(os.listdir(ROOT)):
        gdir = os.path.join(ROOT, group)
        if not os.path.isdir(gdir) or group.startswith("."):
            continue
        for leaf in sorted(os.listdir(gdir)):
            spath = os.path.join(gdir, leaf, "styles", "default.json")
            if not os.path.exists(spath):
                continue
            cdir = os.path.join(gdir, leaf)
            pm = [f for f in os.listdir(cdir) if f.endswith(".pmtiles")]
            style = json.load(open(spath, encoding="utf-8"))

            if pm:
                for key, src in (style.get("sources") or {}).items():
                    src["type"] = src.get("type", "vector")
                    src["url"] = f"pmtiles://../{pm[0]}"
                    src["minzoom"] = 0
                    src["maxzoom"] = MAXZOOM
                sourced += 1

            has_expr = False
            for lyr in style.get("layers", []):
                paint = lyr.get("paint") or {}
                for prop, val in list(paint.items()):
                    new, n = dedupe_match(val)
                    if n:
                        paint[prop] = new
                        deduped += n
                    if isinstance(paint[prop], list) and paint[prop] and \
                            paint[prop][0] in ("match", "step", "interpolate", "case"):
                        has_expr = True
                    # a label layer with an empty field name renders nothing
                    layout = lyr.get("layout") or {}
                    tf = layout.get("text-field")
                    if isinstance(tf, list) and tf[:1] == ["get"] and \
                            (len(tf) < 2 or not tf[1]):
                        layout.pop("text-field", None)

            (driven if has_expr else flat).append(f"{group}/{leaf}")
            json.dump(style, open(spath, "w", encoding="utf-8"),
                      ensure_ascii=False, indent=2)
            fixed += 1

    print(f"styles rewritten      : {fixed}")
    print(f"  given a tile source : {sourced}")
    print(f"  duplicate match keys dropped: {deduped}")
    print(f"  data-driven         : {len(driven)}")
    print(f"  flat (single colour): {len(flat)}")
    report = os.path.join(os.path.dirname(ROOT), FLAT_STYLE_REPORT)
    with open(report, "w") as fh:
        fh.write("\n".join(flat))
    print(f"\nflat-style collections written to {FLAT_STYLE_REPORT}")


if __name__ == "__main__":
    main()
