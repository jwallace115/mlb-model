# SEEP Phase 3 — Exit Path Quality Classification

**Date:** 2026-04-07
**Status:** CLOSE
**Reason:** Classifier fails to meaningfully separate UNSTABLE-SHORT from MANAGED-SHORT above base rate; 84% base rate leaves no room for a useful filter. F5 OOS sample (N=8 scored) is directionally interesting but far too thin to support any operational rule.

---

## Phase 1 — Label Construction

**Source:** `mlb/data/pitcher_game_logs.parquet`
**Population:** All starts with `starter_flag == 1`, `IP < 5.0`, `season >= 2022`
**Total early exits:** 5,852

### Classification Rules

| Label | Criteria |
|---|---|
| MANAGED-SHORT | walks <= 1 AND earned_runs <= 2 |
| UNSTABLE-SHORT | walks >= 3 OR earned_runs >= 4 |
| AMBIGUOUS | everything else |

**Refinement:** 538 AMBIGUOUS starts reclassified to UNSTABLE-SHORT via pitches_per_inning > 20 (pitches / IP).

### Distribution

| Label | N | % |
|---|---|---|
| MANAGED-SHORT | 1,170 | 20.0% |
| UNSTABLE-SHORT | 4,220 | 72.1% |
| AMBIGUOUS | 462 | 7.9% |

**Critical observation:** UNSTABLE-SHORT is the *majority class* at 72%. This is the central problem — when a pitcher exits before 5 IP, the overwhelming default is that something went wrong (walks, runs, or inefficiency). Clean early exits are the exception, not the rule.

### By Season

| Season | N | MANAGED | UNSTABLE | AMBIG |
|---|---|---|---|---|
| 2022 | 1,471 | 21.4% | 68.8% | 9.8% |
| 2023 | 1,459 | 21.7% | 72.3% | 6.0% |
| 2024 | 1,401 | 18.6% | 74.0% | 7.4% |
| 2025 | 1,407 | 18.6% | 73.4% | 8.0% |
| 2026 | 114 | 15.8% | 72.8% | 11.4% |

UNSTABLE rate is stable across seasons (69-74%), trending slightly upward. MANAGED-SHORT is declining (21% to 16%).

### April vs Rest-of-Season

| Period | N | MANAGED | UNSTABLE |
|---|---|---|---|
| April | 1,121 | 15.0% | 76.3% |
| Rest | 4,731 | 21.2% | 71.1% |

April has a +5pp UNSTABLE rate vs rest of season. This is expected: cold weather, rust, inconsistent command early. Notably, April is when our F5 UNDER signals are generated, making the classifier's task even harder.

---

## Phase 2 — Pregame Feature Audit

Features computed with cross-season rolling windows (player-level, shifted by 1 start to avoid leakage). Season_walk_rate uses within-season expanding mean, with career fallback for early-season starts.

### Feature Coverage

All features have 91%+ coverage on the full dataset. For 2026 starters, 290/302 (96%) are scorable after career fallback imputation (12 unscorable are true rookies with zero prior starts in the data).

### Feature Means by Label (classifier population, N=3,668)

| Feature | MANAGED | UNSTABLE | Delta |
|---|---|---|---|
| rolling5_walk_rate | 0.080 | 0.082 | +0.002 |
| rolling5_walk_std | 0.065 | 0.056 | -0.009 |
| recent_walk_spike | 0.182 | 0.262 | +0.080 |
| walk_floor | 2.688 | 3.216 | +0.528 |
| rolling5_pitches_per_ip | 19.002 | 18.518 | -0.484 |
| pitches_per_ip_trend | -0.374 | +0.024 | +0.398 |
| rolling5_unstable_count | 1.793 | 2.282 | +0.489 |
| starts_since_last_unstable | 2.532 | 1.302 | -1.230 |
| season_start_number | 12.365 | 13.623 | +1.258 |
| season_walk_rate | 0.080 | 0.084 | +0.003 |

**Key finding:** The largest raw separators are `starts_since_last_unstable` (-1.23 delta) and `walk_floor` (+0.53). However, `rolling5_walk_rate` has almost zero separation (+0.002). Walk rate is not predictive of the *type* of early exit because most early exits are unstable regardless.

