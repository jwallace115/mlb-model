# PHASE 3 — Classification of Every Inventoried Idea

**Date:** 2026-04-12
**Standard:** Per PHASE0_CLASSIFICATION_STANDARD.md

---

## A. Core Models

### A1. V1 Ridge Totals (Contaminated)
**Classification: REBUILD REQUIRED**

14 of 25 training features used end-of-season FanGraphs aggregates (FM1). Model weights
learned from artificially clean signal. Sigma=4.361 is too tight (real ~4.42+). The model
is directionally correct (xFIP genuinely predicts totals) but the coefficients are
over-fitted to contaminated data. Live inference is clean (daily FG API) but weights
cannot be trusted.

### A2. V1 Ridge Totals (PIT Clean Rebuild)
**Classification: CLEAN KILL**

Fairly tested with PIT-safe expanding-mean features. Honest temporal split.
Results: 2024 ROI=-10.5% (N=175), 2025 ROI=-13.2% (N=55) at p_under>0.57.
Negative at ALL thresholds tested (0.53 through 0.61). The clean V1 architecture
with 25 features and Ridge alpha=50 does not produce a profitable totals signal.

### A3. V1 Rules Mode
**Classification: ARCHIVE**

Not a trained model. Multiplicative heuristic engine using live FG API daily.
No contamination possible (no historical training). Produces the daily card
in rules mode. Not itself a totals "idea" to test — it is operational infrastructure.

### A4. V2 Baseline Engine (Model_B)
**Classification: CLEAN KILL**

Tested fairly with PIT-safe features. 14-feature Ridge, target=market_error.
RMSE barely beats market (+0.01). Strong over bias: mean predicted edge +0.43 runs.
Generates ~900 over signals/season, ~0 under. Not bettable. The V2 architecture
does not produce exploitable signal against the totals market.

---

## B. Overlays

### B1. S12 Overlay (CSW-xFIP Composite)
**Classification: CLEAN KILL**

S12 standalone was retested with PIT-safe data. Overall ROI=-0.8% (N=2596).
In-sample ROI is negative at EVERY threshold tested. OOS 2025 shows +4.7% but
this is a single season and is not stable (2/4 seasons positive). The cutoff
8.4468 was derived from contaminated season-final xFIP (FM1+FM5). Even with
clean data, the signal does not survive. Verdict: dead at all thresholds, permanently.

### B2. P09 Overlay (Hard-Hit x Park)
**Classification: CLEAN KILL**

OOS blind-under test: active games hit 50.9%, inactive hit 52.8%. The overlay
INVERTS — games where P09 fires actually perform WORSE than games where it does
not. Rederived cutoff collapses OOS. Direction is wrong. Permanently dead.

### B3. ST02 Overlay (Road Trip Fatigue)
**Classification: CLEAN KILL**

2022-2025 historical: N=2,172 qualifying games, under rate=52.21%, ROI=-0.3%.
Zero fires in 2026 shadow (early season, rare trigger). V1-dependent overlay
with no standalone value. The road-trip fatigue hypothesis produces near-zero
signal against the market. The market already prices travel effects.

### B4. flyball_wind Discrete Overlay
**Classification: ARCHIVE**

Tested as V2 overlay: FW-active over hit=49.1%, inactive=46.3%. +4pp lift
but within an unprofitable universe (V2 over bias). Already captured as
continuous feature in V2 model. The discrete version adds nothing beyond
what the continuous coefficient provides. Retain for reference only.

---

## C. Shadow Signals

### C1. ADJ_CONTACT
**Classification: RETEST REQUIRED**

PIT-safe (per-start Statcast shift(1).rolling). Live fires independently of V1
(combined>0 gate). Shadow 2026: 53.8% hit rate (65 resolved). Research used V1
interaction gate (FM3) — conclusions cannot transfer. Live standalone needs N=100+
with real closing prices to evaluate. Mechanism is sound (opponent-adjusted contact
rate predicts run suppression). Retest at scale.

### C2. ADJ_HH
**Classification: RETEST REQUIRED**

Same PIT safety as C1. Best early shadow performer: 61.8% hit rate (34 resolved).
Small sample. Research interaction gate was V1-dependent (FM3). Live standalone
is clean. High-priority retest target — needs N=100+ with real prices.

### C3. ADJ_K_RATE
**Classification: RETEST REQUIRED**

