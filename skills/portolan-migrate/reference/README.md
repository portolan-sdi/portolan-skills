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
| `conformance.md` | Template for `docs/conformance.md`, the record of what the catalog claims and what it does not | both | rashid's data pass skips glob-matched partitions of a partitioned collection with no `data` asset (rashid#130), and stac-validator crashes on every Portolan Collection (portolan-spec#157) |
| `tools/reencode.py` | Rewrite source GeoParquet with conformant row groups, then verify nothing moved | road-detections | Source files hold their whole contents in one row group, over the `PTL-DAT-008` 150,000-row cap |
| `tools/build_collection.py` | Generate `collection.json` with measured extent, row count, and asset checksums | road-detections | rashid treats a stale `file:checksum` as a conformance failure, so measured fields cannot be typed by hand |
| `tools/validate_with_data.py` | Run rashid's data pass against staged bytes before publishing | road-detections | Absolute https hrefs do not resolve locally, so `--data-scope local` skips the byte checks silently |
| `tools/sld_graduated.py` | Convert graduated class-break SLDs into MapLibre `step` expressions | pergamino | The CLI's SLD converter handles categorical rules only and rejects range filters |
| `tools/fix_styles.py` | Give every default style a tile source and zoom range, drop duplicate `match` keys | pergamino | Generated styles carry `sources.data` with no URL and no zoom range, so nothing renders |
| `tools/apply_metadata.py` | Apply per-collection titles, descriptions, providers, and links after every `add` | pergamino | `portolan add` overwrites each collection title with the root title and rewrites `stac_extensions` to the version the CLI ships |
