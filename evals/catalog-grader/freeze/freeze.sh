#!/usr/bin/env bash
# Freeze facts for every case in cases.json, FREEZE_JOBS (6) at a time, each in a fresh
# container. Usage: evals/catalog-grader/freeze/freeze.sh [ID ...]
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
eval_dir=$(dirname "$here")
# Snapshot the skill so an edit during a long freeze cannot mix two versions.
skill=$(mktemp -d)
trap 'rm -rf "$skill"' EXIT
cp -r "$eval_dir/../../skills/catalog-grader/." "$skill/"
script_sha=$(sha256sum "$skill/scripts/collect_facts.py" | cut -c1-12)

mkdir -p "${UV_CACHE_HOST:=${XDG_CACHE_HOME:-$HOME/.cache}/catalog-grader-freeze}"
docker build --quiet -t catalog-grader-freeze "$here" > /dev/null

python3 - "$eval_dir/cases.json" "$@" <<'PY' > "$here/.jobs"
import json, sys
cases = json.load(open(sys.argv[1]))
want = set(sys.argv[2:])
for c in cases:
    if want and c["id"] not in want:
        continue
    print(c["id"], c["url"], c.get("repo") or "-", c.get("local") or "-")
PY

run_one() {
  id=$1
  out="$eval_dir/cases/$id/frozen"
  rm -rf "$out"
  mkdir -p "$out"
  docker run --rm --user "$(id -u):$(id -g)" \
    --memory 6g --cpus 2 \
    -v "$skill:/skill:ro" -v "$out:/out" \
    -v "$UV_CACHE_HOST:/cache" -e UV_CACHE_DIR=/cache \
    -e RASHID_TIMEOUT="${RASHID_TIMEOUT:-3600}" \
    catalog-grader-freeze "$@"
  echo "$script_sha" > "$out/collect_facts.sha"
  echo "$id: $(python3 -c "import json;f=json.load(open('$out/facts.json'));print('nodes',len(f.get('nodes',[])),'rashid', f.get('rashid',{}).get('error_count', f.get('rashid',{}).get('error','?')))" 2>/dev/null || echo 'NO facts.json')"
}
export -f run_one
export eval_dir skill script_sha UV_CACHE_HOST

xargs -r -P "${FREEZE_JOBS:-6}" -L 1 bash -c 'run_one "$@"' _ < "$here/.jobs"
rm -f "$here/.jobs"
