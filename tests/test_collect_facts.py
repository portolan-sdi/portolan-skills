"""Test catalog fact collection with local fixtures."""

from __future__ import annotations

import importlib.util
import io
import json
import struct
import subprocess
import sys
from pathlib import Path

import pytest

duckdb = pytest.importorskip("duckdb")
Image = pytest.importorskip("PIL.Image")

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "skills" / "catalog-grader" / "scripts" / "collect_facts.py"


@pytest.fixture(scope="session")
def facts_mod():
    spec = importlib.util.spec_from_file_location("collect_facts", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["collect_facts"] = module
    spec.loader.exec_module(module)
    return module


def png(color=(255, 255, 255), size=(300, 200), stripes=False) -> bytes:
    img = Image.new("RGB", size, color)
    if stripes:
        for x in range(0, size[0], 10):
            for y in range(size[1]):
                img.putpixel((x, y), ((x * 7) % 255, (y * 3) % 255, 90))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


AGENTS = """# Agent guide, {title}

Query the data with DuckDB. The key column is `kind`.

```sql
SELECT kind, count(*) AS n FROM read_parquet('data.parquet') GROUP BY kind ORDER BY n DESC;
```

-- road 3, river 2.

```python
import duckdb
print(duckdb.sql("SELECT count(*) FROM 'data.parquet'").fetchall())
```

```python
factor = 21
```

```python
print(factor * 2)
```

```sql
COPY (SELECT 1 AS one) TO 'written-by-docs.csv';
```

```bash
touch shell-ran
```

Every feature has a kind.
<!-- claim check: SELECT * FROM read_parquet('data.parquet') WHERE kind IS NULL -->

Every n is below 5.
<!--
SELECT * FROM read_parquet('data.parquet') WHERE n >= 5
-->
"""


def collection(tmp: Path, name: str, labels: list[str], thumb: bytes) -> dict:
    d = tmp / name
    (d / "styles").mkdir(parents=True)
    con = duckdb.connect()
    con.execute(
        f"COPY (SELECT * FROM (VALUES ('road', 1), ('road', 2), ('road', 3), ('river', 4), ('river', 5)) t(kind, n)) "
        f"TO '{d / 'data.parquet'}' (FORMAT parquet)"
    )
    (d / "thumbnail.png").write_bytes(thumb)
    style = {"version": 8, "layers": [{"id": "f", "type": "fill", "paint": {"fill-color": ["match", ["get", "kind"], *sum(([lab, "#f00"] for lab in labels), []), "#ccc"]}}]}
    (d / "styles" / "kind.json").write_text(json.dumps(style))
    (d / "README.md").write_text(f"# {name}\n\nAll 5 features of {name}, from [the source](https://example.com/{name}).\n")
    (d / "AGENTS.md").write_text(AGENTS.format(title=name))
    coll = {
        "type": "Collection", "stac_version": "1.1.0", "id": name, "title": name, "description": f"{name} lines.",
        "license": "CC0-1.0", "extent": {"spatial": {"bbox": [[-71.2, 42.2, -70.9, 42.4]]}, "temporal": {"interval": [[None, None]]}},
        "table:row_count": 5,
        "table:columns": [{"name": "kind", "type": "varchar", "description": "Feature kind."}, {"name": "n", "type": "int"}],
        "links": [
            {"rel": "root", "href": "../catalog.json"},
            {"rel": "agents", "href": "./AGENTS.md", "type": "text/markdown"},
            {"rel": "describedby", "href": "./README.md", "type": "text/markdown"},
            {"rel": "license", "href": "./missing-license.txt"},
        ],
        "assets": {
            "data": {"href": "./data.parquet", "type": "application/vnd.apache.parquet", "roles": ["data"]},
            "thumbnail": {"href": "./thumbnail.png", "type": "image/png", "roles": ["thumbnail"]},
            "style-kind": {"href": "./styles/kind.json", "type": "application/vnd.mapbox.style+json", "roles": ["style", "default"]},
        },
    }
    (d / "collection.json").write_text(json.dumps(coll))
    return {"rel": "child", "href": f"./{name}/collection.json", "type": "application/json"}


@pytest.fixture
def catalog(tmp_path: Path) -> Path:
    cat = tmp_path / "cat"
    cat.mkdir()
    children = [
        collection(cat, "roads", ["road", "river", "ghost"], png(stripes=True)),
        collection(cat, "rivers", ["road", "river"], png()),
    ]
    (cat / "README.md").write_text("# Test\n\nTwo collections, 10 features in 2026.\n")
    (cat / "AGENTS.md").write_text("# Agents\n")
    (cat / "catalog.json").write_text(json.dumps({
        "type": "Catalog", "stac_version": "1.1.0", "id": "t", "description": "t",
        "links": [
            {"rel": "root", "href": "./catalog.json"},
            {"rel": "agents", "href": "./AGENTS.md", "type": "text/markdown"},
            {"rel": "describedby", "href": "./README.md", "type": "text/markdown"},
            {"rel": "vcs", "href": "https://github.com/example/cat"},
            *children,
        ],
    }))
    return cat


# ------------------------------------------------------------------ units


def test_blank_and_real_images(facts_mod):
    assert facts_mod.image_facts(png())["likely_blank"] is True
    real = facts_mod.image_facts(png(stripes=True))
    assert real["likely_blank"] is False
    assert real["aspect"] == 1.5


def test_style_match_labels_include_list_labels(facts_mod):
    style = {"layers": [{"type": "fill", "paint": {"fill-color": ["match", ["to-string", ["get", "c"]], ["a", "b"], "#111", "z", "#222", "#000"]}}]}
    got = facts_mod.style_facts(style)
    assert got["match_labels"] == {"c": ["a", "b", "z"]}
    assert got["layer_types"] == ["fill"]


def test_full_extent_zoom(facts_mod):
    assert facts_mod.full_extent_zoom([-180, -85, 180, 85]) == 0
    assert 10 <= facts_mod.full_extent_zoom([-71.2, 42.2, -70.9, 42.4]) <= 12


def test_pmtiles_header(facts_mod):
    head = bytearray(127)
    head[:7] = b"PMTiles"
    head[7] = 3
    head[99] = 1
    head[100], head[101] = 6, 14
    head[102:118] = struct.pack("<iiii", -712000000, 422000000, -709000000, 424000000)
    got = facts_mod.pmtiles_header(bytes(head))
    assert (got["tile_type"], got["min_zoom"], got["max_zoom"]) == ("mvt", 6, 14)
    assert got["bounds"][0] == pytest.approx(-71.2)
    assert facts_mod.pmtiles_header(b"nope" * 40) is None


def test_numeric_claims_skip_years_and_list_markers(facts_mod):
    prose = [(1, "1. First item"), (2, "All 63,073 monuments, surveyed in 2024."), (3, "Coverage is 85% of parcels.")]
    values = [c["value"] for c in facts_mod.numeric_claims(prose)]
    assert values == ["63,073", "85"]


def test_comments_are_not_prose(facts_mod):
    md = facts_mod.parse_markdown("Intro.\n<!-- 12345 rows: SELECT 1 -->\nAll 900 rows.\n<!--\nmulti\nline -->\n")
    assert [c["text"] for c in md["comments"]] == ["12345 rows: SELECT 1", "multi\nline"]
    assert [c["value"] for c in facts_mod.numeric_claims(md["prose"])] == ["900"]


def test_prepare_sql_resolves_relative_paths_for_published_docs(facts_mod):
    sql, rewritten = facts_mod.prepare_sql("SELECT * FROM read_parquet('data.parquet');", "https://h.example/c/AGENTS.md")
    assert "https://h.example/c/data.parquet" in sql
    assert rewritten == ["data.parquet -> https://h.example/c/data.parquet"]
    assert facts_mod.prepare_sql("SELECT 1", "/local/AGENTS.md") == ("SELECT 1", [])


def test_prepare_sql_resolves_bare_file_scans(facts_mod):
    code = "SELECT * FROM 'stops/stops.parquet' s\nJOIN 'routes.parquet' r USING (id)\nWHERE s.x IN (SELECT x FROM read_parquet('a.parquet'));"
    sql, rewritten = facts_mod.prepare_sql(code, "https://h.example/c/AGENTS.md")
    assert "FROM 'https://h.example/c/stops/stops.parquet'" in sql
    assert "JOIN 'https://h.example/c/routes.parquet'" in sql
    assert "read_parquet('https://h.example/c/a.parquet')" in sql
    assert len(rewritten) == 3
    keep = "SELECT * FROM 's3://b/k.parquet'"
    assert facts_mod.prepare_sql(keep, "https://h.example/c/AGENTS.md") == (keep, [])


def test_sql_setup_statements(facts_mod):
    code = "INSTALL spatial;\nLOAD spatial; -- for ST_ functions\nSET VARIABLE base = 'https://h.example';\nSELECT 1;\nCREATE OR REPLACE SECRET s (TYPE s3);"
    assert facts_mod.sql_setup_statements(code) == [
        "INSTALL spatial;", "LOAD spatial;", "SET VARIABLE base = 'https://h.example';", "CREATE OR REPLACE SECRET s (TYPE s3);",
    ]
    assert facts_mod.sql_setup_statements("-- LOAD spatial;\nSELECT 1;") == []


def test_registry_urls_reads_child_links(facts_mod):
    export = {
        "type": "Catalog",
        "links": [
            {"rel": "self", "href": "https://raw.example/exports/catalogs.json"},
            {"rel": "child", "href": "https://data.example/cholmes/trimet/catalog.json"},
            {"rel": "child", "href": "https://data.example/other/catalog.json/"},
        ],
    }
    urls = facts_mod.registry_urls(json.dumps(export).encode())
    assert urls == {"https://data.example/cholmes/trimet/catalog.json", "https://data.example/other/catalog.json"}
    assert facts_mod.registry_urls(b'{"entries": [{"url": "https://x.example/catalog.json"}]}') == {"https://x.example/catalog.json"}


def test_python_packages(facts_mod):
    code = "import os, json\nimport geopandas as gpd\nfrom odc.stac import load\nfrom pystac_client import Client\n"
    assert facts_mod.python_packages(code) == ["aiohttp", "fsspec", "geopandas", "odc-stac", "pyarrow", "pystac-client"]


def test_environment_errors_are_classified(facts_mod):
    got = facts_mod.classify({"ok": False}, 'IO Error: Failed to download extension "spatial"')
    assert got["environment_error"] is True and got["missing_file"] is False
    got = facts_mod.classify({"ok": False}, "FileNotFoundError: data.parquet")
    assert got["environment_error"] is False and got["missing_file"] is True
    got = facts_mod.classify({"ok": False}, "ModuleNotFoundError: No module named 'numpy'")
    assert got["environment_error"] is True
    got = facts_mod.classify({"ok": False}, 'ImportError: Missing optional dependency \'fsspec\'.  Use pip or conda to install fsspec.')
    assert got["environment_error"] is True


# ------------------------------------------------------------ end to end


def test_main_on_fixture(facts_mod, catalog, tmp_path):
    out = tmp_path / "out"
    assert facts_mod.main([str(catalog), "--out", str(out), "--no-rashid", "--timeout", "60"]) == 0
    facts = json.loads((out / "facts.json").read_text())
    nodes = {n["path"]: n for n in facts["nodes"]}
    assert set(nodes) == {"", "roads", "rivers"}

    roads, rivers = nodes["roads"], nodes["rivers"]
    assert roads["parquet_row_count"] == 5 == roads["table_row_count"]
    [check] = roads["legend_checks"]
    assert check["labels_absent_from_data"] == ["ghost"]
    assert rivers["legend_checks"][0]["labels_absent_from_data"] == []
    assert rivers["thumbnail"]["likely_blank"] is True
    assert roads["thumbnail"]["likely_blank"] is False
    assert roads["table_columns"]["undescribed"] == ["n"]
    assert (out / roads["AGENTS.md"]["saved"]).read_text().startswith("# Agent guide, roads")

    blocks = [q for q in facts["queries"] if q["node"] == "roads"]
    sql, py_count, py_define, py_use, copy = blocks
    assert sql["ok"] is True and sql["rows"][0] == ["road", "3"]
    assert sql["followed_by"] == "-- road 3, river 2."
    assert py_count["ok"] is True, py_count
    assert "(5,)" in py_count["stdout"] and py_count["packages"] == ["duckdb"]
    assert py_define["ok"] is True
    assert py_use["ok"] is True and py_use["ran_after_earlier_blocks"] == 2
    assert py_use["stdout"].strip().endswith("42")
    assert copy["ok"] is True
    # New output files stay in the scratch directory.
    assert not list(catalog.rglob("written-by-docs.csv"))
    assert not (out / "work").exists()
    # Shell blocks run only with --run-shell.
    assert [b["lang"] for b in facts["code_blocks_not_run"] if b["node"] == "roads"] == ["bash"]

    checks = {(c["node"], c["line"]): c["claim_holds"] for c in facts["claim_checks"]}
    assert sorted(checks.values(), key=str) == [False, False, True, True]
    assert facts["summary"]["claim_checks_failed"] == 2
    assert roads["AGENTS.md"]["claim_check_count"] == 2

    assert facts["agents_similarity"][0]["ratio"] == 1.0
    # External link status depends on the network.
    broken = {Path(b["target"]).name for b in facts["links"]["broken"] if not b["target"].startswith("http")}
    assert broken == {"missing-license.txt"}
    assert facts["summary"]["thumbnails_likely_blank"] == ["rivers"]
    assert facts["registry"] == {"skipped": True}
    assert facts["summary"]["code_blocks_failed"] == 0
    assert facts["rashid"] == {"skipped": True}


def test_shell_and_registry_submission(facts_mod, catalog, tmp_path):
    out = tmp_path / "out2"
    args = [str(catalog), "--out", str(out), "--no-rashid", "--no-links", "--run-shell", "--registry-submission", "--timeout", "60"]
    assert facts_mod.main(args) == 0
    facts = json.loads((out / "facts.json").read_text())
    shell = [q for q in facts["queries"] if q["lang"] == "bash"]
    assert shell and all(q["ok"] for q in shell)
    assert not list(catalog.rglob("shell-ran"))
    assert facts["registry"] == {"submission": True}


def test_repo_facts(facts_mod, tmp_path):
    repo = tmp_path / "repo"
    wf = repo / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "ci.yml").write_text("on:\n  pull_request:\n  push:\njobs:\n  v:\n    steps:\n      - run: rashid check catalog/\n")
    (wf / "docs.yml").write_text("on:\n  schedule:\n    - cron: '0 6 * * 1'\njobs:\n  d:\n    steps:\n      - run: pytest tests/test_queries.py\n")
    (repo / "tests").mkdir()
    (repo / "tests" / "test_queries.py").write_text("import duckdb, pathlib\nfor md in pathlib.Path('catalog').rglob('*.md'):\n    pass\n")
    (repo / "catalog.parquet").write_text("x")
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", "commit", "-qm", "init"],
        check=True,
    )
    subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", "git@github.com:example/cat.git"], check=True)
    got = facts_mod.repo_facts(repo, "https://github.com/example/cat")
    assert got["is_git"] is True
    assert got["vcs_link_matches_remote"] is True
    assert got["ci_validates_on_pull_request"] is True
    ci, docs = got["workflows"]
    assert ci["triggers"] == ["pull_request", "push"]
    assert docs["scheduled"] is True and "text" not in docs
    assert got["tests_run_doc_queries"] == ["tests/test_queries.py"]
    assert got["ci_checks_docs_on_schedule"] is True
    assert got["tracked_data_files"] == ["catalog.parquet"]
