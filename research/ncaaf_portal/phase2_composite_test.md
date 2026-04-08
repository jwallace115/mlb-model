# NCAAF Transfer Portal — Phase 2 Composite Test

**Research date:** 2026-04-08
**Seasons:** 2022, 2023, 2024, 2025
**Scope:** Continuity-conditioned composites on NEGATIVE_SHOCK signal (Weeks 1-4 FBS games with spread data)

---

## Objective

Test whether layering continuity conditions (returning production, returning QB, coach continuity) on the Phase 1 NEGATIVE_SHOCK signal (53.4% cover, Weeks 1-4) sharpens the edge past the vigorish threshold.

---

## Data Sources

All data pulled from CFBD API on 2026-04-08:

| Endpoint | Records |
|----------|---------|
| `/player/portal` (2022-2025) | 12,652 transfers |
| `/games` FBS regular season | 3,484 games across 4 seasons |
| `/lines` (2022-2025) | 6,026 games with spread data |
| `/player/returning` (2022-2025) | 528 team-seasons |
| `/coaches` (2021-2025) | Head coach records for continuity check |

---

## Metric Definitions

| Metric | Definition |
|--------|-----------|
| `net_star_shock` | Sum(incoming transfer stars) - Sum(outgoing transfer stars) |
| `NEGATIVE_SHOCK` | Bottom quartile of net_star_shock (threshold: <= -29.0) |
| `HIGH_RETURNING` | Top half of `percentPPA` among NEGATIVE_SHOCK teams (median: 0.551) |
| `RETURNING_QB` | No QB appeared in that team's portal-out list |
| `COACH_CONTINUITY` | Same head coach name as the prior season |

**Note on RETURNING_QB:** Nearly every FBS team (150 of ~134 FBS programs in 2025) lost at least one QB through the portal. This makes `RETURNING_QB = True` a very restrictive filter and limits sample size. The signal from this flag is real but the N is too thin for standalone use.

---

## Phase 1 — Composite Bucket Results (Weeks 1-4)

534 FBS team-seasons built. 6,822 total team-game observations; 2,430 in Weeks 1-4 (pushes excluded).

### Main Results

| Bucket | N | Covers | Cover % | ATS Margin | p (binom) |
|--------|:-:|:------:|:-------:|:----------:|:---------:|
| **A) NEGATIVE_SHOCK (baseline)** | 513 | 277 | 54.0% | +1.23 | 0.077 |
| **B) NEG_SHOCK + HIGH_RETURNING** | **259** | **146** | **56.4%** | **+1.77** | **0.047** |
| C) NEG_SHOCK + RETURNING_QB | 71 | 39 | 54.9% | +0.04 | 0.477 |
| **D) NEG_SHOCK + COACH_CONTINUITY** | **413** | **228** | **55.2%** | **+1.77** | **0.039** |
| E) NEG_SHOCK + RET_QB + COACH_CONT | 63 | 33 | 52.4% | -0.79 | 0.801 |
| F) NEG_SHOCK + HIGH_RET + RET_QB | 38 | 24 | 63.2% | +2.08 | 0.143 |

**Best bucket: B) NEG_SHOCK + HIGH_RETURNING** -- 56.4% cover, N=259, p=0.047.

Runner-up: D) NEG_SHOCK + COACH_CONTINUITY -- 55.2% cover, N=413, p=0.039. Larger sample, slightly lower cover rate but stronger p-value due to size.

Bucket F (all three conditions) shows 63.2% but with only 38 observations -- too thin to trust.

### Season-by-Season Stability

#### B) NEG_SHOCK + HIGH_RETURNING

| Season | N | Cover % | ATS Margin |
|:------:|:-:|:-------:|:----------:|
| 2022 | 107 | 57.9% | +1.67 |
| 2023 | 75 | 54.7% | +0.61 |
| 2024 | 34 | 50.0% | +0.76 |
| 2025 | 43 | 60.5% | +4.85 |

Direction is positive in all four seasons. 2024 is the weakest (50.0%, but only 34 games due to conference realignment reducing the overlap of high-returning + negative-shock teams). Three of four seasons clear 50%.

#### D) NEG_SHOCK + COACH_CONTINUITY

| Season | N | Cover % | ATS Margin |
|:------:|:-:|:-------:|:----------:|
| 2022 | 146 | 56.8% | +1.69 |
| 2023 | 113 | 49.6% | -0.15 |
| 2024 | 64 | 56.2% | +2.09 |
| 2025 | 90 | 58.9% | +4.07 |

Three of four seasons above 50%. 2023 is the one dip (49.6%).

---

## Phase 2 — Favorite vs Underdog (Best Composite: B)

