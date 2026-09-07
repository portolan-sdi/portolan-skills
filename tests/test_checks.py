"""Each check against a fake Click tree and fixture ids. No network."""

from pathlib import Path

import pytest

P = Path("skills/x/SKILL.md")


def cmd(drift, *argv):
    return drift.Command(P, 7, list(argv))


def checks(drift, fake_cli, *argv):
    return [(f.check, f.message) for f in drift.check_click_command(cmd(drift, *argv), fake_cli, "cli")]


def test_known_command_and_flags_pass(drift, fake_cli):
    assert checks(drift, fake_cli, "portolan", "add", ".", "--pmtiles", "-c", "x") == []


def test_unknown_subcommand(drift, fake_cli):
    [(check, msg)] = checks(drift, fake_cli, "portolan", "nope")
    assert check == "cli-command"
    assert "nope" in msg


def test_unknown_flag_and_equals_form(drift, fake_cli):
    [(check, msg)] = checks(drift, fake_cli, "portolan", "add", ".", "--depth=2")
    assert check == "cli-flag"
    assert msg.endswith("unknown option --depth")


def test_click_required_option(drift, fake_cli):
    [(check, msg)] = checks(drift, fake_cli, "portolan", "sync", "s3://b")
    assert check == "cli-required"
    assert "--collection" in msg
    assert checks(drift, fake_cli, "portolan", "sync", "s3://b", "-c", "x") == []


def test_runtime_required_license_with_auto(drift, fake_cli):
    [(check, msg)] = checks(drift, fake_cli, "portolan", "init", "--auto")
    assert check == "cli-required"
    assert "--license" in msg
    assert checks(drift, fake_cli, "portolan", "init", "--auto", "--license", "MIT") == []
    # Interactive init prompts for the license, so no flag is required.
    assert checks(drift, fake_cli, "portolan", "init") == []


def test_nested_group(drift, fake_cli):
    assert checks(drift, fake_cli, "portolan", "metadata", "validate") == []
    [(check, _)] = checks(drift, fake_cli, "portolan", "metadata", "init")
    assert check == "cli-command"


def test_id_checks(drift, tmp_path):
    path = tmp_path / "SKILL.md"
    path.write_text("PORTO-CORE-001 is fine. PORTO-FMT-999 is not.\nPTL-DAT-008 ok, PTL-LNK-005 gone.\n")
    skill = drift.parse_skill(path)
    found = drift.check_ids(skill, {"PORTO-CORE-001"}, {"PTL-DAT-008"})
    assert [(f.line, f.check) for f in found] == [(1, "porto-id"), (2, "ptl-id")]


def test_id_checks_skip_when_source_missing(drift, tmp_path):
    path = tmp_path / "SKILL.md"
    path.write_text("PORTO-FMT-999 PTL-LNK-005\n")
    assert drift.check_ids(drift.parse_skill(path), None, None) == []


def test_spec_paths(drift, tmp_path):
    path = tmp_path / "SKILL.md"
    path.write_text("See specs/portolan/core.md and specs/portolan/structure.md.\n")
    found = drift.check_spec_paths(drift.parse_skill(path), {"specs/portolan/core.md"})
    assert [f.message for f in found] == ["specs/portolan/structure.md not in the spec tree"]


def test_sample_body_uses_writing_check(drift, tmp_path):
    hook = tmp_path / "writing_check.py"
    hook.write_text("import sys\nbody = sys.stdin.read()\nsys.exit(1 if 'utilize' in body else 0)\n")
    path = tmp_path / "SKILL.md"
    path.write_text("<!-- drift-sample: issue -->\n```markdown\nWe utilize the tool.\n```\n")
    found = drift.check_samples(drift.parse_skill(path), hook)
    assert len(found) == 1
    assert found[0].check == "sample-body"
    path.write_text("<!-- drift-sample: issue -->\n```markdown\nWe use the tool.\n```\n")
    assert drift.check_samples(drift.parse_skill(path), hook) == []


@pytest.mark.parametrize("mode,blocking", [("pr", False), ("cron", True)])
def test_pin_currency_blocking_by_mode(drift, mode, blocking, monkeypatch):
    monkeypatch.setattr(drift, "latest_version", lambda client, kind, ref: "9.9.9")
    pins = {"portolan-cli": {"version": "0.8.0"}}
    findings, rows = drift.check_pins(pins, client=None, blocking=(mode == "cron"))
    assert [f.blocking for f in findings] == [blocking]
    assert rows[-1] == "| portolan-cli | 0.8.0 | 9.9.9 |"


def test_end_to_end_fixture(drift, fixtures, fake_cli, monkeypatch):
    """The fixture tree has one bad skill. run() must name each defect once."""
    monkeypatch.setattr(drift, "load_click_root", lambda spec: fake_cli)
    monkeypatch.setattr(drift, "load_ptl_ids", lambda: {"PTL-DAT-008"})
    monkeypatch.setattr(drift, "GhHelp", lambda: type("G", (), {"available": False})())
    import io
    import contextlib

    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = drift.run(fixtures, offline=True, mode="pr")
    text = out.getvalue()
    assert code == 1
    assert "skills/bad/SKILL.md:9: cli-flag portolan add: unknown option --nope" in text
    assert "skills/bad/SKILL.md:10: cli-required portolan init: missing required --license" in text
    assert "skills/bad/SKILL.md:13: ptl-id PTL-LNK-005" in text
    assert "--also-nope" not in text
    assert "skills/good/SKILL.md" not in text
    assert "3 findings" in text
