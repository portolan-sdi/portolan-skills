---
name: refresh-catalog
description: Re-extract a mirrored Portolan catalog from its live source on a schedule. Probe each source with two small requests, re-extract only the collections whose source changed, publish each change as a new version, and run the refresh in CI. Work in progress. Use when someone wants a mirror of an ArcGIS, GeoNode, WFS, or similar service to follow its source, or asks how to detect upstream changes.
---

<!-- drift: depends-on: portolan-cli, portolan-spec -->

# Refresh a mirrored catalog

> **This skill is a work in progress.** Each source type in this skill has exactly one reference catalog behind it, and a new source can break any step. Report a step that fails for your source, a source behavior this page omits, or a better signal. A pull request against this skill is the most useful report. An issue in [portolan-skills](https://github.com/portolan-sdi/portolan-skills/issues) also helps. Use the pattern with care, and check each step against the source in front of you.

A mirror matches its source on the day of the build. The source changes after that. In this skill, a scheduled job probes each source and extracts only the collections that changed. Each change becomes a new version, and the earlier versions remain in the bucket unchanged.

Build the catalog first. The `portolan-bootstrap` skill builds it, and the `git-backed-catalog` skill puts its metadata in a repository with CI. This skill adds the refresh on top of both. It assumes that git stores the metadata, because git records every version that the refresh publishes.

## Reference implementations

phl-housing-demo and pergamino-ide-catalog built this pattern independently and reached the same design. Read the one closer to your source before you write code. Each has a `docs/refresh.md` that explains every step and every failure.

| Catalog | Source | Schedule |
|---|---|---|
| [phl-housing-demo](https://github.com/nlebovits/phl-housing-demo) | ArcGIS FeatureServer layers | Daily |
| [pergamino-ide-catalog](https://github.com/nlebovits/pergamino-ide-catalog) | GeoNode, with features from its WFS | Weekly |

The tools in both are plain Python scripts under `tools/`. Copy what fits. The parts that differ by source are the probe and the cadence lookup. The rest is shared.

## The refresh, step by step

Each run walks every collection in a source list (`tools/sources.json` in both catalogs):

1. **Probe** the source. One request reads the time of the last edit, and one reads the row count. See [Source signals](#source-signals).
2. **Decide** whether the collection is due. See [Due collections](#due-collections). Most runs extract nothing.
3. **Extract** the due collection to a scratch directory. Repair invalid geometries and sort the rows on a Hilbert curve. Read the row count before and after the extract. When the two differ, the publisher edited during the extract. Discard it and let the next run retry.
4. **Compare** an order-independent hash of every row with the current version. Equal rows mean the source touched nothing that matters. Record the check and publish nothing. See [Skip versions that change nothing](#skip-versions-that-change-nothing).
5. **Check the styles** against the new rows. A styled column that is gone, a category that held rows and now holds none, or a new value with no category holds the collection back. The `portolan-bootstrap` skill explains [why every legend entry must match the data](../portolan-bootstrap/SKILL.md#the-legend-rule).
6. **Archive** the outgoing current file. Download it from the bucket, check it against the `file:checksum` in `collection.json`, and stage it as an earlier version. See [Versions](#versions).
7. **Record** the new version in `collection.json`, write the new GeoParquet and PMTiles, and render a new thumbnail with the `portolan-thumbnails` skill. A render that fails the blank check keeps the previous image.
8. **Gate** the result with the same checks CI runs on a pull request. The `git-backed-catalog` skill covers [the documented-query checks](../git-backed-catalog/SKILL.md#test-the-documented-queries-and-claims).
9. **Publish** the archives first and the new data next. Upload the metadata last. Then run every documented query against the bucket.
10. **Commit** the published metadata to the default branch from a separate job.

A collection that fails at any step rolls back. Its folder and its staged files return to their state before the run. The other collections still publish. The job then fails and opens an issue, or comments on the open one.

## Source signals

The probe must be cheap. A refresh that probes a thousand layers daily cannot extract each one to find out whether it changed.

| Source | Edit signal | Count signal | Cadence | Known traps |
|---|---|---|---|---|
| ArcGIS FeatureServer | `editingInfo.dataLastEditDate` on the layer's `?f=json` | `query?where=1=1&returnCountOnly=true` | None in the service. Look for a cadence on the publisher's open data page, such as the "Update Frequency" field on OpenDataPhilly | `lastEditDate` also moves on a schema edit. Use `dataLastEditDate`, and fall back to `lastEditDate` only when the first is absent. A layer with edit tracking off has no `editingInfo`. ArcGIS Online throttles bursts, so retry with a growing pause. |
| GeoNode | `last_updated` from `/api/v2/datasets` | WFS `GetFeature` with `resultType=hits` | `maintenance_frequency` on the dataset record | GeoNode moves `last_updated` only when a save goes through GeoNode. An edit made directly in the database behind GeoServer does not move it. Treat a changed count as a change too, and rely on the row hash for the rest. GeoServer ignores `srsName=EPSG:4326` for a layer whose CRS list lacks it, and answers in the native CRS. Check the CRS the extract declares. |

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

When you build a refresh, report what the layout cost you on #1131. The maintainers use that issue to choose the Portolan model.

## Dates in the metadata

`updated` on each mirrored catalog and collection records when the mirror last synced from its source (PORTO-CORE-057). It does not record when the source changed. Put the source's own edit date in a separate field on each version asset and on the collection. The reference catalogs use a prefixed field, `phl:source_updated` and `pergamino:source_updated`. Until the spec defines a common field for this date, choose a name for your catalog and document it.

Set the root catalog's `updated` to the newest collection `updated` below it.

## Numbers and dates in the documentation

Each refresh changes the data, but nothing rewrites the prose. A phrase such as "29,198 parcels" or "extracted 2026-08-26" in a README is wrong after the next version.

* Quote no numbers measured from the data. Point to `table:row_count` in `collection.json` and give a query.
* Name no extraction date. Point to the version list in `collection.json`. A sentence about the first version may keep its date, because the first version never changes.

Enforce both rules with tests that run before every upload. The reference catalogs have `tests/test_no_data_numbers.py` and `tests/test_no_stale_dates.py`.

## The scheduled workflow

Both reference catalogs run the refresh as a GitHub Actions workflow, `.github/workflows/refresh.yml`.

* **Schedule** the run after the publisher's working day, so it sees the full previous day of edits. Check when edits arrive before you pick a time.
* **Allow one writer.** The refresh and the metadata publish workflow share a concurrency group, so they never run at once.
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
| The archived file does not match its checksum | Stop. Something outside the refresh wrote to the bucket |
| The bucket holds a version that git does not | A run published and failed to commit. Commit the run's saved metadata, then rerun |
| The source has no edit signal | Compare the row count and the row hash on every run |
| A step in this skill fails for your source | Open a pull request against this skill |
