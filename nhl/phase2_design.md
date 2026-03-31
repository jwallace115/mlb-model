# NHL Totals Model — Phase 2 Design Document
**Status:** Pending review and approval before Phase 3 begins
**Canonical data source:** `nhl/nhl_games_canonical.csv` (5,248 games, 2021-22 through 2024-25, frozen)
**Date produced:** 2026-03-16

---

## 1. TARGET VARIABLE

### Primary target: `total_goals_final` (`home_score + away_score` from canonical table)

**Justification:** NHL totals markets — DraftKings, FanDuel, and all major US sportsbooks — grade full-game over/under bets on the **final score including overtime and shootout**. A game that goes to OT or SO counts all goals scored in those periods toward the graded total. The canonical column `total_goals_final` (stored as `total_goals` in the CSV) reflects this grading: it is `home_score + away_score`, which is the same number the sportsbook uses to settle the wager. Using `total_goals_reg` (regulation only) would misalign training labels with the bet we are pricing and introduce systematic bias — every OT/SO game where a goal is scored would be a training error even if the model's projection was correct for betting purposes.

The ridge models are therefore trained to predict `home_score` and `away_score` respectively (the final scores including OT/SO), and the Poisson simulation is constructed over those final-score distributions.

**Rejection of `total_goals_reg`:** `total_goals_reg` is retained in the canonical table as a diagnostic column and is available for later analytical phases (e.g., isolating process signal from OT variance), but it is not the modeling target.

### Push handling

A push occurs when `total_goals_final` equals the posted closing line exactly. This is possible only when the closing line is an integer (6.0, 7.0, etc.). When the closing line is a half-point (5.5, 6.5, etc.), pushes are structurally impossible.

**Decision:** `sim_over_prob`, `sim_under_prob`, and `sim_push_prob` are **raw outcome probabilities** across all simulated games, defined as:

```
sim_over_prob  = P(total_goals_final > closing_total)
sim_under_prob = P(total_goals_final < closing_total)
sim_push_prob  = P(total_goals_final == closing_total)
sim_over_prob + sim_under_prob + sim_push_prob = 1.0
```

These are NOT conditional on non-push outcomes. They are reported as raw probabilities and used as-is in edge computation. Conditional on non-push would be: `sim_over_prob / (1 - sim_push_prob)`, but this is not the correct quantity to compare against sportsbook implied probability because the book also prices pushes (they return the stake; they do not win or lose). The raw probability correctly represents what the bettor experiences over a large sample.

---

## 2. SIMULATION ARCHITECTURE

### Model structure

Two independent ridge regression models are trained:
- **Model H**: predicts `home_score` (expected final goals for home team, including OT/SO)
- **Model A**: predicts `away_score` (expected final goals for away team, including OT/SO)

The outputs of these two models are used as Poisson rate parameters:
- `lambda_home = Model_H(features)`
- `lambda_away = Model_A(features)`

**Poisson simulation (v1 — independent):** Home and away goals are drawn independently:
```
X ~ Poisson(lambda_home)
Y ~ Poisson(lambda_away)
total_goals_sim = X + Y
```

Correlation between home and away goals is ignored in v1. This is a known approximation — NHL teams that both shoot well tend to play higher-scoring games (e.g., fast-paced matchups), creating mild positive correlation between X and Y. If v1 calibration reveals systematic under-coverage of high-total outcomes, introducing a correlated Poisson structure (e.g., bivariate Poisson or a shared random effect) is the Phase 4 candidate improvement. For v1, independence is accepted.

**Do not model `total_goals_final` directly.** Modeling the total as a single output would lose the ability to produce team-level lambdas, which are required for the two-layer goalie adjustment structure (Section 3A) and for any future moneyline or puck-line extension.

### OT/SO handling

Since the modeling target is `total_goals_final` (which includes OT and SO goals), OT/SO contribution is **implicitly absorbed into the lambda estimates during training**. The ridge models observe final scores that sometimes include an extra OT goal or a SO winner credit, and they learn to produce expected values that incorporate this. No separate OT period model is built in v1.

