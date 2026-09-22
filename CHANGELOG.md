# Changelog

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## 0.4.0 - 2026-09-07

### Added

- `customize-portolan-browser` adapts a portolan-browser checkout into a
  publisher-branded interface for one existing Portolan catalog. The skill
  inspects the catalog, the browser, and the publisher site, presents a design
  proposal, and stops for approval. It then implements the proposal through the
  browser's own configuration, locale, widget, and theme layers before it writes
  a site-local component. It keeps the catalog immutable, and it sorts every
  finding into the custom browser, the catalog, or upstream portolan-browser.
- `pins.toml` pins portolan-browser, and `scripts/check_drift.py` tracks it.

## 0.3.0 - 2026-09-07

This release rewrites every skill against specification v0.2.0, portolan-cli
0.8.0, and rashid 0.1.8. It adds a checker that keeps them there.

### Added

- `pins.toml` names the upstream versions the skills describe: portolan-cli,
  rashid, the specification tag, the catalog template, and the registry.
- `scripts/check_drift.py` checks every `portolan`, `rashid`, and `gh` command
  in the skills against the pinned tools, every `PORTO-*` id against the spec
  manifest, every `PTL-*` id against the rashid registry, every cited spec
  path against the spec tree, and every sample issue or PR body against the
  writing check. It runs in pre-commit, on every pull request, and weekly.
  The weekly run also fails when a pin lags its upstream.
- `tests/` covers the checker without network access.

### Changed

- Every skill carries a `drift: depends-on` header instead of a hand-typed
  `last-verified` date.
- `portolan-cli` drops its command reference. Agents run `portolan <cmd>
  --help`. The skill keeps the layout the CLI writes, the command to reach for,
  and the facts that trip agents (#44).
- `sourcecoop` drops its generated command reference and its styles section.
  Every `init` carries `--license`. Mirrors carry `via` and `updated` (#42).
- `reading-portolan` absorbs `portolan-consume`. It reads `AGENTS.md`, finds
  assets by role, reads the `rel: pmtiles` link, and copies `partition:glob`
  as written (#39, #40).
- `portolan-bootstrap` names `providers`, `via`, and `updated` for mirrors,
  drops `llms.txt`, and adds the multi-scene raster layout (#43, #26).
- `git-backed-catalog` points at the template's `upload_data.py` and
  `CI_LIGHT`, tells the reader to declare the v0.2.0 schema URI and raise the
  gate's rashid floor, and states the item rule (#46, #26).
- `portolan-migrate` puts the spec above rashid and drops three warnings that
  rashid 0.1.7 and portolan-cli 0.8.0 made false. `apply_metadata.py` keeps
  the root `self` link and stops re-stamping `updated` (#45).
- `portolan-thumbnails` finds the style by role and the PMTiles by link,
  refreshes `file:checksum` after a render, and states the Node 22.5
  requirement with portable commands (#41, #32).
- `register-catalog` and `report-catalog-issue` write bodies in Simplified
  Technical English that pass the org checks. The fork command runs (#47,
  #48).

### Removed

- `portolan-consume`. Its content lives in `reading-portolan`.

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
  structural links relative in the tracked tree. It tells the agent to add a
  publish-step rewrite for the absolute `self` link. The current template does
  not supply that rewrite. The section also names the trap: a validator cannot
  resolve an absolute structural link without a root `self` link, and reports
  nothing for it.
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
  as a specification rule. It records that v1.0.0a0 `init` writes a relative
  root `self` link. The file also gains a release-specific freshness marker.

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
