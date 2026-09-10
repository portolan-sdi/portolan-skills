# What the interface may read from the catalog

The catalog is authoritative and immutable in this work. The browser reads it. The browser
never corrects it.

This file lists the fields the browser already reads, so you can predict what the interface
shows and classify a defect correctly.

## Styles and legends

The browser reads styles only when `type` is `Collection`. Item maps and search maps get no
styles.

It discovers a style by filtering collection assets on the `style` role. The default style is
the asset that carries both `style` and `default` in its `roles`.
`specs/portolan/core.md` defines this under "Visualization Styles". A legacy
`portolan:styles` manifest merges with the asset scan. It never replaces it.

Accepted media types are `application/vnd.mapbox.style+json` and `application/json`. An
absent type is also accepted, because the role is the normative signal. A style document
whose `version` is not 8 is rejected.

The style title comes from `asset.title`, and falls back to the asset key with a leading
`styles/` removed.

A legend comes from the first `fill` layer's `paint['fill-color']`. The browser understands
two expression forms, `step` and `match`. A plain color string, an `interpolate`, or a `case`
yields no legend, and the panel hides.

**Classify these as catalog findings.** A collection with no style-role asset falls back to
default vector layers. That is the first thing to check when a style appears not to apply. A
legend that does not render because the style uses `interpolate` is a catalog finding too.
Do not add a special case to the interface.

## Tiles and direct rendering

The browser prefers TileJSON, then XYZ, then PMTiles. When any tile asset exists, it drops
the PMTiles assets so one tile set loads.

When any tile asset exists, the browser skips direct GeoParquet rendering. GeoParquet renders
directly only when the collection ships no tiles.

Detection rules:

- PMTiles: the media type contains `application/vnd.pmtiles`, or the href ends in `.pmtiles`.
- XYZ vector: the href holds `{z}`, `{x}`, and `{y}`, and the media type contains
  `application/vnd.mapbox-vector-tile` or `application/x-protobuf`.
- TileJSON: the media type starts with `application/json`, and `roles` holds `tiles`.

A style source resolves against the style document's own href, so
`sources.data.url` is the relative path from `styles/` to the data.

## Size gates

The browser reads declared metadata before it opens a file.

| Field | Use |
| --- | --- |
| `geoparquet:feature_count` | Feature count, checked first |
| `table:row_count` | Feature count fallback |
| `file:size` | Byte size |

The caps are `MAX_ROWS` at 10000 rows, `MAX_MAP_PARQUET_BYTES` at 50 MB, and `COG_LAYER_CAP`
at 8 overlays.

A missing `file:size` or row count makes the browser open the file to find out. **That is a
catalog finding.** Fix it in the catalog, not in the interface.

## Style fields and parquet columns

The browser reads the columns a style needs, and prunes the rest. It recognizes the
two-argument `["get", f]` and `["has", f]` forms, and `{token}` syntax inside `text-field`
and `icon-image`.

It does not recognize the deprecated MapLibre filter form, such as
`["==", "naam", "Utrecht"]`. A style that filters that way loses every feature. **That is a
catalog finding.**

## Thumbnails

Card thumbnails come from assets and links that carry the `thumbnail` role. The relevant
options are `defaultThumbnailSize`, `showThumbnailsAsAssets`, and `crossOriginMedia`.

A thumbnail is a designed view. Frame it for the geometry and the card shape. The framing
must still come from valid catalog information. A thumbnail that is blank, that is stretched,
or that shows a bounding box screenshot is a catalog finding. The `portolan-thumbnails` skill
regenerates them.

## Navigation from metadata

The St. Louis fork derives its topics and departments from the STAC Themes extension. It
reads `themes[].concepts`, filtered by a publisher scheme URI, and it reads `keywords`.

Write accessors that return empty when a field is absent. A section whose data is absent then
does not render. Test that behavior, as `tests/unit/stlHome.spec.js` does.

Never key behavior to a collection id. Never hardcode a correction for one metadata value.

## Options the root catalog sets

The root catalog may set 9 browser options through a `stac_browser` field. They are
`apiCatalogPriority`, `cardViewMode`, `crossOriginMedia`, `defaultCollectionSort`,
`defaultItemSort`, `defaultThumbnailSize`, `displayGeoTiffByDefault`, `preferredAssets`, and
`showThumbnailsAsAssets`.

Read them, because they explain interface behavior you did not configure. Do not write them,
because the catalog is immutable in this work. When one of them is wrong, report it as a
catalog finding.

## How to classify a defect

Ask which artifact you must change to fix the problem.

| You must change | Owner |
| --- | --- |
| A component, the theme, a config key, or a locale string | The custom browser |
| Metadata, a style, an asset, a thumbnail, the data, or the tiles | The catalog |
| Shared browser code that every deployment runs | Upstream portolan-browser |

When a fix needs a catalog-specific branch in the interface, you classified it wrong. The
defect is in the catalog.
