# MLB Archetype Engine V1-Lite — Final Branch Close Memo

**Closed:** 2026-04-15  
**Basis:** Clean matchup-base rerun on accepted substrate stack  
**Verdict:** NO-GO (definitive)

---

## 1. PURPOSE

This memo closes MLB Archetype Engine V1-lite definitively. Closure is based on the clean matchup-base rerun — the strongest and most controlled test the concept has received. This memo exists to prevent future drift or mistaken resurrection.

## 2. WHAT THE BRANCH TESTED

V1-lite tested whether rolling lineup identity interacting with opposing starter profile explained scoring behavior beyond broad team strength. In practice, this meant lineup BB% / ISO style identity crossed with opposing starter K% / BB% style profile, at rolling team-game (15-game) and starter (5-start) granularity.

## 3. WHY THE ORIGINAL RUN WAS NOT ENOUGH

The original run ended NO-GO with 40% validation directional consistency. But its analytical path was not reliable:

- The earlier home/away coverage diagnosis was wrong (claimed source flag imbalance; actual cause was a `pitcher_id` vs `player_id` column-name bug that nullified all starter-profile features)
- The original run's validation failure was a false negative driven by corrupted features, not an absent signal
- Therefore the original run alone was not sufficient as the closure basis

## 4. WHAT THE SOURCE-FIX RERUN ESTABLISHED

A same-object rerun corrected the column-name bug while preserving object identity:

- Discovery signal strengthened (max residual 0.804 → 1.158)
- Validation improved from 40% to 66.7% (now passing)
- OOS failed at 43.8% — below chance
- The concept did not revive once the feature defect was fixed
- Verdict: NO-GO, but now on corrected evidence

## 5. WHAT THE CLEAN MATCHUP RERUN ESTABLISHED

A final rerun used the accepted matchup base built from the full repaired substrate stack:

- Symmetric home/away coverage (50/50 — the original asymmetry is gone)
- Correct team-code normalization across all substrates
- PIT-safe rolling features from accepted lineup-state and rolling-starter-profile substrates
- 2022-2023 discovery, 2024 validation, 2025 OOS. 2026 excluded entirely.
- Same concept mediated through the matchup base (concentration dimension dropped — no Gini field available, but the core 2-lineup × 2-SP interaction preserved)

Results:

| Run | Discovery Max Residual | Validation Consistency | OOS Consistency | Verdict |
|-----|----------------------|----------------------|-----------------|---------|
| Original (broken) | 0.804 | 40.0% | not reached | NO-GO |
| Source-fix rerun | 1.158 | 66.7% | 43.8% | NO-GO |
| **Clean matchup rerun** | **0.719** | **56.0%** | **48.0%** | **NO-GO** |

Even with fully corrected infrastructure, the concept fails validation (56% < 60% threshold) and OOS is below chance (48%). The interaction patterns found in discovery do not persist.

## 6. FINAL BRANCH CONCLUSION

The branch is closed. It is closed on corrected evidence, not broken evidence. The concept — BB%/ISO lineup archetypes × K%/BB% starter profiles at rolling team/pitcher granularity — does not produce stable interaction effects across seasons. This is not an "almost worked" branch. OOS consistency below 50% means the discovered patterns are anti-predictive on held-out data, not merely null. Minor tweaks (different windows, different thresholds, adding concentration back) are not justified as continuation of the same branch.

## 7. WHAT SHOULD BE CARRIED FORWARD

- **Same-object reruns matter.** The original run's false negative would have led to incorrect closure reasoning without the correction chain.
- **Source/column bugs create false narratives.** The home/away diagnosis was wrong. The real defect was a column-name mismatch. Always verify root cause from source code.
- **Corrected infrastructure still did not save the concept.** Fixing the data didn't fix the idea.
- **Research standards are durable.** PIT-safe substrate stack, frozen splits, frozen windows, frozen advancement criteria — the protocol worked correctly even though the concept failed.
- **The matchup base is validated as infrastructure.** V1-lite's failure confirms the base layer works correctly — it simply showed that this particular concept has no signal.

## 8. WHAT SHOULD NOT BE CARRIED FORWARD

- Do not treat the original home/away diagnosis as true — it was wrong
- Do not treat the original NO-GO as the final closure basis — the clean rerun is authoritative
- Do not treat this branch as unresolved or "needs one more fix"
- Do not casually reopen with minor tweaks (different window, different threshold) and call it the same object
- Do not cite this branch as evidence that archetypes "almost worked" — OOS was below chance

## 9. STATUS

MLB Archetype Engine V1-lite is CLOSED. Closure is based on the clean matchup-base rerun, which remained NO-GO on corrected infrastructure. No live or shadow object behavior has been changed.

The clean matchup rerun is analytically usable. Any future archetype work must be treated as a new branch, not a continuation of V1-lite.
