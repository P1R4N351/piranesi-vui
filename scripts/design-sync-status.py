#!/usr/bin/env python3
"""Validate .design-sync/last-run.json and emit "<status>\\t<detail>" on stdout.

The design-sync PULL agent's ONLY report channel (runbook step 6). The shell
(scripts/design-sync-pull.sh) owns the ntfy and reads this; an unparseable or
out-of-schema file must NOT be silently read as success, so anything that is not
a valid verdict exits non-zero with no stdout and the shell alerts "no verdict".

Exit: 0 valid (stdout "<status>\\t<detail>"), 2 invalid/unreadable, 3 bad usage.

P10 RELAXATIONS: Rule 5's assert/raise density is deliberately NOT met. This
parser is fail-closed by RETURN VALUE (None -> exit 2) precisely so a malformed
verdict can never propagate as an exception the shell might mask; raising here
would move the failure decision out of the caller. No loops, no recursion, no
dynamic import, every function under 60 lines.
"""
import json
import sys

VALID = ("ok-noop", "ok-changed", "noauth", "error")
MAX_BYTES = 65536
MAX_DETAIL = 400


def load(path):
    """Return the decoded dict, or None if unreadable/oversized/not an object."""
    try:
        with open(path, "rb") as fh:
            raw = fh.read(MAX_BYTES + 1)
    except OSError:
        return None
    if len(raw) > MAX_BYTES or not raw.strip():
        return None
    try:
        obj = json.loads(raw.decode("utf-8", "strict"))
    except (ValueError, UnicodeDecodeError):
        return None
    return obj if isinstance(obj, dict) else None


def verdict(obj):
    """Return (status, detail) if the object is a valid verdict, else None."""
    if obj.get("schema") != 1:
        return None
    status = obj.get("status")
    if not isinstance(status, str) or status not in VALID:
        return None
    detail = obj.get("detail", "")
    if not isinstance(detail, str):
        return None
    detail = " ".join(detail.split())[:MAX_DETAIL]
    return status, (detail or "no detail given")


def main(argv):
    if len(argv) != 2:
        sys.stderr.write("usage: design-sync-status.py <last-run.json>\n")
        return 3
    obj = load(argv[1])
    if obj is None:
        return 2
    got = verdict(obj)
    if got is None:
        return 2
    sys.stdout.write("%s\t%s\n" % got)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
