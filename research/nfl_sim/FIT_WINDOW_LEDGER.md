# Fit-Window Ledger — NFL Sim

Tracks which seasons have been looked at for which purpose, and their status.

## Status Definitions

| Status | Meaning |
|--------|---------|
| DISCOVERY | Used for feature selection, model structure, or tuning |
| VALIDATION | Used for holdout scoring (one look) |
| CONSUMED | Multiple looks; no longer blind |
| NOT BLIND | Seen during development but not formally scored |
| PROSPECTIVE | No look taken; live data accumulating |
| UNTOUCHED | Data exists but has never been opened for this purpose |

## Engine Mechanics (Phase 1–2: play generation, scoring, clock, penalties)

| Season | Status | Date | Commit | Notes |
|--------|--------|------|--------|-------|
| 2020 | DISCOVERY | 2026-09-13 | multiple | Prior-season only (shrink targets) |
| 2021 | DISCOVERY | 2026-09-13 | multiple | Tuned engine mechanics, anchoring convergence |
| 2022 | DISCOVERY | 2026-09-13 | multiple | Same |
| 2023 | DISCOVERY | 2026-09-13 | multiple | Same |
| 2024 | DISCOVERY | 2026-09-14 | multiple | Same; Jacobian estimated on 2024 50 games |
| 2025 | VALIDATION | 2026-09-14 | 19ee88142 | K2 scored once; lock file written (HOLDOUT_2025_SCORED.lock) |
| 2026 | PROSPECTIVE | — | — | Forward experiment nfl_fwd_v1 started week 4 |

## Usage & Prop Maps (Phase 2B–3: player allocation, prop calibration)

| Season | Status | Date | Commit | Notes |
|--------|--------|------|--------|-------|
| 2021 | DISCOVERY | 2026-09-14 | c83c43d90 | Prop isotonic maps fitted 2021–24 |
| 2022 | DISCOVERY | 2026-09-14 | c83c43d90 | Same |
| 2023 | DISCOVERY | 2026-09-14 | c83c43d90 | Same |
| 2024 | DISCOVERY | 2026-09-14 | c83c43d90 | Same |
| 2025 | VALIDATION | 2026-09-14 | 19ee88142 | Props scored once; lock updated |
| 2026 | PROSPECTIVE | — | — | Forward experiment |

## Game-Line Structure Discovery (margin/total bias, c_margin/c_total regressions)

| Season | Status | Date | Commit | Notes |
|--------|--------|------|--------|-------|
| 2021 | CONSUMED | 2026-10-10 | (this order) | Cowork smoke test: anchored_2021-23.parquet, c_margin +0.10 t=0.78, c_total −0.24 t=−1.76 |
| 2022 | CONSUMED | 2026-10-10 | (this order) | Same |
| 2023 | CONSUMED | 2026-10-10 | (this order) | Same |
| 2024 | UNTOUCHED | — | — | Never opened for game-line metrics; anchored_2024.parquet exists but not read |
| 2025 | NOT BLIND | 2026-09-14 | K2 lock | K2 scored 2026-09-14; game-line calibration maps fitted on 2021-24; 2025 not independently blind |
| 2026 | PROSPECTIVE | — | — | Forward experiment; no game-line regression run |

## Game-Line PIT Look (this order: baseline model, unanchored engine)

| Season | Status | Date | Commit | Notes |
|--------|--------|------|--------|-------|
| 2021 | CONSUMED | 2026-10-10 | GL1/GL2/GL3 | Baseline fitted LOO-CV; engine scored unanchored; mixed regression run |
| 2022 | CONSUMED | 2026-10-10 | GL1/GL2/GL3 | Same |
| 2023 | CONSUMED | 2026-10-10 | GL1/GL2/GL3 | Same |
| 2024 | UNTOUCHED | — | — | Reserved for clean look (G1 standing rule) |
| 2025 | NOT BLIND | 2026-09-14 | K2 lock | Touched by K2; cannot be a clean holdout for game lines |
| 2026 | PROSPECTIVE | — | — | Forward protocol (GL_FORWARD_PROTOCOL_v1.md) |

## Forward Experiment (nfl_fwd_v1)

| Season | Status | Date | Commit | Notes |
|--------|--------|------|--------|-------|
| 2021–2025 | N/A | — | — | Historical; not part of forward experiment |
| 2026 | PROSPECTIVE | 2026-09-30 | D254 | Primary count starts week-4 TNF (PIT@CLE) |

---

## Provenance Notes

- **fit_5c2**: 1,084 games, seasons 2021–2024. No fit_meta.json (predates D83).
- **fit_5c2b**: 1,087 games, seasons 2021–2024. No fit_meta.json.
- **fit_5d1**: 1,087 games, seasons 2021–2024. No fit_meta.json.
- **fit_5d2**: 1,087 games, seasons 2021–2024. Backfilled fit_meta.json (engine fp `d929ad258504b275`, usage fp `840412f7295a8323`, commit `7f5a808c5`).
- **fit_5i**: 1,087 games, seasons 2021–2024. fit_meta.json written at fit time (engine fp `7f3d96900218c014`, usage fp `840412f7295a8323`, commit `4c67b0ceb`, completed 2026-09-20T05:16:40Z).
- **HOLDOUT_2025_SCORED.lock**: timestamp 2026-09-14T16:06:49Z, 272 games, calibration sha `8e56e01810b5`.
- **Cowork 2026-10-10 smoke test**: anchored_2021-23.parquet opened; c_margin +0.10 (t=0.78), c_total −0.24 (t=−1.76). This consumed 2021-23 for game-line structure discovery.
