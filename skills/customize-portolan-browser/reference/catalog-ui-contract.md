# Catalog fields the interface reads

The catalog is authoritative and immutable in this work. The browser reads it. The browser
never corrects it.

This file lists the fields the browser already reads, so you can predict what the interface
shows and classify a defect correctly.

## Styles and legends

The browser reads styles when `type` is `Collection` or `Feature`. A partitioned collection
puts one style on each item, because each partition has its own range of values. Catalog
maps and search maps get no styles.

It discovers a style by filtering the assets of that collection or item on the `style` role.
The default style is the asset that has both `style` and `default` in its `roles`.
`specs/portolan/core.md` defines this under "Visualization Styles". A legacy
`portolan:styles` manifest merges with the asset scan. It never replaces it.

Accepted media types are `application/vnd.mapbox.style+json` and `application/json`. An
absent type is also accepted, because the role is the normative signal. A style document
whose `version` is not 8 is rejected.

The style title comes from `asset.title`, and falls back to the asset key with a leading
`styles/` removed.

A legend comes from the `fill-color` of a `fill` layer or the `circle-color` of a `circle`
layer. The browser tries the layers that draw at the current zoom first, then the others. It
uses the first layer that gives a legend, and it reads the legend again after each zoom.

The browser understands two expression forms, `step` and `match`. It first resolves a
`["step", ["zoom"], ...]` wrapper to the ramp for the current zoom. A plain color string, an
`interpolate`, or a `case` yields no legend. A swatch that is not a color string also yields
no legend. The panel then hides.

**Classify these as catalog findings.** A collection with no style-role asset falls back to
default vector layers. That is the first thing to check when a style appears not to apply. A
legend that does not render because the style uses `interpolate` is a catalog finding too.
Do not add a special case to the interface.

## Tiles and direct rendering

The browser prefers TileJSON, then XYZ, then PMTiles. When any tile asset exists, it drops
the PMTiles assets so one tile set loads.

When any tile asset exists, the browser skips direct GeoParquet rendering. GeoParquet renders
directly only when the collection has no tile assets.

Detection rules:

- PMTiles: the media type contains `application/vnd.pmtiles`, or the href ends in `.pmtiles`.
- XYZ vector: the href holds `{z}`, `{x}`, and `{y}`, and the media type contains
  `application/vnd.mapbox-vector-tile` or `application/x-protobuf`.
- TileJSON: the media type starts with `application/json`, and `roles` holds `tiles`.

A style source resolves against the style document's own href, so
`sources.data.url` is the relative path from `styles/` to the data.

## Rasters

The browser decodes each COG in the browser, so the STAC metadata alone sets the color of each
pixel. `docs/rasters.md` in the browser gives the order of precedence:

1. The `color_hint` of each entry in `classification:classes` on band 1 of the asset.
2. The first render whose `assets` list holds the asset key.
3. The first declared render, stretched to the band statistics of the asset.
4. The `viridis` ramp.

When one class lacks a readable `color_hint` or a numeric `value`, the whole asset falls
through to the render rules. A categorical raster in the wrong colors, or in `viridis`, has
incomplete class hints or no render. **That is a catalog finding.**

`docs/layers.md` states which rasters an item opens with and how they stack.
`portolan:render_order` declares the stack. The Portolan specification does not define that
field. The browser reads it as a hint. When the default stack is wrong, report that the item
declares no order. Do not reorder layers in the interface.

## Size gates

The browser reads declared metadata before it opens a file.

| Field | Use |
| --- | --- |
| `geoparquet:feature_count` | Feature count, checked first |
| `table:row_count` | Feature count fallback |
| `file:size` | Byte size |

The caps are `MAX_ROWS` at 10000 rows, `MAX_MAP_PARQUET_BYTES` at 50 MB, and `COG_LAYER_CAP`
at 16 overlays. The layer picker states how many raster assets it could not list.

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

Card thumbnails come from assets and links that have the `thumbnail` role. The relevant
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

Do not key behavior to a collection id, or hardcode a correction for one metadata value.

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
