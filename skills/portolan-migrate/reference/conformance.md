# Conformance Addendum for a Migrated Catalog

<!--
The catalog template ships docs/conformance.md. It records the rashid version
floor, the empty ACCEPTED set, and the stac-check exemption. Start from that
file. Add the section below only when the catalog has a partitioned collection
whose `partition:glob` is remote or absolute. Replace every <PLACEHOLDER>.
-->

## Checks the CI Gate Omits

`tests/test_conformance.py` runs rashid with `--no-data`, and rashid expands
`partition:glob` only when the pattern is local and relative. This catalog's
`<PLACEHOLDER: collection>` publishes its partitions through
`<PLACEHOLDER: s3://... glob>`. A remote or absolute glob cannot be listed
from the local tree, so `PTL-DAT-006`, `PTL-DAT-007`, `PTL-DAT-008`,
`PTL-DAT-012`, and `PTL-DAT-014` never reach those files in CI.

`tools/validate_with_data.py` runs those checks before every publish. It builds
a throwaway tree with the glob rewritten to a local relative pattern and the
partitions symlinked in, then runs `rashid check --data-scope all` over it.
<!-- A maintainer copies this record and fills the placeholders. "no
     error-severity finding" is the result the record states, so the
     positive form the rule asks for would change what the record claims. -->
<!-- vale ai-tells.ContrastiveNegation = NO -->
Last run on <PLACEHOLDER: YYYY-MM-DD> against rashid
<PLACEHOLDER: version>: <PLACEHOLDER: N> partitions, one schema, largest row
group <PLACEHOLDER: N> rows, no error-severity finding.
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
