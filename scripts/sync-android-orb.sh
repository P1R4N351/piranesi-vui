#!/usr/bin/env bash
# sync-android-orb.sh — regenerate the native Android orb's data tables
# (PiranesiOrbParams.kt) in the astroclaw-vui-orb repo from the canonical
# orb-params.json, so the Kotlin orb derives by construction. The astroclaw repo
# is a separate checkout with no shared build, so this is the cross-repo analog
# of sync-ds.sh. Exit 0 = written/verified; 1 = drift under --check; 3 = env error.
#
# Usage:
#   sync-android-orb.sh            # regenerate the Kotlin file
#   sync-android-orb.sh --check    # fail loud if the checked-in Kotlin has drifted
#
# The astroclaw repo path is host-dependent; override with ASTROCLAW_ORB_REPO.
# Absence is a NOTE, not a failure.
set -euo pipefail

readonly ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly REPO="${ASTROCLAW_ORB_REPO:-/home/s/astroclaw-vui-orb}"
readonly REL="apps/android/app/src/main/java/ai/astroclaw/app/ui/PiranesiOrbParams.kt"
readonly TARGET="${REPO}/${REL}"

main() {
  local mode="${1:-write}"
  if [[ ! -d "$REPO" ]]; then
    echo "sync-android-orb: NOTE astroclaw repo absent (${REPO}), skipped."
    exit 0
  fi
  if [[ ! -f "${ROOT}/orb-params.json" ]]; then
    echo "sync-android-orb: orb-params.json missing" >&2
    exit 3
  fi
  if [[ "$mode" == "--check" ]]; then
    python3 "${ROOT}/scripts/gen-kotlin-orb.py" --check "$TARGET"
    exit "$?"
  fi
  if [[ ! -d "$(dirname "$TARGET")" ]]; then
    echo "sync-android-orb: target dir absent: $(dirname "$TARGET")" >&2
    exit 3
  fi
  python3 "${ROOT}/scripts/gen-kotlin-orb.py" --out "$TARGET"
}

main "$@"
