---
name: git-backed-catalog
description: Create, maintain, or contribute to a Portolan catalog whose metadata lives in a git repository, with CI validating every change. Use when someone wants to publish a catalog they can roll back and take pull requests on, or wants to fix metadata in someone else's catalog.
---

<!-- freshness: last-verified: 2026-08-12, maps-to: portolan-sdi/portolan-catalog-template -->

# Git-Backed Portolan Catalogs

A git-backed catalog keeps its metadata in a repository and its data in object storage. The repository publishes the catalog; the bucket serves readers.

Three things make this pattern useful:

* **Rollback.** Git keeps the previous catalog versions and the changes between them.
* **A validation loop.** CI runs `rashid` and `stac-check` on every pull request. Edit, validate, fix, and repeat until the checks pass.
* **A contribution path.** Someone who finds a wrong license or other metadata error can open a pull request instead of finding a contact address.

The repository is also a useful record of how the catalog was built. Keeping the tools, inputs, tests, and publication configuration alongside the catalog makes the workflow easier to reproduce and improve.

See the [git-backed catalogs guidance](https://github.com/portolan-sdi/portolan-spec/blob/main/specs/best-practices/git-backed-catalogs.md) for the background and tradeoffs.

Pick the mode that matches what the user asked for.

## Mode A — Create a new git-backed catalog

This path keeps catalog metadata in a repository and validates every change in CI, which suits a catalog that takes contributions or needs rollback. If the user instead wants to convert a data source and publish it to a bucket, use the `portolan-bootstrap` skill for that data-first path.

Start from the template rather than scaffolding by hand. It ships with a stub catalog that passes `rashid` on the first commit, so CI can be green before the catalog is populated.

```bash
gh repo create <owner>/<name> \
  --template portolan-sdi/portolan-catalog-template \
  --public --clone
cd <name>
```

Then work through `SETUP.md` in the new repository. It is authoritative; do not improvise around it. In summary:

1. Edit `catalog.publish.yaml`: `write_prefix`, `public_base`, and `region`.
2. Edit `catalog/catalog.json`: `id`, `title`, and `description`.
3. Rewrite `catalog/README.md` and `catalog/AGENTS.md`.
4. Rewrite the root `README.md`.
5. Add collections under `catalog/`, each with a `child` link from the root.

Add repository and issue-tracker links to `catalog/catalog.json`:

```json
{
  "rel": "vcs",
  "href": "https://github.com/<owner>/<name>",
  "title": "Source repository"
},
{
  "rel": "issues",
  "href": "https://github.com/<owner>/<name>/issues",
  "title": "Issue tracker"
}
```

Use absolute URLs. The repository is outside the published catalog, so a relative URL would resolve against the published catalog instead.

If you need to record the version of the catalog that came from the repository, use the [STAC VCS Extension](https://github.com/stac-extensions/vcs) on the `vcs` link. It can record the VCS type, branch, commit, or tag. The extension is still a proposal, so do not assume Portolan requires it.

`vcs` and `issues` are recommended conventions, not Core requirements. `rashid` therefore does not require them.

Every setup placeholder is marked `TODO(setup)`. Find what remains with:

```bash
grep -rn "TODO(setup)" . --exclude-dir=.git
```

Two guards will stop you, and both are deliberate:

* `tests/test_setup.py` fails while the repository is **half**-edited. A fully untouched template passes, and so does a finished one.
* `tools/publish.py` refuses to upload while a sentinel value survives in `catalog.publish.yaml`. It checks before any AWS call, so this works without credentials.

Verify before telling the user the repository works:

```bash
python3 tests/run_all.py
python3 tools/publish.py            # dry run; uploads nothing
```

### Pin `rashid` in a Repository Virtualenv

`tests/test_conformance.py` resolves the validator with `shutil.which("rashid")` and prints `SKIP: rashid is not installed` when it finds nothing. It therefore checks against whatever version happens to be on PATH, while CI installs a pinned one. Both migrations in August 2026 ran locally against a stale 0.1.4, which has no `PTL-LNK-007`, `PTL-LNK-008`, `PTL-LNK-009`, or `PTL-AST-006`, so the local gate passed a catalog the CI gate rejects.

Install the pinned version into a repository virtualenv and pin the same version in `.github/workflows/ci.yml`:

```bash
python3 -m venv .venv
.venv/bin/pip install 'rashid==0.1.6' stac-check
.venv/bin/rashid --version
```

Then run the gates through that interpreter, so the version the tests find is the version you chose.

If the user is outside the `portolan-sdi` organization, follow `SETUP.md` step 10 and remove `.github/workflows/repo-checks.yml` and the `ops-sync` blocks. Those enforce that organization's contribution contract.

### Adding a collection

Data files do not belong in git. Build them, upload them to the bucket, and write STAC that references them by public URL. The `.gitignore` already blocks common data formats, so a stray `git add` of a Parquet file is refused.

Large item collections should be generated rather than committed as thousands of files. Write a STAC-GeoParquet item index to the bucket and point `collection.json` at `items.parquet`, so clients read one index instead of thousands of item files.

Fields of the World uses this approach for roughly 45,000 Sentinel-2 items.

Once a collection exists, run the gates before committing. `test_links.py` catches a common mistake: adding a `child` link before the directory it points to exists.

### Uploading Data That Lives Outside `catalog/`

`tools/publish.py` syncs `publish_dir`, which is `catalog/`, and nothing else. That boundary is what keeps a scratch file out of a public bucket, so do not widen it. Data assets too large for git need a second uploader beside publish.py, writing into the same bucket prefix.

Have that uploader import `load_config`, `split_s3_uri`, `content_type_for`, `remote_index`, `is_unchanged`, and `unedited_sentinels` from `publish.py` rather than reimplementing them. Change detection, content-type mapping, and the sentinel guard then cannot drift between the two paths.

Scope it by path and again by file extension. In the microsoft-ml-road-detections migration in August 2026 the staging tree held 45 GB of GeoJSON that tippecanoe consumes and nobody should download, sitting beside the Parquet partitions and the PMTiles archive that ship. An allow-list of suffixes stays correct when new scratch appears. An exclusion list does not. Print a per-suffix breakdown in the dry run so an over-broad scope shows up before anything uploads.

`tools/upload_data.py` in that repository is a working implementation, at 164 lines.

### CI Is Red on the First Push

`tests/test_links.py` resolves every relative link and asset href against the working tree. A fresh clone in CI has the metadata but not the bytes, because `.gitignore` keeps data out of git, so asset hrefs do not resolve and the gate fails there after passing locally.

Gate the exemption on an environment variable rather than dropping the check. Pergamino's `tests/test_links.py` exempts a fixed tuple of data suffixes when `CI_LIGHT=1` is set, and nothing else. Structural links stay checked in both modes. It counts what it skipped and prints the count with a line telling the reader to run without `CI_LIGHT` locally, so the exemption stays visible instead of becoming a silent hole. Locally that catalog checks 2,175 hrefs. In CI it checks 1,628 and skips 547.

## Mode B — Maintain an existing catalog

The normal loop is:

```bash
python3 tests/run_all.py
git add -A && git commit -m "..."
python3 tools/publish.py             # dry run
python3 tools/publish.py --confirm   # upload; needs AWS credentials
```

Six things matter when maintaining an existing catalog:

* **Publishing never deletes.** Removing a file from `catalog/` does not remove the object from the bucket. Delete the object separately if that is intended.
* **Two publishers exist and they do not interoperate.** `portolan push` tracks what it has uploaded in `versions.json`, keyed on sha256. The template's `tools/publish.py` keeps no state and compares local size and MD5 against the remote listing's size and ETag. The `portolan-thumbnails` skill assumes the first, this skill assumes the second. Pick one per catalog and say which in the repository's own `AGENTS.md`.
* **Edit the generator, not generated output.** If the repository has a `tools/` or `scripts/` pipeline, find the source of the generated catalog before editing `catalog/` directly.
* **Do not widen the conformance allow-list to make CI pass.** If `tests/test_conformance.py` has an `ACCEPTED` set, adding a finding to it hides a real problem. Fix the finding or record a waiver in `docs/conformance.md` with a tracking issue.
* **Content types matter.** After changing a file-type mapping, publish with `--force`. A bucket listing does not contain `Content-Type`, so normal change detection may not notice the change.
* **`stac-check` is advisory; `rashid` is the Portolan gate.** Some `stac-check` recommendations intentionally differ from Portolan. For example, it recommends a `self` link, which Portolan forbids because a static catalog may be mirrored or moved. Do not add a `self` link just to silence the warning.

## Mode C — Contribute to someone else's catalog

You have a published `catalog.json` and want to correct something in it.

### Find the repository

First check the root catalog's links:

* `vcs` identifies the source repository.
* `issues` identifies where to report a problem or propose a change.

If the catalog uses the STAC VCS Extension, the `vcs` link may also carry the repository's branch, commit, tag, or VCS type.

If those links are missing, check the catalog's `description` and `README.md`. Older catalogs may use prose to identify their repository even though this is not machine-readable.

Do not guess a repository URL from the catalog ID or provider name. If you cannot identify the repository, ask the user.

For example:

```bash
CATALOG_URL="https://data.source.coop/example/catalog.json"

curl -fsSL "$CATALOG_URL" | python3 -c '
import json, sys

doc = json.load(sys.stdin)

for link in doc.get("links", []):
    if link.get("rel") == "vcs":
        print("repository:", link["href"])
    elif link.get("rel") == "issues":
        print("issues:", link["href"])
'
```

If the catalog contains no machine-readable repository link, read its README and description before asking the user.

The `vcs` and `issues` convention is not a requirement, so older catalogs may not have either link.

### Opening the pull request

```bash
TMP=$(mktemp -d)
gh repo fork <owner>/<repo> \
  --clone "$TMP/repo" --remote
cd "$TMP/repo"

git checkout -b fix-license-metadata

# make the edit

python3 tests/run_all.py
git add -A
git commit -m "fix: correct the license on the parcels collection"
git push -u origin fix-license-metadata

gh pr create --repo <owner>/<repo> \
  --title "fix: correct the license on the parcels collection" \
  --body "..."
```

Run the repository's own checks before pushing. A contribution that fails the maintainer's CI costs them a round trip.

Edit the source, not the generated output. If the repository has a `tools/` pipeline, make the change in the generator or its inputs and regenerate the catalog.

## Reading a git-backed catalog

Reading one is no different from reading any other Portolan catalog. The published tree is still STAC, GeoParquet, COGs, PMTiles, and other supported assets. Use the `reading-portolan` skill.

The repository adds useful context that a published catalog does not provide:

* `git log` shows why metadata changed.
* A commit or tag identifies a fixed version of the catalog.
* CI results show whether that version passed the repository's validation checks.

## Related guidance

See the [Git-Backed Catalogs best practices](https://github.com/portolan-sdi/portolan-spec/blob/main/specs/best-practices/git-backed-catalogs.md) for the full repository layout, publication, generation, validation, and contribution guidance.

The [STAC VCS Extension](https://github.com/stac-extensions/vcs) is relevant when a catalog needs to describe the specific VCS version from which a catalog, collection, item, or link originated. It is currently a proposal and should not be treated as a Portolan requirement.
