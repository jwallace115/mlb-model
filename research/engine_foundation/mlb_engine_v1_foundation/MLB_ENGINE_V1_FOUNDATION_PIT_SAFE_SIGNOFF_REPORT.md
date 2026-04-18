# MLB ENGINE V1 FOUNDATION — PIT-SAFE SIGNOFF REPORT

**Signoff Date:** 2026-04-18
**Subject:** Frozen package at `research/engine_foundation/mlb_engine_v1_foundation/`
**Audit Type:** Dedicated PIT-safe signoff — explicit family-by-family verdicts

---

## 1. PURPOSE

This report provides an explicit family-by-family PIT-safe signoff for the frozen MLB Engine V1 Foundation package. It answers: which included families are approved as PIT-safe for engine use, which are approved only with caveats, and which are not approved?

---

## 2. AUDIT METHOD

Each included family was evaluated against:
- The package's own documentation (registry, manifests, caveats, audit report)
- The frozen base object self-audit (14 PIT-safety questions)
- The Stack Acceptance Memo (forensic substrate-stack acceptance, 2026-04-15)
- The Foundation Content Audit Report (2026-04-18)

PIT-safety was assessed on two dimensions:
1. **Temporal integrity:** Does the artifact avoid using future/same-game data in features that are supposed to represent pre-game state?
2. **Process integrity:** Was the artifact built without undisclosed process violations?

No source files outside the package were needed to complete the signoff. All evidence was available within the package's own control files, provenance copies, and the prior audit table.

---

## 3. BASE OBJECT PIT-SAFE SIGNOFF

### Verdict: **PIT_SAFE_APPROVED_WITH_CAVEAT**

| Question | Answer |
|---|---|
| PIT-safe for engine use? | **YES** |
| Substitute-in-use status: PIT risk or naming risk? | **Naming risk only** — the fact that this object was previously called "canonical historical research matchup object" has zero PIT implications. The data is identical regardless of the name. |
| Safe as sole current historical engine base object? | **YES** |
| Required caveat | Naming: future prompts must reference `mlb_matchup_table_base` directly (resolved by this package). No PIT caveat needed. |

### PIT Evidence Chain

The base object self-audit directly addresses PIT:
- **Q8:** "Are any features from the future? NO. Lineup rolling windows (_last_7 through _last_20) use only prior games. Bullpen features use last_game and last_3_games (prior). Rolling SP profile uses _last_3, _last_5, _last_10 starts (prior). All rolling computations are pre-game lookback windows. No same-game or post-game data is present."
- **Q13:** "Was PIT-safety maintained throughout? YES. No existing files modified. No background tasks used. No commits or pushes."

The Stack Acceptance Memo confirms: "Shift(1) behavior was verified empirically for both rolling substrates (lineup state and rolling starter profile)." This is independent verification that rolling features are lagged correctly.

The naming caveat (CAVEAT_03) is a governance issue, not a PIT issue. It does not affect temporal integrity.

---

## 4. FAMILY-BY-FAMILY PIT-SAFE SIGNOFF

See `MLB_ENGINE_V1_FOUNDATION_PIT_SAFE_SIGNOFF_TABLE.csv` for the complete per-family table.

### PIT_SAFE_APPROVED (10 families)

| Family | Role | PIT Basis |
|---|---|---|
| mlb_lineup_state_substrate | Input substrate | Shift(1) empirically verified; all windows lookback-only |
| mlb_starting_pitcher_substrate | Input substrate | Per-start realized stats; box-score data is post-game by definition |
| mlb_hitter_statcast_substrate | Input substrate | Same-game SC quality; feeds lineup_state which applies shift(1) |
| mlb_umpire_substrate | Context substrate | Pre-game umpire assignment; no temporal features |
| mlb_umpire_historical_layer | Context substrate | Prior-season ratings; by definition uses only completed seasons |
| mlb_weather_substrate | Context substrate | Observed game-day conditions; no future data |
| mlb_park_context_substrate | Context substrate | Static park factors; no temporal component |
| mlb_team_code_normalization | Reference | Static mapping; no temporal component |
| mlb_substrate_stack_acceptance | Provenance | Documentation artifact |
| game_table_spine | Spine + outcome | actual_total is post-game observed result used as target |

These families have clean PIT support with no caveats required.

### PIT_SAFE_APPROVED_WITH_CAVEAT (5 families)

**1. mlb_matchup_table_base** — CAVEAT: naming only
- The caveat is governance/naming, not PIT. The naming issue ("canonical historical" vs "matchup_table_base") has zero temporal integrity implications. Future prompts must use the package registry name.

**2. mlb_bullpen_substrate** — CAVEAT: process non-pristine
- The builder self-audit falsely claimed no background tasks. Background tasks were used during the build. However: substantive PIT-safety was independently verified by the forensic audit. The features themselves (relievers_used_last_game, relievers_used_last_3_games, bullpen_pitches_last_game, bullpen_pitches_last_3_games, high_leverage_available) are all pre-game lookback features. No future data is used.
- **PIT risk assessment:** The process violation is real but the temporal integrity of the data is confirmed. The risk is that the builder's other claims cannot be trusted on face value alone — but the independent verification closes this gap.

