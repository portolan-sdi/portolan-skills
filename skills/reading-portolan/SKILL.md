---
name: reading-portolan
description: Use when exploring, querying, analyzing, or visualizing data from a Portolan catalog (STAC-based cloud-native geospatial data). Covers navigating STAC metadata, querying GeoParquet with DuckDB, cross-dataset joins, geospatial analysis, and creating interactive maps with PMTiles/MapLibre/deck.gl/Potree.
---

# Reading Portolan Data

Explore, analyze, and visualize cloud-native geospatial data from Portolan catalogs.

A Portolan catalog is a STAC-based collection of cloud-native geospatial data — GeoParquet files for vectors, COGs for rasters, COPC for point clouds — served as static files from object storage. No API server needed. You query the data directly with DuckDB, read metadata from STAC JSON, and visualize with PMTiles.

**Specification:** Portolan is defined by the [Portolan Spec](https://github.com/portolan-sdi/portolan-spec). For the most up-to-date details on catalog structure, format requirements, versioning, and best practices, read the spec files directly — especially `core.md`, `structure.md`, `versions.md`, and the format-specific docs under `formats/`. This skill summarizes the key points, but the spec is the authoritative source.

## Tools & Installation

Check which tools are available before starting. Install what's missing.

### Required

**DuckDB** — Primary analysis engine. Handles SQL queries, spatial operations, Parquet reads, and HTTP range requests against remote files.

```bash
# Check
duckdb --version

# Install
brew install duckdb          # macOS
pip install duckdb           # Python
```

DuckDB 1.2+ required. 1.3+ recommended for full spatial/CRS support.

### Recommended

**gpio (geoparquet-io)** — Inspect, validate, convert, and extract GeoParquet files.

```bash
# Check
gpio --version

# Install
pipx install --pre geoparquet-io   # Isolated (recommended)
pip install --pre geoparquet-io    # Or with pip
```

**GDAL/OGR** — Read/convert any geospatial format. Useful for format conversion, reprojection, and accessing formats DuckDB can't read natively.

```bash
# Check
ogr2ogr --version

# Install
brew install gdal            # macOS
conda install -c conda-forge gdal  # conda
pip install gdal             # pip (may need system libs)
```

---

## Step 1: Navigate the Catalog

A Portolan catalog is a directory tree with STAC metadata. Start by reading the catalog structure.

### Catalog Layout

```
catalog-root/
├── catalog.json                 # Root STAC Catalog — lists all collections
├── versions.json                # Catalog-level version tracking
└── {collection_id}/
    ├── collection.json          # STAC Collection — metadata, spatial/temporal extent, assets
    ├── versions.json            # Collection version history + checksums
    ├── {data}.parquet           # Vector data (GeoParquet)
    ├── {data}.pmtiles           # Visualization tiles
    ├── llms.txt                 # AI-readable documentation (if present)
    └── README.md                # Human-readable documentation
```

### Reading STAC Metadata

**Start with `catalog.json`** to discover collections:

```bash
# Local catalog
cat catalog.json | python3 -m json.tool

# Remote catalog (e.g., on Source Cooperative or S3)
curl -s https://data.source.coop/user/catalog-name/catalog.json | python3 -m json.tool
```

The catalog's `links` array lists collections (where `rel` is `"child"`). Each link's `href` points to a `collection.json`.

**Read a collection** to understand the dataset:

```python
import json, urllib.request

collection = json.loads(urllib.request.urlopen(
    "https://data.source.coop/user/catalog/collection-name/collection.json"
).read())

# Key fields
print(collection["title"])           # Human-readable name
print(collection["description"])     # What the data is
print(collection["extent"])          # Spatial bbox + temporal range
print(collection["assets"])          # Available files (parquet, pmtiles, etc.)
print(collection.get("item_assets")) # Schema for item-level assets (partitioned datasets)
```

**Important STAC fields for analysis:**
- `assets.data.href` — Path to the GeoParquet file (relative to collection.json)
- `assets.pmtiles.href` — Path to PMTiles visualization file
- `extent.spatial.bbox` — Bounding box `[west, south, east, north]`
- `extent.temporal.interval` — Time range of the data

### Check for llms.txt

Many Portolan collections include an `llms.txt` file with AI-readable documentation about the dataset — column descriptions, usage examples, and context. Always check for it:

```bash
curl -s https://data.source.coop/user/catalog/collection-name/llms.txt
```

---

## Step 2: Query Data with DuckDB

DuckDB reads GeoParquet files directly — local or remote via HTTP. Load the spatial extension for geometry operations.

### Setup

```sql
INSTALL spatial;
LOAD spatial;
INSTALL httpfs;
LOAD httpfs;
```

### Read Local Files

```sql
SELECT * FROM read_parquet('path/to/data.parquet') LIMIT 10;

-- Schema inspection
DESCRIBE SELECT * FROM read_parquet('path/to/data.parquet');

-- Row count
SELECT count(*) FROM read_parquet('path/to/data.parquet');
```

### Read Remote Files

DuckDB supports HTTP range requests — it only downloads the bytes needed:

```sql
SELECT count(*)
FROM read_parquet('https://data.source.coop/user/catalog/collection/data.parquet');

-- S3
SELECT *
FROM read_parquet('s3://bucket/catalog/collection/data.parquet')
LIMIT 10;
```

For S3, configure credentials:
```sql
SET s3_region = 'us-west-2';
-- For public data, no credentials needed if bucket allows anonymous access
SET s3_access_key_id = '';
SET s3_secret_access_key = '';
```

### Common Analytical Queries

**Counting and aggregation:**
```sql
-- How many features?
SELECT count(*) FROM read_parquet('data.parquet');

-- Group by a category
SELECT category, count(*) as n
FROM read_parquet('data.parquet')
GROUP BY category
ORDER BY n DESC;

-- Top N by a numeric field
SELECT name, height
FROM read_parquet('buildings.parquet')
ORDER BY height DESC
LIMIT 5;
```

**Filtering:**
```sql
-- By attribute
SELECT * FROM read_parquet('data.parquet')
WHERE status = 'active' AND year >= 2020;

-- By bounding box (spatial filter)
SELECT * FROM read_parquet('data.parquet')
WHERE ST_Intersects(
    geometry,
    ST_MakeEnvelope(5.0, 52.0, 6.0, 53.0)
);
```

### Geospatial Analysis

```sql
LOAD spatial;

-- Area calculation (use ST_Area on projected geometries)
SELECT name, ST_Area(geometry) as area_m2
FROM read_parquet('polygons.parquet')
ORDER BY area_m2 DESC
LIMIT 10;

-- Distance between features
SELECT a.name, b.name, ST_Distance(a.geometry, b.geometry) as dist
FROM read_parquet('points_a.parquet') a
CROSS JOIN read_parquet('points_b.parquet') b
WHERE ST_Distance(a.geometry, b.geometry) < 1000;

-- Spatial join — which polygon contains each point?
SELECT p.name as point_name, poly.name as region
FROM read_parquet('points.parquet') p
JOIN read_parquet('regions.parquet') poly
  ON ST_Within(p.geometry, poly.geometry);

-- Buffer and intersect
SELECT a.name, count(*) as nearby_count
FROM read_parquet('parks.parquet') a
JOIN read_parquet('buildings.parquet') b
  ON ST_Intersects(ST_Buffer(a.geometry, 500), b.geometry)
GROUP BY a.name;
```

### Cross-Dataset Joins

One of the most powerful features — join datasets across collections in the same catalog:

```sql
-- Example: Which national park has the most buildings?
SELECT
    parks.name as park_name,
    count(*) as building_count
FROM read_parquet('national-parks/national-parks.parquet') parks
JOIN read_parquet('buildings/buildings.parquet') buildings
    ON ST_Within(buildings.geometry, parks.geometry)
GROUP BY parks.name
ORDER BY building_count DESC;

-- Example: Which park has the most monuments?
SELECT
    parks.name as park_name,
    count(*) as monument_count
FROM read_parquet('national-parks/national-parks.parquet') parks
JOIN read_parquet('monuments/monuments.parquet') monuments
    ON ST_Within(monuments.geometry, parks.geometry)
GROUP BY parks.name
ORDER BY monument_count DESC;
```

For very large datasets, spatial joins can be slow. Strategies:
1. **Filter first**: Reduce rows with WHERE clauses or bbox filters before joining
2. **Use bbox columns**: If the parquet has bbox covering columns, DuckDB can use them for predicate pushdown
3. **Materialize subsets**: `CREATE TABLE subset AS SELECT ... WHERE ...` then join the subset

### Partitioned Datasets

When a collection has multiple parquet files (partitioned datasets >2GB), read them with a glob:

```sql
-- Read all partitions
SELECT * FROM read_parquet('buildings/*.parquet') LIMIT 10;

-- Count across all partitions
SELECT count(*) FROM read_parquet('buildings/*.parquet');

-- Remote glob (S3)
SELECT count(*)
FROM read_parquet('s3://bucket/catalog/buildings/*.parquet');
```

### Export Results

```sql
-- To GeoParquet
COPY (SELECT * FROM read_parquet('data.parquet') WHERE ...)
TO 'output.parquet' (FORMAT PARQUET, COMPRESSION ZSTD);

-- To GeoJSON (for small datasets / web use)
COPY (SELECT * FROM read_parquet('data.parquet') WHERE ...)
TO 'output.geojson' WITH (FORMAT GDAL, DRIVER 'GeoJSON');

-- To CSV (drops geometry)
COPY (SELECT name, value FROM read_parquet('data.parquet'))
TO 'output.csv' (HEADER, DELIMITER ',');
```

---

## Step 3: Inspect with gpio

Use gpio for quick file inspection without writing SQL:

```bash
# File overview
gpio inspect data.parquet

# Detailed stats (row count, bbox, geometry types, CRS, column stats)
gpio inspect stats data.parquet

# Validate cloud-native compliance
gpio check all data.parquet

# Extract a spatial subset
gpio extract data.parquet subset.parquet --bbox "5.0,52.0,6.0,53.0"

# Extract by attribute
gpio extract data.parquet subset.parquet --where "status = 'active'"
```

---

## Step 4: Convert to Legacy Formats with GDAL/OGR

When users need data in traditional GIS formats (Shapefile, GeoPackage, GeoJSON, GeoTIFF, etc.), use GDAL/OGR to convert from Portolan's cloud-native formats.

### Vector Conversion (GeoParquet to legacy)

```bash
# To Shapefile
ogr2ogr output.shp data.parquet

# To GeoPackage
ogr2ogr output.gpkg data.parquet

# To GeoJSON
ogr2ogr output.geojson data.parquet

# To GeoPackage with reprojection
ogr2ogr -t_srs EPSG:4326 output.gpkg data.parquet

# Convert a spatial subset
ogr2ogr -spat 5.0 52.0 6.0 53.0 output.gpkg data.parquet

# Convert with attribute filter
ogr2ogr -where "status = 'active'" output.gpkg data.parquet
```

### Raster Conversion (COG to legacy)

```bash
# COG to standard GeoTIFF
gdal_translate input.tif output.tif -co TILED=NO

# COG to PNG (for preview)
gdal_translate -of PNG -scale input.tif output.png

# Reproject a raster
gdalwarp -t_srs EPSG:4326 input.tif output.tif

# Clip raster to extent
gdalwarp -te 5.0 52.0 6.0 53.0 input.tif output.tif
```

### Reading Remote Files

Use GDAL virtual filesystem prefixes for remote data:

```bash
# HTTP/HTTPS
ogrinfo /vsicurl/https://data.source.coop/user/catalog/collection/data.parquet
ogr2ogr output.gpkg /vsicurl/https://example.com/data.parquet

# S3
ogr2ogr output.gpkg /vsis3/bucket/catalog/collection/data.parquet

# Google Cloud Storage
ogr2ogr output.gpkg /vsigs/bucket/path/data.parquet

# Azure Blob Storage
ogr2ogr output.gpkg /vsiaz/container/path/data.parquet
```

---

## Step 5: Visualize

### Interactive Maps with PMTiles

PMTiles are the preferred visualization format in Portolan catalogs. They enable serverless map rendering via HTTP range requests.

**MapLibre GL JS (HTML):**

```html
<!DOCTYPE html>
<html>
<head>
    <script src="https://unpkg.com/maplibre-gl/dist/maplibre-gl.js"></script>
    <link href="https://unpkg.com/maplibre-gl/dist/maplibre-gl.css" rel="stylesheet" />
    <script src="https://unpkg.com/pmtiles/dist/pmtiles.js"></script>
    <style>body { margin: 0; } #map { width: 100%; height: 100vh; }</style>
</head>
<body>
<div id="map"></div>
<script>
const protocol = new pmtiles.Protocol();
maplibregl.addProtocol("pmtiles", protocol.tile);

const map = new maplibregl.Map({
    container: "map",
    style: {
        version: 8,
        sources: {
            data: {
                type: "vector",
                url: "pmtiles://https://data.source.coop/user/catalog/collection/data.pmtiles"
            }
        },
        layers: [{
            id: "data-layer",
            type: "fill",
            source: "data",
            "source-layer": "data",  // Check PMTiles metadata for layer name
            paint: {
                "fill-color": "#3388ff",
                "fill-opacity": 0.6,
                "fill-outline-color": "#2266cc"
            }
        }]
    }
});

map.addControl(new maplibregl.NavigationControl());
</script>
</body>
</html>
```

**Adapt the URL** to wherever the PMTiles file is hosted.

### deck.gl (for large datasets / 3D)

deck.gl is better for very large datasets, 3D visualization, and analytical overlays:

```html
<!DOCTYPE html>
<html>
<head>
    <script src="https://unpkg.com/deck.gl@latest/dist.min.js"></script>
    <script src="https://unpkg.com/maplibre-gl/dist/maplibre-gl.js"></script>
    <link href="https://unpkg.com/maplibre-gl/dist/maplibre-gl.css" rel="stylesheet" />
    <style>body { margin: 0; } #map { width: 100%; height: 100vh; }</style>
</head>
<body>
<div id="map"></div>
<script>
const deckgl = new deck.DeckGL({
    container: "map",
    mapStyle: "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
    initialViewState: {
        longitude: 5.5,
        latitude: 52.0,
        zoom: 7,
        pitch: 45
    },
    controller: true,
    layers: [
        new deck.GeoJsonLayer({
            id: "data",
            data: "output.geojson",  // Or use MVTLayer for PMTiles
            filled: true,
            getFillColor: [51, 136, 255, 160],
            getLineColor: [34, 102, 204],
            getLineWidth: 1,
            pickable: true
        })
    ]
});
</script>
</body>
</html>
```

For PMTiles with deck.gl, use `MVTLayer`:

```javascript
new deck.MVTLayer({
    id: "pmtiles-layer",
    data: "https://data.source.coop/user/catalog/collection/data.pmtiles",
    getFillColor: [51, 136, 255, 160],
    getLineColor: [34, 102, 204],
    pickable: true
})
```

### COG (Cloud-Optimized GeoTIFF) Visualization

For raster data served as COGs, use Titiler or a client-side renderer:

```javascript
// With MapLibre + COG protocol
// Requires a tile server like Titiler, or use client-side rendering with geotiff.js
const map = new maplibregl.Map({ /* ... */ });
map.addSource("raster", {
    type: "raster",
    tiles: ["https://titiler.xyz/cog/tiles/{z}/{x}/{y}?url=https://path/to/data.tif"],
    tileSize: 256
});
map.addLayer({ id: "raster-layer", type: "raster", source: "raster" });
```

### Point Clouds with COPC & Potree

For COPC (Cloud-Optimized Point Cloud) data:

```html
<!-- Potree viewer for COPC -->
<!DOCTYPE html>
<html>
<head>
    <script src="https://cdn.jsdelivr.net/npm/potree-core/dist/potree.js"></script>
    <style>body { margin: 0; } #viewer { width: 100%; height: 100vh; }</style>
</head>
<body>
<div id="viewer"></div>
<script>
// Potree supports COPC natively
// Point to your COPC file URL
const viewer = new Potree.Viewer(document.getElementById("viewer"));
Potree.loadPointCloud("https://path/to/data.copc.laz", "pointcloud", (e) => {
    viewer.scene.addPointCloud(e.pointcloud);
    viewer.fitToScreen();
});
</script>
</body>
</html>
```

---

## Workflow: Answering Questions About a Catalog

When a user points you at a Portolan catalog and asks questions:

1. **Crawl the catalog tree** — Start with `catalog.json`. Follow all `links` where `rel` is `"child"`. Children can be either **collections** (have `type: "Collection"`) or **sub-catalogs** (have `type: "Catalog"`). Sub-catalogs contain their own `links` to more children — recurse until you've found all collections. Build a full inventory of available datasets before answering.

   ```
   catalog.json
   ├── link (child) → rijkswaterstaat/catalog.json    # sub-catalog
   │   ├── link (child) → tunnels/collection.json     # collection
   │   └── link (child) → bridges/collection.json     # collection
   ├── link (child) → kadaster/catalog.json            # sub-catalog
   │   └── link (child) → bag_light/collection.json   # collection
   └── link (child) → parks/collection.json            # collection (direct child)
   ```

2. **Read `collection.json`** for relevant collection(s) — understand fields, spatial/temporal extent, and assets
3. **Check for `llms.txt`** in each collection — get AI-readable documentation about columns and usage
4. **Identify the right parquet file(s)** from the collection assets (look for `assets.data.href` or browse asset entries with `type: "application/vnd.apache.parquet"`)
5. **Query with DuckDB** — answer the question with SQL
6. **For cross-dataset questions** — join across collection parquet files using spatial predicates

### Example: "How many national parks are in the Netherlands?"

```sql
LOAD spatial;
SELECT count(*) FROM read_parquet('national-parks/national-parks.parquet');
```

### Example: "What are the tallest 5 buildings?"

```sql
SELECT identificatie, bouwjaar, oppervlakte_max
FROM read_parquet('kadaster/bag_light/bag-light.parquet')
ORDER BY oppervlakte_max DESC
LIMIT 5;
```

### Example: "Which national park has the most buildings?"

```sql
LOAD spatial;

SELECT
    np.name as park_name,
    count(*) as building_count
FROM read_parquet('national-parks/national-parks.parquet') np
JOIN read_parquet('kadaster/bag_light/bag-light.parquet') b
    ON ST_Within(b.geom, np.geometry)
GROUP BY np.name
ORDER BY building_count DESC
LIMIT 10;
```

For cross-dataset joins on large datasets, filter spatially first to reduce the join cardinality.

---

## Tips

- **Always `LOAD spatial;`** before any geometry operations in DuckDB
- **Check the CRS** — if data is in a projected CRS (like EPSG:28992 for Netherlands), distance/area calculations are in meters. If in EPSG:4326, they're in degrees.
- **Use `DESCRIBE`** to inspect column names and types before querying
- **bbox covering** in GeoParquet enables predicate pushdown — DuckDB skips row groups outside your spatial filter automatically
- **For very large joins**, materialize filtered subsets first rather than joining full tables
- **Remote reads are fast** — DuckDB's HTTP range request support means you don't need to download entire files
- **`--json` output** from portolan and gpio commands is useful for programmatic catalog exploration
- **Partitioned data** — use glob patterns (`*.parquet`) to read all partitions as one table
