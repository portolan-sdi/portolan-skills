#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml>=6"]
# ///
"""Find the portal record that lists a table or a file, and print it as JSON.

    find_record.py jkan <repo-dir> <table | file-url>
    find_record.py ckan <base-url> <table | file-url>
    find_record.py socrata <domain> <dataset-id>

A JKAN portal is a Jekyll site built from a git repository. Its records are
`_datasets/*.md` front matter. The site's /datasets.json omits resource URLs,
so read the repository, not the site. The script reads both record shapes in
use: the JKAN default (OpenDataPhilly) and RDLS (the Risk Data Library).

A file URL matches a resource with the same URL. A table name matches when a
resource URL names the table as a table:
in a Carto SQL FROM or JOIN, as the Carto API explorer anchor, as the
`filename=` parameter, or as a file name such as `opa_properties_public.csv`.
A word in a page slug does not match, and `opa_properties_public_2020` does
not match `opa_properties_public`.

A CKAN-hosted file, such as an HDX download, has the dataset id in its URL:
`/dataset/<id>/resource/<id>/download/...`. Pass that URL and the script reads
the dataset directly instead of searching.

Exit 0 on one match, 1 on none, 2 on more than one.
"""

from __future__ import annotations

import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import yaml

# Carto SQL URLs name their tables after FROM or JOIN. The Philadelphia Carto
# API explorer names one table in the fragment.
SQL_TABLE_RE = re.compile(r"(?i)\b(?:from|join)\s+([a-z0-9_]+(?:\.[a-z0-9_]+)?)")


def url_text(url: str) -> str:
    return urllib.parse.unquote_plus(url or "").strip()


def tables_in(url: str) -> set[str]:
    """Tables a Carto SQL URL or the Carto API explorer names."""
    text = url_text(url)
    found = set()
    if "carto.com" in text:
        query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query).get("q", [])
        for sql in query:
            found.update(t.lower() for t in SQL_TABLE_RE.findall(sql))
    if "carto-api-explorer" in text and "#" in text:
        found.add(text.split("#", 1)[1].lower())
    return found


def names_table(url: str, table: str) -> bool:
    table = table.lower()
    if table in tables_in(url):
        return True
    parsed = urllib.parse.urlparse(url_text(url))
    query = urllib.parse.parse_qs(parsed.query)
    if table in (f.lower() for f in query.get("filename", [])):
        return True
    # opa_properties_public.csv and opa_properties_public.gdb.zip
    stem = parsed.path.rsplit("/", 1)[-1].split(".", 1)[0].lower()
    return stem == table


def is_url(key: str) -> bool:
    return key.startswith(("http://", "https://"))


def same_url(a: str, b: str) -> bool:
    return url_text(a).rstrip("/") == url_text(b).rstrip("/")


def names_key(url: str, key: str) -> bool:
    return same_url(url, key) if is_url(key) else names_table(url, key)


def resource_url(res: dict) -> str:
    # JKAN and CKAN use `url`. RDLS uses `download_url` and `access_url`.
    for field in ("url", "download_url", "access_url"):
        if res.get(field):
            return str(res[field]).strip()
    return ""


def resource_view(res: dict) -> dict:
    return {
        "name": res.get("name") or res.get("title"),
        "description": res.get("description"),
        "format": res.get("format") or res.get("media_type"),
        "url": resource_url(res),
    }


def match(record: dict, key: str, resources: list[dict]) -> dict | None:
    hits = [r for r in resources if names_key(resource_url(r), key)]
    if not hits:
        return None
    record["matched_resources"] = [resource_view(r) for r in hits]
    record["other_resources"] = [resource_view(r)["name"] for r in resources if r not in hits]
    if is_url(key):
        record["bundle"] = len(resources) > 1
    else:
        tables = set().union(*(tables_in(resource_url(r)) for r in resources)) | {key.lower()}
        record["tables_in_record"] = sorted(tables)
        record["bundle"] = len(tables) > 1
    return record


FRONT_MATTER_RE = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*$", re.DOTALL | re.MULTILINE)


def front_matter(path: Path) -> dict:
    found = FRONT_MATTER_RE.search(path.read_text(encoding="utf-8"))
    if not found:
        return {}
    text = found.group(1)
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError:
        # Some records carry a tab inside a value, which YAML forbids.
        try:
            data = yaml.safe_load(text.replace("\t", " "))
        except yaml.YAMLError as err:
            print(f"skipped {path.name}: invalid front matter ({err.problem})", file=sys.stderr)
            return {}
    return data if isinstance(data, dict) else {}


# RDLS fields passed through as published. See docs.riskdatalibrary.org.
RDLS_FIELDS = (
    "risk_data_type",
    "creator",
    "publisher",
    "contact_point",
    "attributions",
    "temporal",
    "spatial",
    "details",
    "lineage",
    "referenced_by",
    "catalog",
)


def jkan_record(path: Path, fm: dict, licenses: dict) -> dict:
    record = {
        "portal": "jkan",
        "id": path.stem,
        "path": f"/datasets/{path.stem}/",
        "title": fm.get("title"),
    }
    if str(fm.get("schema", "")).startswith("rdls"):
        record["schema"] = fm["schema"]
        record["description"] = fm.get("description")
        record["license"] = {"name": fm.get("license"), "url": None}
        record.update({k: fm[k] for k in RDLS_FIELDS if fm.get(k)})
        record["links"] = [
            link.get("href") for link in fm.get("links") or [] if link.get("rel") != "describedby"
        ]
        return record
    record.update(
        {
            "description": fm.get("notes"),
            "organization": fm.get("organization"),
            "category": fm.get("category"),
            "tags": fm.get("tags"),
            "license": {"name": fm.get("license"), "url": licenses.get(fm.get("license"))},
            "maintainer": fm.get("maintainer"),
            "maintainer_email": fm.get("maintainer_email"),
        }
    )
    return record


