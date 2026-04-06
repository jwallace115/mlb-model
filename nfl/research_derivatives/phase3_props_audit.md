# NFL Player Props Audit — Phase 3

**Date:** 2026-04-06
**Season:** 2025 NFL (284-285 games, 2.3M prop rows)

---

## Verdict: GO NOW on player_receptions with role-redistribution hypothesis

The props archive has excellent coverage, actuals match at 96%, and the receptions
market shows a specific structural bias pattern worth testing immediately.

---

## Step 1 — Props Archive Summary

| Market | Rows | Games | Players | Books | Line Med | Snapshots/Player-Game |
|--------|------|-------|---------|-------|----------|----------------------|
| **player_receptions** | **373K** | **284** | **379** | **8** | **2.5** | **102** |
| **player_reception_yds** | **391K** | **285** | **384** | **8** | **26.5** | **103** |
| player_rush_yds | 185K | 283 | 196 | 8 | 30.5 | 104 |
| player_rush_attempts | 100K | 283 | 177 | 7 | 12.5 | — |
| player_pass_yds | 71K | 285 | 63 | 8 | 222.5 | — |
| player_anytime_td | 954K | 285 | 687 | 8 | — | — |

**Best markets for research:** `player_receptions` and `player_reception_yds`.
Both have ~100 snapshots per player-game (multi-snapshot opener→close history),
380+ players, 8 bookmakers, and 284+ games.

---

## Step 2 — Actuals Coverage

| Source | Rows | Players | Coverage |
|--------|------|---------|----------|
| nflverse player_stats | 19,421 | 2,019 | 100% for all stat fields |
| Name match to props | 364/379 | — | **96%** |
| Injuries | 6,068 reports | 1,453 players | Out/Questionable/Doubtful |
| Snap counts | 26,612 | 2,185 | offense_pct, defense_pct |
| Target share | 5,634 WR/TE/RB games | — | 100% (derivable) |

**Unmatched names (4%):** Minor formatting differences (e.g., "AJ Brown" vs
"A.J. Brown", "Brian Thomas Jr" vs "Brian Thomas Jr."). Fixable with simple
normalization.

---

## Step 3 — Market Efficiency Baseline

### player_receptions (N=3,376 matched player-game-weeks)

| Metric | Value |
|--------|-------|
| Over rate | **46.4%** |
| Under rate | 53.2% |
| Push rate | 0.4% |
| MAE | 1.45 receptions |
| Mean bias | +0.055 (slight over bias) |

### By Line Bucket

| Bucket | N | Over Rate | MAE | Bias |
|--------|---|-----------|-----|------|
| 0-2 | 1,185 | **0.512** | 1.09 | **+0.29** |
| 2-3 | 833 | 0.442 | 1.41 | -0.00 |
| 3-4 | 612 | 0.462 | 1.63 | +0.09 |
| 4-5 | 419 | **0.408** | 1.79 | **-0.26** |
| 5-7 | 292 | **0.421** | 2.04 | **-0.29** |
| 7+ | 35 | 0.400 | 2.57 | -0.60 |

**Key finding:** The market is well-calibrated in the middle (2-3 receptions:
perfectly balanced) but shows systematic bias at the tails:
- **Low lines (0-2):** Over hits 51.2% — market slightly underprices low-usage
  players' receptions (these are RB/TE/WR3 types)
- **High lines (4-7+):** Over hits only 40-42% — market overprices high-usage
  receivers' receptions

This is a structural pattern: markets may anchor too heavily on season averages
for both tails. Low-usage players get slightly more receptions than the market
expects; high-usage players get slightly fewer.

### player_reception_yds (N=3,478)

| Metric | Value |
|--------|-------|
| Over rate | 48.1% |
| MAE | 18.7 yards |
| Bias | +4.0 yards (under-priced) |

Yards are noisier but show a similar slight over-lean.

---

## Step 4 — Structural Hypotheses

### H1: Role Redistribution Under WR1 Absence
**Mechanism:** When a team's WR1 is OUT or LIMITED, the market adjusts their
line downward but may underestimate how much target share redistributes to
the WR2, slot, and TE — particularly receptions (not just yards).

**Data needed:** Injury reports (available: 6,068 rows), snap counts (available),
target share history (derivable), prior-week WR1 target share.

**Already priced?** Partially — markets adjust WR1's line down. But they may
not fully adjust WR2/TE upward, especially for receptions. The low-line
bucket over-rate of 51.2% is consistent with role-redistribution boosting
secondary options.

**Feasibility: GO NOW** — all data exists.

### H2: Checkdown/Short-Route Spike Under Pressure
**Mechanism:** When a team faces a high-pressure defense, the QB's time to
throw decreases. This benefits short-route receivers (slot WR, RB, TE) in
receptions but not necessarily in yards. The market prices receiving yards
from season averages but may not adjust receptions for matchup-specific
pressure environments.

**Data needed:** Defensive pressure rate (derivable from PBP sacks + qb_hits),
receiver route depth (partially available via air_yards), position data.

**Already priced?** Less likely — pressure is a matchup-specific variable that
changes week to week. Season-average pressure rates are known but
game-specific pressure adjustment for each receiver role is harder to price.

**Feasibility: PARTIAL GO** — need to build pressure features from PBP.

### H3: TE Reception Spike in Red-Zone Heavy Games
**Mechanism:** In games projected to have high scoring (high total), TEs see
disproportionate target increases in the red zone. The receptions market
prices overall target share but may not adjust for the scoring-environment
effect on TE targets specifically.

**Data needed:** Red-zone target share by position (derivable from PBP with
yard line data), game total projection.

**Already priced?** Likely partially — TEs in high-total games may already
have adjusted lines. But the interaction between game total and TE role is
non-obvious.

**Feasibility: PARTIAL GO** — red-zone features need to be built.

### H4: Low-Line Over Bias Exploitation (Direct)
**Mechanism:** The 0-2 receptions bucket shows 51.2% over rate. This is the
simplest possible angle: bet OVER on all low-line reception props and collect
the structural bias.

**Data needed:** Already available — just the closing line.

**Already priced?** The vig likely absorbs most of this. At -110, 51.2% over
rate produces ROI of -2.5%. Not profitable standalone. But as a filter
for which low-line players to target with role-redistribution support, it
stacks with H1.

**Feasibility: GO NOW but not standalone** — use as a base-rate tilt, not a signal.

---

## Step 5 — Feasibility Verdict

### GO NOW

**Best first hypothesis: H1 (Role Redistribution Under WR1 Absence)**

Why:
1. All data exists: injury reports, snap counts, target share, props archive
2. The low-line over bias (51.2%) provides a base-rate tailwind for secondary
   receivers getting more targets than expected
3. Role redistribution is a structural state change — exactly the type of
   non-obvious effect that markets handle imperfectly
4. WR1 absence is a discrete, observable event — not a continuous variable
   that markets can smoothly price
5. The receptions market has 373K rows, 102 snapshots per player-game, 8
   bookmakers — plenty of data for a clean test

### Recommended Test Design

1. Identify weeks where each team's WR1 was OUT or LIMITED (from injury reports)
2. For those weeks, check WR2/WR3/TE/RB reception actuals vs closing lines
3. Compare over-rate in WR1-absent weeks vs WR1-present weeks
4. Control for team, opponent defensive quality, and game script
5. If the over-rate for secondary receivers is >53% in WR1-absent weeks,
   there may be a usable role-redistribution edge

**Minimum success threshold:** Over rate >= 53% for secondary receivers in
WR1-absent games, with N >= 100 and directional consistency across team groups.
