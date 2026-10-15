# Catalog navigation

Include these four links on every catalog, subcatalog, and collection as a publishing convention.

## Link targets

Configure the public JSON base, source repository, issue tracker, hosting home, and browser URL template once. Generate STAC and README links from that configuration. Derive each object's published JSON URL from its path under the public base.

| Target | `rel` | `type` | Scope |
|---|---|---|---|
| This object in the data browser | `alternate` | `text/html` | Its own published JSON URL |
| Source repository | `vcs` | `text/html` | The repository that maintains this metadata |
| Issue tracker | `issues` | `text/html` | That repository's issue tracker |
| Hosting repository home | `about` | `text/html` | The human page for this hosted catalog |

On Source Cooperative, use `https://source.coop/<account>/<repo>` for the hosting home and `data.source.coop` for JSON. Keep `via` for the original data source.

Use the [canonical Portolan browser](https://github.com/portolan-sdi/portolan-ops/blob/main/copy/urls.md) by default. For an HTTPS JSON URL, its external route is:

```text
https://browser.portolan-sdi.org/#/external/<host>/<path-to-json>
```

Remove the initial `https://` and preserve path escaping. Do not encode the whole URL as one path segment. See the pinned browser's [configuration](https://github.com/portolan-sdi/portolan-browser/blob/93406b6/config.js) and [URL conversion](https://github.com/portolan-sdi/portolan-browser/blob/93406b6/src/store/index.js). For a custom browser, accept a publisher-supplied template with a placeholder for the full JSON URL. Its route may differ.

Merge generated entries into `links` without duplicates. Preserve structural links, other HTML alternates, translated catalogs, and existing `about` links. Each browser link must open its own object. Report missing targets rather than inventing URLs.

## README generation

Near each catalog, collection, and repository README title, add Markdown links to the four STAC targets: **Open in data browser · Source repository · Report a problem · Hosting repository**.

Link each listed child to its browser page, derived from its published JSON URL, including nested paths. Keep useful documentation links in a separate column.

The pinned `portolan readme` does not generate these links. Add a repeatable step after it, with source and configuration in the catalog project. Run it after each regeneration and report the gap upstream. Avoid hand-editing generated READMEs. `metadata.yaml` alone cannot produce this output.

## Verify before publication

Generate twice. The second run must produce no diff. Check all four targets, README child links, preserved alternate and structural links, and the browser override.

After publication, open the root, a nested catalog if present, and a collection from their READMEs. Confirm that each browser page opens the intended object and its source, issue tracker, and hosting links resolve.
