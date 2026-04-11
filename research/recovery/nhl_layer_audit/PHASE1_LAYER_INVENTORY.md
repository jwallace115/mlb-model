# NHL Layer Inventory (Phase 1)

## Date: 2026-04-10

Source files examined:
- `nhl/nhl_daily_pipeline.py` (1,239 lines)
- `push_nhl.py` (353 lines)
- `nhl/nhl_summaries.py` (280 lines)
- `nhl/phase5_market_architecture.py` (Phase 5 historical grading)
- `nhl/phase45_calibration.py` (calibration audit output)
- `nhl/data/nhl_stop_rules.json`

---

## Layer 1: DRIFT CORRECTION (predict_and_calibrate)

**Location:** `nhl_daily_pipeline.py` lines 608-649

**Constant:** `VALIDATE_DRIFT = 0.4458`

**What it does:** Adds +0.4458 goals (split equally between home/away) to raw
model predictions. Applied universally to every game.

**Logic:** `lh_cal = lh_raw + 0.4458/2.0`, `la_cal = la_raw + 0.4458/2.0`

**Origin:** Phase 4.5 calibration on the OLD MoneyPuck-based model's validate
season (2023-24). The old model's validate-season raw predictions averaged
5.7798 vs actual 6.2256, gap = +0.4458.

**Dynamic drift path:** Code has a stub for computing live-season drift
dynamically (lines 640-643) but it ALWAYS falls through to `VALIDATE_DRIFT`.
The dynamic path was never implemented.

---

## Layer 2: POISSON SIMULATION (simulate)

**Location:** `nhl_daily_pipeline.py` lines 654-678

**What it does:** Draws 10,000 Poisson samples for home/away using calibrated
lambdas, computes over/under/push probabilities against the market line.

**Push correction:** Integer-line corrections for 6.0 and 7.0 lines
(from Phase 4.5 calibration):
- Line 6.0: correction = -0.0471
- Line 7.0: correction = -0.0422

**Origin:** Phase 4.5 calibration on old model. The old model's Poisson sim
produced push_prob=0.1586 at line 6.0, but actual was 0.1115.

---

## Layer 3: GOALIE HANDLING (fetch_goalies + compute_game_features)

**Location:** `nhl_daily_pipeline.py` lines 181-210, 546-603

**Components:**
- `fetch_goalies()` — reads NHL API boxscore for starter goalie name/status
- `home/away_goalie_b2b` — flag if goalie started yesterday
- `home/away_backup_flag` — flag if non-starter is in net
- `home/away_goalie_fatigue` — count of games in last 3 days
- `home/away_goalie_sv_pct_rolling_10` — rolling save% from live season data
- `home/away_goalie_vs_team_baseline` — goalie SV% vs team average

**Origin:** Rebuilt as part of Model A. These features are native to the rebuild
model, not legacy layers. The rebuild model was trained with all these features.

---

## Layer 4: CONFIDENCE TIER SYSTEM (confidence_tier)

**Location:** `nhl_daily_pipeline.py` lines 783-808

**Thresholds:**
- HIGH: edge >= 0.15 AND no high volatility (backups < 2)
- MEDIUM: edge >= 0.12 (if active per stop rules)
- LOW: edge >= THRESHOLD (0.12) but < 0.12 (never reached -- effectively edge < 0.12)
- SHADOW_MEDIUM / SHADOW_LOW: when stop rules shadow the tier

**Stake units:** HIGH=1.0, MEDIUM=0.75, SHADOW_MEDIUM=0.0, LOW=0.5, SHADOW_LOW=0.0

**Note:** The tier system is effectively: HIGH (0.15+), MEDIUM (0.12-0.15), LOW (<0.12).
But THRESHOLD=0.12, so signals below 0.12 are never generated. LOW tier signals
can only exist from historical Phase 5 data, not live pipeline.

---

## Layer 5: STOP RULES (nhl_stop_rules.json)

**Location:** `nhl/data/nhl_stop_rules.json`

**Current state (as of 2026-04-09):**
```json
{
  "high_tier": "active",
  "medium_tier": "shadow",
  "medium_shadow_date": "2026-04-09",
  "medium_shadow_reason": "33.3% win rate 2026 (7-14)",
  "low_tier": "shadow",
  "low_shadow_date": "2026-04-09",
  "low_shadow_reason": "26.7% win rate 2026 (4-11)",
  "evaluation_date": "2026-05-01"
}
```

