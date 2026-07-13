#!/usr/bin/env bash
# verify-all.sh — the documented pre-deploy / CI gate for the Piranesi VUI orb.
# Proves that every derived surface still descends from the ONE canonical source:
#   1. orb-params.json == _ds_bundle.js  (the JSX/bundle stays authoritative)
#   2. every vendored web bundle == canonical (no silent drift)
#   3. the native Android Kotlin tables == what orb-params.json generates
# Exit 0 = all derivations provably intact; non-zero = a break (fail loud).
#
# Run before deploying the hall/kiosk web hosts or building the Android app.
set -euo pipefail

readonly ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
rc=0

step() {
  local label="$1"; shift
  echo "== ${label} =="
  if "$@"; then
    echo "   PASS"
  else
    echo "   FAIL (${label})" >&2
    rc=1
  fi
}

step "orb-params.json == _ds_bundle.js" python3 "${ROOT}/scripts/verify-orb-params.py"
step "vendored web bundles == canonical" bash "${ROOT}/scripts/verify-ds-sync.sh"
step "android kotlin tables == orb-params.json" bash "${ROOT}/scripts/sync-android-orb.sh" --check

if [[ "$rc" -ne 0 ]]; then
  echo "verify-all: DERIVATION BROKEN — see failures above." >&2
  exit 1
fi
echo "verify-all: all derivations intact."
exit 0
