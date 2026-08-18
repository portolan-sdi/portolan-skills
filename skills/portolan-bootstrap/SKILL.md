---
name: portolan-bootstrap
description: Build a complete, well-documented Portolan catalog from a data source — research the data and its publisher, convert to cloud-native formats, write documentation and styles that make it usable, and publish. Use when someone wants to publish, mirror, or 'portolan-ify' a dataset, an open data portal, an ArcGIS or WFS service, or a folder of geospatial files.
---

<!-- freshness: last-verified: 2026-08-12, maps-to: portolan-sdi/portolan-spec specs/best-practices/ -->

# Portolan Bootstrap

This skill takes the data-first path: you hold the files, convert them, document them, and publish the whole catalog to a bucket.

If the user wants catalog metadata to live in a git repository, validated by CI and open to pull requests from other people, use the `git-backed-catalog` skill instead.

If a catalog or a published dataset already exists and the job is to bring it into compliance rather than build it from scratch, use the `portolan-migrate` skill. It audits what is there and repairs it in place, leaving the underlying data alone unless a named requirement forces a change.

## The Goal

A finished catalog clears three bars. Someone who has never seen the data can decide in one screen whether to trust it. An agent can write a correct query on the first try. Every collection renders something meaningful the moment it opens.

Validation is the floor, not the goal. A catalog can pass every check and still tell a reader nothing, and that catalog is not done.

