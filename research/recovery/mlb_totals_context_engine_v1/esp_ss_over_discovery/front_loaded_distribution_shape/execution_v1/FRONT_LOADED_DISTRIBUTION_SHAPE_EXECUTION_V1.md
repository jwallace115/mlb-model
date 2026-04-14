# FRONT_LOADED_DISTRIBUTION_SHAPE — EXECUTION V1

**Executed:** 2026-04-14
**Type:** Frozen PIT-safe research execution — strict pit-safe
**Output dir:** research/recovery/mlb_totals_context_engine_v1/esp_ss_over_discovery/front_loaded_distribution_shape/execution_v1/

---

## 1. INPUT AUDIT

- **CE V1 table:** 9,715 rows, seasons 2022–2025 (2,430 / 2,430 / 2,427 / 2,428)
- **Frozen tercile cuts:** ESP > 48.5482 (HIGH), SS <= 45.9406 (FRAGILE)
- **Universe (ESP=HIGH x SS=FRAGILE):** 1,743 games [2022: 356, 2023: 518, 2024: 422, 2025: 447]
- **ADJ1 (ESP=HIGH x SS=MODERATE):** 977 games [declared before Stage B] — isolates SS effect
- **ADJ2 (ESP=MID x SS=FRAGILE):** 1,057 games [declared before Stage B] — isolates ESP effect
- **Board sample:** 2,000 games, random_state=42
- **Inning cache:** 5,020 unique game_pks fetched from MLB Stats API linescore endpoint; 0 null total_runs
- **Data available in CE V1:** actual_total, actual_f5_total present for all 9,715 rows — inning-level scoring required API fetch
- **Inning window:** innings 1–3 (frozen in hardening memo; not tuned)

---

## 2. STAGE A: DISCOVERY (2022–2023)

| Metric | Universe | Board | Gap |
|---|---|---|---|
| n | 874 | 1003 | — |
| inn_1_3_share mean | 35.061% | 33.936% | +1.126pp |
| inn_1_3_share median | 33.333% | 33.333% | +0.000pp |
| t-stat | 0.991 | — | p=0.3216 |

**CRITERION (>=+7pp): FAIL — gap is +1.13pp**

### By season (discovery):

| Season | Universe | Board | Gap |
|---|---|---|---|
| 2022 | 34.880% (n=356) | 33.424% (n=509) | +1.455pp |
| 2023 | 35.186% (n=518) | 34.463% (n=494) | +0.723pp |

### F5-to-full-game ratio (discovery):
- Universe: 58.19%
- Board: 56.82%
- Gap: +1.37pp

### Day vs evening (discovery):
No meaningful confound — day gap is -1.21pp, evening gap is +1.40pp; both far below threshold.

### Month breakdown (discovery):
No single month exceeds +7pp (April +3.95pp is highest). October shows -18pp but n=16 (noise).

---

## 3. STAGE A: VALIDATION (2024) AND OOS (2025)

**NOT EVALUATED — Stage A discovery FAILED. Per protocol, no stage continues after kill.**

For completeness (not decision-relevant since discovery failed):

| Period | Universe | Board | Gap | p |
|---|---|---|---|---|
| Validation (2024) | 33.743% (n=422) | 30.676% (n=489) | +3.068pp | 0.0566 |
| OOS (2025) | 35.427% (n=447) | 31.332% (n=508) | +4.094pp | 0.0095 |

Both forward periods also fail the +7pp threshold.

### All seasons summary:

| Season | Universe | Board | Gap |
|---|---|---|---|
| 2022 | 34.880% | 33.424% | +1.455pp |
| 2023 | 35.186% | 34.463% | +0.723pp |
| 2024 | 33.743% | 30.676% | +3.068pp |
| 2025 | 35.427% | 31.332% | +4.094pp |

The gap ranges from +0.7pp to +4.1pp. There is a detectable but small positive tendency, peaking in OOS. None reach threshold.

---

## 4. STAGE B: UNIQUENESS

**NOT EVALUATED — Stage A failed. Per protocol, Stage B does not run after a kill.**

Adjacent universes were declared before results (required by protocol):
- ADJ1 (ESP=HIGH x SS=MOD): declared to isolate SS effect
- ADJ2 (ESP=MID x SS=FRAG): declared to isolate ESP effect

Discovery-period statistics for reference:
- Universe: 35.061%
- ADJ1: 32.895% (gap vs universe: +2.166pp)
- ADJ2: 32.736% (gap vs universe: +2.325pp)
- Board: 33.936%

All four groups cluster in the 32.7–35.1% range, suggesting no meaningful separation.

---

## 5. STAGE C: LIVE PATH SCREEN

**NOT EVALUATED — Stage A failed.**

---

## 6. FINAL VERDICT

**NO-GO — CLOSE NOW**

**Reason:** Discovery gap +1.13pp, far below the +7pp threshold. No stage can continue after a kill.

The mechanism claim was: within ESP=HIGH × SS=FRAGILE games, innings 1–3 carry a disproportionately large share of total run mass compared to the MLB board. The empirical result shows a +1.1pp gap in discovery — consistent with a small positive tendency but far below the pre-registered +7pp threshold required for advancement. The median gap is 0pp (both universe and board median = 33.3%). There is no structural front-loading effect detectable in this universe.

### What the data show:
- The ESP=HIGH × SS=FRAGILE universe has a small, statistically non-significant elevation in inn_1_3_share vs the board in discovery (+1.1pp, p=0.32)
- The gap is larger in OOS 2025 (+4.1pp, p=0.009) but still well below threshold and evaluated only for completeness since discovery failed
- Adjacent universes cluster near the same range (ADJ1: 32.9%, ADJ2: 32.7%, Board: 33.9%) — no specificity
- No day/evening confound: evening games show the same small gap pattern
- Month variation is noisy; no structural concentration
- The F5/full-game ratio shows only +1.4pp elevation vs board (58.2% vs 56.8%) — consistent with the small positive tendency

### Mechanism disposition:
The idea is not empirically supported. The mechanism claim was sufficiently specific and falsifiable; it was tested correctly and the data do not support it. The hypothesis is closed.

---

## 7. FILES WRITTEN

1. `FRONT_LOADED_DISTRIBUTION_SHAPE_EXECUTION_V1.md` — this file
2. `FRONT_LOADED_DISTRIBUTION_SHAPE_EXECUTION_V1_REGISTRY.json`
3. `FRONT_LOADED_DISTRIBUTION_SHAPE_STAGE_TABLES.csv`
4. `FRONT_LOADED_DISTRIBUTION_SHAPE_SELF_AUDIT.md`
5. `inning_cache.json` — 5,020 game linescore cache (MLB Stats API)

---

## 8. SELF-AUDIT

See `FRONT_LOADED_DISTRIBUTION_SHAPE_SELF_AUDIT.md`
