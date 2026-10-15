---
name: enrich-metadata
description: Fill a collection's metadata.yaml from the open data portal record that lists the same data, when the data came from a source with no metadata of its own, such as a Carto table, a file download, an HDX file, or a Socrata dataset. A script finds the record in a JKAN, CKAN, or Socrata portal. The skill covers the decisions the script cannot make - bundled records, producer versus uploader, copied records, broken licenses, and notices mixed into descriptions.
---

<!-- drift: depends-on: portolan-cli -->

# Enrich metadata from a portal record

`portolan extract arcgis` and `portolan extract wfs` read metadata from the service. A Carto table, a file URL, or a Socrata dataset has no such metadata. The description, license, and producer are in a portal record somewhere else. This skill finds that record and maps its values to the collection's `.portolan/metadata.yaml`.

Set `SKILL` to this skill's directory once per session.

## Step 1: Get the portal's records

| Portal | How to tell | What the script reads |
|---|---|---|
| JKAN | A Jekyll site. The site serves `/datasets.json`. | The site's git repository, cloned |
| CKAN, including HDX | `$BASE/api/3/action/status_show` returns a CKAN version | The CKAN API |
| Socrata | Data URLs look like `/resource/abcd-1234.json` | The views API |

A JKAN site is built from a GitHub repository, and the repository has a `CNAME` file that holds the site's domain. Clone it. The site's `/datasets.json` has no resource URLs, so it cannot match a table.

| JKAN portal | Repository | Record shape |
|---|---|---|
| OpenDataPhilly | `opendataphilly/opendataphilly-jkan` | JKAN default |
| Risk Data Library (`catalog.riskdatalibrary.org`) | `GFDRR/rdl-jkan` | RDLS (`schema: rdls-10`) |

```bash
git clone --depth 1 https://github.com/opendataphilly/opendataphilly-jkan
```

## Step 2: Find the record

Pass a table name for Carto. Pass the exact file URL for a download.

```bash
uv run "$SKILL/scripts/find_record.py" jkan opendataphilly-jkan opa_properties_public
uv run "$SKILL/scripts/find_record.py" jkan rdl-jkan https://data.worldpop.org/GIS/Population/Global_2000_2020/2019/ATA/ata_ppp_2019.tif
uv run "$SKILL/scripts/find_record.py" ckan https://data.humdata.org "$HDX_FILE_URL"
uv run "$SKILL/scripts/find_record.py" ckan "$CKAN_BASE" opa_properties_public
uv run "$SKILL/scripts/find_record.py" socrata data.example.gov abcd-1234
```

An HDX file URL has the form `https://data.humdata.org/dataset/<id>/resource/<id>/download/<file>`. The script reads that dataset directly.

A table matches only where a resource URL names it as a table. That is a Carto SQL `FROM` or `JOIN`, the Carto API explorer anchor, a `filename=` parameter, or a file name such as `opa_properties_public.csv`. A word in a page slug does not match. Exit 0 is one record, 1 is none, 2 is several.

On exit 1, stop and tell the user. Do not fall back to a title search. On exit 2, list the records for the user, who picks one.

## Step 3: Map the record to metadata.yaml

The script returns the record as published. These decisions are yours.

### One record, many tables

When `bundle` is true, the record describes several tables. On OpenDataPhilly, 84 of the 131 Carto tables share a record. "Philadelphia Properties and Assessment History" covers both `opa_properties_public` and `assessments`. The record's title and description name the bundle, not the collection.

Title the collection from `matched_resources`. Take its description from the per-table metadata page when one exists. OpenDataPhilly links one per table, in the resource named "(Metadata)" on `metadata.phila.gov`. Use the record's description only for facts that are true of every table in it.

### Producer, uploader, and maintainer

| Portal | Producer (`providers`, role `producer`) | Not the producer |
|---|---|---|
| JKAN default | `organization` | `maintainer`, which often holds an email address |
| HDX | `dataset_source` | `organization`, which uploaded the data. `maintainer`, which is an HDX user id. |
| RDLS | `creator` | `publisher`, which is the catalog. `contact_point`. |
| Socrata | `attribution` | The dataset owner |

