#!/usr/bin/env python3
"""Generate catalog/<collection-id>/collection.json.

From microsoft-ml-road-detections (tools/build_collection.py). Generalized as
a reference; edit the constants under "What a new catalog must change".

The prose lives in this file and is hand-written. Everything a machine can
measure is measured: the spatial extent, the row count, the partition file
count, and the size and checksum of every asset. Those have to be generated
rather than typed, because Rashid treats a stale `file:checksum` as a
conformance failure, not a warning, and they change every time an asset is
rebuilt.

    python3 tools/build_collection.py            write collection.json
    python3 tools/build_collection.py --check    exit 1 if it is stale

Assets that do not exist yet are skipped with a note, so this runs before the
tiles and the thumbnail are built.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import struct
import sys
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parent.parent

# --------------------------------------------------------------------------
# What a new catalog must change.
# --------------------------------------------------------------------------

COLLECTION_ID = "<collection-id>"
PARTITION_KEY = "<partition-key>"  # The Hive key, e.g. "country".
PARTITION_DIR = f"by_{PARTITION_KEY}"

STAGING = ROOT / "staging" / COLLECTION_ID
COLLECTION_DIR = ROOT / "catalog" / COLLECTION_ID
OUTPUT = COLLECTION_DIR / "collection.json"

PUBLIC_BASE = "https://data.source.coop/<account>/<repository>"
PMTILES_NAME = f"{COLLECTION_ID}.pmtiles"

LEGEND_NAME = "<legend>.png"
LEGEND_TITLE = "<what the legend classes are>"
THUMBNAIL_TITLE = (
    "Preview rendered with the default style. <basemap attribution, if any.>"
)

LICENSE = "<SPDX-id>"
LICENSE_LINK = {
    "rel": "license",
    "href": "<https://license-url>",
    "type": "text/html",
    "title": "<license name>",
}
UPSTREAM_LINK = {
    "rel": "via",
    "href": "<https://upstream-source-url>",
    "type": "text/html",
    "title": "<upstream source>",
}
UPDATED = "<YYYY-MM-DDT00:00:00Z>"
TEMPORAL_INTERVAL = [["<YYYY-MM-DDT00:00:00Z>", None]]

# The profile schema version the current spec release defines. Every object in
# the tree, root included, must declare the same one.
PORTOLAN_SCHEMA = "https://schemas.portolan-sdi.org/portolan/v0.1.0/schema.json"

# The glob is s3://, not https://, and that is deliberate. Expanding a glob
# needs a listing, which plain HTTP does not provide: an https glob is sent
# literally and 404s. PORTO-FMT-020 exempts `partition:glob` from the
# https-only rule for exactly this reason. The bucket reads anonymously, so
# this costs a consumer nothing but the path-style setting in AGENTS.md.
PARTITION_GLOB = (
    "s3://<region>.opendata.source.coop/<account>/<repository>"
    f"/{COLLECTION_ID}/{PARTITION_DIR}/{PARTITION_KEY}=*/*.parquet"
)

# Prose. Every sentence should be quoted from the upstream publisher, cited to
# a source, or measured from the data. Keep the citations behind each claim in
# the collection README.

TITLE = "<Collection Title>"

DESCRIPTION = (
    "<One paragraph. What each row is, where the data came from, what the "
    "coverage is, and how to read it. Name the license holder and any known "
    "gap in coverage. State how to read one partition over https and every "
    "partition at once with the `s3://` glob in `partition:glob`. The glob "
    "needs s3 rather than https because expanding it requires a listing. Say "
    "what the partition key actually means if it resembles a standard code "
    "without being one.>"
)

KEYWORDS = ["<keyword>", "<keyword>"]

PROVIDERS = [
    {
        "name": "<Upstream publisher>",
        "description": "<What they produced and under what license.>",
        "url": "<https://upstream-url>",
        "roles": ["producer", "licensor"],
    },
    {
        "name": "<Converter>",
        "description": "<Converted the source releases and maintains this catalog.>",
        "email": "<email>",
        "roles": ["processor"],
    },
    {
        "name": "<Host>",
        "description": "<Publishes and hosts this cloud-native mirror.>",
        "url": "<https://host-url>",
        "email": "<email>",
        "roles": ["host"],
    },
]

# One entry per column that needs more than its Arrow type to be usable. Say
# what the values mean, where they came from, and what is not known about
# them. A column the upstream publisher does not document should say so.
COLUMN_DESCRIPTIONS = {
    PARTITION_KEY: (
        "<What the partition key encodes, and any way it departs from the "
        "standard it resembles.>"
    ),
    "geometry": (
        "<Geometry encoding and CRS, plus anything the publisher does not "
        "state and this catalog therefore does not claim.>"
    ),
    "bbox": (
        "GeoParquet 1.1 covering column. Filter on bbox.xmin/ymin/xmax/ymax "
        "before touching geometry. It is what makes a spatial query skip row "
        "groups."
    ),
}

PARTITION_KEY_DESCRIPTION = (
    "<What the key is>, one GeoParquet file per value. Hive-style directory "
    "naming, so a query engine can prune on it without reading any footers."
)

# --------------------------------------------------------------------------


def multihash(path: Path) -> str:
    """sha2-256 as a multihash: 0x12 for the function, 0x20 for the length."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return "1220" + digest.hexdigest()