**Accepted approximation and its direction:** Roughly 25–27% of NHL regular-season games go to OT or SO. For OT games, one additional goal is always scored; for SO games, one goal is credited to the winner but the OT period itself produces zero goals. On balance, OT/SO adds approximately 0.10–0.15 expected goals per game above what a regulation-only model would estimate. The ridge models will absorb this into the intercept and into the learning of team-level features. The Poisson distribution's support is the non-negative integers (0, 1, 2, …), which is appropriate for final total goals including OT/SO. The Poisson assumption of equal mean and variance is an approximation that will be assessed during validation — if the empirical variance exceeds the Poisson mean substantially (overdispersion), a negative binomial response is the Phase 4 candidate upgrade.

---

## 3. FEATURE CANDIDATE LIST

### Column name conventions
- "rolling last N games" means: among the team's last N games with `game_date < current game_date`, current season only, sorted ascending by date
- All rolling features reset at season boundaries (no carry-over from prior seasons)
- "per game" normalization is applied before rolling mean unless otherwise specified

---

### A. Goalie state (two-layer structure, mandatory)

The two layers must remain independently adjustable: Layer 1 captures team defensive process; Layer 2 applies a goalie-specific multiplier on top. The key scenario this structure captures: a team with strong defensive structure (low xGA in Layer 1) starts a weak backup on a back-to-back. Layer 2 downgrades the effective goalie quality substantially. The net effect is `lambda_opponent` rises moderately — not as much as if the team's defense were poor, but more than team xGA alone would suggest.

**Layer 1 — Team defensive baseline** (feeds `lambda_opponent` for whichever side is defending)

| Feature name | Source column(s) | Transformation | Leakage risk |
|---|---|---|---|
| `home_xga_rolling_20` | `home_xgoals_against` (MoneyPuck) | Rolling mean, last 20 home-team games, current season, game_date strictly < current | None — all prior games |
| `home_shots_against_rolling_20` | `home_shots_on_goal` (MoneyPuck, away side in prior games where team was home or away) | Rolling mean, last 20 games, normalized per-60 using `home_goalie_toi`; fallback: raw per-game | None |
| `home_hd_shots_against_rolling_20` | `home_hd_shots_against` (MoneyPuck) | Rolling mean, last 20 games | None |
| `away_xga_rolling_20` | `away_xgoals_against` | Same rolling construction, away team's perspective | None |
| `away_shots_against_rolling_20` | `away_shots_on_goal` (away side) | Same | None |
| `away_hd_shots_against_rolling_20` | `away_hd_shots_against` | Same | None |

**Layer 2 — Goalie adjustment** (shifts `lambda_home` or `lambda_away` relative to team baseline)

All Layer 2 features are tracked per-goalie using `home_goalie_id` / `away_goalie_id` as the grouping key to ensure that starts by different goalies on the same team are not conflated.

