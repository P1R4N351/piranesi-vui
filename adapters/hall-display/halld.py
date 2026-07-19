#!/usr/bin/env python3
"""halld — Piranesi VUI hall display organ (branch-0 kiosk).

A spectator surface for the household's LIVE CONVERSATION capability: polls
the voxd daemons (the process behind wake-word conversation + intercom) on
every configured unit — internode-0 (FULL) and branch-1 (PERIPHERAL) — and
serves the complete VUI orb page reflecting the household's merged
conversational presence, attributed to the unit carrying it.

WAKE-GATED PANEL POWER: the display stays OFF unless a wake-word exchange
happened within the last HALL_WAKE_WINDOW_S (default 3600s) on any unit, or
an intercom session is live right now.

OCCUPANCY-TRIGGERED PANEL POWER (added 2026-07-13): the panel ALSO wakes when
occupancyd (branch-0) reports the office `occupied` — lights on, someone here —
and sleeps again only after the room has been continuously `dark` for
HALL_DARK_GRACE_S. Occupancy is an ADDITIONAL trigger, never a veto: a wake
word still lights the panel in a pitch-dark room, exactly as before. The two
triggers OR together, and the panel sleeps only when BOTH agree it should.
Occupancy `unknown`/unreachable degrades precisely to the old wake-only
behaviour, so a dead camera costs us nothing we had.

LANDSCAPE: on every wake the desired output state — power on, transform
`normal` (landscape) — is asserted, not assumed, and it is RE-asserted whenever
the set of connected outputs changes. That matters because a panel that has
been powered off at the mains drops its hotplug-detect line: the connector
reads `disconnected`, sway destroys the output object, and any orientation we
set earlier dies with it. Re-applying on hotplug is what makes the panel come
back up in landscape by itself when it is switched on again.

HONEST POWER REPORTING: `swaymsg 'output * power on'` returns {"success": true}
when it matches ZERO outputs. That is not a hypothetical — on branch-0 today
every DRM connector reads `disconnected`, sway holds no output object at all,
and this daemon's own journal has been logging a satisfied "[halld] display on"
against a panel that is electrically absent. A monitor that a broken system can
satisfy is not a monitor. So the governor now COUNTS the outputs it actually
addressed: with none present, display_power is reported as "absent" (never
"on"), /health goes unhealthy, and the condition is stated in the log rather
than papered over.

Wake signal: voxd keeps no explicit last_wake_at; `last_transcript_at` is
the faithful proxy (transcripts only arise from post-wake captures and
follow-up turns). Intercom sessions count as live conversation. voxd
restarts clear the in-memory timestamp — the panel then sleeps until the
next wake, which is the honest failure direction for a screen.

Conventions per paneld (workspace/infra/internode-panel): single-file
stdlib daemon, sampler threads feeding cached state, bounded loops,
time-limited HTTP + subprocess, CORS on GETs.
"""
# P10 RELAXATIONS: make_handler() exceeds R4's 40-line budget because it is a
# handler-FACTORY closure -- its "body" is a class definition (the house idiom
# shared with paneld and the original halld), not straight-line logic. Hoisting
# the class to module scope to satisfy the line count would require a global
# mutable HallState, trading a cosmetic R4 warning for a real R5 violation. The
# closure stays.

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

# ---- occupancy trigger ----------------------------------------------------
OCCUPANCY_URL = os.environ.get(
    "HALL_OCCUPANCY_URL", "http://127.0.0.1:9677/occupancy")
OCCUPANCY_POLL_S = float(os.environ.get("HALL_OCCUPANCY_POLL_S", "5"))
# How long the room must be continuously dark before we let the panel sleep.
# Generous on purpose: sleeping the screen in the face of someone who merely
# dimmed the lights is far more annoying than a screen that stays lit a few
# minutes too long.
DARK_GRACE_S = float(os.environ.get("HALL_DARK_GRACE_S", "300"))
# A wake this recent counts as ACTIVE interaction and lights even a dark room;
# older-than-this wake activity does NOT keep a sustained-dark empty room lit.
WAKE_RECENT_S = float(os.environ.get("HALL_WAKE_RECENT_S", "180"))
OCCUPANCY_STALE_S = float(os.environ.get("HALL_OCCUPANCY_STALE_S", "90"))

