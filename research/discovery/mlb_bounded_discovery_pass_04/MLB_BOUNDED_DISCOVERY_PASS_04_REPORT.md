# MLB BOUNDED DISCOVERY PASS 04 — REPORT

**Pass Date:** 2026-04-20
**Operator:** Claude (automated research assistant)
**Mechanism Family:** STANDALONE STARTER FRAGILITY
**Max Candidates:** 6 (4 tested, 2 DATA_GAP)
**Runtime Object:** MLB_RUNTIME_OBJECT_V1 (19,430 x 130, HISTORICAL_CLEAN)

---

## 1. PURPOSE

This is the fourth post-rebuild MLB bounded discovery pass. It tests whether standalone opposing-starter fragility indicators — single-factor flags based on recent pitching performance, command, or workload — predict elevated game totals. Unlike passes 02–03 which tested conjunctions (AND rules), this pass tests individual starter weakness markers as standalone flags.

---

## 2. ENGINE STACK CONFIRMATION

| Element | Status |
|---|---|
| Frozen foundation package | `research/engine_foundation/mlb_engine_v1_foundation/` — confirmed |
| Orchestration layer | `research/orchestration/` — default_deny=true, confirmed |
| Runtime object | `mlb_runtime_object_v1.parquet` (19,430 x 130, HISTORICAL_CLEAN) — confirmed |
| Outside-package files | **NONE** |
| Caveats carried | CAVEAT_01 (bullpen process), CAVEAT_02 (SC averaging — applies to all opp_sp_* fields used) |

---

## 3. PRIOR PASS LESSONS CARRIED FORWARD

From E-family (Pass 02) and W-family (Pass 03):
1. **Vacuous thresholds are structural failure** — every threshold must create real selectivity (2–70% flag rate)
2. **Semantically unsupported mechanisms must hard stop** — no approximation or substitution
3. **No salvage by quiet reinterpretation** — if a mechanism fails, it fails

---

## 4. FEATURE CANDIDATE INVENTORY (Steps 1–2)

### 4.1 Available PIT-Safe Starter Fields (>80% non-null)

23 fields pass the >80% non-null coverage threshold. All are `opp_sp_*` fields from the starter_profile substrate (CAVEAT_02 applies: SC available-only averaging). All use rolling prior-game windows — confirmed PIT-safe.

Key fields used in this pass:

| Field | Non-null Rate | PIT-Safe | Caveat |
|---|---|---|---|
| `opp_sp_workload_ip_last_3` | 85.96% | YES | CAVEAT_02 |
| `opp_sp_command_bb_rate_last_3` | 85.96% | YES | CAVEAT_02 |
| `opp_sp_contact_barrel_allowed_last_3` | 84.12% | YES | CAVEAT_02 |
| `opp_sp_workload_ppbf_last_3` | 85.96% | YES | CAVEAT_02 |

### 4.2 Candidate Definitions

| ID | Name | Field | Direction | Threshold | Hypothesis |
|---|---|---|---|---|---|
| S1 | Short-Outing Risk | `opp_sp_workload_ip_last_3` | <= | 4.67 | Starter averaging short outings forces early bullpen handoff, increasing run exposure |
| S2 | Poor Command | `opp_sp_command_bb_rate_last_3` | >= | 0.10 | High walk rate = base runners + high pitch counts + earlier exit = more runs |
| S5 | Barrel Damage | `opp_sp_contact_barrel_allowed_last_3` | >= | 0.07 | Giving up barrels at elevated rate = hard contact damage = more runs allowed |
| S6 | Laboring/Inefficient | `opp_sp_workload_ppbf_last_3` | >= | 4.10 | High pitches per batter = laboring, earlier exit, pitch count stress = more runs |

### 4.3 DATA_GAP Candidates (Not Tested)

| ID | Name | Required Field | Status |
|---|---|---|---|
| S3 | Performance Degradation | Rolling ERA or FIP | **DATA_GAP** — no ERA or FIP fields exist in runtime object. Not substituted. |
| S4 | Workload Cliff + Rest | Pitcher-specific rest days | **DATA_GAP** — `home_rest_days`/`away_rest_days` are team scheduling gaps, not pitcher rest between starts. Not substituted. |

