# NFL H1 Structural Regime Audit — Phase 1

**Date:** 2026-04-06
**Season:** 2025 NFL (284 games with H1 actuals, 221 with H1 closing lines)
**Source:** nflverse play-by-play → H1 structural features, rolling 4-game windows

---

## Verdict: PARTIAL GO

Promising H1 structural features exist and are cleanly derivable from play-by-play.
However, individual feature correlations with H1 totals are weak (r < 0.15), and
the H1 market close itself only correlates at r=0.173 with actuals — meaning H1
outcomes are inherently noisy. Regime design is feasible but must account for this
high-noise environment.

**Best single regime family to test first: OFFENSIVE SCRIPT SHAPE** (pace ×
efficiency × explosiveness interaction).

---

## Phase 1 — Feature Audit

### Data Source
- `nflreadpy.load_pbp([2025])` — 48,771 plays, 372 columns
- H1 plays: 24,323 (50% of total), 285 unique games
- All features derived from PBP only — no market inputs

### Feature Family Coverage

| Family | Key Features | Coverage | PBP Column Source |
|--------|-------------|----------|------------------|
| **A) Pace** | h1_plays, no_huddle_rate | 89% (rolling r4) | play counts, no_huddle flag |
| **B) Script** | pass_rate, pass_oe, shotgun_rate | 89% | pass_attempt, rush_attempt, pass_oe, shotgun |
| **C) Efficiency** | epa_per_play, success_rate, series_success, first_downs | 89% | epa, success, series_success, first_down |
| **D) Disruption** | sack_rate, turnover_rate, qb_hits | 89% | sack, qb_hit, fumble, interception |
| **E) Explosiveness** | explosive_rate (20+ yard plays), yards_per_play | 89% | yards_gained >= 20 |
| **F) Split/Asymmetry** | H1 vs full-game differences | Requires multi-year | Would need 2024 PBP |
| **G) Participation** | QB/coordinator continuity | Not cleanly derivable yet | Player name tracking only |

**Strongest families: A + B + C + E** — all at 89% rolling coverage, cleanly
derivable, H1-specific.

**Weakest families: F (multi-year), G (requires external roster data).**

### Top Feature Correlations with H1 Total

| Feature | r | N | Notes |
|---------|---|---|-------|
| home_def_h1_def_explosive_rate_r4 | +0.147 | 252 | Defense allowing explosive plays |
| away_def_h1_def_series_success_rate_r4 | +0.132 | 252 | Away D allowing series conversions |
| home_def_h1_def_yards_per_play_r4 | +0.126 | 252 | Defense yards per play allowed |
| home_off_h1_touchdowns_r4 | +0.121 | 252 | Offensive TD scoring tendency |
| home_off_h1_first_downs_r4 | +0.113 | 252 | First-down production |
| away_off_h1_series_success_rate_r4 | +0.107 | 252 | Away offensive series efficiency |
| home_off_h1_plays_r4 | +0.107 | 252 | Pace/volume |
| home_off_h1_no_huddle_rate_r4 | +0.096 | 252 | No-huddle tempo |

**Market baseline:** H1 closing line vs actual r=0.173. Individual structural
features are in the 0.07-0.15 range — below the market but potentially additive
in combination or as regime labels.

---

## Phase 2 — Regime Candidate Families

### R1: OFFENSIVE SCRIPT SHAPE
**Inputs:** pass_rate, explosive_rate, epa_per_play, no_huddle_rate, sack_rate
**Why not Vegas:** These are play-by-play structural shapes, not scoring averages.
A team can have the same scoring average but very different script profiles
(grind vs chunk, aggressive vs conservative, fast vs slow).
**H1 relevance:** Script-driven teams execute their game plan in the first half
before adjustments. Script shape may predict H1 scoring style better than raw
totals indicate.

