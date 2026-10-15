#!/usr/bin/env python3
"""Print eval metrics, cost, and per-case results as Markdown.

    python3 evals/catalog-grader/summary.py .claude/hillclimb/catalog-grader/baseline [.../v1 ...]
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

METRICS = ["pass", "in_band", "key_recall", "false_invent", "quotes_ok", "rules_ok", "coverage_ok", "schema_ok"]


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, centre - half), min(1.0, centre + half)


def summarize(variant: Path) -> list[str]:
    rows = [json.loads(line) for line in (variant / "results.jsonl").read_text().splitlines() if line.strip()]
    errors = variant / "errors.jsonl"
    n_err = len(errors.read_text().splitlines()) if errors.exists() else 0
    if not rows:
        return [f"### {variant.name}", "", "No results.", ""]
    models = sorted({r.get("model") or "?" for r in rows})
    judges = sorted({r.get("judge_model") or "-" for r in rows})
    k = sum(r["grade"]["pass"] for r in rows)
    lo, hi = wilson(k, len(rows))
    cost = sum(r.get("cc_cost_usd") or 0 for r in rows)
    out = [
        f"### {variant.name}: {', '.join(models)}",
        "",
        f"Pass {k}/{len(rows)} = {k / len(rows):.0%} (95% interval {lo:.0%} to {hi:.0%}). "
        f"Cost ${cost:.2f} (${cost / len(rows):.2f} per case-rep). Judge: {', '.join(judges)}. Failed attempts: {n_err}.",
        "",
        "| metric | mean |",
        "|---|---|",
    ]
    for m in METRICS:
        vals = [r["grade"].get(m) for r in rows if r["grade"].get(m) is not None]
        out.append(f"| {m} | {sum(vals) / len(vals):.2f} |" if vals else f"| {m} | - |")
    out += ["", "| case | rep | grade | pass | failed checks | cost | time |", "|---|---|---|---|---|---|---|"]
    for r in sorted(rows, key=lambda r: (r["prompt_id"], r["rep"])):
        g = r["grade"]
        failed = [m for m in ("in_band", "quotes_ok", "rules_ok", "coverage_ok", "schema_ok") if m in g and g[m] != 1]
        out.append(
            f"| {r['prompt_id']} | {r['rep']} | {r.get('report_grade') or '-'} | {'yes' if g['pass'] else 'no'} | "
            f"{', '.join(failed) or '-'} | ${r.get('cc_cost_usd') or 0:.2f} | {r.get('latency_s', 0):.0f}s |"
        )
    return out + [""]


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    for path in argv:
        print("\n".join(summarize(Path(path))))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
