# Piranesi VUI — Design System

**House of Piranesi** is a voice user interface: an ambient assistant whose entire visible presence is a single fluid orb — a jiggly, breathing, pulsating circle carrying the brand's columned-house glyph. It runs full-screen on dedicated displays of any shape: landscape, portrait, square, or round.

This is a **greenfield** system. Sources provided:
- GitHub repo: https://github.com/P1R4N351/piranesi-vui — *empty at build time (no commits)*; kept as the intended home of the product code. Check it again before major work: real code there supersedes this system's inventions.
- Brand SVGs (uploaded): `assets/glyph.svg` (bare columned-house glyph), `assets/mark-circle.svg` (roundel on navy).
- Brief: bronze on dark navy; hue/shade varies with mood/context; fluid animations with a unique signature per state (waiting, listening, thinking, talking, working, error).

## Content fundamentals

Almost no copy exists on screen — the product speaks. When text appears:
- **Captions** are one short sentence, present tense, no exclamation marks: "Setting the study lights to evening." "I did not catch that."
- **State labels** are single lowercase words rendered in small caps: `listening`, `thinking`.
- The assistant says "I"; addresses the user as "you". Courteous, unhurried, slightly formal — a house steward, not a chatbot. No emoji, ever.
- **Threat-mode copy**: terse, imperative, ALL-CAPS via CSS — "YOU ARE NOT KNOWN TO THIS HOUSE." The steward turns sentinel; still no exclamation marks.
- Domestic-classical vocabulary fits the brand: study, gallery, curtains, evening.

## Visual foundations

- **Palette**: dark navy surfaces (`--navy-950…500`, brand `--navy-700 #16294d`) with bronze accents (`--bronze-200…800`, brand `--bronze-500 #C39C72`). Backgrounds are radial navy gradients (lighter navy behind the orb, falling to near-black at edges) — never flat white, never imagery.
- **Mood hues**: the orb (and any state-tinted UI) shifts hue by state — waiting = dim bronze, listening = verdigris, thinking = muted violet, talking = lit gold, working = copper, error = terracotta. All chosen as patinas of bronze so crossfades feel material, not rainbow. Tokens: `--mood-*`.
- **Context modulations**: a second axis layered over any mood (`--mod-*` tokens). `auto` follows the local clock (dawn/day/dusk/night); `rain`/`storm` bring washed blues, droplet rings, gusts and flicker; `degraded` dims to amber caution; `threat` is pufferfish mode — dark crimson (`--mod-threat`), spiked rim, puffed +14%, crimson edge vignette, and ALL-CAPS bold text in `--threat-text`. Everything blends fluidly, entering and leaving.
- **Audio reactivity**: the orb's waveform follows real audio when given it — mic input while listening, speaker output while talking. Auto-gain normalizes the level; without a source, talking uses a pseudo speech envelope.
- **Type**: Cormorant Garamond (display, classical serif) for names/headlines; Verdana (system) for captions/UI; IBM Plex Mono for technical labels. Small-caps tracking `0.18em` is the signature label treatment. *Cormorant Garamond and Plex Mono are Google-Fonts stand-ins — substitute binaries when brand fonts exist.*
- **Motion**: everything morphs, nothing cuts. State changes lerp every parameter (~250ms time constant, `--dur-state` 650ms perceived). Resting tempo is a 4.2s breath (`--dur-breath`). Eases: `--ease-fluid`, `--ease-drift`, `--ease-swell`. Respect `prefers-reduced-motion` in decorative loops.
- **Line quality**: fine concentric echo lines inside the orb rim nod to Piranesi etchings. Strokes are thin, rounded caps, with soft same-hue glows (`--glow-accent`) — glow is the only "shadow"; no drop shadows on dark navy.
- **Text legibility**: only text sitting *inside* the orb (square/round center captions) gets a vignette — a circular radial one matching the orb's shape (`radial-gradient(circle closest-side, …)`). Text beside or below the orb sits directly on the navy, no vignette, no capsule.
- **Shape language**: circles first. Pills for chips/buttons (`--radius-pill`), 12px for panels (`--radius-md`). Hairline borders `--border-subtle` (bronze at 22%); hover brightens toward `--border-strong`. Press states darken, never shrink.
- **Layout**: orb dead-center, sized by `min(vw, vh)`; content keeps clear of edges (round-bezel safe). No fixed chrome.

## Iconography

The columned-house glyph is the only icon — there is no icon set, no icon font, no emoji. It renders inside the orb (stroked on canvas, same hue as the mood) or stands alone as `assets/glyph.svg` / `assets/mark-circle.svg`. Wordmark is set in Cormorant Garamond — **no drawn wordmark exists; do not invent one**. If a future screen truly needs utility icons, propose a thin-stroke set (e.g. Lucide at 1.5px) to the user first.

## Components

- **PiranesiOrb** (`components/orb/`) — the voice orb. Props: `state` (waiting | listening | thinking | working | talking | error), `modulation` (auto | none | dawn | day | dusk | night | rain | storm | degraded | threat), `audio` (MediaStream / media element / AnalyserNode / level fn), `intensity`, `showGlyph`, `color`, `offsetX`. Fills its container; every parameter is fluidly interpolated.

### Intentional additions
None beyond the orb — the product has no other UI. Chips/captions in the kit are demo scaffolding, styled from tokens.

## Index

- `styles.css` → imports `tokens/{colors,typography,spacing,motion}.css`
- `assets/` — `glyph.svg`, `mark-circle.svg`
- `components/orb/` — `PiranesiOrb.jsx` + `.d.ts` + `.prompt.md` + card
- `ui_kits/display/` — full-screen Voice Display (interactive: states + landscape/portrait/square/round shapes)
- `guidelines/` — specimen cards (colors, mood hues, type, spacing, motion, marks)
- `SKILL.md` — agent skill entry point