def file_fields(path: Path) -> dict:
    return {"file:size": path.stat().st_size, "file:checksum": multihash(path)}


def partitions() -> list[Path]:
    root = STAGING / PARTITION_DIR
    if not root.is_dir():
        return []
    out = []
    for part in sorted(root.iterdir()):
        if part.name.startswith(f"{PARTITION_KEY}="):
            out.extend(sorted(part.glob("*.parquet")))
    return out


def scan_partitions(files: list[Path]) -> dict:
    """Row count, spatial extent, and the Arrow schema, from footers only."""
    rows = 0
    minx = miny = float("inf")
    maxx = maxy = float("-inf")
    schema = None
    for path in files:
        parquet = pq.ParquetFile(path)
        rows += parquet.metadata.num_rows
        if schema is None:
            schema = parquet.schema_arrow
        geo = json.loads(parquet.metadata.metadata[b"geo"])
        bbox = geo["columns"][geo["primary_column"]]["bbox"]
        minx, miny = min(minx, bbox[0]), min(miny, bbox[1])
        maxx, maxy = max(maxx, bbox[2]), max(maxy, bbox[3])
    return {
        "rows": rows,
        "bbox": [minx, miny, maxx, maxy],
        "schema": schema,
        "file_count": len(files),
    }


def table_columns(schema) -> list[dict]:
    out = []
    for field in schema:
        entry = {"name": field.name, "type": str(field.type)}
        if field.name in COLUMN_DESCRIPTIONS:
            entry["description"] = COLUMN_DESCRIPTIONS[field.name]
        out.append(entry)
    return out


class NotReady(Exception):
    """The archive exists but is still being written."""


def pmtiles_header(path: Path) -> dict:
    """Zoom range and vector layer names, read from the PMTiles v3 header.

    tippecanoe creates the output file early and writes its header last, so an
    existence check is not enough to know the archive is usable.
    """
    with path.open("rb") as handle:
        head = handle.read(127)
        if head[:7] != b"PMTiles":
            raise NotReady(f"{path.name} has no PMTiles header yet")
        meta_offset, meta_length = struct.unpack_from("<QQ", head, 24)
        internal_compression = head[97]
        min_zoom, max_zoom = head[100], head[101]
        handle.seek(meta_offset)
        blob = handle.read(meta_length)
    if internal_compression == 2:
        blob = gzip.decompress(blob)
    meta = json.loads(blob)
    layers = [layer["id"] for layer in meta.get("vector_layers", [])]
    return {"min_zoom": min_zoom, "max_zoom": max_zoom, "layers": layers}


def style_assets(notes: list[str]) -> dict:
    """Every styles/*.json, with default.json carrying the default role."""
    styles_dir = COLLECTION_DIR / "styles"
    if not styles_dir.is_dir():
        notes.append("no styles/ directory yet; style assets omitted")
        return {}
    assets = {}
    for path in sorted(styles_dir.glob("*.json")):
        stem = path.stem
        doc = json.loads(path.read_text())
        roles = ["style", "default"] if stem == "default" else ["style"]
        key = "style" if stem == "default" else f"style-{stem}"
        asset = {
            "href": f"./styles/{path.name}",
            "type": "application/vnd.mapbox.style+json",
            "title": doc.get("name", stem),
            "roles": roles,
            **file_fields(path),
        }
        if doc.get("description"):
            asset["description"] = doc["description"]
        assets[key] = asset
    return assets