| Feature name | Source column(s) | Transformation | Leakage risk |
|---|---|---|---|
| `home_goalie_sv_pct_rolling_10` | `home_goalie_ga`, `home_goalie_sa` | Per-start SV% = `1 - (ga/sa)`; rolling mean of last 10 starts by this goalie_id, current season, game_date < current | None — prior starts only |
| `home_goalie_vs_team_baseline` | `home_goalie_sv_pct_rolling_10` + team-average goalie SV% over same window | `home_goalie_sv_pct_rolling_10` minus the rolling mean SV% across all goalies who started for this team in the same 10-start window; captures starter vs backup dropoff | None — all prior game data |
| `home_goalie_fatigue` | `home_goalie_starter`, `home_goalie_id`, `game_date` | Count of starts by this goalie_id in the 7 calendar days before `game_date`, current season | None |
| `home_goalie_b2b` | `home_goalie_starter`, `home_goalie_id`, `game_date` | Boolean: 1 if this goalie_id started in a game with `game_date = current_game_date - 1`, current season | None |
| `home_backup_flag` | Live pregame source (not in canonical table) | Boolean: 1 if confirmed starter is not the team's primary starter by games-started rank through prior game. **Same-day live data.** | YES — requires pregame confirmation. See Section 4 for live source. |
| `away_goalie_sv_pct_rolling_10` | `away_goalie_ga`, `away_goalie_sa` | Mirror of home construction | None |
| `away_goalie_vs_team_baseline` | `away_goalie_ga`, `away_goalie_sa`, grouped by `away_goalie_id` | Rolling SV% of tonight's confirmed away starter (last 10 starts) minus rolling average goalie quality across all starters used by the away team over the same window; captures starter vs backup dropoff explicitly | None — all prior game data |
| `away_goalie_fatigue` | `away_goalie_id`, `game_date` | Mirror | None |
| `away_goalie_b2b` | `away_goalie_id`, `game_date` | Mirror | None |
| `away_backup_flag` | Live pregame source | Mirror | YES — same-day live data |

**Notes on Layer 1 / Layer 2 separability:** `lambda_home` is computed using Layer 2 goalie features for the home goalie (who faces away shots) combined with Layer 1 defensive process for the away team (who generates shots). Concretely: `lambda_home` is the model's prediction of home goals scored, so it consumes away defensive Layer 1 features and home offensive features plus the away goalie's Layer 2 adjustment. The feature vectors for Model H and Model A are assembled accordingly and documented explicitly in Phase 3.

---

### B. Team offensive process

| Feature name | Source column(s) | Transformation | Leakage risk |
|---|---|---|---|
| `home_xgf_rolling_20` | `home_xgoals` (MoneyPuck) | Rolling mean, last 20 team games, game_date < current, current season | None |
| `home_shots_for_rolling_20` | `home_shots_on_goal` | Rolling mean, last 20 games | None |
| `home_hd_shots_for_rolling_20` | `home_hd_shots` | Rolling mean, last 20 games | None |
| `away_xgf_rolling_20` | `away_xgoals` | Mirror | None |
| `away_shots_for_rolling_20` | `away_shots_on_goal` | Mirror | None |
| `away_hd_shots_for_rolling_20` | `away_hd_shots` | Mirror | None |

---

### C. Team defensive process

| Feature name | Source column(s) | Transformation | Leakage risk |
|---|---|---|---|
| `home_xga_rolling_20` | `home_xgoals_against` | Rolling mean (same as Layer 1 above — this feature serves double duty) | None |
| `home_shots_against_rolling_20` | `home_hd_shots_against` | Rolling mean | None |
| `home_hd_shots_against_rolling_20` | `home_hd_shots_against` | Rolling mean | None |
| `away_xga_rolling_20` | `away_xgoals_against` | Mirror | None |
| `away_shots_against_rolling_20` | `away_shots_on_goal` (opponent perspective) | Mirror | None |
| `away_hd_shots_against_rolling_20` | `away_hd_shots_against` | Mirror | None |

---

### D. Special teams

| Feature name | Source column(s) | Transformation | Leakage risk |
|---|---|---|---|
| `home_pp_pct_rolling_20` | `home_pp_pct` (canonical per-game) | Rolling mean, last 20 games with `home_pp_opportunities > 0`; null-safe (exclude games with 0 opportunities from denominator) | None |
| `home_pk_pct_rolling_20` | `home_pk_pct` (canonical per-game) | Rolling mean, last 20 games with `away_pp_opportunities > 0` for home team | None |
| `home_pp_opp_per_game_rolling_20` | `home_pp_opportunities` | Rolling mean, last 20 games | None |
| `away_pp_pct_rolling_20` | `away_pp_pct` | Mirror | None |
| `away_pk_pct_rolling_20` | `away_pk_pct` | Mirror | None |
| `away_pp_opp_per_game_rolling_20` | `away_pp_opportunities` | Mirror | None |

