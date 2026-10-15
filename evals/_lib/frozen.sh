#!/usr/bin/env bash
# Pack or fetch frozen eval inputs; see evals/README.md for publishing.
#   evals/_lib/frozen.sh fetch evals/catalog-grader
#   evals/_lib/frozen.sh pack  evals/catalog-grader 2
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
  python3 - "$eval_dir" > "$eval_dir/cases/NOTICE.md" <<'NOTICE'
import collections, json, pathlib, sys
eval_dir = pathlib.Path(sys.argv[1])
print("# Frozen inputs: sources and licenses\n")
print("Frozen metadata, documents, and images retain their publishers' licenses, listed below.")
print("The portolan-skills Apache-2.0 license does not apply to these copies.\n")
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
