#!/usr/bin/env python3
"""Run rashid's data pass against the staged bytes, before publishing.

From microsoft-ml-road-detections (tools/validate_with_data.py). Generalized
as a reference; edit the constants under "What a new catalog must change".

The published catalog addresses its data with absolute https hrefs and an
absolute `partition:glob`, which is correct and is also why the byte-level
checks cannot run locally: those URLs do not resolve until the data is
uploaded. `--data-scope local` skips them silently, so a clean run there
proves nothing about the GeoParquet.

This builds a throwaway tree that mirrors the published layout, with the
remote references rewritten to local ones and the partitions symlinked rather
than copied, then runs rashid over it with the data pass enabled. That is what
exercises PTL-DAT-006 (spatial ordering), 007 (per-row-group statistics), 008
(the 150,000-row cap), 012 (GeoParquet version) and 014 (one schema across
partitions) against real bytes.

Checksums still match because the symlinks point at the same files the
generator measured.

    python3 tools/validate_with_data.py
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# --------------------------------------------------------------------------
# What a new catalog must change.
# --------------------------------------------------------------------------

COLLECTION = "<collection-id>"
PARTITION_KEY = "<partition-key>"  # The Hive key, e.g. "country".
PARTITION_DIR = f"by_{PARTITION_KEY}"
PMTILES = f"{COLLECTION}.pmtiles"

# --------------------------------------------------------------------------

CATALOG = ROOT / "catalog"
STAGING = ROOT / "staging" / COLLECTION


def localise(tree: Path) -> list[str]:
    """Point the collection at local files. Returns what was rewritten."""
    path = tree / COLLECTION / "collection.json"
    doc = json.loads(path.read_text())
    changes = []

    if "partition:glob" in doc:
        changes.append(f"partition:glob {doc['partition:glob']}")
        doc["partition:glob"] = f"./{PARTITION_DIR}/{PARTITION_KEY}=*/*.parquet"

    for key, asset in doc.get("assets", {}).items():
        href = asset.get("href", "")
        if href.startswith("http") and href.endswith(".pmtiles"):
            changes.append(f"assets.{key}.href {href}")
            asset["href"] = f"./{PMTILES}"

    for link in doc.get("links", []):
        if link.get("rel") == "pmtiles" and link.get("href", "").startswith("http"):
            changes.append(f"links[pmtiles].href {link['href']}")
            link["href"] = f"./{PMTILES}"

    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
    return changes


def main() -> int:
    partitions = STAGING / PARTITION_DIR
    if not partitions.is_dir():
        print(f"no staged partitions at {partitions}; run tools/reencode.py first")
        return 1

    with tempfile.TemporaryDirectory(prefix="rashid-data-") as tmp:
        tree = Path(tmp) / "catalog"
        shutil.copytree(CATALOG, tree)

        # Symlink rather than copy. The partitions and the tile archive can run
        # to tens of gigabytes.
        (tree / COLLECTION / PARTITION_DIR).symlink_to(partitions.resolve())
        archive = STAGING / PMTILES
        if archive.exists():
            (tree / COLLECTION / PMTILES).symlink_to(archive.resolve())
        else:
            print(f"note: {PMTILES} is absent, so its byte checks will not run")

        for change in localise(tree):
            print(f"  rewritten: {change}")

        print(f"\nrunning rashid over {tree} with the data pass enabled")
        print("this reads every partition footer, so it takes a few minutes\n")
        result = subprocess.run(
            ["rashid", "check", str(tree), "--data-scope", "all"],
            capture_output=True,
            text=True,
        )
        sys.stdout.write(result.stdout)
        sys.stderr.write(result.stderr)
        return result.returncode


if __name__ == "__main__":
    sys.exit(main())