The walk_std feature is *inverted* — MANAGED exits have higher walk_std, meaning pitchers with variable walk rates are actually more likely to have a clean short outing. This is counterintuitive and suggests the feature captures something about pitcher type (high-variance pitchers who occasionally get pulled early for non-command reasons) rather than command fragility.

---

## Phase 3 — Classifier Build

**Population:** 3,668 starts (IP < 5.0, MANAGED or UNSTABLE, season_start_number >= 4, seasons 2022-2025)
**Split:** Chronological 70/30 (train through 2024-09-02, test through 2025-09-28)

### Results

| Metric | Value |
|---|---|
| Train N | 2,567 |
| Test N | 1,101 |
| Train UNSTABLE rate | 83.7% |
| Test UNSTABLE rate | 85.2% |
| **ROC AUC** | **0.598** |

### Precision Analysis

| Cohort | N | UNSTABLE Rate |
|---|---|---|
| Base rate (test) | 1,101 | 85.2% |
| Bottom decile (low risk) | 111 | 66.7% |
| Q1 (lowest predicted) | 276 | 78.3% |
| Q2 | 275 | 87.3% |
| Q3 | 275 | 85.1% |
| Q4 (highest predicted) | 275 | 88.7% |
| Top quintile | 221 | 88.7% |
| Top decile | 111 | 87.4% |

**The classifier barely separates.** Q1 to Q4 spans 78.3% to 88.7% — only a 10pp range. The top decile (87.4%) is barely above the 85.2% base rate. Even the *lowest-risk* decile has a 66.7% UNSTABLE rate. There is no clean "safe" cohort.

### Feature Coefficients (standardized)

| Feature | Coefficient | Direction |
|---|---|---|
| walk_floor | +0.925 | Higher max walks -> more unstable |
| rolling5_walk_std | -0.661 | Higher walk variance -> less unstable (inverted) |
| rolling5_walk_rate | -0.257 | Higher walk rate -> less unstable (inverted) |
| season_walk_rate | +0.215 | Higher season walk rate -> more unstable |
| starts_since_last_unstable | -0.174 | More time since last unstable -> less unstable |
| rolling5_pitches_per_ip | +0.164 | More pitches per IP -> more unstable |
| rolling5_unstable_count | -0.123 | Higher recent unstable count -> less unstable (inverted) |
| recent_walk_spike | -0.113 | Recent spike -> less unstable (inverted) |
| pitches_per_ip_trend | -0.020 | Negligible |
| season_start_number | -0.007 | Negligible |

**Multiple features have inverted signs.** `rolling5_walk_rate`, `rolling5_walk_std`, `rolling5_unstable_count`, and `recent_walk_spike` all have negative coefficients (predicting *less* unstable), opposite to the intended direction. This is a red flag: the features are not capturing command fragility in the way hypothesized. The inversions likely reflect confounding — pitchers with chronically high walk rates who exit early sometimes have low-run, managed exits (walked guys but didn't get hit), while pitchers with normally low walk rates who exit early do so because runs scored (hard contact, not walks).

**Interpretation:** The classifier is not learning "command fragility predicts unstable exits." It is learning "pitchers who recently had unstable exits are slightly more likely to have another one" (via `starts_since_last_unstable`) and "pitchers whose worst recent game had many walks are more unstable" (via `walk_floor`), but these signals are weak and largely swamped by the 85% base rate.

---

## Phase 4 — F5 Signal Test

### Scoring Coverage

- Total resolved F5 signals: 52 (48 UNDER, 4 OVER)
- 2026 starters scored: 290 / 302 (96%)
- F5 UNDER signals with BOTH starters scored: **8** (out of 48)
- F5 UNDER signals with at least 1 starter scored: 48

The low both-scored rate (8/48) is because most F5 signals come from games where the pitcher_game_logs data hasn't fully populated yet for early 2026 (new team pairings, rookies). Only Opening Day games and the April 6 game had both starters with sufficient history.

### Step 4.5 — Sanity Check

| Group | N | Win Rate | Mean Line |
|---|---|---|---|
| Both scored UNDER | 8 | 37.5% | 4.06 |
| Not both scored UNDER | 40 | 45.0% | 4.67 |

The scored group has lower lines (4.06 vs 4.67), meaning these are tighter games. The lower win rate may partially reflect line difficulty rather than starter quality.

### F5 UNDER Performance Splits (N=8, both scored)

| Split | N | WR | Net Units | Mean Actual | Mean Line |
|---|---|---|---|---|---|
| A) All UNDER | 8 | 37.5% | -1.70u | 5.38 | 4.06 |
| B) NEITHER starter high risk | 5 | 60.0% | +0.55u | 3.60 | 4.00 |
| C) EITHER starter high risk | 2 | 0.0% | -1.50u | 8.00 | 4.25 |
| D) HOME starter high risk | 2 | 0.0% | -1.50u | 8.00 | 4.25 |
| E) AWAY starter high risk | 2 | 0.0% | -1.50u | 7.50 | 4.25 |
| F) BOTH starters high risk | 1 | 0.0% | -0.75u | 6.00 | 4.50 |

