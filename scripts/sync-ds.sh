#!/usr/bin/env bash
# sync-ds.sh — copy the canonical design-system bundle into every consumer's
# web/ds/ directory so they derive by construction, not by hand. After copying
# it self-verifies. Exit 0 = synced + verified; 1 = post-sync verify failed;
# 3 = environment/usage error. See scripts/ds-consumers.txt.
#
# P10: fixed file set, bounded consumer loop, all return values checked.
set -euo pipefail

readonly ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly MANIFEST="${ROOT}/scripts/ds-consumers.txt"
readonly MAX_CONSUMERS=64
readonly DS_FILES=(
  "_ds_bundle.js"
  "styles.css"
  "tokens/colors.css"
  "tokens/motion.css"
  "tokens/spacing.css"
  "tokens/typography.css"
)

# sync_consumer <class> <ds_dir> -> 0 synced/skipped, 1 error.
sync_consumer() {
  local class="$1" ds_dir="$2" abs
  if [[ "$class" == "external" ]]; then
    abs="$ds_dir"
    if [[ ! -d "$(dirname "$abs")" ]]; then
      echo "  NOTE  external parent absent, skipped: ${abs}"
      return 0
    fi
  else
    abs="${ROOT}/${ds_dir}"
  fi
  local i
  for ((i = 0; i < ${#DS_FILES[@]}; i++)); do
    local rel="${DS_FILES[$i]}"
    local src="${ROOT}/${rel}" dst="${abs}/${rel}"
    if [[ ! -f "$src" ]]; then
      echo "  FAIL  canonical file missing: ${rel}" >&2
      return 1
    fi
    if ! mkdir -p "$(dirname "$dst")"; then
      echo "  FAIL  cannot create dir for ${dst}" >&2
      return 1
    fi
    if ! cp -f "$src" "$dst"; then
      echo "  FAIL  copy failed: ${dst}" >&2
      return 1
    fi
  done
  echo "  SYNC  ${class} ${ds_dir}"
  return 0
}

main() {
  if [[ ! -f "$MANIFEST" ]]; then
    echo "sync-ds: manifest not found: ${MANIFEST}" >&2
    exit 3
  fi
  echo "sync-ds: canonical=${ROOT}"
  local count=0 class ds_dir rc=0
  while read -r class ds_dir _rest; do
    [[ -z "${class:-}" || "${class:0:1}" == "#" ]] && continue
    count=$((count + 1))
    if [[ "$count" -gt "$MAX_CONSUMERS" ]]; then
      echo "sync-ds: too many consumers (>${MAX_CONSUMERS})" >&2
      exit 3
    fi
    if ! sync_consumer "$class" "$ds_dir"; then
      rc=1
    fi
  done < "$MANIFEST"
  if [[ "$rc" -ne 0 ]]; then
    echo "sync-ds: one or more copies failed." >&2
    exit 3
  fi
  echo "sync-ds: verifying…"
  "${ROOT}/scripts/verify-ds-sync.sh"
}

main "$@"
