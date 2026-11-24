# Conformance Addendum for a Migrated Catalog

<!--
The catalog template ships docs/conformance.md. It records the rashid version
floor, the empty ACCEPTED set, and the stac-check exemption. Start from that
file. Add the section below only when the catalog has a partitioned collection
whose `partition:glob` is remote or absolute. Replace every <PLACEHOLDER>.
-->

## Checks the CI Gate Omits

`tests/test_conformance.py` runs rashid with `--no-data`. The
`<PLACEHOLDER: collection>` publishes its partitions through
`<PLACEHOLDER: s3://... glob>` (PORTO-FMT-064).

`tools/validate_with_data.py` runs the data checks before every publish. It
rewrites the glob to a local relative pattern in a throwaway tree and
symlinks the partitions. Expect `PTL-PRT-002` at `/partition:glob` of the
rewritten collection. Judge the data pass on `PTL-DAT-*` findings and fail on
any other error. Keep `PTL-PRT-002` out of `ACCEPTED`.

After publishing, run `rashid check "$CATALOG_URL" --data-scope all` to list
the bucket glob anonymously and sample the partition footers.

<!-- A maintainer copies this record and fills the placeholders. "no
     error-severity finding" is the result the record states, so the
     positive form the rule asks for would change what the record claims. -->
<!-- vale ai-tells.ContrastiveNegation = NO -->
Last run on <PLACEHOLDER: YYYY-MM-DD> against rashid
<PLACEHOLDER: version>: <PLACEHOLDER: N> partitions, one schema, largest row
group <PLACEHOLDER: N> rows, no data errors.
<!-- vale ai-tells.ContrastiveNegation = YES -->

A negative control on the same date, a partition with a row group over the
150,000-row cap (PORTO-FMT-009), made `PTL-DAT-008` fire at
`/partition:glob`.

<!--
When you accept a deviation, add a row and a section explaining it, like this:

| Rule | Where | Why accepted | Tracking |
|---|---|---|---|
| <PTL rule id> | <where it fires> | <why the catalog cannot satisfy it yet> | <org/repo#N> |

Then add the rule id to ACCEPTED in tests/test_conformance.py. Both, or
neither.
-->
