# design-sync notes — piranesi-vui

## Provenance (2026-07-10 bootstrap)

- The design system was authored **in the Claude Design app itself** (project
  "Piranesi VUI Design System", id `8af39666-f588-49a2-a32d-e8e57314f5e5`,
  owned by the Piranesi claude.ai login — NOT the command-ds/Sat-login case).
- This repo (`github.com/P1R4N351/piranesi-vui`) was empty at DS build time;
  the DS readme names it as the intended product-code home. On 2026-07-10 the
  project was mirrored down into this repo verbatim as the initial commit —
  the bootstrap sync ran project→repo, once. From here on the repo is the
  source of truth and sync runs repo→project as usual.

## Shape: prebuilt (no converter)

- The repo tree **is already the upload contract layout** — `_ds_bundle.js`,
  `styles.css` → `tokens/*.css`, `components/orb/…` (jsx/d.ts/prompt.md/card),
  `guidelines/*.card.html`, `ui_kits/display/`, `templates/voice-display/`.
  There is no package build, no storybook, no dist/: `package-build.mjs` and
  `resync.mjs` do NOT apply.
- Re-sync procedure: diff repo tree vs `DesignSync(list_files)` + content
  compare on changed candidates, then `finalize_plan` → `write_files` the
  changed paths → re-write `_ds_needs_recompile` sentinel last.
- `_ds_manifest.json` and `uploads/` are app-managed (card index / user
  uploads). Mirrored for completeness; do not hand-edit `_ds_manifest.json` —
  the app rebuilds it from `@dsCard` markers.
- No `_ds_sync.json` anchor exists (honest omission per skill: hand-authored
  layout, no storybook facts). Every re-sync re-verifies what it touches.
- Single component (PiranesiOrb) — verification = render its card +
  `ui_kits/display/index.html` headlessly and eyeball states before pushing.
  Host chromium gotcha: snap chromium can't write /tmp; screenshot to $HOME.

## Conventions header

- Remote `readme.md` already carries the conventions (wrapping, tokens,
  mood/modulation vocabulary, motion, copy rules) — authored in-app. It is the
  README the design agent consumes; treat it as the `conventions.md`
  equivalent. Keep it true rather than rewriting it.
