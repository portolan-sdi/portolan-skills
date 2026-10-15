# Catalog grader rubric

This file is the rubric. `SKILL.md` is the procedure. The grades are A+, A, B, C, D, and F.

rashid decides conformance, which is pass or fail. This rubric grades what a validator cannot check, such as whether the documents are honest and whether a stranger can use the data. A catalog can pass the validator and still be of no use to anyone ([Sundwall, 2025](https://radiant.earth/blog/2025/11/great-data-products/)).

The standards behind each area live in the spec's best-practices guidance. This file cites them and does not restate them:

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

A grade can only go down from step 3 to step 6. Polish in one area does not make up for a defect in another, because the consumer who depends on the broken part never sees the polish.

## Invented claims

An invented claim is a specific statement that a reader would act on and that the evidence does not support. It can appear in any prose the catalog publishes. Column descriptions and link titles count as prose. It is one of two kinds.

**Contradicted.** The data, the metadata, or the cited source says otherwise. Examples:

- A README count that differs from `table:row_count`.
- A license in prose that differs from the JSON.
- A query comment that states a result the query does not return.
- A claim check that returns rows (`claim_holds: false` in `facts.claim_checks`).
- A code meaning that the publisher's code list defines differently.

**Unsupported.** No tier supports it. The source's metadata does not state it, no citation backs it, and the data cannot derive it. The [bootstrap skill](../../portolan-bootstrap/SKILL.md#record-the-source-of-every-claim) defines the three tiers: attested, researched and cited, and derived. Examples:

- A decoded meaning for an integer code, with no code list cited.
- An accuracy figure with no validation source.
- A named user or use with no link.
- A coverage claim, such as "complete" or "authoritative", that the data does not show.

These are not invented claims:

- A vague statement, such as "useful for planning". Grade it under concision.
- A claim the grader could not check because a source did not answer. Record it as unverified.
- A gap stated as a gap, such as "the publisher has not released a code list". That is the correct behavior and gets credit.

An invented claim counts only when the report gives its evidence. The evidence is the exact quote, its location, and what the grader checked.

A wrong claim costs more than a missing one. Leave a column undescribed and the area loses a little, while a wrong description triggers the cap. It is always better for a catalog to say nothing than to make something up.

## Areas

### 1. Machine contract

This area covers what agents and validators read, beyond the rashid errors that set the ceiling.

- **A.** rashid reports no warnings. Each `table:columns` entry has a description, and coded columns are decoded. Providers include `processor` and `licensor` where they apply (PORTO-CORE-048). A mirror lists the original download as a `source` asset when one exists (PORTO-FMT-002), and links the upstream STAC with `canonical` when it exists (PORTO-CORE-054). When geometry and attributes are in separate files, the docs give the join columns and a working example (PORTO-FMT-038).
- **B.** A few rashid warnings, or some columns without descriptions.
- **D.** Warnings across most collections, coded columns copied through undecoded, or a required join left undocumented.

### 2. Honesty and drift

This area covers whether the prose is correct today, and whether it will be correct after the next update.

- **A.** The grader found a source for each claim it checked. Numbers in prose agree with the metadata and the data. Counts, sizes, and dates in prose come from a generator, or the docs give the query that measures them instead. Claims about the data have claim checks. Gaps are stated as gaps.
- **B.** The claims are correct today, but hand-written counts, sizes, or "as of" dates will drift on the next update.
- **D.** The prose contradicts the metadata or the data. A license, a count, the list of collections, or a stated query result disagrees.

The honesty cap in step 4 applies on top of this area grade.

### 3. Documentation

This area covers whether a reader can decide in one screen to trust and use the data. See documentation.md.

- **A.** Each collection README is a narrative. It says what the data is, who made it, how many features it has, and its vintage. Its prose links the source paper, the agency page, the program, and the documentation. It has a described schema table and one Quick Start. It states the known issues and limitations of the data. Each AGENTS.md is specific to its dataset. It gives the join keys, the CRS and its cost to a consumer, the quirks that the schema cannot express, query recipes, related collections, and provenance. Catalog-level READMEs are tables of contents. Each README points agents at its AGENTS.md.
- **B.** The docs exist at each level and are accurate, but thin. Examples are a schema restatement without quirks, and data with known issues that the docs do not mention.
- **D.** A level has no docs, a CLI stub or template text remains, or the text is generic enough to describe any dataset.

### 4. Access

This area covers whether the documented code runs and shows something useful. Read `facts.queries`, which lists each SQL and Python block the script ran. A block with `environment_error: true` failed because the grader could not install an extension or a package. Do not count it against the catalog.

- **A.** The docs of each collection give at least one query or program against the published URL that runs, with a stated result that matches the real one. Where the data supports it, the docs also show one advanced pattern, such as the partition glob or a cross-collection join.
- **B.** The code runs, but it is basic, or it reads relative paths. A SQL path the script resolved shows in `relative_paths_resolved`. A Python block that failed on a relative path shows `missing_file: true`. The docs should use the published URL.
- **D.** The documented code fails, all or most of it, or the docs give none.

### 5. Visuals

This area covers thumbnails, styles, and the first view. View each saved thumbnail. Do not grade a thumbnail from its facts alone.

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

This area covers whether a reader can find things in the tree. See philosophy.md.

- **A.** One dataset per collection. Related collections sit in sub-catalogs when a level has many children, grouped by steward or by the publisher's own topics. Depth is uniform. Ids are short, lowercase, and free of pipeline artifacts. Titles describe.
- **B.** One odd grouping, or an id that contains a pipeline artifact.
- **D.** Several datasets packed into one collection as sibling assets, a long flat list a reader cannot scan, or a taxonomy the grader cannot follow.

### 7. Maintenance

This area covers whether the catalog will remain correct as its sources change.

- **A.** `updated` is current on each mirrored object. Provenance links (`via`, `canonical`) point at specific upstream pages. The host is reachable by URL or email. Each catalog and collection has the links of the [navigation contract](../../portolan-bootstrap/reference/catalog-navigation.md). The docs come from a generator, or agree with the metadata at each level.
- **B.** `updated` lags, or appears only at some levels. Docs are hand-maintained and agree today.
- **D.** `updated` is null across a mirror, no contact route exists, or links return 404 at scale.

### 8. Concision

This area covers whether each sentence is necessary. Length is not the defect. Padding is. A long list of real quirks is never penalized.

- **A.** Each doc says each thing once. AGENTS.md does not restate extents, licenses, or row counts from the JSON. The docs are free of filler, hype, and boilerplate copied across collections (`agents_similarity`).
- **B.** Some padding, or repeated sections across collections.
- **D.** Most collection docs are near copies of each other (similarity 0.9 or more), or padding buries the useful content.

## A requirements

An A catalog is one a stranger can find, trust, and correct. Record each requirement as met, not met, or unknown in `a_requirements`. Unknown counts as not met, so a catalog graded without its repository gets B or lower.

- `git`: the catalog is built from the git repository the grader was given, and the root has `vcs` and `issues` links that match it.
- `ci`: CI runs rashid on each pull request (`facts.repo.ci_validates_on_pull_request`). CI also runs the documented code and claim checks against the published data on a schedule, as the [git-backed-catalog skill](../../git-backed-catalog/SKILL.md#test-the-documented-queries-and-claims) describes (`facts.repo.ci_checks_docs_on_schedule`). Read the workflow and the test to confirm both facts.
- `logo`: the root has an `icon` link to a logo that loads and is clear at small size.
- `registry`: the catalog is in the Portolan registry (`facts.registry.registered`). When the grade is for a registry submission (`facts.registry.submission`), the requirement is met, because the catalog cannot be in the registry before the submission merges.

## A+ requirements

A+ is for a catalog that a stranger would choose over the alternatives. Record each requirement in `a_plus.requirements`, the same way.

- `rashid-clean`: rashid reports no errors and no warnings.
- `candid`: the docs evaluate the data as the [Candid Core Framework](https://lettersfromthreadedfoundry.substack.com/p/candid-core-framework) describes. Where they apply, the docs give these:
  - Suggested uses grounded in real applications.
  - Inappropriate uses.
  - Quantified accuracy, with uncertainty published as data.
  - Named biases, with mitigations.
  - Cited definitions.
- `narrative`: the READMEs describe the world the data represents, not only its schema.
- `experience`: the thumbnails pass the visual gate and the styles show different aspects of the data. An advanced access pattern runs.

An A+ catalog has no invented claims, because one invented claim caps the grade at C.
