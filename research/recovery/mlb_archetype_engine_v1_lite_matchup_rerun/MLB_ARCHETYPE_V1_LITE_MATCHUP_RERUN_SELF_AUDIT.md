# MLB Archetype Engine V1-Lite Matchup Rerun — Self-Audit
**Build Date:** 2026-04-15
**Auditor:** automated self-check at write time

---

## The 15 Standard Questions

**Q1. Was the same-concept identity assessed before any computation?**
YES. Step 0 read the original registry. Step 1 mapped each original dimension to matchup base
fields before any rows were loaded or cuts computed. The CONCENTRATION dimension absence was
documented at that point. No computation ran until identity assessment was complete.

**Q2. Was 2026 data excluded from all analysis?**
YES. obj = mt[mt['season'].isin([2022, 2023, 2024, 2025])].copy() -- 2026 explicitly excluded.
374 rows removed (19,804 -> 19,430). The outcome label came from game_table which has scores
only through 2025 anyway.

**Q3. Were tercile cuts derived exclusively from the discovery split (2022-2023)?**
YES. patience_cuts, damage_cuts, k_cuts, bb_cuts all computed on disc_raw = obj[obj['season']
.isin([2022, 2023])]. These were then applied to all seasons (train/val/OOS) without
modification.

**Q4. Were the advancement thresholds set before discovery ran?**
YES. The frozen advancement standards were declared in the STEP 3 block before any stage
computation: discovery >=0.50, validation >=60%, OOS >=50%. These match the original V1-lite
spec and were not adjusted after seeing results.

**Q5. Was the outcome label a realized postgame field, not a predictor?**
YES. team_runs came exclusively from game_table (home_score/away_score), not from the matchup
base. The matchup base was built with realized scoring excluded by design.

**Q6. Was the main-effect control applied consistently across all three stages?**
YES. lineup_means and sp_means were computed once from the discovery period (2022-2023) and
applied unchanged to validation and OOS. The same grand_mean subtraction was used in all
three stages.

**Q7. Were small-cell results flagged?**
YES. Cell counts are reported in the stage tables. The smallest cells in discovery:
- IMPATIENT_POWER x CONTACT: n=50
- PATIENT_CONTACT x WILD_POWER: n=59
- PATIENT_CONTACT x CONTACT: n=55
All are above 50. No cell was excluded but small cells carry higher variance.

**Q8. Was the home/away symmetry verified?**
YES. Explicitly verified: 9,902 H / 9,902 A in the full matchup base. This was the primary
structural fix vs the original V1-lite (which had 26.7% home coverage due to asymmetric
hitter_game_logs).

**Q9. Were any post-hoc adjustments made after seeing stage results?**
NO. No thresholds, cuts, or archetype definitions were modified after results were computed.
The 9-cell stable set was identified descriptively after OOS ran but is not used to change
any verdict.

**Q10. Is the CONCENTRATION dimension absence properly documented?**
YES. It is flagged in: the same-concept identity assessment (Step 1), the registry JSON
(concentration_dimension_status), the report Section 2, the comparison table Section 7,
and this audit. The rerun is explicitly a 2-dim (not 3-dim) lineup model.

**Q11. Does the final verdict match the stage outcomes?**
YES.
- Discovery: max|resid|=0.719 >= 0.50 -> PASS
- Validation: 56.0% < 60% -> FAIL
- OOS: 48.0% < 50% -> FAIL
Verdict: NO-GO. The two-gate failure is clearly stated. No ambiguity.

**Q12. Are the output files restricted to the 4 authorized files?**
YES. Only these files were written to OUT_DIR:
1. MLB_ARCHETYPE_V1_LITE_MATCHUP_RERUN_REPORT.md
2. MLB_ARCHETYPE_V1_LITE_MATCHUP_RERUN_REGISTRY.json
3. MLB_ARCHETYPE_V1_LITE_MATCHUP_RERUN_STAGE_TABLES.csv
4. MLB_ARCHETYPE_V1_LITE_MATCHUP_RERUN_SELF_AUDIT.md (this file)
State was persisted to /tmp (not the project directory) during computation and not committed.

**Q13. Was the matchup base used as-is without modification?**
YES. No columns were added to or removed from the matchup base parquet. The merge of
game_table scores was done in-memory only. No writes to any source data file.

**Q14. Is the comparison to original V1-lite accurate and fair?**
YES. Original registry values used directly: discovery max|resid|=0.804, validation=40.0%,
verdict=NO-GO. The improvement from 40% to 56% is noted without overclaiming. The
concentration dimension absence is clearly stated as a reduction from the original.

**Q15. Is there any path to a GO decision from this analysis?**
NO. Two hard gates failed. Discovery residuals exist but the pattern is season-specific.
The 9 directionally-stable cells are a descriptive observation, not a GO signal. Any
reanalysis of those 9 cells would require a fresh research object with a pre-registered
hypothesis -- it cannot be back-applied to this analysis.

---

## Audit Verdict

All 15 questions answered. No violations found. Build is clean.
Final verdict NO-GO is supported by the evidence and correctly derived.

**Signed:** automated self-audit, 2026-04-15
