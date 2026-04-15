# TEAM-GAME LINEUP STATE SUBSTRATE — BUILD REPORT

**Build timestamp:** 2026-04-15T09:12:33Z
**Status:** COMPLETE
**Output parquet:** `research/recovery/mlb_lineup_state_substrate/team_game_lineup_state.parquet`
**Rows:** 19,712 | **Columns:** 54

---

## PURPOSE

This substrate aggregates individual batter-game records to the **team-game** level, producing a set of rolling offensive-state features that describe how well a lineup has been hitting in the weeks prior to each game. It serves as the offensive-side input for downstream MLB totals modeling.

The substrate is intentionally team-game granular (not player-game). A downstream model joins on `(game_pk, team)` to enrich any game row with the batting lineup's recent quality.

Key design constraints:
- **PIT-safety is mandatory.** All rolling features use `shift(1)` before windowing, so no game's own statistics contaminate its feature row.
- Per-game realized stats are excluded from the output to prevent accidental target leakage.
- Rolling windows require minimum periods, avoiding false precision from 1–2 game samples.

---

## INPUT AUDIT

### Input 1: batter_game_statcast.parquet
- **Path:** `research/recovery/mlb_hitter_statcast_substrate/batter_game_statcast.parquet`
- **Rows:** 197,497 | **Columns:** 17 (after dedup in upstream substrate, 18 in raw)
- **Seasons:** 2022=48,319 / 2023=48,762 / 2024=48,751 / 2025=48,815 / 2026=2,850
- **Columns used:** `game_pk`, `game_date`, `batter`, `player_id`, `team`, `home_away`, `season`, `bip_count`, `avg_exit_velo`, `hard_hit_rate`, `barrel_rate`, `avg_launch_angle`, `xwoba_contact`, `xba_contact`, `xslg_contact`
- **Warnings:** None. All expected columns present.

### Input 2: hitter_game_logs.parquet
- **Path:** `mlb/data/hitter_game_logs.parquet`
- **Rows:** 204,548 | **Columns:** 28
- **Seasons:** 2022=50,038 / 2023=50,495 / 2024=50,478 / 2025=50,594 / 2026=2,943
- **Columns used:** `game_pk`, `game_date`, `season`, `player_id`, `team`, `home_away`, `plate_appearances`, `at_bats`, `hits`, `doubles`, `triples`, `home_runs`, `walks`, `strikeouts`
- **home_away values:** A=102,427 / H=102,121 (well-balanced)
- **Warnings:** None. `iso` column present in source but recomputed for consistency.

### Input 3: sim/data/game_table.parquet (for game_number only)
- **Rows:** 9,902 | `game_number` column present
- **game_number distribution:** 1=9,740 / 2=162 (game-level rows; each game counts once)
- **Columns used:** `game_pk`, `game_number` only
- **Warnings:** None.

### Team normalization map applied to both HGL and BGS:
```
AZ->ARI, CWS->CHW, KC->KCR, SD->SDP, SF->SFG, TB->TBR, WSH->WSN, ATH->OAK
```

---

## TEAM-GAME AGGREGATION

### Layer A: Box-score offense shape (source: HGL)

Grouped by `(game_pk, team_norm, season, game_date)`. Aggregation:

| Output field     | Source         | Method  |
|------------------|----------------|---------|
| total_pa         | plate_appearances | sum   |
| total_ab         | at_bats        | sum     |
| total_hits       | hits           | sum     |
| total_walks      | walks          | sum     |
| total_k          | strikeouts     | sum     |
| total_hr         | home_runs      | sum     |
| total_doubles    | doubles        | sum     |
| total_triples    | triples        | sum     |
| n_batters        | player_id      | nunique |
| home_away        | home_away      | first   |

Derived per-game rates (used as rolling source; excluded from output):
- `bb_rate = total_walks / total_pa`
- `k_rate = total_k / total_pa`
- `hr_rate = total_hr / total_ab`
- `iso = (2B + 2×3B + 3×HR) / total_ab`

**Layer A rows:** 19,712

### Layer B: Statcast quality (source: BGS)

Grouped by `(game_pk, team_norm, season)`. Aggregated as mean over team's batters for that game.

| Output field          | Source              | Method  |
|-----------------------|---------------------|---------|
| sc_avg_exit_velo      | avg_exit_velo       | mean    |
| sc_hard_hit_rate      | hard_hit_rate       | mean    |
| sc_barrel_rate        | barrel_rate         | mean    |
| sc_avg_launch_angle   | avg_launch_angle    | mean    |
| sc_xwoba_contact      | xwoba_contact       | mean    |
| sc_xba_contact        | xba_contact         | mean    |
| sc_xslg_contact       | xslg_contact        | mean    |
| sc_batter_count       | batter              | nunique |
| sc_total_bip          | bip_count           | sum     |

**Layer B rows:** 19,712

### Join

Left join on `(game_pk, team, season)` — box-score is the spine.

- **Joined rows:** 19,712 (perfect 1:1 match)
- **Statcast coverage:** 19,710/19,712 = 99.99%
  - 2 rows missing Statcast (effectively 0.01%; expected for very early-season or data gaps)
- **game_number:** left-merged from game_table; filled with 1 where absent

---

## COVERAGE

