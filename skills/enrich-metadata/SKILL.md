---
name: enrich-metadata
description: Fill a Portolan collection's metadata.yaml from the record that an open data portal publishes for the same dataset. Supports CKAN portals, DCAT data.json files, and Socrata portals. Find the matching record and show the proposed values. Write only the values the user approves, and never replace a value a person wrote. Use when a collection came from a data API, such as Carto, and its title, description, license, or keywords are thin or missing.
---

<!-- drift: depends-on: portolan-cli -->

# Enrich metadata from an open data catalog

The API that serves a dataset rarely describes it. A Carto SQL table, an ArcGIS layer, or a WFS feature type usually has a matching record on the publisher's open data portal. That record contains the description, license, keywords, and publisher that the data API does not provide.

This skill finds that record and copies its values into the collection's `.portolan/metadata.yaml`. portolan-cli then writes them to `collection.json` and the README.

Use `portolan-bootstrap` to build a catalog. Use this skill after `portolan extract` or `portolan add`, when a collection exists and its descriptive metadata is thin.

## Rules

- Show every value before you write it. Write nothing until the user approves. A wrong license is a legal statement, so it never goes in unapproved.
- Fill only empty fields. A field is empty when it has no value, the `TODO: Add value` marker, or a value that portolan-cli derived. Report every other difference as a conflict. The user decides each conflict.
- Put the publisher in `providers` with the `producer` role. Do not put it in `contact`. `contact` is the person who maintains this catalog, and portolan-cli makes it the `host` provider.
- Copy the catalog's text as published. Strip HTML tags and fix whitespace. Do not summarize, translate, or add facts. If the description is poor, say so and let the user edit it.
- Use one catalog record per collection. Do not merge two records into one collection.

## Step 1: Read the current metadata

Read the collection's own file, the merged values it inherits, and the published result:

```bash
COLL=parcels
cat "$COLL/.portolan/metadata.yaml" 2>/dev/null
cat .portolan/metadata.yaml
jq '{id, title, description, license, providers, links: [.links[] | select(.rel == "via" or .rel == "license")]}' "$COLL/collection.json"
```

A collection that has no `.portolan/metadata.yaml` inherits from the catalog root. `title` and `description` do not inherit. Every other key does, and the collection's own value replaces the inherited one.

Sort each field into one of four states:

| State | How to tell | Action |
|---|---|---|
| Empty | Key absent, `""`, or `[]` | Fill |
| Placeholder | `TODO: Add value` | Fill |
| Derived | `title` equals the collection id in title case (`publico_arbolado` gives `Publico Arbolado`). `description` equals the title. | Fill |
| Human | Anything else | Conflict |

`portolan extract` seeds `source_url`, `description`, `keywords`, and `attribution` from the data service. Treat a seeded value as human. The user decides whether the catalog value is better.

## Step 2: Find the catalog

Start from what you know about the source. Read `source_url` in the metadata, the collection's `AGENTS.md`, and the extract report. Ask the user which portal lists the data if none of these names one. A web search for the publisher name and "open data" also finds most portals.

Do not assume a portal's software. Probe it. Run the three probes against the portal's base URL:

```bash
BASE=https://data.example.gov

# CKAN: prints the CKAN version
curl -fsSL "$BASE/api/3/action/status_show" | jq -r '.result.ckan_version'

# DCAT-US data.json: prints the dataset count
curl -fsSL "$BASE/data.json" | jq '.dataset | length'

# Socrata: prints the number of datasets on the domain
curl -fsSL "https://api.us.socrata.com/api/catalog/v1?domains=${BASE#https://}&limit=1" | jq '.resultSetSize'
```

Some CKAN portals mount the API under a path, such as `$BASE/data/api/3/action/`. A Socrata portal also serves `/data.json`. Prefer the Socrata API there, because it carries attribution. ArcGIS Hub sites serve `/data.json` too. The DCAT steps apply to them.

## Step 3: Find the dataset

Match on the data URL first. A catalog record usually lists the data service URL as a resource or a distribution. That match is close to certain. Fall back to the title only when no URL matches.

Use the most specific part of the source URL as the needle. For Carto, use the table name. For ArcGIS, use the service path. For WFS, use the type name. For Socrata, the dataset id is in the URL. `https://data.example.gov/resource/abcd-1234.json` has the id `abcd-1234`.

**CKAN.** Search, then list each candidate with its resource URLs:

```bash
curl -fsSL "$BASE/api/3/action/package_search?q=opa_properties_public&rows=10" \
  | jq '.result.results[] | {name, title, org: .organization.title, resources: [.resources[].url]}'
```

Then fetch the full record by `name`:

```bash
curl -fsSL "$BASE/api/3/action/package_show?id=$NAME" | jq '.result'
```

**DCAT data.json.** The file can hold thousands of records. Filter it in one pass:

```bash
curl -fsSL "$BASE/data.json" | jq --arg n "opa_properties_public" '
  .dataset[]
  | select(any(.distribution[]?; ((.downloadURL // "") + (.accessURL // "")) | contains($n)))'
```

**Socrata.** Fetch the dataset by id. Search the domain when you have no id:

```bash
curl -fsSL "$BASE/api/views/abcd-1234.json"
curl -fsSL "https://api.us.socrata.com/api/catalog/v1?domains=${BASE#https://}&q=parcels&limit=10" \
  | jq '.results[] | {id: .resource.id, name: .resource.name, link}'
```

