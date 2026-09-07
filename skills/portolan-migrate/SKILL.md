---
name: portolan-migrate
description: Bring an existing non-compliant catalog or published dataset into Portolan compliance without rebuilding it. Audit what is there, decide whether to patch or re-extract, repair metadata, styles and data, prove conformance, then republish and prune what went stale. Use when a catalog already exists and falls short of the spec, when a dataset was published before Portolan, or when someone says a catalog needs migrating, upgrading, or fixing.
---

<!-- drift: depends-on: portolan-cli, rashid, portolan-spec, portolan-catalog-template -->
<!-- Defects and counts come from two migrations run in August 2026:
     pergamino-ide-catalog (183 collections, WFS/GeoServer) and
     microsoft-ml-road-detections (one collection, 235 partitions, 12 GB). -->

# Portolan Migrate

Something already exists. A catalog built by an older toolchain, a folder of GeoParquet with a README, a Source Cooperative product that predates Portolan. It has users, download counts, and URLs other people have written down. Your job is to bring it into compliance without breaking any of that.

Use `portolan-bootstrap` when there is no catalog yet and you are converting a data source. Use this skill when the artifact exists and must survive.

## Preserve What Already Exists

The data is innocent until a named requirement proves otherwise. That single rule decides most of what follows.

Do not re-download upstream, reconstruct from source, filter rows, rename meaningful fields, or change CRS, geometry, or partitioning because a rewrite would be tidier. When a rule forces a change, quantify it. Report before and after row count, file count, and size. Say which rule forced it, and say whether it is reversible:

```
files       235 -> 235
rows        256,555,010 -> 256,555,010
length      54,225,233 km -> 54,225,233 km
row groups  376 -> 2,709
max rg rows 3,593,665 -> 100,000   (PORTO-FMT-009 caps at 150,000)
bytes       11,415,256,478 -> 11,999,057,592   (+5.11%)
```

That table is the deliverable for any data change. Without it you cannot tell a repair from a corruption.

## Principles

**Audit before you plan.** The plan's value is showing how little work is genuinely required. One migration ran a fourteen-point data audit and found exactly one mandatory change.

**Falsify your green run.** A validator that has never failed on this catalog has told you nothing. Plant a known violation and confirm it fires before you trust a clean pass.

**Measure, then write.** Every derived number in the documentation comes from a query you ran over the whole dataset, not a sample and not a plausible guess.

**The old catalog is live.** Its defects are served right now, and its stale objects will survive your push. Treat the remote as something to reconcile, not something that updates itself.

**Ask the publisher.** Licence, sensitivity, and exclusions are their call, not yours. Two of the three cost real rework when guessed.

**Fix upstream faults upstream.** File the issue rather than papering over it here. A workaround in this catalog becomes a defect every other catalog inherits.

## Before You Touch Anything

### Back Up, and Avoid the Two Ways It Goes Wrong

```bash
BK=~/backups/<catalog>-premigration-<YYYYMMDD>
rsync -a \
  --exclude='.git/' --exclude='.venv/' \
  --exclude='.env*' --exclude='.claude/' \
  "$SRC/" "$BK/tree/"
diff -r -q "$SRC" "$BK/tree"
chmod -R a-w "$BK/tree"
```

**A bare `rsync -a` sweeps in credentials.** One session started copying the working tree and had to kill the run, because it was pulling in `.env.local`, `.venv`, and `.git`. Exclude explicitly, then prove the result is clean:

```bash
find "$BK" \( -name '.env*' -o -name '*credential*' \
  -o -name '*secret*' \) -print
```

That must return nothing.

**Build the manifest in Python, not in a shell pipeline.** Terminal output decoration corrupted `find` and `ls` three separate times in one session, once producing an empty manifest that verified successfully. Walk the tree in Python, write sha256 for every file, and assert the file count you expect before declaring the backup good.

Do not treat git as the backup. Data files are gitignored, so a repository is not a copy of the dataset.

### Pull the Remote in Full

A diff is not enough. Fetch the remote bytes and compare them.

One migration found all 178 `collection.json` files byte-identical between local and remote, which meant every defect was live. The same pull found something a metadata diff would have missed: the remote held a **curated** `.portolan/metadata.yaml` with a real title, a Spanish description, a contact, `CC-BY-4.0`, a citation, and thirteen thematic keywords. A local re-extraction had already overwritten it with `TODO: Add value`. The good metadata existed only on the server.