In the HDX Zimbabwe education record, `organization` is "UNESCO" and `dataset_source` is "UNESCO Institute for Statistics (UIS)". The second is the producer. Never write a portal contact into `contact`. `contact` names whoever maintains this catalog.

### Copies of other records

Most Risk Data Library records are copies. 8,312 of 9,666 have `catalog: Humanitarian Data Exchange` and say "automatically extracted from the Humanitarian Data Exchange". Their `links` hold the HDX dataset URL. Read the HDX record and take the description, license, and producer from it:

```bash
curl -fsSL "https://data.humdata.org/api/3/action/package_show?id=worldpop-population-counts-for-antarctica" \
  | jq '.result | {title, dataset_source, license_id, license_url, dataset_date}'
```

Keep from the copy only what the source lacks: `risk_data_type` and the `hazard`, `exposure`, `vulnerability`, or `loss` block. Put those in `processing_notes` or `keywords`.

### Licenses

Portal license strings are often wrong. Write one only after `portolan metadata validate` accepts it. These are values from real records:

| Record says | Write |
|---|---|
| RDLS `CC-BY-4.0`, `CC0-1.0` | That id |
| RDLS `ODbL-1.0/` (1,006 records) | `ODbL-1.0` |
| RDLS `https://example.org/license/unknown`, `Custom`, `GPL` | Nothing. Ask the user. |
| HDX `cc-by-igo` with `license_url` `.../by/3.0/igo/legalcode` | `CC-BY-3.0-IGO` |
| HDX or CKAN `cc-by`, `cc-by-sa` with an unversioned URL | `other` and the URL |
| OpenDataPhilly "Creative Commons 4.0" (URL `/licenses/by/4.0/`) | `CC-BY-4.0` |
| OpenDataPhilly "City of Philadelphia License" | `other` and the terms URL the script returns |
| OpenDataPhilly "License Not Specified" | Nothing. Its URL points to a liability disclaimer. Ask the user. |

Take the version from the license URL when the id has none. Never guess a version.

### Notices in descriptions

Portals put page notices into the description. OpenDataPhilly records open with text such as "Please ignore the 'created by' date below". A notice about the web page is not about the data. Drop it. A notice about the data, such as "values may not reflect the most recent tax year", goes in `known_issues`. Strip HTML and keep the rest as written.

### Dates

HDX `dataset_date` is a range: `[1970-01-01T00:00:00 TO 2019-12-31T23:59:59]`. RDLS has `temporal.start` and `temporal.end`. portolan-cli 0.8.0 has no `metadata.yaml` key for a range. `defaults.temporal` sets one datetime on items that have none. Report the range to the user. Write `defaults.temporal` only for items with no datetime.

### Other fields

| metadata.yaml | JKAN default | HDX or CKAN | RDLS | Socrata |
|---|---|---|---|---|
| `keywords` | `tags` | `tags` | (none) | `tags` |
| `source_url` | the record page | `path` | the source record in `links` | `path` |
| `processing_notes` | (none) | `methodology`, `methodology_other` | `details` | (none) |
| `known_issues` | notices about the data | `caveats` | (none) | (none) |
| `citations` | (none) | (none) | `referenced_by` | (none) |
| `attribution` | (none) | (none) | `attributions` | `attribution` |

HDX `groups` are ISO 3166 alpha-3 country codes, such as `zwe`. They are not keywords.

## Step 4: Get approval and write the file

Show the user the record URL. Then show one table row per field, with the current value, the proposed value, and the record field it came from. Mark each field that a person already wrote as a conflict. Write nothing until the user approves.

Write and apply `metadata.yaml` as `portolan-bootstrap` describes: edit the file, then run `portolan add` with `--force` so the collection reads it. Validate first:

```bash
portolan metadata validate parcels --no-recursive
```
