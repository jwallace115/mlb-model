# Phase 5B -- Usage Layer Repair

**Date:** 2026-09-17
**Commit:** (see git log)
**Scope:** `nfl/sim/usage.py`, `nfl/sim/params_v1.json`

## What Was Wrong

### 1. Missing params block
`params_v1.json` had no `"usage"` key. `build_player_usage()` fell back to defaults
(`share_half_life=inf`, `k_share=50`) instead of the tuned values (`share_half_life=4`,
`k_share=20`). With infinite half-life, all prior weeks are weighted equally; with
`k_share=50`, prior mass dominates until ~50 team opportunities accumulate. Combined
with the zero-evidence override (D14), every player with 0 touches got 1e-8 and
normalized to uniform shares -- KC Week 2 had all 3 QBs at 0.0625.

### 2. Starting-QB identity missing
No mechanism identified which QB was the starter. All QBs with zero in-season touches
received the same 1e-8 share and normalized equally. The engine/board picked the wrong
QB (Justin Fields attributed as KC passer instead of Mahomes).

### 3. Backup QB prior leakage
Backup QBs with a strong s-1 prior (e.g., a QB who started 16 games the previous
season, now a backup on a new team) could carry prior-blended shares even with zero
current-season attempts. The spec says a second QB may only receive share from observed
attempts.

### 4. depth_cols truncation
`load_roster_data()` stripped the new-schema depth chart columns (`pos_rank`, `pos_abb`,
`team`, `dt`) during loading, making the 2025+ depth chart data invisible to the
starting-QB derivation.

## What Changed

### params_v1.json
Added `"usage": {"share_half_life": 4, "k_share": 20, "frozen_at": "2026-09-17",
"frozen_commit": "463a666d0"}`. The builder now raises `ValueError` if this block
is missing -- no default fallbacks.

### derive_starting_qbs(depth, plays)
New function. Three-layer priority:
1. Old-schema depth chart (per-week `depth_team=1`, 2020-2024)
2. PBP leading passer from the previous game (`passer_player_id`, most attempts)
3. New-schema depth chart (static `pos_rank=1`, 2025+)

Each layer only fills keys not already set by a higher-priority layer.

### build_player_usage() -- QB allocation
- **Starting QB with 0 opp:** retains prior-based blend (exempt from the D14 1e-8
  override). After normalization, gets ~100% of QB share when no PBP data exists.
- **Backup QBs:** share set to pure observed proportion (`w_touches / opp`), zero
  if no raw touches. No prior influence.
- **is_starting_qb column:** boolean, one True per team-week.

### load_roster_data()
`depth_cols` expanded to include `pos_rank`, `pos_abb`, `team`, `dt`.

## Test Results

| # | Test | Status |
|---|------|--------|
| (a) | params block present; perturbing k_share changes shares | PASS |
| (b) | shares per team-week sum to 1.00 +/- 0.001 | PASS |
| (c) | KC 2025 wk17 top-3 target share within 0.05 of observed | PASS |
| (d) | starting-QB identity for every 2026 team-week = depth chart / prev-game passer, 100% | PASS |
| (e) | CAR case: no zero-opp player above D14 prior; Dotson/Zaccheaus not on CAR | PASS |
| (f) | PIT byte-identity: 2024 wk10 from truncated data == full-season build | PASS |

## 2026 Week 2 DET/BUF Spot Check

Games used: DET hosted NO (2026_01_NO_DET), BUF at HOU (2026_01_BUF_HOU).

### DET (2026 wk2, built from wk1 PBP)

| Player | Pos | tgt_share | car_share | n_tgt | n_car |
|--------|-----|-----------|-----------|-------|-------|
| *Jared Goff | QB | 0.0000 | 0.0294 | 0 | 1 |
| Jahmyr Gibbs | RB | 0.1445 | 0.9167 | 5 | 29 |
| Sione Vaki | RB | 0.0173 | 0.0539 | 1 | 2 |
| Amon-Ra St. Brown | WR | 0.3427 | 0.0000 | 14 | 0 |
| Jameson Williams | WR | 0.2144 | 0.0000 | 9 | 0 |
| Sam LaPorta | TE | 0.1986 | 0.0000 | 8 | 0 |
| Brock Wright | TE | 0.0457 | 0.0000 | 1 | 0 |
| Isaac TeSlaa | WR | 0.0368 | 0.0000 | 1 | 0 |

### BUF (2026 wk2, built from wk1 PBP)

| Player | Pos | tgt_share | car_share | n_tgt | n_car |
|--------|-----|-----------|-----------|-------|-------|
| *Josh Allen | QB | 0.0000 | 0.1600 | 0 | 4 |
| James Cook | RB | 0.1133 | 0.7164 | 4 | 13 |
| DJ Moore | WR | 0.2276 | 0.0000 | 8 | 0 |
| Khalil Shakir | WR | 0.2125 | 0.0000 | 6 | 0 |
| Dalton Kincaid | TE | 0.1796 | 0.0000 | 6 | 0 |
| Keon Coleman | WR | 0.1131 | 0.0000 | 2 | 0 |
| Josh Palmer | WR | 0.0902 | 0.0000 | 2 | 0 |
| Dawson Knox | TE | 0.0636 | 0.0000 | 1 | 0 |

`*` = is_starting_qb

---

## Phase 5B-fix -- Tuner/Builder Split, Layer-3 Scope

**Date:** 2026-09-17
**Commit:** (see git log)

### Defect (found by Cowork verification of 121e4bd31)

`main()` re-ran the 12-point grid search on 2021-2024 on every build and
unconditionally wrote `params["usage"]`, dropping `frozen_at`/`frozen_commit`.
D42 was therefore enforced only inside `build_player_usage()`, not at the
builder's own entry point.

Additionally, `derive_starting_qbs` layer 3 (static new-schema depth chart)
filled 2025 historical weeks from a depth-chart snapshot that post-dated those
games, making 2025 starting-QB assignments unreliable.

### What Changed

1. **`main()` is build-only.** Reads `params_v1.json`, requires the `"usage"`
   block (raises if absent), builds with the frozen values, never writes the
   file. A `--tune` flag runs the grid search (2021-2024 only; season>=2025
   guard retained) and writes `share_half_life`, `k_share`, `frozen_at`,
   `frozen_commit`, and `grid_results`.

2. **Layer-3 scope restricted to `season >= 2026`.** For 2025 historical weeks
   the static snapshot is not used; keys are left unset and the count is logged.

### Test Results (appended)

| # | Test | Status |
|---|------|--------|
| (g) | plain main() leaves params_v1.json byte-identical (sha256 before/after) | PASS |
| (h) | --tune writes frozen_at, frozen_commit; chosen point = (4, 20) | PASS |
| (i) | no 2025 team-week has layer-3 starting QB; every 2026 wk2 team has one | PASS |
