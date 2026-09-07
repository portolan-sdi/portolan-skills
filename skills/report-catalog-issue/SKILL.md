---
name: report-catalog-issue
description: Report a problem with a catalog registered in the Portolan registry by opening a catalog feedback issue against it.
---

<!-- drift: depends-on: portolan-registry, rashid -->

# Report a Problem with a Registered Catalog

You found something wrong with a Portolan catalog while reading it: a license that misdescribes the data, a collection whose schema contradicts its items, an asset that does not open, a description that documents something else. This skill files that report as a catalog feedback issue on [portolan-registry](https://github.com/portolan-sdi/portolan-registry). The registry mails the person who registered the catalog.

Use it for problems with the data a catalog serves. A problem with the registry itself, its crawl, or its export is an ordinary bug report on the same repo.

## Step 1: Resolve the catalog against the registry

Only a registered catalog can be reported. The registry export lists every one. Each child link carries the registry id.

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

If the script exits 1, stop. The catalog is not in the registry, so there is nobody to notify. Offer the `register-catalog` skill instead.

## Step 2: Run the check that shows the problem

The report is worth nothing without evidence. Run a command against the live catalog and keep both the command and its output.

The validator is the first source of evidence when you hold a local copy of the catalog. It ties each finding to a spec rule id, which the catalog owner can look up. `rashid check` takes a directory, not a URL. `portolan check` gives the same evidence inside a catalog the CLI manages.

```bash
uvx --from 'rashid>=0.1.8,<0.2.0' rashid check ./catalog --summary
```

For a catalog you only reach by URL, fetch the object and show the field. Use `curl` and `jq` for metadata and DuckDB for the data itself.

```bash
curl -fsSL https://data.source.coop/nlebovits/pergamino-ide/catalog.json \
  | jq '{title, stac_extensions}'
```

Never paste output you did not produce. If you cannot reproduce the problem now, say so to the user and stop.

## Step 3: Compose the body

Write in Simplified Technical English. Run `.claude/hooks/writing_check.py --print-rules` in any portolan-sdi repo to read the rules. The `gh issue create` hook blocks a body that fails them. Lead with what is wrong and what should happen instead, in words a reader who did not follow your investigation understands in a minute. Put the evidence after that.

`gh` cannot fill an issue form, so write the headings the form renders. The registry's notifier reads the **Catalog ID** and **Kind of problem** sections by name. Those two spellings must be exact.

<!-- drift-sample: issue -->
````markdown
### Catalog ID

pergamino-ide

### Kind of problem

Schema

### What you found

The root catalog declares no `title` and no `stac_extensions`. Both are MUST fields. The registry lists the catalog by its slug and records no Portolan spec version. Add a `title` and the v0.2.0 schema URI to `stac_extensions`.

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

Kind is one of: Data quality, Schema, Accessibility, Documentation, Other. A missing or wrong metadata field is Schema. A wrong README or description is Documentation. Data quality is for the values in the data files. Accessibility is for an asset that does not open or a host that fails range requests.

One report, one problem. Two problems are two issues. The **How you hit it** block is never empty and never a description of output.

## Step 4: Get approval, then file

Show the user the finished body and the catalog it names. Do not open the issue until they approve it. The report is public and it mails a third party.

```bash
gh issue create \
  --repo portolan-sdi/portolan-registry \
  --label catalog-feedback \
  --title "pergamino-ide: root catalog declares no title or spec version" \
  --body-file body.md
```

The title names the catalog first, then the problem in a few words.

## Step 5: Report back

Give the user the issue URL. Tell them the registry mails the submitter of that catalog. Nothing about the catalog's registration or validity changes. Those come from the nightly crawl, not from feedback.

If the issue comes back with a comment that the catalog is not registered, the id was wrong. Correct the **Catalog ID** section, then ask a maintainer to re-apply the `catalog-feedback` label, which re-sends the notification.
