# Portolan skills

[Overview](#overview) · [Quickstart](#quickstart) · [Installation](#installation) · [Skills](#skills) · [Evaluations](#evaluations)

## Overview

This repository gives your coding agent workflows for building, publishing, reviewing, and using [Portolan](https://www.portolan-sdi.org/) geospatial data catalogs. Give your agent a source URL or a folder of files to turn into a documented catalog.

The skills cover data conversion, metadata research, Git-backed catalogs, map thumbnails, Source Cooperative uploads, catalog reviews, and data analysis. Each directory in [`skills/`](skills/) contains a `SKILL.md` file. Some also include scripts and reference material. They follow the [Agent Skills format](https://agentskills.io/), with installation options for Claude Code, Codex, Gemini CLI, and other agents.

[`evals/`](evals/README.md) contains the catalog-grader evaluation suite. [`pins.toml`](pins.toml) records the upstream versions the skills describe, and [`scripts/check_drift.py`](scripts/check_drift.py) checks their commands and specification references against those versions. Catalog requirements come from the [Portolan specification](https://github.com/portolan-sdi/portolan-spec).

## Quickstart

This example uses [Claude Code](https://code.claude.com/docs/en/setup) and [uv](https://docs.astral.sh/uv/getting-started/installation/). Install both before you begin. For other agents, follow [Installation](#installation), then adapt the skill invocation in the prompt.

1. Install the Portolan plugin and `portolan-cli` from your terminal:

   ```bash
   claude plugin marketplace add portolan-sdi/portolan-skills
   claude plugin install portolan@portolan-skills
   uv tool install portolan-cli
   portolan --version
   ```

2. Open a working directory and start a new session:

   ```bash
   mkdir my-catalog-work
   cd my-catalog-work
   claude
   ```

3. Run the bootstrap skill in the agent session. Replace the source placeholder with a data URL or local path:

   ```text
   /portolan:portolan-bootstrap

   Build a Portolan catalog from <data portal, service URL, or local folder>.
   Use git-backed-catalog to create a GitHub repository for the metadata,
   with validation in CI and data files in object storage.
   Use the bootstrap guidance to research the source, convert the data,
   and write metadata, documentation, and map styles.
   Use portolan-thumbnails to generate and visually check the thumbnails.
   I plan to host the catalog and data on Source Cooperative; use
   sourcecoop for its account and authentication setup.
   Ask me for the repository names, license, and maintainer contact.
   Show me the plan and upload preview before publishing.
   ```

   If you use another storage provider, replace the Source Cooperative request with your destination. Source Cooperative hosting requires an account with write access to the destination repository.

4. Review the agent's source research, proposed collections, license, and storage plan. The Git-backed workflow starts from the [catalog template](https://github.com/portolan-sdi/portolan-catalog-template) and keeps metadata under version control. Bootstrap directs this work to `git-backed-catalog`, which owns repository setup, validation, and publishing. Use the template's publishing tools throughout that workflow.

5. After publication, open the catalog in the [Portolan browser](https://browser.portolan-sdi.org/) and check its maps, thumbnails, and download links. Ask your agent to use `catalog-grader` for a quality review, then `register-catalog` if you want to submit it to the registry.

See the [CLI documentation](https://cli.portolan-sdi.org/) for conversion and publishing commands. The [thumbnail skill requirements](skills/portolan-thumbnails/SKILL.md#requirements) include Node.js 24.12 or later, npm, and an agent that can view images. The [Source Cooperative skill](skills/sourcecoop/SKILL.md#prerequisites) covers its CLI, access, and authentication setup.

## Installation

Choose the instructions for your agent. Copy whole skill directories so the agent can use their scripts and reference files.

### Claude CLI

For Claude Code, use the plugin commands in the [quickstart](#quickstart), then start a new session. Skills use the `portolan:` prefix: `/portolan:portolan-bootstrap` builds a catalog, and `/portolan:reading-portolan` helps you use one.

See [Claude Code plugin installation](https://code.claude.com/docs/en/discover-plugins) for installation scopes and updates.

### Claude web and desktop apps

1. Open **Customize**, then **Plugins**.
2. Select **Add**, **Add marketplace**, then **Add from a repository**.
3. Enter `portolan-sdi/portolan-skills` and install the **Portolan** plugin.

See [Use plugins in Claude](https://support.claude.com/en/articles/13837440-use-plugins-in-claude) for account and workspace requirements. For workflows that run local tools or process files, use Cowork or Claude Code with access to your working directory.

### Codex

From the root of the project where you want to use the skills, run:

```bash
skills_checkout=$(mktemp -d)
git clone https://github.com/portolan-sdi/portolan-skills.git "$skills_checkout"
mkdir -p .agents/skills
cp -R "$skills_checkout"/skills/. .agents/skills/
```

Codex discovers skills in `.agents/skills/`. Invoke one by name, for example `$portolan-bootstrap`, or describe your task so Codex can select it. For installation across your projects, use `~/.agents/skills/` as the destination. See the [official skill documentation](https://learn.chatgpt.com/docs/build-skills) for discovery and invocation details.

### Gemini CLI

Install a skill at user scope:

```bash
gemini skills install https://github.com/portolan-sdi/portolan-skills.git \
  --path skills/portolan-bootstrap --consent
```

Repeat the command with a directory from the [skills list](#skills) for each skill you need. For the quickstart, also install `git-backed-catalog`, `portolan-cli`, `portolan-thumbnails`, and `sourcecoop`. Add `--scope workspace` to install for the current project. See [Gemini CLI skills](https://geminicli.com/docs/cli/skills/) for discovery and management.

### Other agents

If your agent supports Agent Skills, install the skill directories in its documented location. Otherwise, add the relevant `SKILL.md` content to its custom instructions and make the supporting scripts and references available in the workspace.

<!-- BEGIN GENERATED: skills -->
## Skills

| Skill | What it does |
|---|---|
| [`catalog-grader`](skills/catalog-grader/SKILL.md) | Grade a published Portolan catalog from A+ to F and explain each finding with evidence. |
| [`customize-portolan-browser`](skills/customize-portolan-browser/SKILL.md) | Adapt a portolan-browser checkout into a publisher-branded interface for one existing Portolan catalog. |
| [`enrich-metadata`](skills/enrich-metadata/SKILL.md) | Fill a collection's metadata.yaml from the open data portal record that lists the same data, when the data came from a source with no metadata of its own, such as a Carto table, a file download, an HDX file, or a Socrata dataset. |
| [`git-backed-catalog`](skills/git-backed-catalog/SKILL.md) | Create, maintain, or contribute to a Portolan catalog whose metadata is stored in a git repository, with CI that validates each change. |
| [`portolan-bootstrap`](skills/portolan-bootstrap/SKILL.md) | Build a complete, well-documented Portolan catalog from a data source. |
| [`portolan-cli`](skills/portolan-cli/SKILL.md) | Use when publishing, managing, or converting cloud-native geospatial data catalogs with the Portolan CLI. |
| [`portolan-migrate`](skills/portolan-migrate/SKILL.md) | Bring an existing non-compliant catalog or published dataset into Portolan compliance without rebuilding it. |
| [`portolan-thumbnails`](skills/portolan-thumbnails/SKILL.md) | Generate framed, checked thumbnails from Portolan collections using chiitiler (MapLibre GL Native). |
| [`reading-portolan`](skills/reading-portolan/SKILL.md) | Use when exploring, querying, analyzing, or visualizing data from a Portolan catalog (STAC-based cloud-native geospatial data). |
| [`register-catalog`](skills/register-catalog/SKILL.md) | Register a Portolan catalog in the Portolan registry by opening a pull request that adds a catalog entry file. |
| [`report-catalog-issue`](skills/report-catalog-issue/SKILL.md) | Report a problem with a catalog registered in the Portolan registry by opening a catalog feedback issue against it. |
| [`sourcecoop`](skills/sourcecoop/SKILL.md) | Upload geospatial data to Source Cooperative with proper metadata and READMEs using Portolan CLI. |
<!-- END GENERATED: skills -->

## Evaluations

The [catalog-grader eval](evals/catalog-grader/README.md) tests the skill against saved catalog facts and maintainer-approved expected results. Scorer tests run without model calls:

```bash
node --test evals/*/*.test.mjs
```

For a full evaluation, you need Node.js 20 or later, uv, and authenticated Claude Code 2.1.300 or later. Each case starts a paid Claude Code session. Follow the [eval authentication instructions](evals/catalog-grader/README.md#run) before running these commands from this repository's root:

1. Download the frozen inputs and run the unchanged skill as a baseline:

   ```bash
   evals/_lib/frozen.sh fetch evals/catalog-grader
   node evals/catalog-grader/run-eval.mjs \
     --flow .claude/hillclimb/catalog-grader \
     --variant baseline --model claude-opus-5-5 \
     --reps 2 --concurrency 3
   ```

   If the runner requests harness approval, review the files it lists, then repeat the command with `--approve-harness` for one run.

2. Edit the skill, then repeat the runner command with `--variant v1`. Keep the model, case selection, and repetition count the same for comparison.

3. Build the report and print both summaries:

   ```bash
   node evals/_lib/build-report-lite.mjs .claude/hillclimb/catalog-grader/
   python3 evals/catalog-grader/summary.py \
     .claude/hillclimb/catalog-grader/baseline \
     .claude/hillclimb/catalog-grader/v1
   ```

   Open `.claude/hillclimb/catalog-grader/report.html` to compare the results. Include both summaries in your pull request's **Verification** section.

You can also run the [Eval catalog-grader workflow](https://github.com/portolan-sdi/portolan-skills/actions/workflows/eval-catalog-grader.yml), which uploads the results as an artifact. See the [evaluation guide](evals/README.md) for frozen input releases and changes to expected results.

Before submitting a change, check the skills against the pinned upstreams:

```bash
uv run scripts/check_drift.py
```

## License

[Apache-2.0](LICENSE)
