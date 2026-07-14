#!/bin/bash
# Regular design-sync PULL — fire a headless claude agent to pull the Claude
# Design project into the canonical piranesi-vui repo per design-sync-pull.md.
# Durable: invoked from the system crontab. Idempotent + locked + logged.
# The PULL itself needs the DesignSync tool (claude.ai design login), so it runs
# inside a headless `claude -p` agent, not raw shell.
set -uo pipefail
REPO=/home/s/piranesi-vui
LOG=/home/s/Piranesi/logs/design-sync-pull.log
CLAUDE=/home/s/.nvm/versions/node/v24.15.0/bin/claude
LOCK=/tmp/design-sync-pull.lock
mkdir -p "$(dirname "$LOG")"

exec 9>>"$LOCK"
flock -n 9 || { echo "$(date -Is) already running — skip" >>"$LOG"; exit 0; }

[ -x "$CLAUDE" ] || CLAUDE=$(command -v claude) || { echo "$(date -Is) no claude CLI" >>"$LOG"; exit 1; }
cd "$REPO" || { echo "$(date -Is) repo missing" >>"$LOG"; exit 1; }

echo "$(date -Is) === design-sync-pull start ===" >>"$LOG"
timeout 1500 "$CLAUDE" -p "Read scripts/design-sync-pull.md in this repo and follow it EXACTLY. It pulls the Claude Design project 8af39666-f588-49a2-a32d-e8e57314f5e5 (via the DesignSync tool) DOWN into this canonical repo: reconcile only DS-source files (NEVER the repo-only adapters/, scripts/, orb-params.json, .design-sync/), regenerate derived artifacts (scripts/verify-all.sh MUST pass), commit+push to gitea+github with CPCS attribution, deploy the web bundles to the kiosk + branch-0 hall, and ntfy a one-line summary. Be strictly idempotent — a clean no-op when nothing changed. If the design project is unreachable OR the DesignSync tool lacks design authorization in this headless context, ntfy 'design-sync-pull: no design auth in headless' and exit WITHOUT committing (do not fabricate)." \
  --dangerously-skip-permissions >>"$LOG" 2>&1
rc=$?
echo "$(date -Is) === design-sync-pull done rc=$rc ===" >>"$LOG"
exit $rc
