# NHL Defensive Structure Archetypes — Phase 1

**Date:** 2026-04-06
**Data:** 5,248 games across 4 NHL seasons (2021-22 through 2024-25)

---

## Verdict: ADVANCE

Two matchup cells clear all decision criteria. The ANEMIC × BEND_NOT_BREAK cell
shows +0.38 goals residual vs closing line, survives controls (+0.25 controlled),
is directionally consistent in all 4 seasons, and is not concentrated. This is the
strongest structural totals finding across any sport in this research program.

---

## Cluster Definitions

### Defensive Archetypes (K=3)

| Archetype | N | Shots Against | HD Shots Against | xGA | HD Danger Rate | GA (check) |
|-----------|---|--------------|-----------------|-----|---------------|------------|
| **SUPPRESSOR** | 3,601 | 30.4 | **2.7** | **2.90** | **0.091** | 3.01 |
| **BEND_NOT_BREAK** | 2,813 | **32.9** | 3.9 | 3.49 | 0.119 | 3.45 |
| **POROUS** | 4,082 | 28.7 | 3.5 | 3.06 | **0.122** | 2.99 |

SUPPRESSOR: Lowest danger rate (0.091) and lowest xGA. Limits both volume and quality.
BEND_NOT_BREAK: Highest volume allowed (32.9 SA) but moderate danger rate. Allows shots but limits quality.
POROUS: Lower volume than BNB but HIGHEST danger concentration (0.122). Allows fewer shots but more dangerous ones.

Note: POROUS has lower GA than BEND_NOT_BREAK (2.99 vs 3.45) despite higher danger
rate — this is because lower total volume offsets higher danger rate. The archetype
describes SHAPE, not quality. This confirms the archetypes are NOT just "good/bad team."

### Offensive Archetypes (K=3)

| Archetype | N | Shots For | HD Shots For | xGF | HD Danger Rate | GF (check) |
|-----------|---|----------|-------------|-----|---------------|------------|
| **POTENT** | 2,891 | **32.8** | **4.0** | **3.53** | 0.122 | 3.31 |
| **AVERAGE** | 3,885 | 28.4 | 3.4 | 3.02 | 0.120 | 3.01 |
| **ANEMIC** | 3,720 | 30.6 | **2.8** | 2.91 | **0.091** | 3.08 |

ANEMIC: Moderate volume but lowest danger rate (0.091) and lowest xGF. Generates
quantity without quality.

---

## Matchup Cell Results

### HOME OFFENSE × AWAY DEFENSE

| Home Off | Away Def | N | Goals | Close | **Residual** | Flag |
|----------|----------|---|-------|-------|-------------|------|
| **ANEMIC** | **BEND_NOT_BREAK** | **498** | **6.53** | **6.15** | **+0.38** | **STRONG** |
| ANEMIC | SUPPRESSOR | 929 | 6.17 | 5.93 | +0.24 | near |
| POTENT | SUPPRESSOR | 449 | 6.39 | 6.16 | +0.23 | near |
| AVERAGE | BEND_NOT_BREAK | 458 | 6.35 | 6.17 | +0.19 | |
| AVERAGE | POROUS | 1,091 | 6.13 | 6.05 | +0.09 | |
| POTENT | BEND_NOT_BREAK | 461 | 6.37 | 6.34 | +0.03 | |
| ANEMIC | POROUS | 415 | 6.17 | 6.09 | +0.08 | |
| AVERAGE | SUPPRESSOR | 400 | 6.07 | 6.00 | +0.06 | |
| POTENT | POROUS | 545 | 6.13 | 6.20 | -0.08 | |

### AWAY OFFENSE × HOME DEFENSE

| Away Off | Home Def | N | Goals | Close | **Residual** | Flag |
|----------|----------|---|-------|-------|-------------|------|
| **ANEMIC** | **BEND_NOT_BREAK** | **468** | **6.47** | **6.17** | **+0.30** | **STRONG** |
| ANEMIC | SUPPRESSOR | 961 | 6.25 | 5.95 | +0.30 | near |
| AVERAGE | BEND_NOT_BREAK | 484 | 6.40 | 6.17 | +0.23 | near |
| AVERAGE | POROUS | 1,041 | 6.21 | 6.05 | +0.16 | |
| POTENT | BEND_NOT_BREAK | 442 | 6.46 | 6.32 | +0.14 | |
| ANEMIC | POROUS | 447 | 6.14 | 6.06 | +0.08 | |
| AVERAGE | SUPPRESSOR | 409 | 6.00 | 5.98 | +0.02 | |
| POTENT | SUPPRESSOR | 452 | 6.09 | 6.14 | -0.06 | |
| POTENT | POROUS | 542 | 6.13 | 6.24 | -0.10 | |

