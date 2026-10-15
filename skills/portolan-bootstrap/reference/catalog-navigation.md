# Catalog navigation

Every catalog and collection must carry the four links below. Apply the same rule to subcatalogs. These skills use the link set as a publishing convention.

## Link targets

Record the public catalog base URL, source repository URL, issue tracker URL, hosting home URL, and browser URL template in the catalog project's configuration. Reuse them for STAC and README generation. Resolve each object's published JSON URL from its path under the public base, not from a local path or its id.

| Target | `rel` | `type` | Scope |
|---|---|---|---|
| This object in the data browser | `alternate` | `text/html` | Its own published JSON URL |
| Source repository | `vcs` | `text/html` | The repository that maintains this metadata |
| Issue tracker | `issues` | `text/html` | That repository's issue tracker |
| Hosting repository home | `about` | `text/html` | The human page for this hosted catalog |

On Source Cooperative, the hosting home is `https://source.coop/<account>/<repo>`. The public JSON base uses `data.source.coop`. Keep `via` for the original data source. Add the hosting home as a separate link.

Use the [canonical Portolan browser](https://github.com/portolan-sdi/portolan-ops/blob/main/copy/urls.md) by default. For an HTTPS JSON URL, its external route is:

```text
https://browser.portolan-sdi.org/#/external/<host>/<path-to-json>
```

Remove the initial `https://` from the JSON URL. Preserve path escaping. Do not percent-encode the entire URL as one path segment. The pinned browser's [configuration](https://github.com/portolan-sdi/portolan-browser/blob/93406b6/config.js) and [URL conversion](https://github.com/portolan-sdi/portolan-browser/blob/93406b6/src/store/index.js) define this route. A custom browser can use another route: accept a publisher-supplied template with a placeholder for the object's full JSON URL. Do not assume the custom browser uses `/external/`.

The FIRMS root links would include:

```json
[
  {
    "rel": "alternate",
    "type": "text/html",
    "title": "Open in data browser",
    "href": "https://browser.portolan-sdi.org/#/external/data.source.coop/portolan-mirrors/firms-catalog/catalog.json"
  },
  {
    "rel": "vcs",
    "type": "text/html",
    "title": "Source repository",
    "href": "https://github.com/portolan-mirrors/firms-catalog"
  },
  {
    "rel": "issues",
    "type": "text/html",
    "title": "Report a problem",
    "href": "https://github.com/portolan-mirrors/firms-catalog/issues"
  },
  {
    "rel": "about",
    "type": "text/html",
    "title": "Hosting repository",
    "href": "https://source.coop/portolan-mirrors/firms-catalog"
  }
]
```

Merge these entries into `links`. Preserve structural links, other HTML alternates, translated catalogs, and existing `about` links. Update entries owned by this generation step without duplicates on repeated runs. A collection's browser link must open that collection, not the root. If the catalog has no source repository, report the missing target. Never invent a URL.

## README generation

Place a compact link block near the title of each catalog and collection README: **Open in data browser · Source repository · Report a problem · Hosting repository**. Make each label a Markdown link to the corresponding STAC target. Include the block in the repository README too, so a visitor can open the published data.

When a README lists child collections or subcatalogs, link each row or entry to that child's browser page. Retain useful documentation links in a separate column. Derive the browser target from the child's published JSON URL, including nested paths.

The pinned `portolan readme` does not emit this block or child browser links. In CLI projects, add a repeatable generation step after `portolan readme` for the navigation links and README additions. Keep its configuration and source in the catalog project. Run it after each regeneration, and record the generator gap upstream. Do not hand-edit generated READMEs or claim that metadata.yaml alone enables this output.

## Verify before publication

Generate twice and require no diff on the second run. Check every catalog and collection for all four targets, and every README child entry against that child's browser target. Check that existing alternate and structural links survive regeneration. Test the configured browser override too.

After publication, open the root, a nested catalog when present, and a collection from their README links. Confirm that each browser page loads the intended object and that its source, issue tracker, and hosting links resolve. A schema validation pass alone does not check these destinations.
