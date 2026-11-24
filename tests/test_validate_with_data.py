"""Check the exception for the rewritten glob in the staged-byte gate."""

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

TOOL = (
    Path(__file__).resolve().parents[1]
    / "skills/portolan-migrate/reference/tools/validate_with_data.py"
)
EXPECTED = {
    "rule_id": "PTL-PRT-002",
    "severity": "error",
    "path": "buildings/collection.json",
    "json_pointer": "/partition:glob",
}
PUBLISHED_GLOB = "s3://bucket/parts/*.parquet"


@pytest.mark.parametrize(
    "findings, returncode, expected_exit",
    [
        ([EXPECTED], 1, 0),
        ([], 0, 1),
        ([EXPECTED], 2, 1),
        ([EXPECTED, EXPECTED | {"path": "other/collection.json"}], 1, 1),
        ([EXPECTED | {"json_pointer": "/assets"}], 1, 1),
        ([EXPECTED, EXPECTED | {"rule_id": "PTL-DAT-008"}], 1, 1),
        ([EXPECTED, EXPECTED | {"rule_id": "PTL-PRT-001"}], 1, 1),
        ([EXPECTED, EXPECTED | {"rule_id": "PTL-DAT-006", "severity": "warning"}], 1, 0),
    ],
)
def test_staged_glob_report(monkeypatch, tmp_path, findings, returncode, expected_exit):
    spec = importlib.util.spec_from_file_location("validate_with_data", TOOL)
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    monkeypatch.setattr(tool, "COLLECTION", "buildings")
    monkeypatch.setattr(tool, "PARTITION_KEY", "zone")
    monkeypatch.setattr(tool, "PARTITION_DIR", "parts")
    monkeypatch.setattr(tool, "CATALOG", tmp_path / "catalog")
    monkeypatch.setattr(tool, "STAGING", tmp_path / "staging")
    published = tool.CATALOG / "buildings" / "collection.json"
    published.parent.mkdir(parents=True)
    published.write_text(json.dumps({"partition:glob": PUBLISHED_GLOB}))
    (tool.STAGING / "parts").mkdir(parents=True)

    def run(argv, *, capture_output, text):
        tree = Path(argv[2])
        assert argv == ["rashid", "check", str(tree), "--data-scope", "all", "--json"]
        assert capture_output and text
        assert (tree / "buildings/parts").is_symlink()
        doc = json.loads((tree / "buildings/collection.json").read_text())
        assert doc["partition:glob"] == "./parts/zone=*/*.parquet"
        return subprocess.CompletedProcess(
            argv, returncode, json.dumps({"findings": findings}), ""
        )

    monkeypatch.setattr(tool.subprocess, "run", run)
    assert tool.main() == expected_exit
    assert json.loads(published.read_text())["partition:glob"] == PUBLISHED_GLOB