Same PIT safety. Shadow 2026: 56.7% (30 resolved). Mechanism sound (K-rate
predicts run suppression). Needs larger sample with real prices.

### C4. ADJ_BB_RATE
**Classification: CLEAN KILL**

PIT-safe but shadow 2026 shows 50.0% hit rate (16 resolved). Walk rate
does not independently predict under outcomes. The mechanism is weaker
than K-rate or contact rate for totals prediction. Kill.

### C5. ADJ_RUN_SUPP
**Classification: RETEST REQUIRED**

Shadow 2026: 55.9% (34 resolved). PIT-safe. Run suppression composite
has directional promise. Needs N=100+ with real prices.

### C6. CS013
**Classification: UNVERIFIABLE**

0 fires in 128 games. The signal threshold is too restrictive for the
current data environment. Cannot evaluate a signal that never fires.
Code is clean (PIT-safe boxscores). The IDEA may have merit but the
IMPLEMENTATION produces no testable output.

### C7. CS028
**Classification: UNVERIFIABLE**

2 fires in 105 games, 1 resolved. Trivially small. Same as CS013 —
the implementation is too restrictive to generate evaluable evidence.

### C8. KP04
**Classification: UNVERIFIABLE**

0 fires in 226 games. Thresholds from Statcast P75 percentiles (FM5)
may not transfer to PGL-derived proxies (FM6). The signal never activates.
Cannot evaluate.

### C9. CS004
**Classification: RETEST REQUIRED**

Shadow signal with PIT-safe boxscore inputs. CS004 under-interaction
research (research/signal_discovery/cs004_under_interactions/) shows
directional promise. Needs evaluation of current shadow fire rate and
hit rate.

### C10. Combined Short Exit
**Classification: UNVERIFIABLE**

0 fires in 128 games. PIT-safe (IP shift(1).rolling(15)). The
short-starter-exit hypothesis has merit but the implementation
produces no fires. Cannot evaluate.

---

## D. F5 Signals

### D1. F5 Totals Engine (Under)
**Classification: VOID / CONTAMINATED**

Directly consumes V1 p_under probabilities. Threshold 0.57 tuned on
contaminated V1 output. Signal count drops 85% (1033->160) with clean V1.
The engine has no independent signal — it is entirely parasitic on V1.
With V1 dead (A2 CLEAN KILL), F5 under engine is void.

### D2. F5 Totals Engine (Over)
**Classification: VOID / CONTAMINATED**

Same V1 dependency as D1. Research shows promising numbers (59.2% win rate,
+12.4% ROI at p>0.57) but these were computed using contaminated V1
probabilities. The apparent edge is likely inflated by V1 lookahead.
Cannot trust any of the reported numbers.

### D3. F5 Run Line Signal B (Home)
**Classification: CLEAN (KEEP)**

Zero red flags. Uses live FG xFIP (daily-fresh). Independent of V1.
Threshold: xFIP gap >= 1.0. Pooled ROI +27.9% (N=335, 2024-2025).
PIT-safe. Only surviving MLB totals-market object with positive evidence.

### D4. F5 Run Line Signal B (Away)
**Classification: CLEAN KILL**

Away-side mirror tested fairly: ROI=-3.5% in 2025. The edge is strongly
asymmetric — home-side signals are profitable, away-side mirrors are not.
The market correctly prices away-team starter dominance in F5 run lines.

### D5. CS025 F5 RL Command Overlay
**Classification: RETEST REQUIRED**

Overlay on D3: adds CSW/BB command quality filter. Research shows 74.5% hit
rate (N=153), permutation=100th percentile. However, it does NOT improve over
unfiltered Signal B (73.4%). The overlay adds complexity without adding edge.
Retest only if D3 shows signs of degradation — then command filter may help
as a precision tool.

### D6. F5 Standalone (Not Built)
**Classification: ARCHIVE**

Does not exist. Would need independent clean architecture. Deferred
indefinitely — D3 is the productive F5 path.

---

## E. Team Totals

### E1. Team Totals (Home Under)
**Classification: VOID / CONTAMINATED**

Identity NEVER-MATCHED (FM3). Three distinct TT objects found in codebase,
none equivalent. Research used xFIP with end-of-season lookahead (FM1).
Live uses ERA with PIT-safe expanding mean. Coefficient 0.621 derived from
contaminated research. 93.8% fire rate = pathological overfiring (FM7).
56% degraded mode. No price data. 5/5 red flags. The most contaminated
object in the entire system.

