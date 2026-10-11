# GL Forward Protocol v1 — Game-Line Prospective Grading

## Freeze

The freeze pins three objects:

1. **Engine fingerprint** — content-based SHA256[:16] from `calibration.engine_fingerprint()`.
   The engine code, tables, and calibration on main at the time of the first freeze
   define the sim distribution. No engine change is applied to game-line grading
   without a new freeze and a fresh forward count.

2. **Baseline params** — the ridge coefficients from `gameline_baseline.fit_baseline`,
   the shrinkage parameters (k, k_qb, prior_weight, prior_regression from params_v1.json),
   and the chosen `hl_games` (currently infinity, G2). Coefficients are serialized
   alongside the freeze.

3. **hl_games pinned** — the decay parameter is frozen at the value chosen by LOO-CV
   on 2021-23 (currently infinity). It is not re-tuned on forward data.

## Weekly Capture

Each week, before the Hard Rock snapshot used by the reader (N54), both objects
write their game-line numbers into an append-only parquet:

### Sim object (unanchored engine)
- `game_id`, `season`, `week`
- `raw_m` (unanchored mean margin), `raw_t` (unanchored mean total)
- `sd_m`, `sd_t` (standard deviations)
- `p_home_win`
- `engine_fingerprint`
- `N` (must be 5,000, D51)
- `seed_key`
- `capture_utc` (timestamp of capture)

### Baseline object
- `game_id`, `season`, `week`
- `baseline_m` (predicted mean margin), `baseline_t` (predicted mean total)
- `baseline_sd_m`, `baseline_sd_t` (residual SDs from training)
- `capture_utc`

### Market snapshot (from reader's Hard Rock pull)
- `game_id`, `season`, `week`
- `hr_spread`, `hr_total` (Hard Rock pre-kickoff line)
- `hr_spread_price`, `hr_total_price` (prices, for CLV)
- `snapshot_utc` (timestamp; age labelled if > 10 min before kickoff)

All three are written to the same append-only parquet
(`nfl/data/sim/outputs/gl1/forward_log.parquet`) with a `source` column
(`sim`, `baseline`, `market`).

## Grading

Three metrics, computed only on games where all three objects have a pre-kickoff entry:

### (i) CLV vs Hard Rock close
- For each game, compute the sim's implied probability of home cover and over/under
  at the Hard Rock number.
- After the game, compare to the Hard Rock CLOSING line (not the pre-kickoff snapshot).
- CLV = (implied prob at close) − (implied prob at snapshot). Positive = the sim was
  ahead of the market move.
- Reported as: mean CLV, t-stat, by week.

### (ii) Mixed-regression c on forward games
- actual = a + b·mkt + c·sim on the forward sample.
- Same form as G2's in-sample test. If c is significantly positive, the engine adds
  information over the close on truly prospective data.

### (iii) Log-loss vs de-vigged market
- Compute each object's P(home cover) and P(over) at the market number.
- Log-loss scored against outcomes.
- Compare: sim, baseline, de-vigged market (from Hard Rock prices).

## Mode

**PILOT** until:
1. The 2024 clean look (a separate order, after the ChatGPT audit G5) confirms or
   refutes the in-sample c on untouched data.
2. The ChatGPT audit (G5) finds no provenance defects.
3. At least 125 forward games have been graded.

After all three conditions are met, promote to **PRIMARY** (game-line numbers enter
the reader's opinion formation, under N54).

## Constraints

- Nothing is tuned on 2026 data. The freeze is the freeze.
- The sim is a **layer** under N54 (the pick is the reader's opinion, not the sim's
  number). It is never the picker.
- ~125 games before any reading of forward results is reported. This is approximately
  8 weeks of a full NFL slate.
- The forward log is append-only. No retroactive edits. If a capture fails, the game
  is missing, not backfilled.
- Freeze timing cannot be gamed: the engine fingerprint is content-based (not git HEAD),
  and the baseline coefficients are deterministic from the PBP data + params. A
  re-freeze after seeing forward data requires a new freeze entry with a new timestamp
  and resets the forward count.
