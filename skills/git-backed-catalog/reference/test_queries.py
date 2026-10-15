#!/usr/bin/env python3
"""Every query and every checked claim in the catalog docs has to hold.

Two kinds of check, both read from the Markdown under catalog/:

* Every ```sql block runs, in document order, on one DuckDB connection per
  file, exactly as a reader would paste it. The last statement must return at
  least one row. An empty result usually means a renamed category or a filter
  that no longer matches.
* Every <!-- claim-check ... --> comment holds a query that returns the rows
  that break the claim next to it. The claim holds when the query returns no
  rows. These run on a separate connection with spatial and httpfs loaded and
  the variable `base` set to public_base from catalog.publish.yaml.

Put one of these on the line before a ```sql fence to change how it is run:

    <!-- query-check: empty-ok -->         an empty result is correct
    <!-- query-check: skip <reason> -->    a fragment, not a runnable query

The data changes after the docs are written, so CI runs this on a schedule as
well as on every pull request. See .github/workflows/docs-check.yml.

Run: python3 tests/test_queries.py [--report report.md]
"""
import argparse
import os
import re
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "catalog"
sys.path.insert(0, str(ROOT / "tools"))

from publish import load_config  # noqa: E402

TIMEOUT = 600  # seconds per statement
RETRY_WAIT = 30  # seconds before the one retry of a network error

FENCE = re.compile(r"^```sql[ \t]*\n(.*?)^```", re.S | re.M)
MARKER = re.compile(r"<!--\s*query-check:\s*(empty-ok|skip\s+\S.*?)\s*-->\s*$")
CLAIM = re.compile(r"<!--\s*claim-check[ \t]*\n(.*?)-->", re.S)
CLAIM_SETUP = "INSTALL spatial; LOAD spatial; INSTALL httpfs; LOAD httpfs;"


def blocks(text):
    """Yield (line, sql, marker) for each sql fence in a Markdown text."""
    for m in FENCE.finditer(text):
        line = text.count("\n", 0, m.start()) + 1
        before = text[:m.start()].rstrip("\n").rsplit("\n", 1)[-1]
        marker = MARKER.search(before)
        yield line, m.group(1).strip(), marker.group(1) if marker else ""


def claims(text):
    """Yield (line, sql) for each claim-check comment."""
    for m in CLAIM.finditer(text):
        yield text.count("\n", 0, m.start()) + 1, m.group(1).strip()


def run(con, sql):
    """Run each statement in turn. Return the last result's rows, or None
    when the last statement returns no result set (SET, INSTALL, LOAD)."""
    rows = None
    for stmt in con.extract_statements(sql):
        timer = threading.Timer(TIMEOUT, con.interrupt)
        timer.start()
        try:
            result = con.execute(stmt.query)
        finally:
            timer.cancel()
        rows = result.fetchmany(5) if result.description else None
    return rows


def run_retrying(con, duckdb, sql):
    """A public bucket drops an occasional request. Retry once on a network
    error so that a scheduled run does not open an issue for a blip."""
    try:
        return run(con, sql)
    except (duckdb.IOException, duckdb.HTTPException):
        time.sleep(RETRY_WAIT)
        return run(con, sql)


def first_line(exc):
    if type(exc).__name__ == "InterruptException":
        return f"timed out after {TIMEOUT}s"
    return (str(exc).strip().splitlines() or [""])[0][:300]


def check_file(md, duckdb, base):
    """Return (ran, failures) for one Markdown file."""
    text = md.read_text()
    label = md.relative_to(ROOT)
    failures, ran = [], 0

    con = duckdb.connect()
    for line, sql, marker in blocks(text):
        if marker.startswith("skip"):
            continue
        ran += 1
        try:
            rows = run_retrying(con, duckdb, sql)
        except duckdb.Error as exc:
            failures.append((f"{label}:{line}", "query failed", first_line(exc)))
            continue
        if rows == [] and marker != "empty-ok":
            failures.append((f"{label}:{line}", "query returned no rows", ""))
    con.close()

    found = list(claims(text))
    if found:
        con = duckdb.connect()
        run(con, CLAIM_SETUP)
        con.execute("SET VARIABLE base = ?", [base])
        for line, sql in found:
            ran += 1
            try:
                rows = run_retrying(con, duckdb, sql)
            except duckdb.Error as exc:
                failures.append((f"{label}:{line}", "claim check failed", first_line(exc)))
                continue
            if rows:
                shown = "; ".join(str(r) for r in rows)
                failures.append((f"{label}:{line}", "claim does not hold", shown[:300]))
        con.close()
    failures.sort(key=lambda f: int(f[0].rsplit(":", 1)[1]))
    return ran, failures


def report(failures, ran, path):
    lines = [f"{len(failures)} of {ran} documented queries and claims fail.", "",
             "| Where | Problem | Detail |", "|---|---|---|"]
    for where, what, detail in failures:
        detail = detail.replace("|", "\\|").replace("\n", " ")
        lines.append(f"| `{where}` | {what} | {detail} |")
    lines += ["", "Fix the doc, or find out why the data changed. Do not delete "
              "the check to make it pass."]
    path.write_text("\n".join(lines) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, help="write failures as Markdown")
    args = parser.parse_args()

    try:
        import duckdb
    except ImportError:
        # CI must run the check, so a missing install is a failure there.
        if os.environ.get("CI"):
            print("FAIL: duckdb is not installed")
            return 1
        print("SKIP: duckdb is not installed. pip install duckdb")
        return 0

    base = load_config()["public_base"].rstrip("/")
    files = sorted(CATALOG.rglob("*.md"))
    ran, failures = 0, []
    for md in files:
        n, f = check_file(md, duckdb, base)
        ran += n
        failures += f

    if args.report:
        report(failures, ran, args.report)
    if ran == 0:
        print("FAIL: no SQL blocks or claim checks found; the docs lost their examples")
        return 1
    for where, what, detail in failures:
        print(f"FAIL {where}: {what}" + (f": {detail}" if detail else ""))
    if failures:
        print(f"FAIL: {len(failures)} of {ran} documented queries and claims fail")
        return 1
    print(f"PASS: {ran} documented queries and claims hold in {len(files)} file(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
