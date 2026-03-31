# NBA Small-Edge System — Postmortem Memo

**Date:** March 2026
**Status:** Research complete — system not validated for deployment

---

## 1. What Was Built

The NBA small-edge system filters the Ridge totals model to games where model disagreement with the closing line is small (0.00 to 1.00 points). The hypothesis was that the model is most reliable when it *slightly* disagrees with the market rather than when it strongly disagrees.

Components:

- **Core filter:** 0.00 <= |model_edge| <= 1.00 (approximately 15% of all games qualify)
- **Base model:** Ridge regression on 15 features (ORTG, DRTG, pace, trends, 3PA rate, FT rate, B2B flag)
- **Fast pace overlay:** Both teams above median pace AND model leans OVER, boost confidence +1 tier
- **Phase 6 RS shadow tracker:** Append-only log, 150-bet validation threshold, running since March 14, 2026
- **Phase 6 PO shadow tracker:** Separate playoff log (begins April 19, 2026), exploratory only
- **Projection archive:** Daily projections persisted to cumulative parquet from March 14, 2026 forward

---

## 2. Research Phases Completed

| Phase | Description | Key Finding |
|-------|-------------|-------------|
| Phase 5 | Small-edge discovery | 0-1 range showed +5.6% ROI on 2024-25 holdout (179 bets, 55.3% hit) |
| Phase 6 | Forward shadow deployed | Running since March 14, 2026; 6 graded bets at time of memo |
| Phase 7 | Tier calibration audit | HIGH tier inflated at 58% of all bets; inverted performance (LOW > MEDIUM > HIGH) |
| Phase 7B v1 | Master hypothesis test (29 hypotheses) | All failed — insufficient sample in 2-season discovery window |
| Phase 7B v2 | Expanded discovery (4 seasons attempted) | Only 2 seasons available; recomputed base ROI was -13.1% |
| Phase 7B Base Audit | Reconcile +5.6% vs -13.1% discrepancy | Confirmed no data issue — different seasons, genuine regime difference |
| Phase 8 | 2025-26 pre-live point-in-time replay | Full replay produced -3.8% ROI on 131 bets (Oct 2025 – Mar 2026) |

---

## 3. The Full Performance Picture

| Season | N | Hit Rate | ROI | Role |
|--------|---|----------|-----|------|
| 2022-23 | 197 | 47.2% | -9.9% | Discovery |
| 2023-24 | 159 | 43.4% | -17.2% | Discovery |
| 2024-25 | 179 | 55.3% | +5.6% | Holdout (original validation) |
| 2025-26 pre-live | 131 | 50.4% | -3.8% | Point-in-time replay |
| 2025-26 live | 6 | 50.0% | -4.5% | Phase 6 RS (too small to interpret) |

**Weighted average across all 4 seasons: approximately -7% ROI on 666 bets.**

---

## 4. What the Data Shows

The NBA small-edge system produced one clearly profitable season (2024-25: +5.6%) inside three negative or near-flat seasons (-9.9%, -17.2%, -3.8%). The evidence does not support the conclusion that the 0-1 edge zone represents a structural market inefficiency.

**The +5.6% vs -13.1% discrepancy** was initially alarming but ultimately straightforward: Phase 5 computed +5.6% on the 2024-25 holdout season, while Phase 7B v2 computed -13.1% on the 2022-23 + 2023-24 discovery window. Both numbers are correct. They measure different seasons. The model's small-edge zone was unprofitable for two years, then profitable in the third, then near-flat in the fourth.

**The fast pace overlay** showed dramatically different behavior across seasons. In 2024-25 shadow testing, it produced 67% hit rate and +27.3% ROI on 30 bets. In the 2025-26 pre-live replay, it produced 45.5% hit rate and -13.2% ROI on 33 bets. This instability suggests the overlay captured favorable variance in one season rather than a repeatable causal mechanism.

**Sub-bucket behavior is unstable.** In 2024-25, the smallest edges (0.00-0.25) were most profitable. In the 2025-26 replay, that bucket was the worst (-27.0%) while the largest edges (0.75-1.00) were best (+12.3%). No consistent sub-structure emerged across seasons.

**Phase 7B v2 tested 14 hypotheses** (14 more were skipped due to missing data) and found zero that reliably amplified, killed, or filtered the small-edge signal. The base +5.6% ROI from 2024-25 could not be explained by any game type, team context, or market condition — it appears to have been diffuse favorable variance rather than a concentrated exploitable pattern.

**Pattern-level conclusion:** The edge is either regime-dependent (tied to a specific market environment that existed in 2024-25 but not in other seasons) or was a single favorable season in a fundamentally break-even system. The data does not support deployment.

---

## 5. What Was Ruled Out

| Hypothesis | Result | Reason |
|------------|--------|--------|
| Circadian misalignment (NBA) | No signal | Priced in; direction flipped across seasons |
| Cumulative load / fatigue | No signal | Priced in; no stable directional bias |
| 29 kill zone / amplifier / market behavior filters (Phase 7B) | All failed | N collapse below gates or directional instability |
| Tier recalibration | Not viable | Inflation confirmed but no threshold config restored monotonicity |
| Fast pace overlay as standalone amplifier | Unstable | +27% in one season, -13% in next |
| Extreme totals as kill zone | Insufficient N | Only 11 qualifying bets in discovery |
| Mid-range total band as amplifier | Failed | -9.8% ROI on 108 qualifying bets |
| Home hot offensive form | Failed | -14.7% ROI on 47 qualifying bets |

---

## 6. Current Decision

The NBA small-edge system (Phase 6) is reclassified from "validation of a likely edge" to **"monitoring an unproven idea that currently lacks historical support across multiple seasons."**

**Operational rules going forward:**

