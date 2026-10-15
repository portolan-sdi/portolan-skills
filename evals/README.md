# Skill evaluations

Use these evaluations with the workflow in
[Automating eval design and hillclimbing with Claude](https://claude.dev/blog/automating-eval-design-and-hillclimbing/).
The goal is to build evaluations for every skill and improve both the skills
and their evaluations over time. The current suite covers
[`catalog-grader`](catalog-grader/README.md).

Use `/claude-api build-eval` in Claude Code to design an evaluation for a skill,
with representative tasks and a grader that maintainers review.
Use `/claude-api hillclimb` to improve a skill against its evaluation, one
change at a time. Check results on held-out cases to assess whether an
improvement extends beyond the cases used to guide the edits.

Each evaluation runs test cases against saved inputs and compares the output
with maintainer-approved expected results. To run one, follow the
[catalog-grader instructions](catalog-grader/README.md). The runner saves
results to `.claude/hillclimb/<skill>/<variant>/`.

To compare a skill change, run the unchanged skill as `baseline` and your change
as `v1`. Build `report.html`, then paste both summaries into the pull request's
**Verification** section. If you change the expected results, use a separate
pull request and explain each edit.

## Publish frozen inputs

The `frozen.lock` file pins the published input archive and its checksum.

1. Pack the inputs with `evals/_lib/frozen.sh pack EVAL_DIR VERSION`.
2. Review the sources and licenses in the generated `cases/NOTICE.md` file. If
   a license prohibits redistribution, remove the case and explain why in the pull request.
   The copies retain their publishers' licenses.
3. Commit and push `frozen.lock`. Create a prerelease at that commit with the
   tarball as its asset and `NOTICE.md` as its notes:

   ```bash
   gh release create evals-catalog-grader-frozen-v1 \
     evals/catalog-grader/dist/catalog-grader-frozen-v1.tar.gz \
     --prerelease --target "$(git rev-parse HEAD)" \
     --title "catalog-grader eval: frozen inputs v1" \
     --notes-file evals/catalog-grader/cases/NOTICE.md
   ```

4. Verify the download and checksum from a clean directory:

   ```bash
   evals/_lib/frozen.sh fetch evals/catalog-grader
   ```

Publish a new version when inputs change. Never replace a published asset.
