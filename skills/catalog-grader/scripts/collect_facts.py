#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["duckdb>=1.2", "pillow>=10", "pyyaml>=6"]
# ///
"""Collect the checkable facts about one Portolan catalog, for the grader.

Everything here is measured, never judged. The grader reads facts.json and
grades the parts that need judgment. Run it once per catalog:

    uv run collect_facts.py CATALOG --out DIR [--repo PATH]

CATALOG is the published root `catalog.json` URL, or a local catalog
directory (for fixtures and evals). `--repo` is the git checkout the catalog
is built from. The script writes DIR/facts.json plus copies of every
README.md, AGENTS.md, thumbnail, and icon under DIR, so the grader reads the
same bytes the facts describe.

The script runs the SQL and Python blocks in the documentation, plus the
shell blocks with --run-shell, each in its own process and its own scratch
directory under DIR/work. That code comes from the catalog, so run the
script on a machine you can throw away, such as a CI runner.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import difflib
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

USER_AGENT = "portolan-catalog-grader/1"
REGISTRY_EXPORT = "https://raw.githubusercontent.com/portolan-sdi/portolan-registry/main/exports/catalogs.json"
STRUCTURAL_RELS = {"root", "parent", "child", "item", "self", "collection"}
MD_LINK_RE = re.compile(r"(?<!!)\[([^\]]*)\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
MD_IMAGE_RE = re.compile(r"!\[[^\]]*\]\(\s*<?([^)\s>]+)>?")
BARE_URL_RE = re.compile(r"(?<![(<\[\"'=])\bhttps?://[^\s)<>\]\"'`]+")
FENCE_RE = re.compile(r"^(\s*)(```+|~~~+)\s*([A-Za-z0-9_+-]*)[^\n]*$")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
NUMBER_RE = re.compile(r"(?<![\w.#/-])(\d{1,3}(?:[,  ]\d{3})+|\d+(?:\.\d+)?)(\s?%|\s+[A-Za-z][A-Za-z-]*)?")
READ_FN_RE = re.compile(
    r"\b(read_parquet|parquet_scan|read_csv|read_csv_auto|read_json|read_json_auto|st_read|parquet_metadata|parquet_file_metadata)\s*\(\s*'([^']+)'",
    re.IGNORECASE,
)
# DuckDB also reads a quoted file path in FROM or JOIN directly (a replacement scan).
SCAN_RE = re.compile(r"\b(FROM|JOIN)\s+'([^']+)'", re.IGNORECASE)
SQL_LANGS = {"sql", "duckdb"}
# A claim check is a query in an HTML comment that returns the rows that
# break the claim (see the git-backed-catalog skill). No rows means true.
CLAIM_SQL_RE = re.compile(r"\b(SELECT|WITH)\b", re.IGNORECASE)


# ------------------------------------------------------------------ fetching


@dataclass
class Fetched:
    ok: bool
    status: int | None
    data: bytes = b""
    error: str | None = None
    final: str | None = None


def is_url(ref: str) -> bool:
    return ref.startswith(("http://", "https://"))


def resolve(base: str, href: str) -> str:
    """Resolve href against the location of the document at base."""
    if is_url(href) or href.startswith(("s3://", "gs://", "mailto:")):
        return href
    if is_url(base):
        return urllib.parse.urljoin(base, href)
    path = href.split("#", 1)[0].split("?", 1)[0]
    return os.path.normpath(os.path.join(os.path.dirname(base), urllib.parse.unquote(path)))


def fetch(ref: str, timeout: float = 30, limit: int | None = None) -> Fetched:
    if not is_url(ref):
        try:
            data = Path(ref).read_bytes()
            return Fetched(True, 200, data if limit is None else data[:limit], final=ref)
        except OSError as exc:
            return Fetched(False, None, error=str(exc))
    req = urllib.request.Request(ref, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read() if limit is None else resp.read(limit)
            return Fetched(True, resp.status, data, final=resp.geturl())
    except urllib.error.HTTPError as exc:
        return Fetched(False, exc.code, error=f"HTTP {exc.code}")
    except Exception as exc:  # network errors take many forms
        return Fetched(False, None, error=f"{type(exc).__name__}: {exc}")


def fetch_head_bytes(ref: str, n: int, timeout: float = 30) -> Fetched:
    """The first n bytes, by a range request for a URL."""
    if not is_url(ref):
        return fetch(ref, timeout, limit=n)
    req = urllib.request.Request(ref, headers={"User-Agent": USER_AGENT, "Range": f"bytes=0-{n - 1}"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return Fetched(True, resp.status, resp.read(n), final=resp.geturl())
    except urllib.error.HTTPError as exc:
        return Fetched(False, exc.code, error=f"HTTP {exc.code}")
    except Exception as exc:
        return Fetched(False, None, error=f"{type(exc).__name__}: {exc}")


def pmtiles_header(data: bytes) -> dict | None:
    """Parse the fixed 127-byte PMTiles v3 header."""
    import struct

    if len(data) < 127 or data[:7] != b"PMTiles" or data[7] != 3:
        return None
    tile_type = {0: "unknown", 1: "mvt", 2: "png", 3: "jpeg", 4: "webp", 5: "avif"}.get(data[99], str(data[99]))
    min_lon, min_lat, max_lon, max_lat = (v / 1e7 for v in struct.unpack("<iiii", data[102:118]))
    return {
        "tile_type": tile_type,
        "min_zoom": data[100],
        "max_zoom": data[101],
        "bounds": [min_lon, min_lat, max_lon, max_lat],
        "center_zoom": data[118],
        "addressed_tiles": struct.unpack("<Q", data[72:80])[0],
    }


def full_extent_zoom(bbox: list[float], width: int = 1024, height: int = 768) -> int | None:
    """The highest zoom at which bbox fits a width x height map of 512-pixel tiles."""
    import math

    if len(bbox) < 4:
        return None
    west, south, east, north = bbox[0], bbox[1], bbox[-2], bbox[-1]
    span_x = ((east - west) % 360 or 360) / 360 if east < west else (east - west) / 360

    def merc(lat: float) -> float:
        lat = max(min(lat, 85.0511), -85.0511)
        return (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2

    span_y = abs(merc(south) - merc(north))
    fits = [d / (512 * s) for d, s in ((width, span_x), (height, span_y)) if s > 0]
    if not fits:
        return 22
    return max(0, min(22, math.floor(math.log2(min(fits)))))


def probe(ref: str, timeout: float = 20) -> dict:
    """Check that a link resolves without downloading the target."""
    if ref.startswith("mailto:"):
        return {"target": ref, "ok": None, "status": None, "note": "mailto, not checked"}
    if ref.startswith(("s3://", "gs://")):
        return {"target": ref, "ok": None, "status": None, "note": "bucket URL, not checked"}
    if not is_url(ref):
        exists = Path(ref).exists()
        return {"target": ref, "ok": exists, "status": 200 if exists else 404}
    result: dict = {"target": ref}
    for method, headers in (("HEAD", {}), ("GET", {"Range": "bytes=0-0"})):
        req = urllib.request.Request(ref, method=method, headers={"User-Agent": USER_AGENT, **headers})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                result.update(ok=True, status=resp.status, final=resp.geturl())
                return result
        except urllib.error.HTTPError as exc:
            result.update(ok=False, status=exc.code)
            if exc.code not in (403, 405, 501):
                return result
        except Exception as exc:
            result.update(ok=False, status=None, error=f"{type(exc).__name__}: {exc}")
            return result
    return result


def load_json(ref: str) -> tuple[dict | None, str | None]:
    got = fetch(ref)
    if not got.ok:
        return None, got.error
    try:
        return json.loads(got.data), None
    except ValueError as exc:
        return None, f"invalid JSON: {exc}"


# ------------------------------------------------------------------ markdown


@dataclass
class CodeBlock:
    lang: str
    line: int
    code: str
    after: str  # the prose line that follows the fence, often the expected result


def parse_markdown(text: str) -> dict:
    lines = text.splitlines()
    blocks: list[CodeBlock] = []
    headings: list[str] = []
    prose: list[tuple[int, str]] = []
    comments: list[dict] = []
    i = 0
    while i < len(lines):
        m = FENCE_RE.match(lines[i])
        if m:
            fence, lang, start = m.group(2), m.group(3).lower(), i + 1
            body: list[str] = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith(fence[:3]):
                body.append(lines[i])
                i += 1
            after = next((ln.strip() for ln in lines[i + 1 : i + 4] if ln.strip()), "")
            blocks.append(CodeBlock(lang, start, "\n".join(body), after))
            i += 1
            continue
        if "<!--" in lines[i]:
            # An HTML comment is not prose. Keep it apart, since a claim
            # check query can live in one.
            start, joined = i + 1, lines[i]
            while "-->" not in joined[joined.index("<!--") :] and i + 1 < len(lines):
                i += 1
                joined += "\n" + lines[i]
            for body in re.findall(r"<!--(.*?)-->", joined, re.S):
                comments.append({"line": start, "text": body.strip()})
            rest = re.sub(r"<!--.*?-->", " ", joined, flags=re.S)
            if rest.strip():
                prose.append((start, rest.replace("\n", " ")))
            i += 1
            continue
        h = HEADING_RE.match(lines[i])
        if h:
            headings.append(f"{h.group(1)} {h.group(2)}")
        prose.append((i + 1, lines[i]))
        i += 1
    prose_text = "\n".join(t for _, t in prose)
    links = [{"text": t, "href": h} for t, h in MD_LINK_RE.findall(prose_text)]
    images = MD_IMAGE_RE.findall(prose_text)
    stripped = MD_LINK_RE.sub(r"\1", prose_text)
    stripped = re.sub(r"`[^`]*`", " ", stripped)
    bare = BARE_URL_RE.findall(stripped)
    return {
        "headings": headings,
        "blocks": blocks,
        "prose": prose,
        "comments": comments,
        "links": links,
        "images": images,
        "bare_urls": bare,
        "words": len(re.findall(r"\b\w+\b", stripped)),
    }


def numeric_claims(prose: list[tuple[int, str]], limit: int = 60) -> list[dict]:
    """Numbers stated in prose, with their sentence, for the grader to verify.

    Years, list markers, and version-like tokens are left out. The grader
    decides which of these are claims and checks each one.
    """
    out: list[dict] = []
    for line_no, text in prose:
        if HEADING_RE.match(text):
            continue
        clean = MD_LINK_RE.sub(r"\1", re.sub(r"`[^`]*`", " ", text))
        for m in NUMBER_RE.finditer(clean):
            raw = m.group(1)
            value = float(re.sub(r"[,  ]", "", raw))
            if re.fullmatch(r"\d{4}", raw) and 1800 <= value <= 2100:
                continue
            if value < 10 and not m.group(2):
                continue
            if clean[: m.start()].strip() == "" and clean[m.end() : m.end() + 1] in (".", ")"):
                continue  # ordered-list marker
            out.append({"line": line_no, "value": raw, "unit": (m.group(2) or "").strip(), "text": text.strip()[:300]})
            if len(out) >= limit:
                return out
    return out


# --------------------------------------------------------------- thumbnails


def image_facts(data: bytes) -> dict:
    from PIL import Image, ImageStat

    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception as exc:
        return {"decodes": False, "error": str(exc)}
    width, height = img.size
    rgb = img.convert("RGBA")
    # Composite transparency over white, the way a browser card shows it.
    flat = Image.new("RGB", rgb.size, (255, 255, 255))
    flat.paste(rgb, mask=rgb.split()[3])
    small = flat.resize((64, 64))
    colors = small.getcolors(64 * 64) or []
    dominant = max(colors)[0] / (64 * 64) if colors else 1.0
    stddev = sum(ImageStat.Stat(small.convert("L")).stddev)
    alpha = rgb.split()[3]
    transparent = sum(alpha.resize((64, 64)).histogram()[:16]) / (64 * 64)
    return {
        "decodes": True,
        "format": img.format,
        "width": width,
        "height": height,
        "aspect": round(width / height, 3) if height else None,
        "bytes": len(data),
        "unique_colors_64px": len(colors),
        "dominant_color_share": round(dominant, 3),
        "luminance_stddev": round(stddev, 2),
        "transparent_share": round(transparent, 3),
        "likely_blank": dominant > 0.97 or stddev < 2.0,
    }


# ------------------------------------------------------------------- styles


def walk_expressions(node, found: list) -> None:
    if isinstance(node, list) and node and isinstance(node[0], str):
        op = node[0]
        if op in ("match", "step", "interpolate", "case"):
            found.append(node)
    if isinstance(node, list):
        for child in node:
            walk_expressions(child, found)
    elif isinstance(node, dict):
        for child in node.values():
            walk_expressions(child, found)


def get_column(expr) -> str | None:
    """The column a `["get", col]` input reads, also through to-string and the like."""
    if isinstance(expr, list) and expr:
        if expr[0] == "get" and len(expr) >= 2 and isinstance(expr[1], str):
            return expr[1]
        for child in expr[1:]:
            col = get_column(child)
            if col:
                return col
    return None


def style_facts(style: dict) -> dict:
    layers = style.get("layers") or []
    exprs: list = []
    walk_expressions(layers, exprs)
    driven: list[dict] = []
    match_labels: dict[str, list] = {}
    for e in exprs:
        col = get_column(e[1]) if e[0] == "match" else get_column(e)
        driven.append({"op": e[0], "column": col})
        if e[0] == "match" and col and len(e) > 3:
            labels: list = []
            for lab in e[2:-1:2]:
                labels.extend(lab if isinstance(lab, list) else [lab])
            match_labels.setdefault(col, [])
            for lab in labels:
                if lab not in match_labels[col]:
                    match_labels[col].append(lab)
    colors: list[str] = []
    for layer in layers:
        for key, val in (layer.get("paint") or {}).items():
            if key.endswith("-color") and isinstance(val, str):
                colors.append(val.lower())
    return {
        "name": style.get("name"),
        "has_description": bool((style.get("metadata") or {}).get("description") or style.get("description")),
        "layer_count": len(layers),
        "layer_types": sorted({layer.get("type") for layer in layers if layer.get("type")}),
        "data_driven": driven,
        "match_labels": match_labels,
        "literal_colors": sorted(set(colors)),
    }


# --------------------------------------------------------------------- SQL

QUERY_RUNNER = r"""
import json, sys, time, duckdb
job = json.loads(sys.stdin.read())
out = {"ok": False}
t0 = time.time()

