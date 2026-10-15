"""skills/enrich-metadata/scripts/find_record.py against recorded portal records.

The JKAN records are trimmed from opendataphilly/opendataphilly-jkan (MIT).
The HDX record is trimmed from the unesco_dataset.json fixture in
OCHA-DAP/hdx-python-api (MIT).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "skills" / "enrich-metadata" / "scripts" / "find_record.py"
FIXTURES = ROOT / "tests" / "fixtures" / "enrich-metadata"
JKAN = FIXTURES / "jkan"
HDX = FIXTURES / "hdx" / "unesco-data-for-zimbabwe.json"


@pytest.fixture(scope="session")
def fr():
    spec = importlib.util.spec_from_file_location("find_record", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["find_record"] = module
    spec.loader.exec_module(module)
    return module


def test_jkan_table_matches_one_record(fr):
    [record] = fr.jkan(JKAN, "opa_properties_public")
    assert record["id"] == "philadelphia-properties-and-assessment-history"
    assert [r["name"] for r in record["matched_resources"]] == [
        "Properties  (CSV)",
        "Properties (GeoJSON)",
        "Properties  (API)",
    ]


def test_jkan_bundle_lists_the_other_tables(fr):
    [record] = fr.jkan(JKAN, "opa_properties_public")
    assert record["bundle"] is True
    assert record["tables_in_record"] == ["assessments", "opa_properties_public"]


def test_jkan_license_name_resolves_to_url(fr):
    [record] = fr.jkan(JKAN, "assessments")
    assert record["license"] == {
        "name": "City of Philadelphia License",
        "url": "https://metadata.phila.gov/#help/help-faqs/what-are-the-terms-of-use/",
    }


def test_jkan_page_slug_word_is_not_a_table(fr):
    # "property-assessments" and "...district-wide-assessments-administered..."
    # contain the word, but neither names the table.
    [record] = fr.jkan(JKAN, "assessments")
    assert record["id"] == "philadelphia-properties-and-assessment-history"
    assert [r["name"] for r in record["matched_resources"]] == [
        "Property Assessment History (CSV)",
        "Property Assessment History (API)",
    ]


def test_jkan_longer_table_name_does_not_match(fr):
    assert fr.jkan(JKAN, "opa_properties") == []
    assert fr.jkan(JKAN, "opa_properties_public_2020") == []


def test_jkan_tab_in_value_still_parses(fr):
    record = fr.front_matter(JKAN / "_datasets" / "real-estate-tax-balances.md")
    assert record["resources"][1]["url"].startswith("https://services.arcgis.com/")


@pytest.mark.parametrize(
    ("url", "table", "expected"),
    [
        ("https://phl.carto.com/api/v2/sql?q=SELECT+*+FROM+a_b", "a_b", True),
        ("https://phl.carto.com/api/v2/sql?q=SELECT+*+FROM+x+JOIN+a_b+ON+1", "a_b", True),
        ("https://phl.carto.com/api/v2/sql?filename=a_b&format=csv", "a_b", True),
        ("https://cityofphiladelphia.github.io/carto-api-explorer/#a_b", "a_b", True),
        ("https://downloads.example.org/a_b.gdb.zip", "a_b", True),
        ("https://downloads.example.org/a_b_2020.csv", "a_b", False),
        ("https://example.org/news/a_b-explained/", "a_b", False),
    ],
)
def test_names_table(fr, url, table, expected):
    assert fr.names_table(url, table) is expected


def test_hdx_hosted_resource_reads_the_dataset(fr):
    pkg = json.loads(HDX.read_text())
    url = pkg["resources"][1]["url"]
    match = fr.CKAN_RESOURCE_RE.search(url)
    assert match.group(1) == pkg["id"]

    [record] = fr.ckan_hosted("https://data.humdata.org", pkg, match.group(2))
    assert record["matched_resources"][0]["name"] == "National Monitoring indicator list"
    assert record["bundle"] is True
    assert len(record["other_resources"]) == 2


def test_hdx_fields_pass_through(fr):
    pkg = json.loads(HDX.read_text())
    record = fr.ckan_record("https://data.humdata.org", pkg)
    # The organization uploaded the data. dataset_source produced it.
    assert record["organization"] == "UNESCO"
    assert record["dataset_source"] == "UNESCO Institute for Statistics (UIS)"
    assert record["dataset_date"] == "[1970-01-01T00:00:00 TO 2019-12-31T23:59:59]"
    assert record["groups"] == ["zwe"]
    assert record["license"]["url"] == "http://creativecommons.org/licenses/by/3.0/igo/legalcode"
    assert "caveats" not in record  # empty upstream


def test_hdx_unknown_resource_id_is_no_match(fr):
    pkg = json.loads(HDX.read_text())
    assert fr.ckan_hosted("https://data.humdata.org", pkg, "not-a-resource") == []


def test_front_matter_value_may_contain_dashes(fr, tmp_path):
    path = tmp_path / "x.md"
    path.write_text("---\ndetails: 'SQL used --- to filter'\ntitle: X\n---\n")
    assert fr.front_matter(path) == {"details": "SQL used --- to filter", "title": "X"}


def test_front_matter_invalid_record_is_skipped(fr, tmp_path, capsys):
    path = tmp_path / "bad.md"
    path.write_text("---\ndetails: 'unterminated\n---\n")
    assert fr.front_matter(path) == {}
    assert "skipped bad.md" in capsys.readouterr().err
