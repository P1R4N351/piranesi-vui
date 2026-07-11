#!/usr/bin/env python3
"""Tests for vui_tiled — no hardware, no pyserial: a FakeSerial plays the
lid screen (emits ENQ frames, captures tile replies) while the real
SerialPump, StateStore and HTTP API run in-process. Linux-runnable.
"""
import json
import threading
import time
import unittest
import urllib.request
from http.server import ThreadingHTTPServer

import vui_tiled as vt


class FakeSerial:
    """Plays the MCU: hands out one ENQ per read(), records replies."""

    def __init__(self):
        self.writes = []
        self._seq = 0
        self._lock = threading.Lock()

    def read(self, n):
        time.sleep(0.01)
        self._seq += 1
        return vt.ENQ_HEAD + str(self._seq % 10).encode() + vt.TRAILER

    def write(self, b):
        with self._lock:
            self.writes.append(bytes(b))

    def close(self):
        pass

    def frames(self):
        with self._lock:
            return list(self.writes)


def payload_of(frame):
    assert frame[0] == 0xAA and frame.endswith(vt.TRAILER)
    return frame[1], frame[4:-4].decode("latin-1")


def wait_for(pred, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if pred():
            return True
        time.sleep(0.05)
    return False


class VuiTiledTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = vt.StateStore()
        cls.fake = FakeSerial()
        cls.pump = vt.SerialPump(cls.store, lambda: cls.fake)
        cls.pump.start()
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0),
                                      vt.make_handler(cls.store, cls.pump))
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.pump.stop()
        cls.srv.shutdown()

    def api(self, method, path, body=None):
        req = urllib.request.Request(
            "http://127.0.0.1:%d%s" % (self.port, path),
            data=json.dumps(body).encode() if body is not None else None,
            method=method, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.loads(r.read())

    def drain_and_collect(self, min_frames=10):
        start = len(self.fake.frames())
        self.assertTrue(
            wait_for(lambda: len(self.fake.frames()) >= start + min_frames),
            "pump did not answer ENQs")
        return [payload_of(f) for f in self.fake.frames()[start:]]

    def find_tile(self, frames, tile_id):
        for tid, payload in reversed(frames):
            if tid == tile_id:
                return payload
        self.fail("tile 0x%02x never sent" % tile_id)

    def test_1_ambient_waiting(self):
        frames = self.drain_and_collect(16)
        dat = self.find_tile(frames, 0x6B)
        self.assertRegex(dat, r"Weather:(1|3);")   # clear day/night = waiting
        cpu = self.find_tile(frames, 0x53)
        self.assertIn("CPU:PIRANESI WAITING", cpu)

    def test_2_collective_threat(self):
        snap = self.api("POST", "/state",
                        {"state": "working", "modulation": "threat",
                         "counts": [7, 12], "intensity": 90,
                         "set_by": "hades-drill", "ttl_s": 60})
        self.assertEqual(snap["source"], "collective")
        frames = self.drain_and_collect(16)
        dat = self.find_tile(frames, 0x6B)
        self.assertIn("Weather:36", dat)           # tornado = pufferfish
        self.assertIn("TemprLo:7,TemprHi:12", dat)
        self.assertIn("NOT KNOWN TO THIS HOUSE", self.find_tile(frames, 0x53))
        self.assertIn("mood threat", self.find_tile(frames, 0x36))
        self.assertIn("VOLUME:90", self.find_tile(frames, 0x10))

    def test_3_ttl_expiry_falls_back(self):
        self.api("POST", "/state", {"state": "talking", "ttl_s": 1})
        self.assertTrue(wait_for(
            lambda: self.api("GET", "/state")["source"] == "ambient", 5))
        frames = self.drain_and_collect(16)
        self.assertIn("CPU:PIRANESI WAITING", self.find_tile(frames, 0x53))

    def test_4_ambient_critical_maps_to_error(self):
        self.store.set_ambient("critical", "gpu 93C")
        frames = self.drain_and_collect(16)
        dat = self.find_tile(frames, 0x6B)
        self.assertIn("Weather:11", dat)           # thunderstorm = error
        self.assertIn("Battery:10", self.find_tile(frames, 0x1A))
        snap = self.api("GET", "/state")
        self.assertEqual(snap["lume_reason"], "gpu 93C")
        self.store.set_ambient("healthy")

    def test_5_validation_and_health(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self.api("POST", "/state", {"state": "belligerent"})
        self.assertEqual(cm.exception.code, 400)
        h = self.api("GET", "/health")
        self.assertTrue(h["ok"] and h["port_ok"] and h["enq"] > 0)

    def test_6_wire_format(self):
        for f in self.fake.frames()[-8:]:
            self.assertEqual(f[0], 0xAA)
            self.assertEqual(f[2], 0x00)
            self.assertTrue(f.endswith(vt.TRAILER))
            f[4:-4].decode("latin-1")  # payload must be latin-1 clean


if __name__ == "__main__":
    unittest.main(verbosity=2)
