#!/usr/bin/env bash
# design-sync-pull.test.sh — fault-injection suite for the shell-owned alert path.
#
# Delta #27: a check that cannot fail is not a check. Every assertion below is
# paired with an INJECTED FAULT that makes it fail, so a PASS here is evidence
# rather than decoration. Nothing touches the real repo, the real log, the real
# notify dedupe stamps, or Sat's phone: DS_REPO/DS_LOG/DS_LOCK/DS_CLAUDE and
# NOTIFY_DEDUPE_DIR are redirected into a temp tree and every ntfy publish goes
# to a local sink that records it.
#
# Usage: bash scripts/design-sync-pull.test.sh
# Exit:  0 all assertions pass, 1 any failure, 3 environment missing.
#
# P10 RELAXATIONS: (1) the sink-readiness wait is a loop, bounded at 50
# iterations; (2) Rule 10 `set -e` is off on purpose — a suite that aborts on its
# first failing assertion reports one defect and hides the rest; (3) the `rm -rf`
# in cleanup() targets only the mktemp -d scratch tree and is guarded on a
# /tmp/ prefix, which is the per-session-scratch carve-out.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NOTIFY_SH="${DS_NOTIFY_SH:-/home/s/Piranesi/astroclaw/workspace/skills/notify.sh}"
TMP=""
PORT=0
SINK_PID=0
PASS=0
FAIL=0

