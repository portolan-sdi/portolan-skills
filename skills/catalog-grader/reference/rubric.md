# Catalog grader rubric

rashid checks whether a catalog conforms to the specification. Use this rubric with the [catalog review procedure](../SKILL.md) to grade its quality from A+ to F. The criteria come from the specification's guidance for:

- [README and AGENTS.md content](https://github.com/portolan-sdi/portolan-spec/blob/main/specs/best-practices/documentation.md).
- [Data styles](https://github.com/portolan-sdi/portolan-spec/blob/main/specs/best-practices/styling.md).
- [Catalog scope, structure, names, and maintenance](https://github.com/portolan-sdi/portolan-spec/blob/main/specs/best-practices/philosophy.md).
- [Git repositories and CI](https://github.com/portolan-sdi/portolan-spec/blob/main/specs/best-practices/git-backed-catalogs.md).

## Compute the grade

Apply these steps in order. Record each step in the report's `computation` field.

1. **Set the grade limit (`ceiling`).** Read `facts.rashid`.
   - For an unreadable root or a root that is not a STAC catalog (`PTL-GEN-000` or structural errors on most objects), assign **F** and stop.
   - If rashid reports errors, limit the grade to **D**.
   - If rashid did not run, limit the grade to **C** and mark the report incomplete.
   - Otherwise, apply no limit.
2. **Grade each area.** Assign A, B, C, or D using the criteria below. Use C when the findings fall between the B and D criteria.
3. **Combine the area grades.** Start with the lowest area grade. If at least five of the other seven areas have an A, raise the overall grade one step, up to A.
4. **Honesty cap.** One invented claim caps the grade at **C**. Two or more cap it at **D**.
5. **Apply the grade limit** from step 1.
6. **Check the A requirements.** If the grade is A but the catalog does not meet every [A requirement](#a-requirements), lower it to **B**.
7. **Check the A+ requirements.** If the grade is still A and the catalog meets the [A+ requirements](#a-requirements-1), award **A+**. Otherwise, leave the grade unchanged.

## Invented claims

An invented claim is a statement a reader could act on that the evidence does not support. Check column descriptions and link titles as well as documents. Use one of these two kinds:

**Contradicted:** The statement disagrees with the data, metadata, or cited source. Examples include:

- A README count that differs from `table:row_count`.
- A license in prose that differs from the JSON.
- A query comment that describes a result the query does not return.
- A claim check that returns rows (`claim_holds: false` in `facts.claim_checks`).
- A code meaning that the publisher's code list defines differently.

**Unsupported:** No source supports the claim under the [bootstrap skill's evidence criteria](../../portolan-bootstrap/SKILL.md#record-the-source-of-every-claim). Examples include:

- A decoded meaning for an integer code, with no code list cited.
- An accuracy figure with no validation source.
- A named user or use with no link.
- A coverage claim, such as "complete" or "authoritative", that the data does not show.

These are not invented claims:

- Vague statements such as "useful for planning", which you assess under concision.
- Claims you cannot check because a source does not answer, which you record as unverified.
- Explicit gaps such as "the publisher has not released a code list". Give credit for stating these gaps.

Before counting a claim as invented, record its exact quote, location, and the evidence from your checks. Missing information lowers the relevant area grade, while an invented claim also triggers the honesty cap.

## Areas

### 1. Machine contract

- **A.** rashid reports no warnings. Each `table:columns` entry has a description, and the docs explain what coded values mean. Where applicable, check PORTO-CORE-048, PORTO-FMT-002, PORTO-CORE-054, and PORTO-FMT-038.
- **B.** rashid reports a few warnings, or some columns lack descriptions.
- **D.** Most collections have warnings, coded columns lack explanations, or a required join is undocumented.

### 2. Honesty and drift

- **A.** Each claim you checked has a source, and numbers agree with the metadata and data. Counts, sizes, and dates are generated, or the docs provide queries in their place. The docs include checks for data claims and state any gaps.
- **B.** The claims are correct today, but hand-written counts, sizes, or "as of" dates will drift on the next update.
- **D.** The prose contradicts the metadata or the data. A license, a count, the list of collections, or a stated query result disagrees.

### 3. Documentation

- **A.** Each collection's `README.md` describes the data, creator, feature count, and vintage in prose, with links to its sources. It describes the schema and includes a quickstart and known limitations. Its `AGENTS.md` explains the join keys, coordinate reference system and its implications, quirks, recipes, related collections, and provenance. Catalog READMEs serve as tables of contents, and each README links to its `AGENTS.md`. See the [documentation guidance](https://github.com/portolan-sdi/portolan-spec/blob/main/specs/best-practices/documentation.md).
- **B.** The docs are accurate and present at each level but omit useful details, such as dataset quirks or known issues.
- **D.** A level has no docs, a CLI stub or template text remains, or the text is generic enough to describe any dataset.

### 4. Access

Use `facts.queries` to check the documented examples. If a block has `environment_error: true`, exclude its failure from the grade.

- **A.** Each collection has at least one working query or program that reads a published URL and returns the stated result. Where the data supports it, the docs also show an advanced pattern, such as a partition glob or a join across collections.
- **B.** The examples run but only show basic queries or use relative paths instead of published URLs. Look for `relative_paths_resolved` in SQL results and `missing_file: true` in Python results.
- **D.** Most or all examples fail, or the docs have no examples.

### 5. Visuals

View each saved thumbnail before grading it.

- **A.**
  - Each geospatial collection has a thumbnail that passes the six questions in the [portolan-thumbnails visual gate](../../portolan-thumbnails/SKILL.md#gate-2-visual).
  - Each collection with attributes worth showing has several data-driven styles, with one marked `default`.
  - Each `match` label exists in the data (`legend_checks`).
  - Default palettes differ across sibling collections.
  - Across the catalog, three or more visualizations show different aspects of the data, unless the data is only geometry.
  - No tileset starts above its full-extent zoom (`starts_above_full_extent`).
- **B.** Each collection has a good thumbnail and one default style, with minor defects such as a failed visual check, an undescribed style, or a shared palette.
- **D.** The catalog has at least one of these defects:
  - A geospatial collection with no thumbnail, a blank one, or one that returns 404.
  - A legend that lists values the data does not have.
  - Styles that paint each feature the same flat color.
  - A blank first view, because the tiles start above the full-extent zoom.

### 6. Organization

- **A.** Each collection contains one dataset. Subcatalogs organize large groups by data owner or the publisher's topics at a consistent depth. Titles describe the data, and IDs are short and lowercase without leftover pipeline names. See the [catalog organization guidance](https://github.com/portolan-sdi/portolan-spec/blob/main/specs/best-practices/philosophy.md).
- **B.** One collection has an odd grouping, or an ID includes a leftover pipeline name.
- **D.** A collection mixes datasets as sibling assets, or the catalog's structure is hard to follow because it is too flat or uses unclear categories.

### 7. Maintenance

- **A.** Each mirrored object's `updated` is current, and its provenance links (`via`, `canonical`) identify specific upstream pages. Readers can contact the host through a URL or email. Each catalog and collection has [navigation links](../../portolan-bootstrap/reference/catalog-navigation.md), and the docs are generated or agree with the metadata at every level.
- **B.** Some objects have stale or missing `updated` values, or the docs are maintained by hand and agree with the metadata today.
- **D.** All objects in a mirror have a null `updated`, readers have no way to contact the host, or many links return 404.

### 8. Concision

Check whether the text helps readers use the data. A long list of real quirks is useful and should not lower the grade.

- **A.** Each document states each fact once. `AGENTS.md` does not repeat extents, licenses, or row counts from the JSON. The docs contain no filler, hype, or boilerplate copied across collections (`agents_similarity`).
- **B.** Some text adds no useful information, or sections repeat across collections.
- **D.** Most collection docs are near copies of each other (similarity 0.9 or more), or padding buries the useful content.

## A requirements

Record each requirement in `a_requirements` as met, not met, or unknown. An unconfirmed requirement counts as not met.

- `git`: The provided repository builds the catalog, and the root's `vcs` and `issues` links match it.
- `ci`: CI runs rashid on pull requests (`facts.repo.ci_validates_on_pull_request`) and [documented code and claim checks](../../git-backed-catalog/SKILL.md#test-the-documented-queries-and-claims) against published data on a schedule (`facts.repo.ci_checks_docs_on_schedule`). Confirm both in the workflow and test.
- `logo`: The root has an `icon` link to a logo that loads and is clear at a small size.
- `registry`: The catalog is registered (`facts.registry.registered`). For a submission review (`facts.registry.submission`), waive this requirement.

## A+ requirements

Record each requirement in `a_plus.requirements` as met, not met, or unknown.

- `rashid-clean`: rashid reports no errors and no warnings.
- `candid`: The docs follow the [Candid Core Framework](https://lettersfromthreadedfoundry.substack.com/p/candid-core-framework). Where applicable, they include:
  - Suggested uses grounded in real applications.
  - Inappropriate uses.
  - Quantified accuracy, with uncertainty published as data.
  - Named biases, with mitigations.
  - Cited definitions.
- `narrative`: The READMEs describe the world the data represents, not only its schema.
- `experience`: The thumbnails pass the visual checks and the styles show different aspects of the data. At least one advanced access pattern runs successfully.
