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
import urllib.request

# Configure BEFORE import: fast ticks, short window, mock units, fake power.
TMP = tempfile.mkdtemp()
POWER_LOG = os.path.join(TMP, "power.log")
POWER_SH = os.path.join(TMP, "power.sh")
with open(POWER_SH, "w") as f:
    f.write("#!/bin/sh\necho \"$1\" >> %s\n" % POWER_LOG)
os.chmod(POWER_SH, 0o755)
os.environ.update({
    "HALL_VOX_UNITS": "unit-a=http://127.0.0.1:9681,unit-b=http://127.0.0.1:9682",
    "HALL_POLL_S": "0.2", "HALL_POWER_TICK_S": "0.3",
    "HALL_WAKE_WINDOW_S": "5", "HALL_POWER_CMD": POWER_SH,
    "HALL_BIND": "127.0.0.1", "HALL_PORT": "0",
})
import halld  # noqa: E402


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
        cls.gov = halld.PowerGovernor(cls.state)
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

    def test_6_both_dead_shows_error(self):
        self.va.srv.shutdown()
        self.vb.srv.shutdown()
        self.assertTrue(wait_for(
            lambda: self.api("/vox/status")["state"] == "error", 8))
        h = self.api("/health")
        self.assertFalse(any(h["units"].values()))


if __name__ == "__main__":
    unittest.main(verbosity=2)