# ---- output/orientation ---------------------------------------------------
SWAY_USER = os.environ.get("HALL_SWAY_USER", "p")
SWAY_SOCK_GLOB = os.environ.get("HALL_SWAY_SOCK_GLOB", "sway-ipc.*.sock")
# `normal` is landscape. (`90`/`270` would be portrait on a landscape panel.)
TRANSFORM = os.environ.get("HALL_TRANSFORM", "normal")
OUTPUT_SEL = os.environ.get("HALL_OUTPUT", "*")
ENSURE_VUI = os.environ.get("HALL_ENSURE_VUI", "1") not in ("0", "off", "false")
VUI_CMD = os.environ.get(
    "HALL_VUI_CMD", "/home/p/dashboard/kiosk/start-chromium.sh")
VUI_PROC = os.environ.get("HALL_VUI_PROC", "chromium")
SWAY_TIMEOUT_S = 10
WEB_ROOT = os.environ.get(
    "HALL_WEB_ROOT",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "web"))
THINKING_HORIZON_S = 30  # transcript newer than reply => pipeline deliberating

# ---- control-centre report panel ------------------------------------------
# voxd POSTs a voice status report to /report; halld renders it as a panel
# ALONGSIDE the orb for ttl_s seconds and counts the acceptance as display-wake
# activity so the panel lights even if the screen was off. The wire contract is
# FROZEN (voxd is the sender): title (<=60, required) + domain (enum) + spoken
# (<=300) + tiles (<=8) + lines (<=6) + ttl_s (clamped 15..600, default 90).
REPORT_DEFAULT_TTL_S = float(os.environ.get("HALL_REPORT_DEFAULT_TTL_S", "90"))
REPORT_MIN_TTL_S = float(os.environ.get("HALL_REPORT_MIN_TTL_S", "15"))
REPORT_MAX_TTL_S = float(os.environ.get("HALL_REPORT_MAX_TTL_S", "600"))
REPORT_MAX_TILES = int(os.environ.get("HALL_REPORT_MAX_TILES", "8"))
REPORT_MAX_LINES = int(os.environ.get("HALL_REPORT_MAX_LINES", "6"))
# Hard ceiling on the POST body: a report is small; anything larger is a bug or
# an attack, not a report. Read is bounded to exactly Content-Length <= this.
REPORT_MAX_BODY = int(os.environ.get("HALL_REPORT_MAX_BODY", "16384"))
REPORT_TITLE_MAX = 60      # per-field caps (frozen contract; not env genes)
REPORT_SPOKEN_MAX = 300
REPORT_TILE_LABEL_MAX = 24
REPORT_TILE_VALUE_MAX = 16
REPORT_LINE_MAX = 90
REPORT_DOMAINS = ("overview", "fleet", "services", "spoolers",
                  "alerts", "advisories", "sessions")

UNITS = []
for part in UNITS_SPEC.split(","):
    part = part.strip()
    if part and "=" in part:
        name, url = part.split("=", 1)
        UNITS.append((name.strip(), url.strip().rstrip("/")))

# Priority of conversational presence when merging units (highest wins).
PRIORITY = {"talking": 5, "thinking": 4, "listening": 3,
            "working": 2, "waiting": 1, "error": 0}


# ---- sway IPC -------------------------------------------------------------
# Spoken to directly (rather than only through display-power.sh) because the
# governor needs to ENUMERATE outputs and set orientation, not just flip power.

def _sway_env():
    """Locate the kiosk's sway IPC socket, as display-power.sh does."""
    import glob
    import pwd
    uid = pwd.getpwnam(SWAY_USER).pw_uid
    rundir = "/run/user/%d" % uid
    socks = sorted(glob.glob(os.path.join(rundir, SWAY_SOCK_GLOB)))
    if not socks:
        raise RuntimeError("no sway IPC socket in %s (kiosk not running?)" % rundir)
    env = dict(os.environ)
    env.update({"XDG_RUNTIME_DIR": rundir, "SWAYSOCK": socks[0]})
    return env, uid


