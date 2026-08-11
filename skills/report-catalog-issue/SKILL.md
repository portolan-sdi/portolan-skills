---
name: report-catalog-issue
description: Report a problem with a catalog registered in the Portolan registry by opening a catalog feedback issue against it.
---

<!-- freshness: last-verified: 2026-08-11, maps-to: portolan-sdi/portolan-registry -->

# Report a Problem with a Registered Catalog

You found something wrong with a Portolan catalog while reading it: a license that misdescribes the data, a collection whose schema contradicts its own items, an asset that will not open, a description that documents something else. This skill files that report as a catalog feedback issue on [portolan-registry](https://github.com/portolan-sdi/portolan-registry), which mails whoever registered the catalog.

Use it for problems with **the data a catalog serves**. A problem with the registry itself, its crawl or its export, is an ordinary bug report on the same repo.

## Step 1: Resolve the catalog against the registry

Only a registered catalog can be reported. The registry export lists every one, and each child link carries its id.

```bash
# Accepts either the registry id or the catalog.json URL
NEEDLE="pergamino-ide"

curl -fsSL https://raw.githubusercontent.com/portolan-sdi/portolan-registry/refs/heads/main/exports/catalogs.json \
  | NEEDLE="$NEEDLE" python3 -c "
import json, os, sys
needle = os.environ['NEEDLE'].rstrip('/')
links = [l for l in json.load(sys.stdin)['links'] if l.get('rel') == 'child']
for l in links:
    if needle in (l.get('portolan_registry:id'), l.get('href', '').rstrip('/')):
        print(l['portolan_registry:id'])
        break
else:
    print('NOT REGISTERED. Ids:', ', '.join(l['portolan_registry:id'] for l in links), file=sys.stderr)
    raise SystemExit(1)
"
```

If it prints nothing, stop. The catalog is not in the registry, so there is nobody to notify. Offer the `register-catalog` skill instead.

## Step 2: Run the check that shows the problem

The report is worth nothing without evidence. Run a command against the live catalog and keep both the command and its output. `curl` and `jq` for metadata, DuckDB for the data itself.

```bash
curl -fsSL https://data.source.coop/nlebovits/pergamino-ide/catalog.json \
  | jq '{title, stac_extensions}'
```

Never paste output you did not produce. If you cannot reproduce the problem right now, say so to the user and stop.

## Step 3: Compose the body

`gh` cannot fill an issue form, so write the same headings the form renders. The registry's notifier reads the **Catalog ID** and **Kind of problem** sections by name, so those two spellings must be exact.

````markdown
### Catalog ID

pergamino-ide

### Kind of problem

Data quality

### What you found

The root catalog declares no `title` and no `stac_extensions`, so the registry
lists it by its slug and records no Portolan spec version.

### How you hit it

```shell
$ curl -fsSL https://data.source.coop/nlebovits/pergamino-ide/catalog.json | jq '{title, stac_extensions}'
{
  "title": null,
  "stac_extensions": null
}
```

### Date observed

2026-08-11

### Tool or agent

curl 8.5.0
````

Kind is one of: Data quality, Schema, Accessibility, Documentation, Other.

## Step 4: Hold it to the budget

CI lints every issue body on this repo and labels a failing one `needs-rewrite`. Three rules decide it:

- 200 words outside fenced code blocks, across the whole body.
- Six non-code lines under any one heading. Detail belongs in the block.
- Something pasted in a fence. The **How you hit it** block is what satisfies this, so it is never empty and never a description of output.

One report, one problem. Two problems are two issues.

## Step 5: Get approval, then file

Show the user the finished body and the catalog it names. Do not open the issue until they approve it: the report is public and it mails a third party.

```bash
gh issue create \
  --repo portolan-sdi/portolan-registry \
  --label catalog-feedback \
  --title "pergamino-ide: root catalog declares no title or spec version" \
  --body-file body.md
```

The title names the catalog first, then the problem in a few words.

## Step 6: Report back

Give the user the issue URL. Tell them the submitter of that catalog is mailed automatically, and that nothing about the catalog's registration or validity changes: those come from the nightly crawl, not from feedback.

If the issue comes back with a comment saying the catalog is not registered, the id was wrong. Correct the **Catalog ID** section, then ask a maintainer to re-apply the `catalog-feedback` label, which re-sends the notification.
