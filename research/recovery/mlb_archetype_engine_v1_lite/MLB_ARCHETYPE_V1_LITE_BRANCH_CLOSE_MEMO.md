# MLB Archetype Engine V1-Lite — Branch Close Memo

**Closed:** 2026-04-14  
**Basis:** Corrected same-object rerun  
**Verdict:** NO-GO

---

## 1. PURPOSE

This memo closes MLB Archetype Engine V1-lite. Closure is based on the corrected same-object rerun, not the flawed original run. This memo exists to prevent future drift, mistaken resurrection, or treatment of this branch as unresolved.

## 2. WHAT THE BRANCH TESTED

V1-lite tested whether rolling lineup identity (patience + damage dependence) interacting with opposing starter profile (bat-miss ability + command stability) explained scoring behavior beyond what broad team offensive strength alone predicts. It used 15-game rolling windows, PIT-safe shift(1) construction, and a 2022-23 / 2024 / 2025 discovery / validation / OOS split.

## 3. WHAT WENT WRONG IN THE ORIGINAL RUN

The original run ended NO-GO with 40% validation directional consistency. However, the original analytical path was not fully reliable:

- The original run reported a home/away coverage asymmetry (26.7% home vs 98.2% away) and attributed it to a raw source `home_away` flag imbalance
- That diagnosis was wrong. The raw source was already balanced (102K home / 102K away)
- The real defect was a `pitcher_id` vs `player_id` column name bug in the pipeline script that nullified all starter-profile rolling features
- With null SP features, the `dropna` filter dropped most rows asymmetrically, creating the apparent home/away coverage gap
- The original NO-GO was a false negative caused by corrupted features, not an absent signal

## 4. WHAT THE CORRECTED RERUN ESTABLISHED

A same-object rerun was executed with only the column name bug corrected. The post-run compliance audit confirmed:

- **Same-object identity preserved:** Identical dimensions, windows, thresholds, splits, sources, labels
- **Coverage balanced:** 98.4% home, 98.4% away (symmetric)
- **Discovery:** PASS — max residual 1.158 runs (stronger than original's 0.804)
- **Validation:** PASS — 66.7% directional consistency (vs original's 40% false fail)
- **OOS:** FAIL — 43.8% directional consistency, below chance (50%)

The corrected rerun also revealed that the original run's validation failure was a false negative. With clean data, the signal passes validation but fails the true holdout test.

**Process violations:** The rerun spawned unauthorized background polling tasks and created an unauthorized `_rerun_results.pkl` file. The post-run compliance audit classified these as process non-pristine but analytically non-material — they did not affect outputs or the research conclusion.

## 5. FINAL BRANCH CONCLUSION

The branch is closed. It is closed on corrected evidence, not flawed evidence. The lineup archetype × starter profile interaction concept at this granularity (BB%, ISO, K%, BB% with 15-game rolling windows) does not survive the full forward validation chain. Discovery signal exists. Validation signal exists. OOS signal does not — 43.8% directional consistency is below random chance. This is not an "almost worked" branch.

## 6. WHAT SHOULD BE CARRIED FORWARD

- **Process lesson:** Corrected reruns must preserve same-object identity. The rerun correctly did this.
- **Diagnosis lesson:** Source/column/path bugs can create false narratives. The original home/away diagnosis was wrong. Always verify root cause from source code, not just from symptom-level statistics.
- **Validation lesson:** Validation pass alone is not enough. OOS failure closed this branch — the concept showed in-sample and near-sample signal but failed true holdout.
- **Substrate lesson:** Team-level BB% and ISO at 15-game rolling granularity may be too noisy for stable archetype labels. A fundamentally different construction (longer windows, Statcast-level features, per-matchup rather than per-team identity) would be required for any future attempt — and would constitute a new branch.

## 7. WHAT SHOULD NOT BE CARRIED FORWARD

- Do not treat the original home/away diagnosis as true — it was wrong
- Do not treat the original NO-GO as the reason for closure — the corrected rerun is the authoritative result
- Do not treat this branch as unresolved or "needs one more fix"
- Do not casually reopen it with minor tweaks (different window, different threshold) and call it the same object — any redesign is a new branch requiring full revalidation
- Do not cite this branch as evidence that archetypes "almost worked" — OOS consistency was below chance

## 8. STATUS

MLB Archetype Engine V1-lite is CLOSED. Closure is based on the corrected same-object rerun, which remained NO-GO after failing OOS. No live or shadow object behavior has been changed.

Process was non-pristine but analytically non-material. Any future archetype work must be treated as a new branch, not a continuation of this one.