cleanup() {
  (( SINK_PID > 0 )) && kill "$SINK_PID" 2>/dev/null
  [[ -n "$TMP" && "$TMP" == /tmp/* ]] && rm -rf "$TMP"
  return 0
}
trap cleanup EXIT

ok()   { PASS=$((PASS+1)); printf 'PASS  %s\n' "$1"; }
bad()  { FAIL=$((FAIL+1)); printf 'FAIL  %s\n' "$1"; }
check() { # <desc> <expected> <actual>
  if [[ "$2" == "$3" ]]; then ok "$1"; else bad "$1 (want='$2' got='$3')"; fi
}

start_sink() {
  PORT=$(( 20000 + RANDOM % 20000 ))
  python3 -c '
import sys, http.server
port, out = int(sys.argv[1]), sys.argv[2]
class H(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n).decode("utf-8", "replace").replace("\n", " ")
        with open(out, "a") as fh:
            fh.write("%s\t%s\t%s\n" % (self.headers.get("Title", ""),
                                       self.headers.get("Priority", ""), body))
        self.send_response(200); self.end_headers(); self.wfile.write(b"ok")
    def log_message(self, *a): pass
http.server.HTTPServer(("127.0.0.1", port), H).serve_forever()
' "$PORT" "$TMP/sink.tsv" &
  SINK_PID=$!
  local i=0
  while (( i < 50 )); do
    if curl -s -m 1 -X POST -d ping "http://127.0.0.1:${PORT}/t" >/dev/null 2>&1; then
      : >"$TMP/sink.tsv"; return 0
    fi
    i=$((i+1)); sleep 0.1
  done
  echo "sink did not come up on port $PORT" >&2
  return 3
}

setup_repo() {
  mkdir -p "$TMP/repo/.design-sync" "$TMP/repo/scripts" "$TMP/dedupe" || return 3
  cp "$HERE/design-sync-status.py" "$TMP/repo/scripts/" || return 3
  git -C "$TMP/repo" init -q                       || return 3
  git -C "$TMP/repo" config user.email t@t         || return 3
  git -C "$TMP/repo" config user.name t            || return 3
  echo seed >"$TMP/repo/seed"                      || return 3
  git -C "$TMP/repo" add -A                        || return 3
  git -C "$TMP/repo" commit -qm seed               || return 3
  printf '#!/bin/bash\necho dispatched >> "%s/agent-runs"\n[ -n "${DS_TEST_JSON:-}" ] && printf %%s "$DS_TEST_JSON" > "%s/repo/.design-sync/last-run.json"\nprintf %%s "${DS_TEST_OUT:-}"\nexit ${DS_TEST_RC:-0}\n' "$TMP" "$TMP" \
    >"$TMP/stub-claude" || return 3
  chmod +x "$TMP/stub-claude" || return 3
  # Credential-store fixtures for the preflight. `authorized` is the default for
  # every pre-existing assertion, so they keep exercising the dispatched-agent
  # path exactly as before; the others drive the preflight's three outcomes.
  # Token VALUES are dummies — the preflight only asks whether the key exists.
  printf '{"claudeAiOauth":{"accessToken":"x"},"designOauth":{"accessToken":"x","scopes":["user:design:read"]}}\n' \
    >"$TMP/creds-authorized.json"   || return 3
  printf '{"claudeAiOauth":{"accessToken":"x"}}\n' \
    >"$TMP/creds-no-design.json"    || return 3
  printf '{not json\n' >"$TMP/creds-corrupt.json" || return 3
  # The stub records every dispatch so "the agent did not run" is asserted on
  # evidence, not on the absence of an alert.
  return 0
}

# Run the subject once; echo how many ntfy messages the sink received.
# Everything is POSITIONAL on purpose: bash persists `VAR=x func` assignments
# into the calling shell, so an env-prefix style here would leak DS_TEST_RC=1
# from the quota case into every later assertion.
run_once() { # <status-json|""> [agent-rc] [agent-stdout] [dedupe-disable 0|1] [creds-file]
  local before after
  before="$(wc -l <"$TMP/sink.tsv")"
  DS_TEST_JSON="${1:-}" DS_TEST_RC="${2:-0}" DS_TEST_OUT="${3:-}" \
  NOTIFY_DEDUPE_DISABLE="${4:-0}" \
  DS_REPO="$TMP/repo" DS_LOG="$TMP/run.log" DS_LOCK="$TMP/lock" \
  DS_CLAUDE="$TMP/stub-claude" DS_NOTIFY_SH="$NOTIFY_SH" DS_AGENT_TIMEOUT=30 \
  DS_CREDENTIALS="${5:-$TMP/creds-authorized.json}" \
  NOTIFY_DEDUPE_DIR="$TMP/dedupe" NTFY_URL="http://127.0.0.1:${PORT}" \
  NTFY_TOPIC=test NTFY_FALLBACK_URL=none NTFY_OOB_URL="" \
    bash "$HERE/design-sync-pull.sh" >/dev/null 2>&1
  after="$(wc -l <"$TMP/sink.tsv")"
  printf '%d' $(( after - before ))
}

last_field() { tail -1 "$TMP/sink.tsv" | cut -f"$1"; }

# The verdict the subject itself recorded for the most recent run. Asserting on
# this instead of on "the last line in the sink" is what makes the negative
# cases sound: a SUPPRESSED alert leaves the sink's last line unchanged, so a
# naive tail would keep reading the previous run's title and pass by accident —
# which is exactly how the first draft of assertion 4b passed nothing at all.
last_status() { grep -o 'status=[a-z-]*' "$TMP/run.log" | tail -1 | cut -d= -f2; }

J_NOAUTH='{"schema":1,"ts":"t","status":"noauth","detail":"DesignSync needs design-system authorization","head":"x","ds_files":null}'
J_NOOP='{"schema":1,"ts":"t","status":"ok-noop","detail":"33 files byte-identical","head":"x","ds_files":33}'
J_CHANGED='{"schema":1,"ts":"t","status":"ok-changed","detail":"pulled _ds_bundle.js, commit abc1234","head":"x","ds_files":34}'

main() {
  [[ -r "$NOTIFY_SH" ]] || { echo "notify.sh missing: $NOTIFY_SH" >&2; return 3; }
  TMP="$(mktemp -d /tmp/cpcs-dspull-test.XXXXXX)" || return 3
  : >"$TMP/sink.tsv"
  setup_repo || return 3
  start_sink || return 3

  # 1 — noauth alerts, at default priority, naming the remedy not the symptom.
  check "noauth fires once" 1 "$(run_once "$J_NOAUTH")"
  check "noauth priority is default (not high)" default "$(last_field 2)"
  case "$(last_field 3)" in *"/design-login"*) ok "noauth body names /design-login" ;;
                            *) bad "noauth body names /design-login" ;; esac

  # 2 — THE NOISE FIX: an unchanged condition is suppressed on the next tick.
  check "noauth 2nd tick suppressed" 0 "$(run_once "$J_NOAUTH")"
  check "noauth 3rd tick suppressed" 0 "$(run_once "$J_NOAUTH")"
  # 2b — INJECTED FAULT: disable dedupe. If assertion 2 could not fail, this
  # would still read 0. It must read 1.
  check "FAULT dedupe off -> noauth fires again" 1 \
    "$(run_once "$J_NOAUTH" 0 "" 1)"

  # 3 — recovery: a good run clears the key, so the NEXT outage alerts at once.
  check "ok-noop emits heartbeat" 1 "$(run_once "$J_NOOP")"
  check "ok-noop priority is min" min "$(last_field 2)"
  check "recovered outage alerts immediately" 1 "$(run_once "$J_NOAUTH")"

  # 4 — a blind instrument must ALARM, never read as success.
  rm -f "$TMP/repo/.design-sync/last-run.json"
  check "missing status file alerts" 1 "$(run_once "")"
  check "missing status file is high" high "$(last_field 2)"
  case "$(last_field 1)" in *"no verdict"*) ok "missing status titled 'no verdict'" ;;
                            *) bad "missing status titled 'no verdict'" ;; esac
  rm -f "$TMP/repo/.design-sync/last-run.json"
  check "unparseable status alerts" 1 "$(run_once '{not json')"
  # An out-of-schema status value is the SAME condition as unhandled JSON (the
  # agent's verdict is unusable), so it dedupes onto the same key — asserted on
  # the recorded verdict, then re-armed to prove the alert itself still fires.
  rm -f "$TMP/repo/.design-sync/last-run.json"
  run_once '{"schema":1,"status":"totally-fine"}' >/dev/null
  check "out-of-schema is not a verdict" unparseable "$(last_status)"
  rm -f "$TMP/dedupe/design-sync-status.stamp" "$TMP/repo/.design-sync/last-run.json"
  check "out-of-schema alerts when re-armed" 1 \
    "$(run_once '{"schema":1,"status":"totally-fine"}')"

  # 4b — INJECTED FAULT (the other direction): a VALID verdict must NOT be
  # classified as a missing/unusable one. Without this, assertion 4 could be
  # firing on everything and would still look green.
  rm -f "$TMP/repo/.design-sync/last-run.json"
  run_once "$J_NOOP" >/dev/null
  check "FAULT valid verdict classified ok-noop" ok-noop "$(last_status)"

  # 5 — a stale file (agent died before rewriting it) is not believed.
  touch -d '2000-01-01' "$TMP/repo/.design-sync/last-run.json" || return 3
  check "stale status file alerts" 1 "$(run_once "")"
  check "stale status file is high" high "$(last_field 2)"

  # 6 — quota exhaustion is its own low-priority stream, not a FAILED page.
  rm -f "$TMP/repo/.design-sync/last-run.json"
  check "quota alerts" 1 \
    "$(run_once "" 1 "You've hit your weekly limit")"
  check "quota priority is low" low "$(last_field 2)"

  # 6b — THE REGRESSION: the banner's <kind> is not always "weekly". Every
  # "session limit" tick in production (5 of them, 2026-09-04..05) was
  # misclassified as `error` and paged HIGH "FAILED"; status=quota had fired 0
  # times in 76 quota events. Assert the OBSERVED wording, verdict-first — a
  # `low` read on the sink alone would pass on a suppressed page.
  rm -f "$TMP/repo/.design-sync/last-run.json"
  run_once "" 1 "You've hit your session limit · resets 5pm (America/Toronto)" >/dev/null
  check "session limit is quota, not error" quota "$(last_status)"
  rm -f "$TMP/dedupe/design-sync-quota.stamp" "$TMP/repo/.design-sync/last-run.json"
  check "session limit alerts when re-armed" 1 \
    "$(run_once "" 1 "You've hit your session limit · resets 5pm (America/Toronto)")"
  check "session limit priority is low" low "$(last_field 2)"
  case "$(last_field 3)" in *"session limit"*) ok "quota body names the limit kind" ;;
                            *) bad "quota body names the limit kind" ;; esac

  # 6c — INJECTED FAULT (the other direction): the broadened match must not
  # swallow a genuine failure. A crash whose output merely mentions "limit" is
  # still an `error` page, not a low-priority quota notice.
  rm -f "$TMP/repo/.design-sync/last-run.json"
  run_once "" 1 "TypeError: request exceeded the configured limit" >/dev/null
  check "FAULT unrelated 'limit' stays error" error "$(last_status)"

  # 7 — real news is never deduped into silence.
  check "ok-changed alerts" 1 "$(run_once "$J_CHANGED")"
  check "ok-changed priority is default" default "$(last_field 2)"
  check "ok-changed repeats (repeat-after 0)" 1 "$(run_once "$J_CHANGED")"

  # 8 — THE PREFLIGHT: `/design-login` mints a `designOauth` slot in the Claude
  # Code credential store and DesignSync refuses without it, so when that slot is
  # provably absent the agent's verdict is already known and spending a ~25-min
  # agent run on it is what exhausts the session quota. Assert the verdict AND
  # that no agent was dispatched — an alert alone would pass either way.
  : >"$TMP/agent-runs"
  rm -f "$TMP/dedupe/design-sync-auth.stamp" "$TMP/repo/.design-sync/last-run.json"
  check "no designOauth -> noauth without the agent" 1 \
    "$(run_once "" 0 "" 0 "$TMP/creds-no-design.json")"
  check "preflight verdict is noauth" noauth "$(last_status)"
  check "preflight did not dispatch the agent" 0 "$(wc -l <"$TMP/agent-runs")"
  # The preflight must leave a CURRENT report, not a file frozen at the last
  # dispatched run — a stale last-run.json is read as `stale` and pages HIGH.
  check "preflight rewrote last-run.json" noauth \
    "$(python3 "$HERE/design-sync-status.py" "$TMP/repo/.design-sync/last-run.json" | cut -f1)"

  # 8b — INJECTED FAULT: a check that cannot fail is not a check. With the slot
  # PRESENT the agent must still be dispatched, or the preflight would be
  # silently pausing the pull forever and assertion 8 would pass on nothing.
  : >"$TMP/agent-runs"
  rm -f "$TMP/repo/.design-sync/last-run.json"
  run_once "$J_NOOP" >/dev/null
  check "FAULT designOauth present -> agent dispatched" 1 "$(wc -l <"$TMP/agent-runs")"

  # 8c — FAILS OPEN: an unreadable or corrupt credential store means "cannot
  # tell", never "provably absent". Suppressing a run we have NOT confirmed
  # would be exactly the silent-failure class this suite exists to prevent.
  : >"$TMP/agent-runs"
  rm -f "$TMP/repo/.design-sync/last-run.json"
  run_once "$J_NOOP" 0 "" 0 "$TMP/creds-corrupt.json" >/dev/null
  check "FAULT corrupt store still dispatches" 1 "$(wc -l <"$TMP/agent-runs")"
  : >"$TMP/agent-runs"
  rm -f "$TMP/repo/.design-sync/last-run.json"
  run_once "$J_NOOP" 0 "" 0 "$TMP/creds-absent.json" >/dev/null
  check "FAULT missing store still dispatches" 1 "$(wc -l <"$TMP/agent-runs")"

  printf '\n%d passed, %d failed\n' "$PASS" "$FAIL"
  (( FAIL == 0 )) || return 1
  return 0
}

main "$@"
exit $?
