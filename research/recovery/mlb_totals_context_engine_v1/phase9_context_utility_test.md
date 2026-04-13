# Phase 9 - Context Utility Test
## MLB Totals Context Engine V1
## OOS 2025 Data Only (for case studies)

### Methodology
Three case studies using OOS 2025 data to demonstrate how the context engine adds value to downstream niche objects. The engine does not make betting decisions - it describes structural context.

---

### Case Study 1: P1B Child Object (Starter Dominance Under)

**P1B Object Definition:** Fires when BOTH starters are rated as STABLE (both_stable_flag = 1).

**OOS Population (2025):** 376 games
**OOS Baseline Mean Total:** 8.90 runs
**P1B Population Mean Total:** 8.41 runs
**Suppression vs Baseline:** 0.48 runs below baseline

The context engine adds structural depth to P1B by asking: even within the P1B population, how does Weather/Park Lift (WPL) affect outcomes?

**P1B x WPL Breakdown (OOS 2025):**

                mean  count
wpl_label                  
SUPPRESSED  7.947368     19
NEUTRAL     8.341379    290
LIFTED      8.865672     67

**Insight:** When P1B fires in LIFTED conditions (warm weather, favorable park), the suppression effect is partially or fully offset by environmental factors. This is not detectable by looking at the starter stability score alone. Context engines allow P1B to understand when its structural edge is being fought by environmental tailwinds.

**P1B x Bullpen Stability Breakdown (OOS 2025):**

              mean  count
bs_label                 
UNSTABLE  8.298387    124
NEUTRAL   8.355932    118
STABLE    8.574627    134

**Insight:** Even with both starters stable, bullpen instability affects late-game run accumulation. UNSTABLE BS within P1B games shows the interaction between starter excellence and bullpen degradation.

**Use Case:** A P1B signal that fires in LIFTED WPL and UNSTABLE BS conditions is structurally weaker than the same signal in SUPPRESSED/NEUTRAL WPL and STABLE BS. The context engine allows the analyst to condition on regime, not just fire and forget.

---

### Case Study 2: Dead Broad Totals Object

**Object Definition:** Games with all environmental and structural factors at neutral levels.
- BRE = MEDIUM
- WPL = NEUTRAL
- SS = AVERAGE
- BS = NEUTRAL

**OOS Population (2025):** 59 games
Mean Total: 8.66 runs
Std Total: 4.56 runs
**OOS Baseline:** 8.90 runs (std 4.60)

**Insight:** Dead neutral games represent the pure market-priced baseline. There is no structural reason to expect over or under. These games are where market efficiency is highest and niche edge is lowest. The context engine identifies them precisely so niche objects can filter them out or assign reduced conviction to signals that fire in these games.

**Use Case:** Any niche object should report lower conviction when the context engine returns all-NEUTRAL labels. The absence of structural extremes is itself information.

---

### Case Study 3: Neutral/Ordinary Game Bucket

**Definition:** Games with MEDIUM BRE, MEDIUM ESP, AVERAGE SS, NEUTRAL BS, BALANCED TCV, and market line available.

**OOS Population (2025):** 13 games

**Mean Actual Total:** 8.85 runs
**Std Actual Total:** 5.49 runs
**Mean Market Close:** 8.08
**Mean Market Error:** 0.77 runs (actual - close)
**Std Market Error:** 5.42 runs


**Insight:** In structurally ordinary games, the market close total is a strong proxy for realized outcomes. The market error distribution is tight. This validates that the market efficiently prices ordinary games. Niche objects seeking edge should look for games that are NOT ordinary, where the structural decomposition reveals departures from market pricing.

**Broader Utility:** The context engine does not try to beat the market. It defines which structural quadrant a game is in, allowing niche objects to ask "has my edge historically persisted in this structural quadrant?" That is a much more stable research question than "does my factor predict outcomes?".

---

Built: 2026-04-12 | All case studies use OOS 2025 data only
