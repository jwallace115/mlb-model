# PHASE 2 — Locked Failure Modes

**Date:** 2026-04-12
**Scope:** All known contamination classes affecting MLB totals objects

---

## Failure Mode 1: End-of-Season FanGraphs Feature-Construction Lookahead

**Mechanism:** `sim/modules/fg_historical.py` called FanGraphs API with `season=YYYY, ind=0`,
returning full-season aggregates. Every game in a season saw the same end-of-year stats.
April games used September information.

**Affected features:** 14 of 25 V1 features (sp_xfip x2, sp_k_pct x2, sp_bb_pct x2,
sp_avg_ip x2, wrc_plus x2, bullpen_delta x2, bp_delta_exposure x2) plus flyball_wind interaction.

**Affected objects:**
- A1 (V1 Ridge contaminated) — PRIMARY victim, all weights learned from contaminated data
- A2 (V1 PIT rebuild) — FIXED, but result is negative OOS
- B1 (S12) — cutoff 8.4468 derived from season-final xFIP
- B2 (P09) — cutoff derived from contaminated research cycle
- D1 (F5 Totals Engine) — threshold 0.57 tuned on contaminated V1 probabilities
- D2 (F5 Over Engine) — same V1 dependency
- E1/E2 (Team Totals) — research coefficient 0.621 derived from contaminated SP data

**Detection:** Confirmed by Gate 4 check — Gerrit Cole had 15 unique PIT xFIP values in 2022
vs 1 value in contaminated build.

---

## Failure Mode 2: MoneyPuck-Dependent Features (NHL cross-reference)

**Mechanism:** NHL model features sourced from MoneyPuck which has its own undisclosed
feature construction. Not directly applicable to MLB but establishes pattern of
third-party data trust issues.

**Affected MLB objects:** NONE directly. Referenced for pattern awareness.

---

## Failure Mode 3: Research/Live Identity Mismatch

**Mechanism:** The object tested in research is not the same object running in production.
Different inputs, different thresholds, different formulas.

**Primary victim:** E1/E2 (Team Totals) — THREE distinct TT objects found:
1. Research version: xFIP-based with baseline 4.231, end-of-season lookahead
2. Live pipeline version: ERA-based with baseline 4.50, PIT-safe expanding mean
3. Original design doc: Yet another formula variant
None of the three are equivalent. Research conclusions cannot be applied to live code.

**Secondary victims:**
- C1-C5 (ADJ signals) — Research used V1 p_under>0.57 as interaction gate; live fires standalone on combined>0. Direction is different (research = interaction signal, live = standalone). However, live code is arguably cleaner (no V1 dependency).

---

## Failure Mode 4: Discovery-Validation Leakage

**Mechanism:** Using the same data to discover a pattern and validate it. The "OOS" test
is not truly out-of-sample because the researcher saw the OOS data during discovery.

**Primary victim (NBA):** Archetype features discovered via full-dataset median splits.
**MLB relevance:** Over Scanner Wave 1 promoted OV043/OV016/OV001 based on 2024-2025 data
with V1 interaction lift. The V1 interaction is contaminated. Standalone results are cleaner
but the promotion decision itself was influenced by seeing the OOS data.

---

## Failure Mode 5: Within-Sample Median Classification

**Mechanism:** Using sample-dependent quantile boundaries (median, Q80, etc.) that shift
with different data. A threshold that looks optimal in-sample may be noise.

**Affected objects:**
- B1 (S12) — cutoff 8.4468 is the P80 of 2024 S12 values
- B2 (P09) — cutoff 31.7305 is the Q20 of hard-hit x park values
- C8 (KP04) — thresholds from P75 percentiles of historical data

---

## Failure Mode 6: PGL Proxy Failure

**Mechanism:** Pitcher Game Log (PGL) features used as proxy for missing Statcast/FG
data may not capture the same signal. Zone% and Whiff% from PGL are approximations
of CSW and Whiff rate from Statcast.

**Affected objects:**
- C8 (KP04) — uses PGL-derived metrics; 0 fires in 226 games suggests thresholds
  calibrated on Statcast data don't transfer to PGL proxies

---

## Failure Mode 7: Degraded-Mode Silent Overfiring

**Mechanism:** When a required input is missing (e.g., pitcher ERA for a new starter),
the signal falls back to a degraded mode that fires anyway due to structural bias
in the formula.

**Primary victim:** E1 (Team Totals) — 56% of records in degraded mode, 93.8% total
fire rate. base_gap = closing_total * 0.5015 - 0.248 structurally > 0 for most lines,
so even with zero SP adjustment the signal fires.

---

## Failure Mode 8: Stale Cache / Frozen Priors

**Mechanism:** Static lookup tables or cached priors that were correct at creation time
but degrade as the underlying distribution shifts.

**Affected objects:**
- A1 (V1 Ridge) — sigma=4.361 from contaminated training, real sigma likely ~4.42+
- Umpire ratings table — ~50 umpires with career rates; new umpires or career shifts not captured
- Park factors — static per-park config in config.py; does not account for park modifications

**Severity:** Low for umpire/park (slow-changing). Moderate for sigma (affects all confidence intervals).

---

## Cross-Reference: Failure Mode → Object Matrix

| Object | FM1 | FM2 | FM3 | FM4 | FM5 | FM6 | FM7 | FM8 |
|--------|-----|-----|-----|-----|-----|-----|-----|-----|
| A1 V1 Ridge (contaminated) | X | | | | | | | X |
| A2 V1 PIT rebuild | | | | | | | | |
| A3 V1 Rules Mode | | | | | | | | X |
| A4 V2 Engine | | | | | | | | |
| B1 S12 | X | | | | X | | | |
| B2 P09 | X | | | | X | | | |
| B3 ST02 | | | | | | | | |
| B4 flyball_wind | X | | | | | | | |
| C1-C5 ADJ signals | | | X | X | | | | |
| C6 CS013 | | | | | | | | |
| C7 CS028 | | | | | | | | |
| C8 KP04 | | | | | X | X | | |
| C9 CS004 | | | | | | | | |
| C10 Combined Short Exit | | | | | | | | |
| D1 F5 Under Engine | X | | | | | | | |
| D2 F5 Over Engine | X | | | | | | | |
| D3 F5 RL Signal B | | | | | | | | |
| D4 F5 RL Away | | | | | | | | |
| D5 CS025 F5 RL overlay | | | | | | | | |
| E1/E2 Team Totals | X | | X | | | | X | |
| F1 Alt-Total Surface | | | | | | | | |
| F2 Run-Line Asymmetry | | | | | | | | |
| G1 Over Scanner | | | | X | | | | |
| H1 Distribution Shape | | | | | | | | |
| H2 NRFI Selector | | | | | | | | |
| H3 MLB Props | | | | | | | | |
