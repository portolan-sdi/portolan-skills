# Portolan Skills

AI agent skills for working with [Portolan](https://github.com/portolan-sdi/portolan-spec) cloud-native geospatial data catalogs.

Skills use the [Agent Skills](https://github.com/anthropics/agent-skills) open standard (`SKILL.md` format), which works across multiple AI coding tools.

## Skills

### `portolan-cli`

Guides AI agents through publishing and managing Portolan catalogs with the [portolan-cli](https://github.com/portolan-sdi/portolan-cli). Covers catalog initialization, format conversion (GeoParquet, COG, COPC), versioning, sync to object storage, and partitioning workflows.

### `reading-portolan`

Guides AI agents through exploring, querying, analyzing, and visualizing data from any Portolan-compliant catalog. Covers:

- Navigating STAC catalog trees (including nested sub-catalogs)
- Querying GeoParquet with DuckDB (local and remote via HTTP range requests)
- Geospatial analysis — spatial joins, area/distance calculations, buffering
- Cross-dataset joins across collections
- Converting to legacy formats (Shapefile, GeoPackage, GeoTIFF) with GDAL/OGR
- Interactive maps with PMTiles + MapLibre GL JS
- Large dataset / 3D visualization with deck.gl
- Point cloud rendering with COPC + Potree

## Install

### Claude Code (CLI & Desktop)

```bash
claude plugin marketplace add portolan-sdi/portolan-skills
claude plugin install portolan
```

Skills become available as `portolan:portolan-cli` and `portolan:reading-portolan`.

### Claude Code (Web / Cowork)

The web app at [claude.ai/code](https://claude.ai/code) does not currently support plugin installation. To use these skills in Cowork, paste the content of a SKILL.md file into your project's `CLAUDE.md` or provide it as context.

### Gemini CLI

Gemini CLI natively supports the same `SKILL.md` format:

```bash
# Install both skills at user scope
gemini skills install https://github.com/portolan-sdi/portolan-skills.git --path skills/portolan-cli --consent
gemini skills install https://github.com/portolan-sdi/portolan-skills.git --path skills/reading-portolan --consent

# Or at workspace scope (shared via version control)
gemini skills install https://github.com/portolan-sdi/portolan-skills.git --path skills/reading-portolan --scope workspace --consent
```

### OpenAI Codex CLI

Codex CLI also supports `SKILL.md` files. Copy the skills into your project's `.agents/skills/` directory:

```bash
# Clone and copy into your project
git clone https://github.com/portolan-sdi/portolan-skills.git /tmp/portolan-skills
mkdir -p .agents/skills
cp -r /tmp/portolan-skills/skills/portolan-cli .agents/skills/
cp -r /tmp/portolan-skills/skills/reading-portolan .agents/skills/
```

### Any AI Agent (Manual)

The skills are just markdown files. For any AI coding tool that supports custom instructions or system prompts:

1. Copy the content of the relevant `SKILL.md` file
2. Add it to your tool's custom instructions, system prompt, or project context file (`CLAUDE.md`, `GEMINI.md`, `AGENTS.md`, `.cursorrules`, etc.)

## Sync

The `portolan-cli` skill is kept in sync with the [SKILL.md](https://github.com/portolan-sdi/portolan-cli/blob/main/SKILL.md) in the portolan-cli repo.

A [GitHub Action](.github/workflows/sync-cli-skill.yml) runs weekly (and can be triggered manually) to check for upstream changes. If the SKILL.md has changed, it opens a PR with the updated content so you can review before merging. The action prepends the skill frontmatter automatically.

To sync manually:

```bash
curl -fsSL https://raw.githubusercontent.com/portolan-sdi/portolan-cli/main/SKILL.md -o /tmp/skill.md
# Copy content after the frontmatter in skills/portolan-cli/SKILL.md
```

## License

Apache-2.0
