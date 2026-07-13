#!/usr/bin/env python3
"""test_ds_sync — repo test hook wiring the derivation guards into unittest, so a
normal test run fails loud if a derived surface drifts from the canonical source.

Covers the two in-repo, host-independent guards:
  - orb-params.json still equals _ds_bundle.js (JSX/bundle stays authoritative)
  - every in-repo vendored web bundle is byte-identical to canonical

The cross-repo Android Kotlin check (scripts/sync-android-orb.sh --check) lives in
verify-all.sh because it needs the astroclaw checkout, which is host-dependent.
"""
import os
import subprocess
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class DsSyncTest(unittest.TestCase):
    def test_orb_params_matches_bundle(self):
        r = subprocess.run(
            ["python3", os.path.join(ROOT, "scripts", "verify-orb-params.py")],
            capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_vendored_bundles_in_sync(self):
        r = subprocess.run(
            ["bash", os.path.join(ROOT, "scripts", "verify-ds-sync.sh")],
            capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