### E2. Team Totals (Away Under)
**Classification: VOID / CONTAMINATED**

Same as E1. Same contamination chain. Suppressed in live code with
comment "52-54% in research, below threshold" — correct discipline but
the research numbers themselves are contaminated.

### E3. Team Totals (Away Over)
**Classification: CLEAN KILL**

Research showed 52-54% hit rate — below profitability threshold at standard
vig. Correctly suppressed. Even if data were clean, not profitable.

---

## F. Market Structure Research

### F1. Alt-Total Surface Mispricing
**Classification: WRONG MARKET FRAME**

82% directional consistency in curvature error. Books overestimate over
probability at distance +2 to +5. But hold widens at exactly those extremes
(5.9%->7.0-7.2%), absorbing the raw 4-7% edge. Only 1-2 of 7 books showed
positive ROI. Real statistical pattern, wrong betting expression.

### F2. Run-Line Comeback Asymmetry
**Classification: CLEAN KILL**

Walk-off truncation is real (8.9pp excess 1-run home wins) but perfectly
priced. Home/away -1.5 cover rates: 35.8% vs 35.9% across 9,857 games.
No pregame conditional bucket reaches significance. Clean null.

### F3. F5 vs Full-Game Path Mismatch
**Classification: RETEST REQUIRED**

Research in progress. 3,880 usable games (2024-2025). The late_implied
(full_game - f5_line) feature construction is clean (market data only).
Insufficient evidence to classify definitively. Continue research.

### F4. Cross-Market Triangle
**Classification: ARCHIVE**

Market data only. Informational research about market structure.
Not itself a bettable signal. Retain for reference.

---

## G. Over-Side Research

### G1. Over Scanner Wave 1
**Classification: RETEST REQUIRED**

Ten candidate signals scanned across 4,855 games. Top performers:
- OV043 (bullpen overuse): +8.1pp V1 interaction lift, but V1 interaction is contaminated
- OV016 (pitch count fatigue): +7.6pp V1 lift, same contamination concern
- OV001 (BB x hard-hit): +6.2pp V1 lift

Standalone results are weaker (OV016 +4.3%, others negative). The V1
interaction gate inflated these numbers (FM4). Standalone retesting with
clean data and real prices is required. The OVER SIDE of the market is
the least-explored territory with the most potential.

### G2. V2 Over Bias
**Classification: ARCHIVE**

V2 model has systematic +0.43 run over bias. This is a diagnostic finding,
not an actionable signal. The bias reveals that the V2 feature set captures
over-direction information but cannot beat the market spread.

---

## H. Distribution / Shape / Props

### H1. Distribution Shape Engine
**Classification: ARCHIVE**

Phase 1 complete: 174,870 starter-games classified into 8 archetypes.
Same-mean/different-shape test shows measurable archetype effects on hit
props (+5.2pp for POWER_STABLE at line=0.5). This is PROPS infrastructure,
not totals. Retain for props development.

### H2. NRFI Selector (Phases 1-5)
**Classification: WRONG MARKET FRAME**

Thorough 5-phase research. Best combined filter: NRFI=55.7%, ROI at -135 = -3.0%.
The NRFI market has structural vig of -135 (implied 57.4%) that absorbs the
available edge. No filter combination can overcome the hold. Selector V1
(F5 ascending) delivers 34.9% top-3 card hit rate but cannot be profitably
bet at market prices. Real directional signal, wrong market (vig too high).

### H3. MLB Props (K, TB, Hits)
**Classification: ARCHIVE**

Multiple model phases across strikeouts, total bases, and hits props.
These are separate from the totals market. Retain as independent research
track. Not classified as totals ideas.

---

## I. Signal Discovery Infrastructure

### I1. Canonical Signal Board
**Classification: ARCHIVE**

44 concepts catalogued. 12 upgrade candidates, 32 new signals. Infrastructure
for future research prioritization. Not itself a testable signal.

### I2. Engine 1-6 (Discovery Engines)
**Classification: ARCHIVE**

Pitcher state, bullpen network, archetype interaction, umpire zone, run
environment, cascade. Scanned for patterns. Some findings incorporated
into shadow signals (ADJ, CS series). The engines themselves are research
infrastructure, not signals.