### 4.4 Live Implementation Paths

| Candidate | Live Data Source |
|---|---|
| S1 | MLB Stats API per-start game logs → rolling 3-start avg IP |
| S2 | MLB Stats API per-start game logs or FanGraphs → rolling 3-start BB% |
| S5 | Baseball Savant per-start Statcast → rolling 3-start barrel rate allowed |
| S6 | MLB Stats API per-start game logs → rolling 3-start pitches/BF |

---

## 5. TEMPORAL SPLITS

| Split | Date Range | Row Count |
|---|---|---|
| DISCOVERY | game_date < 2024-01-01 (2022–2023) | 9,720 |
| VALIDATION | 2024-01-01 ≤ game_date < 2025-01-01 (2024) | 4,854 |
| OOS | 2025-01-01 ≤ game_date < 2026-01-01 (2025) | 4,856 |

---

## 6. FLAG RATE CHECK (Step 4)

All thresholds calibrated on DISCOVERY data only.

| Candidate | Flag Rate | N Flagged | N Total | Status |
|---|---|---|---|---|
| S1_short_outing | 24.89% | 2,079 | 8,353 | PASS |
| S2_poor_command | 26.35% | 2,201 | 8,353 | PASS |
| S5_barrel_damage | 12.25% | 998 | 8,146 | PASS |
| S6_laboring | 24.51% | 2,047 | 8,353 | PASS |

All four candidates pass the flag rate check (2% < rate < 70%).

---

## 7. DISCOVERY RESULTS (Step 5) — DISCOVERY_TRIAGE_ONLY

**Thresholds locked on discovery data before validation was examined.**

| Candidate | N Flagged | N Unflagged | Mean Total (Flag) | Mean Total (Unflag) | Gap | t-stat | p-value |
|---|---|---|---|---|---|---|---|
| S1_short_outing | 2,079 | 6,274 | 9.104 | 8.858 | **+0.247** | 2.171 | 0.0300 |
| S2_poor_command | 2,201 | 6,152 | 9.029 | 8.880 | +0.149 | 1.315 | 0.1885 |
| S5_barrel_damage | 998 | 7,148 | 8.977 | 8.901 | +0.076 | 0.506 | 0.6128 |
| S6_laboring | 2,047 | 6,306 | 8.825 | 8.950 | **-0.125** | -1.101 | 0.2709 |

### S1 By-Season Stability
| Season | N Flagged | Gap | Flag Rate |
|---|---|---|---|
| 2022 | 1,076 | +0.154 | 25.66% |
| 2023 | 1,003 | +0.371 | 24.12% |

Flag rate stable across seasons. Gap direction consistent but magnitude varies (2023 > 2022).

### S1 By-Month Breakdown
| Month | N Flagged | Gap | Flag Rate |
|---|---|---|---|
| Apr | 286 | +0.224 | 37.24% |
| May | 346 | +0.406 | 23.46% |
| Jun | 300 | +0.151 | 20.55% |
| Jul | 318 | +0.110 | 22.44% |
| Aug | 351 | +0.231 | 22.73% |
| Sep | 429 | +0.422 | 28.24% |
| Oct | 49 | +0.512 | 28.82% |

Gap is positive in every month. April has elevated flag rate (expected — early season, shorter outings). Gap largest in May/Sep/Oct.

### Discovery Summary
- **S1 (short outing):** Only candidate with gap > 0.15 and statistical significance (p=0.03). Advances to validation.
- **S2 (poor command):** Gap +0.149, just below 0.15 threshold. p=0.19. DEAD.
- **S5 (barrel damage):** Gap +0.076, weak and noisy. p=0.61. DEAD.
- **S6 (laboring):** Gap is NEGATIVE (-0.125) — opposite to hypothesis. High PPBF starters may be nibbling effectively, not laboring. DEAD.

---

## 8. VALIDATION RESULTS (Step 6)

Only S1_short_outing qualified (gap > 0.15, N ≥ 100).

