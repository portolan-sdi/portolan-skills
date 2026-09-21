#!/usr/bin/env python3
"""Re-encode the source GeoParquet files with conformant row groups.

From microsoft-ml-road-detections (tools/reencode.py). Generalized as a
reference; edit the constants under "What a new catalog must change".

Rashid rule PTL-DAT-008 caps a row group at 150,000 rows. In that migration
215 of the 235 source files held their entire contents in a single row group,
the largest being 3,593,665 rows, so a spatial query had to read the whole
file. This script rewrites each file with 100,000-row row groups.

Nothing else changes. Rows keep their existing Hilbert order because batches
are streamed in file order, the schema is copied from the source including its
`geo` metadata, and compression stays ZSTD.

Reading is streamed rather than loaded whole, so peak memory per worker is one
batch (roughly 12 MB) instead of one file (up to 10 GB for the largest
partition in that catalog).

    python3 reencode.py            convert into staging/
    python3 reencode.py --verify   compare staging/ against the source
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import sys
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parent.parent

# --------------------------------------------------------------------------
# What a new catalog must change.
# --------------------------------------------------------------------------

# The pre-migration tree this catalog was built from. It sits outside the
# repository because it is the working directory the original conversion ran
# in, and it is not something the repository owns. Override with --source.
SOURCE_ROOT = Path.home() / "path/to/pre-migration/tree"

COLLECTION_ID = "<collection-id>"
PARTITION_KEY = "<partition-key>"  # The Hive key, e.g. "country".
PARTITION_DIR = f"by_{PARTITION_KEY}"
STAGING_ROOT = ROOT / "staging" / COLLECTION_ID / PARTITION_DIR

GEOMETRY_COLUMN = "geometry"

COMPRESSION = "zstd"
COMPRESSION_LEVEL = 15  # Match the level the source files were written with.

# Set True only when every geometry is a WKB LineString and a total length is
# worth reporting. The verification pass compares this before and after, which
# is what proves the re-encode moved no coordinates.
MEASURE_LINESTRING_LENGTH = True

# --------------------------------------------------------------------------

ROW_GROUP_SIZE = 100_000  # Rashid PTL-DAT-008 caps this at 150,000.
MAX_ROW_GROUP_ROWS = 150_000  # The PTL-DAT-008 cap itself.

EARTH_RADIUS_M = 6_371_008.8


def source_files() -> list[Path]:
    """Every source partition, sorted, discovered without shelling out to find."""
    found = []
    for region in sorted(SOURCE_ROOT.iterdir()):
        partition_root = region / PARTITION_DIR
        if not partition_root.is_dir():
            continue
        for part in sorted(partition_root.iterdir()):
            if not part.name.startswith(f"{PARTITION_KEY}="):
                continue
            found.extend(sorted(part.glob("*.parquet")))
    return found


def partition_value(path: Path) -> str:
    return path.parent.name.split("=", 1)[1]


def target_for(path: Path) -> Path:
    value = partition_value(path)
    return STAGING_ROOT / f"{PARTITION_KEY}={value}" / f"{value}.parquet"


def geodesic_km(wkb_column: pa.Array, n_points: np.ndarray) -> float:
    """Sum great-circle segment length over a run of WKB LineStrings.

    Coordinates are extracted from the Arrow buffers directly, so this stays
    vectorised. Every record is a little-endian LineString with a 9-byte
    header, which lets the coordinate region be isolated by dropping those
    bytes. Accuracy is within roughly 0.5% of a true WGS84 geodesic, which is
    ample for a documented total.
    """
    offsets = np.frombuffer(wkb_column.buffers()[1], dtype=np.int32)
    offsets = offsets[: len(wkb_column) + 1].astype(np.int64)
    data = np.frombuffer(wkb_column.buffers()[2], dtype=np.uint8)
    base = offsets[0]

    keep = np.ones(offsets[-1] - base, dtype=bool)
    keep[((offsets[:-1] - base)[:, None] + np.arange(9)).ravel()] = False
    coords = data[base : offsets[-1]][keep].view(np.float64).reshape(-1, 2)

    lon = np.radians(coords[:, 0])
    lat = np.radians(coords[:, 1])
    mid_lat = (lat[:-1] + lat[1:]) * 0.5
    segments = EARTH_RADIUS_M * np.hypot(np.diff(lat), np.diff(lon) * np.cos(mid_lat))
    segments[np.cumsum(n_points)[:-1] - 1] = 0.0  # Drop cross-geometry joins.
    return float(segments.sum()) / 1000.0


def measure(path: Path) -> dict:
    """Everything the verification step needs, read in a single pass."""
    parquet = pq.ParquetFile(path)
    meta = parquet.metadata
    geo = json.loads(meta.metadata[b"geo"])

    max_row_group = max(
        meta.row_group(i).num_rows for i in range(meta.num_row_groups)
    )

    length_km = 0.0
    values: set[str] = set()
    columns = [GEOMETRY_COLUMN, PARTITION_KEY]
    for batch in parquet.iter_batches(batch_size=250_000, columns=columns):
        if MEASURE_LINESTRING_LENGTH:
            wkb = batch.column(GEOMETRY_COLUMN)
            offsets = np.frombuffer(wkb.buffers()[1], dtype=np.int32)
            offsets = offsets[: len(wkb) + 1].astype(np.int64)
            n_points = (offsets[1:] - offsets[:-1] - 9) // 16
            length_km += geodesic_km(wkb, n_points)
        key = batch.column(PARTITION_KEY)
        if pa.types.is_dictionary(key.type):
            key = key.dictionary_decode()
        values.update(key.unique().to_pylist())

    return {
        "rows": meta.num_rows,
        "row_groups": meta.num_row_groups,
        "max_row_group_rows": max_row_group,
        "bytes": path.stat().st_size,
        "geo": geo,
        "schema": str(parquet.schema_arrow.remove_metadata()),
        "length_km": length_km,
        "partition_values": sorted(values),
    }


def convert(path: Path) -> tuple[str, str | None]:
    value = partition_value(path)
    target = target_for(path)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        parquet = pq.ParquetFile(path)
        schema = parquet.schema_arrow  # Carries the `geo` metadata key.

        writer = pq.ParquetWriter(
            target,
            schema,
            compression=COMPRESSION,
            compression_level=COMPRESSION_LEVEL,
        )
        try:
            for batch in parquet.iter_batches(batch_size=ROW_GROUP_SIZE):
                table = pa.Table.from_batches([batch], schema=batch.schema)
                if not table.schema.equals(schema):
                    table = table.cast(schema.remove_metadata()).replace_schema_metadata(
                        schema.metadata
                    )
                writer.write_table(table, row_group_size=ROW_GROUP_SIZE)
        finally:
            writer.close()
        return value, None
    except Exception as exc:  # noqa: BLE001 - reported per file, run continues
        if target.exists():
            target.unlink()
        return value, repr(exc)


def run_convert(workers: int) -> int:
    files = source_files()
    print(f"converting {len(files)} files into {STAGING_ROOT} with {workers} workers")
    failures = []
    done = 0
    with cf.ProcessPoolExecutor(workers) as pool:
        for value, error in pool.map(convert, files):
            done += 1
            if error:
                failures.append((value, error))
                print(f"  [{done}/{len(files)}] {value} FAILED {error}")
            elif done % 25 == 0 or done == len(files):
                print(f"  [{done}/{len(files)}] ok")
    if failures:
        print(f"\n{len(failures)} failures:")
        for value, error in failures:
            print(f"  {value}: {error}")
        return 1
    print("all files converted")
    return 0


def run_verify(workers: int) -> int:
    files = source_files()
    print(f"verifying {len(files)} files")

    pairs = [(f, target_for(f)) for f in files]
    missing = [t for _, t in pairs if not t.exists()]
    if missing:
        print(f"FAIL: {len(missing)} staged files missing, first: {missing[0]}")
        return 1

    with cf.ProcessPoolExecutor(workers) as pool:
        before = list(pool.map(measure, [s for s, _ in pairs]))
        after = list(pool.map(measure, [t for _, t in pairs]))

    problems = []
    schemas = set()
    for (source, _), was, now in zip(pairs, before, after):
        value = partition_value(source)
        schemas.add(now["schema"])
        if was["rows"] != now["rows"]:
            problems.append(f"{value}: rows {was['rows']} -> {now['rows']}")
        if was["geo"] != now["geo"]:
            problems.append(f"{value}: geo metadata changed")
        if was["partition_values"] != now["partition_values"]:
            problems.append(f"{value}: {PARTITION_KEY} values changed")
        if was["schema"] != now["schema"]:
            problems.append(f"{value}: schema changed")
        if now["max_row_group_rows"] > MAX_ROW_GROUP_ROWS:
            problems.append(
                f"{value}: max row group {now['max_row_group_rows']} "
                f"exceeds {MAX_ROW_GROUP_ROWS}"
            )
        if abs(was["length_km"] - now["length_km"]) > 0.001:
            problems.append(
                f"{value}: length {was['length_km']:.3f} -> {now['length_km']:.3f} km"
            )

    if len(schemas) != 1:
        problems.append(f"PTL-DAT-014: {len(schemas)} distinct schemas across partitions")

    def total(rows, key):
        return sum(r[key] for r in rows)

    print()
    print(f"{'metric':<26}{'before':>18}{'after':>18}")
    print(f"{'files':<26}{len(before):>18,}{len(after):>18,}")
    print(f"{'rows':<26}{total(before,'rows'):>18,}{total(after,'rows'):>18,}")
    print(f"{'bytes':<26}{total(before,'bytes'):>18,}{total(after,'bytes'):>18,}")
    print(f"{'row groups':<26}{total(before,'row_groups'):>18,}{total(after,'row_groups'):>18,}")
    print(
        f"{'max row group rows':<26}"
        f"{max(r['max_row_group_rows'] for r in before):>18,}"
        f"{max(r['max_row_group_rows'] for r in after):>18,}"
    )
    print(
        f"{'total length km':<26}"
        f"{total(before,'length_km'):>18,.0f}{total(after,'length_km'):>18,.0f}"
    )
    growth = total(after, "bytes") / total(before, "bytes") - 1
    print(f"\nsize change: {growth * 100:+.2f}%")

    if problems:
        print(f"\nVERIFICATION FAILED, {len(problems)} problems:")
        for line in problems[:40]:
            print(f"  {line}")
        return 1
    print(
        f"\nVERIFICATION PASSED: rows, geometry length, {PARTITION_KEY} values, "
        "geo metadata and schema are unchanged. Every row group is within the "
        f"{MAX_ROW_GROUP_ROWS:,}-row cap."
    )
    return 0


def main() -> int:
    global SOURCE_ROOT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true", help="compare staging against source")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument(
        "--source",
        type=Path,
        default=SOURCE_ROOT,
        help=f"pre-migration by_region tree (default: {SOURCE_ROOT})",
    )
    args = parser.parse_args()
    SOURCE_ROOT = args.source
    if not SOURCE_ROOT.is_dir():
        print(f"source tree not found: {SOURCE_ROOT}")
        return 1
    return run_verify(args.workers) if args.verify else run_convert(args.workers)


if __name__ == "__main__":
    sys.exit(main())
