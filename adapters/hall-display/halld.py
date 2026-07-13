#!/usr/bin/env python3
"""halld — Piranesi VUI hall display organ (branch-0 kiosk).

A spectator surface for the household's LIVE CONVERSATION capability: polls
the voxd daemons (the process behind wake-word conversation + intercom) on
every configured unit — internode-0 (FULL) and branch-1 (PERIPHERAL) — and
serves the complete VUI orb page reflecting the household's merged
conversational presence, attributed to the unit carrying it.

WAKE-GATED PANEL POWER: the display stays OFF unless a wake-word exchange
happened within the last HALL_WAKE_WINDOW_S (default 3600s) on any unit, or
an intercom session is live right now. Power toggling shells out to the
host's existing display-power.sh (sway `output * power`), so this organ
composes with — and supersedes — the old fixed morning/evening timers.

Wake signal: voxd keeps no explicit last_wake_at; `last_transcript_at` is
the faithful proxy (transcripts only arise from post-wake captures and
follow-up turns). Intercom sessions count as live conversation. voxd
restarts clear the in-memory timestamp — the panel then sleeps until the
next wake, which is the honest failure direction for a screen.

Conventions per paneld (workspace/infra/internode-panel): single-file
stdlib daemon, sampler threads feeding cached state, bounded loops,
time-limited HTTP + subprocess, CORS on GETs.
"""
import json
import os
import subprocess
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BIND = os.environ.get("HALL_BIND", "0.0.0.0")
PORT = int(os.environ.get("HALL_PORT", "9676"))
UNITS_SPEC = os.environ.get(
    "HALL_VOX_UNITS",
    "internode-0=http://piranesi-internode-0.tail8d99b6.ts.net:9668,"
    "branch-1=http://piranesi-branch-1.tail8d99b6.ts.net:9668")
POLL_S = float(os.environ.get("HALL_POLL_S", "2"))
WAKE_WINDOW_S = float(os.environ.get("HALL_WAKE_WINDOW_S", "3600"))
POWER_CMD = os.environ.get(
    "HALL_POWER_CMD", "/home/p/dashboard/kiosk/display-power.sh")
POWER_TICK_S = float(os.environ.get("HALL_POWER_TICK_S", "20"))
WEB_ROOT = os.environ.get(
    "HALL_WEB_ROOT",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "web"))
THINKING_HORIZON_S = 30  # transcript newer than reply => pipeline deliberating

UNITS = []
for part in UNITS_SPEC.split(","):
    part = part.strip()
    if part and "=" in part:
        name, url = part.split("=", 1)
        UNITS.append((name.strip(), url.strip().rstrip("/")))

# Priority of conversational presence when merging units (highest wins).
PRIORITY = {"talking": 5, "thinking": 4, "listening": 3,
            "working": 2, "waiting": 1, "error": 0}

# Context modulation is a household-wide posture, so it merges by SEVERITY, not
# by which unit is loudest: any unit reporting "threat" puts the whole house in
# threat; "degraded" outranks the default "auto". Values come from each unit's
# voxd /status.modulation (contract: auto | degraded | threat). Unknown/future
# values fall through to "auto" so an older display never mis-renders.
MOD_SEVERITY = {"threat": 2, "degraded": 1, "auto": 0}


def merge_modulation(current, reported):
    """Fold one unit's reported modulation into the house posture so far."""
    if reported == "threat":
        return "threat"
    if reported == "degraded" and current != "threat":
        return "degraded"
    return current


def _ts(iso):
    if not iso:
        return 0.0
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return time.mktime(time.strptime(iso[:19], fmt))
        except ValueError:
            continue
    return 0.0


def unit_presence(st):
    """Map one voxd /status dict to (state, caption) — same derivation the
    vivid kiosk uses, minus the unreachable case (handled by the merger)."""
    if st.get("intercom", {}).get("active"):
        return "talking", "Intercom open."
    if st.get("playing"):
        reply = st.get("last_reply") or st.get("last_say") or ""
        return "talking", reply[:140]
    heard, replied = _ts(st.get("last_transcript_at")), _ts(st.get("last_reply_at"))
    if heard and heard > replied and time.time() - heard < THINKING_HORIZON_S:
        return "thinking", ""
    if st.get("convo_active"):
        return "listening", ""
    return "waiting", ""


