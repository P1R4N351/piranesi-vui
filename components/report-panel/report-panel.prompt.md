The control-centre report panel: use it whenever the voice organ delivers a **status report** that benefits from a graphic alongside the spoken words — a fleet sweep, a services roll-call, an alerts digest. It renders ALONGSIDE the `PiranesiOrb` (orb shifts/scales aside; panel docks right on landscape, bottom on portrait), never replacing it.

```jsonc
// voxd POSTs this to halld /report; the panel appears within ~2s and self-dismisses at ttl.
{
  "title": "Spooler fleet degraded",     // <=60, required
  "domain": "alerts",                    // overview|fleet|services|spoolers|alerts|advisories|sessions
  "spoken": "Two spoolers are warning.", // <=300, the TTS track (not drawn)
  "tiles": [                             // <=8 stat tiles
    { "label": "Nodes up", "value": "16/17", "ok": true  },
    { "label": "Spoolers", "value": "2 warn", "ok": false },
    { "label": "Queue",    "value": "—",      "ok": null  }
  ],
  "lines": ["internode-0 spooler starved", "branch-1 at RAM ceiling"], // <=6 advisory rows
  "ttl_s": 90                            // clamped 15..600, default 90
}
```

- **Header**: `title` in the display serif, a small-caps `domain` label, and a receipt timestamp (`at`, server-stamped).
- **Tiles**: label small-caps/muted, value large. `ok: true` -> bronze/healthy accent; `ok: false` -> terracotta alert accent (`--mood-error`); `ok: null` -> neutral. Up to 8; a 9th+ is truncated, not rejected.
- **Lines**: up to 6 advisory rows, bronze bullet + body text. Over-cap rows are truncated.
- **Motion**: subtle slide-and-settle entrance (`--dur-state`/`--ease-swell`), fade-out on expiry — consistent with `tokens/motion.css`. No external fonts or CDNs; styled entirely from the DS tokens.
- **Lifecycle**: the panel is driven off halld's merged `/vox/status` feed (`report_active` + `report` + `report_until`) that the page already polls, so it needs no second connection. An accepted report also counts as display-wake activity — the panel lights even if the screen was asleep.
- Colors come from the DS mood/context tokens (`tokens/colors.css`), never hard-coded hexes; the panel reads correctly against the bronze-on-navy surface at any aspect ratio.
