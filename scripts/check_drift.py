#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml>=6", "httpx>=0.27", "click>=8"]
# ///
"""Check every SKILL.md against the tools and the spec it depends on.

The skills restate nothing that the CLI, the validator, or the spec can
answer. What they do state, this script checks against the pinned versions
in pins.toml:

- cli-command, cli-flag, cli-required: every `portolan ...` line in a bash
  fence names a command and flags that the pinned portolan-cli accepts.
- rashid-flag: same for `rashid ...` lines against the pinned rashid.
- gh-flag: every `gh ...` line uses flags that `gh <cmd> --help` lists.
- porto-id: every PORTO-CORE-NNN or PORTO-FMT-NNN id exists in the spec
  manifest at the pinned tag.
- ptl-id: every PTL-XXX-NNN id exists in the pinned rashid registry.
- spec-path: every `specs/.../*.md` path exists in the spec tree at the tag.
- sample-body: every markdown fence marked `<!-- drift-sample: issue -->` or
  `<!-- drift-sample: pr -->` passes .claude/hooks/writing_check.py.
- pin-currency: the pins match the latest release of each upstream. This
  check reports on a pull request and blocks on the weekly cron.

Usage:
    uv run scripts/check_drift.py [--offline] [--mode pr|cron] [--root DIR]

Exit 1 on any blocking finding. Each finding prints as
`<path>:<line>: <check-id> <message>`.

Exempt one fenced block from the command checks with a comment on the line
before the fence: `<!-- drift-skip: <reason of 8 or more characters> -->`.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

import click
import httpx
import yaml

FENCE_RE = re.compile(r"^(\s*)```([A-Za-z0-9_-]*)\s*$")
SKIP_RE = re.compile(r"<!--\s*drift-skip:\s*(.{8,}?)\s*-->")
SAMPLE_RE = re.compile(r"<!--\s*drift-sample:\s*(issue|pr)\s*-->")
DEPENDS_RE = re.compile(r"<!--\s*drift:\s*depends-on:\s*([a-z0-9, -]+?)\s*-->")
PORTO_RE = re.compile(r"\bPORTO-(?:CORE|FMT)-\d{3}\b")
PTL_RE = re.compile(r"\bPTL-[A-Z]{3}-\d{3}\b")
SPEC_PATH_RE = re.compile(r"\bspecs/[A-Za-z0-9_./-]+\.md\b")
FLAG_RE = re.compile(r"^--?[A-Za-z]")
PLACEHOLDER_RE = re.compile(r"<[^<>\s]+>|\{[^{}\s]+\}|\$\{[^}]*\}|\$[A-Za-z_][A-Za-z0-9_]*")
GH_FLAG_RE = re.compile(r"(?m)^\s+(?:-[A-Za-z], )?(--[a-z][a-z0-9-]*)")

SHELL_LANGS = {"bash", "sh", "shell", "zsh", ""}
TARGET_COMMANDS = {"portolan", "rashid", "gh"}
CLICK_ROOTS = {"portolan": "portolan_cli:cli", "rashid": "rashid.cli:main"}

# Options the CLI enforces at runtime rather than through Click's
# `required`. portolan init prompts for a license unless --auto or --json
# is passed, then exits with PRTLN-VAL004 when it is missing.
RUNTIME_REQUIRED = {
    ("portolan", "init"): ({"--auto", "--json"}, {"--license"}),
}

UPSTREAMS = {
    "portolan-cli": ("pypi", "portolan-cli"),
    "rashid": ("pypi", "rashid"),
    "portolan-spec": ("release", "portolan-sdi/portolan-spec"),
    "portolan-catalog-template": ("head", "portolan-sdi/portolan-catalog-template"),
    "portolan-registry": ("head", "portolan-sdi/portolan-registry"),
}


@dataclass
class Finding:
    path: Path
    line: int
    check: str
    message: str
    blocking: bool = True

    def render(self, root: Path) -> str:
        rel = self.path.relative_to(root) if self.path.is_absolute() else self.path
        level = "" if self.blocking else " (warning)"
        return f"{rel}:{self.line}: {self.check}{level} {self.message}"


@dataclass
class Block:
    path: Path
    line: int
    lang: str
    lines: list[str]
    skipped: str | None = None
    sample: str | None = None


@dataclass
class Command:
    path: Path
    line: int
    argv: list[str]

    @property
    def name(self) -> str:
        return self.argv[0]


@dataclass
class Skill:
    path: Path
    text: str
    depends_on: set[str] = field(default_factory=set)
    blocks: list[Block] = field(default_factory=list)


# --------------------------------------------------------------- extraction


def parse_skill(path: Path) -> Skill:
    text = path.read_text(encoding="utf-8")
    skill = Skill(path=path, text=text)
    m = DEPENDS_RE.search(text)
    if m:
        skill.depends_on = {d.strip() for d in m.group(1).split(",") if d.strip()}
    skill.blocks = extract_blocks(path, text.splitlines())
    return skill


def extract_blocks(path: Path, lines: list[str]) -> list[Block]:
    blocks: list[Block] = []
    current: Block | None = None
    pending_skip: str | None = None
    pending_sample: str | None = None
    for idx, raw in enumerate(lines, start=1):
        m = FENCE_RE.match(raw)
        if current is None:
            if m:
                current = Block(path, idx, m.group(2).lower(), [])
                current.skipped = pending_skip
                current.sample = pending_sample
                pending_skip = pending_sample = None
                continue
            stripped = raw.strip()
            if not stripped:
                continue
            sm = SKIP_RE.search(raw)
            if sm:
                pending_skip = sm.group(1)
                continue
            am = SAMPLE_RE.search(raw)
            if am:
                pending_sample = am.group(1)
                continue
            pending_skip = pending_sample = None
        else:
            if m and m.group(2) == "":
                blocks.append(current)
                current = None
            else:
                current.lines.append(raw)
    return blocks


def logical_lines(lines: list[str]) -> list[tuple[int, str]]:
    """Join backslash continuations and drop full-line comments.

    Returns (offset, text) pairs, where offset counts from the first body
    line of the block.
    """
    out: list[tuple[int, str]] = []
    buf: list[str] = []
    start = 0
    for i, raw in enumerate(lines):
        if not buf and raw.lstrip().startswith("#"):
            continue
        if not buf:
            start = i
        if raw.rstrip().endswith("\\"):
            buf.append(raw.rstrip()[:-1])
            continue
        buf.append(raw)
        out.append((start, " ".join(part.strip() for part in buf)))
        buf = []
    if buf:
        out.append((start, " ".join(part.strip() for part in buf)))
    return out


def mask_substitutions(text: str) -> str:
    """Replace every `$( ... )`, nested or not, with PLACEHOLDER."""
    out: list[str] = []
    i = 0
    while i < len(text):
        if text.startswith("$(", i):
            depth = 0
            j = i
            while j < len(text):
                if text.startswith("$(", j):
                    depth += 1
                    j += 2
                    continue
                if text[j] == "(":
                    depth += 1
                elif text[j] == ")":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            if depth != 0:
                # Unclosed on this line. Leave it so the quote check can
                # absorb the following lines, then mask on the retry.
                out.append(text[i:])
                break
            out.append("PLACEHOLDER")
            i = j + 1
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def split_commands(text: str) -> list[list[str]]:
    """Tokenize one logical shell line into simple commands."""
    text = PLACEHOLDER_RE.sub("PLACEHOLDER", mask_substitutions(text))
    lexer = shlex.shlex(text, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    lexer.commenters = "#"
    tokens = list(lexer)
    commands: list[list[str]] = []
    current: list[str] = []
    for tok in tokens:
        if tok in {"&&", "||", ";", "|", ";;", "&"}:
            if current:
                commands.append(current)
            current = []
        elif tok in {"(", ")", "<", ">", ">>", "<<", "2>", "&>"}:
            continue
        else:
            current.append(tok)
    if current:
        commands.append(current)
    return commands


def extract_commands(block: Block) -> tuple[list[Command], list[Finding]]:
    commands: list[Command] = []
    findings: list[Finding] = []
    if block.lang not in SHELL_LANGS:
        return commands, findings
    pending: list[tuple[int, str]] = list(logical_lines(block.lines))
    while pending:
        offset, text = pending.pop(0)
        line = block.line + 1 + offset
        parts: list[list[str]] | None = None
        # A quoted string may span lines (python -c "..."). Absorb following
        # logical lines until the quote closes.
        for _ in range(40):
            try:
                parts = split_commands(text)
                break
            except ValueError as exc:
                if "No closing quotation" in str(exc) and pending:
                    text = text + "\n" + pending.pop(0)[1]
                    continue
                findings.append(Finding(block.path, line, "parse-error", f"{exc}: {text[:60]}"))
                break
        if parts is None:
            continue
        for argv in parts:
            argv = [a for a in argv if a]
            if not argv:
                continue
            # Strip leading env assignments such as FOO=bar cmd.
            while argv and "=" in argv[0] and not argv[0].startswith("-"):
                argv = argv[1:]
            if not argv or argv[0] not in TARGET_COMMANDS:
                continue
            if "--help" in argv or "-h" in argv:
                continue
            commands.append(Command(block.path, line, argv))
    return commands, findings


def split_flags(argv: list[str], value_flags: set[str] = frozenset()) -> tuple[list[str], list[str]]:
    """Return (positionals, flags). `--x=v` yields `--x`.

    A flag in `value_flags` consumes the next token as its value, so that
    value is not mistaken for a positional (`portolan --format json check`).
    """
    positionals: list[str] = []
    flags: list[str] = []
    skip = False
    for tok in argv[1:]:
        if skip:
            skip = False
            continue
        if tok == "--":
            break
        if FLAG_RE.match(tok):
            name = tok.split("=", 1)[0]
            flags.append(name)
            skip = name in value_flags and "=" not in tok
        else:
            positionals.append(tok)
    return positionals, flags


def value_options(cmd: click.Command) -> set[str]:
    """Options of `cmd` that take a value (not flags)."""
    out: set[str] = set()
    for param in cmd.params:
        if isinstance(param, click.Option) and not param.is_flag:
            out.update(param.opts)
            out.update(param.secondary_opts)
    return out


# ----------------------------------------------------------- click checks


def load_click_root(spec: str) -> click.Command:
    module_name, attr = spec.split(":")
    module = importlib.import_module(module_name)
    return getattr(module, attr)


def resolve_command(root: click.Command, positionals: list[str]) -> tuple[click.Command, list[str], list[str]]:
    """Walk groups greedily. Returns (command, path, remaining positionals)."""
    cmd = root
    path: list[str] = []
    rest = list(positionals)
    while isinstance(cmd, click.Group) and rest and rest[0] in cmd.commands:
        path.append(rest[0])
        cmd = cmd.commands[rest.pop(0)]
    return cmd, path, rest


def accepted_flags(cmd: click.Command) -> set[str]:
    flags: set[str] = {"--help"}
    for param in cmd.params:
        if isinstance(param, click.Option):
            flags.update(param.opts)
            flags.update(param.secondary_opts)
    return flags


def required_flags(cmd: click.Command) -> list[set[str]]:
    out: list[set[str]] = []
    for param in cmd.params:
        if isinstance(param, click.Option) and param.required:
            out.append(set(param.opts) | set(param.secondary_opts))
    return out


def collect_value_options(root: click.Command) -> set[str]:
    out = value_options(root)
    if isinstance(root, click.Group):
        for sub in root.commands.values():
            out |= collect_value_options(sub)
    return out


def check_click_command(command: Command, root: click.Command, prefix: str) -> list[Finding]:
    findings: list[Finding] = []
    positionals, flags = split_flags(command.argv, collect_value_options(root))
    cmd, path, rest = resolve_command(root, positionals)
    shown = " ".join([command.name, *path])
    if isinstance(cmd, click.Group):
        if not rest and cmd is root and flags:
            # `portolan --version` or `portolan --format json`: root only.
            pass
        else:
            candidate = rest[0] if rest else "(none)"
            findings.append(
                Finding(command.path, command.line, f"{prefix}-command", f"{shown}: no subcommand named {candidate}")
            )
            return findings
    allowed = accepted_flags(cmd)
    # Options of the groups on the path are accepted anywhere on the line.
    node = root
    allowed |= accepted_flags(node)
    for name in path:
        node = node.commands[name]
        allowed |= accepted_flags(node)
    for flag in flags:
        if flag not in allowed:
            findings.append(Finding(command.path, command.line, f"{prefix}-flag", f"{shown}: unknown option {flag}"))
    present = set(flags)
    for group in required_flags(cmd):
        if not present & group:
            findings.append(
                Finding(command.path, command.line, f"{prefix}-required", f"{shown}: missing required {sorted(group)[0]}")
            )
    when, need = RUNTIME_REQUIRED.get((command.name, *path), (set(), set()))
    if when & present and not need & present:
        findings.append(
            Finding(command.path, command.line, f"{prefix}-required", f"{shown}: missing required {sorted(need)[0]}")
        )
    return findings


# --------------------------------------------------------------- gh check


class GhHelp:
    def __init__(self) -> None:
        self.cache: dict[tuple[str, ...], set[str] | None] = {}
        self.available = shutil.which("gh") is not None

    def flags(self, path: tuple[str, ...]) -> set[str] | None:
        if path in self.cache:
            return self.cache[path]
        try:
            proc = subprocess.run(["gh", *path, "--help"], capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.TimeoutExpired):
            self.cache[path] = None
            return None
        if proc.returncode != 0:
            self.cache[path] = None
            return None
        found = set(GH_FLAG_RE.findall(proc.stdout)) | {"--help"}
        self.cache[path] = found
        return found


def check_gh_command(command: Command, helper: GhHelp) -> list[Finding]:
    if not helper.available:
        return []
    positionals, flags = split_flags(command.argv)
    # gh <group> <cmd>: the first two positionals name the command.
    path = tuple(p for p in positionals[:2] if p != "PLACEHOLDER")
    if not path:
        return []
    known = helper.flags(path)
    if known is None and len(path) == 2:
        known = helper.flags(path[:1])
    if known is None:
        return [Finding(command.path, command.line, "gh-command", f"gh {' '.join(path)}: no such command")]
    shown = " ".join(["gh", *path])
    return [
        Finding(command.path, command.line, "gh-flag", f"{shown}: unknown option {f}")
        for f in flags
        if f not in known and f.startswith("--")
    ]


# ------------------------------------------------------------ id checks


def check_ids(skill: Skill, porto_ids: set[str] | None, ptl_ids: set[str] | None) -> list[Finding]:
    findings: list[Finding] = []
    for idx, line in enumerate(skill.text.splitlines(), start=1):
        if porto_ids is not None:
            for rid in PORTO_RE.findall(line):
                if rid not in porto_ids:
                    findings.append(Finding(skill.path, idx, "porto-id", f"{rid} not in the spec manifest"))
        if ptl_ids is not None:
            for rid in PTL_RE.findall(line):
                if rid not in ptl_ids:
                    findings.append(Finding(skill.path, idx, "ptl-id", f"{rid} not in the rashid registry"))
    return findings


def check_spec_paths(skill: Skill, spec_paths: set[str]) -> list[Finding]:
    findings: list[Finding] = []
    for idx, line in enumerate(skill.text.splitlines(), start=1):
        for p in SPEC_PATH_RE.findall(line):
            if p not in spec_paths:
                findings.append(Finding(skill.path, idx, "spec-path", f"{p} not in the spec tree"))
    return findings


# ------------------------------------------------------- sample bodies


def check_samples(skill: Skill, writing_check: Path) -> list[Finding]:
    findings: list[Finding] = []
    for block in skill.blocks:
        if block.sample is None:
            continue
        body = "\n".join(block.lines) + "\n"
        proc = subprocess.run(
            [sys.executable, str(writing_check), "--kind", block.sample, "--stdin"],
            input=body,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout).strip().splitlines()
            problems = [d for d in detail if re.match(r"^L\d+:", d.strip())] or detail[:3]
            if not problems:
                problems = [f"writing_check.py exited {proc.returncode}"]
            for d in problems:
                findings.append(Finding(skill.path, block.line, "sample-body", d.strip()))
    return findings


# ------------------------------------------------------------- network


def fetch_json(client: httpx.Client, url: str) -> dict:
    headers = {}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token and "api.github.com" in url:
        headers["Authorization"] = f"Bearer {token}"
    resp = client.get(url, headers=headers, follow_redirects=True, timeout=30)
    resp.raise_for_status()
    return resp.json()


def cached(cache_dir: Path, key: str, loader) -> object:
    cache_dir.mkdir(exist_ok=True)
    path = cache_dir / f"{key}.json"
    if path.exists():
        return json.loads(path.read_text())
    value = loader()
    path.write_text(json.dumps(value))
    return value


def spec_manifest_ids(client: httpx.Client, tag: str) -> list[str]:
    url = f"https://raw.githubusercontent.com/portolan-sdi/portolan-spec/{tag}/specs/portolan/requirements.yaml"
    resp = client.get(url, timeout=30)
    resp.raise_for_status()
    data = yaml.safe_load(resp.text)
    return [entry["id"] for entry in data.get("requirements", [])]


def spec_tree_paths(client: httpx.Client, tag: str) -> list[str]:
    data = fetch_json(client, f"https://api.github.com/repos/portolan-sdi/portolan-spec/git/trees/{tag}?recursive=1")
    return [e["path"] for e in data.get("tree", []) if e["path"].endswith(".md")]


def latest_version(client: httpx.Client, kind: str, ref: str) -> str:
    if kind == "pypi":
        return fetch_json(client, f"https://pypi.org/pypi/{ref}/json")["info"]["version"]
    if kind == "release":
        return fetch_json(client, f"https://api.github.com/repos/{ref}/releases/latest")["tag_name"]
    if kind == "head":
        return fetch_json(client, f"https://api.github.com/repos/{ref}/commits/main")["sha"][:7]
    raise ValueError(kind)


def check_pins(pins: dict, client: httpx.Client, blocking: bool) -> tuple[list[Finding], list[str]]:
    findings: list[Finding] = []
    rows = ["| Upstream | Pinned | Latest |", "|---|---|---|"]
    for name, (kind, ref) in UPSTREAMS.items():
        entry = pins.get(name, {})
        pinned = entry.get("version") or entry.get("tag") or entry.get("sha")
        if not pinned:
            continue
        try:
            latest = latest_version(client, kind, ref)
        except (httpx.HTTPError, KeyError) as exc:
            rows.append(f"| {name} | {pinned} | (fetch failed: {exc}) |")
            continue
        rows.append(f"| {name} | {pinned} | {latest} |")
        if latest != pinned:
            findings.append(Finding(Path("pins.toml"), 1, "pin-currency", f"{name} pinned {pinned}, latest {latest}", blocking))
    return findings, rows


# ----------------------------------------------------------------- main


def load_ptl_ids() -> set[str] | None:
    try:
        registry = importlib.import_module("rashid.registry")
    except ImportError:
        return None
    return set(registry.CHECKS)


def run(root: Path, offline: bool, mode: str) -> int:
    pins = tomllib.loads((root / "pins.toml").read_text())
    skills = [parse_skill(p) for p in sorted((root / "skills").glob("*/SKILL.md"))]
    writing_check = root / ".claude" / "hooks" / "writing_check.py"
    cache_dir = root / ".drift-cache"
    findings: list[Finding] = []
    notes: list[str] = []

    roots: dict[str, click.Command] = {}
    for name, spec in CLICK_ROOTS.items():
        try:
            roots[name] = load_click_root(spec)
        except ImportError:
            notes.append(f"{name} is not installed, command checks skipped")
    gh = GhHelp()
    if not gh.available:
        notes.append("gh is not installed, gh checks skipped")
    ptl_ids = load_ptl_ids()
    if ptl_ids is None:
        notes.append("rashid is not installed, ptl-id check skipped")

    porto_ids: set[str] | None = None
    spec_paths: set[str] | None = None
    pin_rows: list[str] = []
    tag = pins["portolan-spec"]["tag"]
    with httpx.Client() as client:
        try:
            if offline and not (cache_dir / f"manifest-{tag}.json").exists():
                notes.append("offline and no cache, porto-id and spec-path skipped")
            else:
                porto_ids = set(cached(cache_dir, f"manifest-{tag}", lambda: spec_manifest_ids(client, tag)))
                spec_paths = set(cached(cache_dir, f"tree-{tag}", lambda: spec_tree_paths(client, tag)))
        except httpx.HTTPError as exc:
            notes.append(f"spec fetch failed ({exc}), porto-id and spec-path skipped")
        if not offline:
            pin_findings, pin_rows = check_pins(pins, client, blocking=(mode == "cron"))
            findings.extend(pin_findings)

    for skill in skills:
        for block in skill.blocks:
            commands, parse_findings = extract_commands(block)
            findings.extend(parse_findings)
            if block.skipped:
                continue
            for command in commands:
                if command.name in roots:
                    findings.extend(check_click_command(command, roots[command.name], command.name if command.name == "rashid" else "cli"))
                elif command.name == "gh":
                    findings.extend(check_gh_command(command, gh))
        findings.extend(check_ids(skill, porto_ids, ptl_ids))
        if spec_paths is not None:
            findings.extend(check_spec_paths(skill, spec_paths))
        if writing_check.exists():
            findings.extend(check_samples(skill, writing_check))

    for f in findings:
        print(f.render(root))
    for note in notes:
        print(f"note: {note}")
    if pin_rows:
        print()
        print("\n".join(pin_rows))
    blocking = [f for f in findings if f.blocking]
    warnings = len(findings) - len(blocking)
    print()
    print(f"check_drift: {len(skills)} skills, {len(blocking)} findings, {warnings} warnings")
    return 1 if blocking else 0


def bootstrap(root: Path, argv: list[str]) -> None:
    """Re-run under `uv run --with` so the pinned CLI and rashid import.

    `uv run scripts/check_drift.py` resolves only the inline dependencies.
    The command checks need portolan-cli and rashid at the versions in
    pins.toml, so when either import fails this re-executes the script with
    those packages added. The environment flag stops a second hop.
    """
    if os.environ.get("CHECK_DRIFT_BOOTSTRAPPED") or shutil.which("uv") is None:
        return
    try:
        importlib.import_module("portolan_cli")
        importlib.import_module("rashid.registry")
        return
    except ImportError:
        pass
    pins = tomllib.loads((root / "pins.toml").read_text())
    cli = pins["portolan-cli"]["version"]
    rashid = pins["rashid"]["version"]
    env = dict(os.environ, CHECK_DRIFT_BOOTSTRAPPED="1")
    cmd = [
        "uv", "run", "--quiet",
        "--with", f"portolan-cli=={cli}",
        "--with", f"rashid=={rashid}",
        "--script", str(Path(__file__).resolve()),
        *argv,
    ]
    os.execvpe("uv", cmd, env)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--offline", action="store_true", help="skip network checks; use the cache when present")
    parser.add_argument("--mode", choices=["pr", "cron"], default="pr", help="cron makes pin-currency blocking")
    parser.add_argument("--no-bootstrap", action="store_true", help="do not re-run under uv with the pinned tools")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if not args.no_bootstrap:
        bootstrap(root, sys.argv[1:] if argv is None else argv)
    return run(root, args.offline, args.mode)


if __name__ == "__main__":
    sys.exit(main())
