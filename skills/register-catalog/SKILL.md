---
name: register-catalog
description: Register a Portolan catalog in the Portolan registry by opening a pull request that adds a catalog entry file.
---


<!-- freshness: last-verified: 2026-08-12, maps-to: portolan-sdi/portolan-registry -->

# Register a Catalog in the Portolan Registry

You are helping a user add their Portolan catalog to the [portolan-registry](https://github.com/portolan-sdi/portolan-registry) by opening a pull request. The registry crawls and validates submitted catalogs, then exports their metadata. (Portolan uses STAC to organize its `catalog.json`, but a Portolan catalog is its own thing — don't call it a STAC catalog.)

## Key fact: submitters provide a URL and an address

A registry entry is a single YAML file with two fields, both required:

```yaml
url: https://example.com/stac/catalog.json
submitter_email: you@example.org
```

CI auto-extracts everything else (title, description, bbox, license, counts, etc.) by crawling the catalog. **Never** add other fields or invent metadata. The [schema](https://github.com/portolan-sdi/portolan-registry/blob/main/schema/entry.schema.json) forbids it (`additionalProperties: false`), and an entry missing either required field fails the registry check.

## Step 1: Validate the catalog URL

The URL must end in `catalog.json` and point to a reachable Portolan catalog root.

```bash
curl -fsSL "$CATALOG_URL" | python3 -c "
import sys, json
c = json.load(sys.stdin)
assert c.get('type') == 'Catalog', f\"not a catalog root (type={c.get('type')})\"
print('OK:', c.get('id'), '-', c.get('title', '(no title)'))
"
```

If the URL doesn't end in `catalog.json`, isn't reachable, or isn't a catalog root, stop and tell the user. Do not proceed with an invalid entry.

## Step 2: Derive the slug

The slug is the directory that contains `catalog.json` — the last path segment before the filename. No need to invent one.

```bash
# .../source-coop/nlebovits/ide-pergamino/catalog.json  ->  ide-pergamino
SLUG=$(basename "$(dirname "$CATALOG_URL")")
echo "$SLUG"
```

The file will be `catalogs/$SLUG.yaml`.

## Step 3: Ask the user for the submitter address

Ask the user which address to record, and wait for an answer. Never guess one, and never read it out of git config: the person answerable for a registration is not always the person running the command.

Tell them what the address is for. The registry mails it when the catalog stops validating, and when someone files feedback against it. It stays in `catalogs/` and never reaches `exports/catalogs.json`.

```bash
SUBMITTER_EMAIL="you@example.org"  # supplied by the user
```

## Step 4: Open the PR

Use `gh` to fork (if needed), branch, add the file, and open the PR — all without leaving the working directory:

```bash
# CATALOG_URL, SLUG, and SUBMITTER_EMAIL carry over from the steps above

# Fork (no-op if already forked) and clone to a temp dir
TMP=$(mktemp -d)
gh repo fork portolan-sdi/portolan-registry \
  --clone "$TMP/portolan-registry" --remote
cd "$TMP/portolan-registry"

# Create the entry on a new branch
git checkout -b "add-$SLUG"
printf 'url: %s\nsubmitter_email: %s\n' \
  "$CATALOG_URL" "$SUBMITTER_EMAIL" > "catalogs/$SLUG.yaml"
git add "catalogs/$SLUG.yaml"
git commit -m "Add $SLUG catalog"
git push -u origin "add-$SLUG"

# Open the PR against the upstream repo
gh pr create \
  --repo portolan-sdi/portolan-registry \
  --title "Add $SLUG catalog" \
  --body "Registers \`$CATALOG_URL\` in the Portolan registry."
```

## Step 5: Report

Give the user the PR URL (printed by `gh pr create`) and explain that CI will crawl and validate the catalog, then export its metadata to `exports/catalogs.json` once merged.

## Alternative: web submission

If the user prefers not to use GitHub, the web form at [portolan-sdi.org](https://www.portolan-sdi.org) takes the same two values: the `catalog.json` URL and an email address.
