# Portolan Skills

AI agent skills for working with [Portolan](https://github.com/portolan-sdi/portolan-spec) cloud-native geospatial data catalogs.

Skills use the [Agent Skills](https://github.com/anthropics/agent-skills) open standard (`SKILL.md` format), which works across multiple AI coding tools.

<!-- BEGIN GENERATED: skills -->
## Skills

### `chiitiler-thumbnails`

Generate high-quality thumbnails from Portolan collections using chiitiler (MapLibre GL Native). Renders the collection's actual styles/default.json server-side with optional basemap. Requires Node.js 18+.

### `portolan-bootstrap`

End-to-end catalog creation from a data source - extract, enrich metadata, generate assets, push to remote

### `portolan-cli`

Use when publishing, managing, or converting cloud-native geospatial data catalogs with the Portolan CLI. Covers init, add, check, push, pull, sync, partitioning, and format conversion workflows.

### `portolan-consume`

Guide users through querying and exploring Portolan/STAC catalogs with optimized GeoParquet and COGs

### `reading-portolan`

Use when exploring, querying, analyzing, or visualizing data from a Portolan catalog (STAC-based cloud-native geospatial data). Covers navigating STAC metadata, querying GeoParquet with DuckDB, cross-dataset joins, geospatial analysis, and creating interactive maps with PMTiles/MapLibre/deck.gl/Potree.

### `register-catalog`

Register a Portolan catalog in the Portolan registry by opening a pull request that adds a catalog entry file.

### `sourcecoop`

Upload geospatial data to Source Cooperative with proper metadata and READMEs using Portolan CLI.

<!-- END GENERATED: skills -->

## Install

### Claude Code (CLI & Desktop)

```bash
claude plugin marketplace add portolan-sdi/portolan-skills
claude plugin install portolan
```

Skills become available as `portolan:portolan-cli`, `portolan:reading-portolan`, `portolan:portolan-bootstrap`, `portolan:portolan-consume`, `portolan:sourcecoop`, and `portolan:register-catalog`.

### Claude Code (Web / Cowork)

The web app at [claude.ai/code](https://claude.ai/code) does not currently support plugin installation. To use these skills in Cowork, paste the content of a SKILL.md file into your project's `CLAUDE.md` or provide it as context.

### Gemini CLI

Gemini CLI natively supports the same `SKILL.md` format:

```bash
# Install skills at user scope
gemini skills install https://github.com/portolan-sdi/portolan-skills.git \
  --path skills/portolan-cli --consent
gemini skills install https://github.com/portolan-sdi/portolan-skills.git \
  --path skills/reading-portolan --consent
gemini skills install https://github.com/portolan-sdi/portolan-skills.git \
  --path skills/portolan-bootstrap --consent
gemini skills install https://github.com/portolan-sdi/portolan-skills.git \
  --path skills/portolan-consume --consent
gemini skills install https://github.com/portolan-sdi/portolan-skills.git \
  --path skills/sourcecoop --consent
gemini skills install https://github.com/portolan-sdi/portolan-skills.git \
  --path skills/register-catalog --consent

# Or at workspace scope (shared via version control)
gemini skills install https://github.com/portolan-sdi/portolan-skills.git \
  --path skills/reading-portolan --scope workspace --consent
```

### OpenAI Codex CLI

Codex CLI also supports `SKILL.md` files. Copy the skills into your project's `.agents/skills/` directory:

```bash
# Clone and copy into your project
git clone https://github.com/portolan-sdi/portolan-skills.git /tmp/portolan-skills
mkdir -p .agents/skills
cp -r /tmp/portolan-skills/skills/* .agents/skills/
```

### Any AI Agent (Manual)

The skills are just markdown files. For any AI coding tool that supports custom instructions or system prompts:

1. Copy the content of the relevant `SKILL.md` file
2. Add it to your tool's custom instructions, system prompt, or project context file (`CLAUDE.md`, `GEMINI.md`, `AGENTS.md`, `.cursorrules`, etc.)

## License

Apache-2.0