The same pull also found 106 declared style assets that were never uploaded and returned live 404s, two corrupt 28,672-byte PMTiles that were SQLite intermediates, and stray `.pmtiles-journal` files. Against 20,513 downloads in the previous 28 days.

For a large partitioned dataset, join on partition key and size rather than fetching everything, then spot-check ETags against local md5. Fall back to size alone where the ETag shows a multipart upload.

Stop and ask if the two copies differ in a way that changes which is authoritative.

## Audit

### Read the Extraction Report First

If the catalog came from `portolan extract`, `.portolan/extraction-report.json` names every layer that failed and why. One catalog's report read `188 layers, 179 succeeded, 9 failed`, in two clean classes:

```
Cannot do natural order without a primary key, please add
```

WFS pagination on a table with no primary key. Five layers, three attempts each.

```
Unable to merge: Field alt-piso has incompatible types: double vs int64
```

An Arrow schema conflict between pages. Four layers.

Two further failures did not appear in the report at all. One layer extracted 1,098 features whose geometries were all NULL and was dropped downstream in silence. Another failed at the tiling stage yet stayed linked in `catalog.json`, so the catalog advertised a collection with no tiles, no thumbnail, and no style.

Compare the child links in `catalog.json` against the directories on disk. That catalog had 188 directories and 178 links, so ten collections existed and were unreachable.

### Count Every Defect Across Every Collection

Sampling hides the shape of the problem. Count. One catalog's audit, which is a serviceable checklist for the next one:

| Field | Found | Requirement |
|---|---|---|
| `title` | 1 of 178 | MUST |
| `providers` | 0 of 178 | MUST |
| Licence other than `proprietary` | 0 of 178 | `proprietary` MUST NOT be used (PORTO-CORE-060) |
| `rel: describedby` | 0 of 178 | MUST |
| `rel: agents` | 0 of 178 | MUST |
| Portolan schema URI | 0 of 178 | MUST (PORTO-CORE-006) |
| Style carrying the `default` role | 0 of 178, though 167 shipped two styles | MUST where more than one |
| `AGENTS.md` on disk | 0 | MUST |
| Populated temporal extent | 0 of 178 | |
| `documentation` asset | 56 of 178, though 178 READMEs existed on disk | |
| CRS | 63 declared EPSG:3857 over EPSG:4326 data | |

Also look for unregistered custom fields, asset roles that disagree between collections, and `rel: via` links typed `text/html` where the response is GML.

Then read `.portolan/metadata.yaml`. That catalog's carried literal `'TODO: Add value'` for contact, name, email, and licence, and the generated root README **published those placeholders as document text**, including a malformed `TODO: Add value <TODO: Add value>`. Generated documentation propagates whatever the metadata says, so unfilled templates become published prose.

Audit data from Parquet footer statistics rather than by reading rows. Nulls, minima, maxima, distinct values, geometry types, and schema drift across partitions all live in the column-chunk metadata. An entire 256-million-row integrity audit ran without touching row data.

### Classify, Then Size the Work

Sort every collection into one bucket: already conformant, metadata only, documentation only, style only, thumbnail only, conversion required, data-quality problem, provenance or licence problem, or unresolved. Present the counts. That table is what tells the user whether this is an afternoon or a week.

Before any conversion, run the `portolan-bootstrap` mirror-path assessment against representative upstream assets. Add its evidence and maintenance estimate to the migration checkpoint. Use a metadata-only mirror only when upstream data meets all applicable specification requirements. Otherwise, build a full mirror with conformant data copies.

## Check Whether the Toolchain Moved Before You Decide to Patch

This is the highest-leverage step in the skill, and it is easy to skip.

One catalog was built on 2026-06-09 with `portolan 1.0.0a0` and `gpio 1.2.0`, and nine layers had failed extraction. The plan was to patch them one at a time. Re-running extraction on the current toolchain recovered **eight of eight in 103 seconds**, where the original harvest had spent 821 seconds and failed. The reason was a single upstream commit adding a `sortBy` parameter for stable pagination on tables with no primary key, plus schema unification for the `decimal128` against `int64` conflicts.

Inspecting the new output changed the plan entirely. The current CLI wrote a far better collection than the one on disk: schema URI, checksums, `AGENTS.md`, `rel: via`, `table:columns`, a `default`-roled style, and a legend harvested from WMS `GetLegendGraphic`. The new `default.json` was the publisher's own SLD cartography rather than flat blue.

So before choosing:

