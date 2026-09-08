# Migration Reference Artifacts

Templates and reference scripts taken from two migrations run in August 2026.
`road-detections` is microsoft-ml-road-detections, one 12 GB collection in 235
country partitions. `pergamino` is pergamino-ide-catalog, 183 collections
harvested from a WFS/GeoServer source and grouped into sub-catalogs.

Each script keeps the module docstring it was written with, because the
docstring states the defect that forced the script to exist. Catalog-specific
values are lifted to constants at the top under a "What a new catalog must
change" banner. The scripts are readable standalone and are not expected to run
unedited.

| File | What it is for | From | Defect or gap it works around |
|---|---|---|---|
| `conformance.md` | Addendum to the template's `docs/conformance.md` for a collection with a remote `partition:glob` | road-detections | rashid expands only a local relative glob, so a remote or absolute glob leaves the partitions unread |
| `tools/reencode.py` | Rewrite source GeoParquet with conformant row groups, then verify nothing moved | road-detections | Source files hold their whole contents in one row group, over the `PTL-DAT-008` 150,000-row cap |
| `tools/build_collection.py` | Generate `collection.json` with measured extent, row count, checksums, and `s3` alternates | road-detections | rashid treats a stale `file:checksum` as a conformance failure, so measured fields cannot be typed by hand |
| `tools/validate_with_data.py` | Run rashid's data pass against staged bytes before publishing | road-detections | The published `partition:glob` is `s3://`, which rashid cannot list locally, so the partition checks never run |
| `tools/sld_graduated.py` | Convert graduated class-break SLDs into MapLibre `step` expressions | pergamino | The CLI's SLD converter reads an equality filter only. It skips a range filter. The output needs `fix_styles.py` to get a source URL |
| `tools/fix_styles.py` | Give every default style a tile source and zoom range, drop duplicate `match` keys | pergamino | Generated styles carry `sources.data` that omits the URL and the zoom range, so nothing renders |
| `tools/apply_metadata.py` | Apply harvested titles, descriptions, providers, and links after every `add` | pergamino | `portolan add` cannot derive metadata that lives outside the tree, such as upstream abstracts and attribution |
