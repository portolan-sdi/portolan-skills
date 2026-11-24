#!/usr/bin/env python3
"""Run rashid's data pass against the staged bytes, before publishing.

From microsoft-ml-road-detections (tools/validate_with_data.py). Generalized
as a reference; edit the constants under "What a new catalog must change".

The published catalog keeps its absolute bucket glob (PORTO-FMT-064).
After publishing, run rashid 0.4.0 against the catalog URL to list the glob
anonymously and sample partition footers.

This builds a throwaway tree with local hrefs and symlinked partitions.
rashid 0.4.0 checks every file matched by the local relative glob and
reports PTL-PRT-002 at /partition:glob because the glob is relative.
The run requires that finding on the rewritten collection and fails on
any other error, including data errors.

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
            ["rashid", "check", str(tree), "--data-scope", "all", "--json"],
            capture_output=True,
            text=True,
        )
        sys.stdout.write(result.stdout)
        sys.stderr.write(result.stderr)
        if result.returncode != 1:
            print("expected rashid to report a relative-glob error", file=sys.stderr)
            return 1
        try:
            findings = json.loads(result.stdout)["findings"]
            expected = []
            other_errors = []
            collection = tree / COLLECTION / "collection.json"
            for finding in findings:
                if finding["rule_id"] == "PTL-PRT-002":
                    path = Path(finding["path"])
                    if (
                        finding["severity"] == "error"
                        and finding.get("json_pointer") == "/partition:glob"
                        and (tree / path).resolve() == collection.resolve()
                    ):
                        expected.append(finding)
                        continue
                    print("unexpected PTL-PRT-002 finding", file=sys.stderr)
                    return 1
                if finding["severity"] == "error":
                    other_errors.append(finding)
        except (ValueError, KeyError, TypeError) as exc:
            print(f"invalid rashid JSON report: {exc}", file=sys.stderr)
            return 1

        if len(expected) != 1:
            print("expected one PTL-PRT-002 at the rewritten glob", file=sys.stderr)
            return 1
        return 1 if other_errors else 0


if __name__ == "__main__":
    sys.exit(main())