---

### E. Rest and schedule

| Feature name | Source column(s) | Transformation | Leakage risk |
|---|---|---|---|
| `home_days_rest` | `home_rest_days` (canonical) | Direct use; None if first game of season | None |
| `away_days_rest` | `away_rest_days` | Direct | None |
| `home_b2b` | `home_is_b2b` | Direct boolean | None |
| `away_b2b` | `away_is_b2b` | Direct boolean | None |
| `home_games_last_7` | `home_games_last_7` | Direct integer count | None |
| `away_games_last_7` | `away_games_last_7` | Direct | None |

---

### F. Recent scoring form

| Feature name | Source column(s) | Transformation | Leakage risk |
|---|---|---|---|
| `home_goals_scored_rolling_10` | `home_score` (when team is home) + `away_score` (when team is away) | Rolling mean goals scored per game, last 10 team games regardless of home/away, game_date < current, current season | None |
| `away_goals_scored_rolling_10` | Same construction for away team | Mirror | None |
| `home_goals_allowed_rolling_10` | Opponent's score in each of home team's last 10 games | Rolling mean | None |
| `away_goals_allowed_rolling_10` | Mirror | Mirror | None |

Rolling windows for Section F use 10 games (shorter than the 20-game process windows) to capture recent momentum. Both windows are correct — process windows use 20 games for stability; form windows use 10 games for recency sensitivity.

---

### F2. Shot pressure, danger pressure, and penalty volume

All six features in this section share the same rolling window rules:
- Rolling 20-game window
- `game_date` strictly less than current `game_date` — no same-game data
- Season boundaries reset the window to empty (no cross-season carry-over)
- Shrinkage toward current-season league average applies when fewer than 20 games are available (Section 6 rules)

| Feature name | Source column(s) | Transformation | Leakage risk |
|---|---|---|---|
| `home_shot_pressure` | `home_shots_for`, `away_shots_against` (MoneyPuck) | `home_shots_for_rolling_20 − away_shots_against_rolling_20`; rolling mismatch proxy — positive value means home team generating more shot volume than away team suppresses; rolling_20 window, game_date < current, season resets | None — both inputs derived from prior games only |
| `away_shot_pressure` | `away_shots_for`, `home_shots_against` (MoneyPuck) | `away_shots_for_rolling_20 − home_shots_against_rolling_20`; same construction, away perspective; rolling_20, game_date < current, season resets | None |
| `home_hd_pressure` | `home_hd_shots_for`, `away_hd_shots_against` (MoneyPuck) | `home_hd_shots_for_rolling_20 − away_hd_shots_against_rolling_20`; danger-level version of shot pressure — isolates high-danger chances generated vs suppressed; rolling_20, game_date < current, season resets | None |
| `away_hd_pressure` | `away_hd_shots_for`, `home_hd_shots_against` (MoneyPuck) | `away_hd_shots_for_rolling_20 − home_hd_shots_against_rolling_20`; mirror of home construction; rolling_20, game_date < current, season resets | None |
| `home_penalties_taken_rolling_20` | `away_pp_opportunities` (canonical per-game) | Rolling_20 mean of `away_pp_opportunities` per game; equals this team's penalties taken per game entering tonight; rolling_20, game_date < current, season resets | None |
| `away_penalties_taken_rolling_20` | `home_pp_opportunities` (canonical per-game) | Rolling_20 mean of `home_pp_opportunities` per game; equals this team's penalties taken per game entering tonight; mirror of above; rolling_20, game_date < current, season resets | None |

**Note on derivation:** All four pressure features are derived at feature-construction time from the rolling means already defined in Sections B and C. They require no additional raw canonical columns beyond `home_shots_on_goal`, `home_hd_shots`, `home_hd_shots_against`, and their away mirrors — all of which are already present in the canonical table from MoneyPuck.

**Note on penalties source:** `home_pp_opportunities` and `away_pp_opportunities` are the only per-game penalty proxy available in the canonical table. A team's penalties taken in a game equals the opponent's PP opportunities in that same game. No additional data source is required.

