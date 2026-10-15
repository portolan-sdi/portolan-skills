# Skill evals

Each eval has cases, frozen inputs, maintainer-approved gold, a runner, and a
scorer. See the [catalog-grader eval](catalog-grader/README.md) to run one.
Results go in `.claude/hillclimb/<skill>/<variant>/`.

To compare a skill change, run `baseline` and `v1`, build `report.html`, and
paste both summaries into the pull request's Verification section. Change gold
in a separate pull request with a reason for each edit.

## Publish frozen inputs

`frozen.lock` pins a release tarball and its checksum. To publish a version:

1. Pack the inputs with `evals/_lib/frozen.sh pack EVAL_DIR VERSION`.
2. Review the generated `cases/NOTICE.md` for sources and licenses. Remove
   cases whose licenses prohibit redistribution and explain removals in the pull request.
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