| Metric                    | Value         |
|---------------------------|---------------|
| Total team-game rows      | 19,712        |
| Seasons covered           | 2022–2026     |
| Doubleheader game_number=2| 324 team-game rows |
| Statcast coverage         | 99.99%        |
| Teams after normalization | 30            |

---

## ROLLING LOGIC

### Sort order
`(team, season, game_date, game_number)` — ascending. This ensures doubleheader game 1 precedes game 2 within the same calendar day.

### PIT-safety mechanism
All rolling features are computed as:
```python
x.shift(1).rolling(window, min_periods=min_per).mean()
```
The `shift(1)` excludes the current game from its own feature. The rolling mean then operates on the previous games only, within the same `(team, season)` group.

### Windows and minimum periods

| Window | Min Periods | Rationale                                    |
|--------|-------------|----------------------------------------------|
| 7      | 5           | Short-term hot/cold streak; requires 5 games |
| 10     | 7           | Medium-term form                             |
| 15     | 10          | Seasonal half-month context                  |
| 20     | 12          | Longer trend; prevents early-season noise    |

### Null rate by window (all rolling families identical)
- last_7: 3.8% null (season-start teams with <5 prior games)
- last_10: 5.3%
- last_15: 7.5%
- last_20: 8.7%

These nulls are expected and structurally correct — they represent the first weeks of each season where a team hasn't yet accumulated enough prior games.

---

## FEATURE FAMILIES

### Contact Quality Family (7 metrics × 4 windows = 28 rolling cols)
Source: batter_game_statcast substrate (Statcast ground-truth, BIP-only)

| Feature name          | Source column       | Meaning                             |
|-----------------------|---------------------|-------------------------------------|
| contact_ev            | sc_avg_exit_velo    | Average exit velocity on contact    |
| contact_hh_rate       | sc_hard_hit_rate    | Hard-hit rate (EV >= 95 mph)        |
| contact_barrel_rate   | sc_barrel_rate      | Barrel rate                         |
| contact_la            | sc_avg_launch_angle | Average launch angle                |
| contact_xwoba         | sc_xwoba_contact    | Expected wOBA on contact            |
| contact_xba           | sc_xba_contact      | Expected BA on contact              |
| contact_xslg          | sc_xslg_contact     | Expected SLG on contact             |

### Plate Discipline Family (2 metrics × 4 windows = 8 rolling cols)
Source: hitter_game_logs (box-score)

| Feature name    | Source column | Meaning              |
|-----------------|---------------|----------------------|
| plate_bb_rate   | bb_rate       | Walk rate (BB/PA)    |
| plate_k_rate    | k_rate        | Strikeout rate (K/PA)|

### Damage Shape Family (2 metrics × 4 windows = 8 rolling cols)
Source: hitter_game_logs (box-score)

| Feature name    | Source column | Meaning                |
|-----------------|---------------|------------------------|
| damage_iso      | iso           | Isolated power (2B+3B+HR formula / AB) |
| damage_hr_rate  | hr_rate       | HR rate (HR/AB)        |

**Total approved rolling columns: 44**

---

## FIELD DISPOSITION

### Identity columns (6)
`game_pk`, `game_date`, `season`, `team`, `home_away`, `game_number`

### Approved rolling columns (44)
All `*_last_{7,10,15,20}` columns. These are the intended feature set for downstream use.

### Carried-only columns (4)
`n_batters`, `sc_batter_count`, `sc_total_bip`, `total_pa`

These are game-level observed counts retained for diagnostic and weighting purposes. They are **not** rolling features and **must not** be used as predictive features directly — they are per-game observations.

### Excluded from output (18 columns — per-game realized)
`total_ab`, `total_hits`, `total_walks`, `total_k`, `total_hr`, `total_doubles`, `total_triples`,
`bb_rate`, `k_rate`, `hr_rate`, `iso`,
`sc_avg_exit_velo`, `sc_hard_hit_rate`, `sc_barrel_rate`, `sc_avg_launch_angle`,
`sc_xwoba_contact`, `sc_xba_contact`, `sc_xslg_contact`

These per-game realized statistics are excluded because using them as features for a game's own prediction would be data leakage. They remain available in source parquets.

---

## PIT-SAFETY VERDICT

**PASS.** All rolling features use `shift(1)` before windowing within `(team, season)` groups sorted by `(game_date, game_number)`. No game's own statistics appear in its own feature row. Per-game realized stats are excluded from output entirely.

---

## WARNINGS

1. **2 rows with missing Statcast** (0.01%): `sc_*` rolling features for these 2 rows will be null for the window containing those games. This is negligible and expected.
2. **2026 partial season**: Rolling features for 2026 games reflect early-season samples only. The min_periods guard prevents features from being populated until sufficient history exists.
3. **Carried-only columns are not PIT-safe features**: `total_pa`, `n_batters`, `sc_batter_count`, `sc_total_bip` are game-level actuals. They must not be used as predictive inputs for that game — only for diagnostic weighting.
4. **home_away='A'/'H' encoding**: Inherited from HGL source. Downstream users should be aware this differs from some other substrates that use 'home'/'away'.

---

## STATUS

COMPLETE. All 4 permitted output files written. No background tasks used. No additional files created.