**Effect:** MEDIUM and LOW tiers are both shadowed. Only HIGH tier signals
(edge >= 0.15) receive non-zero stake. SHADOW_MEDIUM and SHADOW_LOW get
stake_units = 0.0 (logged but not bet).

---

## Layer 6: EDGE CALCULATION (compute_edges)

**Location:** `nhl_daily_pipeline.py` lines 762-778

**What it does:** Standard implied-probability edge calculation.
- Removes vig from over/under prices
- Edge = model_prob - fair_prob

**Origin:** Standard, model-agnostic. Portable.

---

## Layer 7: SIGNAL QUALIFICATION

**Location:** `nhl_daily_pipeline.py` lines 957-1028

**Threshold:** `THRESHOLD = 0.12` (edge must be >= 0.12 to generate a signal)

**Additional logic:**
- Caution flag for OVER signals on 6.5 lines
- Line movement from open snapshot
- Scoring-form features logged for summary generation

---

## Layer 8: GRADING / RESULTS (grade_yesterday)

**Location:** `nhl_daily_pipeline.py` lines 1055-1207

**What it does:** Fetches yesterday's final scores from NHL API, grades
WIN/LOSS/PUSH based on actual total vs line, writes CLV from snapshots.

**Settlement:** Uses final score (including OT/SO goals). This is standard
NHL totals settlement.

**CLV computation:** Uses morning (7am) and pregame (5pm) line snapshots
from `nhl_clv_snapshots.parquet`.

---

## Layer 9: OT/SO DIAGNOSTICS (build_ot_diagnostics in push_nhl.py)

**Location:** `push_nhl.py` lines 117-171

**What it does:** Shadow diagnostic only. Computes how many graded signals
had their result flipped by OT/SO goals (e.g., UNDER that would have won
in regulation but lost because OT added a goal).

**Origin:** Uses `went_to_ot`, `went_to_so`, `reg_total_goals` from
`nhl_games_canonical.csv`.

**Effect on output:** Reference only. Does NOT affect W/L/P grading.

---

## Layer 10: SUMMARIES (nhl_summaries.py)

**Location:** `nhl/nhl_summaries.py`

**What it does:** Generates plain-English reasoning for each signal.
Scores factors (goalie backup, B2B, scoring form, PP mismatch) and
picks top aligned/counter factors for 2-3 sentence summary.

**Dependencies:** Uses feature values from the signal dict. Does not
access the model directly.

---

## Layer 11: CLV SNAPSHOT INFRASTRUCTURE

**Location:** `refresh_5pm.py` lines 171-221, `nhl_daily_pipeline.py` grade_yesterday

**What it does:**
- Morning run (7am): pipeline generates signals with closing_total
- 5pm refresh: captures morning lines as "morning" snapshot before re-running pipeline
- Grading: computes CLV = closing_line - line_taken (directional by side)

**Data store:** `nhl/nhl_clv_snapshots.parquet`

---

## Layer 12: LINE MOVEMENT TRACKING

**Location:** `nhl_daily_pipeline.py` lines 882-894

**What it does:** Loads open-line snapshot for the day and computes
line_movement = current_line - open_line. Stored in signal but not
used for filtering or tier assignment.

**Data store:** `nhl/data/nhl_lines_open_YYYY_MM_DD.json`

---

## Layer 13: DATA QUALITY AUDIT (push_nhl.py)

**Location:** `push_nhl.py` lines 237-270

**What it does:** Pre-serialization checks on signal validity
(game_id not null, edge in [0,1], valid tier, valid side).
Sets `data_quality_warning` flag in JSON output.

---

## Layer 14: SEASON PERFORMANCE AGGREGATION

**Location:** `push_nhl.py` lines 173-211

**What it does:** Aggregates W/L/P/hit/ROI from nhl_results.parquet
(historical Phase 5 data) by split and tier. Does NOT include live
signals in season performance.

---

## Layer 15: LIVE SEASON FEATURE COMPUTATION

**Location:** `nhl_daily_pipeline.py` lines 305-541

**What it does:** Fetches all completed 2025-26 regular-season games
from NHL API, caches them, and computes rolling features (goals, shots,
PP%, PK%, goalie SV%) for each team entering today's game.

**Extended for rebuild:** Fetches SOG, PP goals, PP opportunities,
and goalie SA/GA from boxscore + play-by-play APIs.

**Shrinkage:** Uses 2024-25 league-average priors with linear shrinkage
weight = min(n_games, window) / window. Matches rebuild exactly.
