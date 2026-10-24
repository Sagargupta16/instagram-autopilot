#!/usr/bin/env bash
# Bring uv.lock and requirements.txt back into agreement after a Renovate update.
#
# Renovate edits requirements.txt as a plain pip file: it bumps packages that only uv.lock holds
# (certifi in PR #37) without relocking them, and it pins a direct dependency's fix version while
# uv.lock resolves a newer one (filelock in PR #42). Every package whose pin differs from the uv
# export is relocked to the newest version pyproject.toml allows, then requirements.txt is
# exported again with the command in its header. Leaves both files unchanged when they agree.
set -euo pipefail
export LC_ALL=C

pins() {
  local file=$1
  tr -d '\r' <"$file" | grep -E '^[A-Za-z0-9._-]+==' | sort
}

current=$(mktemp)
trap 'rm -f "$current"' EXIT
uv export --frozen --no-dev --no-hashes --output-file "$current" >/dev/null
mapfile -t stale < <(comm -23 <(pins requirements.txt) <(pins "$current") | cut -d= -f1)

if ((${#stale[@]})); then
  echo "Relocking: ${stale[*]}"
  upgrades=()
  for name in "${stale[@]}"; do upgrades+=(--upgrade-package "$name"); done
  uv lock --no-build "${upgrades[@]}"
fi
uv export --frozen --no-dev --no-hashes --output-file requirements.txt --no-cache >/dev/null
