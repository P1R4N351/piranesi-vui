# design-sync notes — piranesi-vui

## Provenance (2026-07-10 bootstrap)

- The design system was authored **in the Claude Design app itself** (project
  "Piranesi VUI Design System", id `8af39666-f588-49a2-a32d-e8e57314f5e5`,
  owned by the Piranesi claude.ai login — NOT a personal login).
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
- **`readme.md` is REPO-authoritative, and the PULL must never blind-overwrite
  it** (2026-08-15). Commit 3055c76 (2026-07-13) added two repo-side sections —
  "Runtime modulation feed" and "Deriving & drift-proofing" — that were never
  pushed up, so the remote copy sat as a strict SUBSET of local for a month.
  `scripts/design-sync-pull.md` step 2 says to overwrite every changed DS-source
  file from remote; readme.md IS a DS-source file, so a literal execution would
  have deleted both sections. ~30 successful cron pulls in that window did not
  regress it — the runbook is executed by an agent that noticed local was ahead —
  but that is judgment, not a guarantee. Before writing readme.md during a pull,
  diff it and push repo→project when local is the superset.

## Sync-direction rule (both directions are live)

- The design app is the upstream for ORB ANIMATION/EFFECT work (2026-07-13
  designation, `scripts/design-sync-pull.md`). It is NOT upstream for the repo's
  own engineering documentation. Practical split:
  - project → repo: `_ds_bundle.js`, `PiranesiOrb.jsx`, cards, tokens, templates.
  - repo → project: `readme.md` (see above), and anything documenting downstream
    wiring the design app has no visibility into.

## Cron pull health (checked 2026-08-15)

- `41 */4 * * *` → `scripts/design-sync-pull.sh` (via `cron-load-gate.sh`), log
  `$DS_LOG`. **Last rc=0 was 2026-08-13T00:53.**
  Every run since has failed: weekly-limit, then repeated
  `401 OAuth access token has been revoked`, then `Request timed out`. Overall
  31 rc=0 / 143 rc!=0 across 174 runs — the weekly-limit class dominates.
- The main/interactive session authenticates to DesignSync fine; the failure is
  specific to the headless `claude -p` agent's design OAuth. A revoked token
  needs a re-auth on this host before the automated pull resumes.
- The job logs rc=1 and moves on — nothing pages on a dead pull. It is a silent
  no-op exactly like the class `design-sync-pull.md` step 6 warns about; the
  ntfy-on-failure branch never runs because auth dies before the agent starts.