**Direction is correct:** NEITHER high-risk = 60% WR (+0.55u), EITHER high-risk = 0% WR (-1.50u). But this is **N=8 total, N=2 in the high-risk group**. This is not evidence — it is noise.

### Partial Scoring (at least 1 starter, N=48)

| Split | N | WR | Net Units | Mean Actual | Mean Line |
|---|---|---|---|---|---|
| All partial | 48 | 43.8% | -5.18u | 5.25 | 4.57 |
| Low risk (Q1-Q3) | 36 | 41.7% | -4.77u | 5.47 | 4.56 |
| High risk (Q4) | 12 | 50.0% | -0.41u | 4.58 | 4.62 |

With partial scoring, the direction **inverts** — high-risk starters have *better* UNDER performance (50% vs 42%). This contradicts the hypothesis entirely.

---

## Phase 5 — Practical Framing Assessment

| Option | Assessment |
|---|---|
| A) Suppress UNDER when either HIGH | No basis: N=2, inverts with partial scoring |
| B) Suppress when both HIGH | No basis: N=1 |
| C) Suppress home HIGH only | No basis |
| D) Context badge | No value: classifier AUC 0.598, no meaningful separation |
| **E) CLOSE** | **Correct decision** |

---

## Decision: CLOSE

### Primary Reasons

1. **Base rate problem.** 72-85% of early exits are UNSTABLE-SHORT. The question "will this early exit be unstable?" has a trivially dominant answer: yes. A classifier that always predicts UNSTABLE achieves 85% accuracy. The useful question would be "will this pitcher exit early?" — but that is a quality/durability question, which is out of scope for this phase.

2. **Classifier failure.** AUC of 0.598 with an 85% base rate means the model adds almost no information. Top quartile vs bottom quartile spans only 10pp (88.7% vs 78.3%). No cohort achieves below 67% UNSTABLE rate.

3. **Inverted feature coefficients.** Multiple command-fragility features (walk_rate, walk_std, recent_walk_spike, unstable_count) have *negative* coefficients, meaning they predict *less* instability. This means the feature family is not capturing what we hypothesized. The "command fragility" framing does not work because walk propensity is confounded with overall pitcher type.

4. **F5 OOS evidence is insufficient.** Only 8 signals have both starters scored. The directionally correct N=5/N=2 split in the fully-scored group inverts when using partial scoring (N=48). There is no stable signal.

5. **April compounds the problem.** April has a 76% UNSTABLE rate (vs 71% rest of season). Our F5 signals are generated during this period, making the classifier's already-weak separation even less useful.

### What This Tells Us

The Phase 2 finding (leash-state is not predictive within F5 UNDER signals) and Phase 3 finding (exit-type classification fails) converge on the same conclusion: **once a pitcher exits before 5 IP, the mode of exit is not predictable from pregame command indicators.** Early exits are overwhelmingly unstable, and the rare clean early exits (injury, strategic pull, low pitch count) cannot be predicted from walk history or pitch efficiency.

The productive path forward is not "predict which early exits will be messy" but rather "predict which games will have early exits at all" — which is a pitcher durability/quality question outside the SEEP command-fragility scope.

### Files Referenced
- `mlb/data/pitcher_game_logs.parquet` — source data (84,372 rows, 22 columns)
- `mlb_sim/logs/f5_signals_2026.json` — 52 F5 signals (48 UNDER, 4 OVER)
