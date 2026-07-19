#!/usr/bin/env python3
"""halld tests — two mock voxds + a fake power script; real pollers,
merger, governor and HTTP API. Linux-runnable, no hardware."""
import http.server
import json
import os
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request

# Configure BEFORE import: fast ticks, short window, mock units. Report TTLs are
# shrunk to seconds so expiry is testable without a 15s real-world floor.
TMP = tempfile.mkdtemp()
POWER_LOG = os.path.join(TMP, "power.log")
os.environ.update({
    "HALL_VOX_UNITS": "unit-a=http://127.0.0.1:9681,unit-b=http://127.0.0.1:9682",
    "HALL_POLL_S": "0.2", "HALL_POWER_TICK_S": "0.3",
    "HALL_WAKE_WINDOW_S": "5", "HALL_WAKE_RECENT_S": "5",
    "HALL_BIND": "127.0.0.1", "HALL_PORT": "0",
    "HALL_REPORT_MIN_TTL_S": "1", "HALL_REPORT_MAX_TTL_S": "3",
    "HALL_REPORT_DEFAULT_TTL_S": "2",
})
import halld  # noqa: E402

# The occupancy-aware governor talks to sway directly (it must ENUMERATE
# outputs, not just flip power), so the harness stubs the sway seam: a fake
# output table whose `power` field the governor both reads (drift detection)
# and drives, with every apply logged like the old fake power script.
FAKE_SWAY = {"outputs": [{"name": "HDMI-A-2", "active": True, "power": True,
                          "transform": "normal"}]}


def _fake_sway_outputs():
    return [dict(o) for o in FAKE_SWAY["outputs"]]


def _fake_apply_display(on, transform=None, sel=None):
    outs = FAKE_SWAY["outputs"]
    if not outs:
        return 0
    for o in outs:
        o["power"] = bool(on)
    with open(POWER_LOG, "a") as f:
        f.write(("on" if on else "off") + "\n")
    return len(outs)


halld.sway_outputs = _fake_sway_outputs
halld.apply_display = _fake_apply_display
halld.ensure_vui = lambda: None


class MockVox(threading.Thread):
    def __init__(self, port):
        super().__init__(daemon=True)
        self.port = port
        self.status = {"ok": True, "listener": "on", "playing": False,
                       "convo_active": False, "intercom": {"active": False},
                       "last_transcript_at": None, "last_reply_at": None,
                       "last_reply": None, "last_say": None}
        outer = self

        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                b = json.dumps(outer.status).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(b)))
                self.end_headers()
                self.wfile.write(b)

            def log_message(self, *a):
                pass

        self.srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), H)

    def run(self):
        self.srv.serve_forever()


def iso(t):
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(t))