---

### G. Home/away factors

| Feature name | Source column(s) | Transformation | Leakage risk |
|---|---|---|---|
| `is_home` | Implicit (Model H is always for home team; Model A for away) | The models are team-side-specific so home ice is absorbed into the asymmetric training data rather than as an explicit feature. No boolean is needed since each model is trained only on the corresponding team side. | None |

**Home ice adjustment:** Rather than an explicit dummy variable, home ice advantage is captured structurally: Model H is trained using home-team features as offensive inputs and away-team features as defensive inputs; Model A is the reverse. The intercepts of the two models will naturally estimate the mean home/away scoring asymmetry. An explicit `is_home` boolean would be redundant in this structure. If out-of-sample residuals reveal systematic home/away bias, an explicit adjustment term will be added in Phase 4.

---

### H. Market prior — decision

**Decision: Exclude `closing_total` and all market-derived fields from ridge model inputs (option a) for v1.**

**Justification:** The purpose of the model is to produce a projection that is independent of the market. If `closing_total` is included as a ridge feature, the model will learn to track the market rather than the underlying game process. This creates a circular dependency: the projection would partially mirror the line we are comparing it against, making it impossible to detect genuine edge. Even a small ridge coefficient on `closing_total` would pull `projected_total` toward the closing line and compress estimated edge toward zero.

`closing_total` is used in exactly one place: the market integration layer (Section 7), after the projection is finalized. It is compared against `projected_total` but never fed back into the models that produce it.

**Implication for deployment:** The model runs entirely off team-process and goalie features available before puck drop. The closing line is fetched separately and only used in the final edge calculation. This also means the model can produce projections even when no market line is available, which is useful for monitoring.

---

## 4. LEAKAGE AUDIT

### Hard rules

1. **All rolling and statistical features** use only rows where `game_date < current game_date`. No same-game data. This is enforced by computing features as of the prior game in the sorted game sequence.

2. **Season boundaries reset all rolling windows.** A team's rolling window on October 15 of season N contains only games from season N. It does not carry forward any game from season N-1. This is consistent with the canonical table's enrichment approach and with the known non-stationarity between NHL seasons (roster changes, rule adjustments, coaching changes).

3. **No cross-season contamination in training rows.** Training rows for a game on Date D may only include rolling features computed from games with `game_date < D` and `season_year == current season_year`. The feature construction code in Phase 3 must enforce this with an explicit season-boundary filter inside every rolling computation.

4. **Validation and OOS seasons are not visible during training feature construction.** Rolling window calculations for training rows (2021-22, 2022-23) must be computed in a pipeline that has access only to training-season game rows. The validate and OOS seasons are held out entirely until the model is frozen.

### Features that require same-day live data

The following features cannot be computed from canonical historical data alone. They require a live data feed consulted before each game's puck drop.

| Feature | Why same-day | Live source | Timing |
|---|---|---|---|
| `home_backup_flag` | The confirmed starting goalie is announced ~60–90 minutes before puck drop. Historical data records who started, but tomorrow's starter is unknown until game-day. | NHL Stats API `/v1/gamecenter/{gameId}/boxscore` (pregame state) or `/v1/game/{gameId}/feed/live` | 60–90 min before puck drop |
| `away_backup_flag` | Same | Same endpoint | Same |
| Confirmed starting goalie identity (to select correct `goalie_sv_pct_rolling_10`) | Goalie must be confirmed to select the correct goalie_id rolling stats | Same endpoint; fallback to injury/lineup reports | Same |

**Handling in training:** During training, the confirmed starter is known retroactively from `home_goalie_id` and `away_goalie_id` in the canonical table. The `home_backup_flag` is approximated historically by ranking goalies by games-started within each team-season and flagging any starter who is not the team's top-ranked starter as a backup. This retroactive approximation is explicitly labeled as an approximation — in live deployment, the flag comes from the confirmed pregame announcement, which is more accurate.

