# catalog-grader eval

This eval runs the [catalog-grader](../../skills/catalog-grader/SKILL.md) skill on published catalogs and scores each report. It checks the grade and the findings, the parts of a report that the registry acts on, and the evidence for each finding.

Each case is one catalog. `collect_facts.py` collected its facts once, and the eval froze them. The skill starts at Step 2, and two runs read the same input.

## Metrics

A report passes when all five hard checks hold.

| Metric | Kind | Passes when |
|---|---|---|
| `schema_ok` | hard | `report.json` validates against `report.schema.json` |
| `rules_ok` | hard | The grade follows from the report's area grades, caps, ceiling, and A requirements, and the report marks itself incomplete when the facts require it |
| `quotes_ok` | hard | Every finding's quote appears verbatim in the saved documents or `facts.json` |
| `coverage_ok` | hard | The report read every collection, or at least 12 (Step 3) |
| `in_band` | hard | The grade is in the gold band |
| `key_recall` | judge | Share of the gold key findings the report states |
| `false_invent` | judge | Invented findings whose evidence does not hold |

A second model, the judge, scores the last two. The judge must not be the model under test. `grade.mjs` holds the scoring, and `grade.test.mjs` tests it.

## Requirements

- Node.js 20 or newer, and [uv](https://docs.astral.sh/uv/)
- Claude Code 2.1.300 or newer
- Credentials for the headless sessions. On Linux, a `claude` login works. On macOS, set `CLAUDE_CODE_OAUTH_TOKEN` from `claude setup-token`, or set `ANTHROPIC_API_KEY`.

## Run it

Run these from the repository root.

```bash
evals/_lib/frozen.sh fetch evals/catalog-grader
node evals/catalog-grader/run-eval.mjs \
  --flow .claude/hillclimb/catalog-grader \
  --variant baseline --model claude-opus-5-5 \
  --reps 2 --concurrency 3
node evals/_lib/build-report-lite.mjs \
  .claude/hillclimb/catalog-grader/
python3 evals/catalog-grader/summary.py \
  .claude/hillclimb/catalog-grader/baseline
```

The runner refuses to start when the runner, the scorer, the cases, or the gold changed since a person last approved them. Read the diff, then add `--approve-harness` once.

`CG_EVAL_ONLY=id1,id2` runs only those cases. `CG_EVAL_JUDGE` sets the judge, which is `claude-sonnet-5-5` by default. Set it to `claude-opus-5-5` when the skill runs on Sonnet. `CG_EVAL_REGRADE_FROM=<variant dir>` scores the reports of an earlier run again without running the skill, which you need after a scoring change.

Start the same command again to resume a run. Cases that failed for a reason outside the skill, such as a timeout or an API error, are in `errors.jsonl`, and they run again.

### Cost

On 2026-10-15, one case took 2 to 9 minutes. It cost $1.88 to $4.62 on Opus 5.5 at high effort, and $0.51 to $1.98 on Sonnet 5.5. The judge adds about $0.02 per case.

The **Eval catalog-grader** workflow runs the same commands on a GitHub runner. A maintainer starts it from the Actions tab.

## Change the cases or the gold

The cases and the gold change together with the frozen inputs.

1. Add the case to `cases.json`.
2. Freeze it. The script runs `collect_facts.py` in a Docker container, because it runs code from the catalog's documentation.

   ```bash
   evals/catalog-grader/freeze/freeze.sh <case-id>
   ```

3. Read `cases/<case-id>/frozen/facts.json` and the saved documents. Write the gold entry: a grade band, and the problems a correct report must state. Put who confirmed it in `source`.
4. Pack the next version. The command writes `frozen.lock` and the tarball.

   ```bash
   evals/_lib/frozen.sh pack evals/catalog-grader <N>
   ```

5. Commit `cases.json`, `gold.json`, and `frozen.lock` in one pull request, and push.
6. Publish the release. [Publish frozen inputs](../README.md#publish-frozen-inputs) gives the steps.

A catalog changes after the eval freezes it, so its gold describes the frozen version. To catch up with a catalog, freeze it again, check its gold, and publish a new version.
