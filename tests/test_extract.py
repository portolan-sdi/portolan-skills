"""Bash fence extraction and tokenizing."""

from pathlib import Path


def blocks_of(drift, text: str):
    return drift.extract_blocks(Path("skills/x/SKILL.md"), text.splitlines())


def commands_of(drift, text: str):
    out = []
    for block in blocks_of(drift, text):
        cmds, findings = drift.extract_commands(block)
        assert findings == []
        out.extend(cmds)
    return out


def test_fence_line_numbers(drift):
    text = "intro\n\n```bash\nportolan init\n```\n"
    [block] = blocks_of(drift, text)
    assert block.line == 3
    [cmd] = commands_of(drift, text)
    assert cmd.line == 4


def test_continuation_and_trailing_comment(drift):
    text = "```bash\nportolan add . \\\n  --pmtiles   # build tiles\n```\n"
    [cmd] = commands_of(drift, text)
    assert cmd.argv == ["portolan", "add", ".", "--pmtiles"]


def test_full_line_comment_and_assignment_skipped(drift):
    text = "```bash\n# comment\nTMP=$(mktemp -d)\nFOO=bar portolan add \"$TMP\"\n```\n"
    [cmd] = commands_of(drift, text)
    assert cmd.argv == ["portolan", "add", "PLACEHOLDER"]


def test_placeholders_and_nested_substitution(drift):
    text = '```bash\nSLUG=$(basename "$(dirname "$URL")")\nportolan add <path> {org}/x --collection ${NAME}\n```\n'
    [cmd] = commands_of(drift, text)
    assert cmd.argv == ["portolan", "add", "PLACEHOLDER", "PLACEHOLDER/x", "--collection", "PLACEHOLDER"]


def test_pipes_and_and_split(drift):
    text = "```bash\ncd x && portolan init --auto | tee log; rashid check .\n```\n"
    cmds = commands_of(drift, text)
    assert [c.argv for c in cmds] == [["portolan", "init", "--auto"], ["rashid", "check", "."]]


def test_multiline_quoted_python(drift):
    text = '```bash\nBBOX=$(python3 -c "\nimport json\nprint(1)")\nportolan add .\n```\n'
    [cmd] = commands_of(drift, text)
    assert cmd.argv == ["portolan", "add", "."]


def test_help_lines_and_other_langs_ignored(drift):
    text = "```bash\nportolan add --help\n```\n```python\nportolan add .\n```\n"
    assert commands_of(drift, text) == []


def test_skip_marker_attaches_to_next_fence(drift):
    text = "<!-- drift-skip: shows an old flag on purpose -->\n```bash\nportolan add --old\n```\n```bash\nportolan add .\n```\n"
    first, second = blocks_of(drift, text)
    assert first.skipped == "shows an old flag on purpose"
    assert second.skipped is None


def test_sample_marker(drift):
    text = "<!-- drift-sample: issue -->\n```markdown\n## What happened?\n```\n"
    [block] = blocks_of(drift, text)
    assert block.sample == "issue"


def test_depends_on_header(drift, tmp_path):
    path = tmp_path / "SKILL.md"
    path.write_text("---\nname: x\n---\n<!-- drift: depends-on: portolan-cli, rashid -->\n")
    skill = drift.parse_skill(path)
    assert skill.depends_on == {"portolan-cli", "rashid"}