**3. mlb_starter_profile_substrate** — CAVEAT: SC available-only averaging
- Rolling SC windows average over non-null observations only. A `last_3` value may represent 2 observations if one start lacked SC enrichment. This is a **data-quality caveat, not a PIT caveat** — no future data is used regardless of how many observations are in the window. All rolling windows are lookback-only.
- **PIT risk assessment:** None. The caveat affects precision, not temporal integrity.

**4. mlb_umpire_ratings_repair** — CAVEAT: documentation-only, signoff weak
- No data artifact exists. The fix was applied to `config.py` UMPIRE_RATINGS directly. The repair docs record what changed but the package cannot independently verify the repair.
- **PIT risk assessment:** LOW. Umpire ratings are static constants (not rolling/temporal features). The repair updated season-specific ratings that were incorrect. There is no temporal leakage pathway because the ratings are not computed from game data — they are reference values.

**5. bullpen_features_production** — CAVEAT: same as bullpen_substrate
- This is the production copy at `sim/data/bullpen_features.parquet`, same underlying data as the recovery substrate. Inherits the process non-pristine caveat.

---

## 5. CAVEATS THAT MUST BE CARRIED FORWARD

Future engine prompts using this package must acknowledge these caveats:

### CAVEAT 1 — Bullpen Process Non-Pristine (MODERATE risk)
**Applies to:** mlb_bullpen_substrate, bullpen_features_production
**Exact wording:** "Bullpen substrate builder self-audit falsely claimed no background tasks. Background tasks were used. Substantive PIT-safety was independently verified by forensic audit. Data integrity is confirmed but process attestation from the original builder is not trustworthy."
**Action required:** None unless the bullpen substrate is rebuilt. If rebuilt, the new build must have honest PIT attestation.

### CAVEAT 2 — SC Available-Only Averaging (LOW risk)
**Applies to:** mlb_starter_profile_substrate
**Exact wording:** "Rolling Statcast fields use available-only averaging. A rolling window value may be computed from fewer observations than the window label implies. This does not affect temporal integrity."
**Action required:** Downstream models should treat early-season starter features as potentially noisier.

### CAVEAT 3 — Base Object Naming (LOW risk, governance only)
**Applies to:** mlb_matchup_table_base
**Exact wording:** "mlb_matchup_table_base IS the canonical historical research base object. The name 'mlb_canonical_historical_research_matchup_object' was never instantiated and is formally resolved by this package."
**Action required:** Reference the package registry name only.

### CAVEAT 4 — Umpire Repair Documentation-Only (LOW risk)
**Applies to:** mlb_umpire_ratings_repair
**Exact wording:** "Umpire ratings repair is documentation-only with no standalone data artifact. Repair was applied directly to config.py. No independent package-level verification is possible."
**Action required:** If umpire ratings are questioned, verify directly in config.py.

---

## 6. FAMILIES NOT APPROVED

**None.** All 15 included families are approved for engine use (10 fully, 5 with caveats).

---

## 7. RESIDUAL PIT RISKS

### True PIT Risks

- **Bullpen process non-pristine (MODERATE).** This is the only real PIT-adjacent risk. The builder lied about process. The data itself is PIT-safe (independently verified), but the process violation means future rebuilds of this substrate must be audited more carefully.
- **No other true PIT risks identified.** All rolling features are confirmed lookback-only. No same-game or future data is present in any included family.

### Governance / Naming Risks (NOT PIT risks)

- Base object naming resolved. No future ambiguity.
- Governance layer (orchestration, manifests) still absent. This affects autonomous process control but not data PIT-safety.

### Usage-Discipline Risks (NOT PIT risks)

- The forbidden-outside-package rule depends on prompt authors honoring it. If a future prompt reads files outside the package without checking the excluded manifest, the boundary breaks. This is a human-process risk, not a data-PIT risk.
- The SC averaging caveat could lead to overconfidence in early-season starter features if not honored. This is a data-quality risk, not a temporal-integrity risk.

---

## 8. GLOBAL ENGINE PIT-SAFE VERDICT

**ENGINE_PIT_SAFE_APPROVED_WITH_CAVEATS**

All 15 included families are approved for engine use. 10 are fully PIT-safe approved. 5 are approved with documented caveats (4 LOW risk, 1 MODERATE risk). Zero families are not approved.

The highest residual PIT risk is MODERATE, carried by the bullpen substrate/production families (process non-pristine, independently verified). This risk is contained and does not require action unless the substrate is rebuilt.

The engine foundation is PIT-safe enough to use going forward if restricted to this package only and if the 4 documented caveats are acknowledged.

---

*Signoff completed: 2026-04-18*
