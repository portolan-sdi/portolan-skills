# Changelog

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## 0.2.1 - 2026-08-28

The skills now track Portolan specification v0.2.0 and rashid 0.1.8.

### Changed

- Link guidance follows spec v0.2.0. The specification retired
  `PORTO-CORE-034`, which had required every structural link to be relative and
  had forbidden a `self` link. It added `PORTO-CORE-081`, a SHOULD for an
  absolute `self` link on the root catalog of a catalog served from a single
  fixed URL. `git-backed-catalog`, `portolan-migrate`, and `portolan-cli` said
  Portolan forbids a `self` link. They no longer do.
- `git-backed-catalog` gains a "Links and the Publish Step" section. It keeps
  structural links relative in the tracked tree and has the publish step write
  the absolute `self` link from `public_base`. It also names the trap: a
  validator cannot resolve an absolute structural link without a root `self`
  link, and reports nothing for it.
- `git-backed-catalog` asks for `rashid>=0.1.8,<0.2.0` rather than
  `rashid==0.1.6`. Releases 0.1.5 through 0.1.7 report an error for a `self`
  link and for an absolute structural `href`, both of which spec v0.2.0 allows.
- `git-backed-catalog` and `portolan-migrate` described a conformance gate that
  prints `SKIP: rashid is not installed` and exits 0. The catalog template fails
  instead, both when rashid is absent and when its version falls outside the
  required range.
- The `portolan-migrate` reference tools stamp
  `https://schemas.portolan-sdi.org/portolan/v0.2.0/schema.json`.
  `apply_metadata.py` carried v0.1.1 and `build_collection.py` carried v0.1.0,
  which is the root-versus-child mismatch the skill itself warns about.
- `portolan-migrate` reference `conformance.md` cited `PTL-LNK-005`, which
  rashid removed in 0.1.8.
- `portolan-cli` states the relative-link behavior as CLI behavior rather than
  as a specification rule. The file also gains a freshness marker.

## 0.2.0 - 2026-08-20

This release adds eight skills. The plugin now covers the whole catalog
lifecycle. It builds a catalog, repairs an old one, publishes it, registers it,
and reports problems with it.

### Upgrade From 0.1.0

Version 0.1.0 shipped in May 2026. The version string never changed after that.
`claude plugin update` compares version strings. It therefore reports "already
at the latest version" to every user on 0.1.0. Those users still run the
two-skill May release. Run these commands once to get this release:

```bash
claude plugin marketplace update portolan-skills
claude plugin uninstall portolan@portolan-skills
claude plugin install portolan@portolan-skills
```

This release bumps the version string, so `claude plugin update` finds the next
release.

### Added

- `portolan-bootstrap`. Build a complete catalog from a data source. The skill
  researches the data and the publisher. It converts the data to cloud-native
  formats, writes the documentation and the styles, then publishes the result.
- `portolan-migrate`. Bring an existing catalog into compliance without a
  rebuild. The skill audits the catalog, then repairs the metadata, the styles,
  and the data. It ships six reference tools and a conformance guide.
- `portolan-thumbnails`. Render thumbnails from the `styles/default.json` file
  that the collection publishes. The skill uses chiitiler and MapLibre GL
  Native. It frames every bbox to the 3:2 shape of the browser card. Each image
  passes a blank probe and a visual review. The skill needs Node.js 18 or later.
- `portolan-consume`. Query and explore a catalog through its GeoParquet and COG
  assets.
- `git-backed-catalog`. Keep the catalog metadata in a git repository. CI
  validates every change. Use the skill to publish a catalog you can roll back,
  or to correct the metadata in a catalog that another person owns.
- `register-catalog`. Register a catalog in the Portolan registry through a pull
  request.
- `report-catalog-issue`. Report a problem with a registered catalog as a
  catalog feedback issue.
- `sourcecoop`. Upload data to Source Cooperative with the metadata and the
  README files that the platform needs.

### Changed

- `portolan-cli`. The skill documents `check --no-data`, `check --live`, and
  `check --fix --dry-run`. It documents `add --datetime`, `add --workers`,
  `add --pmtiles`, and `add --stac-geoparquet`. It explains the three
  `--merge-strategy` values.
- `portolan-cli`. The `extract` section names the three subcommands `arcgis`,
  `wfs`, and `carto`. Each one takes a positional output directory. There is no
  `--output` flag.
- `portolan-cli`. The `metadata` and `readme` commands walk the whole catalog by
  default. The `--no-recursive` flag limits them to one path.
- `reading-portolan`. The skill finds the style JSON that a collection
  publishes. An agent reads that style before it writes map code. The skill
  covers relative PMTiles URLs and a style switcher.

### Repository

- `AGENTS.md` carries the org agent norms. `CLAUDE.md` imports them.
- `repo-checks.yml` runs the org repo checks on every pull request.
- A pre-commit hook runs `scripts/generate-readme.py`. The hook writes the
  skills section of `README.md`.
- The repo adds the Apache-2.0 `LICENSE` file.
- The repo drops `sync-cli-skill.yml`. The `portolan-cli` skill lives here now.

## 0.1.0 - 2026-05-07

The first release. It contains two skills, `portolan-cli` and
`reading-portolan`.