def _swaymsg(args, want_json=False):
    """Run swaymsg as the kiosk user. Time-limited; raises on failure."""
    env, uid = _sway_env()
    cmd = ["swaymsg"] + (["-t"] if want_json else []) + list(args)
    if os.geteuid() != uid:                      # halld runs as root
        cmd = ["sudo", "-u", SWAY_USER, "-E"] + cmd
    out = subprocess.run(cmd, env=env, timeout=SWAY_TIMEOUT_S, check=True,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return out.stdout.decode("utf-8", "ignore")


def sway_outputs():
    """[{name, active, power, transform, ...}] — the outputs sway ACTUALLY has.

    An empty list is the honest answer when the panel is powered off at the
    mains: its hotplug-detect line drops, the connector reads `disconnected`,
    and sway holds no output object to command. This is the fact that
    `output * power on` silently hides by succeeding against nothing.
    """
    doc = json.loads(_swaymsg(["get_outputs"], want_json=True) or "[]")
    return doc if isinstance(doc, list) else []


def apply_display(on, transform=TRANSFORM, sel=OUTPUT_SEL):
    """Assert the desired output state. Returns the number of outputs addressed.

    The count is the point: it is the difference between "we asked" and "it
    landed", and reporting it is what stops this daemon from lying about a
    display that is not there.
    """
    outs = sway_outputs()
    if not outs:
        return 0
    if on:
        _swaymsg(["output %s power on" % sel])
        _swaymsg(["output %s transform %s" % (sel, transform)])
    else:
        _swaymsg(["output %s power off" % sel])
    return len(outs)


def vui_running():
    """Is the VUI browser up? Matched on process NAME, never on command line.

    `pgrep -f chromium` would also match any process whose ARGUMENTS merely
    mention chromium — a log grep, a deploy script, the shell that launched it,
    this daemon's own supervisor. A false positive there is silent and nasty:
    ensure_vui() would conclude the VUI was already running and never start it,
    leaving a lit panel showing nothing. `-x` matches the executable name
    exactly, which is the question we are actually asking.
    """
    return subprocess.run(["pgrep", "-x", VUI_PROC], timeout=5,
                          stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL).returncode == 0


def ensure_vui():
    """Start the VUI browser if an output exists and nothing is showing it.

    Only ever called when outputs are present, so on a panel-less host this is
    inert. Fire-and-forget: sway owns the child's lifetime, not us.
    """
    if not ENSURE_VUI or vui_running():
        return False
    env, _uid = _sway_env()
    _swaymsg(["exec %s" % VUI_CMD])
    print("[halld] VUI absent with an output present — started %s" % VUI_CMD,
          flush=True)
    return True


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


# Context modulation is a household-wide posture, merged by SEVERITY:
# threat > degraded > storm > rain > auto. Any unit reporting a higher-severity
# posture wins for the whole house; an unknown/absent value is severity 0 and
# never lowers the posture. Values come from each voxd /status.modulation. Lets a
# threat posture AND real weather (rain/storm) reach the branch-0 hall orb.
MOD_SEVERITY = {"threat": 4, "degraded": 3, "storm": 2, "rain": 1, "auto": 0}


def merge_modulation(current, reported):
    """Fold one unit's reported modulation into the house posture so far, by
    severity. An unknown/absent reported value is severity 0."""
    if MOD_SEVERITY.get(reported, 0) > MOD_SEVERITY.get(current, 0):
        return reported
    return current


def want_on(wake_active, wake_recent, occ_state, dark_for_s):
    """Should the panel be lit? The whole policy, in one place.

        wake word / intercom in the last WAKE_RECENT_S -> ON (a wake word in a
                                                dark room must still light the
                                                screen — but only RECENTLY, not
                                                for the whole hour-long window)
        room dark for >= grace, no RECENT wake -> off (a dark empty room has
                                                nobody to look at the screen;
                                                this OVERRIDES the stale long
                                                wake window — the bug where an
                                                hour-old transcript kept a dark
                                                empty room lit)
        wake word / intercom within WAKE_WINDOW_S, room not dark-abandoned -> ON
        room occupied                   -> ON
        room dark, but < grace          -> ON  (don't sleep the instant lights dip)
        occupancy unknown, no wake      -> off (degrades EXACTLY to the old
                                                wake-only behaviour)
    """
    if wake_recent:                                 # active interaction NOW: light it
        return True                                 # even in a dark room
    if occ_state == "dark" and dark_for_s >= DARK_GRACE_S:
        return False                                # sustained dark + no recent wake:
                                                    # sleep, beating the stale window
    if wake_active:
        return True
    if occ_state == "occupied":
        return True
    if occ_state == "dark":
        return dark_for_s < DARK_GRACE_S
    return False                                    # unknown: as it always was


# ---- report validation ----------------------------------------------------
# Pure functions: turn a POSTed body into a clean, bounded report or raise.
# The contract's split is deliberate: the four "malformed" cases (missing/
# overlong title, unknown domain, wrong types) are REJECTED (400); over-cap
# tiles/lines and out-of-range ttl are TRUNCATED/CLAMPED with a loud warning.

class ReportError(ValueError):
    """A report body the contract rejects outright => HTTP 400."""


def _clean_tiles(raw, warn):
    """Validate + truncate the tile list (<= REPORT_MAX_TILES). Loud on trim."""
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ReportError("tiles must be a list")
    if len(raw) > REPORT_MAX_TILES:
        warn.append("tiles truncated %d->%d" % (len(raw), REPORT_MAX_TILES))
    tiles = []
    n = min(len(raw), REPORT_MAX_TILES)              # bounded loop
    for i in range(n):
        t = raw[i]
        if not isinstance(t, dict):
            raise ReportError("tile %d must be an object" % i)
        label, value, ok = t.get("label"), t.get("value", ""), t.get("ok", None)
        if not isinstance(label, str) or not label:
            raise ReportError("tile %d needs a non-empty string label" % i)
        if not isinstance(value, str):
            raise ReportError("tile %d value must be a string" % i)
        if ok not in (True, False, None):
            raise ReportError("tile %d ok must be true/false/null" % i)
        if len(label) > REPORT_TILE_LABEL_MAX:
            warn.append("tile %d label truncated" % i)
            label = label[:REPORT_TILE_LABEL_MAX]
        if len(value) > REPORT_TILE_VALUE_MAX:
            warn.append("tile %d value truncated" % i)
            value = value[:REPORT_TILE_VALUE_MAX]
        tiles.append({"label": label, "value": value, "ok": ok})
    return tiles


def _clean_lines(raw, warn):
    """Validate + truncate the advisory lines (<= REPORT_MAX_LINES). Loud."""
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ReportError("lines must be a list")
    if len(raw) > REPORT_MAX_LINES:
        warn.append("lines truncated %d->%d" % (len(raw), REPORT_MAX_LINES))
    lines = []
    n = min(len(raw), REPORT_MAX_LINES)              # bounded loop
    for i in range(n):
        ln = raw[i]
        if not isinstance(ln, str):
            raise ReportError("line %d must be a string" % i)
        if len(ln) > REPORT_LINE_MAX:
            warn.append("line %d truncated" % i)
            ln = ln[:REPORT_LINE_MAX]
        lines.append(ln)
    return lines


def _clean_ttl(raw, warn):
    """Clamp ttl_s to [MIN, MAX]; default when absent. bool is NOT a number."""
    if raw is None:
        return REPORT_DEFAULT_TTL_S
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise ReportError("ttl_s must be a number")
    ttl = float(raw)
    clamped = min(max(ttl, REPORT_MIN_TTL_S), REPORT_MAX_TTL_S)
    if clamped != ttl:
        warn.append("ttl_s clamped %g->%g" % (ttl, clamped))
    return clamped


def validate_report(doc):
    """(report, warnings) or raise ReportError. The whole accept policy."""
    if not isinstance(doc, dict):
        raise ReportError("body must be a JSON object")
    warn = []
    title = doc.get("title")
    if not isinstance(title, str) or not title.strip():
        raise ReportError("title is required")
    if len(title) > REPORT_TITLE_MAX:
        raise ReportError("title exceeds %d chars" % REPORT_TITLE_MAX)
    domain = doc.get("domain", "overview")
    if not isinstance(domain, str) or domain not in REPORT_DOMAINS:
        raise ReportError("unknown domain")
    spoken = doc.get("spoken", "")
    if not isinstance(spoken, str):
        raise ReportError("spoken must be a string")
    if len(spoken) > REPORT_SPOKEN_MAX:
        warn.append("spoken truncated")
        spoken = spoken[:REPORT_SPOKEN_MAX]
    report = {"title": title, "domain": domain, "spoken": spoken,
              "tiles": _clean_tiles(doc.get("tiles"), warn),
              "lines": _clean_lines(doc.get("lines"), warn),
              "ttl_s": _clean_ttl(doc.get("ttl_s"), warn)}
    return report, warn


class HallState:
    def __init__(self):
        self._lock = threading.Lock()
        self._units = {name: {"reachable": False, "status": {}, "at": 0.0}
                       for name, _ in UNITS}
        self._started = time.time()
        self.display_power = None      # None until first governor decision
        self.last_power_change = 0.0
        self.power_errors = 0
        self.outputs = []              # names of the outputs sway actually has
        self.occ = {"state": "unknown", "at": 0.0, "luma": None,
                    "reachable": False, "dark_since": None}
        self.report = None             # last accepted report (retained on expiry)
        self.report_until = 0.0        # epoch the panel stops being active
        self.report_accepted_at = 0.0  # epoch of last accept (wake-activity mark)

    def set_report(self, doc):
        """Validate + store a report. Returns (until, warnings); raises
        ReportError on a malformed body. The store also stamps `at`/`until`
        into the retained copy so the page can render a timestamp and the
        governor can treat it as wake activity."""
        report, warn = validate_report(doc)
        now = time.time()
        until = now + report["ttl_s"]
        stored = dict(report)
        stored["at"] = now
        stored["until"] = until
        with self._lock:
            self.report = stored
            self.report_until = until
            self.report_accepted_at = now      # counts as recent wake (governor)
        return until, warn

    def report_view(self):
        """(active, report_or_None, until). `report` is the LAST accepted
        report, retained after expiry (GET /report shows it); `active` flips
        false once now >= until (the feed then hides the panel)."""
        with self._lock:
            rep = dict(self.report) if self.report else None
            until = self.report_until
        active = rep is not None and time.time() < until
        return active, rep, until

    def occupancy(self):
        """(state, dark_for_s). `unknown` whenever the sensor cannot be trusted,
        which every caller must treat as PERMISSIVE (i.e. as the old behaviour)."""
        with self._lock:
            occ = dict(self.occ)
        fresh = occ["reachable"] and (time.time() - occ["at"]) <= OCCUPANCY_STALE_S
        if not fresh:
            return "unknown", 0.0
        dark_for = (time.time() - occ["dark_since"]
                    if occ["state"] == "dark" and occ["dark_since"] else 0.0)
        return occ["state"], dark_for

    def set_occupancy(self, doc):
        with self._lock:
            now = time.time()
            if doc is None:
                self.occ["reachable"] = False
                return
            state = doc.get("state")
            if state not in ("occupied", "dark", "unknown"):
                self.occ["reachable"] = False
                return
            was = self.occ["state"]
            if state == "dark" and was != "dark":
                self.occ["dark_since"] = now       # start the grace clock
            elif state != "dark":
                self.occ["dark_since"] = None
            self.occ.update({"state": state, "at": now, "luma": doc.get("luma"),
                             "reachable": True})

    def update(self, name, status):
        with self._lock:
            self._units[name] = {"reachable": status is not None,
                                 "status": status or {}, "at": time.time()}

    def _merge_units(self, units):
        """Fold the per-unit voxd statuses into one presence. Unchanged logic."""
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
        if not any_reachable:
            best = ("error", "The voices of the house are silent.", None)
        return best, last_activity, intercom_live, modulation

    def merged(self):
        """One voxd-shaped status for the page + gate facts."""
        with self._lock:
            units = {n: dict(u) for n, u in self._units.items()}
        best, last_activity, intercom_live, modulation = self._merge_units(units)
        wake_active = intercom_live or (
            last_activity and time.time() - last_activity < WAKE_WINDOW_S)
        wake_recent = intercom_live or (
            last_activity and time.time() - last_activity < WAKE_RECENT_S)
        # A live report is active interaction: it must light the panel even in
        # a dark, unoccupied room for its whole lifetime — exactly like a recent
        # wake word. report_active is level-triggered off report_until, so when
        # the report expires the governor reconciles back to the prior policy
        # with no extra bookkeeping (same style as the occupancy trigger).
        report_active, report_rep, report_until = self.report_view()
        wake_active = bool(wake_active) or report_active
        wake_recent = bool(wake_recent) or report_active
        state, caption, unit = best
        occ_state, dark_for = self.occupancy()
        return {
            "ok": True,
            "state": state,
            "caption": caption,
            "source_unit": unit,
            "modulation": modulation,
            "wake_active": bool(wake_active),
            "last_activity_at": last_activity or None,
            "intercom_live": intercom_live,
            "occupancy": occ_state,
            "occupancy_luma": self.occ.get("luma"),
            "dark_for_s": round(dark_for, 1),
            "want_display_on": want_on(bool(wake_active), bool(wake_recent),
                                        occ_state, dark_for),
            "report_active": report_active,
            "report": report_rep if report_active else None,
            "report_until": report_until if report_until else None,
            "outputs": list(self.outputs),
            "outputs_present": len(self.outputs),
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


class OccupancyPoller(threading.Thread):
    """Keep the room's light/dark state fresh. Failure is silent-but-visible:
    the doc goes unreachable, occupancy() reports `unknown`, and the governor
    falls back to wake-only. A camera outage must not change what the panel
    does, only what we know about why."""

    def __init__(self, state, url=OCCUPANCY_URL):
        super().__init__(daemon=True)
        self.state, self.url = state, url
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def run(self):
        if not self.url:
            return
        while not self._stop.is_set():
            doc = None
            try:
                with urllib.request.urlopen(self.url, timeout=4) as r:
                    doc = json.loads(r.read(65536).decode("utf-8", "ignore"))
            except Exception:
                doc = None
            self.state.set_occupancy(doc)
            self._stop.wait(OCCUPANCY_POLL_S)


class DisplayGovernor(threading.Thread):
    """Assert the desired panel state: power, orientation, and the VUI itself.

    Re-asserts on ANY change to the set of outputs, not only when the wake/
    occupancy decision flips. That is what handles the panel being switched on
    at the wall: its hotplug line comes back, sway creates a fresh output object
    with default orientation, and we immediately drive it to power-on +
    landscape. Without the re-assert, a panel could return in the wrong
    orientation, or dark, and stay that way until the next wake word.
    """

    def __init__(self, state):
        super().__init__(daemon=True)
        self.state = state
        self._stop = threading.Event()
        self._last_outputs = None
        self._warned_absent = False

    def stop(self):
        self._stop.set()

    def _apply(self, on):
        try:
            n = apply_display(on)
            if n == 0:
                # The honest branch. sway answers {"success": true} to
                # `output * power on` with no outputs attached, which is how
                # this daemon spent months reporting a panel it did not have.
                self.state.display_power = "absent"
                if not self._warned_absent:
                    print("[halld] NO OUTPUTS: sway holds no output object "
                          "(every DRM connector reads disconnected — panel off "
                          "at the mains or unplugged). Power/orientation "
                          "commands would be silently accepted and do nothing, "
                          "so they are NOT being claimed as applied.",
                          flush=True)
                    self._warned_absent = True
                return
            self._warned_absent = False
            self.state.display_power = "on" if on else "off"
            self.state.last_power_change = time.time()
            print("[halld] display %s on %d output(s)%s"
                  % (self.state.display_power, n,
                     " (landscape: transform=%s)" % TRANSFORM if on else ""),
                  flush=True)
            if on:
                ensure_vui()
        except Exception as e:
            self.state.power_errors += 1
            self.state.display_power = "error"
            print("[halld] power %s failed: %s" % ("on" if on else "off", e),
                  flush=True)

    def run(self):
        while not self._stop.is_set():
            try:
                outs = sway_outputs()
            except Exception as e:
                outs = []
                if self._last_outputs != []:
                    print("[halld] cannot enumerate outputs: %s" % e, flush=True)
            names = sorted(o.get("name", "?") for o in outs)
            self.state.outputs = names

            want = self.state.merged()["want_display_on"]
            current = self.state.display_power
            hotplug = self._last_outputs is not None and names != self._last_outputs
            if hotplug:
                print("[halld] outputs changed: %s -> %s (re-asserting state)"
                      % (self._last_outputs or "none", names or "none"), flush=True)
            self._last_outputs = names

            # Reconcile against what sway REPORTS, not what we last commanded.
            # A compositor restart (the daily kiosk chromium-leak restart)
            # recreates the same output name powered ON: no hotplug edge, and
            # our own bookkeeping still says "off" — so an edge-triggered
            # governor leaves the panel lit until the next wake cycle.
            actual_on = None
            if outs:
                actual_on = any(o.get("power", o.get("dpms")) for o in outs)
            drift = actual_on is not None and actual_on != want
            if drift and not hotplug:
                print("[halld] power drift: sway reports %s, want %s "
                      "(external change — re-asserting)"
                      % ("on" if actual_on else "off", "on" if want else "off"),
                      flush=True)

            stale_claim = current in (None, "absent", "error")
            if hotplug or stale_claim or drift or (current == "on") != want:
                self._apply(want)
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
                # A panel we cannot address is NOT a healthy panel. Saying so
                # is the entire point: the previous version reported ok=True
                # while commanding zero outputs.
                healthy = m["outputs_present"] > 0 and state.power_errors == 0
                return self._json(200 if healthy else 503, {
                    "ok": healthy,
                    "display_power": m["display_power"],
                    "outputs": m["outputs"],
                    "outputs_present": m["outputs_present"],
                    "wake_active": m["wake_active"],
                    "occupancy": m["occupancy"],
                    "occupancy_luma": m["occupancy_luma"],
                    "want_display_on": m["want_display_on"],
                    "units": {n: u["reachable"] for n, u in m["units"].items()},
                    "power_errors": state.power_errors})
            if self.path == "/vox/status":
                return self._json(200, state.merged())
            if self.path == "/report":        # last accepted report + liveness
                active, rep, until = state.report_view()
                return self._json(200, {"active": active, "report": rep,
                                        "until": until if until else None})
            if self.path == "/occupancy":     # what the hall believes about the room
                m = state.merged()
                return self._json(200, {
                    "state": m["occupancy"], "luma": m["occupancy_luma"],
                    "dark_for_s": m["dark_for_s"],
                    "want_display_on": m["want_display_on"]})
            return self._static()

        def _static(self):
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

        def do_POST(self):
            if self.path != "/report":
                return self._json(404, {"ok": False, "error": "not found"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except (TypeError, ValueError):
                length = 0
            if length <= 0 or length > REPORT_MAX_BODY:
                return self._json(400, {"ok": False,
                                        "error": "missing or oversized body"})
            raw = self.rfile.read(length)          # bounded by REPORT_MAX_BODY
            try:
                doc = json.loads(raw.decode("utf-8", "ignore"))
            except ValueError:
                return self._json(400, {"ok": False, "error": "invalid JSON"})
            try:
                until, warn = state.set_report(doc)
            except ReportError as e:
                # Loud: a rejected report is a caller bug worth seeing in journald.
                print("[halld] /report REJECTED: %s" % e, flush=True)
                return self._json(400, {"ok": False, "error": str(e)})
            print("[halld] /report accepted: title=%r domain=%s until=%.0f%s"
                  % (doc.get("title"), doc.get("domain", "overview"), until,
                     (" [adjusted: " + "; ".join(warn) + "]") if warn else ""),
                  flush=True)
            return self._json(200, {"ok": True, "until": until})

    return Handler


def main():
    state = HallState()
    pollers = [UnitPoller(state, n, u) for n, u in UNITS]
    pollers.append(OccupancyPoller(state))
    for p in pollers:
        p.start()
    gov = DisplayGovernor(state)
    gov.start()
    srv = ThreadingHTTPServer((BIND, PORT), make_handler(state))
    print("[halld] units=%s http=%s:%d wake_window=%ss occupancy=%s "
          "dark_grace=%ss transform=%s" %
          ([n for n, _ in UNITS], BIND, PORT, WAKE_WINDOW_S,
           OCCUPANCY_URL or "off", DARK_GRACE_S, TRANSFORM),
          flush=True)
    try:
        srv.serve_forever()
    finally:
        gov.stop()
        for p in pollers:
            p.stop()


if __name__ == "__main__":
    main()
