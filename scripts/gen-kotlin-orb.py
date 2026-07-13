#!/usr/bin/env python3
"""gen-kotlin-orb.py — emit the native Android orb's data tables from the
canonical orb-params.json, so the Kotlin orb provably DERIVES from the same
source as the web orb instead of hand-copying its numbers.

Usage:
  gen-kotlin-orb.py                 # print generated Kotlin to stdout
  gen-kotlin-orb.py --out FILE      # write generated Kotlin to FILE
  gen-kotlin-orb.py --check FILE    # exit 1 (loud) if FILE != freshly generated

The generated file is a mechanical projection of orb-params.json. Never edit it
by hand; edit the JSON (verified against _ds_bundle.js by verify-orb-params.py)
and regenerate.

P10: fixed table shapes, bounded loops, every I/O return value checked.
"""
import argparse
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PARAMS = os.path.join(ROOT, "orb-params.json")
MAX_ROWS = 32  # generous upper bound on states/mods/colors


def kf(x):
    """Format a JSON number as a Kotlin Float literal."""
    f = float(x)
    if f == int(f):
        return "%df" % int(f)
    return repr(f) + "f"


def hex_triple(hexstr):
    """'#8F8168' -> 'Triple(0x8F / 255f, 0x81 / 255f, 0x68 / 255f)'."""
    h = hexstr.strip().lstrip("#")
    assert len(h) == 6, "expected 6-digit hex, got %r" % hexstr
    r, g, b = h[0:2], h[2:4], h[4:6]
    return "Triple(0x%s / 255f, 0x%s / 255f, 0x%s / 255f)" % (
        r.upper(), g.upper(), b.upper())


def gen_glyph(polylines):
    lines = []
    assert len(polylines) <= MAX_ROWS
    for seg in polylines:
        pts = ", ".join("%sf to %sf" % (kf(p[0])[:-1], kf(p[1])[:-1]) for p in seg)
        lines.append("    listOf(%s)," % pts)
    return "\n".join(lines)


def gen_color_map(colors):
    lines = []
    assert len(colors) <= MAX_ROWS
    for name, hexv in colors.items():
        lines.append('    "%s" to %s,' % (name, hex_triple(hexv)))
    return "\n".join(lines)


def gen_states(states, keys):
    lines = []
    assert len(states) <= MAX_ROWS
    for name, s in states.items():
        amps = ", ".join(kf(a) for a in s["amps"])
        parts = ["%s = %s" % (k, kf(s[k])) for k in keys]
        body = "amps = floatArrayOf(%s), %s" % (amps, ", ".join(parts))
        lines.append('    "%s" to State(%s),' % (name, body))
    return "\n".join(lines)


def gen_mods(mods, keys):
    lines = []
    assert len(mods) <= MAX_ROWS
    for name, m in mods.items():
        parts = ["%s = %s" % (k, kf(m[k])) for k in keys]
        lines.append('    "%s" to Mod(%s),' % (name, ", ".join(parts)))
    return "\n".join(lines)


def render(p):
    sp = p["spike"]
    return TEMPLATE % {
        "ks": ", ".join(kf(x) for x in p["ks"]),
        "ws": ", ".join(kf(x) for x in p["ws"]),
        "glyph_cx": kf(p["glyphCenter"]["x"]),
        "glyph_cy": kf(p["glyphCenter"]["y"]),
        "glyph_viewbox": kf(p["glyphViewBox"]),
        "glyph_stroke": kf(p["glyphStrokeWidth"]),
        "glyph": gen_glyph(p["glyphPolylines"]),
        "radius_frac": kf(p["radiusFrac"]),
        "lerp_tau": kf(p["lerpTau"]),
        "audio_tau": kf(p["audioTau"]),
        "env_drive": kf(p["envDriveScale"]),
        "gust_scale": kf(p["gustScale"]),
        "flicker_scale": kf(p["flickerScale"]),
        "spike_harmonic": kf(sp["harmonic"]),
        "spike_power": int(sp["power"]),
        "spike_scale": kf(sp["scale"]),
        "spike_spin": kf(sp["spinMul"]),
        "spike_wave": kf(sp["waveMul"]),
        "spike_env": kf(sp["envMul"]),
        "spike_thresh": kf(sp["threshold"]),
        "threat_text": p["threatTokens"]["threatText"],
        "threat_surface": p["threatTokens"]["threatSurface"],
        "threat_copy": p["threatCopy"],
        "mood": gen_color_map(p["moodFallbacks"]),
        "mod_color": gen_color_map(p["modFallbacks"]),
        "states": gen_states(p["states"], p["stateKeys"]),
        "mods": gen_mods(p["mods"], p["modKeys"]),
    }