### R2: DEFENSIVE VULNERABILITY SHAPE
**Inputs:** def_explosive_rate, def_series_success_rate, def_yards_per_play, def_sack_rate
**Why not Vegas:** Defensive structure (bend-don't-break vs attack vs porous)
is more granular than broad team defense metrics.
**H1 relevance:** Defenses that allow explosive plays early create volatile
H1 scoring environments.

### R3: PACE × EFFICIENCY INTERACTION
**Inputs:** h1_plays (volume) × epa_per_play (quality)
**Why not Vegas:** Pure pace and pure efficiency are known individually, but
their interaction creates distinct game environments that may be mispriced
in derivative markets.
**H1 relevance:** High-pace + high-efficiency = high-scoring H1. Low-pace +
low-efficiency = suppressed H1. The cross-product matters more than either alone.

### R4: DISRUPTION FRAGILITY
**Inputs:** sack_rate, turnover_rate, qb_hits
**Why not Vegas:** Broad offensive quality metrics don't capture how much an
offense degrades under pressure. Some teams maintain efficiency under duress;
others collapse.
**H1 relevance:** First-half scripts are more structured and less adaptive
than second-half play. Disruption-fragile offenses may be more vulnerable
in H1 than their full-game stats suggest.

---

## Phase 3 — Feasibility Screen

| Regime | Data Ready? | Coverage | Vegas Proxy Risk | Sample Size | Best For |
|--------|-------------|----------|-----------------|-------------|----------|
| **R1 Script Shape** | **YES** | 89% | **Low** | 252 games | H1 totals |
| R2 Def Vulnerability | YES | 89% | Medium | 252 games | H1 totals |
| R3 Pace × Efficiency | YES | 89% | Medium-High | 252 games | H1 totals |
| R4 Disruption Fragility | YES | 89% | Low | 252 games | H1 totals, player props |

**R1 (Script Shape)** has the lowest Vegas proxy risk because it measures HOW
teams score, not HOW MUCH. Pass rate + explosive rate + no-huddle rate + sack
rate are structural descriptors that markets may not fully price into H1
derivative lines.

**R3 (Pace × Efficiency)** has the highest proxy risk because pace and
efficiency individually are well-known, and their combination may already be
reflected in the H1 total line.

### Preliminary K=3 Clustering (R1 on home offense only)

| Cluster | N | H1 Total | Pass Rate | Explosive% | EPA/play | No-Huddle% | Sack% |
|---------|---|----------|-----------|-----------|----------|-----------|-------|
| TEMPO (0) | 7 | **27.7** | .526 | .044 | +.008 | **.719** | .037 |
| EFFICIENT (1) | 138 | 23.6 | .575 | .066 | +.117 | .073 | .027 |
| STRUGGLING (2) | 107 | **21.8** | .573 | .042 | -.107 | .065 | .052 |

H1 total spread: 21.8 → 27.7 across clusters (+5.9 points). Cluster 0 is
tiny (N=7, likely BUF/MIA heavy no-huddle games) — would need to be handled
carefully. The EFFICIENT vs STRUGGLING split (23.6 vs 21.8 = +1.8pp) is more
stable but modest.

Market residual: EFFICIENT cluster is -0.8 below market close, STRUGGLING is
-0.4 below. Both negative — the market may already partially price this.

---

## Phase 4 — Prioritization

| Rank | Regime | Data Ready | Vegas Distinct | H1 Useful | Sample Risk | Simplicity |
|------|--------|-----------|---------------|-----------|-------------|------------|
| **1** | **R1 Script Shape** | **A** | **A** | **B+** | **B** | **A** |
| 2 | R4 Disruption | A | A | B | B | A |
| 3 | R2 Def Vulnerability | A | B | B+ | B | B |
| 4 | R3 Pace × Efficiency | A | C | A | B | A |

**Recommendation: Test R1 (Offensive Script Shape) first.**

It has the cleanest non-market inputs, lowest proxy risk, and the most
interpretable cluster descriptions. The initial K=3 showed a meaningful H1
total spread, even if the market already captures some of it.

The test should be:
1. Cluster both home and away offenses into script-shape regimes
2. Build 3×3 matchup cells (home offense regime × away offense regime)
3. Test whether any cells have H1 total residuals vs the closing line
4. Control for obvious covariates (full-game total, spread, weather)
5. Check both-half-of-season stability

---

## Next Steps

1. Build R1 (Script Shape) regimes for both home and away offenses
2. Build R2 (Defensive Vulnerability) regimes for both home and away defenses
3. Test 3×3 offense vs offense cells for H1 total residuals
4. If promising, add defense dimension (3×3×3 = 27 cells, likely too fragmented —
   may need to collapse to 3×3×2 or similar)
5. Control for market-known context before claiming any structural edge