---

## Key Finding: ANEMIC × BEND_NOT_BREAK

When an ANEMIC offense (low danger rate, moderate volume) faces a BEND_NOT_BREAK
defense (high volume allowed, moderate danger rate), the game produces +0.3 to
+0.4 more goals than the closing line suggests.

**Mechanism hypothesis:** ANEMIC offenses generate many low-danger chances.
BEND_NOT_BREAK defenses allow high shot volume but control danger quality. The
result is a game with high shot counts on both sides — but the market prices
these games based on the lower xG profiles of both teams, underestimating how
high-volume/low-danger games can still produce goals through volume alone
(rebounds, tips, screen shots, bounces).

---

## Control Check

| Cell | Raw Residual | After Controlling Close + Goalie + B2B | Survives? |
|------|-------------|---------------------------------------|-----------|
| **HO: ANEMIC × BNB** | **+0.38** | **+0.25** | **YES** |
| **AO: ANEMIC × BNB** | **+0.30** | **+0.20** | **YES** |
| AO: ANEMIC × SUPPRESSOR | +0.30 | +0.07 | NO |
| HO: ANEMIC × SUPPRESSOR | +0.24 | +0.00 | NO |

The ANEMIC × BEND_NOT_BREAK cell survives controls on both sides. The
ANEMIC × SUPPRESSOR cells collapse — the closing total already captures
that matchup quality.

---

## Season Stability

### ANEMIC × BEND_NOT_BREAK (Home Offense side)

| Season | N | Residual | Direction |
|--------|---|---------|-----------|
| 2021-22 | 172 | +0.45 | **OK** |
| 2022-23 | 208 | +0.39 | **OK** |
| 2023-24 | 86 | +0.18 | **OK** |
| 2024-25 | 32 | +0.48 | **OK** |
| **Consistent: 4/4** | | | |

### ANEMIC × BEND_NOT_BREAK (Away Offense side)

| Season | N | Residual | Direction |
|--------|---|---------|-----------|
| 2021-22 | 155 | +0.35 | **OK** |
| 2022-23 | 206 | +0.25 | **OK** |
| 2023-24 | 79 | +0.08 | **OK** |
| 2024-25 | 28 | +1.05 | **OK** |
| **Consistent: 4/4** | | | |

**Directionally consistent in all 4 seasons on both sides.** This is the strongest
stability result in the entire research program.

---

## Concentration Check

| Cell | Top 2 Teams | Share | After Removing Top 2 |
|------|------------|-------|---------------------|
| HO: ANEMIC × BNB | CBJ (72), MTL (67) | 14% | N=366, resid=+0.24 |
| AO: ANEMIC × BNB | CBJ (71), ANA (50) | 13% | N=350, resid=+0.28 |

Not concentrated. Top 2 teams contribute ~14% of observations. Effect survives
their removal at +0.24 to +0.28 (vs +0.30 to +0.38 full).

---

## Decision Criteria

| Criterion | Result | Status |
|-----------|--------|--------|
| Residual > 0.3 goals | +0.38 (HO), +0.30 (AO) | **PASS** |
| Survives controls | +0.25 (HO), +0.20 (AO) | **PASS** |
| Consistent 3+ of 4 seasons | **4/4 both sides** | **PASS** |
| N >= 30 | 498 (HO), 468 (AO) | **PASS** |
| Not concentrated | Top 2 = 14%, survives removal | **PASS** |

All five criteria pass.

---

## Recommended Next Step

Test whether the ANEMIC × BEND_NOT_BREAK OVER lean produces a usable market
residual after accounting for:
1. Goalie-specific context (starter quality, fatigue)
2. Special teams context (PP/PK rates)
3. Game-specific context (rest, travel, divisional)

If the residual holds at +0.20+ after fuller controls, this is a candidate for
shadow tracking in the live NHL pipeline.
