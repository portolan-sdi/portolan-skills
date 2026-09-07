---
name: sourcecoop
description: Upload geospatial data to Source Cooperative with proper metadata and READMEs using Portolan CLI.
---

<!-- drift: depends-on: portolan-cli, rashid, portolan-spec -->

# Source Cooperative Upload Skill

You are helping a user publish a Portolan catalog to [Source Cooperative](https://source.coop), an open data commons for geospatial data. This skill covers the upload path. To build the catalog from a data source, use the `portolan-bootstrap` skill first, then return here.

The [Portolan spec](https://github.com/portolan-sdi/portolan-spec) is ground truth. The CLI and the validator implement it. Run `portolan <cmd> --help` for the flags of any command below. Do not restate the help text in your answers.

## Prerequisites

Source Cooperative requires automated access for programmatic uploads. Check for it before anything else:

```bash
grep -l "source" ~/.aws/credentials 2>/dev/null \
  || echo "No source profile found"
portolan config list
```

If no credentials exist, the user with automated access sets them up in Step 2. The user without access requests it at hello@source.coop.

## Workflow Overview

1. Gather the organization and product names.
2. Set credentials in `.env`.
3. Initialize the catalog with a license.
4. Add files.
5. Write metadata: contact, license, providers, `source_url`.
6. Generate READMEs and write `AGENTS.md`.
7. Run the validator locally.
8. Push, then probe the published host.

## Step 1: Gather Information

Ask the user for:

1. The Source Cooperative organization slug (required). Examples: `nlebovits`, `radiant-mlhub`, `vida`.
2. The product name (optional). Defaults to the current directory name.

Build the remote URL:

```
s3://us-west-2.opendata.source.coop/{org}/{product}/
```

## Step 2: Credential Setup

The CLI refuses to store `remote`, `profile`, and `region` in `.portolan/config.yaml`. That file is pushed with the catalog. Put them in `.env` at the catalog root or in `PORTOLAN_REMOTE` and `PORTOLAN_PROFILE` environment variables.

```bash
# ~/.aws/credentials needs a profile named "source-coop"
# with the key pair from the Source Cooperative dashboard.
cat > .env << 'EOF'
PORTOLAN_REMOTE=s3://us-west-2.opendata.source.coop/{org}/{product}/
PORTOLAN_PROFILE=source-coop
EOF

portolan config list
```

Source Cooperative issues temporary credentials. When an upload fails with an auth error, refresh the key pair from the dashboard.

## Step 3: Initialize Catalog

`portolan init` requires a license. With `--auto` and no `--license`, it exits with `PRTLN-VAL004`. Every collection inherits the catalog license, and `portolan add` refuses a collection without one.

```bash
portolan init --title "{product_title}" --auto --license CC-BY-4.0
portolan info
```

`init` writes `catalog.json`, `AGENTS.md`, and `README.md` beside each other, linked with `rel: agents` and `rel: describedby` (PORTO-CORE-005, PORTO-CORE-061, PORTO-CORE-062). It also writes `versions.json`. That file is a CLI artifact, not part of the spec.

## Step 4: add files

Files must sit in collection subdirectories. Files at the catalog root are skipped.

```bash
mkdir -p buildings
mv *.parquet buildings/
portolan add .
```

Add `--pmtiles` for vector collections so the catalog ships a render path (PORTO-CORE-065). The CLI writes the PMTiles as a `rel: pmtiles` link with a `pmtiles:layers` array (PORTO-FMT-011) and a default style asset under `styles/`.

## Step 5: write metadata

`portolan metadata init` writes a `.portolan/metadata.yaml` template at every STAC level. `portolan metadata validate` requires `contact.name`, `contact.email`, and `license`. Nothing else is required by the CLI. The spec requires more.

Fill these fields at every level:

- `contact`: name and email of the maintainer.
- `license`: an SPDX identifier.
- `providers`: at least one `producer`, the organization that created the data (PORTO-CORE-047). The `host` is whoever maintains this catalog, not AWS or Source Cooperative. Leave the host out and the CLI derives it from `contact`. The host needs a `url` or an `email` (PORTO-CORE-051).
- `source_url`: the page the data came from.

Most Source Cooperative uploads are mirrors. The producer and the host differ. For a mirror, the spec requires a `via` link of type `text/html` to the original source (PORTO-CORE-053) and a top-level `updated` field set at each sync (PORTO-CORE-057). The CLI derives both from `providers` and `source_url` when you run `portolan add`. When the source publishes its own STAC catalog, add a `canonical` link to that STAC root as well (PORTO-CORE-054).

Temporal defaults for items without a date live under `defaults.temporal` in the same file. There is no `temporal_extent` key.

Recommended fields: `keywords`, `citation`, `attribution`, `processing_notes`, and `known_issues`.

```bash
portolan metadata init
portolan metadata validate
```

## Step 6: Generate READMEs and write AGENTS.md

```bash
portolan readme
```

Never hand-edit a generated README. Edit `.portolan/metadata.yaml` and regenerate. The README must carry a title, a description, the license, and the data provenance (PORTO-CORE-063).

`AGENTS.md` is not generated from metadata. The CLI scaffolds a stub. Replace the stub at the catalog and at every collection with real content: what the data is, how the files connect, and queries you ran against the data. Follow the `portolan-bootstrap` skill and `specs/best-practices/documentation.md` for what belongs there.

## Linking to Source Cooperative

Source Cooperative serves the same objects under two hostnames. `source.coop` renders a page a person can read. `data.source.coop` returns raw bytes.

- `source.coop`: links in `metadata.yaml`, STAC `description` fields, generated READMEs, issue and pull request bodies.
- `data.source.coop`: STAC asset `href` values, `curl`, DuckDB `read_parquet()`, anything a client resolves programmatically.

```
https://source.coop/{org}/{product}                       # human-facing page
https://data.source.coop/{org}/{product}/catalog.json     # machine-facing bytes
```

## Step 7: Validate before push

An object conforms only when it passes the validator. Run it before every push and fix every error:

```bash
portolan check
```

Read the PTL rule ids in the output. Each one cites the spec requirement it enforces.

## Step 8: Push and probe

```bash
portolan push --dry-run
portolan push --verbose
```

`--workers` sets the number of parallel collections and has no cap. `--concurrency` sets the concurrent uploads within a collection and defaults to 8. On a home network, leave `--adaptive` on and lower `--chunk-concurrency` before you raise anything.

After the push, probe the published host. The host must honor `Range` requests with an accurate HEAD `Content-Length` (PORTO-CORE-043) and send CORS headers on every file (PORTO-CORE-045). `rashid check` takes the local catalog directory, never a URL. The base URL makes the relative hrefs probeable:

```bash
rashid check --live \
  --live-base-url https://data.source.coop/{org}/{product}/ .
```

Then open the catalog in the browser and confirm the default style renders visible data: `https://browser.portolan-sdi.org/#/external/data.source.coop/{org}/{product}/catalog.json`.

## Styles

Styles are collection-level assets with the `style` role and media type `application/vnd.mapbox.style+json` (PORTO-CORE-069, PORTO-FMT-015). With more than one style, exactly one asset carries both `style` and `default` (PORTO-CORE-070). The CLI writes the source URL in each style as `pmtiles://../<file>.pmtiles`. A bare relative path fails to load in MapLibre. There is no `portolan:styles` array in the spec.

Style files upload with `portolan push` like any other asset. For how many styles to write and what they should show, follow the `portolan-bootstrap` skill and `specs/best-practices/styling.md`.

## Troubleshooting

### Access denied or 403 Forbidden

The credentials are invalid, expired, or scoped to another prefix.

1. Check `~/.aws/credentials` under `[source-coop]`.
2. Check that `PORTOLAN_REMOTE` matches the assigned prefix exactly.
3. Refresh the credentials from the Source Cooperative dashboard.
4. Contact hello@source.coop for access to a different prefix.

### No such bucket

The bucket is always `us-west-2.opendata.source.coop`. Check `PORTOLAN_REMOTE` in `.env`.

### Push conflict

Someone else pushed since your last pull. `portolan pull` requires the remote URL as an argument:

```bash
portolan pull s3://us-west-2.opendata.source.coop/{org}/{product}/
portolan push
```

### Slow uploads

Raise `--concurrency` first, then `--workers` when the catalog has many collections. Watch for errors.

### Metadata validation fails

Run `portolan metadata validate`. Add the missing `contact.name`, `contact.email`, or `license` to the named `metadata.yaml`.

### Live probe fails

A CORS or range finding from `rashid check --live` names a host you do not control. Report it to hello@source.coop with the failing URL and the rule id.

## Complete Example

```bash
cd ~/data/phl-aerial-imagery
portolan init --title "Philadelphia Aerial Imagery" --auto --license CC-BY-4.0
cat > .env << 'EOF'
PORTOLAN_REMOTE=s3://us-west-2.opendata.source.coop/nlebovits/phl-aerial-imagery/
PORTOLAN_PROFILE=source-coop
EOF
portolan add . --pmtiles
portolan metadata init
# Edit .portolan/metadata.yaml: contact, license, providers, source_url
portolan metadata validate
portolan readme
# Write AGENTS.md at the catalog and at every collection
portolan check
portolan push --verbose
rashid check --live \
  --live-base-url https://data.source.coop/nlebovits/phl-aerial-imagery/ .
```
