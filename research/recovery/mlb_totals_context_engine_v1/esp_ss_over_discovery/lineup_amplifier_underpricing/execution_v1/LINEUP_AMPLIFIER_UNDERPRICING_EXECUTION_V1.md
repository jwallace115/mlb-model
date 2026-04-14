# LINEUP_AMPLIFIER_UNDERPRICING — Execution V1

**Executed:** 2026-04-14
**Protocol:** Frozen LINEUP_AMPLIFIER_UNDERPRICING test per hardening memo 2026-04-13
**Scope:** ESP=HIGH x SS=FRAGILE universe; trait families BB_PCT, ISO; generic control OPS

---

## 1. INPUT AUDIT

### CE V1 Universe
- Context engine table: 9,715 rows (2022-2025)
- Frozen tercile cuts: ESP > 48.5482, SS <= 45.9406
- Universe: 1,743 games total
- After trait feature merge: 1,692 games (51 dropped — early-season rolling window insufficient)

### Season breakdown (clean universe)
- 2022: 342 games
- 2023: 518 games
- 2024: 422 games
- 2025: 410 games
- All seasons well above 100-game minimum

### Feature construction
CE V1 has NO offensive columns (confirmed). Rolling traits built from:
- Source: mlb/data/hitter_game_logs.parquet (204,548 rows, seasons 2022-2025)
- Available columns: game_pk, game_date, team, PA, AB, hits, singles, doubles, triples, HR, walks, HBP, sac_flies, K, ISO, OBP, SLG
- Team name mapping applied: CHW->CWS, TBR->TB, SDP->SD, KCR->KC, ARI->AZ, WSN->WSH, SFG->SF
- Rolling window: 30 games, shift(1) before rolling (strict PIT-safe)
- Minimum periods: 15 games

### Trait families (pre-declared before any outcome data examined)
1. **BB_PCT (avg_bb_pct):** Average of home and away team rolling 30-game BB% (walks/PA)
2. **ISO (avg_iso):** Average of home and away team rolling 30-game ISO ((2B + 2*3B + 3*HR)/AB)
3. **OPS (avg_ops):** Average of home and away team rolling 30-game OPS — GENERIC LINEUP CONTROL
4. **Handedness/platoon:** SKIPPED — lineup-confirmation-dependent, no clean pregame source

### Audit status: PASS — all four pre-declared families accounted for, no additional families tested

---

## 2. STAGE A: DISCOVERY (2022-2023)

### Discovery set
- 860 games (2022: 342, 2023: 518)

### Frozen median splits (derived from discovery data only)
- avg_bb_pct median: 0.081911
- avg_iso median: 0.156165
- avg_ops median: 0.708279

### BB_PCT results
- HIGH BB_PCT (n=430): mean actual total = 9.488
- LOW BB_PCT (n=430): mean actual total = 9.191
- Raw gap: +0.298 (t=0.92, p=0.355) — NOT statistically significant
- Partial correlation controlling for OPS: r=-0.010, p=0.775 — EFFECTIVELY ZERO
- Within HIGH-OPS subgroup: gap=+0.163 (p=0.732)
- Within LOW-OPS subgroup: gap=+0.250 (p=0.595)
- By season: 2022 gap=+0.335, 2023 gap=-0.101 (DIRECTION REVERSAL)

### ISO results
- HIGH ISO (n=430): mean actual total = 9.395
- LOW ISO (n=430): mean actual total = 9.284
- Raw gap: +0.112 (t=0.35, p=0.729) — NOT statistically significant
- Partial correlation controlling for OPS: r=+0.025, p=0.473 — EFFECTIVELY ZERO
- Within HIGH-OPS subgroup: gap=+0.419 (p=0.493)
- Within LOW-OPS subgroup: gap=-0.960 (p=0.111)
- By season: 2022 gap=-0.904, 2023 gap=+0.249 (SIGN REVERSAL)

### OPS (generic control) results
- HIGH OPS (n=430): mean actual total = 9.540
- LOW OPS (n=430): mean actual total = 9.140
- Raw gap: +0.400 (t=1.24, p=0.214) — NOT statistically significant
- By season: 2022 gap=-0.893, 2023 gap=+0.774 (SIGN REVERSAL even for generic lineup quality)

### Kill rule evaluation
**Kill rule: If NO trait family shows residual beyond wRC+/OPS control: STOP**

- BB_PCT: partial_r=-0.010 — no residual beyond OPS control. TRIGGERED.
- ISO: partial_r=+0.025 — no residual beyond OPS control. TRIGGERED.

Additional concerns:
- Seasonal instability: both trait families and the generic OPS control show sign reversals between 2022 and 2023
- This indicates the underlying mechanism claim — that lineup traits specifically amplify scoring within the ESP=HIGH x SS=FRAGILE universe — does not hold even in discovery
- The raw gaps for BB_PCT and ISO are not only non-significant but near-zero after controlling for generic lineup quality
- Even the generic lineup control (OPS) is unstable between seasons within this universe

**KILL RULE TRIGGERED. Test halted after Stage A.**

---

## 3. STAGE B: VALIDATION (2024)

**NOT EXECUTED.** Kill rule triggered in Stage A.

---

## 4. STAGE C: OOS (2025)

**NOT EXECUTED.** Kill rule triggered in Stage A.

---

## 5. STAGE D: LIVE PATH SCREEN

**NOT EXECUTED.** Kill rule triggered in Stage A.

---

## 6. FINAL VERDICT

**NO-GO — CLOSE NOW**

The mechanism claim requires that specific lineup trait families (BB_PCT, ISO) add predictive value for actual total scoring within the ESP=HIGH x SS=FRAGILE universe, beyond what generic lineup quality (OPS) already explains. This claim was tested in discovery (2022-2023) and failed on every dimension:

- Both trait families show near-zero partial correlations after OPS control (r=-0.010 and r=+0.025)
- Neither raw gap is statistically significant (p=0.355, p=0.729)
- Both traits show direction reversals across 2022 and 2023
- The generic OPS control itself is unstable within this universe (sign reversal 2022->2023)

The mechanism does not appear to exist in the data. The idea that the market specifically underprices lineup trait interactions within this structural state is not supported. The most likely explanation is that the ESP=HIGH x SS=FRAGILE universe does not create a coherent lineup-amplification environment measurable from rolling team-level stats.

LINEUP_AMPLIFIER_UNDERPRICING is **CLOSED**. No live object. No shadow object. No further research warranted under this mechanism claim without a materially different data source or mechanism reformulation.

---

## 7. DATA SOURCES USED

- research/recovery/mlb_totals_context_engine_v1/context_engine_output_table.parquet
- mlb/data/hitter_game_logs.parquet

No live, shadow, or excluded sources were touched.
