#!/usr/bin/env python3
"""vui-tiled — Piranesi VUI morph for the AtomMan X7 Ti lid display.

The atom-pc lid screen is a 4-inch serial-fed MCU tile panel (COM3, 115200,
ENQ -> tile-reply; see README). It has NO framebuffer, so this morph
translates the House of Piranesi VUI vocabulary into the panel's fixed
tiles: the weather icon becomes the mood glyph (threat = tornado), the CPU
tile's name string carries the state label, TemprLo/TemprHi carry two
collective counts, and BAT reflects mesh health.

COLLECTIVE-CONTROLLED: any household member POSTs /state to set the display
(with a TTL); when nothing is asserted, the panel falls back to the mesh's
ambient affect polled from the spooler /lume endpoint — it reflects the
collective, never just this box's own CPU.

FOUNDATION: builds directly on the proven household groundwork —
  * atomman-proto (atom-pc C:/Users/Gary/atomman-proto, verified 2026-05-29):
    the ENQ/tile serial protocol, frame builder, fixed (id,seq) rotation and
    the stop-SCCS / RSFT_AutoStartSCCSTask restore procedure are lifted from
    drive.py unchanged.
  * paneld (workspace infra/internode-panel): the device-panel organ
    conventions — single-file stdlib daemon, sampler/cache threads, bounded
    loops, CORS, Nice'd service — and the lume ethogram as the household's
    ambient affect (spooler GET /lume -> {expr: boot|healthy|active|degraded|
    critical|lanes|override, reason, ...}).

stdlib + pyserial. Runs on Windows (production) and Linux (tests, with an
injected fake serial). One file by design — scp-able, no packaging.
"""
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# ---------------------------------------------------------------- config
PORT_SERIAL = os.environ.get("VUI_TILES_COM", "COM3")
BAUD = 115200
HTTP_BIND = os.environ.get("VUI_TILES_BIND", "0.0.0.0")
HTTP_PORT = int(os.environ.get("VUI_TILES_PORT", "9674"))
# Collective ambient = the household workhorse's lume organ (internode-0
# internode spooler :11434 — the ONE lume owner on that box). atom-pc is on
# the tailnet, so MagicDNS resolves. Override for a different affect source.
LUME_URL = os.environ.get(
    "VUI_TILES_LUME_URL",
    "http://piranesi-internode-0.tail8d99b6.ts.net:11434/lume")
LUME_POLL_S = float(os.environ.get("VUI_TILES_LUME_POLL_S", "10"))
DEFAULT_TTL_S = float(os.environ.get("VUI_TILES_DEFAULT_TTL_S", "120"))
NIGHT_FROM, NIGHT_TO = 20, 7  # local hours using night icon variants

TRAILER = b"\xcc\x33\xc3\x3c"
ENQ_HEAD = b"\xaa\x05"

STATES = ("waiting", "listening", "thinking", "talking", "working", "error")
MODS = ("none", "auto", "dawn", "day", "dusk", "night", "rain", "storm",
        "degraded", "threat")

# Weather icon codes (RamSet/AtomMan): mood glyph per state; modulation wins.
ICON_DAY = {"waiting": 1, "listening": 5, "thinking": 30, "talking": 7,
            "working": 33, "error": 11}
ICON_NIGHT = {"waiting": 3, "listening": 6, "thinking": 30, "talking": 8,
              "working": 33, "error": 11}
ICON_MOD = {"rain": 14, "storm": 16, "degraded": 31, "threat": 36}

# Expressive activity meter per state (documented, not a real CPU reading).
ACTIVITY = {"waiting": 5, "listening": 35, "thinking": 80, "talking": 60,
            "working": 95, "error": 15}

LUME_STATE = {  # ambient mesh affect -> (state, modulation)
    "boot": ("waiting", "auto"), "healthy": ("waiting", "auto"),
    "lanes": ("waiting", "auto"),      # per-lane summary mode = nominal
    "active": ("working", "auto"), "override": ("working", "auto"),
    "degraded": ("waiting", "degraded"), "critical": ("error", "auto"),
}
LUME_HEALTH = {"boot": 60, "healthy": 100, "lanes": 100, "active": 85,
               "override": 85, "degraded": 40, "critical": 10}


