---
name: reading-portolan
description: Use when exploring, querying, analyzing, or visualizing data from a Portolan catalog (STAC-based cloud-native geospatial data). Covers reading AGENTS.md and STAC metadata, finding assets by role, querying GeoParquet and Parquet with DuckDB, reading COGs, cross-dataset joins, partitioned collections, and interactive maps with PMTiles and MapLibre.
---

<!-- drift: depends-on: portolan-spec -->

# Reading Portolan Data

A Portolan catalog is a STAC catalog served as static files from object storage. Vector data is GeoParquet paired with PMTiles. Raster data is Cloud Optimized GeoTIFF (COG). Tabular data is plain Parquet with no geometry column. There is no API server. You read the JSON, then query the files in place with DuckDB or rasterio.

The [Portolan specification](https://github.com/portolan-sdi/portolan-spec) is ground truth. Read `specs/portolan/core.md` and `specs/portolan/formats.md` at tag v0.2.0 when this skill and a catalog disagree. Rule ids such as `PORTO-CORE-061` point into `specs/portolan/requirements.yaml`.

## Step 1: Detect the Environment

Check what is installed before you suggest a tool.

```bash
duckdb --version
python -c "import duckdb; print(duckdb.__version__)"
python -c "import geopandas; print(geopandas.__version__)"
python -c "import rasterio; print(rasterio.__version__)"
python -c "import rioxarray; print('rioxarray ok')"
gpio --version
ogr2ogr --version
```

| Installed | Vectors and tables | Rasters |
|---|---|---|
| DuckDB | `read_parquet` with the `spatial` and `httpfs` extensions. Best choice. | Not applicable |
| GeoPandas only | `gpd.read_parquet()` | Not applicable |
| rioxarray | Not applicable | `rioxarray.open_rasterio()`. Best choice. |
| rasterio only | Not applicable | `rasterio.open()` |
| Nothing | Suggest DuckDB | Suggest rioxarray |

If nothing is installed, explain the options and offer to guide an install. Respect a no. Every tool above reads remote files by HTTP range request, so nobody needs to download a whole file first.

Install a current DuckDB with the `spatial` extension.

## Step 2: Read the Metadata

### Catalog Layout

```
catalog-root/
├── catalog.json                 # Root STAC Catalog
├── AGENTS.md                    # Agent guide, linked as rel: agents
├── README.md                    # Human guide, linked as rel: describedby
└── {collection_id}/
    ├── collection.json          # Extent, providers, license, assets, links
    ├── AGENTS.md
    ├── README.md
    ├── {data}.parquet           # data asset
    ├── {data}.pmtiles           # rel: pmtiles link
    ├── thumbnail.png            # thumbnail asset
    ├── styles/default.json      # style asset with the default role
    └── {item_id}/{item_id}.json # one directory per item, when items exist
```

Every catalog and every collection carries an `AGENTS.md` and a `README.md` (PORTO-CORE-061, PORTO-CORE-062). A `versions.json` beside them is a CLI artifact, not part of the specification. Ignore it when you read data. There is no `llms.txt` in the specification.

### Crawl the Catalog

Start at `catalog.json`. Follow every link with `rel: child`. A child with `"type": "Catalog"` is a sub-catalog, so recurse into it. A child with `"type": "Collection"` is a dataset. Build the full inventory before you answer a question.

```bash
BASE=https://example.com/catalog
curl -s $BASE/catalog.json | jq -r '.links[] | select(.rel=="child") | .href'
```

### Read AGENTS.md First

Every collection links its `AGENTS.md` with `rel: agents` and its `README.md` with `rel: describedby`. Read `AGENTS.md` before you write a query. It names the join keys, the coordinate system, the useful aggregations, and the data quality traps. The README carries the schema table and the provenance.

```bash
COLL=$BASE/collection-id
curl -s $COLL/collection.json \
  | jq -r '.links[] | select(.rel=="agents" or .rel=="describedby") | .href'
curl -s $COLL/AGENTS.md
```

### Read collection.json

```bash
curl -s $COLL/collection.json | jq '{
  id, title, license, updated,
  spec: [.stac_extensions[] | select(test("portolan-sdi.org/portolan"))],
  bbox: .extent.spatial.bbox,
  time: .extent.temporal.interval,
  providers: [.providers[] | {name, roles}],
  via: [.links[] | select(.rel=="via" or .rel=="canonical") | .href],
  pmtiles: [.links[] | select(.rel=="pmtiles") | {href, layers: .["pmtiles:layers"]}],
  assets: (.assets | to_entries | map({key, href: .value.href, type: .value.type, roles: .value.roles})),
  glob: .["partition:glob"],
  columns: [.["table:columns"][]? | {name, type}]
}'
```

What each field tells you:

- `stac_extensions` carries `https://schemas.portolan-sdi.org/portolan/v0.2.0/schema.json`. That URI is the only signal of the specification version (PORTO-CORE-006).
- `license` is an SPDX identifier, or `other` with a `rel: license` link (PORTO-CORE-058, PORTO-CORE-059). Report it before you redistribute anything.
- `providers` lists at least one `producer` and exactly one `host`, last (PORTO-CORE-047). When the producer and the host are the same organization, the catalog is official. When they differ, the catalog is a mirror.
- A mirror carries a `via` link (`text/html`) to the original source (PORTO-CORE-053). It carries a `canonical` link when the source publishes its own STAC (PORTO-CORE-054). It sets top-level `updated` to the last sync time (PORTO-CORE-057). Compare `updated` with the source when freshness matters.
- `table:columns` documents the columns with names, types, and descriptions. Read it before `DESCRIBE`.
- `partition:glob` is present only on a partitioned collection. See Step 4.

### Find Assets by Role

Asset keys carry no meaning. Filter on `roles` (PORTO-CORE-027). Every asset carries a `type` and at least one role (PORTO-CORE-025).

| Role | What it is | Media type |
|---|---|---|
| `data` | The primary GeoParquet, Parquet, or COG | `application/vnd.apache.parquet` or `image/tiff; application=geotiff; profile=cloud-optimized` |
| `collection-mirror` | `items.parquet`, a stac-geoparquet copy of the items | `application/vnd.apache.parquet` |
| `style` | A MapLibre GL style. One also carries `default`. | `application/vnd.mapbox.style+json` |
| `visual` | The PMTiles file, when it is also a distribution asset | `application/vnd.pmtiles` |
| `thumbnail` | Preview image | `image/png`, `image/jpeg`, or `image/webp` |
| `source` | The upstream original a mirror converted from | Any |

```bash
curl -s $COLL/collection.json \
  | jq -r '.assets | to_entries[] | select(.value.roles | index("data")) | .value.href'
```

Hrefs are relative to the file that holds them. An absolute asset href uses `https` (PORTO-CORE-023). An asset may add an `s3://` or `gs://` URL under `alternate` (PORTO-CORE-024). Use the `https` href with DuckDB unless you have bucket credentials. Do not rewrite an `https` URL into `s3://` by hand.

### Where the Data Lives

- A single-file vector, tabular, or single-COG collection puts its `data` asset on the collection (PORTO-CORE-017).
- A raster collection with several scenes puts one COG on each item. Items live at `{item_id}/{item_id}.json`. The collection should also publish `items.parquet` with the `collection-mirror` role (PORTO-FMT-040, PORTO-FMT-041). Query that file to find scenes instead of fetching every item JSON.
- A partitioned vector collection puts its files behind `partition:glob` (PORTO-FMT-019). It may also list partitions as items.
- A tabular collection is a Parquet `data` asset with no geometry column (PORTO-FMT-034). Its `extent.spatial.bbox` is the area the table refers to, not a footprint. When geometry and attributes live in separate files, the README documents the join columns and carries a working join example (PORTO-FMT-038). Copy that example.

## Step 3: Query Vectors and Tables with DuckDB

```sql
INSTALL spatial; LOAD spatial;
INSTALL httpfs; LOAD httpfs;
```

For a private `s3://` bucket, set `s3_region`, `s3_access_key_id`, and `s3_secret_access_key` before you read.

### Explore Before You Query

```sql
-- Schema. Compare with table:columns.
DESCRIBE SELECT * FROM read_parquet('https://.../data.parquet') LIMIT 0;

-- Row count. Reads the footer only.
SELECT count(*) FROM read_parquet('https://.../data.parquet');

-- Always LIMIT during exploration.
SELECT * FROM read_parquet('https://.../data.parquet') LIMIT 10;

-- Sample values for a column.
SELECT DISTINCT column_name FROM read_parquet('https://.../data.parquet') LIMIT 20;
```

### Use the File Layout

Portolan GeoParquet follows rules that make remote queries cheap:

- Rows are spatially ordered (PORTO-FMT-006). Hilbert order is common, but it is one scheme among several. Do not assume a specific curve.
- Every file carries per-row-group spatial statistics (PORTO-FMT-007). GeoParquet 1.1 files carry a `bbox` covering column with min and max statistics. GeoParquet 2.x files may carry native geometry statistics and no `bbox` column. Check `DESCRIBE` before you reference `bbox`.
- Row groups hold at most 150,000 rows (PORTO-FMT-009). A spatial or attribute filter skips whole groups from metadata.
- Files are compressed, `zstd` by default.

When a `bbox` column exists, filter on it first. The filter prunes row groups without parsing geometry.

```sql
SELECT * FROM read_parquet('https://.../data.parquet')
WHERE bbox.xmin > 5.0 AND bbox.xmax < 6.0
  AND bbox.ymin > 52.0 AND bbox.ymax < 53.0
LIMIT 100;
```

Refine with the geometry only after the bbox pass:

```sql
SELECT * FROM (
  SELECT * FROM read_parquet('https://.../data.parquet')
  WHERE bbox.xmin > 5.0 AND bbox.xmax < 6.0
    AND bbox.ymin > 52.0 AND bbox.ymax < 53.0
)
WHERE ST_Intersects(geometry, ST_MakeEnvelope(5.0, 52.0, 6.0, 53.0));
```

Without a `bbox` column, use `ST_Intersects` directly. DuckDB still prunes on native statistics where the file has them.

### Common Patterns

```sql
-- Attribute filter and aggregation
SELECT province, sum(population) AS total_pop, count(*) AS n
FROM read_parquet('https://.../data.parquet')
WHERE year >= 2020
GROUP BY province ORDER BY total_pop DESC;

-- Area and distance. Units follow the CRS.
SELECT name, ST_Area(geometry) AS area FROM read_parquet('https://.../polygons.parquet')
ORDER BY area DESC LIMIT 10;

-- Point in polygon
SELECT p.name, r.name AS region
FROM read_parquet('https://.../points.parquet') p
JOIN read_parquet('https://.../regions.parquet') r
  ON ST_Within(p.geometry, r.geometry);
```

Check the CRS in `DESCRIBE` or in the collection metadata before you trust an area or a distance. A projected CRS gives meters. EPSG:4326 gives degrees.

### Cross-Collection Joins

Collections in one catalog share a base URL, so a join across them is one query. Read each collection's `AGENTS.md` for the join key first. An attribute join on a documented key beats a spatial join.

```sql
-- Which park holds the most buildings?
SELECT parks.name, count(*) AS building_count
FROM read_parquet('https://.../parks/parks.parquet') parks
JOIN read_parquet('https://.../buildings/buildings.parquet') b
  ON ST_Within(b.geometry, parks.geometry)
GROUP BY parks.name ORDER BY building_count DESC;
```

Large spatial joins are slow. Filter each side with a WHERE clause or a bbox pass first. Materialize a filtered subset with `CREATE TABLE subset AS SELECT ...`, then join the subset.

### Export

```sql
COPY (SELECT * FROM read_parquet('https://.../data.parquet') WHERE ...)
TO 'subset.parquet' (FORMAT PARQUET, COMPRESSION ZSTD);

COPY (SELECT * FROM read_parquet('https://.../data.parquet') WHERE ...)
TO 'subset.geojson' WITH (FORMAT GDAL, DRIVER 'GeoJSON');
```

For other formats use `ogr2ogr`. It reads remote files through `/vsicurl/https://...`, `/vsis3/bucket/...`, and `/vsigs/bucket/...`. `gpio inspect data.parquet` and `gpio inspect stats data.parquet` give a quick summary without SQL. `gpio check all data.parquet` reports whether a file follows the layout rules above.

## Step 4: Partitioned Collections

A collection with `partition:glob` spreads its rows over several files. The glob is the bulk-access path (PORTO-FMT-019). Copy it as written. Do not build your own pattern from the asset hrefs, because the scheme decides the directory layout.

The glob may use `s3://` or `gs://` even though asset hrefs use `https` (PORTO-FMT-020). Glob expansion needs a bucket listing, and plain `https` cannot list. DuckDB does not expand an `https` glob.

```sql
-- Public GCS bucket: an anonymous secret is enough.
LOAD httpfs;
CREATE SECRET (TYPE gcs);

-- Copy partition:glob from collection.json.
SELECT count(*) FROM read_parquet(
  'gs://bucket/catalog/collection/quadkey_prefix=*/*.parquet'
);

-- Explore one partition first.
SELECT * FROM read_parquet(
  'gs://bucket/catalog/collection/quadkey_prefix=00/*.parquet'
) LIMIT 10;

-- Hive-style paths prune on the partition key.
SELECT * FROM read_parquet(
  'gs://bucket/catalog/collection/quadkey_prefix=*/*.parquet',
  hive_partitioning = true
) WHERE quadkey_prefix = '00';
```

For `s3://`, set the region and, for a private bucket, the keys. Every partition file shares one schema (PORTO-FMT-021), so the glob queries as one table. When the partitions are also items, `items.parquet` or the item JSONs give each partition's bbox.

## Step 5: Read Rasters

A single COG is a collection `data` asset. A multi-scene collection has one item per scene. Query `items.parquet` (role `collection-mirror`) with DuckDB to select scenes by bbox or datetime, then open the COG href from the chosen rows.

Every band of a Portolan COG carries an embedded minimum, maximum, mean, and standard deviation (PORTO-FMT-027). They sit in the leading header block, so one range request returns them. Read them from the tags. Do not compute statistics from pixels.

```python
import rasterio

with rasterio.open("https://example.com/catalog/collection/scene.tif") as src:
    print(src.crs, src.bounds, src.res, src.count, src.nodata)
    for band in range(1, src.count + 1):
        print(band, src.tags(band))  # STATISTICS_MINIMUM, _MAXIMUM, _MEAN, _STDDEV
```

Read windows, not whole files. `rioxarray.open_rasterio(url)` is lazy. `da.isel(x=slice(0, 512), y=slice(0, 512)).compute()` fetches only the tiles that window touches. Use `src.overviews(1)` and a decimated read for a whole-extent preview.

For conversion, `gdal_translate` and `gdalwarp` read the same `/vsicurl/` URLs as `ogr2ogr`. Point cloud support is not yet defined in the specification (PORTO-FMT-039). Do not promise COPC support.

## Step 6: Visualize

Use MapLibre GL JS with the PMTiles protocol. Do not export GeoJSON or inline data for a web map. The collection already ships tiles built for the browser.

### Find the Tiles

PMTiles is a collection-level link with `rel: pmtiles` and type `application/vnd.pmtiles` (PORTO-FMT-011). Its `pmtiles:layers` array names the layers a client shows by default (PORTO-FMT-012). Those names are the `source-layer` values for MapLibre. Do not guess the layer name from the file name. An asset with the `visual` role may carry the same file when the publisher also offers it for download.

```bash
curl -s $COLL/collection.json \
  | jq '.links[] | select(.rel=="pmtiles") | {href, layers: .["pmtiles:layers"]}'
```

`pmtiles show data.pmtiles --metadata` prints the full layer list from a local or remote archive.

### Use the Shipped Style

A collection with PMTiles carries at least one style asset (PORTO-FMT-014). Filter assets on the `style` role (PORTO-CORE-069). When there are several, exactly one also carries `default` (PORTO-CORE-070). Each style is a complete MapLibre GL style, version 8, with media type `application/vnd.mapbox.style+json` (PORTO-FMT-015). Its `sources.data.url` is a path relative to the `styles/` directory, usually `../{name}.pmtiles`. Resolve it against the style URL before you load it.

```bash
curl -s $COLL/collection.json \
  | jq '.assets | to_entries[] | select(.value.roles | index("style")) | {key, href: .value.href, roles: .value.roles}'
```

Reference files in this skill:

- `reference/style-default.json` shows the shape of a shipped style.
- `reference/map-style.html` loads a style asset, resolves its PMTiles URL, and switches styles.
- `reference/map-inline.html` builds a style inline when the collection ships none. It takes the PMTiles URL and the `source-layer` from the `rel: pmtiles` link.
- `reference/map-multi.js` draws two collections on one map.

Read the shipped style even when you build your own map. It holds the right `source-layer`, a palette matched to the attribute values, and the `match` and `filter` expressions that show which values exist.

### Data-Driven Styling

MapLibre expressions style by attribute:

```javascript
"fill-color": ["match", ["get", "category"], "residential", "#4361ee", "commercial", "#e63946", "#999999"]
"fill-opacity": ["interpolate", ["linear"], ["get", "value"], 0, 0.1, 100, 0.9]
"filter": ["==", ["get", "status"], "active"]
```

Use deck.gl only for 3D extrusion or analytical overlays that MapLibre cannot draw. Its `MVTLayer` reads the same PMTiles file. For a COG on a web map you need a tile server. Rendering rasters in the browser is out of scope for this skill.

## Workflow: Answer a Question About a Catalog

1. Crawl `catalog.json` and every sub-catalog. List the collections.
2. Read the `AGENTS.md` of each relevant collection.
3. Read `collection.json`. Note the license, the providers, `updated`, `table:columns`, and `partition:glob`.
4. Pick the `data` asset by role, or copy `partition:glob`, or query `items.parquet`.
5. Explore with `DESCRIBE`, `count(*)`, and `LIMIT 10`.
6. Answer with one DuckDB query. Filter before you join.
7. For a map, use the `rel: pmtiles` link and the `default` style asset.
8. Report the license and, for a mirror, the `via` source and the `updated` time.

## Troubleshooting

**403 or 404 on a data URL.** Confirm the href resolves against the file that holds it, not against the catalog root. A private bucket needs credentials. Do not turn an `https` href into `s3://` by hand.

**Glob returns nothing or errors.** You used an `https` glob. Copy `partition:glob` from `collection.json` and configure the bucket scheme it uses.

**Column not found.** Column names are case sensitive. Read `table:columns` and `DESCRIBE`. The geometry column is usually `geometry`, but confirm it. A file without a `bbox` column is GeoParquet 2.x with native statistics.

**Wrong units.** Check the CRS. Reproject with `ST_Transform` or compute in the native CRS.

**Empty map.** The `source-layer` does not match `pmtiles:layers`, or the style's relative `pmtiles://` URL was not resolved against the style file's URL.

**Slow query.** Add `LIMIT`. Filter on `bbox` or an attribute before a spatial predicate. Query one partition first. Check `file:size` on the asset before a full scan.

**Memory pressure.** DuckDB streams. For GeoPandas, pass `columns=` and a `bbox=` filter. For rasters, read windows.