**All other features** (Sections B, C, D, E, F) are computed entirely from historical game data with `game_date < current game_date` and carry no leakage risk.

---

## 5. TRAINING / VALIDATION / OOS SPLIT

| Split | Seasons | Games | Role |
|---|---|---|---|
| **Train** | 2021-22, 2022-23 | 2,624 | Ridge model fitting, hyperparameter cross-validation (time-series CV within train split only) |
| **Validate** | 2023-24 | 1,312 | Model selection, calibration assessment, provisional threshold calibration |
| **OOS** | 2024-25 | 1,312 | Final performance evaluation; not touched until model is frozen post-validation |

**Explicit confirmation:** No data from the 2023-24 (validate) or 2024-25 (OOS) seasons appears in any rolling window calculation for training rows. The feature construction pipeline in Phase 3 enforces this by:
1. Sorting all games by `(season_year, game_date)`
2. For each training row, computing rolling features using only rows where `season_year == current season_year AND game_date < current game_date AND season_year IN (2021, 2022)`
3. The validate and OOS game rows are never included in any join, aggregate, or rolling computation used to produce training features

**Cross-validation within train:** Hyperparameter tuning (ridge alpha selection) uses time-series cross-validation within the 2021-22 and 2022-23 seasons. Specifically: train on 2021-22, validate on 2022-23 (one fold); this mirrors the train/validate split structure and avoids standard k-fold which would leak future games into training windows.

**Note on 2024-25 completeness:** The canonical table contains all 1,312 regular-season games of the 2024-25 season through April 17, 2025. The OOS designation is correct regardless — this season's data is held out entirely and evaluated only after the model trained on 2021-22/2022-23 and validated on 2023-24 is frozen.

---

## 6. MISSING DATA RULES

### Goalie not yet confirmed at prediction time

Use the team's **rolling mean goalie quality** over the last 10 starts by any goalie for that team in the current season. This is the team-level baseline from Layer 1 of the goalie structure. The goalie adjustment (Layer 2) is set to zero (neutral multiplier). `home_backup_flag` is set to `null` (unknown, not 0 or 1). The prediction is produced but flagged with `goalie_confirmed_flag = False`. Users of the model output should treat such predictions as lower-confidence.

### MoneyPuck data unavailable for a recent game

MoneyPuck data lags by 1–2 days for very recent games. If a game within a rolling window is missing MoneyPuck columns (`home_xgoals` is null), that game is **excluded from the rolling denominator** — i.e., treat it as if the game does not exist for the purposes of that rolling window. Do not impute zero. Do not impute the team mean. Simply skip the game. If this reduces the effective window below 5 games, apply the small-sample shrinkage rule below. In live deployment, MoneyPuck-dependent features for the most recent 1–2 games may be temporarily unavailable; the fallback is to use the rolling value computed from all available prior games with valid MoneyPuck data.

### Market line unavailable

The prediction pipeline always runs. `projected_total`, `lambda_home`, `lambda_away`, `sim_over_prob`, `sim_under_prob`, and `sim_push_prob` are always produced. If `closing_total` is null: `edge_over`, `edge_under`, `closing_total_bucket`, and `confidence_tier` are set to null. No bet recommendation is emitted. The record is still written to the output table with `market_available = False`.

### Team played fewer than 5 games in lookback window

Apply **Bayesian shrinkage toward the current-season league average**. The shrinkage formula for any rolling statistic `stat`:

```
shrunk_stat = w * raw_rolling_mean + (1 - w) * current_season_league_avg
w = min(n_games_available, 20) / 20
```

At 0 games: 100% league average. At 5 games: 25% raw + 75% league average. At 20+ games: 100% raw rolling mean. This is a linear interpolation between league average (reliable prior) and raw sample (noisy but team-specific).

`current_season_league_avg` is computed from all games completed in the current season as of the prediction date, using only `game_date < current game_date`. It is not a hardcoded constant — it updates daily as the season progresses.