1. Read the toolchain versions the old catalog recorded in `.portolan/`.
2. Compare against what is installed now.
3. Re-extract one representative collection and diff the result against its current form.

Re-extraction can be cheaper than patching and strictly better in output. It can also be wrong, when the upstream service has changed or gone away. Make it a checkpoint and show the diff.

### Checkpoint: Patch or Re-extract

Present the version delta, the sample diff, an estimated runtime for a full re-extraction, and anything the old catalog holds that a re-extraction would destroy. Ask which path to take.

## The spec is ground truth. rashid checks it

[portolan-spec](https://github.com/portolan-sdi/portolan-spec) is the standard. Every requirement carries a `PORTO-CORE-NNN` or `PORTO-FMT-NNN` id in `specs/portolan/requirements.yaml`. rashid implements those requirements and reports `PTL-*` rule ids that cite them. `portolan check` runs rashid.

Where rashid and the spec disagree, the spec decides. File the disagreement against rashid, cite the `PORTO` id, and record the workaround in `docs/conformance.md`. Do not weaken the validator, suppress findings, or add an allow-list entry to obtain a clean run. Where the CLI, `stac-check`, or your own reading disagrees with rashid and the spec is silent, rashid stands until the spec says otherwise.

### Pin the version

The catalog template's `tests/test_conformance.py` runs whatever `rashid` is on `PATH`. It fails when rashid is absent or outside `>=0.1.5,<0.2.0`, and its `docs/conformance.md` says why. Install the pinned version into a repository virtualenv and pin the same version in CI.

Then check which one you are invoking. `portolan check` imports rashid from the CLI's own environment, while a bare `rashid check` uses whatever is on `PATH`. The two are routinely different versions on the same machine. Re-running with a newer validator and getting an identical error count is a finding, not a confirmation. It can mean the rules you care about never ran.

### Declare One Schema Version

Every catalog and collection MUST declare the versioned Portolan schema URI in `stac_extensions` (PORTO-CORE-006). rashid reads the profile version from the **root** catalog and flags every object whose URI differs from it as `PTL-CNF-002`. Measured on a 197-object catalog by flipping only the root URI, that is 196 findings, one per object. Set the version once, at the root, and make the per-collection pass match it.

Take the version from the spec release you are targeting. The CLI stamps the highest schema version the installed rashid bundles, so what it writes tracks a dependency rather than your target. With portolan-cli 0.8.0 and rashid 0.1.8 that is v0.2.0, which matches spec v0.2.0. Pin the pair and check the stamped URI once. The reference generators keep the URI in a module constant so the choice is explicit.

### Partitions behind a remote glob go unchecked

rashid 0.1.8 runs `PTL-DAT-006`, `PTL-DAT-007`, `PTL-DAT-008`, `PTL-DAT-012`, and `PTL-DAT-014` over every file a local relative `partition:glob` matches, and reports once per collection at `/partition:glob`. A remote or absolute glob (`s3://`, `https://`, `/data`) cannot be listed from the local tree, so those partitions go unread and the run stays clean.

A published partitioned collection uses exactly that layout. Its data assets carry absolute `https` hrefs and its glob uses a bucket-native scheme, which PORTO-FMT-020 permits because glob expansion needs a listing. So a clean local run before upload proves nothing about the partitions.

Build a throwaway tree that mirrors the published layout, with hrefs rewritten to relative paths and the glob rewritten to a local relative pattern. Symlink the partitions rather than copy them, then run the data pass against that tree. Checksums still match, because the symlinks point at the same files the generator measured. See `reference/tools/validate_with_data.py`.

### Run a Negative Control

Build a deliberately broken copy of the catalog, run the validator, and confirm it fails. Do this before you trust any clean run, not after. Plant a partition with a row group over the 150,000-row cap (PORTO-FMT-009) and confirm `PTL-DAT-008` fires at `/partition:glob`. It is the cheapest step in this skill.

### Never Widen the Allow-List

The template ships `docs/conformance.md` and an `ACCEPTED` set in `tests/test_conformance.py` that starts empty. A rule id enters `ACCEPTED` only alongside a row in that file naming what was accepted, where, why, and the issue tracking it. Both or neither. A silently widened allow-list is a false claim about what the catalog conforms to.

`reference/conformance.md` carries the one section a migrated catalog adds to the template's file.

### `stac-check` Is Advisory, and Currently Crashes

Every Portolan Collection fails it with `'list' object has no attribute 'get'`. That is a stac-validator defect, tracked as [portolan-spec#157](https://github.com/portolan-sdi/portolan-spec/issues/157), and the template's `tests/test_stac_valid.py` and `docs/conformance.md` already tolerate that one string narrowly. The spec's own reference catalog fails identically, so no change to your catalog avoids it. Diagnosing it from scratch cost eleven turns in one session and six in the other. Do not re-diagnose it.

`stac-check` also recommends a `rel: self` link. The spec agrees for the root of a catalog served from one fixed URL, which SHOULD carry an absolute `self` link (PORTO-CORE-081). Keep that link. rashid uses it as the base for resolving absolute structural links.

## Styles Are Where the Value Is

An old catalog usually validates long before it communicates anything. One had 177 `styles/default.json` files containing **three distinct paint blocks** between them: flat blue fill, flat blue circle, flat blue line. No data-driven expressions at all. The source URL was a bare relative path with no `pmtiles://` prefix, so nothing loaded in MapLibre and every thumbnail came out monochrome.

The publisher's real cartography was already in the catalog, sitting in `styles/source.json`, 75 of them data-driven. Those files had **no `url` key at all**.

The single highest-leverage fix in that entire migration was one sentence: `source.json` has the semantics and `default.json` has the working source, so merge them. Combined with a re-harvest of the remaining SLDs from the WMS `GetStyles` endpoint, that took the catalog from 0 to 90 data-driven styles and from 3 to 68 distinct colours.

So before writing any style of your own, look for cartography the catalog already carries or the publisher still serves. Read the styling rules and the legend rule in `portolan-bootstrap`, which apply unchanged here.

Two conversion limits to expect. The CLI's SLD converter handles categorical rules, where a filter is `PropertyIsEqualTo` and becomes a `match` expression. A graduated class-break SLD carries a range filter instead, and the converter **skips those rules in silence**. There is no warning and no entry in the conversion report, so a choropleth degrades to a flat style that looks intentional. Where every rule is graduated, the failure surfaces as the misleading `No valid symbolizers found in SLD rules`.

Worse, a rule mixing equality with a range converts to something quietly wrong, because the filter search descends through the enclosing `And` and finds the equality alone.

Those styles are frequently the publisher's most considered cartography. In one catalog 81 of 92 SLDs converted, and all 11 failures were choropleths. `reference/tools/sld_graduated.py` converts them to a `step` expression, which is also the form the browser can derive a legend from. Its output carries no source `url`. Run `reference/tools/fix_styles.py` after it, or the style will not load.

### Four Defects No Validator Sees

rashid does not parse style bodies. These appear only when you render, and `portolan-thumbnails` carries the full detail:

* `fill-opacity: 0.0`, which is invisible and valid.
* `circle-color: #ffffff` against a white background.
* A `symbol` layer with no `glyphs` endpoint, which crashes MapLibre GL Native outright.
* `match` labels mixing types. MapLibre requires all-integer or all-string, so floats, or integers beside a string, return HTTP 400.

Render every collection and look at the images. That is the only gate that catches these.

## Measure Before You Write the Number

Three separate rounds of invented figures reached draft documentation in one session: a bbox count off by 35 percent, three query results, and global quantiles computed from a biased 40-file sample. All were plausible. All were wrong.

Every derived number ships only after you compute it over the whole dataset. Two traps make wrong numbers easy:

**DuckDB `ST_Length_Spheroid` returns silently wrong finite values**, not just `NaN`, and was still wrong in 1.5.5. Cross-checked against a hand-written Vincenty inverse, a haversine implementation over raw WKB agreed to 0.2 percent while DuckDB disagreed erratically in both directions. `ST_Union_Agg` also segfaults on large geometries. Use the bbox covering column instead.

**Measure spatial ordering against each file's own extent.** One session spent seven turns concluding a catalog had no spatial ordering anywhere, then found the opposite: 170 of 179 files were Hilbert-ordered and none were unordered. The first measurement scored every file against one catalog-wide envelope, and a file sorted on its own extent traces a different curve, so it reads as random under someone else's. Run an explicitly sorted control to calibrate the threshold before believing either answer.

## Sensitive Data

Scan in two stages. A regex over column names flagged 41 of 179 collections in one catalog. Sampling two non-null values per flagged column cleared **38 of the 41**, a 93 percent false-positive rate on names alone.

The one genuine finding was not caught by name matching at all. It was identified by the combination of columns present, plus reading the free-text fields. Names tell you where to look, not what you found.

Two lessons that cost rework:

**Publishing the exclusion reasons is itself a disclosure.** A README listing which layers were withheld and why is a map to exactly the data you decided not to amplify. Keep the list, drop the reasons.

**The publisher decides.** In that migration the data owner reviewed the finding and rejected it outright, which made four exclusions moot after they had shipped. Ask before excluding, and treat your own scan as a question rather than a verdict.

## Restructuring at Scale

A flat catalog of 178 collections is hard to browse and expensive to fetch. Grouping one into 13 thematic sub-catalogs took it from 2,129 rashid errors to 239, because much of the error count was structural.

Map collections to groups with an **explicit table**, not a pattern match. A regex is harder to audit than a list, and a misfiled collection means a permanent ID change once the catalog is published. Validate the table: every collection appears exactly once, no gaps, no overlaps, and the excluded set is named separately.

Do not collapse collections because the count feels large, and do not preserve all of them blindly either. Collection identity is a user-visible URL. Any substantial restructuring is a checkpoint.

Where a collection has few features, check its tile zoom. A two-feature collection tiled to `maxzoom 0` puts both points in a single pixel, and no framing rescues that. `portolan-thumbnails` covers the repair.

## Publication

Do everything locally first. Then, in order: diff, publish, verify as a consumer, prune.

### The Diff Comes First

One restructure produced this:

```
NEW (added)  : 1,682
REPLACED     : 2        catalog.json, README.md
ORPHANED     : 1,492    left live unless pruned
```

Publishing never deletes. Those 1,492 objects stay served, at their old URLs, alongside the new catalog, until something removes them.

Guard the prune list. Any remote key that matches one of the new prefixes but is absent locally goes into a `refuse` bucket, never a `delete` one, because that pattern means your local tree is incomplete rather than that the object is stale. Prove every object you intend to delete is recoverable from the backup, dry-run the deletion, then batch it.

### Four Traps Found Only After Publishing

**`partition:glob` must use a bucket-native scheme.** Expanding a glob needs a directory listing and plain HTTP does not provide one, so the pattern is sent literally and returns 404. PORTO-FMT-020 exempts the glob from the https-only rule for exactly this reason. Enabling asterisks in HTTP paths does not rescue it. An https glob cannot work at all. The single-file case is unaffected, so state plainly in the documentation which access path needs credentials and which does not.

**A bucket name containing dots needs path-style addressing.** Virtual-host addressing fails TLS verification. The documented setup has to say so, along with the endpoint, or the reader's first query fails.

**Link checking by HTTP status does not work on Source Cooperative.** It is a single-page app and returns 200 for every path, including paths outside the product. Fetch the rendered page and read the emitted HTML.

**Relative markdown links resolve one directory too high**, because the rendered root page has no trailing slash, so a bare `href="AGENTS.md"` points outside the product. Publish absolute URLs.

### Run Every Documented Query Against Published Data

A gate, not a courtesy. Use only the setup the documentation gives the reader, from a clean environment. This is what caught the broken `partition:glob`, after the catalog had already been declared finished.

If a documented query fails, fix the query or delete it. Do not ship it broken.

Then re-run the validator against the live catalog, which probes the host for range support and CORS headers. `portolan check --live` takes the published base URL as `--url`, overriding `publish.public_url`. Running rashid directly, the same argument is spelled `--live-base-url`.

## Mechanics

Read `portolan-cli` for the full command reference and `git-backed-catalog` for repository and publication mechanics. This section covers only what migration adds.

Both migrations ran the repository path: a catalog repo created from `portolan-sdi/portolan-catalog-template`, generators under `tools/`, gates under `tests/`, and publication through `tools/publish.py`. Follow `git-backed-catalog` for that. Two cautions specific to migration:

**A turn interrupt kills a foreground background job.** One extraction died at 84 of 187 layers while reporting exit 0. Detach long runs and poll a log for a completion sentinel:

```bash
nohup ./run-extract.sh > /dev/null 2>&1 < /dev/null &
until grep -q 'DONE exit=' extract.log; do sleep 20; done
```

**Exit code 0 can mean "aborted at a confirmation prompt."** Pipe `yes |` into anything that prompts, or you will read a successful exit from a command that did nothing.

**Deferring thumbnails leaves a rule firing.** Migration often stages thumbnails separately, through `portolan-thumbnails`, so `portolan add --no-thumbnails` is the common call. That leaves `PTL-VIZ-001` failing until the images land. Expect it in the interim baseline rather than chasing it. Pair `--no-thumbnails` with `check.disabled` in `.portolan/config.yaml` only for a catalog that will never ship thumbnails at all.

### Apply what add cannot derive

`portolan add` regenerates `collection.json`. Since portolan-cli 0.8.0 a collection's own `metadata.yaml` is authoritative for its title, description, license, and providers, and an ancestor's `metadata.yaml` only fills a field the collection still lacks. A re-add no longer replaces a title a maintainer set on the collection, and a catalog title never becomes a collection title.

What `add` still cannot derive is metadata that lives outside the tree: titles and descriptions harvested from an upstream service, originators credited in a free-text attribution field, and hand-written text for layers whose upstream abstract is useless. Keep that in a generator and re-apply it as an idempotent last pass after every `add`. See `reference/tools/apply_metadata.py`. Add a CI gate that regenerates and diffs, so a hand-edit to generated output fails the build rather than surviving until the next regeneration wipes it.

Two fields the generator must leave alone. It keeps the root's absolute `self` link, because the spec asks for one (PORTO-CORE-081). It does not touch `updated`, because a mirror sets `updated` to the time of the last sync from source (PORTO-CORE-057), and a metadata re-apply is not a sync.

### Reference Implementations

`reference/tools/` carries six scripts lifted from the two migrations. Each names in its docstring the defect that forced it to exist.

| Script | Works around |
|---|---|
| `reencode.py` | Row groups over the `PTL-DAT-008` cap, streamed so peak memory is one batch |
| `build_collection.py` | Measured extents, counts, and checksums, with a staleness check |
| `validate_with_data.py` | A remote `partition:glob` that the data pass cannot list locally |
| `sld_graduated.py` | The SLD converter skipping class-break rules |
| `fix_styles.py` | Generated styles carrying no source URL and no zoom range |
| `apply_metadata.py` | Metadata `add` cannot derive from the tree |

## Checkpoints

| Checkpoint | Present | Ask |
|---|---|---|
| Starting state | Local and remote inventory, what differs, which is authoritative | Proceed, or resolve the discrepancy first? |
| Audit findings | Defect counts per field, collections per bucket, estimated work | Is this the right scope? |
| Patch or re-extract | Version delta, sample diff, runtime estimate, what re-extraction would destroy | Which path? |
| Licence and contact | What the source states, and where it says it | Confirm licence, name, email |
| Sensitive layers | Flagged columns, sampled values, proposed exclusions | Confirm with the publisher before excluding |
| Restructuring | Proposed grouping table, collection IDs that would change | Approve before IDs move |
| Style plan | Recovered publisher cartography, measured distributions, legend viability | Approve before tiling |
| Data transformation | Before and after counts, the rule forcing it, reversibility | Approve? |
| Publication diff | Objects added, replaced, orphaned, unchanged | Publish? |
| Prune list | Objects to delete, proof each is in the backup | Delete? |

## Failure Handling

| Situation | Action |
|---|---|
| Backup contains a credential file | Delete the backup and redo it with explicit excludes |
| Shell-built manifest looks wrong or empty | Rebuild it in Python and assert the file count |
| Local and remote metadata disagree | Stop and ask which is authoritative. Do not assume local |
| A layer failed extraction in the old catalog | Read the report, check whether the toolchain has since fixed it |
| Collection directory exists but is unlinked | Decide explicitly whether to link or remove it. Do not leave it stranded |
| Validator passes on first run | Plant a violation and confirm it fails before believing the pass |
| rashid and the spec disagree | The spec decides. File the issue against rashid with the `PORTO` id, and record the workaround in `docs/conformance.md` |
| A finding cannot be fixed | Add a row to `docs/conformance.md` with a tracking issue, then the id to `ACCEPTED`. Never one without the other |
| `stac-check` crashes on a Collection | Expected. The template's gate tolerates that one string. Do not re-diagnose it |
| Style renders blank | Check opacity, colour against background, glyphs, and `match` label types before blaming the renderer |
| Publisher cartography exists but will not convert | Convert it yourself rather than substituting an invented palette |
| Number cannot be computed over the full dataset | Say the coverage in the documentation. Do not extrapolate from a sample |
| Sensitivity scan flags a column | Sample values before acting. Expect most flags to be false |
| Remote holds objects your local tree lacks | Refuse to delete them and report. An incomplete local tree looks identical to a stale remote |
| Documented query fails against published data | Fix the query or delete it. Do not ship it broken |
| CLI, browser, validator, or spec behaves wrongly | File the issue upstream and record the workaround in `known_issues` |
