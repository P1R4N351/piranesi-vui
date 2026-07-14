The voice orb: use it whenever the Piranesi assistant needs a visible presence — it is the product's entire face.

```jsx
<div style={{ width: 400, height: 400, background: "var(--surface-deep)" }}>
  <PiranesiOrb state="listening" />
</div>
```

- `state`: `waiting` (dim breath) · `listening` (verdigris, inward ripples) · `thinking` (violet, rotating lobes) · `talking` (gold, speech-envelope jitter + glyph pulse) · `working` (copper, rim comet) · `error` (terracotta tremor). Transitions morph fluidly — just swap the prop.
- Meaningful resolutions add a one-off spin flourish (rim pattern swirls once, decaying): leaving `working` for waiting/listening/talking (task done) and `thinking→talking` (answer arrived). Other transitions stay spin-free.
- `modulation`: context layer over any state — `auto` (default; dawn/day/dusk/night from local clock), `rain` (droplet rings), `storm` (gusts + flicker), `degraded` (dim amber caution), `threat` (pufferfish: dark crimson, spikes, puffed +14%, pair with all-caps text). All fluidly blended.
- `audio`: pass the mic `MediaStream` (input) or the assistant's output `<audio>` element / `AnalyserNode` — the waveform, glyph pulse and glow follow the real signal. Or a `() => 0..1` function. Omit for the built-in pseudo envelope.
- Fills its parent; parent supplies the navy background. Works at any aspect ratio or on round displays.
- `intensity` scales motion + glow; `color` overrides the mood hue; `showGlyph={false}` for a bare orb; `offsetX={-0.22}` slides the orb aside (fluidly) so text can sit beside it on wide displays — return to `0` when idle.
