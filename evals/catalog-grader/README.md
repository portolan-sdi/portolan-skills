# catalog-grader eval

Runs [catalog-grader](../../skills/catalog-grader/SKILL.md) from Step 2 on frozen
catalog facts. [grade.mjs](grade.mjs) defines the metrics.
[grade.test.mjs](grade.test.mjs) tests the checks that do not use a model.

## Run

Requires Node.js 20+, [uv](https://docs.astral.sh/uv/), and Claude Code 2.1.300+.
On Linux, sign in to `claude`. On macOS, set `CLAUDE_CODE_OAUTH_TOKEN` from
`claude setup-token`, or set `ANTHROPIC_API_KEY`.

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

After reviewing harness changes, add `--approve-harness` once. Repeat the command
to resume a run. Failed attempts in `errors.jsonl` run again.

| Environment variable | Use |
|---|---|
| `CG_EVAL_ONLY=id1,id2` | Run selected cases |
| `CG_EVAL_JUDGE` | Set a judge model that differs from the tested model |
| `CG_EVAL_REGRADE_FROM=<variant dir>` | Rescore saved reports after a scoring change |

The **Eval catalog-grader** workflow runs the eval manually and uploads results.
Each case starts a paid Claude Code session.

## Update cases

1. Add the case to `cases.json` and freeze it in Docker:

   ```bash
   evals/catalog-grader/freeze/freeze.sh <case-id>
   ```

2. Review `cases/<case-id>/frozen/facts.json` and saved documents. Add the grade
   band and required findings to `gold.json`, naming the reviewer in `source`.
3. [Pack and publish](../README.md#publish-frozen-inputs) the next version.
   Include `cases.json`, `gold.json`, and `frozen.lock` in one pull request.

Gold describes the frozen catalog. To update it, freeze the case again and
review its gold before publishing.
