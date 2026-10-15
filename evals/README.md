# Skill evals

An eval measures whether a skill does its job, so a change to the skill can show that it helps. Each eval has four parts:

- **Cases.** Real inputs the skill runs on, in `cases.json`.
- **Frozen inputs.** Anything a case needs that changes over time, such as a published catalog, is captured once and versioned, so two runs of the eval read the same bytes.
- **Gold.** What a correct result contains for each case, in `gold.json`. A maintainer confirms each entry.
- **A runner and a scorer.** The runner starts headless Claude Code with this plugin on each case. The scorer turns each result into metrics.

| Path | Holds |
|---|---|
| `evals/<skill>/` | One eval: cases, gold, runner, scorer, and its README |
| `evals/<skill>/frozen.lock` | The release and checksum of the frozen inputs |
| `evals/_lib/frozen.sh` | Packs and fetches frozen inputs |
| `evals/_lib/build-report-lite.mjs` | Builds `report.html` from a run |
| `.claude/hillclimb/<skill>/` | Run output: one directory per variant (`baseline`, `v1`, ...) |

The frozen inputs are too large for git. Each version is a tarball on a release of this repository named `evals-<skill>-frozen-v<N>`.

## Publish frozen inputs

A maintainer with write access publishes each version of an eval's frozen inputs. v1 of the catalog-grader inputs was published this way on 2026-10-15.

1. Read `cases/NOTICE.md`, which `frozen.sh pack` writes into the tarball. It lists the source, license, and licensor of each case. The copies keep their publishers' licenses, not this repository's Apache-2.0. Remove a case whose license does not allow redistribution, and record the decision in the pull request.
2. Commit `frozen.lock` and push. The release tag must point at a pushed commit that holds this `frozen.lock`.
3. Create the release as a pre-release, with `NOTICE.md` as its notes. GitHub needs the full commit SHA.

   ```bash
   gh release create evals-catalog-grader-frozen-v1 \
     evals/catalog-grader/dist/catalog-grader-frozen-v1.tar.gz \
     --prerelease --target "$(git rev-parse HEAD)" \
     --title "catalog-grader eval: frozen inputs v1" \
     --notes-file evals/catalog-grader/cases/NOTICE.md
   ```

4. Check the release from a clean directory. `fetch` verifies the sha256 in `frozen.lock`.

   ```bash
   evals/_lib/frozen.sh fetch evals/catalog-grader
   ```

Never replace the asset of a published version. Publish the next version instead, so an old `frozen.lock` keeps fetching the bytes it names.

## Improve a skill with its eval

1. Fetch the frozen inputs and run the baseline. The eval's README gives the commands.
2. Change the skill. Change one thing at a time, so a score change traces to it.
3. Run the change as the next variant (`--variant v1`), and compare the two in `report.html`.
4. Paste the summary of both variants into the pull request's Verification section.

`/claude-api hillclimb` in Claude Code automates this loop. It holds back a random test set, and it reverts any change that does not also improve those held-out cases.

The pull request that changes a skill should not also change its gold. Change gold in its own pull request, with the reason for each edit.

## Evals

- [catalog-grader](catalog-grader/README.md)

To add an eval for another skill, run `/claude-api build-eval` in Claude Code, and follow the layout above.