class HallState:
    def __init__(self):
        self._lock = threading.Lock()
        self._units = {name: {"reachable": False, "status": {}, "at": 0.0}
                       for name, _ in UNITS}
        self._started = time.time()
        self.display_power = None      # None until first governor decision
        self.last_power_change = 0.0
        self.power_errors = 0

    def update(self, name, status):
        with self._lock:
            self._units[name] = {"reachable": status is not None,
                                 "status": status or {}, "at": time.time()}

    def merged(self):
        """One voxd-shaped status for the page + gate facts."""
        with self._lock:
            units = {n: dict(u) for n, u in self._units.items()}
        best = ("error", "", None)   # state, caption, unit
        best_rank = -1
        last_activity = 0.0
        intercom_live = False
        any_reachable = False
        modulation = "auto"
        for name, u in units.items():
            if not u["reachable"]:
                continue
            any_reachable = True
            st = u["status"]
            modulation = merge_modulation(modulation, st.get("modulation"))
            if st.get("intercom", {}).get("active"):
                intercom_live = True
            last_activity = max(last_activity, _ts(st.get("last_transcript_at")))
            state, caption = unit_presence(st)
            rank = PRIORITY[state]
            # tie-break: most recent transcript owns the hall
            if rank > best_rank or (
                    rank == best_rank and
                    _ts(st.get("last_transcript_at")) > last_activity):
                best_rank = rank
                best = (state, caption, name)
        wake_active = intercom_live or (
            last_activity and time.time() - last_activity < WAKE_WINDOW_S)
        state, caption, unit = best
        if not any_reachable:
            state, caption, unit = "error", "The voices of the house are silent.", None
        return {
            "ok": True,
            "state": state,
            "caption": caption,
            "source_unit": unit,
            "modulation": modulation,
            "wake_active": bool(wake_active),
            "last_activity_at": last_activity or None,
            "intercom_live": intercom_live,
            "display_power": self.display_power,
            "units": {n: {"reachable": u["reachable"],
                          "listener": u["status"].get("listener"),
                          "playing": u["status"].get("playing"),
                          "convo_active": u["status"].get("convo_active"),
                          "intercom": u["status"].get("intercom", {}).get("active"),
                          "last_transcript_at": u["status"].get("last_transcript_at")}
                      for n, u in units.items()},
            "uptime_s": round(time.time() - self._started, 1),
        }


class UnitPoller(threading.Thread):
    def __init__(self, state, name, url):
        super().__init__(daemon=True)
        self.state, self.name, self.url = state, name, url
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def run(self):
        while not self._stop.is_set():
            status = None
            try:
                with urllib.request.urlopen(self.url + "/status", timeout=4) as r:
                    status = json.loads(r.read(262144).decode("utf-8", "ignore"))
            except Exception:
                status = None
            self.state.update(self.name, status)
            self._stop.wait(POLL_S)


class PowerGovernor(threading.Thread):
    """Holds the panel dark outside the wake window. Only speaks to the
    power script on state CHANGES (sway output power is not idempotent-free:
    each call round-trips IPC and posts an advisory)."""

    def __init__(self, state, power_cmd=POWER_CMD):
        super().__init__(daemon=True)
        self.state = state
        self.power_cmd = power_cmd
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def _apply(self, on):
        try:
            subprocess.run([self.power_cmd, "on" if on else "off"],
                           timeout=15, check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.state.display_power = "on" if on else "off"
            self.state.last_power_change = time.time()
            print("[halld] display %s" % self.state.display_power, flush=True)
        except Exception as e:
            self.state.power_errors += 1
            print("[halld] power %s failed: %s" % ("on" if on else "off", e),
                  flush=True)

    def run(self):
        while not self._stop.is_set():
            want_on = self.state.merged()["wake_active"]
            current = self.state.display_power
            if current is None or (current == "on") != want_on:
                self._apply(want_on)
            self._stop.wait(POWER_TICK_S)


def make_handler(state):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass  # /vox/status polls every 400ms; journald doesn't need them

        def _json(self, code, obj):
            b = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

        def do_GET(self):
            if self.path == "/health":
                m = state.merged()
                return self._json(200, {
                    "ok": True, "display_power": m["display_power"],
                    "wake_active": m["wake_active"],
                    "units": {n: u["reachable"] for n, u in m["units"].items()},
                    "power_errors": state.power_errors})
            if self.path == "/vox/status":
                return self._json(200, state.merged())
            # static site
            path = "/index.html" if self.path in ("/", "") else self.path
            path = os.path.normpath(path).lstrip("/")
            full = os.path.join(WEB_ROOT, path)
            if not full.startswith(os.path.abspath(WEB_ROOT)) or not os.path.isfile(full):
                return self._json(404, {"error": "not found"})
            ctype = {"html": "text/html", "js": "application/javascript",
                     "css": "text/css", "svg": "image/svg+xml"}.get(
                full.rsplit(".", 1)[-1], "application/octet-stream")
            with open(full, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    return Handler


def main():
    state = HallState()
    pollers = [UnitPoller(state, n, u) for n, u in UNITS]
    for p in pollers:
        p.start()
    gov = PowerGovernor(state)
    gov.start()
    srv = ThreadingHTTPServer((BIND, PORT), make_handler(state))
    print("[halld] units=%s http=%s:%d wake_window=%ss power=%s" %
          ([n for n, _ in UNITS], BIND, PORT, WAKE_WINDOW_S, POWER_CMD),
          flush=True)
    try:
        srv.serve_forever()
    finally:
        gov.stop()
        for p in pollers:
            p.stop()


if __name__ == "__main__":
    main()
