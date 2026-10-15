#!/usr/bin/env bash
# Freeze one case inside the container.
# Usage: freeze-case ID URL REPO_URL|- LOCAL_PATH|-
# /skill is the catalog-grader skill (read-only). /out is the case directory.
set -euo pipefail
id=$1 url=$2 repo_url=$3 local_path=$4

work=$(mktemp -d)
args=()
if [ "$repo_url" != "-" ]; then
  git clone --quiet --filter=blob:none "$repo_url" "$work/repo"
  args+=(--repo "$work/repo")
  git -C "$work/repo" rev-parse HEAD > /out/repo-sha.txt
fi

target=$url
if [ "$local_path" != "-" ]; then
  target="$work/repo/$(dirname "$local_path")"
fi

uv run --quiet /skill/scripts/collect_facts.py "$target" \
  --out /out --rashid-timeout "${RASHID_TIMEOUT:-3600}" "${args[@]}" \
  > /out/collect.log 2>&1 || echo "collect_facts exit $?" >> /out/collect.log

# Discard side effects from documentation code.
rm -rf /out/work
date -u +%FT%TZ > /out/frozen-at.txt