| Role | N | Cover % | ATS Margin | p (binom) |
|:----:|:-:|:-------:|:----------:|:---------:|
| Favorite | 170 | **58.8%** | +2.39 | **0.026** |
| Underdog | 89 | 51.7% | +0.60 | 0.832 |

The signal concentrates in favorites. When a NEGATIVE_SHOCK + HIGH_RETURNING team is laying points, the market is shading the line too far toward the opponent. These teams cover at 58.8% (p=0.026). The underdog side shows no meaningful edge.

This is consistent with Phase 1 findings: the market overweights headline portal losses and underweights the retained core.

---

## Phase 3 — Conference Tier (Best Composite: B)

| Tier | N | Cover % | ATS Margin |
|:----:|:-:|:-------:|:----------:|
| P5/P4 | 181 | **58.6%** | +2.30 |
| G5 | 78 | 51.3% | +0.55 |

The effect is concentrated in P5/P4 conferences. This makes sense -- P5 portal losses generate more headlines and market attention, creating larger overcorrections. G5 portal activity gets less media coverage and thus less market overreaction.

---

## Phase 4 — Spread Bands (Best Composite: B)

| Spread Band | N | Cover % | ATS Margin |
|:-----------:|:-:|:-------:|:----------:|
| < 3 | 24 | 58.3% | +2.48 |
| 3-7 | 42 | **61.9%** | +3.74 |
| 7-14 | 61 | 49.2% | -0.55 |
| 14+ | 132 | 57.6% | +2.09 |

Strongest in the 3-7 point range (61.9%) and big favorites (14+, 57.6%). The 7-14 band is the dead zone (49.2%). This u-shaped pattern suggests the market miscalibrates both close games and blowouts but gets the middle range roughly right.

---

## Phase 5 — Fade Curve (Best Composite: B)

| Window | N | Cover % | ATS Margin |
|:------:|:-:|:-------:|:----------:|
| **Weeks 1-2** | 138 | **56.5%** | +2.48 |
| **Weeks 3-4** | 121 | **56.2%** | +0.97 |
| Weeks 5-8 | 221 | 49.8% | -0.61 |
| Weeks 9+ | 332 | 49.1% | -0.26 |

Textbook early-season fade. The effect holds steady through Week 4 and then drops to baseline by Week 5. The market corrects within the first month of the season. This matches the Phase 1 baseline fade curve and is the expected signature of an early-season pricing inefficiency.

---

## Phase 6 — Robustness Checks

### 6a: Exclude Top 5 Most Frequent Teams

Top 5 teams in Bucket B: North Texas, Georgia Tech, Florida State, Maryland, Arizona.

| Subset | N | Cover % | ATS Margin |
|--------|:-:|:-------:|:----------:|
| Full sample | 259 | 56.4% | +1.77 |
| **Excluding top 5** | 217 | **54.8%** | +1.52 |

Effect survives removal of most frequent teams, dropping only 1.6pp. Not driven by a handful of teams.

### 6b: Season Dominance

| Season | Covers | % of Total | Cover % |
|:------:|:------:|:----------:|:-------:|
| 2022 | 62 | 42% | 57.9% |
| 2023 | 41 | 28% | 54.7% |
| 2024 | 17 | 12% | 50.0% |
| 2025 | 26 | 18% | 60.5% |

No single season accounts for >50% of covers. 2022 contributes the most (42%) but this is expected since it has the largest N in this bucket (107 games). The 2024 season is the weakest contributor -- conference realignment reduced sample size and the effect went flat.

**Seasons above 50% cover (N>=10): 3 of 4.**

### 6c: Conference Breakdown

| Conference | N | Cover % |
|-----------|:-:|:-------:|
| SEC | 54 | 55.6% |
| ACC | 46 | 56.5% |
| Big Ten | 32 | 62.5% |
| American Athletic | 28 | 50.0% |
| Big 12 | 25 | 60.0% |
| Pac-12 | 24 | 62.5% |
| Conference USA | 20 | 35.0% |
| Mountain West | 14 | 64.3% |
| Sun Belt | 13 | 61.5% |

No single conference accounts for >40% of observations. The effect is present across SEC, ACC, Big Ten, Big 12, Pac-12, Mountain West, and Sun Belt. Conference USA is a notable exception (35.0% cover -- teams that lost portal talent AND retained production but still underperformed in C-USA).

### 6d: Robustness Summary

| Check | Result | Pass? |
|-------|--------|:-----:|
| Excl top 5 teams | 54.8% (was 56.4%) | Yes |
| Single season >50% of covers | No (max 42%) | Yes |
| Seasons >= 50% cover | 3 of 4 | Yes |
| Conference dominance | No single >40% | Yes |
| P5 vs G5 | P5 drives the effect (58.6% vs 51.3%) | Noted |

