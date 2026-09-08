---
name: git-backed-catalog
description: Create, maintain, or contribute to a Portolan catalog whose metadata is stored in a git repository, with CI that validates each change. Use when someone wants to publish a catalog they can roll back and take pull requests on, or wants to fix metadata in someone else's catalog.
---

<!-- drift: depends-on: portolan-catalog-template, portolan-spec, rashid -->

# Git-Backed Portolan Catalogs

A git-backed catalog keeps its metadata in a repository and its data in object storage. The repository publishes the catalog. The bucket serves readers.

This pattern is useful for three reasons:

* **Rollback.** Git keeps every previous version of the catalog and the changes between them.
* **A validation loop.** CI runs `rashid` on every pull request. Edit, validate, fix, and repeat until the checks pass.
* **A contribution path.** Someone who finds a wrong license can open a pull request instead of hunting for a contact address.

See the [git-backed catalogs guidance](https://github.com/portolan-sdi/portolan-spec/blob/main/specs/best-practices/git-backed-catalogs.md) for the background and tradeoffs. The specification is ground truth. `rashid` implements it.

Pick the mode that matches what the user asked for.

## Mode A: create a new git-backed catalog

This path suits a catalog that takes contributions or needs rollback. If the user wants to convert a data source and publish it to a bucket, use the `portolan-bootstrap` skill instead.

Start from the template. It provides a stub catalog that passes `rashid` on the first commit, so CI is green before the catalog is populated.

```bash
gh repo create <owner>/<name> \
  --template portolan-sdi/portolan-catalog-template \
  --public --clone
cd <name>
```

Then work through `SETUP.md` in the new repository. It is authoritative. Do not improvise around it. Its ten steps are:

1. Point `catalog.publish.yaml` at your storage: `write_prefix`, `public_base`, and `region`.
2. Name the catalog in `catalog/catalog.json`: `id`, `title`, and `description`.
3. Rewrite `catalog/README.md` and `catalog/AGENTS.md`.
4. Rewrite the repository `README.md`.
5. Decide official or mirror. A mirror collection needs `providers` with the `producer` and `host` roles set correctly, a `via` link to the source (PORTO-CORE-053), and `updated` at each sync (PORTO-CORE-057).
6. Add a logo, optionally, as a root `rel: icon` link with an image media type (PORTO-CORE-075).
7. Replace the `TODO(setup)` hrefs in the `vcs` and `issues` links the template provides. Both are absolute URLs, because the repository is outside the published catalog.
8. Add collections.
9. Finish: no `TODO(setup)` remains, `python3 tests/run_all.py` passes, `python3 tools/publish.py` dry-runs clean. Then delete `tests/test_setup.py` and `SETUP.md`.
10. Outside the `portolan-sdi` organization, remove `.github/workflows/repo-checks.yml` and the `ops-sync` blocks.

These two guards stop you, and both are deliberate:

* `tests/test_setup.py` fails while the repository is half-edited. An untouched template passes, and so does a finished one.
* `tools/publish.py` refuses to upload while a sentinel value remains in `catalog.publish.yaml`. It checks before any AWS call, so this works without credentials.

### Declare the current schema version

The template at `ed23c3b` declares `https://schemas.portolan-sdi.org/portolan/v0.1.1/schema.json` in `catalog/catalog.json`. Change it to the v0.2.0 URI before you add anything (PORTO-CORE-006). Every object in the tree declares the same URI (PORTO-CORE-009). A v0.1.1 catalog that carries an absolute `self` link fails validation, because v0.1.1 forbids that link and v0.2.0 recommends it (PORTO-CORE-081).

### Raise the validator floor in the gate

`tests/test_conformance.py` fails when `rashid` is absent or outside its version range. The template hard-codes `MIN_VERSION = (0, 1, 5)` and `SPEC = "rashid>=0.1.5,<0.2.0"`. Raise both to `0.1.8`, which is the first version that accepts a v0.2.0 root `self` link. Install the same version into a repository virtualenv, so the version the tests find is the version CI installs:

```bash
python3 -m venv .venv
.venv/bin/pip install 'rashid>=0.1.8,<0.2.0'
.venv/bin/rashid --version
```

### Adding a collection

Data files do not belong in git. Build them, upload them to the bucket, and write STAC that references them by public URL. The `.gitignore` already blocks common data formats.

Each collection directory contains `collection.json`, `AGENTS.md`, and `README.md` (PORTO-CORE-005). The `AGENTS.md` link is `rel: agents` and the `README.md` link is `rel: describedby`, both `type: text/markdown` (PORTO-CORE-061, PORTO-CORE-062). The root's `child` link has `type: application/json` and a `title` (PORTO-CORE-033, PORTO-CORE-039). An absolute asset href uses `https`, never `s3` (PORTO-CORE-023). Offer the `s3` form through the alternate-assets extension (PORTO-CORE-024).

Items are normative. A collection with more than one raster scene models each scene as an item in its own subdirectory (PORTO-CORE-015, PORTO-CORE-071). Commit that item JSON. A collection with many items also publishes `items.parquet`, registered as a collection asset with role `collection-mirror` (PORTO-FMT-040, PORTO-FMT-041). The mirror is derived from the items. It never replaces item JSON or the collection's `item` links (PORTO-FMT-042). Generate the mirror with `portolan stac-geoparquet`, and keep the generator, not only its output, in the repository.

The single-file rule is the exception: one GeoParquet file or one COG is a collection-level asset with no item (PORTO-CORE-017, PORTO-CORE-072).

Run the gates before committing. `tests/test_links.py` catches a `child` link added before its directory exists.

### Uploading the data

`tools/publish.py` syncs `catalog/` and nothing else. The narrow scope keeps a scratch file out of a public bucket. Do not widen it.

The template provides `tools/upload_data.py` for the data. Set `data_dir` in `catalog.publish.yaml` to the staging directory. The script admits only files under `data_dir` with a publishable suffix, imports its change detection and sentinel guard from `publish.py`, and never deletes. Run it dry first:

```bash
python3 tools/upload_data.py            # dry run
python3 tools/upload_data.py --confirm  # upload; needs AWS credentials
```

Its change detection compares a multipart object by size alone. Pass `--force` after you replace a file with one of the same size.

### CI checks links without the bytes

A fresh clone in CI has the metadata and not the data, so asset hrefs do not resolve there. The template's `ci.yml` sets `CI_LIGHT=1`, and `tests/test_links.py` then exempts asset hrefs with a data suffix. Structural links stay checked. Leave `CI_LIGHT` unset locally, so the full check runs where the bytes are.

## Mode B: maintain an existing catalog

The loop is:

```bash
python3 tests/run_all.py
git add -A && git commit -m "fix: ..."
python3 tools/publish.py             # dry run
python3 tools/publish.py --confirm   # upload; needs AWS credentials
```

These six points matter:

* **Publishing never deletes.** Removing a file from `catalog/` does not remove the object from the bucket. Delete the object separately when that is intended.
* **`portolan push` and `tools/publish.py` do not interoperate.** `portolan push` tracks uploads in `versions.json`, a CLI artifact keyed on sha256. The template's `tools/publish.py` keeps no state and compares local size and MD5 against the bucket listing. Pick one per catalog and say which in the repository's `AGENTS.md`.
* **Edit the generator, not generated output.** If the repository has a `tools/` pipeline, change the source of the generated catalog.
* **Do not widen the conformance allow-list to make CI pass.** Adding a finding to `ACCEPTED` in `tests/test_conformance.py` hides a defect in the catalog. Fix the finding or record a waiver in `docs/conformance.md` with a tracking issue.
* **Content types matter.** After changing a file-type mapping, publish with `--force`. A bucket listing omits `Content-Type`, so change detection does not notice.
* **Links and the publish step.** Keep structural links relative in the tracked tree, so the catalog validates at any path. A published root SHOULD carry an absolute `self` link (PORTO-CORE-081). The template's `publish.py` at `ed23c3b` does not write that link. Add it in the tracked `catalog.json` with the `public_base` URL, or add a rewrite to the publish step.

## Mode C: contribute to someone else's catalog

You have a published `catalog.json` and want to correct something in it.

### Find the repository

Check the root catalog's links. `vcs` names the source repository. `issues` names where to report a problem. Both are best-practice conventions rather than Core requirements, so older catalogs may lack them. If the catalog uses the [STAC VCS Extension](https://github.com/stac-extensions/vcs), the `vcs` link may also carry a branch, commit, or tag.

```bash
curl -fsSL "$CATALOG_URL" | jq -r '.links[] | select(.rel == "vcs" or .rel == "issues") | "\(.rel): \(.href)"'
```

If those links are missing, read the catalog's `description` and `README.md`. Do not guess a repository URL from the catalog id or provider name. If you cannot identify the repository, ask the user.

### Open the pull request

```bash
TMP=$(mktemp -d)
gh repo fork <owner>/<repo> --clone "$TMP/repo"
cd "$TMP/repo"

git checkout -b fix/parcels-license

# make the edit

python3 tests/run_all.py
git add -A
git commit -m "fix: correct the license on the parcels collection"
git push -u origin fix/parcels-license

gh pr create --repo <owner>/<repo> \
  --title "fix: correct the license on the parcels collection" \
  --body-file body.md
```

Run the repository's own checks before pushing. A contribution that fails the maintainer's CI costs them a round trip. Edit the source, not the generated output. A repository in the `portolan-sdi` organization lints the PR body: write `## What changed`, `## Why`, and `## Verification` in Simplified Technical English, and paste the check you ran under Verification.

## Reading a Git-backed catalog

Reading one is no different from reading any other Portolan catalog. Use the `reading-portolan` skill. The repository adds context a published catalog does not: `git log` shows why metadata changed, a tag marks a fixed version, and CI results show whether that version passed validation.
