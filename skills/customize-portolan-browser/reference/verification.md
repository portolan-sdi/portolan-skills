# Verification

A homepage screenshot proves almost nothing. Drive the running site and assert the behavior
the approved design promises.

## Tests in the browser repository

`portolan-browser` contains unit tests and end-to-end tests. It contains **no screenshot
baselines** and **no visual regression suite**. It also tests **no mobile viewport**, because
the `Pixel 5` project is commented out in `playwright.config.js`. Only Desktop Chrome at
1280x720 runs.

So your script must set every viewport itself, and must assert computed values rather than
compare images.

These inherited checks still apply:

```bash
pnpm run lint
pnpm run test:unit
pnpm run docs:lint
```

`pnpm run test:unit` is the fast, high-value check. It covers styles, parquet, map layers, and
the registry.

The inherited `tests/e2e` suite asserts the upstream multi-catalog product. It expects a data
source picker at the root and an API search page. A browser that serves one catalog has
neither. Both existing forks made that workflow manual and left the files unchanged. Merges
from upstream then cause no conflicts in them. Do not rewrite those tests to pass against
your configuration.

## The fork's own test

Copy `verify-template.mjs` into the repository as `verify-<publisher>.mjs`. It drives a real
browser against the running site.

```bash
node_modules/.bin/vite --port 8080 --strictPort &
node verify-<publisher>.mjs
```

The script has these constraints.

**MapLibre renders only when the tab is visible.** Automation that drives a backgrounded tab
shows an inert map that loads no style and requests no tiles. That looks exactly like a
broken basemap. Verify maps through this script, never through a hidden tab.

**A production build strips Vue component internals.** The map probe walks the Vue tree to
reach the MapLibre instance. Run the script against the dev server. To run it against a
build, set `STAC_BROWSER_E2E=true`, which enables the production devtools hook.

**Skip, do not fail, when the catalog is offline.** The branding shell is the fork's promise
either way. Keep the catalog-dependent checks separate, and report them as skipped.

## Select representative states

Repeated checks of similar small polygon layers miss the real problems. Choose a small,
varied set.

Cover these when the catalog contains them:

- point, line, polygon, and tabular collections;
- a large collection and a sparse one;
- a long linear network, and a wide-extent or unusual-extent collection;
- a collection with several styles, and one with one style;
- a partitioned collection whose items have their own styles;
- a categorical raster, and a multi-band scene;
- a collection with rich metadata, and one with thin metadata;
- a populated topic, department, or tag, and an empty one.

## Checks

### Layout

- Desktop and mobile viewports.
- No horizontal overflow. Assert `scrollWidth` equals `clientWidth` on the document element.
- Card and thumbnail framing across different extents.

### Navigation and content

- The homepage hierarchy, the navigation, the filters, and the search.
- Populated and empty topic, department, and tag states.
- Direct links. A filtered view should carry its selection in the URL and reload the same.
- License, provenance, documentation, and download affordances.
- Footer provenance. The footer must link to the data and to the publisher. It must also
  link to the source code.

### Visual

- Assert computed styles, not images. Read `backgroundColor`, `color`, and `fontFamily` from
  the real elements, and compare them to the approved tokens.
- Basemap and data layer order. The stack runs ground, then buildings, then data, then
  labels.
- Style selection and legend rendering, as the catalog provides them.

### Interaction

- Normal, hover, focus, loading, empty, and error states.
- Links must look clickable. Buttons need correct hover and focus states.
- A pressed toggle must be legible. The St. Louis fork fixed an invisible pressed state on
  outline buttons.
- Controls must be legible before interaction.

### Build and performance

- A production build, with `pnpm run build`.
- No console errors. Filter the known noise, such as favicon and `ResizeObserver` messages.
- Browser memory and responsiveness on the largest layer. The browser caps a direct parquet
  read at 10000 rows and 50 MB, and caps COG overlays at 16. A collection near a cap is the
  one to check.

## Report by owner

Sort every finding into one of three lists. Name the affected route, collection, asset, or
interface state, and describe what you observed.

1. **Custom browser changes**, implemented in this repository.
2. **Catalog findings**, which need a change upstream of the interface.
3. **Generic browser findings**, which belong in a `portolan-browser` issue or patch.

Write "the legend panel is empty on `collections/parcels`, because
`styles/default.json` colors the fill with an `interpolate` expression". Do not write "some
legends are broken".

A failed check is never repaired by a catalog-specific transformation in the interface.
Classify it instead.