Read an exemplar before you start. [portolan-nl](https://source.coop/cholmes/portolan-nl) is a published catalog that clears all three bars.

The [portolan-reference catalog](https://github.com/portolan-sdi/portolan-spec/tree/main/examples/catalog/portolan-reference) in portolan-spec is the annotated minimum. Both show what descriptions, agent guides, and styles look like when the work is actually done.

The Portolan CLI is one way to get there, not the definition of done. Where a better tool fits a step, use it: [gpio](https://github.com/developmentseed/geoparquet-io) for conversion and spatial sorting, tippecanoe directly for tiling options the CLI does not expose, DuckDB for profiling a column before you style it.

Record what you ran in the collection's `AGENTS.md` so the next person can reproduce it. The [spec](https://github.com/portolan-sdi/portolan-spec) is the standard and the CLI implements it. Read [philosophy.md](https://github.com/portolan-sdi/portolan-spec/blob/main/specs/best-practices/philosophy.md) for what the standard is buying.

## Raster Collections

Use a collection-level asset for a collection that contains one raster file. Do not create an item directory for that case.

Model each scene as an item when a collection contains multiple raster scenes. Put each COG in its item's subdirectory. Link every normative item JSON from `collection.json` with an `item` link. Keep `items.parquet` as a derived mirror with the `collection-mirror` role.

```text
pop-1975/
  collection.json          # carries one `item` link per scene
  items.parquet            # derived mirror, `collection-mirror` role
  thumbnail.png
  pop-1975-R5_C11/
    pop-1975-R5_C11.json   # normative item
    GHS_POP_…_R5_C11.tif   # item-level asset
```

The published `nlebovits/jrc-glofas` reference contains 271 `item` links. Its links use paths such as `./ID100_N80_W20/ID100_N80_W20.json` and type `application/geo+json`.

## Working Agreement

**Checkpoint when uncertain.** Asking costs a minute. Guessing costs a republish.

**Dry-run before anything expensive.** Extraction, conversion, tiling, and push all have dry-run modes. Use them, and report the numbers before you spend the time.

**Warn inline, summarize at the end.** A failed layer does not stop the run. It also does not disappear from the final report.

**Front-load research and quality control.** A rendering that lies costs more to fix than to prevent, because the user finds it on a screenshot after publication.

**Fix upstream faults upstream.** When the browser, the CLI, or the spec is wrong, file the issue there rather than papering over it in this catalog. A workaround here becomes a defect every other catalog inherits.

**Reuse the publisher's vocabulary.** Their topics, tags, department names, and words for things are what the data's audience already searches for. Invented taxonomies compete with the ones readers know.

**Publish when you can defend it.** Every collection should survive the question "where did this sentence come from, and does that map show what the legend claims?" Publish after that is true, not before.

## Every Claim Carries Its Source

Research widely. Then make each claim traceable. A fact belongs in the catalog when it falls into one of three tiers, and nowhere else.

**Attested.** The source states it: service metadata, a GetCapabilities document, the portal's dataset page, a published data dictionary. Copy the wording rather than paraphrasing it for license, attribution, and legal statements. Record where it came from.

**Researched and cited.** You found it outside the source's own metadata, in the publisher's data dictionary PDF, an agency program page, a standard's code list, or the ordinance that created the program.

This tier is encouraged, and it is often the difference between a usable catalog and a shelf of column names. The condition is a link. A researched fact reaches the catalog with the URL it came from recorded in the collection's `processing_notes`, and, where a reader benefits, as a markdown link in the description or the `AGENTS.md` provenance section. Decoding a coded column means citing the code list you decoded it from.

**Derived.** You computed it from the published data: row counts, value distributions, category frequencies, or a measure like sale price per square foot.

Derivation is allowed when the computation is reproducible, so put the query in `AGENTS.md` and let the reader rerun it. Never state a derived number you did not actually compute.

Anything else is invention, including the plausible kind. Guessing that pipe-material code 109 means ductile iron is invention. Finding the utility's code list and citing it is research. Reporting that 109 is the most common value in the column is derivation.

When research fails, say so in the documentation instead of papering over it. "The publisher has not released a code list for `MATERIAL`; the values are opaque integers" is honest and useful to a reader. A column left undescribed is a smaller failure than a column described wrongly.

The `known_issues` field in `.portolan/metadata.yaml` is where those gaps belong, alongside coverage limits and anything else a consumer would otherwise discover the hard way.

The record lives in `.portolan/metadata.yaml` alongside the rest of the human-enriched metadata:

```yaml
source_url: "https://example.gov/data/parcels"
attribution: "City of Example, Assessor's Office"
processing_notes: >
  Extracted from the ArcGIS FeatureServer on
  2026-08-12. MATERIAL codes decoded from the
  utility's published code list at
  https://example.gov/water/pipe-codes.pdf.
  Price per square foot derived from SALE_PRICE
  and SHAPE_Area; see AGENTS.md for the query.
```

**The test.** Before publishing, take any sentence from a description, a README, or an `AGENTS.md` and answer two questions: which tier is this, and where is its source? A sentence with no answer does not ship.

Three fields never come from research alone. Title, license, and contact stay checkpointed. You may propose a license you found on the publisher's terms page, and the user confirms it.

Translation is checkpointed too. Do not translate a title or description unless the source publishes both languages or the user asks for it.

## Research the Data Before You Convert It

Do this before extraction, not after. What you learn here decides which datasets are worth carrying, which columns need decoding, and which styles will say anything at all.

Work these targets in order.

**1. The portal dataset page and its siblings.** Read the page for each candidate dataset, plus the portal's own topic and tag structure. Publishers routinely explain a dataset in prose on the portal in text that never reaches the service metadata. Their topics and tags are also worth reusing, because they are the vocabulary the data's own audience already knows.

**2. The service's own metadata.** For ArcGIS, fetch the service and layer JSON:

```bash
curl -s "<SERVICE_URL>/0?f=json" | jq '.fields'
```

Field aliases and `domains` frequently carry the coded-value lists that decode integer columns, which is the cheapest research win available. For WFS, read the capabilities and schema documents:

```bash
curl -s "<WFS_URL>?service=WFS\
&request=GetCapabilities"
```

`portolan extract arcgis <URL> --dry-run` and the WFS equivalent list layers without downloading anything, so use them here to size the job.

**3. Published data dictionaries and metadata files.** Attached PDFs, FGDC or ISO XML, and the `.txt` readme shipped inside a shapefile download are the usual home of column meanings.

**4. The owning department and the program.** Knowing which office publishes a dataset and which program produced it explains update cadence, coverage gaps, and what the rows are actually counting.

**5. The licensing terms page.** Find the terms that apply to this dataset rather than assuming the portal-wide default covers it.

**6. Sibling portals.** Many cities and agencies also run an ArcGIS Online organization gallery holding layers the open data portal does not list. Check it for both duplicates and genuine additions, and say which candidates are which.

**7. Existing publisher cartography.** SLD files, style JSON, and tile servers let you match the publisher's own colors rather than inventing a palette. Save the source style files as assets in the collection.

Record findings per candidate as you go: what the dataset is, who publishes it, what each non-obvious column means and where that meaning came from, what stays opaque, and whether it duplicates another candidate.

### Checkpoint: Research Findings

Present this before extracting anything:

* The candidate list with a one-line description each, and which ones you propose to drop as duplicative or low-value.
* Columns you decoded, with the source for each.
* Columns that remain opaque after research.
* Proposed license and attribution, with the page you found them on.
* Estimated feature counts, total size, and time.

Ask whether to proceed with this candidate set.

## The Documentation Contract

The standards live in [documentation.md](https://github.com/portolan-sdi/portolan-spec/blob/main/specs/best-practices/documentation.md) and the scoring in [grader.md](https://github.com/portolan-sdi/portolan-spec/blob/main/specs/best-practices/grader.md). Read both. This section covers only what agents reliably get wrong.

### STAC Descriptions

Every URL is a markdown link. A bare URL renders as plain text in the data browser and the reader cannot click it. This includes URLs that arrive inside text copied from the source, which is where most of them come from.

```markdown
File a new service request at
https://example.gov/csb/submit        <- renders as text

File a new [service request](https://example.gov/csb/submit).
```


Mention the agent guide in the prose with an inline [AGENTS.md](AGENTS.md) link. Appending "Start at the catalog agent guide" as a trailing sentence reads as boilerplate and gets skipped.

Call the browser page the "data browser" or the "interactive data page". It is not an "interactive map": it is also where a reader downloads the data, checks the license, previews the schema, and follows links out.

Do not link a collection description to itself. A "view this collection" link on the collection page is noise.

### README.md

Generated output, never hand-edited. It is built from STAC metadata plus `.portolan/metadata.yaml`. Edit the YAML and regenerate with `portolan readme`. A hand-edited README is silently replaced on the next run.

### AGENTS.md

The CLI scaffolds a stub on `init`, `add`, and `check --fix`, and never overwrites an existing file. The collection stub carries fixed headings: `## Overview`, `## Accessing the data`, `## Schema & field notes`, `## Data quality & usage notes`, `## Example queries`, and `## Related collections`.

Replacing that stub prose is your job. An unedited stub is a shipped defect, and validation will not catch it.

Write the join keys, the CRS and what it costs a consumer, the quirks a query will hit, and recipes that run. When a tabular dataset reaches the map through a join, the join belongs here as a query someone can paste and run, not as a sentence describing that a join exists:

```sql
-- Sales joined to parcel geometry on parcel id
SELECT s.sale_price, s.sale_date, p.geometry
FROM read_parquet('sales.parquet') s
JOIN read_parquet('parcels.parquet') p
  ON s.parcel_id = p.parcel_id;
```

Every query in `AGENTS.md` must have been run against the published data. A recipe that fails on the first try is worse than no recipe, because it costs the reader the time to debug someone else's mistake.

### Column Descriptions

`table:columns` is where researched meaning lands. A coded column carried through with no decoded meaning is unfinished work, whether or not the catalog validates.

Fill the description from research, not from the column name. `MATERIAL` described as "material" adds nothing.

### llms.txt

Nothing in the CLI generates it, and the `reading-portolan` skill tells consumers to fetch it. Author it, or decide explicitly not to and record why.

### Link Hygiene

Use `source.coop` URLs for anything a human reads, because that host renders READMEs and agent guides. Use `data.source.coop` only for raw byte fetches by a machine.

This applies to thumbnails, README links, and "additional resources" lists, all of which land on the wrong host by default. The `sourcecoop` skill is the canonical home for this rule and the rest of the Source Cooperative workflow.

## Styles That Say Something

Ship three to five styles per dataset, chosen after you query the actual distributions. A style that paints every feature the same color says nothing the bounding box did not already say.

Read [styling.md](https://github.com/portolan-sdi/portolan-spec/blob/main/specs/best-practices/styling.md) and the visualization section of [core.md](https://github.com/portolan-sdi/portolan-spec/blob/main/specs/portolan/core.md) for the requirements.

Choose styles from findings, not from column types. Sale price plus area becomes price per square foot. A date column becomes an age band or a recency band. A category column is worth styling only once you have confirmed the categories are populated and mean something.

Name styles in the reader's language. If a term needs explaining to the user who commissioned the catalog, it will not survive contact with a stranger.

Vary palettes across sibling collections. Two boundary datasets in the same pale blue read as the same dataset in a card grid, and a reader scanning cards will not look twice.

### The Legend Rule

As of 2026-08-12, the browser derives a legend only from a `fill` layer whose `fill-color` is a `match` or `step` array expression. An `interpolate` expression yields no legend. A `case` expression yields no legend. Line, circle, and symbol layers yield no legend at all. See [portolanStyles.js](https://github.com/portolan-sdi/portolan-browser/blob/main/src/utils/portolanStyles.js) for current behavior.

A style that produces a legend therefore looks like this:

```json
{
  "type": "fill",
  "paint": {
    "fill-color": [
      "match", ["get", "material"],
      "ductile_iron", "#1f77b4",
      "lead", "#d62728",
      "#cccccc"
    ]
  }
}
```

Two consequences follow. A line or point dataset gets no legend from its natural layer type, so plan its styles knowing that, and consider a fill layer where the geometry supports one.

And every `match` branch must be checked against real values before shipping. A legend listing ten categories over a map painted one color is the most common visible defect in a new catalog. Verify with a query, not by reading the style:

```sql
SELECT category, count(*)
FROM read_parquet('data.parquet')
GROUP BY category
ORDER BY 2 DESC;
```

Every branch in the `match` expression should appear in that result, and every populated category worth showing should appear in the `match`.

### Checkpoint: Style Plan

Per collection, present the proposed styles, the column each uses, the distribution you measured, and whether a legend will appear. Ask for approval before generating tiles.

## Assets and Provenance

Carry the publisher's own files into the catalog as assets, linked at their original locations. A reader who wants the authoritative original should not have to leave the catalog and search for it, and a reader checking your work needs to see what you started from.

Carry, at minimum:

* The download the publisher offers: shapefile, KML, GeoJSON, GeoPackage, CSV.
* Metadata files shipped with it: FGDC or ISO XML, a data dictionary PDF, the `.txt` readme inside a shapefile zip.
* Cartography: SLD files, style JSON, or a tile service URL you matched colors against.
* Logos and branding the publisher makes available, when the catalog is a mirror of their site.

Give each carried asset a title that says what it is and where it came from, so the asset list reads as a provenance record rather than a pile of filenames. The publisher's cartography files earn their place here too: an SLD or style JSON you matched is evidence for the colors you chose.

When the source is a feature service or a WFS endpoint rather than a file, link the endpoint and describe what you did to get the data. Layer selection, pagination, and any bbox filter belong in `processing_notes`.

Record the extraction date. A mirror without a date cannot be compared to the live service, and a reader has no way to judge how stale it is.

Keep GeoParquet in the source CRS. Reprojection belongs in the PMTiles, which need Web Mercator to render. A consumer who needs native coordinates cannot recover them from a reprojected file, and the reprojection is rarely mentioned where they would look.

Drop `lat` and `lon` columns when a geometry column carries the same information. They survive extraction from tabular sources and then show up in `table:columns` as noise a consumer has to reason about.

See [conversion-defaults.md](https://github.com/portolan-sdi/portolan-spec/blob/main/specs/best-practices/conversion-defaults.md) for format and compression defaults.

## Quality Control Before You Publish

Open each collection in the data browser and look at it. Most defects in a new catalog are visible, and none of them are caught by validation.

Per collection:

* The default style renders visible data at the full extent. A blank map or a barely-visible tint is a failure, not a subtle style.
* Every legend entry corresponds to values that exist in the data.
* The bbox is tight. One outlier row dragging the extent into the next state makes every thumbnail useless.
* The first PMTiles load is small enough to open on a laptop, and the data is still complete at the target zoom. An 11 MB first tile hanging a browser tab is a real report from a real catalog.
* The thumbnail shows data rather than basemap, and its aspect ratio matches the card it appears in. Hand off to the `portolan-thumbnails` skill when the generated thumbnail is not good enough.
* Every link in the description, README, and `AGENTS.md` resolves, and human-facing links point at `source.coop`.

Check the bbox with a query rather than by eye, because one stray row is invisible at full extent and moves the whole frame:

```sql
SELECT count(*)
FROM read_parquet('data.parquet')
WHERE NOT ST_Within(
  geometry,
  ST_MakeEnvelope(-90.4, 38.5, -90.1, 38.8)
);
```

Check tile weight in the browser's network panel, or by opening the PMTiles in [pmtiles.io](https://pmtiles.io) and zooming. Watch two things at once: the first tile has to stay small, and the data still has to be complete at the zoom where people will look at it. Tightening one usually breaks the other, so confirm both after every tippecanoe change.

Then run the validator. Run it again with `--live` once the catalog is published, which probes the host for range support and CORS headers:

```bash
portolan check
portolan check --live
```

Score the result against [grader.md](https://github.com/portolan-sdi/portolan-spec/blob/main/specs/best-practices/grader.md) and report the tier per section at the final checkpoint.

Verify the catalog as a consumer would, using the `reading-portolan` skill. Run the queries you wrote into `AGENTS.md`. If a documented query does not run, the documentation is wrong.

### Checkpoint: Publish

Present the file count, total size, destination, the grader tiers, and every warning accumulated during the run. Ask before pushing.

## Mechanics

Commands verified against the CLI on 2026-08-12. The `portolan-cli` skill is the full reference; this section covers the bootstrap path only.

Starting from a remote service. `extract` initializes the catalog for you unless you pass `--raw`:

```bash
portolan extract arcgis "<URL>" ./catalog \
  --dry-run
portolan extract arcgis "<URL>" ./catalog \
  --license CC-BY-4.0
cd catalog
portolan add . --pmtiles
portolan metadata init
portolan readme
```

Starting from a directory of files:

```bash
portolan init --license CC-BY-4.0
portolan scan --suggest-collections
portolan check --fix --dry-run
portolan check --fix
portolan add . --pmtiles
portolan metadata init
portolan readme
```

Both paths then run through research, documentation, styles, and quality control before any push.

| Step | Command | Notes |
|---|---|---|
| List a service's layers | `portolan extract arcgis <URL> --dry-run` | Subcommands: `arcgis`, `wfs`, `carto`. `--layers` and `--exclude-layers` take glob patterns. |
| Extract a service | `portolan extract arcgis <URL> <OUTPUT_DIR>` | The output directory is positional. `--license` is required unless the source publishes a license URL of its own. |
| Start from local files | `portolan init --license CC-BY-4.0` | A license is required. `--auto` skips the remaining prompts; `--title` and `--description` set them directly. |
| Survey a directory | `portolan scan --suggest-collections` | Recursive by default. `--fix` renames files with invalid characters; pair it with `--dry-run` first. |
| Preview conversions | `portolan check --fix --dry-run` | Shows what would be converted to cloud-native formats without writing anything. |
| Convert | `portolan check --fix` | `--workers` sets parallelism. `--no-data` skips reading asset bytes for a faster pass. |
| Track files and build assets | `portolan add . --pmtiles` | There is no `--recursive` flag; a directory path covers its contents. `--workers`, `--stac-geoparquet`, and `--force-pmtiles` also apply. |
| Create metadata templates | `portolan metadata init` | Recursive by default. `--no-recursive` limits it to one level, `--force` overwrites. |
| Generate READMEs | `portolan readme` | Recursive by default. `--check` exits 1 when a README is stale, for CI. |
| Build STAC-GeoParquet | `portolan stac-geoparquet` | Recommended for collections over 100 items. Runs on all collections unless `-c` names one. |
| Partition a large file | `portolan partition <file> <out> --preview` | Files over 2 GB are partitioned automatically during `add`; use this to control the strategy. |
| Inspect one target | `portolan info <path>` | Format, CRS, bbox, and feature count for a file, a collection, or the catalog. |
| Preview a push | `portolan push --dry-run` | Skips the remote state check, so it will not detect conflicts. |
| Push | `portolan push -v` | Destination comes from `PORTOLAN_REMOTE`, a `.env` file, or a positional URL. |

Files must sit in subdirectories, because each subdirectory becomes a STAC collection. Move anything at the catalog root into a named directory before adding it.

Destination setup is delegated. Use the `sourcecoop` skill for Source Cooperative, which is the common case, and the `git-backed-catalog` skill when the metadata belongs in a repository. After publishing, use the `register-catalog` skill to add the catalog to the registry.

## Checkpoints and Failure Handling

| Checkpoint | Present | Ask |
|---|---|---|
| Research findings | Candidates, decoded columns, opaque columns, proposed license | Proceed with this set? |
| Discovery | Layer or file count, feature estimates, size, time, warnings | Proceed with extraction? |
| Extraction complete | Success count, failures with reasons, total size | Continue? |
| Destination | Options available | Where should this publish? |
| License and contact | What the source states, and where it says it | Confirm license, name, and email |
| Style plan | Styles per collection, columns, distributions, legend viability | Approve before tiling? |
| Quality control | Per-collection checklist results and grader tiers | Fix now, or publish? |
| Publish | File count, size, destination, accumulated warnings | Push? |

| Situation | Action |
|---|---|
| Layer fails extraction | Warn inline, continue, summarize at end |
| Missing CRS | Flag it, ask the user whether it is critical |
| Dataset over 100k features | Warn about time and memory before proceeding |
| Credentials invalid | Stop and help the user fix it |
| Mixed languages in source metadata | Checkpoint and ask which is primary |
| Field exists in source but was not extracted | Checkpoint with the exact source text |
| Required field missing from source | Checkpoint and ask the user to provide it |
| Column meaning not found after research | Document the gap; do not guess |
| Legend lists categories the data lacks | Fix the style before publishing, not after |
| Thumbnail shows basemap only | Hand off to `portolan-thumbnails` before publishing |
| Documented query fails when rerun | Fix the query or delete it; do not ship it broken |
| Source file cannot be carried as an asset | Link the endpoint and record why in `processing_notes` |
| Browser, CLI, or spec behaves wrongly | File the issue upstream; note the workaround in `known_issues` |
