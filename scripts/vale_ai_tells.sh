#!/usr/bin/env bash
# Run the repo-local ai-tells gate. .github/workflows/ai-tells.yml runs the
# same command.
#
# `vale sync` writes .vale/styles, which .gitignore keeps out of the tree, so
# a fresh clone has no style to check against. Report that and pass, the way
# check_drift.py --offline skips the checks that need the network. CI always
# syncs first, so the gate still blocks there.
set -euo pipefail

if ! command -v vale >/dev/null 2>&1; then
  echo "vale is not installed. Skipping the ai-tells gate."
  echo "Install it from https://vale.sh, then run: vale sync"
  exit 0
fi

if [ ! -d .vale/styles/ai-tells ]; then
  echo "The ai-tells style is absent. Skipping the ai-tells gate."
  echo "Run: vale sync"
  exit 0
fi

exec vale --output=line skills README.md AGENTS.md
