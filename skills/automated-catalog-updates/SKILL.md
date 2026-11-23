---
name: automated-catalog-updates
description: Set up automated updates for a Portolan catalog that mirrors a source that changes regularly. CI or cron runs the scripts on a schedule, and no agent takes part after setup. Each run re-extracts only the collections whose source changed and publishes each change as a new version. Work in progress, and the place to run large extracts is still open. Use when someone wants a mirror of an ArcGIS, GeoNode, WFS, or similar service to update itself.
---

<!-- drift: depends-on: portolan-cli, portolan-spec -->

# Automated catalog updates

> **This skill is a work in progress.** Each source type in this skill has exactly one reference catalog behind it, and a new source can break any step. Report a step that fails for your source, a source behavior this page omits, a place you ran the job, or a better signal. A pull request against this skill is the most useful report. An issue in [portolan-skills](https://github.com/portolan-sdi/portolan-skills/issues) also helps.

A mirror matches its source on the day of the extract, and the source changes after that. This skill sets up automated updates: a set of scripts plus a scheduled job that runs them. You write both once. After that, CI or cron runs the job, and no agent or person takes part. Each run re-extracts only the collections whose source changed. Each change becomes a new version, and the earlier versions remain in the bucket unchanged.

Build the catalog first. The `portolan-bootstrap` skill builds it, and the `git-backed-catalog` skill puts its metadata in a repository with CI. The scheduled job runs in that repository and commits each new version to git.

## Reference implementations

phl-housing-demo and pergamino-ide-catalog mirror layers that the publisher edits in place. They built the same design independently, and each has a `docs/refresh.md` that explains every step and every failure. firms-catalog mirrors a stream that only grows. See [Append-only streams](#append-only-streams). Read the catalog closest to your source before you write code.

| Catalog | Source | Schedule |
|---|---|---|
| [phl-housing-demo](https://github.com/nlebovits/phl-housing-demo) | ArcGIS FeatureServer layers | Daily |
| [pergamino-ide-catalog](https://github.com/nlebovits/pergamino-ide-catalog) | GeoNode, with features from its WFS | Weekly |
| [firms-catalog](https://github.com/portolan-mirrors/firms-catalog) | NASA FIRMS fire detections, an append-only stream | Hourly window, daily merge |

The tools in both are plain Python scripts under `tools/`. Copy what fits. The parts that differ by source are the probe and the cadence lookup. The rest is shared.

## Compute for the job

This is the open question. phl-housing-demo, pergamino-ide-catalog, and firms-catalog each run on a free GitHub-hosted runner. That works while the largest unit of work fits on one runner in one job.

| Option | Status | Fits |
|---|---|---|
| [GitHub-hosted runner](https://docs.github.com/en/actions/reference/runners/github-hosted-runners), public repository | Used by all three reference catalogs | One collection's source download, GeoParquet, PMTiles, and archived version fit in 14 GB of disk and 16 GB of memory, within the [job time limit](https://docs.github.com/en/actions/reference/limits). A private repository gets 2 CPUs and 8 GB of memory |
| Larger GitHub runner | Not tried | More disk, memory, and CPU on the same workflow. Paid |
| Self-hosted runner | Not tried | The same workflow on a machine you control. You maintain the machine |
| Cloud batch job, started by a cloud scheduler | Not tried | Large extracts. The job can run in the bucket's region and avoid egress charges. The workflow logic moves out of GitHub Actions |

firms-catalog splits large work into small units that each fit on a free runner:

* One year of detections is about 1 GB of GeoParquet and 1.3 GB of PMTiles. The year build peaks at about 3 GB of disk and has a 300-minute timeout.
* The historical backfill is about 24 hours of API calls. A matrix runs one sensor-year per job, and each job averages 26 minutes, inside the 6-hour job limit. The jobs run one at a time, because the API rate limit applies to the key across all jobs.
* The backfill jobs get no cloud credentials. They pass their output to a short publish job as workflow artifacts. A Source Cooperative session token expires long before a 24-hour run ends.
* Later jobs read the published data back from the bucket, one year at a time. The full archive is 9 GB, and a runner has 14 GB of disk.

Measure before you choose. Run the extract of the largest collection by hand, and record the time, the peak disk use, and the peak memory. Tippecanoe and the archive download often need more disk than the extract itself.

A source with millions of rows may be too slow to extract in full on every change. Some ArcGIS layers have a per-row edit date field, and a query on that field returns only the changed rows. No reference catalog does incremental extraction yet. A merge of changed rows into the current GeoParquet needs a stable row key from the source.

GitHub disables a scheduled workflow in a public repository after 60 days with no repository activity. The job commits only when a source changes. A quiet source can let the schedule lapse. Watch for it, or give the job a reason to commit.

## Steps in each run

For a layer that the publisher edits in place, the script walks every collection in a source list (`tools/sources.json` in phl-housing-demo and pergamino-ide-catalog):

1. **Probe** the source. One request reads the time of the last edit, and one reads the row count. See [Source signals](#source-signals).
2. **Decide** whether the collection is due. See [Due collections](#due-collections). Most runs extract nothing.
3. **Extract** the due collection to a scratch directory. Repair invalid geometries and sort the rows on a Hilbert curve. Read the row count before and after the extract. When the two differ, the publisher edited during the extract. Discard it and let the next run retry.
4. **Compare** an order-independent hash of every row with the current version. Equal rows mean the source touched nothing that matters. Record the check and publish nothing. See [Skip versions that change nothing](#skip-versions-that-change-nothing).
5. **Check the styles** against the new rows. A styled column that is gone, a category that held rows and now holds none, or a new value with no category holds the collection back. The `portolan-bootstrap` skill explains [why every legend entry must match the data](../portolan-bootstrap/SKILL.md#the-legend-rule).
6. **Archive** the outgoing current file. Download it from the bucket, check it against the `file:checksum` in `collection.json`, and stage it as an earlier version. See [Versions](#versions).
7. **Record** the new version in `collection.json`, write the new GeoParquet and PMTiles, and render a new thumbnail. pergamino-ide-catalog renders with chiitiler, the renderer that the `portolan-thumbnails` skill documents. A render that fails the blank check keeps the previous image.
8. **Gate** the result with the same checks CI runs on a pull request. The `git-backed-catalog` skill covers [the documented-query checks](../git-backed-catalog/SKILL.md#test-the-documented-queries-and-claims).
9. **Publish** the archives first and the new data next. Upload the metadata last. Then run every documented query against the bucket.
10. **Commit** the published metadata to the default branch from a separate job.

A collection that fails at any step rolls back. Its folder and its staged files return to their state before the run. The other collections still publish. The job then fails and opens an issue, or comments on the open one.

## Append-only streams

Some sources only add rows. Fire detections, sensor readings, and event feeds never edit a past row. A full re-extract of such a source grows without limit, and a content hash gives no benefit. firms-catalog uses a different layout:

* Partition the collection by year (`year=<Y>/`). A finished year never changes, so its files and tiles are built once.
* An hourly job rewrites one small file, `year=<Y>/live.parquet`, from the source's rolling recent window. The hourly upload is about 34 MB instead of the whole year.
* A daily job merges the window into the year's `detections.parquet` and rebuilds that year's tiles.
* The hourly job commits nothing to git. It regenerates the extents, the row counts, and `updated`, and uploads them. Git stores only the stable catalog definition.

The window moves forward and the archive does not. When the hourly job stops for longer than the window, rows age out of the feed before any file stores them. Every job still passes, and the total row count still climbs. This happened once: the hourly job failed from 2026-09-16 to 2026-09-21, and 42 hours of detections left the feed. Before each merge, firms-catalog now checks every hour of the year against the archive and the window. It refetches each missing hour from the source's API, and it fails the run when a refetch returns no data for a missing hour.

A job that commits nothing gives GitHub no repository activity. Check the 60-day schedule rule in [Compute for the job](#compute-for-the-job).

## Source signals

The probe must be cheap. A job that probes a thousand layers daily cannot extract each one to find out whether it changed.

| Source | Edit signal | Count signal | Cadence | Known traps |
|---|---|---|---|---|
| ArcGIS FeatureServer | `editingInfo.dataLastEditDate` on the layer's `?f=json` | `query?where=1=1&returnCountOnly=true` | None in the service. Look for a cadence on the publisher's open data page, such as the "Update Frequency" field on OpenDataPhilly | `lastEditDate` also moves on a schema edit. Use `dataLastEditDate`, and fall back to `lastEditDate` only when the first is absent. A layer with edit tracking off has no `editingInfo`. ArcGIS Online throttles bursts, so retry with a growing pause. |
| NASA FIRMS | None. The bulk CSV feeds are regenerated on a schedule. On 2026-09-07 they were 20 to 29 minutes old, and detections appeared about 2 h 37 min after observation | Not used | The feed's own schedule. firms-catalog runs hourly | The bulk CSV feeds need no API key and cost no API calls. The area API needs a key and limits each key to 5,000 transactions per 10 minutes. A whole-globe one-day request costs 36 |
| GeoNode | `last_updated` from `/api/v2/datasets` | WFS `GetFeature` with `resultType=hits` | `maintenance_frequency` on the dataset record | GeoNode moves `last_updated` only when a save goes through GeoNode. An edit made directly in the database behind GeoServer leaves it unchanged. Treat a changed count as a change too, and rely on the row hash for the rest. GeoServer ignores `srsName=EPSG:4326` for a layer whose CRS list lacks it, and answers in the native CRS. Check the CRS the extract declares. |

No other source type has a reference implementation yet. CKAN, Socrata, plain WFS, and OGC API Features each expose different signals, and some expose none. When a source has no edit signal, compare the row count and the row hash on every run. Report what you learn about a new source so it can join this table.

## Due collections

A collection is due when both conditions hold:

* The edit signal moved past the current version, or past the last check that changed nothing.
* At least `min_days` have passed since the current version.

`min_days` stops a layer that the publisher touches every day from producing a version every day. Take it from the cadence the publisher states. A publisher who edits daily but states a weekly cadence gets weekly versions. Use 7 when the publisher states nothing. Record the source of each value, because the version history later shows the real cadence and the value should follow it.

pergamino-ide-catalog maps GeoNode's `maintenance_frequency`, an ISO 19115 code, like this:

| `maintenance_frequency` | `min_days` |
|---|---|
| `continual`, `daily`, `weekly`, `asNeeded`, `irregular`, `notPlanned`, `unknown` | 7 |
| `fortnightly` | 14 |
| `monthly` and longer | 28 |

phl-housing-demo sets each value by hand in `tools/sources.json`, next to the stated cadence and the URL of the page that states it (`frequency_source`). Its one "as needed" layer gets a `min_days` of 1, not 7. The catalogs disagree on "as needed". Choose per layer, and record the reason next to the value.

The first version of a collection is always due. With the force flag, a run ignores both conditions. It still publishes nothing when the rows hash the same.

## Skip versions that change nothing

An edit signal says the source was saved, not that the rows changed. Hash the rows to find out. The hash must ignore row order, because a service can return the same rows in a different order. It must also give one value for two repairs of the same geometry. Normalize geometry before you hash it. Both reference catalogs use DuckDB with the spatial extension:

```sql
SELECT sum(hash(t)::HUGEINT)::VARCHAR || ':' || count(*)
FROM (
  SELECT * REPLACE (ST_AsWKB(ST_Normalize(geometry)) AS geometry)
  FROM read_parquet('data.parquet')
) AS t;
```

A sum of per-row hashes ignores order. An XOR of the same hashes would also ignore order, but a duplicated row would cancel itself out. The normalization matters in practice. In phl-housing-demo, 29 repaired rows in one layer made an unchanged source look changed until the hash normalized geometry. Store the hash on the version asset, and compare the new extract against it.

## Versions

Portolan has no settled model for earlier versions of collection data yet. [portolan-cli#1131](https://github.com/portolan-sdi/portolan-cli/issues/1131) tracks the decision. Until the issue closes, both reference catalogs use one layout, which they write with their own scripts:

| Path | Content | Changes |
|---|---|---|
| `<coll>/<coll>.parquet` | The current version | Every new version |
| `<coll>/<coll>.pmtiles` | Tiles for the current version | Every new version |
| `<coll>/versions/<version>.parquet` | An earlier version | Never |
| `<coll>/collection.json` | One asset per version | Every new version |

The asset named after the collection is the current version. Its URL never changes. Each earlier version is an asset named `version-<version>` with the role `archive`. The version label is the UTC date of the extract, and a second forced run on one day gets `<date>-2`.

Never overwrite an object under `versions/`, and upload every archive before you replace any current file. With that order, a failed upload cannot lose the only copy of a version. A checksum mismatch on the archived file means that another process wrote to the bucket, and you must find that process before you continue.

When you set up automated updates, report what the layout cost you on #1131. The maintainers use that issue to choose the Portolan model.

## Dates in the metadata

`updated` on each mirrored catalog and collection records the time of the last sync from the source (PORTO-CORE-057). Put the source's own edit date in a separate field on each version asset and on the collection. The reference catalogs use a prefixed field, `phl:source_updated` and `pergamino:source_updated`. Until the spec defines a common field for this date, choose a name for your catalog and document it.

Set the root catalog's `updated` to the newest collection `updated` below it.

## Numbers and dates in the documentation

Each re-extraction changes the data, but nothing rewrites the prose. A phrase such as "29,198 parcels" or "extracted 2026-08-26" in a README is wrong after the next version.

* Quote no numbers measured from the data. Point to `table:row_count` in `collection.json` and give a query.
* Name no extraction date. Point to the version list in `collection.json`. A sentence about the first version may keep its date, because the first version never changes.

Enforce both rules with tests that run before every upload. The reference catalogs have `tests/test_no_data_numbers.py` and `tests/test_no_stale_dates.py`.

## The scheduled workflow

Both reference catalogs run the scripts as a GitHub Actions workflow, `.github/workflows/refresh.yml`.

* **Schedule** the run after the publisher's working day, so it sees the full previous day of edits. Check when edits arrive before you pick a time.
* **Allow one writer.** The scheduled job and the metadata publish workflow share a concurrency group, so they never run at once.
* **Request credentials late.** Sign in after the extract. The short-lived token then covers only the upload. Use the provider's workload identity federation. Store no key. Both reference catalogs document the Source Cooperative setup in the Credentials section of their `docs/refresh.md`.
* **Separate the commit.** A second job with `contents: write` and no cloud credentials commits the published metadata. A run that published and then failed to commit leaves the bucket ahead of git. The publish workflow must detect that and stop.
* **Report failures.** A third job opens one issue for a failed run, or comments on the open one.
* **Offer manual inputs.** Accept a list of collections and a force flag. Add a dry run that prints what is due and why.

## New and removed datasets

Never add a dataset to the catalog because it appeared at the source. A public portal can hold records about private people, and every layer needs a data review before it is mirrored. Report a new dataset as a notice in the refresh issue. A dataset that the source removes stays in the catalog at its last version, and the notice says so.

## Failure handling

| Situation | Action |
|---|---|
| The probe fails | Skip the collection. The next run retries |
| The row count moved during the extract | Discard the extract. The next run retries |
| The new rows break a style | Hold the collection back. Fix the style against the new rows, then rerun that collection |
| The archived file does not match its checksum | Stop. Something outside the scheduled job wrote to the bucket |
| The bucket holds a version that is missing from git | A run published and failed to commit. Commit the run's saved metadata, then rerun |
| The source has no edit signal | Compare the row count and the row hash on every run |
| A step in this skill fails for your source | Open a pull request against this skill |
