# Catalog navigation

Give readers a way to open the data in a browser, find its source repository, report a problem, and visit its hosting page. Include the four links below on every catalog, subcatalog, and collection.

## Link targets

Keep the public catalog base URL, source repository, issue tracker, hosting page, and browser URL template in the catalog project's configuration. Use that configuration to generate both STAC and README links. For each object, build the published JSON URL from its path under the public base URL.

| Target | `rel` | `type` | Scope |
|---|---|---|---|
| This object in the data browser | `alternate` | `text/html` | Its own published JSON URL |
| Source repository | `vcs` | `text/html` | The repository that maintains this metadata |
| Issue tracker | `issues` | `text/html` | That repository's issue tracker |
| Hosting page | `about` | `text/html` | The page readers visit for this hosted catalog |

On Source Cooperative, use `https://source.coop/<account>/<repo>` for the hosting page and `data.source.coop` for JSON files. Reserve `via` links for the original data source.

Unless the publisher provides another browser, use the [canonical Portolan browser URL](https://github.com/portolan-sdi/portolan-ops/blob/main/copy/urls.md). To open a published JSON file, use this route:

```text
https://browser.portolan-sdi.org/#/external/<host>/<path-to-json>
```

Remove `https://` from the JSON URL and preserve any escaping in its path. Do not encode the entire URL as one path segment. The pinned browser's [route configuration](https://github.com/portolan-sdi/portolan-browser/blob/93406b6/config.js) and [URL conversion code](https://github.com/portolan-sdi/portolan-browser/blob/93406b6/src/store/index.js) define this format. If the publisher uses a custom browser, ask for its URL template with a placeholder for the full JSON URL.

When you generate `links`, update the entries your generator owns without adding duplicates or removing existing links. Preserve structural links, other HTML alternates, translated catalogs, and existing `about` links. Each browser link must open that specific catalog or collection. If a target is missing, report it rather than inventing a URL.

## README generation

Near each catalog, collection, and repository README title, add Markdown links to the four STAC targets: **Open in data browser · Source repository · Report a problem · Hosting repository**.

When a README lists child catalogs or collections, link each entry to that child's browser page. Build the link from its published JSON URL, including any nested paths, and keep useful documentation links in a separate column.

The pinned `portolan readme` does not generate these links, and `metadata.yaml` alone cannot add them. Add a generation step after `portolan readme` instead of editing generated READMEs by hand. Keep its source and configuration in the catalog project, run it after each regeneration, and report the missing feature upstream.

## Verify before publication

Run the generator twice and confirm that the second run makes no changes. Check all four link targets and the browser link for each child listed in a README, including any custom browser URL. Confirm that existing alternate and structural links survive regeneration.

After publication, follow the README links to the root and a collection. If the catalog has nested catalogs, open one of those too. Confirm that each browser page shows the intended object and that its repository, issue tracker, and hosting links work.