"Use available games" alone (without shrinkage) is rejected because early-season raw estimates from 2–4 games have variance high enough to produce nonsensical lambdas (e.g., a team that allowed 8 goals in game 1 and 0 in game 2 has a raw xGA mean that is meaningless as a model input).

### Rolling window spans season boundary

The window **resets to empty at the start of each season**. There is no carry-over. A team playing game 3 of the new season has an effective window of 2 games, and shrinkage applies as described above. This is the correct behavior even though it means less information is available early in the season — the alternative (carrying over prior-season stats) introduces stale information from a roster, coaching, or stylistic context that may have changed substantially. If early-season predictive accuracy is materially worse than mid-season accuracy, the shrinkage prior (prior-season team mean vs current-season league mean) is the Phase 4 candidate adjustment.

---

## 7. MARKET INTEGRATION

### Closing total bucket

```python
def bucket(line):
    if line == 5.5: return "5.5"
    if line == 6.0: return "6.0"
    if line == 6.5: return "6.5"
    return "other"
```

`closing_total_bucket` captures the four distinct line values observed in 2023-24 (5.5, 6.0, 6.5, 7.0). Lines outside {5.5, 6.0, 6.5} are bucketed as "other." The distribution from 2023-24 was: 6.5 (49%), 6.0 (40%), 5.5 (8%), 7.0 (4%).

### Projected total comparison

```
projected_total = lambda_home + lambda_away
raw_edge_over   = projected_total - closing_total   (positive → model sees more goals than market)
raw_edge_under  = closing_total - projected_total   (positive → model sees fewer goals than market)
```

`raw_edge_over` and `raw_edge_under` are the **goals-based edge** in the same units as the closing line. These are intuitive but do not account for Poisson shape or vig. The probability-based edge below is used for bet qualification.

### Probability-based edge

Market implied probabilities are computed from American odds with vig removed:

```
implied_over_raw  = 100 / (over_price + 100)   if over_price > 0
                  = |over_price| / (|over_price| + 100)  if over_price < 0

implied_under_raw = 100 / (under_price + 100)  if under_price > 0
                  = |under_price| / (|under_price| + 100) if under_price < 0

vig_factor        = implied_over_raw + implied_under_raw   (> 1.0 due to vig)
implied_over_fair  = implied_over_raw / vig_factor
implied_under_fair = implied_under_raw / vig_factor

edge_over  = sim_over_prob  - implied_over_fair
edge_under = sim_under_prob - implied_under_fair
```

This uses the vig-normalized implied probability as the fair benchmark. `sim_over_prob` and `sim_under_prob` are the raw Poisson simulation probabilities (not push-conditional) as defined in Section 1.

### Provisional signal threshold

**Candidate threshold (provisional — must be validated empirically after calibration):**

A prediction qualifies for a bet recommendation if:
- `edge_over >= 0.04` OR `edge_under >= 0.04` (4 percentage point edge over vig-normalized fair line), AND
- `confidence_tier` is HIGH or MEDIUM (see Section 8 for tier definition), AND
- `goalie_confirmed_flag = True` for both teams

A 4pp threshold is chosen as the provisional starting point based on the range at which Poisson model edges in comparable sports (MLB totals) have historically shown positive EV at standard vig. **This is not derived from NHL validation data.** The final threshold must be set by examining the calibration curve on the 2023-24 validation season — specifically, the relationship between `edge_over` and observed over-rate across the validation set. The threshold will be moved up or down based on that curve.

### Push handling in probability computation

`sim_push_prob` is the fraction of simulated games where `simulated_total == closing_total`. At a line of 6.0, this is approximately `P(X+Y=6)` under the bivariate Poisson with the given lambdas. At half-point lines, `sim_push_prob = 0` by definition.

`sim_over_prob + sim_under_prob + sim_push_prob = 1.0` exactly (enforced by simulation construction).

