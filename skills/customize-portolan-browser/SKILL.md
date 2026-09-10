---
name: customize-portolan-browser
description: Adapt a portolan-browser checkout into a publisher-branded interface for one existing Portolan catalog. Inspect the catalog, the browser, and the publisher's site, propose a design, wait for approval, then implement it through browser configuration before site-local code. Use when someone wants a custom, branded, or white-labeled STAC or Portolan browser for a catalog that already exists.
---

<!-- drift: depends-on: portolan-browser, portolan-spec -->

# Customize a Portolan browser for a publisher

This skill adapts an existing browser to one publisher and one catalog. The result reuses
the publisher's visual language and words. It stays a working Portolan browser.

Two browsers already follow this shape. `cholmes/stlouis-data-browser` serves the City of
St. Louis mirror. `cholmes/trimet-data-browser` serves the TriMet mirror. Both keep their
changes in a small set of files so `git pull upstream main` stays cheap.

## Scope

This skill changes the user interface only.

- The catalog is authoritative. Do not edit catalog metadata, styles, legends, thumbnails,
  bounding boxes, source links, converted assets, or data files. Report a catalog defect.
  Do not correct it in the browser.
- Prefer configuration. Change site-local components only when the approved design needs
  behavior that configuration cannot express.
- Upstream work needs separate approval. Report a generic browser defect. Do not edit the
  upstream repository or open an upstream pull request without an explicit request.
- Publication needs separate approval. Do not deploy, publish, push, or open a pull request
  unless the user asks.

## Inputs you must have

Ask for any input you do not have. Do not invent a catalog. Do not pick an unrelated browser
version. Do not infer the publisher from weak evidence.

1. **The catalog.** A local path or a URL to `catalog.json`.
2. **The browser.** A `portolan-browser` checkout or repository, at a known commit.
3. **Publisher evidence.** A reference site, screenshots, or both. Prefer the live site.

## Step 1: Inspect the inputs

Read the catalog structure and several representative collections. Read the browser
configuration surface, the theme, the tests, and `AGENTS.md`. Read the publisher's live site
and take its real CSS values.

Extract only evidence that changes the interface:

- typography, colors, spacing, icons, logos, link treatment, and button states;
- the publisher's words for datasets, rows, departments, topics, tags, downloads, and maps;
- the publisher's page hierarchy and the elements it makes prominent;
- catalog dimensions that hold enough values to support navigation;
- real differences between collections, such as geometry type, extent, size, styles,
  legends, metadata richness, and available assets.

Prefer official CSS, design tokens, and reusable assets. Confirm that you may reuse an asset
before you copy it. Read `reference/catalog-ui-contract.md` for the catalog fields the
browser reads.

## Step 2: Propose the design and stop

Give the user a compact proposal. Wait for approval. Revise the proposal when feedback
changes your reading of the evidence. Do not edit the browser before approval.

`reference/proposal.md` lists the required contents and explains how to keep the
interpretation restrained.

## Step 3: Implement the approved proposal

Work down this ladder. Move to the next layer only when the current one cannot express the
approved requirement.

### Layer 1: the root catalog

The root catalog sets 9 options through a `stac_browser` field, with no rebuild. They are
`apiCatalogPriority`, `cardViewMode`, `crossOriginMedia`, `defaultCollectionSort`,
`defaultItemSort`, `defaultThumbnailSize`, `displayGeoTiffByDefault`, `preferredAssets`, and
`showThumbnailsAsAssets`. Read them. Never write them, because the catalog is immutable here.

### Layer 2: `config.js`

`src/merged-config.js` merges four sources in order. They are `config.js`, the `SB_CONFIG`
file, `SB_*` environment variables, and `window.STAC_BROWSER_CONFIG` from
`public/runtime-config.js`. Command line parameters no longer exist.

The keys a rebrand normally sets are `catalogUrl`, `catalogTitle`, `catalogImage`,
`catalogTitleAfterImage`, `allowExternalAccess`, `allowedDomains`, `enforcedColorMode`,
`supportedLocales`, `pathPrefix`, `historyMode`, `cardViewMode`, `defaultCollectionSort`,
`showKeywordsInCatalogCards`, `preferredAssets`, `socialSharing`, `registryUrl`, and
`footerLinks`. `docs/options.md` documents every key.

A browser that serves one catalog sets `catalogUrl`, and sets `allowExternalAccess` to false.
That choice skips the registry start page.

Develop against a local catalog copy with an environment override:

```bash
npx serve /path/to/catalog --cors -l 8081
SB_catalogUrl=http://localhost:8081/catalog.json pnpm start
```

### Layer 3: words, through the locale files

Terminology is configuration. `src/locales/<code>/custom.json` merges over `texts.json`, so
you override a string without a code change. Rename the STAC nouns there:

```json
{
  "stacCollection": "Dataset | Datasets",
  "stacItem": "Row | Rows"
}
```