class StateStore:
    """Collective assertion (TTL-bound) over an ambient floor."""

    def __init__(self):
        self._lock = threading.Lock()
        self._asserted = None      # dict or None
        self._ambient = ("waiting", "auto")
        self._lume_expr = "boot"
        self._lume_reason = ""
        self._started = time.time()

    def assert_state(self, body, client):
        state = body.get("state", "waiting")
        mod = body.get("modulation", "auto")
        if state not in STATES:
            raise ValueError("state must be one of %s" % (STATES,))
        if mod not in MODS:
            raise ValueError("modulation must be one of %s" % (MODS,))
        ttl = float(body.get("ttl_s", DEFAULT_TTL_S))
        ttl = max(1.0, min(ttl, 86400.0))
        with self._lock:
            self._asserted = {
                "state": state, "modulation": mod,
                "caption": str(body.get("caption", ""))[:200],
                "counts": [int(x) for x in (body.get("counts") or [0, 0])[:2]],
                "intensity": max(0, min(100, int(body.get("intensity", 50)))),
                "set_by": str(body.get("set_by", client))[:80],
                "set_at": time.time(), "ttl_s": ttl,
            }

    def clear(self):
        with self._lock:
            self._asserted = None

    def set_ambient(self, expr, reason=""):
        with self._lock:
            self._lume_expr = expr
            self._lume_reason = reason
            self._ambient = LUME_STATE.get(expr, ("waiting", "auto"))

    def effective(self):
        with self._lock:
            a = self._asserted
            if a and time.time() - a["set_at"] > a["ttl_s"]:
                self._asserted = a = None
            if a:
                return dict(a, source="collective", lume=self._lume_expr)
            st, mod = self._ambient
            return {"state": st, "modulation": mod, "caption": "",
                    "counts": [0, 0], "intensity": 30, "set_by": "",
                    "source": "ambient", "lume": self._lume_expr,
                    "lume_reason": self._lume_reason}

    def snapshot(self):
        eff = self.effective()
        eff["uptime_s"] = round(time.time() - self._started, 1)
        return eff


def _is_night():
    h = time.localtime().tm_hour
    return h >= NIGHT_FROM or h < NIGHT_TO


def icon_for(state, mod):
    if mod in ICON_MOD:
        return ICON_MOD[mod]
    if mod == "night":
        return ICON_NIGHT[state]
    if mod in ("dawn", "day", "dusk"):
        return ICON_DAY[state]
    return (ICON_NIGHT if _is_night() else ICON_DAY)[state]


# ------------------------------------------------------------- tile builders
def tiles_for(eff):
    """Return the (id, seq, payload) rotation for the effective state."""
    now = time.localtime()
    label = ("PIRANESI " + eff["state"]).upper()
    if eff["modulation"] == "threat":
        label = "NOT KNOWN TO THIS HOUSE"
    act = ACTIVITY[eff["state"]]
    lo, hi = (eff["counts"] + [0, 0])[:2]
    health = LUME_HEALTH.get(eff["lume"], 60)
    dat = ("{Date:%s;Time:%s;Week:%d;Weather:%d;TemprLo:%d,TemprHi:%d,"
           "Zone:PIRANESI,Desc:%s}") % (
        time.strftime("%Y/%m/%d", now), time.strftime("%H:%M:%S", now),
        now.tm_wday if now.tm_wday != 6 else 0,  # panel weeks: 0=Sunday
        icon_for(eff["state"], eff["modulation"]), lo, hi,
        eff["caption"][:60] or eff["state"])  # Desc is a dead field; carried anyway
    return [
        (0x53, 0x32, "{CPU:%s;Tempr:%d;Useage:%d;Freq:3800000;Tempr1:%d;}"
         % (label[:24], act, act, act)),
        (0x36, 0x33, "{GPU:%s;Tempr:%d;Useage:%d;}"
         % (("mood " + eff["modulation"])[:24], health, eff["intensity"])),
        (0x49, 0x34, "{Memory:HOUSE;Used:%d;Available:%d;Total:100;Useage:%d;}"
         % (act, 100 - act, act)),
        (0x4f, 0x35, "{DiskName:MESH;Tempr:%d;UsageSpace:%d;AllSpace:100;Usage:%d;}"
         % (health, 100 - health, 100 - health)),
        (0x6b, 0x36, dat),
        (0x27, 0x37, "{SPEED:%d;NETWORK:%d,%d;}" % (act * 20, lo, hi)),
        (0x10, 0x39, "{VOLUME:%d;}" % eff["intensity"]),
        (0x1a, 0x3c, "{Battery:%d;}" % health),
    ]


