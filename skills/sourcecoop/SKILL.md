---
name: sourcecoop
description: Upload geospatial data to Source Cooperative with proper metadata and READMEs using Portolan CLI.
---

<!-- drift: depends-on: portolan-cli, rashid, portolan-spec, source-coop-cli -->

# Source Cooperative Upload Skill

You are helping a user publish a Portolan catalog to [Source Cooperative](https://source.coop), an open data commons for geospatial data. This skill covers the upload path. To build the catalog from a data source, use the `portolan-bootstrap` skill first, then return here.

The [Portolan spec](https://github.com/portolan-sdi/portolan-spec) is ground truth. The CLI and the validator implement it. Run `portolan <cmd> --help` for the flags of any command below. Do not restate the help text in your answers.

## Prerequisites

Source Cooperative serves its object storage through a data proxy at `data.source.coop`. The [`source-coop` CLI](https://github.com/source-cooperative/source-coop-cli) authenticates you against the proxy and issues temporary S3 credentials. Check for it first:

```bash
source-coop --version
```

Install it with Homebrew, or with the installer script the CLI README documents:

```bash
brew install source-cooperative/tap/source-coop
```

You also need a Source Cooperative account with write access to the repository. The user without access requests it at hello@source.coop.

## Workflow Overview

1. Gather the organization and product names.
2. Log in with `source-coop` and set the remote in `.env`.
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

The proxy addresses the account as the bucket and the repository as the key prefix. Build the remote URL from them:

```
s3://{org}/{product}/
```

## Step 2: Log in and set the remote

`source-coop login` opens a browser for the OAuth2 authorization code flow. It caches the temporary credentials in the OS keyring:

```bash
source-coop login
```

### The remote

The remote is the destination that `portolan push` writes to. The proxy addresses the account as the bucket and the repository as the key prefix. `portolan push` reads the destination from `PORTOLAN_REMOTE` when you give it no argument.

The CLI refuses to store `remote`, `profile`, `region`, and `s3_endpoint` in `.portolan/config.yaml`. That file is pushed with the catalog. Put the remote and the endpoint in `.env` at the catalog root:

```bash
cat > .env << 'EOF'
PORTOLAN_REMOTE=s3://{org}/{product}/
PORTOLAN_S3_ENDPOINT=data.source.coop
EOF

portolan config list
```

`PORTOLAN_S3_ENDPOINT` sends every request to the proxy with path-style addressing. Without it, the CLI resolves the bucket against AWS.

### Credentials for portolan push

`source-coop creds --format env` prints the `export` lines that `portolan push` reads:

```bash
eval $(source-coop creds --format env)
```

The command sets `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and `AWS_SESSION_TOKEN` in the current shell. Run `portolan push` in that same shell. The credentials expire. When an upload fails with `AccessDenied`, run `source-coop login` and the `eval` line again.

### The AWS profile for every other tool

The aws CLI, boto3, rclone, and DuckDB read `~/.aws/config`. Add this profile once to point them at the proxy:

```ini
[profile source]
credential_process = source-coop creds
endpoint_url = https://data.source.coop
```

```bash
aws s3 ls s3://{org}/{product}/ --profile source
```

botocore runs `source-coop creds` on each call, so this profile refreshes itself. Use it to list the prefix and to confirm what the push wrote.

`portolan push` reads the profile name, but it looks only in `~/.aws/credentials` for a key pair. It does not run `credential_process`, and it does not read `endpoint_url`. From `~/.aws/config` it reads only `region`. Do not set `PORTOLAN_PROFILE=source`. A profile name other than `default` also discards the environment credentials that the `eval` line set. The push then finds no key pair and falls back to the instance metadata service at `169.254.169.254`.

portolan-sdi/portolan-cli#872 tracks `credential_process` support in the CLI. Use the `eval` line above until a release includes it.

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

Add `--pmtiles` for vector collections so the catalog provides a render path (PORTO-CORE-065). The CLI writes the PMTiles as a `rel: pmtiles` link with a `pmtiles:layers` array (PORTO-FMT-011) and a default style asset under `styles/`.

## Step 5: write metadata

`portolan metadata init` writes a `.portolan/metadata.yaml` template at every STAC level. `portolan metadata validate` requires `contact.name`, `contact.email`, and `license`. The CLI requires no other field. The spec requires more.

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

Never hand-edit a generated README. Edit `.portolan/metadata.yaml` and regenerate. PORTO-CORE-063 requires four things in the README:

- the title
- the description
- the license
- the data provenance

`AGENTS.md` is not generated from metadata. The CLI scaffolds a stub. Replace the stub at the catalog and at every collection with real content. Describe the data, explain how the files connect, and show queries you ran against the data. Follow the `portolan-bootstrap` skill and `specs/best-practices/documentation.md` for what belongs there.

## Linking to Source Cooperative

Source Cooperative serves the same objects under two hostnames. `source.coop` renders a page a person can read. `data.source.coop` returns raw bytes.

- `source.coop`: the human-facing host. Use it in `metadata.yaml` links, STAC `description` fields, generated READMEs, and issue and pull request bodies.
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

The credentials expired, or they do not cover the prefix.

1. Run `source-coop login`, then `eval $(source-coop creds --format env)` in the shell you push from.
2. Check that `AWS_SESSION_TOKEN` is set in that shell.
3. Check that `PORTOLAN_REMOTE` names the organization and the repository you have write access to.
4. Contact hello@source.coop for access to a different repository.

### Bucket not found

The proxy returns `NoSuchBucket: bucket not found: {org}` when the first path segment is not an account. Check the organization slug in `PORTOLAN_REMOTE`. The remote takes the form `s3://{org}/{product}/`, not the name of an S3 bucket.

### Push conflict

Someone else pushed since your last pull. `portolan pull` requires the remote URL as an argument:

```bash
portolan pull s3://{org}/{product}/
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
PORTOLAN_REMOTE=s3://nlebovits/phl-aerial-imagery/
PORTOLAN_S3_ENDPOINT=data.source.coop
EOF
source-coop login
eval $(source-coop creds --format env)
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
