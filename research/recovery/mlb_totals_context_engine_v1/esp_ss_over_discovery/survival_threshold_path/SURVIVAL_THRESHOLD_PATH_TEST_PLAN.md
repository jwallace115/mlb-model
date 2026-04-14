# SURVIVAL_THRESHOLD_PATH — Test Plan Design

**Frozen:** 2026-04-14  
**Type:** Research test-plan design — no testing executed

---

## 1. PURPOSE

This document designs a staged test plan for SURVIVAL_THRESHOLD_PATH. No test has been run. The plan preserves strict PIT-safe discipline and separates retrospective descriptive confirmation from live pregame prediction.

## 2. RESEARCH OBJECT DEFINITION

Within the ESP=HIGH × SS=FRAGILE universe, full-game scoring may follow a path-bifurcation structure: games where the fragile starter survives the early stress window follow a lower-scoring trajectory, while games where the starter breaks early shift into a higher-scoring regime. The claim is that this produces a mixture distribution for full-game totals, not a smooth mean shift.

Retrospective path labeling (did the starter survive or break?) and live pregame prediction (can we predict which path before the game?) are separate research questions. They must not be blurred.

## 3. CORE PIT-SAFETY DISTINCTION

- Realized early survival / break is an **in-game outcome**. It cannot be used as a pregame feature.
- Retrospective path classification is valid only for descriptive confirmation (Stage A).
- Any future live object would require a **pregame predictor** of subpath probability, not realized path labels.
- A pregame predictor object is a different research object from the retrospective bifurcation finding. It requires its own validation chain.

## 4. STAGE A — RETROSPECTIVE DESCRIPTIVE CONFIRMATION

**Question:** Does the bifurcation pattern exist descriptively?

**Pre-registered definitions (must be frozen before any results are examined):**
- **Early window:** Starter completes fewer than 3.0 innings pitched = BREAK. Starter completes 3.0+ innings = SURVIVAL. This threshold is chosen structurally: 3 IP is one turn through the order, the minimum for a "quality" appearance.
- **Universe:** ESP=HIGH × SS=FRAGILE per frozen CE V1 bucket definitions.

**Test:**
1. Within the universe, split games into BREAK vs SURVIVAL using the frozen 3.0 IP threshold
2. Compare full-game total distributions for BREAK vs SURVIVAL subpaths
3. Report: mean, median, standard deviation, and distribution shape for each subpath
4. Report the split ratio (what fraction of games are BREAK vs SURVIVAL)

**Reporting requirements:**
- Results by season (2022, 2023, 2024, 2025) — all four must be reported
- Results by month (April through October)
- If the bifurcation pattern exists in fewer than 3 seasons, flag as a stability concern before advancing
- If a single month accounts for >40% of the pattern, flag before advancing

**Advancement criterion (must be defined before execution):**
- BREAK subpath mean total must exceed SURVIVAL subpath mean total by ≥ 1.5 runs
- The difference must be present in at least 3 of 4 seasons
- If either condition fails: do not advance to Stage B

**Temporal splits:**
- Discovery: 2022–2023
- Validation: 2024
- OOS: 2025
- Stage A descriptive confirmation may use all years for reporting, but the advancement criterion must hold in discovery AND validation independently

## 5. STAGE B — UNIQUENESS / NON-TRIVIALITY CHECK

**Question:** Is this bifurcation specific to ESP=HIGH × SS=FRAGILE, or generic?

**Test:**
1. Apply the same BREAK/SURVIVAL split (3.0 IP threshold) to:
   - All MLB games (board baseline)
   - ESP=HIGH × SS=STABLE
   - ESP=LOW × SS=FRAGILE
   - ESP=MID × SS=MODERATE
2. Compare the BREAK–SURVIVAL scoring gap in each universe
3. The gap in ESP=HIGH × SS=FRAGILE must be materially larger than in all comparison universes

**Kill condition:**
- If the board-wide BREAK–SURVIVAL gap is ≥ 80% as large as the ESP=HIGH × SS=FRAGILE gap, the pattern is generic and the branch is closed
- Uniqueness comparison must be reported by season — a pattern unique in aggregate but driven by one season is not stable

## 6. STAGE C — PREGAME PREDICTABILITY SCREEN

**Question:** Can any PIT-safe pregame feature predict subpath probability?

**Rules:**
- No realized early outcomes may enter this stage
- Only pregame-available, PIT-safe features are allowed

**Candidate pregame proxy families:**
- Starter expected innings (rolling average IP from prior starts, shift(1))
- First-inning vulnerability proxies (rolling first-inning ERA or OPS-against, shift(1))
- Starter pitch-count efficiency (pitches per IP rolling, shift(1))
- Pregame lineup depth / contact quality vs starter handedness *(lineup-confirmation-dependent)*