Domains in Europe use `api.eu.socrata.com` for the search.

Accept a match without asking only when a resource URL contains the needle and exactly one record matches. Otherwise show the user up to five candidates with their titles, publishers, and URLs, and ask which one is correct. If no record matches, say so and stop. Do not fill metadata from a record that is probably the same dataset.

## Step 4: Map the record

Map the record to `metadata.yaml` keys:

| metadata.yaml | CKAN `result` | DCAT dataset | Socrata view |
|---|---|---|---|
| `title` | `title` | `title` | `name` |
| `description` | `notes` | `description` | `description` |
| `keywords` | `tags[].name` | `keyword` | `tags` |
| `license`, `license_url` | `license_id`, `license_title`, `license_url` | `license` (a URL) | `license.name`, `license.termsLink` |
| `providers` (producer) | `organization.title` | `publisher.name` | `attribution`, else ask |
| `attribution` | (none) | (none) | `attribution` |
| `source_url` | `$BASE/dataset/<name>` | `landingPage` | `$BASE/d/<id>` |

Notes on the mapping:

- **Keywords.** Copy them as published. Drop only exact duplicates. `portolan readme` hides keywords that look like codes.
- **Providers.** A producer entry is `name`, `roles`, and `url`. Add `licensor` to the roles when the producer issued the license. If the merged metadata already lists providers, copy the list and add the producer to it. An own `providers` key replaces the inherited list.
- **Contact.** Do not fill `contact` from `maintainer`, `contactPoint`, or the dataset owner. Put a data contact in `known_issues` only if the user asks for it.
- **source_url.** portolan-cli writes it as the `via` link of a mirror. It points to the page a reader goes to for the original. A seeded data API URL is a human value. Report the catalog page as a conflict, and do not replace the seeded URL silently.
- **Temporal coverage.** portolan-cli 0.8.0 has no `metadata.yaml` key for a date range. `defaults.temporal` sets one datetime for items that have none. Report the catalog's temporal coverage in the proposal. Propose `defaults.temporal` only when the collection's items have no datetime, and say that it sets one date, not a range.

### License

Write an SPDX identifier only when the record states the license and its version. Otherwise write `license: other` with `license_url` set to the license text. Never guess a version.

| Record says | Write |
|---|---|
| CKAN `cc-zero`, or a URL under `creativecommons.org/publicdomain/zero/1.0/` | `CC0-1.0` |
| CKAN `odc-pddl` | `PDDL-1.0` |
| CKAN `odc-odbl` | `ODbL-1.0` |
| CKAN `odc-by` | `ODC-By-1.0` |
| A Creative Commons URL with a version, such as `creativecommons.org/licenses/by/4.0/` | That id, such as `CC-BY-4.0` |
| CKAN `cc-by`, `cc-by-sa`, or `uk-ogl` with no version in the title or URL | `other` and the URL |
| A public domain mark, such as `http://www.usa.gov/publicdomain/label/1.0/` | `other` and the URL |
| `notspecified`, or a license with no URL | Nothing. Report it and ask the user. |

A collection inherits the root license when it has none of its own. Write `license` in the collection's file only when the record's license differs from the inherited one.

## Step 5: Show the proposal

Show the matched record first: its title, publisher, and URL. Then show one table with every field:

```
field        current                     proposed                                  action
title        Opa Properties Public       Philadelphia Properties and Assessments   fill (derived)
description  Opa Properties Public       Property characteristics and assessed...  fill (derived)
license      CC0-1.0 (inherited)         other + https://example.org/terms         CONFLICT
keywords     []                          parcels, property, assessments            fill
providers    (none)                      City of Philadelphia [producer, licensor] fill
source_url   https://phl.carto.com/...   https://data.example.gov/dataset/opa      CONFLICT
temporal     n/a                         2018-01-01 to 2026-09-30                  report only
```

Print the full description under the table. Say for each conflict what the current value is and where it came from. Wait for the user to approve the fills and to decide each conflict.

## Step 6: Write and apply

Edit the collection's `.portolan/metadata.yaml` in place. Change only the approved keys. Keep the comments and the key order. Do not round-trip the file through a YAML library that drops comments. Create the file if the collection has none, with only the approved keys.

Validate the file, then apply it. A plain `portolan add` skips unchanged files and does not re-read `metadata.yaml`. `--force` re-reads every file in the collection, so it is slow on a large collection.

```bash
portolan metadata validate parcels --no-recursive
cp parcels/collection.json /tmp/parcels.before.json
portolan add parcels/ --force
portolan readme parcels --no-recursive
```

Compare the two versions of `collection.json`. The title, description, license, providers, `updated`, and the `license` and `via` links can change. The assets and the extent must not change:

```bash
diff <(jq -S '{assets, extent}' /tmp/parcels.before.json) <(jq -S '{assets, extent}' parcels/collection.json)
```

If the assets or the extent changed, tell the user and stop. Restore from version control if they ask.

Run `portolan check` last. Report the rules it still flags that the catalog record could not fill.

## Report

Tell the user:

- the catalog record you used, with its URL
- each field you wrote, and the conflicts they kept
- the fields the record did not have, such as a license with no URL
