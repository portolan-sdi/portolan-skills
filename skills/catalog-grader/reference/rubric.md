# Catalog grader rubric

rashid checks conformance. This rubric grades catalog quality from A+ to F. Follow [the skill procedure](../SKILL.md) and the spec's guidance:

- [documentation.md](https://github.com/portolan-sdi/portolan-spec/blob/main/specs/best-practices/documentation.md) for README and AGENTS.md content.
- [styling.md](https://github.com/portolan-sdi/portolan-spec/blob/main/specs/best-practices/styling.md) for styles.
- [philosophy.md](https://github.com/portolan-sdi/portolan-spec/blob/main/specs/best-practices/philosophy.md) for scope, structure, names, and maintenance.
- [git-backed-catalogs.md](https://github.com/portolan-sdi/portolan-spec/blob/main/specs/best-practices/git-backed-catalogs.md) for the repository and CI.

## Compute the grade

Apply these steps in order. Record each step in the report's `computation` field.

1. **Ceiling.** Read `facts.rashid`.
   - The root is unreadable, or is not a STAC catalog (`PTL-GEN-000`, or structural errors on most objects): the grade is **F**. Stop.
   - rashid reports one or more errors: the ceiling is **D**.
   - rashid did not run: the ceiling is **C**, and the report is incomplete.
   - Otherwise there is no ceiling.
2. **Areas.** Give each area below a grade of A, B, C, or D. Each area anchors A, B, and D. A C is a mix of B and D findings.
3. **Combine.** The overall grade is the lowest area grade. Raise it one step when at least five of the other seven areas are A. The raise never goes above A.
4. **Honesty cap.** One invented claim caps the grade at **C**. Two or more cap it at **D**.
5. **Apply the ceiling** from step 1.
6. **A requirements.** A catalog at A after step 5 stays at A only when it meets the full list of [A requirements](#a-requirements). Otherwise it drops to **B**.
7. **A+.** A catalog at A after step 6 gets A+ only when it meets the full list of [A+ requirements](#a-requirements-1). Otherwise it stays at A.

## Invented claims

An invented claim is an unsupported statement a reader could act on, including column descriptions and link titles. It has one of two kinds:

**Contradicted.** The data, the metadata, or the cited source says otherwise. Examples:

- A README count that differs from `table:row_count`.
- A license in prose that differs from the JSON.
- A query comment that states a result the query does not return.
- A claim check that returns rows (`claim_holds: false` in `facts.claim_checks`).
- A code meaning that the publisher's code list defines differently.

**Unsupported.** None of the [bootstrap skill's evidence tiers](../../portolan-bootstrap/SKILL.md#record-the-source-of-every-claim) supports it. Examples:

- A decoded meaning for an integer code, with no code list cited.
- An accuracy figure with no validation source.
- A named user or use with no link.
- A coverage claim, such as "complete" or "authoritative", that the data does not show.

These are not invented claims:

- A vague statement, such as "useful for planning". Grade it under concision.
- A claim the grader could not check because a source did not answer. Record it as unverified.
- An explicit gap, such as "the publisher has not released a code list". Give credit for stating gaps.

Count an invented claim only with an exact quote, its location, and evidence from the grader's checks. Missing information lowers the relevant area grade. An invented claim also triggers the honesty cap.

## Areas

### 1. Machine contract

- **A.** rashid reports no warnings. Each `table:columns` entry has a description, and coded columns are decoded. Check PORTO-CORE-048, PORTO-FMT-002, PORTO-CORE-054, and PORTO-FMT-038 where applicable.
- **B.** A few rashid warnings, or some columns without descriptions.
- **D.** Warnings across most collections, coded columns copied through undecoded, or a required join left undocumented.

### 2. Honesty and drift

- **A.** Each checked claim has a source. Numbers agree with the metadata and data. Counts, sizes, and dates are generated or replaced with queries. Data claims have checks. Gaps are explicit.
- **B.** The claims are correct today, but hand-written counts, sizes, or "as of" dates will drift on the next update.
- **D.** The prose contradicts the metadata or the data. A license, a count, the list of collections, or a stated query result disagrees.

### 3. Documentation

- **A.** Each collection README describes the data, creator, feature count, and vintage in prose, with source links, a described schema, a quickstart, and known limitations. Each AGENTS.md gives dataset-specific join keys, CRS implications, quirks, recipes, related collections, and provenance. Catalog READMEs serve as tables of contents. Each README links to its AGENTS.md. See documentation.md.
- **B.** The docs exist at each level and are accurate, but thin. Examples are a schema restatement without quirks, and data with known issues that the docs do not mention.
- **D.** A level has no docs, a CLI stub or template text remains, or the text is generic enough to describe any dataset.

### 4. Access

Read `facts.queries`. Exclude blocks with `environment_error: true` from the grade.

- **A.** The docs of each collection give at least one query or program against the published URL that runs, with a stated result that matches the real one. Where the data supports it, the docs also show one advanced pattern, such as the partition glob or a cross-collection join.
- **B.** Code runs but is basic or uses relative paths (`relative_paths_resolved` in SQL, `missing_file: true` in Python). Examples should use published URLs.
- **D.** The documented code fails, all or most of it, or the docs give none.

### 5. Visuals

View each saved thumbnail before grading it.

- **A.**
  - Each geospatial collection has a thumbnail that passes the six questions in the [portolan-thumbnails visual gate](../../portolan-thumbnails/SKILL.md#gate-2-visual).
  - Each collection with attributes worth showing has several data-driven styles, with one marked `default`.
  - Each `match` label exists in the data (`legend_checks`).
  - Default palettes differ across sibling collections.
  - Across the catalog, three or more visualizations show different aspects of the data, unless the data is only geometry.
  - No tileset starts above its full-extent zoom (`starts_above_full_extent`).
- **B.** A good thumbnail and one default style per collection, with minor defects. Examples are a thumbnail that fails one question, a style with no description, and siblings that share a palette.
- **D.** One or more of these:
  - A geospatial collection with no thumbnail, a blank one, or one that returns 404.
  - A legend that lists values the data does not have.
  - Styles that paint each feature the same flat color.
  - A blank first view, because the tiles start above the full-extent zoom.

### 6. Organization

- **A.** One dataset per collection. Large groups use subcatalogs organized by data owner or publisher topics. Depth is uniform. IDs are short, lowercase, and free of pipeline artifacts. Titles describe the data. See philosophy.md.
- **B.** One odd grouping, or an id that contains a pipeline artifact.
- **D.** Several datasets packed into one collection as sibling assets, a long flat list a reader cannot scan, or a taxonomy the grader cannot follow.

### 7. Maintenance

- **A.** Each mirrored object's `updated` is current. Provenance links (`via`, `canonical`) identify specific upstream pages. The host is reachable by URL or email. Each catalog and collection has [navigation links](../../portolan-bootstrap/reference/catalog-navigation.md). Docs are generated or agree with the metadata at each level.
- **B.** `updated` lags, or appears only at some levels. Docs are hand-maintained and agree today.
- **D.** `updated` is null across a mirror, no contact route exists, or links return 404 at scale.

### 8. Concision

Judge unnecessary text, not length. Do not penalize long lists of real quirks.

- **A.** Each doc says each thing once. AGENTS.md does not restate extents, licenses, or row counts from the JSON. The docs are free of filler, hype, and boilerplate copied across collections (`agents_similarity`).
- **B.** Some padding, or repeated sections across collections.
- **D.** Most collection docs are near copies of each other (similarity 0.9 or more), or padding buries the useful content.

## A requirements

Record each requirement in `a_requirements` as met, not met, or unknown. Unknown counts as not met.

- `git`: the provided repository builds the catalog, and the root's `vcs` and `issues` links match it.
- `ci`: CI runs rashid on pull requests (`facts.repo.ci_validates_on_pull_request`) and [documented code and claim checks](../../git-backed-catalog/SKILL.md#test-the-documented-queries-and-claims) against published data on a schedule (`facts.repo.ci_checks_docs_on_schedule`). Confirm both in the workflow and test.
- `logo`: the root has an `icon` link to a logo that loads and is clear at small size.
- `registry`: `facts.registry.registered` is true, or `facts.registry.submission` waives this requirement.

## A+ requirements

Record each requirement in `a_plus.requirements` as met, not met, or unknown.

- `rashid-clean`: rashid reports no errors and no warnings.
- `candid`: the docs follow the [Candid Core Framework](https://lettersfromthreadedfoundry.substack.com/p/candid-core-framework), with these where applicable:
  - Suggested uses grounded in real applications.
  - Inappropriate uses.
  - Quantified accuracy, with uncertainty published as data.
  - Named biases, with mitigations.
  - Cited definitions.
- `narrative`: the READMEs describe the world the data represents, not only its schema.
- `experience`: the thumbnails pass the visual gate and the styles show different aspects of the data. An advanced access pattern runs.