Three cautions apply. The `catalogs`, `items`, and `search` groups hold their own worded
copies of the same nouns, so change those keys too. Repeat every override in each locale
listed in `supportedLocales`. Each `footerLinks` label resolves as an i18n key first, and
falls back to the literal text.

### Layer 4: content slots, through widget hooks

`widgets.config.js` maps a hook id to an array of widget definitions. The browser has 23
hooks. `docs/widgets.md` lists them, and `pnpm run docs:hooks` regenerates that list. The
useful ones for a landing page are `root-start`, `root-before-content`, `footer-start`,
`view-catalog-meta-start`, `view-catalog-catalogs-start`, and `view-catalog-items-end`.

`src/widgets/` ships `AlertBox`, `CustomText`, and `Featured`. A definition takes an `id` or
a `component`, plus `props` and an optional `condition`. The `condition` receives
`{ data, state, getters }`. Use it to limit a widget to the root catalog.

Neither existing fork used this layer. Check it before you write a component.

### Layer 5: the theme

`src/theme/variables.scss` holds the palette, the fonts, and the breakpoints as Sass
variables. Put every brand value there. Do not paste a hex literal into a component.

`src/theme/custom.scss` takes anything a variable cannot express. `docs/styling.md` states
that upstream never changes that file, so it is the safe place for an override.

Two facts matter here. `custom.scss` already hardcodes `#202a4f`, `#343e63`, and `#d4d8e8`,
which do not follow `$primary`, so a rebrand must edit them. Styling is build time only. The
`--sb-*` custom properties come from `page.scss`, and `README.md` names a `runtime-style.css`
that the repository does not contain.

`index.html` holds the favicon and the web font link as literal text. Edit the file. Only
`catalogUrl`, `catalogTitle`, and `pathPrefix` are interpolated there.

### Layer 6: site-local components

Add a component only for an approved requirement that the layers above cannot meet. Keep the
change narrow. Preserve normal browser behavior.

Both forks replaced the upstream `.site` header row in `src/StacBrowser.vue` with their own
header component. Each passes the upstream props and events straight through, which keeps
search, the sidebar, authentication, and the locale chooser working. Follow that pattern.

Name a new file for the publisher, such as `StlHeader.vue`. Keep data-derived behavior
generic. Read catalog metadata. Never key behavior to a collection id, and never correct a
particular metadata value in the interface.

Do not build a second frontend. Do not replace portolan-browser with a new application.

### Map constraints

`MAP_CONSTRAINTS` is not an upstream key. Both forks export it from `basemaps.config.js`, and
spread it into the MapLibre constructor from `src/components/maps/MapMixin.js`. Add it the
same way when the design bounds the map to a region.

`basemaps.config.js` exports `configureBasemap(stac)`. This fork uses MapLibre, so a vector
basemap is `{ url, title }` and a raster basemap is
`{ title, raster: true, attribution, tiles: [...] }`. `docs/basemaps.md` still documents the
OpenLayers keys of the parent project, so do not follow it.

## Step 4: Verify representative behavior

A homepage screenshot is not verification. Read `reference/verification.md`. Copy
`reference/verify-template.mjs` into the repository as `verify-<publisher>.mjs` and fill in
the publisher assertions.

The repository holds no screenshot baselines and no mobile viewport, so your script must set
both viewports itself. Run the repository gates as well:

```bash
pnpm run lint
pnpm run test:unit
```

Do not repair a failed check by adding a catalog-specific transformation to the interface.
Classify the failure instead.

## Step 5: Report findings by owner

Give the user three lists. Name the affected route, collection, asset, or interface state for
every finding, and describe what you observed. Do not write "some legends are broken".

1. **Custom browser changes.** What you implemented in this repository.
2. **Catalog findings.** Problems that need a change to metadata, styles, assets, thumbnails,
   data, or tiling, upstream of the interface.
3. **Generic browser findings.** Problems that belong in a `portolan-browser` issue or patch.

The third list has precedent. TriMet's layer order fix now lives upstream as
`StacMapLayer._addLayerBelowLabels`, with `tests/unit/layerOrder.spec.js`. The St. Louis
parquet table pagination now lives upstream as `tests/unit/parquetTable.spec.js`. Report the
finding. Wait for approval before you touch the upstream repository.

## Repository rules

- The toolchain is pnpm. `CONTRIBUTING.md` and `README.md` still say npm, and every workflow
  uses `pnpm install --frozen-lockfile`.
- `portolan-browser` is ISC, not Apache-2.0. A derived browser keeps that license.
- Never edit `CLAUDE.md`, or the `ops-sync` block of `AGENTS.md`. The next sync overwrites
  both. Put repository rules below the block in `AGENTS.md`.
- Record the customization surface in the new repository's `AGENTS.md`. Both forks carry a
  table that maps each file to what it owns.
- Never fabricate a tile URL, a style name, or a hex value. Take each one from the source.
  Mark any value you chose rather than sampled.
