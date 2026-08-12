---
name: git-backed-catalog
description: Create, maintain, or contribute to a Portolan catalog whose metadata lives in a git repository, with CI validating every change. Use when someone wants to publish a catalog they can roll back and take pull requests on, or wants to fix metadata in someone else's catalog.
---

<!-- freshness: last-verified: 2026-08-12, maps-to: portolan-sdi/portolan-catalog-template -->

# Git-Backed Portolan Catalogs

A git-backed catalog keeps its metadata in a repository and its data in object
storage. The repository publishes to the bucket; the bucket serves readers.

Three things this buys, and they are why the pattern is worth the setup:

- **Rollback.** A published catalog is one mutable tree. Overwrite a
  `collection.json` with a broken one and the previous version is gone. Git is
  the undo.
- **A gate you can iterate against.** CI runs `rashid` and `stac-check` on
  every pull request. You edit, push, read the findings, fix, and repeat until
  the check is green. Editing straight into a bucket is guessing.
- **A contribution path.** Someone who spots a wrong license can open a pull
  request instead of hunting for an email address.

Background and the tradeoffs are in the
[git-backed catalogs guidance](https://github.com/portolan-sdi/portolan-spec/blob/main/specs/best-practices/git-backed-catalogs.md).

Pick the mode that matches what the user asked for.

## Mode A — Create a new git-backed catalog

Start from the template rather than scaffolding by hand. It ships a stub that
passes `rashid` on the first commit, so CI is green before the user writes
anything.

```bash
gh repo create <owner>/<name> \
  --template portolan-sdi/portolan-catalog-template \
  --public --clone
cd <name>
```

Then work through `SETUP.md` in the new repo. It is a numbered checklist and it
is authoritative; do not improvise around it. In summary:

1. Edit `catalog.publish.yaml`: `write_prefix`, `public_base`, `region`.
2. Edit `catalog/catalog.json`: `id`, `title`, `description`.
3. Rewrite `catalog/README.md` and `catalog/AGENTS.md`.
4. Rewrite the root `README.md`.
5. Add collections under `catalog/`, each with a `child` link from the root.

`SETUP.md` stops at the catalog's own metadata. Add two more links to
`catalog/catalog.json` by hand. The template ships neither, because it cannot
know the repository URL before the repository exists.

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

Use absolute URLs. The repository sits outside the published catalog, so a
relative href resolves against the bucket. `vcs` is the first thing Mode C
looks for. `issues` gives a reader who spots a wrong license somewhere to say
so. Both are a recommended convention rather than a Core requirement, so
`rashid` will not remind you.

Every placeholder is marked `TODO(setup)`. Find what is left with:

```bash
grep -rn "TODO(setup)" . --exclude-dir=.git
```

Two guards will stop you, and both are deliberate:

- `tests/test_setup.py` fails while the repo is **half**-edited. A fully
  untouched template passes, and so does a finished one.
- `tools/publish.py` refuses to upload while a sentinel value survives in
  `catalog.publish.yaml`. It checks before any AWS call, so this fires without
  credentials.

Verify before you tell the user it works:

```bash
python3 tests/run_all.py
python3 tools/publish.py            # dry run; uploads nothing
```

If the user is outside the portolan-sdi organization, follow `SETUP.md` step 10
and delete `.github/workflows/repo-checks.yml` plus the `ops-sync` blocks. Those
enforce that organization's contribution contract and will fail their pull
requests otherwise.

### Adding a collection

Data files never enter git. Build them, upload them to the bucket, and write
STAC that references them by their public URL. The `.gitignore` already blocks
the common formats, so a stray `git add` of a Parquet file is refused.

Item collections that run to thousands of files should be generated, not
committed. Write a STAC-GeoParquet item index to the bucket and point
`collection.json` at that `items.parquet`, so a client reads one index instead
of thousands of item files. Fields of the World does this for roughly 45,000
Sentinel-2 tiles, and `.gitignore` enforces the policy.

Once a collection exists, run the gates before committing. `test_links.py`
catches the most common mistake, which is adding a `child` link before the
directory it points at exists.

## Mode B — Maintain an existing one

The loop is edit, validate, commit, publish.

```bash
python3 tests/run_all.py            # gates first
git add -A && git commit -m "..."
python3 tools/publish.py            # dry run: what would change
python3 tools/publish.py --confirm  # upload; needs AWS credentials
```

Five things worth knowing before you touch someone's catalog:

- **Publishing never deletes.** Removing a file from `catalog/` does not
  unpublish it. Delete the object yourself if that is the intent.
- **If the catalog is generated, edit the generator.** Repos with a `tools/` or
  `scripts/` pipeline rebuild `catalog/` wholesale, so a hand-edit is
  overwritten on the next build. Look for a regeneration test before assuming
  you can edit the tree directly.
- **Do not widen the conformance allow-list to make CI pass.** If
  `tests/test_conformance.py` has an `ACCEPTED` set, adding a rule to it
  silences a real finding. Fix the finding, or record the waiver in
  `docs/conformance.md` with a tracking issue.
- **Content types matter.** After changing how a file type is mapped, publish
  with `--force`. A bucket listing carries no Content-Type, so change detection
  cannot see that a mapping moved.
- **`stac-check` is advisory; `rashid` is the gate.** Some of its
  best-practice notes contradict Portolan deliberately. It recommends a `self`
  link, which Portolan forbids, because a static catalog that hardcodes its own
  location cannot be mirrored or moved. `tests/test_stac_valid.py` prints those
  notes as warnings and does not fail on them. Do not add a `self` link to
  quiet one.

## Mode C — Contribute to someone else's catalog

You have a published `catalog.json` and want to fix something in it.

### Finding the repository

Portolan recommends that a git-backed catalog publish a `vcs` link to its
repository and an `issues` link to its tracker. Check those first. They are a
convention rather than a requirement, and catalogs published before it carry
neither, so fall back to `git:repository` and then to a `host` provider whose
`url` is a repository. The last is the weakest signal, because a provider `url`
means "where this organization can be reached" and a repository there is
indistinguishable from a homepage.

```bash
CATALOG_URL="https://data.source.coop/example/catalog.json"
curl -fsSL "$CATALOG_URL" | python3 -c '
import json, sys
doc = json.load(sys.stdin)

# 1. The recommended link relations. Separate purposes, so read both.
for link in doc.get("links", []):
    if link.get("rel") == "vcs":
        print("vcs link:", link["href"])
    if link.get("rel") == "issues":
        print("issues link:", link["href"])

# 2. A git:repository field. Not a Portolan field, but published in the wild.
if doc.get("git:repository"):
    print("git:repository:", doc["git:repository"])

# 3. A host provider whose url is a repository.
for p in doc.get("providers", []):
    url = p.get("url", "")
    if "host" in p.get("roles", []) and ("github.com" in url or "gitlab" in url):
        print("host provider:", url)
'
```

Against the three published catalogs this was written from, that finds Fields
of the World by its `vcs` link and both TriMet and St. Louis by their `host`
provider.

If none of them hit, read the `description` and the linked `README.md`. TriMet
and Fields of the World both also name their repository in prose, and a catalog
that carries nothing machine-readable may still say it there.

**If you still cannot find it, ask the user.** Do not guess a repository URL
from the catalog id or the organization name. A pull request opened against the
wrong repository wastes a stranger's time.

A validator cannot demand these links, because a published catalog does not say
whether a repository exists, so the fallbacks stay. If the catalog you are
fixing carries no `vcs` or `issues` link, adding both is a good first pull
request. The reasoning is in
[Link a catalog to its repository](https://github.com/portolan-sdi/portolan-spec/blob/main/specs/best-practices/git-backed-catalogs.md#link-a-catalog-to-its-repository).

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

Run the repository's own gates before pushing. A contribution that fails the
maintainer's CI costs them a round trip.

Edit the source, not the output. If the repo has a `tools/` pipeline, your fix
belongs in the generator or in the data it reads, and the catalog change comes
from re-running it.

## Reading a git-backed catalog

Reading one is no different from reading any other Portolan catalog. The
published tree is the same STAC, GeoParquet, COGs, and PMTiles. Use the
`reading-portolan` skill.

The repository adds three things a plain catalog lacks, none of which needs a
skill: `git log` explains why a field changed, a tag or commit gives a fixed
version to read when the published tree is mutable, and a green CI badge means
the metadata passed the validators on that commit.