def show(v):
    if isinstance(v, (bytes, bytearray)):
        return f"<binary {len(v)} bytes>"
    s = str(v)
    return s if len(s) <= 200 else s[:200] + "..."

try:
    con = duckdb.connect()
    if job["search_path"]:
        con.execute("SET file_search_path = '" + job["search_path"].replace("'", "''") + "'")
    res = None
    for stmt in con.extract_statements(job["sql"]):
        res = con.execute(stmt.query)
    if res is not None and res.description:
        out["columns"] = [d[0] for d in res.description]
        out["rows"] = [[show(v) for v in row] for row in res.fetchmany(job["max_rows"])]
    out["ok"] = True
except Exception as exc:
    out["error"] = f"{type(exc).__name__}: {exc}"[:600]
out["seconds"] = round(time.time() - t0, 2)
print(json.dumps(out))
"""

# A failure to fetch an extension or a package is the grader's environment,
# not the catalog. The grader must not count it against the docs.
ENV_ERROR_RE = re.compile(
    r"Failed to (download|install)[^\n]*extension|extension[^\n]*could not be (downloaded|installed)"
    r"|No solution found when resolving|Failed to (fetch|download)[^\n]*(pypi|files\.pythonhosted)"
    r"|uv: command not found"
    # The script installs the packages a block imports. A module the block uses
    # without importing it (numpy behind DuckDB's .df(), pyarrow behind pandas)
    # is missing from the grader's environment, not from the catalog.
    r"|ModuleNotFoundError: No module named|Use pip or conda to install",
    re.IGNORECASE,
)
# A relative path that does not resolve: a docs defect of its own kind.
MISSING_FILE_RE = re.compile(r"FileNotFoundError|No such file or directory|No files found that match the pattern", re.IGNORECASE)

# Import names whose PyPI package has another name.
IMPORT_PACKAGES = {
    "odc": "odc-stac", "pystac_client": "pystac-client", "rioxarray": "rioxarray", "sklearn": "scikit-learn",
    "PIL": "pillow", "yaml": "pyyaml", "osgeo": "gdal", "cv2": "opencv-python-headless", "stac_geoparquet": "stac-geoparquet",
    "geoarrow": "geoarrow-pyarrow", "lonboard": "lonboard", "planetary_computer": "planetary-computer", "dateutil": "python-dateutil",
}


def work_dir(doc_ref: str, local_root: str | None) -> str:
    """A fresh directory to run one block in.

    For a local catalog it links the files beside the document, so a
    relative path reads what a reader of the published copy would read,
    while anything the block writes stays out of the catalog.
    """
    import tempfile

    base = OUT_DIR / "work"
    base.mkdir(parents=True, exist_ok=True)
    path = tempfile.mkdtemp(dir=base)
    if local_root:
        src = os.path.dirname(doc_ref)
        for name in os.listdir(src):
            try:
                os.symlink(os.path.join(src, name), os.path.join(path, name))
            except OSError:
                pass
    return path


def classify(out: dict, text: str) -> dict:
    out["environment_error"] = bool(not out.get("ok") and ENV_ERROR_RE.search(text or ""))
    out["missing_file"] = bool(not out.get("ok") and not out["environment_error"] and MISSING_FILE_RE.search(text or ""))
    return out


def prepare_sql(code: str, doc_ref: str) -> tuple[str, list[str]]:
    """Resolve relative paths in read functions against a published document's URL.

    A reader who pastes the query runs it from their own directory, so a
    relative path in published docs is a defect. The grader still learns
    whether the query works, and the report says the path was resolved.
    """
    rewritten: list[str] = []
    if not is_url(doc_ref):
        return code, rewritten

    def fix(m: re.Match) -> str:
        path = m.group(2)
        if is_url(path) or path.startswith(("s3://", "gs://", "/")):
            return m.group(0)
        absolute = urllib.parse.urljoin(doc_ref, path)
        rewritten.append(f"{path} -> {absolute}")
        return m.group(0).replace(f"'{path}'", f"'{absolute}'")

    return SCAN_RE.sub(fix, READ_FN_RE.sub(fix, code)), rewritten


def run_sql(code: str, doc_ref: str, local_root: str | None, timeout: int, max_rows: int = 5) -> dict:
    sql, rewritten = prepare_sql(code, doc_ref)
    cwd = work_dir(doc_ref, local_root)
    job = {"sql": sql, "search_path": cwd if local_root else "", "max_rows": max_rows}
    try:
        proc = subprocess.run(
            [sys.executable, "-I", "-c", QUERY_RUNNER],
            input=json.dumps(job), capture_output=True, text=True, timeout=timeout, cwd=cwd,
        )
        lines = proc.stdout.strip().splitlines()
        out = json.loads(lines[-1]) if lines else {"ok": False, "error": proc.stderr.strip()[-600:]}
    except subprocess.TimeoutExpired:
        out = {"ok": False, "error": f"timed out after {timeout}s"}
    except ValueError:
        out = {"ok": False, "error": "query runner returned no result"}
    if rewritten:
        out["relative_paths_resolved"] = rewritten
    return classify(out, out.get("error", ""))


def python_packages(code: str) -> list[str]:
    """The PyPI packages a block imports, leaving out the standard library."""
    import ast

    names: set[str] = set()
    try:
        for node in ast.walk(ast.parse(code)):
            if isinstance(node, ast.Import):
                names.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                names.add(node.module.split(".")[0])
    except SyntaxError:
        names.update(re.findall(r"^\s*(?:from|import)\s+([A-Za-z_]\w*)", code, re.M))
    std = set(sys.stdlib_module_names)
    packages = {IMPORT_PACKAGES.get(n, n.replace("_", "-")) for n in names if n not in std}
    # pandas and geopandas read Parquet through pyarrow, which a reader installs but rarely imports.
    # They open URLs through fsspec, whose HTTP filesystem needs aiohttp.
    if packages & {"pandas", "geopandas"}:
        packages |= {"pyarrow", "fsspec", "aiohttp"}
    return sorted(packages)


def strip_magics(code: str) -> tuple[str, list[str]]:
    """Drop notebook lines (`!pip install`, `%matplotlib`) that plain Python rejects."""
    kept, dropped = [], []
    for line in code.splitlines():
        (dropped if line.lstrip().startswith(("!", "%")) else kept).append(line)
    return "\n".join(kept), dropped


def run_program(argv: list[str], cwd: str, timeout: int, extra_env: dict | None = None) -> dict:
    env = dict(os.environ, MPLBACKEND="Agg", PYTHONDONTWRITEBYTECODE="1", **(extra_env or {}))
    t0 = time.time()
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, cwd=cwd, env=env)
        out = {"ok": proc.returncode == 0, "exit_code": proc.returncode,
               "stdout": proc.stdout[-1500:], "stderr": proc.stderr[-1500:]}
    except subprocess.TimeoutExpired:
        out = {"ok": False, "error": f"timed out after {timeout}s"}
    except FileNotFoundError as exc:
        out = {"ok": False, "error": str(exc)}
    out["seconds"] = round(time.time() - t0, 2)
    return classify(out, (out.get("stderr") or "") + (out.get("error") or ""))


def run_python(code: str, doc_ref: str, local_root: str | None, timeout: int) -> dict:
    from shutil import which

    code, dropped = strip_magics(code)
    packages = python_packages(code)
    cwd = work_dir(doc_ref, local_root)
    script = os.path.join(cwd, "_block.py")
    Path(script).write_text(code, encoding="utf-8")
    if which("uv"):
        argv = ["uv", "run", "--no-project", "--quiet", "--python", "3.12"]
        for pkg in packages:
            argv += ["--with", pkg]
        argv += ["python", script]
    else:
        argv = [sys.executable, script]
    out = run_program(argv, cwd, timeout)
    out["packages"] = packages
    if dropped:
        out["notebook_lines_dropped"] = dropped
    return out


def run_shell(code: str, doc_ref: str, local_root: str | None, timeout: int) -> dict:
    cwd = work_dir(doc_ref, local_root)
    script = os.path.join(cwd, "_block.sh")
    Path(script).write_text(code, encoding="utf-8")
    return run_program(["bash", "-e", script], cwd, timeout)


def query_value(sql: str, local_root: str | None, timeout: int, doc_ref: str) -> dict:
    return run_sql(sql, doc_ref, local_root, timeout, max_rows=200)


# -------------------------------------------------------------------- crawl


@dataclass
class Crawl:
    root: str
    out: Path
    local_root: str | None
    timeout: int
    max_nodes: int
    nodes: list[dict] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)
    link_targets: dict[str, list[str]] = field(default_factory=dict)
    saved: set[str] = field(default_factory=set)

    def note_link(self, target: str, where: str) -> None:
        self.link_targets.setdefault(target, [])
        if where not in self.link_targets[target]:
            self.link_targets[target].append(where)

    def save(self, rel_name: str, data: bytes) -> str:
        path = self.out / rel_name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return str(path.relative_to(self.out))


def slug(node_path: str) -> str:
    return node_path.replace("/", "__") or "root"


def node_rel_path(root: str, ref: str) -> str:
    base = os.path.dirname(root)
    if is_url(ref):
        rel = ref[len(base) :].lstrip("/") if ref.startswith(base) else ref
    else:
        rel = os.path.relpath(ref, base)
    return os.path.dirname(rel)


def collect_doc(crawl: Crawl, node: dict, ref: str, kind: str, key: str) -> dict:
    got = fetch(ref, crawl.timeout)
    doc: dict = {"href": ref, "fetched": got.ok, "status": got.status}
    if not got.ok:
        doc["error"] = got.error
        return doc
    text = got.data.decode("utf-8", "replace")
    doc["saved"] = crawl.save(f"docs/{slug(node['path'])}/{kind}", got.data)
    doc["sha256"] = hashlib.sha256(got.data).hexdigest()
    md = parse_markdown(text)
    doc["words"] = md["words"]
    doc["headings"] = md["headings"]
    doc["bare_urls"] = md["bare_urls"][:30]
    doc["numeric_claims"] = numeric_claims(md["prose"])
    doc["code_blocks"] = [
        {"lang": b.lang or "(none)", "line": b.line, "lines": b.code.count("\n") + 1, "followed_by": b.after[:200]}
        for b in md["blocks"]
    ]
    doc["_blocks"] = md["blocks"]
    doc["_claim_checks"] = [
        {"line": c["line"], "sql": c["text"][m.start() :]}
        for c in md["comments"]
        for m in [CLAIM_SQL_RE.search(c["text"])]
        if m
    ]
    doc["links"] = []
    for link in md["links"] + [{"text": "(image)", "href": h} for h in md["images"]]:
        href = link["href"]
        if href.startswith("#"):
            continue
        target = resolve(ref, href)
        doc["links"].append({"text": link["text"][:80], "href": href, "target": target})
        crawl.note_link(target, f"{node['path'] or '.'}/{kind}")
    return doc


def crawl_node(crawl: Crawl, ref: str, depth: int = 0) -> None:
    if len(crawl.nodes) >= crawl.max_nodes:
        crawl.errors.append({"href": ref, "error": f"node limit {crawl.max_nodes} reached, not crawled"})
        return
    obj, err = load_json(ref)
    if obj is None:
        crawl.errors.append({"href": ref, "error": err})
        return
    path = node_rel_path(crawl.root, ref)
    node: dict = {
        "path": path,
        "href": ref,
        "type": obj.get("type"),
        "id": obj.get("id"),
        "title": obj.get("title"),
        "description": obj.get("description"),
        "description_words": len(re.findall(r"\b\w+\b", obj.get("description") or "")),
        "description_bare_urls": BARE_URL_RE.findall(MD_LINK_RE.sub(r"\1", obj.get("description") or ""))[:20],
        "license": obj.get("license"),
        "updated": obj.get("updated"),
        "stac_extensions": obj.get("stac_extensions") or [],
        "keywords": obj.get("keywords") or [],
        "providers": [{"name": p.get("name"), "roles": p.get("roles"), "url": p.get("url"), "email": p.get("email")} for p in obj.get("providers") or []],
    }
    links = obj.get("links") or []
    node["links"] = [
        {k: l.get(k) for k in ("rel", "href", "type", "title", "hreflang") if l.get(k) is not None}
        for l in links
        if l.get("rel") not in ("child", "item")
    ]
    node["child_count"] = sum(1 for l in links if l.get("rel") == "child")
    node["item_link_count"] = sum(1 for l in links if l.get("rel") == "item")
    for l in links:
        href = l.get("href")
        if not href or l.get("rel") in ("child", "item", "root", "parent", "self", "collection"):
            continue
        crawl.note_link(resolve(ref, href), f"{path or '.'}/links[{l.get('rel')}]")
    if obj.get("description"):
        for t, h in MD_LINK_RE.findall(obj["description"]):
            crawl.note_link(resolve(ref, h), f"{path or '.'}/description")

    for rel, kind in (("describedby", "README.md"), ("agents", "AGENTS.md")):
        link = next((l for l in links if l.get("rel") == rel and str(l.get("type", "")).startswith("text/markdown")), None)
        link = link or next((l for l in links if l.get("rel") == rel), None)
        node[kind] = collect_doc(crawl, node, resolve(ref, link["href"]), kind, rel) if link else None

    if obj.get("type") == "Collection":
        collection_facts(crawl, node, obj, ref)
    crawl.nodes.append(node)

    for l in links:
        if l.get("rel") == "child" and l.get("href"):
            crawl_node(crawl, resolve(ref, l["href"]), depth + 1)


def collection_facts(crawl: Crawl, node: dict, obj: dict, ref: str) -> None:
    assets = obj.get("assets") or {}
    node["assets"] = [
        {"key": k, "roles": a.get("roles") or [], "type": a.get("type"), "href": a.get("href"), "title": a.get("title"), "file:size": a.get("file:size")}
        for k, a in assets.items()
    ]
    for a in assets.values():
        if a.get("href"):
            crawl.note_link(resolve(ref, a["href"]), f"{node['path']}/assets")
    cols = obj.get("table:columns") or []
    node["table_columns"] = {
        "count": len(cols),
        "described": sum(1 for c in cols if (c.get("description") or "").strip()),
        "undescribed": [c.get("name") for c in cols if not (c.get("description") or "").strip()],
    }
    node["table_row_count"] = obj.get("table:row_count")
    node["partition_glob"] = obj.get("partition:glob")

    # Thumbnail
    thumb_key = next((k for k, a in assets.items() if "thumbnail" in (a.get("roles") or [])), None)
    if thumb_key:
        target = resolve(ref, assets[thumb_key]["href"])
        got = fetch(target, crawl.timeout)
        thumb: dict = {"key": thumb_key, "href": target, "fetched": got.ok, "status": got.status}
        if got.ok:
            ext = os.path.splitext(urllib.parse.urlparse(target).path)[1] or ".img"
            thumb["saved"] = crawl.save(f"thumbnails/{slug(node['path'])}{ext}", got.data)
            thumb.update(image_facts(got.data))
        else:
            thumb["error"] = got.error
        node["thumbnail"] = thumb
    else:
        node["thumbnail"] = None

    # Styles
    styles = []
    for k, a in assets.items():
        roles = a.get("roles") or []
        if "style" not in roles:
            continue
        target = resolve(ref, a["href"])
        style_obj, err = load_json(target)
        entry: dict = {"key": k, "title": a.get("title"), "default": "default" in roles, "href": target}
        if style_obj is None:
            entry["error"] = err
        else:
            entry.update(style_facts(style_obj))
        styles.append(entry)
    node["styles"] = styles

    # PMTiles header: does the first view at full extent have tiles?
    pm = next((l for l in obj.get("links") or [] if l.get("rel") == "pmtiles" and l.get("href")), None)
    if pm:
        target = resolve(ref, pm["href"])
        got = fetch_head_bytes(target, 127, crawl.timeout)
        header = pmtiles_header(got.data) if got.ok else None
        bbox = ((obj.get("extent") or {}).get("spatial") or {}).get("bbox") or [[]]
        fit = full_extent_zoom(bbox[0])
        node["pmtiles"] = {
            "href": target,
            "fetched": got.ok,
            "error": got.error if not got.ok else (None if header else "not a PMTiles v3 header"),
            "header": header,
            "full_extent_zoom": fit,
            "starts_above_full_extent": bool(header and fit is not None and header["min_zoom"] > fit),
        }
    else:
        node["pmtiles"] = None

    # Data asset: row count and the legend check
    data = data_source(obj, ref)
    node["data_source"] = data
    if data:
        res = query_value(f"SELECT sum(num_rows) AS n FROM parquet_file_metadata({sql_str(data)})", crawl.local_root, crawl.timeout, ref)
        node["parquet_row_count"] = int(res["rows"][0][0]) if res.get("ok") and res.get("rows") and res["rows"][0][0] not in ("None", None) else None
        if not res.get("ok"):
            node["parquet_row_count_error"] = res.get("error")
        node["legend_checks"] = legend_checks(crawl, styles, data, ref)


def sql_str(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def data_source(obj: dict, ref: str) -> str | None:
    glob = obj.get("partition:glob")
    if glob and (is_url(glob) or not is_url(ref)):
        return glob if is_url(glob) else resolve(ref, glob)
    for a in (obj.get("assets") or {}).values():
        roles = a.get("roles") or []
        if "data" in roles and "parquet" in str(a.get("type", "")) and a.get("href"):
            return resolve(ref, a["href"])
    return None


def legend_checks(crawl: Crawl, styles: list[dict], data: str, ref: str) -> list[dict]:
    """Compare every `match` label with the values the column holds."""
    out: list[dict] = []
    for style in styles:
        for col, labels in (style.get("match_labels") or {}).items():
            entry = {"style": style["key"], "column": col, "labels": labels[:100]}
            q = (
                f'SELECT CAST("{col}" AS VARCHAR) AS v, count(*) AS n FROM read_parquet({sql_str(data)}) '
                f'GROUP BY 1 ORDER BY 2 DESC LIMIT 200'
            )
            res = query_value(q, crawl.local_root, crawl.timeout, ref)
            if not res.get("ok"):
                entry["error"] = res.get("error")
                out.append(entry)
                continue
            values = {r[0]: int(r[1]) for r in res.get("rows", [])}
            label_strs = {str(lab) for lab in labels}
            entry["labels_absent_from_data"] = [lab for lab in labels if str(lab) not in values][:50]
            entry["top_values_without_label"] = [
                {"value": v, "rows": n} for v, n in values.items() if v not in label_strs
            ][:20]
            entry["distinct_values_seen"] = len(values)
            out.append(entry)
    return out


# ------------------------------------------------------------- repo facts


def repo_facts(repo: Path, root_vcs: str | None) -> dict:
    import yaml

    facts: dict = {"path": str(repo), "exists": repo.is_dir()}
    if not repo.is_dir():
        return facts

    def git(*args: str) -> str | None:
        try:
            proc = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.TimeoutExpired):
            return None
        return proc.stdout.strip() if proc.returncode == 0 else None

    facts["is_git"] = git("rev-parse", "--is-inside-work-tree") == "true"
    if facts["is_git"]:
        facts["head"] = git("rev-parse", "HEAD")
        facts["last_commit_date"] = git("log", "-1", "--format=%cI")
        facts["commit_count"] = int(git("rev-list", "--count", "HEAD") or 0)
        remotes = (git("remote", "-v") or "").splitlines()
        facts["remotes"] = sorted({r.split()[1] for r in remotes if len(r.split()) >= 2})
        if root_vcs:
            norm = lambda u: re.sub(r"(\.git)?/?$", "", re.sub(r"^git@([^:]+):", r"https://\1/", u)).lower()
            facts["vcs_link_matches_remote"] = any(norm(r) == norm(root_vcs) for r in facts["remotes"])
        tracked = (git("ls-files") or "").splitlines()
        facts["tracked_file_count"] = len(tracked)
        heavy = [f for f in tracked if f.lower().endswith((".parquet", ".pmtiles", ".tif", ".tiff", ".zip", ".gpkg", ".shp", ".laz", ".copc.laz"))]
        facts["tracked_data_files"] = heavy[:30]
        facts["tracked_data_file_count"] = len(heavy)
        facts["top_level"] = sorted({f.split("/", 1)[0] + ("/" if "/" in f else "") for f in tracked})

    workflows = []
    wf_dir = repo / ".github" / "workflows"
    for wf in sorted(list(wf_dir.glob("*.yml")) + list(wf_dir.glob("*.yaml"))) if wf_dir.is_dir() else []:
        text = wf.read_text(encoding="utf-8", errors="replace")
        entry: dict = {"file": str(wf.relative_to(repo))}
        try:
            data = yaml.safe_load(text) or {}
            on = data.get(True, data.get("on"))  # PyYAML reads the key `on` as True
            entry["triggers"] = sorted(on) if isinstance(on, dict) else ([on] if isinstance(on, str) else list(on or []))
        except yaml.YAMLError as exc:
            entry["parse_error"] = str(exc)[:200]
        entry["runs_rashid"] = bool(re.search(r"\brashid\b", text))
        entry["runs_portolan_check"] = bool(re.search(r"portolan\s+check", text))
        entry["runs_stac_check"] = bool(re.search(r"stac[-_]check|stac-validator|stac-node-validator", text))
        entry["calls_test_runner"] = bool(re.search(r"\b(pytest|run_all\.py|npm test|make test)\b", text))
        entry["scheduled"] = "schedule" in (entry.get("triggers") or [])
        entry["text"] = text[:4000]
        workflows.append(entry)
    facts["workflows"] = workflows
    facts["other_ci"] = [p for p in (".gitlab-ci.yml", ".circleci/config.yml", "azure-pipelines.yml", ".woodpecker.yml") if (repo / p).exists()]
    tests_dir = repo / "tests"
    facts["tests"] = sorted(str(p.relative_to(repo)) for p in tests_dir.rglob("*") if p.is_file())[:50] if tests_dir.is_dir() else []
    facts["tests_mention_rashid"] = any(
        "rashid" in (repo / t).read_text(encoding="utf-8", errors="replace") for t in facts["tests"] if t.endswith(".py")
    )
    # A test that reads the Markdown and runs its SQL is the docs check the
    # git-backed-catalog skill asks for. The grader confirms by reading it.
    facts["tests_run_doc_queries"] = sorted(
        t for t in facts["tests"]
        if t.endswith(".py")
        and re.search(r"\.md\b|README|AGENTS", (text := (repo / t).read_text(encoding="utf-8", errors="replace")))
        and re.search(r"duckdb|```sql|read_parquet", text, re.I)
    )
    facts["ci_checks_docs_on_schedule"] = any(
        w["scheduled"] and (any(Path(t).name in w["text"] for t in facts["tests_run_doc_queries"]) or (w["calls_test_runner"] and facts["tests_run_doc_queries"]))
        for w in workflows
    )
    facts["ci_validates_on_pull_request"] = any(
        "pull_request" in (w.get("triggers") or []) and (w["runs_rashid"] or w["runs_portolan_check"] or (w["calls_test_runner"] and facts["tests_mention_rashid"]))
        for w in workflows
    )
    for w in workflows:
        w.pop("text", None)
    facts["publish_config"] = [p for p in ("catalog.publish.yaml", "catalog.publish.yml") if (repo / p).exists()]
    return facts


# --------------------------------------------------------------- the rest


def similarity(nodes: list[dict], kind: str, limit: int = 60) -> list[dict]:
    """Pairs of collections whose docs are near copies of each other."""
    docs = []
    for n in nodes:
        doc = n.get(kind)
        if n.get("type") != "Collection" or not doc or not doc.get("saved"):
            continue
        docs.append((n, doc))
    docs = docs[:limit]
    texts = {}
    for n, doc in docs:
        text = (OUT_DIR / doc["saved"]).read_text(encoding="utf-8", errors="replace")
        for token in filter(None, [n.get("title"), n.get("id"), (n.get("id") or "").split("/")[-1]]):
            text = text.replace(token, "<NAME>")
        texts[n["path"]] = re.sub(r"\s+", " ", text)
    pairs = []
    keys = list(texts)
    for i, a in enumerate(keys):
        for b in keys[i + 1 :]:
            sm = difflib.SequenceMatcher(None, texts[a], texts[b], autojunk=False)
            if sm.real_quick_ratio() < 0.6 or sm.quick_ratio() < 0.6:
                continue
            ratio = sm.ratio()
            if ratio >= 0.6:
                pairs.append({"a": a, "b": b, "ratio": round(ratio, 3)})
    return sorted(pairs, key=lambda p: -p["ratio"])[:40]


def registry_urls(data: bytes) -> set[str]:
    """Catalog URLs in the registry export.

    The export is a STAC catalog that links each registered catalog as a
    child. Older exports listed entries with a "url" field, so read both.
    """
    doc = json.loads(data)
    urls = {link["href"] for link in doc.get("links", []) if link.get("rel") == "child" and link.get("href")}
    urls |= set(re.findall(r'"url"\s*:\s*"([^"]+)"', data.decode("utf-8", "replace")))
    return {u.rstrip("/") for u in urls}


def run_rashid(rashid_cmd: list[str], catalog: str, data: bool, timeout: int) -> dict:
    cmd = [*rashid_cmd, "check", "--json", "--all"]
    if not data:
        cmd.append("--no-data")
    cmd.append(catalog)
    out: dict = {"command": " ".join(cmd)}
    try:
        version = subprocess.run([*rashid_cmd, "--version"], capture_output=True, text=True, timeout=300)
        out["version"] = version.stdout.strip() or version.stderr.strip()[-200:]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError as exc:
        out["error"] = f"rashid not found: {exc}"
        return out
    except subprocess.TimeoutExpired:
        out["error"] = f"rashid timed out after {timeout}s"
        return out
    try:
        report = json.loads(proc.stdout)
    except ValueError:
        out["error"] = (proc.stderr or proc.stdout).strip()[-1000:]
        return out
    out.update(
        passed=report.get("passed"),
        files_checked=report.get("files_checked"),
        error_count=report.get("error_count"),
        warning_count=report.get("warning_count"),
        info_count=report.get("info_count"),
        by_rule=(report.get("summary") or {}).get("by_rule", []),
        findings=report.get("findings", [])[:300],
    )
    return out


def default_rashid() -> list[str]:
    from shutil import which

    if which("rashid"):
        return ["rashid"]
    if which("uvx"):
        return ["uvx", "--quiet", "rashid"]
    return ["rashid"]


PYTHON_LANGS = {"python", "py", "python3", "ipython", "pycon"}
SHELL_LANGS = {"bash", "sh", "shell", "zsh", "console"}


SQL_SETUP_RE = re.compile(r"^\s*(INSTALL|LOAD|SET|CREATE\s+(OR\s+REPLACE\s+)?(PERSISTENT\s+)?SECRET)\b", re.IGNORECASE)


def sql_setup_statements(code: str) -> list[str]:
    """The statements in a SQL block that change the session: extensions, settings, secrets."""
    text = "\n".join(re.sub(r"--.*$", "", line) for line in code.splitlines())
    return [stmt.strip() + ";" for stmt in text.split(";") if SQL_SETUP_RE.match(stmt)]


def run_doc_code(crawl: Crawl, max_blocks: int, timeout: int, shell: bool) -> list[dict]:
    """Run the SQL and Python blocks in the docs, and the shell blocks when asked.

    Docs often split one program across blocks, as a notebook does. A Python
    block that fails on an undefined name runs again after the earlier
    Python blocks of the same document. A SQL block that fails runs again
    after the setup statements (INSTALL, LOAD, SET, CREATE SECRET) of the
    earlier SQL blocks, and the second result is kept only when it succeeds.
    """
    results: list[dict] = []
    for n in crawl.nodes:
        for kind in ("README.md", "AGENTS.md"):
            doc = n.get(kind)
            if not doc or not doc.get("_blocks"):
                continue
            earlier: list[str] = []
            sql_setup: list[str] = []
            for b in doc["_blocks"]:
                lang = b.lang or "(none)"
                if lang in SQL_LANGS:
                    runner = "sql"
                elif lang in PYTHON_LANGS:
                    runner = "python"
                elif lang in SHELL_LANGS and shell:
                    runner = "shell"
                else:
                    continue
                base = {"node": n["path"] or ".", "doc": kind, "line": b.line, "lang": lang,
                        "code": b.code[:2000], "followed_by": b.after[:200]}
                if len(results) >= max_blocks:
                    results.append({**base, "ok": None, "error": f"not run, over the {max_blocks}-block limit"})
                    continue
                if runner == "sql":
                    res = run_sql(b.code, doc["href"], crawl.local_root, timeout)
                    if not res.get("ok") and sql_setup:
                        again = run_sql("\n".join([*sql_setup, b.code]), doc["href"], crawl.local_root, timeout)
                        if again.get("ok"):
                            again["ran_after_earlier_blocks"] = len(sql_setup)
                            res = again
                    sql_setup.extend(sql_setup_statements(b.code))
                elif runner == "python":
                    res = run_python(b.code, doc["href"], crawl.local_root, timeout)
                    if not res["ok"] and earlier and "NameError" in (res.get("stderr") or ""):
                        again = run_python("\n\n".join([*earlier, b.code]), doc["href"], crawl.local_root, timeout)
                        again["ran_after_earlier_blocks"] = len(earlier)
                        res = again
                    earlier.append(b.code)
                else:
                    res = run_shell(b.code, doc["href"], crawl.local_root, timeout)
                results.append({**base, **res})
    return results


def run_claim_checks(crawl: Crawl, max_blocks: int, timeout: int) -> list[dict]:
    """Run each claim check. A check that returns rows means the claim is false."""
    results = []
    for n in crawl.nodes:
        for kind in ("README.md", "AGENTS.md"):
            doc = n.get(kind) or {}
            for c in doc.get("_claim_checks") or []:
                if len(results) >= max_blocks:
                    results.append({"node": n["path"] or ".", "doc": kind, "line": c["line"], "ok": None, "error": "not run, over the limit"})
                    continue
                res = run_sql(c["sql"], doc["href"], crawl.local_root, timeout)
                res["claim_holds"] = (not res.get("rows")) if res.get("ok") else None
                results.append({"node": n["path"] or ".", "doc": kind, "line": c["line"], "sql": c["sql"][:2000], **res})
    return results


OUT_DIR = Path(".")


def main(argv: list[str] | None = None) -> int:
    global OUT_DIR
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("catalog", help="published root catalog.json URL, or a local catalog directory")
    ap.add_argument("--out", required=True, type=Path, help="directory for facts.json and the saved files")
    ap.add_argument("--repo", type=Path, help="git checkout the catalog is built from")
    ap.add_argument("--rashid", default=None, help="command that runs rashid (default: rashid on PATH, else uvx rashid)")
    ap.add_argument("--no-rashid", action="store_true", help="skip the rashid run")
    ap.add_argument("--rashid-data", action="store_true", help="let rashid read every asset (slow on large catalogs)")
    ap.add_argument("--no-code", action="store_true", help="do not run the code in the documentation")
    ap.add_argument("--run-shell", action="store_true", help="also run the shell blocks in the documentation")
    ap.add_argument("--registry-submission", action="store_true", help="the catalog is being submitted to the registry, so it cannot be registered yet")
    ap.add_argument("--no-links", action="store_true", help="do not probe links")
    ap.add_argument("--no-registry", action="store_true", help="do not look the catalog up in the registry")
    ap.add_argument("--max-blocks", type=int, default=80, help="code blocks and claim checks to run, each")
    ap.add_argument("--max-links", type=int, default=600)
    ap.add_argument("--max-nodes", type=int, default=400)
    ap.add_argument("--timeout", type=int, default=120, help="seconds per query and per fetch")
    ap.add_argument("--rashid-timeout", type=int, default=None, help="seconds for the rashid run (default: 10 times --timeout)")
    args = ap.parse_args(argv)

    started = time.time()
    OUT_DIR = args.out.resolve()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    catalog = args.catalog
    local_root = None
    if not is_url(catalog):
        p = Path(catalog).resolve()
        root_file = p if p.name == "catalog.json" else p / "catalog.json"
        local_root = str(root_file.parent)
        catalog = str(root_file)

    crawl = Crawl(catalog, OUT_DIR, local_root, args.timeout, args.max_nodes)
    crawl_node(crawl, catalog)
    root = crawl.nodes[0] if crawl.nodes and crawl.nodes[0]["href"] == catalog else None

    facts: dict = {
        "schema": "catalog-grader-facts/1",
        "catalog": args.catalog,
        "local": local_root is not None,
        "collected_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "crawl_errors": crawl.errors,
    }

    if root:
        icon = next((l for l in root["links"] if l.get("rel") == "icon"), None)
        if icon:
            target = resolve(catalog, icon["href"])
            got = fetch(target, args.timeout)
            facts["icon"] = {"href": target, "fetched": got.ok, "status": got.status}
            if got.ok:
                ext = os.path.splitext(urllib.parse.urlparse(target).path)[1] or ".img"
                facts["icon"]["saved"] = crawl.save(f"icon{ext}", got.data)
                facts["icon"].update(image_facts(got.data))
        else:
            facts["icon"] = None
        rel = lambda r: next((l.get("href") for l in root["links"] if l.get("rel") == r), None)
        facts["root_links"] = {r: rel(r) for r in ("self", "vcs", "issues", "license", "via", "canonical")}

    facts["rashid"] = (
        {"skipped": True}
        if args.no_rashid
        else run_rashid(args.rashid.split() if args.rashid else default_rashid(), args.catalog if is_url(args.catalog) else local_root, args.rashid_data, args.rashid_timeout or args.timeout * 10)
    )

    if args.no_links:
        facts["links"] = {"skipped": True}
    else:
        targets = sorted(crawl.link_targets)
        checked = targets[: args.max_links]
        with concurrent.futures.ThreadPoolExecutor(16) as pool:
            results = list(pool.map(probe, checked))
            # A connection error or a server error gets one retry.
            retry = [i for i, r in enumerate(results) if r.get("ok") is False and (r.get("status") is None or r["status"] >= 500)]
            for i, r in zip(retry, pool.map(probe, [results[i]["target"] for i in retry])):
                results[i] = r
        for r in results:
            r["cited_in"] = crawl.link_targets[r["target"]][:10]
        refused_codes = {401, 403, 407, 429, 451}
        broken = [r for r in results if r.get("ok") is False and r.get("status") is not None and r["status"] not in refused_codes]
        refused = [r for r in results if r.get("ok") is False and r.get("status") in refused_codes]
        unreachable = [r for r in results if r.get("ok") is False and r.get("status") is None]
        external = [r for r in results if is_url(r["target"])]
        facts["links"] = {
            "total": len(targets),
            "checked": len(checked),
            "ok_count": sum(1 for r in results if r.get("ok")),
            # An HTTP error status, or a local file that does not exist.
            "broken": broken,
            # 401, 403, 429: the host refused the grader. Often a bot block,
            # so the link is unverified, not broken.
            "refused": refused,
            # No HTTP answer at all: DNS, TLS, timeout, or a proxy refusal.
            "unreachable": unreachable,
            # Most external links unanswered points at the grader's network.
            "network_suspect": bool(external) and len(unreachable) + len(refused) > 0.5 * len(external),
            "not_checked": [r for r in results if r.get("ok") is None],
        }

    facts["queries"] = [] if args.no_code else run_doc_code(crawl, args.max_blocks, args.timeout, args.run_shell)
    facts["claim_checks"] = [] if args.no_code else run_claim_checks(crawl, args.max_blocks, args.timeout)
    ran = {(q["node"], q["doc"], q["line"]) for q in facts["queries"]}
    facts["code_blocks_not_run"] = [
        {"node": n["path"] or ".", "doc": kind, "lang": b.lang or "(none)", "line": b.line}
        for n in crawl.nodes
        for kind in ("README.md", "AGENTS.md")
        if n.get(kind) and n[kind].get("_blocks")
        for b in n[kind]["_blocks"]
        if (n["path"] or ".", kind, b.line) not in ran
    ]
    facts["agents_similarity"] = similarity(crawl.nodes, "AGENTS.md")
    facts["readme_similarity"] = similarity(crawl.nodes, "README.md")

    if args.registry_submission:
        facts["registry"] = {"submission": True}
    elif args.no_registry or local_root:
        facts["registry"] = {"skipped": True}
    else:
        got = fetch(REGISTRY_EXPORT, args.timeout)
        if got.ok:
            try:
                urls = registry_urls(got.data)
                facts["registry"] = {"registered": args.catalog.rstrip("/") in urls, "entries": len(urls)}
            except Exception as exc:
                facts["registry"] = {"error": str(exc)}
        else:
            facts["registry"] = {"error": got.error}

    facts["repo"] = repo_facts(args.repo.resolve(), (facts.get("root_links") or {}).get("vcs")) if args.repo else None

    for n in crawl.nodes:
        for kind in ("README.md", "AGENTS.md"):
            if n.get(kind):
                n[kind].pop("_blocks", None)
                n[kind]["claim_check_count"] = len(n[kind].pop("_claim_checks", []) or [])
    facts["nodes"] = crawl.nodes
    facts["summary"] = {
        "catalogs": sum(1 for n in crawl.nodes if n["type"] == "Catalog"),
        "collections": sum(1 for n in crawl.nodes if n["type"] == "Collection"),
        "code_blocks_run": sum(1 for q in facts["queries"] if q.get("ok") is not None),
        "code_blocks_failed": sum(1 for q in facts["queries"] if q.get("ok") is False and not q.get("environment_error")),
        "code_blocks_environment_errors": sum(1 for q in facts["queries"] if q.get("environment_error")),
        "claim_checks_failed": sum(1 for q in facts["claim_checks"] if q.get("claim_holds") is False),
        "links_broken": len(facts["links"].get("broken", [])),
        "links_unverified": len(facts["links"].get("unreachable", [])) + len(facts["links"].get("refused", [])),
        "thumbnails_likely_blank": [n["path"] for n in crawl.nodes if (n.get("thumbnail") or {}).get("likely_blank")],
        "seconds": round(time.time() - started, 1),
    }
    (OUT_DIR / "facts.json").write_text(json.dumps(facts, indent=2, ensure_ascii=False))
    import shutil

    shutil.rmtree(OUT_DIR / "work", ignore_errors=True)  # does not follow the links into the catalog
    print(f"wrote {OUT_DIR / 'facts.json'}")
    print(json.dumps(facts["summary"], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
