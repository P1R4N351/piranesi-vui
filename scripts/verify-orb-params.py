#!/usr/bin/env python3
"""verify-orb-params.py — assert orb-params.json still equals the authoritative
numbers in _ds_bundle.js (the compiled PiranesiOrb). This is the keystone that
keeps the JSX/bundle authoritative: the JSON is only a mirror, and drift between
them fails loud here. Exit 0 = equal; 1 = mismatch; 3 = environment error.

P10: bounded brace/line scans, fixed comparison set, all returns checked.
"""
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PARAMS = os.path.join(ROOT, "orb-params.json")
BUNDLE = os.path.join(ROOT, "_ds_bundle.js")
TOL = 1e-9
MAX_SCAN = 200000  # hard upper bound on brace scan characters


def extract_literal(text, marker):
    """Return the JS object/array literal following `const <marker> = `."""
    idx = text.find("const %s = " % marker)
    assert idx >= 0, "marker not found: %s" % marker
    start = idx + len("const %s = " % marker)
    open_ch = text[start]
    close_ch = "}" if open_ch == "{" else "]"
    depth = 0
    end = start
    for i in range(start, min(len(text), start + MAX_SCAN)):
        c = text[i]
        if c == open_ch:
            depth += 1
        elif c == close_ch:
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    assert depth == 0, "unbalanced literal for %s" % marker
    return text[start:end]


def js_to_json(literal):
    """Convert a numbers/strings-only JS literal to JSON and parse it."""
    quoted = re.sub(r'([{,]\s*)([A-Za-z_]\w*)\s*:', r'\1"\2":', literal)
    quoted = re.sub(r',(\s*[}\]])', r'\1', quoted)
    return json.loads(quoted)


def num_eq(a, b):
    return abs(float(a) - float(b)) <= TOL


def cmp_table(kind, want, got, errs):
    """Compare two name->dict tables of numbers."""
    if set(want) != set(got):
        errs.append("%s: key set differs %s vs %s"
                    % (kind, sorted(want), sorted(got)))
        return
    for name in want:
        wrow, grow = want[name], got[name]
        if set(wrow) != set(grow):
            errs.append("%s.%s: field set differs" % (kind, name))
            continue
        for field in wrow:
            wv, gv = wrow[field], grow[field]
            if isinstance(wv, list):
                if len(wv) != len(gv) or any(not num_eq(x, y) for x, y in zip(wv, gv)):
                    errs.append("%s.%s.%s: %s != %s" % (kind, name, field, wv, gv))
            elif not num_eq(wv, gv):
                errs.append("%s.%s.%s: %s != %s" % (kind, name, field, wv, gv))


def cmp_colors(kind, want, got, errs):
    if set(want) != set(got):
        errs.append("%s: key set differs" % kind)
        return
    for name in want:
        if want[name].upper() != got[name].upper():
            errs.append("%s.%s: %s != %s" % (kind, name, want[name], got[name]))


def cmp_list(kind, want, got, errs):
    if len(want) != len(got) or any(not num_eq(x, y) for x, y in zip(want, got)):
        errs.append("%s: %s != %s" % (kind, want, got))


def spike_from_bundle(text, errs, params):
    """Pull the spike-term constants out of the rimAt() source line."""
    m = re.search(
        r'cur\.spikes \* ([\d.]+) \* Math\.pow\(Math\.abs\(Math\.sin\('
        r'(\d+) \* a \+ spinPhase \* ([\d.]+) \+ wavePhase \* ([\d.]+)\)\), '
        r'(\d+)\) \* \(1 \+ ([\d.]+) \* \(envMul - 1\)\)', text)
    thr = re.search(r'cur\.spikes > ([\d.]+)', text)
    if not m or not thr:
        errs.append("spike: could not locate spike term in bundle")
        return
    got = {"scale": float(m.group(1)), "harmonic": float(m.group(2)),
           "spinMul": float(m.group(3)), "waveMul": float(m.group(4)),
           "power": float(m.group(5)), "envMul": float(m.group(6)),
           "threshold": float(thr.group(1))}
    want = params["spike"]
    for k in want:
        if not num_eq(want[k], got[k]):
            errs.append("spike.%s: json %s != bundle %s" % (k, want[k], got[k]))


def main():
    for path in (PARAMS, BUNDLE):
        if not os.path.isfile(path):
            sys.stderr.write("verify-orb-params: missing %s\n" % path)
            return 3
    with open(PARAMS, "r", encoding="utf-8") as fh:
        p = json.load(fh)
    with open(BUNDLE, "r", encoding="utf-8") as fh:
        b = fh.read()

    errs = []
    cmp_table("STATES", p["states"], js_to_json(extract_literal(b, "STATES")), errs)
    cmp_table("MODS", p["mods"], js_to_json(extract_literal(b, "MODS")), errs)
    cmp_colors("MOOD_FALLBACKS", p["moodFallbacks"],
               js_to_json(extract_literal(b, "MOOD_FALLBACKS")), errs)
    cmp_colors("MOD_FALLBACKS", p["modFallbacks"],
               js_to_json(extract_literal(b, "MOD_FALLBACKS")), errs)
    cmp_list("KS", p["ks"], js_to_json(extract_literal(b, "KS")), errs)
    cmp_list("WS", p["ws"], js_to_json(extract_literal(b, "WS")), errs)

    glyph = js_to_json(extract_literal(b, "GLYPH_PATHS"))
    if glyph != p["glyphPaths"]:
        errs.append("GLYPH_PATHS: %s != %s" % (p["glyphPaths"], glyph))
    center = js_to_json(extract_literal(b, "GLYPH_CENTER"))
    if not (num_eq(center["x"], p["glyphCenter"]["x"])
            and num_eq(center["y"], p["glyphCenter"]["y"])):
        errs.append("GLYPH_CENTER: %s != %s" % (p["glyphCenter"], center))

    spike_from_bundle(b, errs, p)

    # Threat tokens live in the bundle's MOD_FALLBACKS + the tokens CSS.
    if p["threatTokens"]["modThreat"].upper() != p["modFallbacks"]["threat"].upper():
        errs.append("threatTokens.modThreat != modFallbacks.threat")

    if errs:
        sys.stderr.write("verify-orb-params: MISMATCH between orb-params.json and _ds_bundle.js:\n")
        for e in errs:
            sys.stderr.write("  - %s\n" % e)
        return 1
    sys.stdout.write("verify-orb-params: orb-params.json matches _ds_bundle.js (states, mods, colors, ks/ws, glyph, spike).\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