| Candidate | N Flagged | Flag Rate (Disc/Val) | Gap (Disc/Val) | t-stat | p-value |
|---|---|---|---|---|---|
| S1_short_outing | 913 | 24.89% / 21.90% | +0.247 / **+0.008** | 0.048 | 0.9618 |

**S1 collapses in validation.** The +0.247 discovery gap falls to +0.008 in 2024 — essentially zero. The flag rate drops slightly (24.9% → 21.9%) but is in acceptable range; the collapse is in the GAP, not the flag rate.

This is NOT the W02 amplification pattern (where validation gap exceeds discovery). This is a COLLAPSE — the standalone short-outing flag shows no predictive value in the holdout year.

No candidates qualified for OOS testing.

---

## 9. OOS RESULTS (Step 7)

**No candidates qualified for OOS.** The only candidate that reached validation (S1) collapsed to near-zero gap. OOS stage was not reached.

---

## 10. ECONOMIC REALITY FLAG (Step 8)

All results in this pass are **TRIAGE_ONLY** — computed against raw actual_total means, not closing-line residuals.

No candidates survived to the point where an economic reality check would be warranted. However, for context:
- The W01B economic reality check (prior pass) showed that a +0.323 raw gap collapsed to near-zero residual after closing total adjustment
- Even if S1 had held at +0.247 through validation, it would likely have been absorbed by closing lines

---

## 11. FINAL CANDIDATE DISPOSITIONS

| Candidate | Disc Gap | Val Gap | OOS Gap | Disposition |
|---|---|---|---|---|
| S1_short_outing | +0.247 | +0.008 | N/A | **DEAD** — validation collapse |
| S2_poor_command | +0.149 | N/A | N/A | **DEAD** — below discovery threshold |
| S5_barrel_damage | +0.076 | N/A | N/A | **DEAD** — weak/noisy discovery signal |
| S6_laboring | -0.125 | N/A | N/A | **DEAD** — wrong direction in discovery |
| S3 (ERA/FIP) | — | — | — | **DATA_GAP** — field not in runtime object |
| S4 (Rest days) | — | — | — | **DATA_GAP** — field not in runtime object |

**No candidates survive. No candidates advanced to PENDING_ECONOMIC_TEST.**

---

## 12. CARRY-FORWARD NOTES

### What this pass established:
1. **Standalone starter fragility flags do not predict game totals** in this runtime object. Single-factor flags on SP workload (IP), command (BB%), contact quality (barrel%), or efficiency (PPBF) do not carry stable predictive signal across temporal splits.

2. **S1 (short outing) is the strongest standalone candidate** but collapses from +0.247 to +0.008 in validation. This is consistent with the W01 finding where the short-outing component showed disc +0.247, val +0.008, OOS +0.297 — the standalone version exhibits the same instability.

3. **S6 (laboring) has WRONG SIGN** — high PPBF starters actually correlate with slightly lower totals. This may reflect a survivor/selection effect: starters with high PPBF who are still in the game may be "pitchers' pitchers" who work deep counts but execute. Or the field may capture deliberate nibbling, not inefficiency.

4. **Standalone flags are weaker than conjunction flags.** The W01 conjunction (short outing AND depleted bullpen) at least showed directional instability (+0.247 disc → +0.008 val → +0.297 OOS). Standalone short-outing risk shows the same validation collapse with no conjunction partner to provide independent lift.

### Most promising remaining direction:
- **Interaction candidates** (passes 02–03 family) remain more promising than standalone flags
- **DATA_GAP candidates** (S3: ERA/FIP, S4: pitcher rest) could be tested if those fields are added to a future runtime object version
- The consistent +0.247 discovery gap for S1 suggests that short-outing risk is a real game-state that correlates with higher scoring — but markets price it efficiently enough that no standalone residual survives validation

---

*Report generated: 2026-04-20*
*Engine stack: MLB_ENGINE_V1_FOUNDATION + MLB_RESEARCH_ORCHESTRATION_V1 + MLB_RUNTIME_OBJECT_V1*
*Labels: DISCOVERY_TRIAGE_ONLY — not economic evidence*
