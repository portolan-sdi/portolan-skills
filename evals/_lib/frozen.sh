#!/usr/bin/env bash
# Pack or fetch the frozen inputs of one skill eval.
#
# The frozen inputs (facts, saved docs, thumbnails) are too large for git. Each
# version is a tarball attached to a GitHub release of this repository. The
# eval directory commits frozen.lock, which names the release and the
# tarball's sha256, so every run grades the same bytes.
#
#   evals/_lib/frozen.sh fetch evals/catalog-grader
#   evals/_lib/frozen.sh pack  evals/catalog-grader 2
#
# pack writes dist/<skill>-frozen-v<N>.tar.gz and frozen.lock. A maintainer
# then creates the release that frozen.lock names and uploads the tarball.
set -euo pipefail

REPO_URL=https://github.com/portolan-sdi/portolan-skills
cmd=${1:?usage: frozen.sh fetch|pack EVAL_DIR [VERSION]}
eval_dir=$(cd "${2:?usage: frozen.sh fetch|pack EVAL_DIR [VERSION]}" && pwd)
skill=$(basename "$eval_dir")
lock="$eval_dir/frozen.lock"

case "$cmd" in
pack)
  version=${3:?pack needs a version number}
  tag="evals-$skill-frozen-v$version"
  asset="$skill-frozen-v$version.tar.gz"
  mkdir -p "$eval_dir/dist"
  # The frozen inputs are copies of other publishers' documents and images.
  # NOTICE.md names the source, license, and licensor of each case.
  python3 - "$eval_dir" > "$eval_dir/cases/NOTICE.md" <<'NOTICE'
import collections, json, pathlib, sys
eval_dir = pathlib.Path(sys.argv[1])
print("# Frozen inputs: sources and licenses\n")
print("Each directory under `cases/` holds copies of one published catalog's metadata, documents, and images,")
print("saved for the eval. The copies keep the license of their source. The Apache-2.0 license of")
print("portolan-skills does not apply to them. Use each case under the terms its publisher states below.\n")
print("| Case | Catalog | License | License page | Licensor |")
print("|---|---|---|---|---|")
for facts in sorted(eval_dir.glob("cases/*/frozen/facts.json")):
    f = json.loads(facts.read_text())
    root = next((n for n in f.get("nodes", []) if n.get("path") == ""), {})
    licenses = collections.Counter(n.get("license") for n in f.get("nodes", []) if n.get("license"))
    names = sorted({p.get("name") for n in f.get("nodes", []) for p in n.get("providers") or []
                    if set(p.get("roles") or []) & {"licensor", "producer"} and p.get("name")})
    page = (f.get("root_links") or {}).get("license") or "-"
    print(f"| {facts.parent.parent.name} | [{root.get('title') or f.get('catalog')}]({f.get('catalog')}) | "
          f"{', '.join(k for k, _ in licenses.most_common()) or 'not stated'} | {page} | {', '.join(names[:4]) or 'not stated'} |")
NOTICE
  # Sorted, owner-free, fixed-mtime entries make the tarball reproducible.
  (cd "$eval_dir" && { echo cases/NOTICE.md; find cases -path '*/frozen/*' -type f -not -path '*/work/*' | LC_ALL=C sort; }) \
    > "$eval_dir/dist/files.txt"
  tar -C "$eval_dir" --owner=0 --group=0 --numeric-owner --mtime='2026-01-01 00:00Z' \
    -cf - -T "$eval_dir/dist/files.txt" | gzip -n > "$eval_dir/dist/$asset"
  sha=$(sha256sum "$eval_dir/dist/$asset" | cut -d' ' -f1)
  python3 - "$eval_dir" "$tag" "$asset" "$sha" "$REPO_URL" > "$lock" <<'PY'
import json, pathlib, sys
eval_dir, tag, asset, sha, repo = sys.argv[1:]
cases = {}
for d in sorted(pathlib.Path(eval_dir, "cases").glob("*/frozen")):
    read = lambda n: (d / n).read_text().strip() if (d / n).exists() else None
    cases[d.parent.name] = {"frozen_at": read("frozen-at.txt"), "collect_facts_sha": read("collect_facts.sha"),
                            "repo_sha": read("repo-sha.txt")}
print(json.dumps({"tag": tag, "asset": asset, "url": f"{repo}/releases/download/{tag}/{asset}",
                  "sha256": sha, "cases": cases}, indent=2))
PY
  rm "$eval_dir/dist/files.txt"
  echo "wrote $eval_dir/dist/$asset ($(du -h "$eval_dir/dist/$asset" | cut -f1)) and $lock"
  echo "Read $eval_dir/cases/NOTICE.md, commit frozen.lock, and push. Then publish with:"
  echo "  gh release create $tag $eval_dir/dist/$asset --prerelease \\"
  echo "    --target \"\$(git rev-parse HEAD)\" --title \"$skill eval: frozen inputs v$version\" \\"
  echo "    --notes-file $eval_dir/cases/NOTICE.md"
  echo "See evals/README.md, section Publish frozen inputs."
  ;;
fetch)
  [ -f "$lock" ] || { echo "no $lock; freeze the cases first" >&2; exit 1; }
  read -r url sha asset < <(python3 -c 'import json,sys;l=json.load(open(sys.argv[1]));print(l["url"],l["sha256"],l["asset"])' "$lock")
  tmp=$(mktemp -d)
  trap 'rm -rf "$tmp"' EXIT
  curl -fsSL "$url" -o "$tmp/$asset"
  echo "$sha  $tmp/$asset" | sha256sum -c --quiet - || { echo "checksum mismatch for $asset" >&2; exit 1; }
  tar -C "$eval_dir" -xzf "$tmp/$asset"
  echo "fetched $asset into $eval_dir/cases"
  ;;
*)
  echo "usage: frozen.sh fetch|pack EVAL_DIR [VERSION]" >&2; exit 2 ;;
esac
