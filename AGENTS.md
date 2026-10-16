<!-- ops-sync:begin — synced from portolan-sdi/portolan-ops. Edit there, not here. -->
# Portolan agent norms

All agents MUST read this document before starting work, with no exceptions, ever. (Claude Code does not read `AGENTS.md` but imports this file via a one-line `CLAUDE.md`.) Most of this content is synced downstream from `portolan-ops`. Put repo-specific instructions in `AGENTS.md`, never in `CLAUDE.md`, which the sync overwrites.

## Ground rules

Agents MUST read the complete contents of [norms](https://github.com/portolan-sdi/portolan-ops/blob/main/norms) and [policies](https://github.com/portolan-sdi/portolan-ops/blob/main/policies/) before starting work, with no exceptions, ever.

The [portolan-spec](https://github.com/portolan-sdi/portolan-spec) repo is the absolute ground truth for the Portolan spec. All other tools are downstream of it.

Before documenting any command, flag, or API, verify that it exists.

Use conventional commits always.

All tickets and PRs MUST follow the [templates](https://github.com/portolan-sdi/portolan-ops/blob/main/templates/).

## Org-wide facts

The canonical homepage is <https://www.portolan-sdi.org/>. Canonical URLs live in [copy/urls.md](https://github.com/portolan-sdi/portolan-ops/blob/main/copy/urls.md). Do not hardcode variants.

Community discussion happens in the [Portolan Google Group](https://groups.google.com/g/portolan) and the [Portolan channel](https://cloudnativegeo.slack.com/archives/C0A1JBH9529) in Cloud-Native Geo Slack. Planning happens in [org-level GitHub projects](https://github.com/orgs/portolan-sdi/projects/1).

Files between `ops-sync` markers are synced from [portolan-ops](https://github.com/portolan-sdi/portolan-ops). They are overwritten on every sync run. To change one, edit it in portolan-ops.

One canonical home per fact. If a value like a color, URL, or policy line exists in portolan-ops, link to it rather than copying it.
<!-- ops-sync:end -->

## Skills track pinned upstreams

Every skill states facts about portolan-cli, rashid, the specification, the catalog template, or the registry. `pins.toml` names the version of each that the skills describe. `scripts/check_drift.py` checks every `portolan`, `rashid`, and `gh` command in a bash fence, every `PORTO-*` and `PTL-*` id, every cited `specs/...md` path, and every sample body marked `<!-- drift-sample: issue -->` or `<!-- drift-sample: pr -->` against those versions. Run it before you file a change:

```bash
uv run scripts/check_drift.py
```

Pre-commit runs it with `--offline`. The `Drift` workflow runs it on every pull request and once a week. The weekly run fails when a pin lags its upstream and keeps one tracking issue open.

Each `SKILL.md` has `<!-- drift: depends-on: ... -->` on line 6. That comment lists the upstreams the skill states facts about. There is no `last-verified` date. `git log pins.toml` records when a pin last moved.

A skill restates nothing that `portolan <cmd> --help`, the spec, or rashid output can answer. Cite a spec rule by its id, such as `PORTO-CORE-081`. Do not paraphrase the rule. To show a wrong command on purpose, put `<!-- drift-skip: <reason> -->` on the line before the fence.

To move a pin, edit `pins.toml`. Then run the checker and fix every finding in the same pull request.