def wait_for(pred, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if pred():
            return True
        time.sleep(0.05)
    return False


class HalldTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.va, cls.vb = MockVox(9681), MockVox(9682)
        cls.va.start()
        cls.vb.start()
        cls.state = halld.HallState()
        cls.pollers = [halld.UnitPoller(cls.state, n, u) for n, u in halld.UNITS]
        for p in cls.pollers:
            p.start()
        cls.gov = halld.DisplayGovernor(cls.state)
        cls.gov.start()
        srv = http.server.ThreadingHTTPServer(
            ("127.0.0.1", 0), halld.make_handler(cls.state))
        cls.port = srv.server_address[1]
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        wait_for(lambda: all(
            u["reachable"] for u in cls.state.merged()["units"].values()))

    def api(self, path):
        with urllib.request.urlopen(
                "http://127.0.0.1:%d%s" % (self.port, path), timeout=5) as r:
            return json.loads(r.read())

    def power_calls(self):
        try:
            return open(POWER_LOG).read().split()
        except FileNotFoundError:
            return []

    def post(self, path, body):
        data = json.dumps(body).encode()
        req = urllib.request.Request(
            "http://127.0.0.1:%d%s" % (self.port, path), data=data,
            method="POST", headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as ex:
            return ex.code, json.loads(ex.read())

    def test_1_idle_means_display_off(self):
        self.assertTrue(wait_for(lambda: self.power_calls()[-1:] == ["off"]))
        m = self.api("/vox/status")
        self.assertEqual(m["state"], "waiting")
        self.assertFalse(m["wake_active"])

    def test_2_wake_turns_on_and_attributes(self):
        # transcript + reply both present => exchange done, follow-up window
        # open => listening. (Transcript alone would rank "thinking".)
        now = time.time()
        self.vb.status.update(last_transcript_at=iso(now - 3),
                              last_reply_at=iso(now - 1),
                              convo_active=True)
        self.assertTrue(wait_for(lambda: self.power_calls()[-1:] == ["on"]))
        m = self.api("/vox/status")
        self.assertTrue(m["wake_active"])
        self.assertEqual(m["state"], "listening")
        self.assertEqual(m["source_unit"], "unit-b")

    def test_3_talking_outranks_listening(self):
        self.va.status.update(playing=True, last_reply="Evening, the study is lit.")
        self.assertTrue(wait_for(
            lambda: self.api("/vox/status")["state"] == "talking"))
        m = self.api("/vox/status")
        self.assertEqual(m["source_unit"], "unit-a")
        self.assertIn("study", m["caption"])
        self.va.status.update(playing=False, last_reply=None)

    def test_4_window_expiry_turns_off(self):
        self.vb.status.update(convo_active=False,
                              last_transcript_at=iso(time.time() - 10))
        self.assertTrue(wait_for(lambda: self.power_calls()[-1:] == ["off"], 8))
        self.assertFalse(self.api("/vox/status")["wake_active"])

    def test_5_intercom_forces_on(self):
        self.va.status["intercom"] = {"active": True}
        self.assertTrue(wait_for(lambda: self.power_calls()[-1:] == ["on"]))
        m = self.api("/vox/status")
        self.assertEqual(m["state"], "talking")
        self.assertEqual(m["caption"], "Intercom open.")
        self.va.status["intercom"] = {"active": False}

    def test_5b_modulation_merges_by_severity(self):
        # Contract: /vox/status.modulation in {auto,degraded,threat}. The house is
        # a single posture, merged by SEVERITY: any unit reporting threat puts the
        # whole house in threat; degraded outranks the default auto.
        self.assertEqual(self.api("/vox/status").get("modulation"), "auto")
        self.vb.status["modulation"] = "degraded"
        self.assertTrue(wait_for(
            lambda: self.api("/vox/status")["modulation"] == "degraded"))
        self.va.status["modulation"] = "threat"
        self.assertTrue(wait_for(
            lambda: self.api("/vox/status")["modulation"] == "threat"))
        self.va.status.pop("modulation", None)
        self.vb.status.pop("modulation", None)
        self.assertTrue(wait_for(
            lambda: self.api("/vox/status")["modulation"] == "auto"))

    def test_5c_external_power_on_is_reconciled(self):
        # The 2026-07-15 bug: the daily kiosk restart restarts sway, which
        # recreates the SAME output name powered ON — no hotplug edge, and the
        # governor's own bookkeeping still said "off", so an edge-triggered
        # governor left a dark empty hall lit all night. The governor must
        # reconcile against the power state sway REPORTS and re-assert off.
        self.assertTrue(wait_for(lambda: self.power_calls()[-1:] == ["off"], 8))
        n = len(self.power_calls())
        for o in FAKE_SWAY["outputs"]:
            o["power"] = True                    # sway restarted: panel back on
        self.assertTrue(wait_for(
            lambda: len(self.power_calls()) > n
            and self.power_calls()[-1] == "off"))
        self.assertFalse(FAKE_SWAY["outputs"][0]["power"])

    def test_6_both_dead_shows_error(self):
        self.va.srv.shutdown()
        self.vb.srv.shutdown()
        self.assertTrue(wait_for(
            lambda: self.api("/vox/status")["state"] == "error", 8))
        h = self.api("/health")
        self.assertFalse(any(h["units"].values()))

    # ---- control-centre report panel --------------------------------------
    # Ordered after test_6: both mock voxes are dead, so there is no wake
    # activity and the display baseline is OFF — a clean stage to prove a
    # report LIGHTS the panel purely on its own.

    def test_7_report_accepts_lights_and_echoes(self):
        # Baseline: no wake, display sleeps.
        self.assertTrue(wait_for(lambda: self.power_calls()[-1:] == ["off"], 8))
        code, body = self.post("/report", {
            "title": "Household overview", "domain": "overview",
            "spoken": "All fleets nominal.",
            "tiles": [{"label": "Siblings", "value": "17", "ok": True},
                      {"label": "Alerts", "value": "0", "ok": None},
                      {"label": "Spooler", "value": "DOWN", "ok": False}],
            "lines": ["branch-0 load 14.2", "gitea CT110 healthy"]})
        self.assertEqual(code, 200)
        self.assertTrue(body["ok"])
        self.assertGreater(body["until"], time.time())
        # An accepted report counts as wake activity: the dark, voice-silent
        # hall must LIGHT within a governor tick or two.
        self.assertTrue(wait_for(lambda: self.power_calls()[-1:] == ["on"], 4))
        # The feed the page polls carries the report alongside the orb state.
        m = self.api("/vox/status")
        self.assertTrue(m["report_active"])
        self.assertEqual(m["report"]["title"], "Household overview")
        self.assertEqual(len(m["report"]["tiles"]), 3)
        self.assertEqual(m["report"]["tiles"][2]["ok"], False)
        self.assertTrue(m["want_display_on"])
        # GET /report agrees.
        g = self.api("/report")
        self.assertTrue(g["active"])
        self.assertEqual(g["report"]["domain"], "overview")

    def test_8_report_clamp_truncate_and_reject(self):
        # ttl clamps to MAX (3s in this harness) despite asking for 999.
        code, body = self.post("/report", {"title": "Clamp me", "ttl_s": 999})
        self.assertEqual(code, 200)
        self.assertLessEqual(body["until"] - time.time(), 3.3)
        # Over-cap tiles/lines are TRUNCATED (not rejected): 12->8, 10->6.
        big = {"title": "Truncate me", "domain": "fleet",
               "tiles": [{"label": "n%d" % i, "value": str(i), "ok": None}
                         for i in range(12)],
               "lines": ["line %d" % i for i in range(10)]}
        code, body = self.post("/report", big)
        self.assertEqual(code, 200)
        self.assertTrue(wait_for(
            lambda: self.api("/vox/status").get("report", {})
            and self.api("/vox/status")["report"]["title"] == "Truncate me"))
        m = self.api("/vox/status")
        self.assertEqual(len(m["report"]["tiles"]), 8)
        self.assertEqual(len(m["report"]["lines"]), 6)
        # Malformed bodies are REJECTED with 400 (contract's four cases).
        for bad in ({"domain": "overview"},                 # missing title
                    {"title": "x" * 61},                    # overlong title
                    {"title": "T", "domain": "nope"},       # unknown domain
                    {"title": "T", "tiles": [{"label": "L", "ok": "yes"}]},  # bad ok
                    {"title": "T", "ttl_s": "soon"}):       # wrong type
            code, body = self.post("/report", bad)
            self.assertEqual(code, 400, bad)
            self.assertFalse(body["ok"])
            self.assertIn("error", body)

    def test_9_report_expiry_flips_and_sleeps(self):
        # Short-lived report; after it lapses, GET /report.active flips false,
        # the feed drops the panel, and (no other wake) the panel sleeps again.
        code, body = self.post("/report", {"title": "Ephemeral", "ttl_s": 1})
        self.assertEqual(code, 200)
        self.assertTrue(wait_for(lambda: self.api("/report")["active"], 3))
        self.assertTrue(wait_for(
            lambda: not self.api("/report")["active"], 5))
        m = self.api("/vox/status")
        self.assertFalse(m["report_active"])
        self.assertIsNone(m["report"])
        # GET /report still RETAINS the last accepted report body, only inactive.
        self.assertEqual(self.api("/report")["report"]["title"], "Ephemeral")
        # With the report gone and voices dead, the hall sleeps.
        self.assertTrue(wait_for(lambda: self.power_calls()[-1:] == ["off"], 6))


if __name__ == "__main__":
    unittest.main(verbosity=2)
