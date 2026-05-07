# Portolan Skills

Claude Code skills for working with [Portolan](https://github.com/portolan-sdi/portolan-spec) cloud-native geospatial data catalogs.

## Skills

### `portolan:portolan-cli`

Guides AI agents through publishing and managing Portolan catalogs with the [portolan-cli](https://github.com/portolan-sdi/portolan-cli). Covers catalog initialization, format conversion (GeoParquet, COG, COPC), versioning, sync to object storage, and partitioning workflows.

### `portolan:reading-portolan`

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

```bash
claude plugin marketplace add portolan-sdi/portolan-skills
claude plugin install portolan
```

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