1. Phase 6 RS shadow continues running — do not shut off
2. Do not optimize, add overlays, or adjust thresholds
3. Do not deploy bankroll based on current results
4. Projection archive runs daily — 2025-26 forward data is being preserved
5. Revisit at end of 2025-26 season with full same-season dataset
6. The fast pace overlay remains active in config but its value is now uncertain

---

## 7. What Is Not Ruled Out

The research eliminated specific hypotheses within the 0-1 edge framework, but several alternative frameworks remain untested:

- **Large-edge framework (Phase 9):** The model's biggest disagreements with the market were not profitable historically, but a different architecture (e.g., market-residual) at larger edges has not been tested
- **Market movement / line behavior framework:** Requires opening line data (not yet sourced for NBA). This was the highest-priority data gap identified in Phase 7B — 5 hypotheses were blocked by its absence
- **Pace shock / delta framework:** Testing whether sudden pace changes (team acquires fast player, coaching change) create temporary mispricings. Buildable from existing pipeline
- **Public betting percentage overlay:** Highest-priority external data source identified but not available
- **The NBA market may be fundamentally more efficient than MLB or soccer totals markets** — this is itself a useful finding that should inform resource allocation

---

## 8. Next Steps

1. **End of 2025-26 season evaluation:** Combine Phase 6 RS live results + Phase 8 replay + projection archive into a full same-season dataset. This will be the definitive test — one complete season tracked with the same model, same thresholds, no modifications
2. **Opening line data sourcing:** Would unlock 5 blocked hypotheses (M1, M5, M7, A3, K5) — the most productive single data addition
3. **Phase 9 large-edge framework test:** Different architecture, not a patch on the current system. Worth testing independently
4. **Resource allocation review:** If end-of-season evaluation confirms no edge, redirect NBA research resources to sports where validated edges exist (MLB, soccer)

---

## 9. Key Lessons

1. **A single profitable holdout season is not sufficient validation.** The +5.6% ROI on 2024-25 passed all formal gates at the time, but 179 bets is a thin sample and one season can be explained by variance. Future validation should require either multiple seasons of discovery-era profitability or a clear causal mechanism that explains why the edge exists.

2. **Discovery-era performance is the floor, not the ceiling.** When the discovery window shows -13.1% and the holdout shows +5.6%, the discovery number is the more informative signal about structural edge. Holdout validation protects against overfitting but does not guarantee the edge is real — it can also reflect favorable variance.

3. **Sub-filtering a narrow signal zone rarely helps.** The 0-1 edge zone contains only ~15% of games. Further sub-filtering by any condition (pace, total band, B2B, etc.) collapses N below meaningful thresholds. If the base signal is diffuse across all game types, there is no sub-condition to exploit — the edge is either real everywhere or nowhere.

4. **Build the projection archive from day one.** The inability to replay the full 2025-26 season was a preventable gap. Daily projections should always be persisted to a cumulative file. This was fixed on March 14, 2026 but five months of data were lost.

5. **Market efficiency varies by sport.** The NBA closing totals market appears more efficient than MLB or soccer totals. The same model architecture that produces validated edges in other sports does not automatically transfer. Each market should be evaluated on its own terms, and "no edge found" is a legitimate and useful research outcome.

---

---

## 10. Phase 9-12 Cumulative Findings (March 2026)

Four independent pregame frameworks tested, all null:
- Phase 9 (edge size): no stable signal
- Phase 10 (market movement): no stable signal
- Phase 11 (pace expectations): strong retrospective signal (+23%),
  no predictive signal (-3.5%)
- Phase 12 (variance environments): no signal

Conclusion: NBA pregame totals are efficient on price, movement,
pace, and variance dimensions at the team/market level.

Key structural clue: Large outcome deviations from the closing line
are real and priceable retrospectively, but not predictable with
team-level pregame data. Player-level pace and lineup composition
are the most promising remaining hypothesis.

Next phase: Model B v1 — Player Pace / Lineup Layer

---

---

## 11. Model B v1 — Player Pace Delta (March 2026)

Result: Correlation gate failed. Research program closed.

Player pace delta feature:
- Baseline team pace correlation vs actual pace: 0.132
- Player-adjusted pace correlation vs actual pace: 0.095
- Adding player-level data made prediction worse, not better

Key failure reasons:
1. Injury data only available for 2023-24 (67% of games had zero adjustment)
2. Pace deltas noisy at minimum threshold — dominated by role players
3. Market already prices player availability into totals

---

## 12. Final Conclusion — NBA Pregame Totals (March 2026)

Status: CLOSED

Five independent frameworks tested, all null:
- Phase 9 (edge size): no signal
- Phase 10 (market movement): no signal
- Phase 11 (pace expectations): no predictive signal
- Phase 12 (variance environments): no signal
- Model B v1 (player pace delta): correlation gate failed

NBA pregame totals are efficiently priced across price, movement,
pace, variance, and player-availability dimensions.

Decision: Do not continue NBA pregame totals research without
materially new data (public betting %, tracking data, lineup
confirmation APIs with full historical coverage).

Phase 6 RS shadow continues running as a passive monitor only.
No further active research on NBA pregame totals until end of
2025-26 season review.

---

*This memo was generated March 2026 and should be updated when Phase 6 RS reaches the 150-bet threshold or when end-of-season evaluation is completed.*

*Files referenced: nba/phase8_replay_2025_rs.parquet, nba/data/nba_phase6_rs_shadow.parquet, nba/phase7b/master_summary_v2.txt, nba/phase7b/base_audit.txt, nba/phase10/movement_summary.txt, nba/phase11/pace_shock_summary.txt, nba/phase12/variance_summary.txt, nba/model_b/model_b_v1_summary.txt*
