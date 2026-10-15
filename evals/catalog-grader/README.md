# Evaluate catalog-grader

This evaluation runs the [catalog-grader skill](../../skills/catalog-grader/SKILL.md)
from step 2 using saved catalog facts. The [scorer](grade.mjs) defines the
metrics, and [unit tests](grade.test.mjs) cover the checks that don't use a model.

## Run

You need Node.js 20 or later, [uv](https://docs.astral.sh/uv/), and Claude Code
2.1.300 or later.
On Linux, sign in to `claude`. On macOS, set `CLAUDE_CODE_OAUTH_TOKEN` from
`claude setup-token`, or set `ANTHROPIC_API_KEY`.

If the run stops for approval, review the listed files and add
`--approve-harness` for one run.

Run from the repository root:

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

To resume a run, repeat the runner command. It retries failed attempts listed
in `errors.jsonl`.

| Environment variable | Use |
|---|---|
| `CG_EVAL_ONLY=id1,id2` | Run selected cases |
| `CG_EVAL_JUDGE` | Set a judge model that differs from the tested model |
| `CG_EVAL_REGRADE_FROM=<variant dir>` | Rescore saved reports after a scoring change |

You can also run the evaluation from the **Eval catalog-grader** workflow,
which uploads the results.
Each case starts a paid Claude Code session.

## Update cases

1. Add the case to `cases.json` and freeze it in Docker:

   ```bash
   evals/catalog-grader/freeze/freeze.sh <case-id>
   ```

2. Review `cases/<case-id>/frozen/facts.json` and the saved documents. Add the
   expected grade band and required findings to `gold.json`, and name the
   reviewer in `source`.
3. [Pack and publish](../README.md#publish-frozen-inputs) the next version.
   Include `cases.json`, `gold.json`, and `frozen.lock` in one pull request.

To change a case's expected results, freeze the catalog again and review the
changes before publishing.
