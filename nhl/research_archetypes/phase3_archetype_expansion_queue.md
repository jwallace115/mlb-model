# NHL Archetype Expansion — Phase 3

**Date:** 2026-04-06
**Data:** 5,248 games, 4 NHL seasons (2021-22 through 2024-25)
**Harness:** K=2 on offense + K=2 on defense, mandatory goalie-state split

---

## Summary: 4 ADVANCE, 2 NEAR MISS, 2 ARCHIVE

Three of the four advancing branches survive the confirmed-starter gate with
positive OVER residuals (+0.27 to +0.30 goals). One survives with a negative
residual (UNDER lean). Two of the four are 4/4 seasons consistent.

**The strongest finding: Branch 7 (Special Teams Net) — +0.30 goals in
confirmed-starter games, 4/4 seasons, N=370.**

---

## Top 8 Branches Tested

| # | Branch | Best Resid | N | Starter Resid | N_s | Seasons | Top2% | Verdict |
|---|--------|-----------|---|--------------|-----|---------|-------|---------|
| 7 | **Special Teams Net** | +0.39 | 1,094 | **+0.30** | **370** | **4/4** | 10% | **ADVANCE** |
| 6 | **Goalie Workload** | +0.32 | 1,163 | **+0.28** | **387** | **4/4** | 11% | **ADVANCE** |
| 8 | **Process Dominance** | +0.24 | 1,862 | **+0.27** | **663** | **4/4** | 10% | **ADVANCE** |
| 5 | Danger Concentration | +0.26 | 1,478 | **-0.28** | 337 | 3/4 | 11% | ADVANCE (UNDER) |
| 4 | Shot Dominance | +0.28 | 1,350 | +0.23 | 406 | 3/4 | 12% | NEAR MISS |
| 1 | HD Pressure Asymmetry | +0.30 | 1,393 | -0.17 | 403 | 3/4 | 9% | NEAR MISS |
| 3 | Penalty Environment | +0.32 | 569 | +0.14 | 170 | 3/4 | 11% | ARCHIVE |
| 2 | Volume vs Efficiency | +0.19 | 2,024 | -0.32 | 340 | 1/4 | 10% | ARCHIVE |

---

## Branch Details

### Branch 7: Special Teams Net (ADVANCE — STRONGEST)
**Inputs:** pp_pk_net + pp_opp_r20 (offense), pp_pk_net + pen_r20 (defense)
**Starter residual:** +0.30 goals (N=370)
**All 4 seasons consistent**
**Mechanism:** Games where one team has strong PP and the other takes many penalties
create high-scoring first-half environments that the market underestimates from
the game total line. Special teams efficiency interacts with penalty volume to
produce more goals than the broad process stats suggest.

### Branch 6: Goalie Workload (ADVANCE)
**Inputs:** sf_r20 + hd_sf_r20 (offense), sa_r20 + hd_sa_r20 (defense)
**Starter residual:** +0.28 goals (N=387)
**All 4 seasons consistent**
**Mechanism:** This is similar to the Phase 1 shot-volume archetypes but uses
a different clustering from the defense-first approach. The starter-game
residual (+0.28) survives the goalie-state gate that killed the Phase 2 cell.

### Branch 8: Process Dominance (ADVANCE — LARGEST SAMPLE)
**Inputs:** xgf_r20 + danger_ratio (offense), xga_r20 + danger_ratio (defense)
**Starter residual:** +0.27 goals (N=663 — largest confirmed-starter sample)
**All 4 seasons consistent**
**Mechanism:** When one side has high xGF and high danger ratio facing a defense
with low xGA suppression, the game produces more goals than the closing total
implies. This combines quality (xG) with style (danger ratio) for a richer
matchup descriptor.

### Branch 5: Danger Concentration (ADVANCE — UNDER lean)
**Inputs:** hd_rate_o + xgf_r20 (offense), hd_rate_d + xga_r20 (defense)
**Starter residual:** -0.28 goals (N=337)
**3/4 seasons consistent**
**Mechanism:** A specific danger-concentration matchup produces FEWER goals than
the closing total in confirmed-starter games. This is the first UNDER-lean cell
found in the archetype program.

---

## Near Miss Backlog

| Branch | Starter Resid | N_s | Seasons | Issue |
|--------|--------------|-----|---------|-------|
| 4. Shot Dominance | +0.23 | 406 | 3/4 | Below +0.25 threshold |
| 1. HD Pressure Asymmetry | -0.17 | 403 | 3/4 | Below +0.15 magnitude |

---

## Fast Validation Harness Design

The harness used for all 8 branches:

1. **Cluster:** K=2 offense + K=2 defense using StandardScaler + KMeans (seed=42)
2. **Matchup cells:** Test all 2×2=4 cells for home-offense × away-defense AND
   away-offense × home-defense (8 total cells per branch)
3. **Raw residual:** mean(total_goals - closing_total) per cell, require N >= 30
4. **Goalie-state split:** MANDATORY — report confirmed-starter residual separately
5. **Season consistency:** Count seasons where cell residual direction matches overall
6. **Concentration:** Top 2 team share in the cell
7. **Verdict:** ADVANCE if |starter_resid| >= 0.25, N_s >= 50, seasons >= 3/4, top2 < 25%

---

## Full 40-Candidate Ranked List (abbreviated — top 15)

| Rank | Candidate | Distinct | Data | Useful | Total |
|------|-----------|----------|------|--------|-------|
| 1 | Special teams PP/PK net + penalty load | 5 | 5 | 5 | **15** |
| 2 | Goalie workload shape (shots + HD faced) | 4 | 5 | 5 | **14** |
| 3 | Process dominance (xG + danger ratio) | 4 | 5 | 5 | **14** |
| 4 | HD pressure asymmetry | 4 | 5 | 4 | **13** |
| 5 | Shot dominance ratio + xG | 3 | 5 | 5 | **13** |
| 6 | Danger concentration (HD rate + xG) | 4 | 5 | 4 | **13** |
| 7 | Volume vs efficiency style | 3 | 5 | 4 | **12** |
| 8 | Penalty discipline environment | 4 | 5 | 3 | **12** |
| 9 | Rebound ecology (HD + shot pressure) | 5 | 3 | 4 | 12 |
| 10 | First-period pace (not available) | 5 | 1 | 5 | 11 |
| 11 | Rush transition style (not available) | 5 | 1 | 5 | 11 |
| 12 | Goalie rebound control (not available) | 5 | 1 | 4 | 10 |
| 13-40 | (remaining — all score 7-10) | 2-4 | 1-4 | 2-3 | 7-10 |

Branches 9-12 scored well on conceptual distinctness but are blocked by missing
data (period-level splits, transition events, rebound data). These would require
a new data source (e.g., NHL play-by-play API or MoneyPuck event-level data).

---

## Recommended Next Steps

1. **Deep-validate Branch 7 (Special Teams Net)** — strongest finding (+0.30 in
   confirmed-starter games, 4/4 seasons). Run the full Phase 2-style validation
   with market residual, ROI, goalie interaction detail, and concentration removal.

2. **Deep-validate Branch 8 (Process Dominance)** — largest confirmed-starter
   sample (N=663, 4/4 seasons, +0.27). The large N makes this the most robust
   candidate even if the residual is slightly smaller.

3. **Explore Branch 5 (UNDER lean)** — the first UNDER-lean cell in the program.
   If validated, this provides a directional counterpart to the OVER leans.

4. **Do NOT test branches 9-12** without new data sources. Period-level and
   transition data would require NHL API integration not currently in the pipeline.