def jkan(repo: Path, key: str) -> list[dict]:
    licenses_file = repo / "_data" / "licenses.yml"
    licenses = {}
    if licenses_file.is_file():
        items = (yaml.safe_load(licenses_file.read_text(encoding="utf-8")) or {}).get("items", [])
        licenses = {i.get("name"): i.get("url") for i in items}

    # Parse only the records whose text names the key. The Risk Data Library
    # holds nearly 10,000 records, and parsing all of them takes minutes.
    needle = (url_text(key).rstrip("/") if is_url(key) else key).lower()
    out = []
    for path in sorted((repo / "_datasets").glob("*.md")):
        if needle not in url_text(path.read_text(encoding="utf-8")).lower():
            continue
        fm = front_matter(path)
        record = jkan_record(path, fm, licenses)
        if (hit := match(record, key, fm.get("resources") or [])) is not None:
            out.append(hit)
    return out


def get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


# Fields HDX adds to CKAN. Other CKAN portals add their own; read the raw
# package_show output when a portal has a field this list does not name.
HDX_FIELDS = (
    "dataset_source",
    "methodology",
    "methodology_other",
    "caveats",
    "dataset_date",
    "data_update_frequency",
    "license_other",
)
CKAN_RESOURCE_RE = re.compile(r"/dataset/([^/]+)/resource/([^/?#]+)")


def ckan_record(base: str, pkg: dict) -> dict:
    record = {
        "portal": "ckan",
        "id": pkg.get("name"),
        "path": f"{base}/dataset/{pkg.get('name')}",
        "title": pkg.get("title"),
        "description": pkg.get("notes"),
        "organization": (pkg.get("organization") or {}).get("title"),
        "groups": [g.get("name") for g in pkg.get("groups") or []],
        "tags": [t.get("name") for t in pkg.get("tags") or []],
        "license": {
            "id": pkg.get("license_id"),
            "name": pkg.get("license_title"),
            "url": pkg.get("license_url"),
        },
        "maintainer": pkg.get("maintainer"),
        "maintainer_email": pkg.get("maintainer_email"),
    }
    record.update({k: pkg[k] for k in HDX_FIELDS if pkg.get(k)})
    return record


def ckan_hosted(base: str, pkg: dict, resource_id: str) -> list[dict]:
    resources = pkg.get("resources") or []
    hits = [r for r in resources if r.get("id") == resource_id]
    record = ckan_record(base, pkg)
    record["matched_resources"] = [resource_view(r) for r in hits]
    record["other_resources"] = [resource_view(r)["name"] for r in resources if r not in hits]
    record["bundle"] = len(resources) > 1
    return [record] if hits else []


def ckan(base: str, key: str) -> list[dict]:
    base = base.rstrip("/")
    if hosted := CKAN_RESOURCE_RE.search(key):
        pkg = get_json(f"{base}/api/3/action/package_show?id={hosted.group(1)}")["result"]
        return ckan_hosted(base, pkg, hosted.group(2))

    # CKAN copies each resource URL into the tokenized `urls` Solr field.
    # The tokenizer splits on underscores, so the phrase also hits longer
    # table names. match() keeps the resources that name the table.
    q = urllib.parse.urlencode({"q": f'urls:"{key}"', "rows": 100})
    results = get_json(f"{base}/api/3/action/package_search?{q}")["result"]["results"]
    out = []
    for pkg in results:
        hit = match(ckan_record(base, pkg), key, pkg.get("resources") or [])
        if hit is not None:
            out.append(hit)
    return out


def socrata(domain: str, dataset_id: str) -> list[dict]:
    # A Socrata data URL carries the dataset id (/resource/abcd-1234.json),
    # so there is nothing to search.
    domain = domain.removeprefix("https://").rstrip("/")
    view = get_json(f"https://{domain}/api/views/{dataset_id}.json")
    lic = view.get("license") or {}
    return [
        {
            "portal": "socrata",
            "id": dataset_id,
            "path": f"https://{domain}/d/{dataset_id}",
            "title": view.get("name"),
            "description": view.get("description"),
            "category": view.get("category"),
            "tags": view.get("tags"),
            "attribution": view.get("attribution"),
            "attribution_link": view.get("attributionLink"),
            "license": {
                "id": view.get("licenseId"),
                "name": lic.get("name"),
                "url": lic.get("termsLink"),
            },
            "bundle": False,
        }
    ]


def main(argv: list[str]) -> int:
    if len(argv) != 4 or argv[1] not in ("jkan", "ckan", "socrata"):
        print(__doc__, file=sys.stderr)
        return 64
    kind, where, key = argv[1:]
    if kind == "jkan":
        records = jkan(Path(where), key)
    elif kind == "ckan":
        records = ckan(where, key)
    else:
        records = socrata(where, key)
    print(json.dumps(records, indent=2, ensure_ascii=False))
    if not records:
        return 1
    return 0 if len(records) == 1 else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