def build_frame(idb, seqb, txt):
    return bytes([0xAA, idb, 0x00, seqb]) + txt.encode("latin-1", "ignore") + TRAILER


# ------------------------------------------------------------- serial pump
class SerialPump(threading.Thread):
    """Answer every device ENQ with the next tile for the effective state.

    Reopens the port on failure (bounded backoff) — SCCS-restart or USB
    re-enumeration must not kill the daemon.
    """

    def __init__(self, store, serial_factory):
        super().__init__(daemon=True)
        self.store = store
        self.serial_factory = serial_factory
        self.enq = 0
        self.sent = 0
        self.port_ok = False
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def run(self):
        buf = bytearray()
        idx = 0
        ser = None
        while not self._stop.is_set():
            if ser is None:
                try:
                    ser = self.serial_factory()
                    self.port_ok = True
                    buf.clear()
                except Exception as e:
                    self.port_ok = False
                    print("[vui-tiled] serial open failed: %s (retry 5s)" % e,
                          flush=True)
                    self._stop.wait(5)
                    continue
            try:
                d = ser.read(64)
                if d:
                    buf += d
                while TRAILER in buf:
                    cut = buf.index(TRAILER) + 4
                    fr = bytes(buf[:cut])
                    del buf[:cut]
                    if fr[:2] == ENQ_HEAD:
                        self.enq += 1
                        rot = tiles_for(self.store.effective())
                        idb, seqb, payload = rot[idx % len(rot)]
                        idx += 1
                        ser.write(build_frame(idb, seqb, payload))
                        self.sent += 1
            except Exception as e:
                print("[vui-tiled] serial error: %s (reopening)" % e, flush=True)
                try:
                    ser.close()
                except Exception:
                    pass
                ser = None
                self.port_ok = False
        if ser is not None:
            try:
                ser.close()
            except Exception:
                pass


# ------------------------------------------------------------- ambient poll
class LumePoller(threading.Thread):
    def __init__(self, store):
        super().__init__(daemon=True)
        self.store = store
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def run(self):
        import urllib.request
        while not self._stop.is_set():
            try:
                with urllib.request.urlopen(LUME_URL, timeout=5) as r:
                    j = json.loads(r.read(8192).decode("utf-8", "ignore"))
                expr = j.get("expr") or j.get("expression") or "healthy"
                self.store.set_ambient(str(expr), str(j.get("reason") or ""))
            except Exception:
                self.store.set_ambient("degraded", "lume unreachable")
            self._stop.wait(LUME_POLL_S)


# ------------------------------------------------------------------ HTTP API
def make_handler(store, pump):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            print("%s %s" % (self.address_string(), fmt % args), flush=True)

        def _json(self, code, obj):
            b = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

        def do_GET(self):
            if self.path == "/health":
                self._json(200, {"ok": True, "port_ok": pump.port_ok,
                                 "enq": pump.enq, "sent": pump.sent})
            elif self.path == "/state":
                self._json(200, store.snapshot())
            else:
                self._json(200, {"service": "vui-tiled",
                                 "endpoints": ["/health", "/state",
                                               "POST /state", "POST /clear"]})

        def do_POST(self):
            n = min(int(self.headers.get("Content-Length", 0) or 0), 65536)
            try:
                body = json.loads(self.rfile.read(n) or b"{}")
            except Exception:
                return self._json(400, {"error": "bad json"})
            if self.path == "/state":
                try:
                    store.assert_state(body, self.client_address[0])
                except ValueError as e:
                    return self._json(400, {"error": str(e)})
                return self._json(200, store.snapshot())
            if self.path == "/clear":
                store.clear()
                return self._json(200, store.snapshot())
            self._json(404, {"error": "unknown endpoint"})

    return Handler


def real_serial():
    import serial  # pyserial
    return serial.Serial(PORT_SERIAL, BAUD, timeout=0.3, write_timeout=1.0)


def main(serial_factory=real_serial):
    store = StateStore()
    pump = SerialPump(store, serial_factory)
    lume = LumePoller(store)
    pump.start()
    lume.start()
    srv = ThreadingHTTPServer((HTTP_BIND, HTTP_PORT), make_handler(store, pump))
    print("[vui-tiled] serial=%s http=%s:%d lume=%s" %
          (PORT_SERIAL, HTTP_BIND, HTTP_PORT, LUME_URL), flush=True)
    try:
        srv.serve_forever()
    finally:
        pump.stop()
        lume.stop()


if __name__ == "__main__":
    main()