When comparing against market implied probability: the market at a half-point line has `implied_over_fair + implied_under_fair ≈ 1.0` (no push mass). At an integer line, the market's implied probs do not explicitly quote push odds — the push is absorbed into the return of stake. The vig-normalized implied probs still sum to 1.0 from the market's two-sided quote. The model's raw `sim_over_prob` (which includes push as a separate mass) is therefore an apples-to-apples comparison because it represents the probability of winning the bet as stated.

---

## 8. OUTPUT SPEC

One prediction record per game, produced daily before first puck drop. All fields explicitly defined.

| Field | Type | Definition |
|---|---|---|
| `game_id` | string | NHL Stats API game ID from canonical table |
| `game_date` | date | YYYY-MM-DD, local market date |
| `home_team` | string | 3-letter NHL abbreviation |
| `away_team` | string | 3-letter NHL abbreviation |
| `lambda_home` | float | Expected goals for home team (Model H output); same units as `home_score` |
| `lambda_away` | float | Expected goals for away team (Model A output) |
| `projected_total` | float | `lambda_home + lambda_away`; the model's total expected goals |
| `sim_over_prob` | float | P(simulated total > closing_total); null if `closing_total` is null |
| `sim_under_prob` | float | P(simulated total < closing_total); null if `closing_total` is null |
| `sim_push_prob` | float | P(simulated total == closing_total); 0.0 for half-point lines; null if `closing_total` is null |
| `closing_total` | float | Market closing line (from `total_line` in canonical; null if unavailable) |
| `closing_total_bucket` | string | "5.5" / "6.0" / "6.5" / "other" / null |
| `edge_over` | float | `sim_over_prob - implied_over_fair`; null if `closing_total` or odds unavailable |
| `edge_under` | float | `sim_under_prob - implied_under_fair`; null if unavailable |
| `confidence_tier` | string | "HIGH" / "MEDIUM" / "LOW" / null — see tier framework below |
| `home_goalie_confirmed` | boolean | True if confirmed starting goalie for home team is known before puck drop |
| `away_goalie_confirmed` | boolean | True if confirmed starting goalie for away team is known before puck drop |
| `home_backup_flag` | boolean / null | True if home starting goalie is not team's primary starter; null if goalie unconfirmed |
| `away_backup_flag` | boolean / null | Mirror |

### Confidence tier framework (provisional)

Tiers are driven by three variables: (1) absolute edge magnitude, (2) goalie confirmation status, and (3) effective rolling window size (sample reliability). Final thresholds must be calibrated empirically on the 2023-24 validation season.

**Provisional definitions:**

| Tier | Conditions (all must hold) |
|---|---|
| **HIGH** | `edge_over >= 0.06` OR `edge_under >= 0.06`, AND `home_goalie_confirmed = True` AND `away_goalie_confirmed = True`, AND both teams have ≥ 15 games in rolling windows, AND neither team is on a back-to-back with a confirmed backup |
| **MEDIUM** | `edge_over >= 0.04` OR `edge_under >= 0.04`, AND at least one goalie confirmed, AND both teams have ≥ 10 games in rolling windows |
| **LOW** | `edge_over >= 0.02` OR `edge_under >= 0.02`, OR either goalie unconfirmed, OR rolling window < 10 games for either team |
| **null** | `closing_total` unavailable; no edge can be computed |

The 0.06 / 0.04 / 0.02 thresholds are provisional starting points, not empirically derived. They will be replaced with validated thresholds after examining the calibration curve on the 2023-24 validation season.

**Variables that drive tier assignment:**
1. `edge_over` / `edge_under` — primary signal magnitude
2. `home_goalie_confirmed`, `away_goalie_confirmed` — pregame information completeness
3. Effective rolling window size (n_games used in rolling features) — data reliability
4. `home_backup_flag`, `away_backup_flag` — lineup completeness and reliability of Layer 2 goalie adjustment

---

*Phase 3 does not begin until this document is reviewed and approved.*