TEMPLATE = '''// GENERATED FILE — DO NOT EDIT BY HAND.
// Source of truth: piranesi-vui/orb-params.json (mirror of components/orb/PiranesiOrb.jsx).
// Regenerate: python3 scripts/gen-kotlin-orb.py --out <path-to-this-file>
// Verify:     python3 scripts/gen-kotlin-orb.py --check <path-to-this-file>
// The web orb (_ds_bundle.js) and this native orb therefore share ONE upstream.
package ai.astroclaw.app.ui

/** Data tables for [PiranesiOrb], mechanically generated from orb-params.json. */
internal object OrbTables {
  class State(
    val glow: Float,
    val alpha: Float,
    val breathAmp: Float,
    val breathHz: Float,
    val amps: FloatArray,
    val spin: Float,
    val ripple: Float,
    val comet: Float,
    val envelope: Float,
    val audioW: Float,
    val glyphBase: Float,
    val glyphPulse: Float,
    val speed: Float,
  )

  class Mod(
    val w: Float,
    val ampMul: Float,
    val speedMul: Float,
    val glowMul: Float,
    val alphaMul: Float,
    val radiusMul: Float,
    val spikes: Float,
    val drops: Float,
    val flicker: Float,
    val gust: Float,
  )

  val KS = floatArrayOf(%(ks)s)
  val WS = floatArrayOf(%(ws)s)

  const val GLYPH_CX = %(glyph_cx)s
  const val GLYPH_CY = %(glyph_cy)s
  const val GLYPH_VIEWBOX = %(glyph_viewbox)s
  const val GLYPH_STROKE = %(glyph_stroke)s
  val GLYPH: List<List<Pair<Float, Float>>> = listOf(
%(glyph)s
  )

  const val RADIUS_FRAC = %(radius_frac)s
  const val LERP_TAU = %(lerp_tau)s
  const val AUDIO_TAU = %(audio_tau)s
  const val ENV_DRIVE_SCALE = %(env_drive)s
  const val GUST_SCALE = %(gust_scale)s
  const val FLICKER_SCALE = %(flicker_scale)s

  const val SPIKE_HARMONIC = %(spike_harmonic)s
  const val SPIKE_POWER = %(spike_power)d
  const val SPIKE_SCALE = %(spike_scale)s
  const val SPIKE_SPIN_MUL = %(spike_spin)s
  const val SPIKE_WAVE_MUL = %(spike_wave)s
  const val SPIKE_ENV_MUL = %(spike_env)s
  const val SPIKE_THRESHOLD = %(spike_thresh)s

  const val THREAT_TEXT = "%(threat_text)s"
  const val THREAT_SURFACE = "%(threat_surface)s"
  const val THREAT_COPY = "%(threat_copy)s"

  /** Mood hues — patinas of bronze, keyed by conversational state. */
  val MOOD: Map<String, Triple<Float, Float, Float>> = mapOf(
%(mood)s
  )

  /** Context-modulation tints, keyed by modulation name. */
  val MOD_COLOR: Map<String, Triple<Float, Float, Float>> = mapOf(
%(mod_color)s
  )

  /** Per-state motion signatures. */
  val STATES: Map<String, State> = mapOf(
%(states)s
  )

  /** Context modulations layered over any state. */
  val MODS: Map<String, Mod> = mapOf(
%(mods)s
  )
}
'''


def load_params():
    if not os.path.isfile(PARAMS):
        sys.stderr.write("gen-kotlin-orb: params not found: %s\n" % PARAMS)
        sys.exit(3)
    with open(PARAMS, "r", encoding="utf-8") as fh:
        return json.load(fh)


def main(argv):
    ap = argparse.ArgumentParser(description="Generate Kotlin orb tables.")
    ap.add_argument("--out", help="write generated Kotlin to this path")
    ap.add_argument("--check", help="fail if this file differs from generated")
    args = ap.parse_args(argv)

    text = render(load_params())

    if args.check:
        if not os.path.isfile(args.check):
            sys.stderr.write("gen-kotlin-orb: --check target absent: %s\n" % args.check)
            return 1
        with open(args.check, "r", encoding="utf-8") as fh:
            have = fh.read()
        if have != text:
            sys.stderr.write(
                "gen-kotlin-orb: DRIFT — %s is not what orb-params.json generates.\n"
                "  Regenerate: python3 scripts/gen-kotlin-orb.py --out %s\n"
                % (args.check, args.check))
            return 1
        sys.stdout.write("gen-kotlin-orb: %s is in sync with orb-params.json.\n" % args.check)
        return 0

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
        sys.stdout.write("gen-kotlin-orb: wrote %s\n" % args.out)
        return 0

    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