**Screen protocol:**
1. Within the ESP=HIGH × SS=FRAGILE universe, compute candidate proxies PIT-safe
2. Test whether any proxy meaningfully separates BREAK from SURVIVAL games in discovery data only
3. If a credible proxy is identified, it constitutes a **new research object** distinct from the Stage A retrospective finding
4. That new object requires its own independent discovery/validation/OOS chain and may not inherit Stage A's sample as discovery evidence

**If no credible pregame proxy exists:**
- The branch remains descriptive only
- It does not proceed toward a live object
- This is an acceptable outcome — not every real pattern is tradable

## 7. STAGE D — GO / NO-GO RULES

| Condition | Decision |
|-----------|----------|
| Stage A bifurcation confirmed, advancement criteria met | Proceed to Stage B |
| Stage A fails advancement criteria | CLOSE — no further testing |
| Stage B confirms uniqueness | Proceed to Stage C |
| Stage B shows generic pattern | CLOSE — bifurcation is board-wide, not special |
| Stage C identifies credible pregame proxy | New object — requires own validation chain |
| Stage C finds no pregame proxy | HOLD as descriptive-only — do not deploy |
| Any stage shows seasonal instability | Flag and reassess before advancing |

The advancement criterion from Stage A to Stage B must be defined before Stage A is executed (defined above: ≥1.5 run gap, present in ≥3 seasons). Setting this threshold after seeing results would contaminate Stage B.

## 8. LEAKAGE / IDENTITY RISKS

- **Post-hoc early-window tuning:** If 3.0 IP doesn't produce results and the researcher tries 2.0 or 4.0, this is a new hypothesis, not a refinement. Each window is a separate object.
- **Collapsing retrospective and live objects:** Using Stage A's retrospective path labels as if they were pregame features. They are not.
- **Same-day postgame information:** Using realized pitch counts, actual bullpen usage, or game-state information as pregame predictors.
- **Universe redefinition:** Changing the ESP/SS bucket boundaries after discovery.
- **FRONT_LOADED_DISTRIBUTION_SHAPE overlap:** If bifurcation confirmation looks identical to continuous front-loading, the two ideas may not be distinct. The distinctiveness test is: does the pattern require the BREAK/SURVIVAL split, or does it exist without imposing one?

## 9. REQUIRED DATA AND APPROVED FEATURE FAMILIES

**Retrospective descriptive outcomes (Stages A–B):**
- Starter innings pitched per game (from `mlb/data/pitcher_game_logs.parquet`, PIT-safe with shift(1) for features, raw for outcome labeling)
- Inning-level scoring (MLB Stats API linescore)
- Full-game totals (from `sim/data/game_table.parquet`)
- CE V1 bucket labels (from `context_engine_output_table.parquet`)

**Possible pregame predictors (Stage C only):**
- Rolling starter IP average (pitcher_game_logs, shift(1).expanding() or rolling window)
- Rolling first-inning performance metrics (pitcher_game_logs, shift(1))
- Pregame lineup descriptors if lineup-confirmed *(lineup-confirmation-dependent)*

**Excluded sources regardless of relevance:**
- `research/opponent_adjusted_engine_v2/pitcher_recent_adjusted_features.parquet`
- Any file derived from `sim/phase2_build_features.py`
- Any V1-era feature table in `mlb_sim/data/` with ambiguous historical construction lineage

## 10. WHAT WOULD KILL THE IDEA EARLY

- Stage A: BREAK–SURVIVAL mean gap < 1.5 runs
- Stage A: Pattern present in fewer than 3 of 4 seasons
- Stage B: Board-wide gap ≥ 80% of universe-specific gap
- Stage C: No PIT-safe pregame proxy meaningfully separates subpaths
- Any stage: Effect collapses into generic bullpen exposure (bullpen IP fully explains the gap)
- Any stage: Effect is indistinguishable from FRONT_LOADED_DISTRIBUTION_SHAPE without the split
- Definitions too flexible to freeze (multiple windows all "work" — suggests tuning artifact)

## 11. STATUS

SURVIVAL_THRESHOLD_PATH test-plan design is frozen for research use only. No testing has been run, no signal has been defined, and no live or shadow object behavior has been changed.

Any actual test execution requires a separate approved prompt. The five mandatory research-discipline checks (PIT-safety, discovery/validation/OOS separation, research=live identity, contaminated-positive exclusion, actual-price requirement) become mandatory at execution.
