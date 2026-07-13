#!/usr/bin/env bash
# verify-ds-sync.sh — assert every DS-bundle consumer is byte-identical to the
# canonical design system. Exit 0 = all in sync; exit 1 = drift (fail loud);
# exit 3 = environment/usage error. No mutation. See scripts/ds-consumers.txt.
#
# P10: fixed file set, bounded consumer loop, all return values checked.
set -euo pipefail

readonly ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly MANIFEST="${ROOT}/scripts/ds-consumers.txt"
readonly MAX_CONSUMERS=64
# The exact, fixed set of files that constitute the shipped bundle. Each path is
# identical relative to the canonical root and to a consumer's web/ds/ root.
readonly DS_FILES=(
  "_ds_bundle.js"
  "styles.css"
  "tokens/colors.css"
  "tokens/motion.css"
  "tokens/spacing.css"
  "tokens/typography.css"
)

fail=0
notes=0

# hash <file> -> prints sha256 hex, or empty string if the file is absent.
hash() {
  local f="$1"
  if [[ ! -f "$f" ]]; then
    printf ''
    return 0
  fi
  sha256sum "$f" | cut -d' ' -f1
}

# verify_consumer <class> <ds_dir> -> 0 in-sync/skipped, 1 drift/missing.
verify_consumer() {
  local class="$1" ds_dir="$2"
  local abs
  if [[ "$class" == "external" ]]; then
    abs="$ds_dir"
    if [[ ! -d "$abs" ]]; then
      echo "  NOTE  external consumer absent, skipped: ${abs}"
      notes=$((notes + 1))
      return 0
    fi
  else
    abs="${ROOT}/${ds_dir}"
    if [[ ! -d "$abs" ]]; then
      echo "  FAIL  repo consumer missing: ${ds_dir}"
      return 1
    fi
  fi
  local bad=0 i
  for ((i = 0; i < ${#DS_FILES[@]}; i++)); do
    local rel="${DS_FILES[$i]}"
    local want got
    want="$(hash "${ROOT}/${rel}")"
    got="$(hash "${abs}/${rel}")"
    if [[ -z "$want" ]]; then
      echo "  FAIL  canonical file missing: ${rel}"
      bad=1
    elif [[ "$want" != "$got" ]]; then
      echo "  FAIL  drift: ${ds_dir}/${rel}"
      echo "          canonical ${want}"
      echo "          consumer  ${got:-<absent>}"
      bad=1
    fi
  done
  if [[ "$bad" -eq 0 ]]; then
    echo "  OK    ${class} ${ds_dir}"
  fi
  return "$bad"
}

main() {
  if [[ ! -f "$MANIFEST" ]]; then
    echo "verify-ds-sync: manifest not found: ${MANIFEST}" >&2
    exit 3
  fi
  echo "verify-ds-sync: canonical=${ROOT}"
  local count=0 class ds_dir
  while read -r class ds_dir _rest; do
    [[ -z "${class:-}" || "${class:0:1}" == "#" ]] && continue
    count=$((count + 1))
    if [[ "$count" -gt "$MAX_CONSUMERS" ]]; then
      echo "verify-ds-sync: too many consumers (>${MAX_CONSUMERS})" >&2
      exit 3
    fi
    if ! verify_consumer "$class" "$ds_dir"; then
      fail=1
    fi
  done < "$MANIFEST"
  if [[ "$count" -eq 0 ]]; then
    echo "verify-ds-sync: no consumers listed" >&2
    exit 3
  fi
  if [[ "$fail" -ne 0 ]]; then
    echo "verify-ds-sync: DRIFT DETECTED — run scripts/sync-ds.sh and review." >&2
    exit 1
  fi
  echo "verify-ds-sync: all ${count} consumer(s) in sync (${notes} skipped)."
  exit 0
}

main "$@"