def build() -> tuple[dict, list[str]]:
    notes: list[str] = []
    files = partitions()
    if not files:
        raise SystemExit(f"no partitions found under {STAGING / PARTITION_DIR}")
    scan = scan_partitions(files)

    assets: dict = {}

    pmtiles = STAGING / PMTILES_NAME
    pmtiles_link = None
    extensions = [
        PORTOLAN_SCHEMA,
        "https://schemas.portolan-sdi.org/incubating/partition/v1.0.0/schema.json",
        "https://stac-extensions.github.io/table/v1.2.0/schema.json",
        "https://stac-extensions.github.io/file/v2.1.0/schema.json",
    ]
    if not pmtiles.exists():
        header = None
        notes.append(f"{pmtiles.name} not built yet; visual asset and pmtiles link omitted")
    else:
        try:
            header = pmtiles_header(pmtiles)
        except NotReady as exc:
            header = None
            notes.append(f"{exc}; visual asset and pmtiles link omitted")
    if header:
        extensions.insert(
            2, "https://stac-extensions.github.io/web-map-links/v1.3.0/schema.json"
        )
        href = f"{PUBLIC_BASE}/{COLLECTION_ID}/{PMTILES_NAME}"
        assets["visual"] = {
            "href": href,
            "type": "application/vnd.pmtiles",
            "title": "Vector tiles, zoom 0 to %d" % header["max_zoom"],
            "description": (
                "Overview tiles for browsing. Built at zoom %d to %d with feature "
                "dropping, so they are not a substitute for the GeoParquet at street "
                "level." % (header["min_zoom"], header["max_zoom"])
            ),
            "roles": ["visual"],
            **file_fields(pmtiles),
        }
        pmtiles_link = {
            "rel": "pmtiles",
            "href": href,
            "type": "application/vnd.pmtiles",
            "title": "Vector tiles",
            "pmtiles:layers": header["layers"],
        }

    assets.update(style_assets(notes))

    legend = COLLECTION_DIR / "legends" / LEGEND_NAME
    if legend.exists():
        assets["legend"] = {
            "href": f"./legends/{LEGEND_NAME}",
            "type": "image/png",
            "title": LEGEND_TITLE,
            "roles": ["legend"],
            **file_fields(legend),
        }
    else:
        notes.append(f"legends/{LEGEND_NAME} not built yet; legend asset omitted")

    thumbnail = COLLECTION_DIR / "thumbnail.png"
    if thumbnail.exists():
        assets["thumbnail"] = {
            "href": "./thumbnail.png",
            "type": "image/png",
            "title": THUMBNAIL_TITLE,
            "roles": ["thumbnail"],
            **file_fields(thumbnail),
        }
    else:
        notes.append("thumbnail.png not built yet; thumbnail asset omitted")

    links = [
        {"rel": "root", "href": "../catalog.json", "type": "application/json"},
        {"rel": "parent", "href": "../catalog.json", "type": "application/json"},
        {
            "rel": "describedby",
            "href": "./README.md",
            "type": "text/markdown",
            "title": "Collection README",
        },
        {
            "rel": "agents",
            "href": "./AGENTS.md",
            "type": "text/markdown",
            "title": "Collection agent guide",
        },
        dict(LICENSE_LINK),
        dict(UPSTREAM_LINK),
    ]
    if pmtiles_link:
        links.append(pmtiles_link)

    collection = {
        "type": "Collection",
        "stac_version": "1.1.0",
        "stac_extensions": extensions,
        "id": COLLECTION_ID,
        "title": TITLE,
        "description": DESCRIPTION,
        "license": LICENSE,
        "keywords": KEYWORDS,
        "updated": UPDATED,
        "providers": PROVIDERS,
        "extent": {
            "spatial": {"bbox": [scan["bbox"]]},
            "temporal": {"interval": TEMPORAL_INTERVAL},
        },
        "partition:scheme": "hive",
        "partition:strategy": "attribute",
        "partition:keys": [
            {
                "name": PARTITION_KEY,
                "type": "string",
                "description": PARTITION_KEY_DESCRIPTION,
            }
        ],
        "partition:file_count": scan["file_count"],
        "partition:glob": PARTITION_GLOB,
        "table:row_count": scan["rows"],
        "table:primary_geometry": "geometry",
        "table:columns": table_columns(scan["schema"]),
        "assets": assets,
        "links": links,
    }
    return collection, notes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="exit 1 if collection.json is stale"
    )
    args = parser.parse_args()

    collection, notes = build()
    rendered = json.dumps(collection, indent=2, ensure_ascii=False) + "\n"

    if args.check:
        if not OUTPUT.exists():
            print(f"STALE: {OUTPUT} does not exist")
            return 1
        if OUTPUT.read_text() != rendered:
            print(f"STALE: {OUTPUT} does not match tools/build_collection.py")
            print("       run: python3 tools/build_collection.py")
            return 1
        print(f"current: {OUTPUT.relative_to(ROOT)}")
        return 0

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(rendered)
    print(f"wrote {OUTPUT.relative_to(ROOT)}")
    print(f"  partitions   {collection['partition:file_count']}")
    print(f"  rows         {collection['table:row_count']:,}")
    print(f"  bbox         {['%.6f' % v for v in collection['extent']['spatial']['bbox'][0]]}")
    print(f"  assets       {', '.join(collection['assets']) or 'none yet'}")
    for note in notes:
        print(f"  note: {note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