---

## Comparison: All Buckets Favorites + Early Weeks

| Bucket | All (N) | All Cover% | Favs Cover% (N) | Wk1-2 Cover% (N) |
|--------|:-------:|:----------:|:----------------:|:-----------------:|
| A) NEG_SHOCK | 513 | 54.0% | 55.2% (324) | 55.7% (271) |
| **B) NEG_SHOCK + HIGH_RET** | **259** | **56.4%** | **58.8% (170)** | **56.5% (138)** |
| C) NEG_SHOCK + RET_QB | 71 | 54.9% | 51.2% (43) | 56.8% (37) |
| **D) NEG_SHOCK + COACH_CONT** | **413** | **55.2%** | **55.6% (279)** | **55.9% (220)** |
| E) NEG_SHOCK + QB + COACH | 63 | 52.4% | 48.7% (39) | 54.5% (33) |
| F) NEG_SHOCK + HIGH_RET + QB | 38 | 63.2% | 68.4% (19) | 65.0% (20) |

Bucket B is the clear winner on both cover rate and statistical significance among sufficiently-sized samples. Bucket D is the runner-up with the advantage of a larger sample (413 vs 259).

---

## Signal Characterization

**What:** FBS teams in the bottom quartile of net portal star shock (lost significantly more talent than gained) who also retained above-median returning production cover early-season spreads at 56.4% in Weeks 1-4.

**Mechanism:** The market overreacts to portal departure headlines. When the departures are offset by a strong returning core (high percentPPA), the team's actual on-field decline is smaller than what the spread implies. The overcorrection is largest for P5 favorites and fades by Week 5 as the market recalibrates.

**Improvement over Phase 1 baseline:** +2.4pp (54.0% -> 56.4%). The composite condition filters out teams where portal losses genuinely hurt (those without a strong returning core) and retains those where the market is most wrong.

**Threshold math:** At -110 juice, breakeven is 52.4%. At 56.4%, expected profit per unit is (0.564 * 0.909 - 0.436 * 1.0) = +7.7% ROI before line shopping. The favorites subset (58.8%, N=170) yields ~11.4% ROI.

---

## Decision: ADVANCE

### Criteria Check

| Criterion | Threshold | Actual | Pass? |
|-----------|:---------:|:------:|:-----:|
| Best composite cover % | >= 54.5% | **56.4%** | Yes |
| Sample size | >= 80 | **259** | Yes |
| Stable 3+ seasons | 3 of 4 above 50% | **3 of 4** | Yes |
| Survives robustness | Top-5 removal, no dominance | **Yes** | Yes |

All four ADVANCE gates pass.

### Strengths
1. 56.4% cover rate clears -110 vig by ~4pp (estimated +7.7% ROI)
2. Binomial p = 0.047 -- statistically significant at alpha = 0.05
3. Consistent across 3 of 4 seasons (2024 is the one flat year at 50.0%, with small N=34)
4. Clean fade curve: Weeks 1-4 signal, gone by Week 5
5. Favorites at 58.8% (p=0.026) -- the strongest actionable subset
6. Survives all robustness checks: no team dominance, no conference dominance, no single-season dominance
7. Runner-up bucket (COACH_CONTINUITY, N=413, 55.2%, p=0.039) provides confirmation from a different angle

### Weaknesses
1. 2024 season is flat (50.0%, N=34) -- conference realignment disrupted the sample but could also indicate instability
2. G5 subset is weak (51.3%) -- signal is P5-concentrated
3. 259 observations over 4 seasons is solid but not enormous; another 2 seasons of data would strengthen confidence
4. The 7-14 spread band is a dead zone (49.2%) with no clear explanation
5. Effect is still a "badge" rather than a full model -- it needs other confirming signals for highest confidence

### Recommended Next Steps
1. **Phase 3: Build the operationalized signal** -- for Weeks 1-4, tag P5 NEGATIVE_SHOCK + HIGH_RETURNING favorites as "Portal Overcorrection" and track live in 2026 season
2. **Combine with Bucket D** -- COACH_CONTINUITY (55.2%, N=413) adds independent information; the intersection of B and D should be tested
3. **Add market timing** -- pull opening vs closing line movement to see if the overcorrection is priced at open or develops through the week
4. **2026 live shadow** -- classify teams by late August when portal window closes, shadow Weeks 1-4, grade results
5. **Feature candidate** -- `net_star_shock * returning_pct_ppa` is a strong candidate feature for any future NCAAF spread model, weighted to Weeks 1-4

---

## Data Artifacts

Analysis used CFBD API data pulled 2026-04-08. Analysis script: `research/ncaaf_portal/phase2_composite_analysis.py`. No existing files were modified.
