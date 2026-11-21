# Piranesi VUI — AtomMan tile morph (`vui-tiled`)

The VUI for **the AtomMan PC's built-in square lid display** (Minisforum AtomMan
X7 Ti, 4-inch serial-fed MCU tile panel — **no framebuffer**, so no orb).
This morph translates the House of Piranesi vocabulary into the panel's
fixed tile grammar, and is **controlled by the collective**: any household
member asserts the display over HTTP; when nothing is asserted it settles
to the mesh's ambient affect (spooler lume ethogram) — never this box's
own CPU stats.

Foundation: the proven `atomman-proto` serial work (`drive.py`, control
verified 2026-05-29) and the `paneld` device-organ conventions.
Protocol reference: github.com/RamSet/AtomMan.

## Tile grammar (what the panel actually shows)

| Panel tile | House meaning |
|---|---|
| Weather icon | **Mood glyph.** waiting=clear (day 1/night 3 by clock), listening=few clouds (5/6), thinking=mist (30), talking=scattered clouds (7/8), working=squalls (33), error=thunderstorm (11). Modulation overrides: rain=14, storm=16, degraded=haze 31, **threat=tornado 36**. |
| CPU name + meters | State label (`PIRANESI LISTENING`; threat mode: `NOT KNOWN TO THIS HOUSE`) + expressive activity meter (fixed per state, documented — not a CPU reading). |
| GPU name + meters | `mood <modulation>` + mesh health / intensity. |
| Date/Time | Real clock (the steward keeps honest time). TemprLo/TemprHi = two collective counts from the assertion (`counts:[lo,hi]`). Zone/Desc are dead fields (firmware never displays them) — carried anyway for serial sniffers. |
| MEM / DSK / NET | Activity + mesh-health derived meters (HOUSE / MESH labels). |
| VOLUME | Intensity 0–100. |
| Battery | Mesh health from lume expr (healthy 100 … critical 10). |

## Control API (`:9674`, tailnet)

- `GET /health` — `{ok, port_ok, enq, sent}` (enq/sent counting proves the
  screen is being fed).
- `GET /state` — effective state + `source: collective|ambient` + lume expr.
- `POST /state` — `{state, modulation?, caption?, counts?:[lo,hi],
  intensity?:0-100, ttl_s?:1-86400, set_by?}`. TTL-bound; expiry falls back
  to ambient. 400 on unknown state/modulation.
- `POST /clear` — drop the assertion immediately.

Ambient: polls `VUI_TILES_LUME_URL` (the household spooler's `:11434/lume`
endpoint; set it for your deployment) every
10s; expr→state map in `LUME_STATE`; lume unreachable shows as degraded.

## Deploy (AtomMan PC, Windows)

```powershell
# 1. stage:  scp vui_tiled.py <user>@<atomman-address>:C:/piranesi/vui-tiles/
# 2. venv with pyserial (reuse the proto's, or):
py -3 -m venv C:\piranesi\vui-tiles\venv
C:\piranesi\vui-tiles\venv\Scripts\pip install pyserial
# 3. stop the vendor feeder (COM3 is single-owner):
Stop-Process -Name SCCSLaunch,SCCS -Force
schtasks /change /tn "RSFT_AutoStartSCCSTask" /disable
# 4. run as a scheduled task (SYSTEM, onstart):
schtasks /create /tn "PiranesiVuiTiles" /sc onstart /ru SYSTEM /rl HIGHEST `
  /tn "PiranesiVuiTiles" /tr "C:\piranesi\vui-tiles\venv\Scripts\python.exe C:\piranesi\vui-tiles\vui_tiled.py"
schtasks /run /tn "PiranesiVuiTiles"
```

**RESTORE vendor display** (fully reversible): stop the task, then
`schtasks /change /tn "RSFT_AutoStartSCCSTask" /enable` and
`schtasks /run /tn "RSFT_AutoStartSCCSTask"` (must run in the interactive
session — `Start-Process` over SSH lands in the wrong session).

## Tests

`python3 test_vui_tiled.py` — hardware-free: a FakeSerial plays the MCU
(ENQ emitter + reply capture) under the real pump/store/API. Covers wire
format, ambient mapping, collective assertion + TTL fallback, threat
grammar, validation.
