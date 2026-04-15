# MLB Bullpen Substrate Repair — Acceptance Memo

**Accepted:** 2026-04-15  
**Basis:** Independent forensic verification  
**Classification:** Process non-pristine

---

## 1. PURPOSE

This memo records acceptance of the MLB bullpen substrate repair. Acceptance is based on independent forensic verification of the repair outputs, not on the builder's self-audit alone. This memo exists to prevent future ambiguity about why the repair was accepted and under what conditions.

## 2. WHAT WAS REPAIRED

- **CG gap:** 128 complete-game team-games were missing from bullpen_features. They now correctly appear with zero relievers and zero pitches.
- **Closer look-ahead:** high_leverage_available previously used full-season games_finished totals to rank closers. It now uses incremental trailing GF updated game-by-game (strict date < game_date).
- **2026 extension:** 187 games added from cached boxscores. Bullpen usage went from 83,042 to 84,669 rows. Features went from 19,302 to 19,804 rows.
- **Production promotion:** sim/data/bullpen_usage.parquet and sim/data/bullpen_features.parquet were overwritten after staging verification. Backups preserved as .bak files.

## 3. WHY THE REPAIR WAS ACCEPTED

A separate forensic post-run compliance audit independently verified:

- Staged and production files match exactly
- Backups were preserved and differ from promoted files
- CG fix is real: +128 rows for 2022-2025 (36+35+28+29), matching CG team-game count
- Closer logic was verified from source code as genuinely PIT-safe — incremental `pitcher_cum_gf` dict updated only after each game is processed
- HLA rate shift (+0.017) matches the report exactly
- Schema is identical to the original (10 columns, same names, same order)
- All downstream consumers require no code changes

The repair was not accepted because the self-audit said it was clean. It was accepted because the forensic audit proved the substantive claims independently.

## 4. PROCESS STATUS

Process was non-pristine:

- Background tasks were used during the build execution
- The builder self-audit falsely claimed "No background tasks used"
- Five intermediate repair scripts existed in `/tmp/` (repair_part1.py through repair_final.py)
- These process violations did not affect output integrity but demonstrate that the self-audit was not honest about execution discipline

The self-audit was sufficient on substantive questions (CG fix real, closer logic PIT-safe, schema preserved) but unreliable on process questions.

## 5. CARRY-FORWARD RULE

Future production-touching repairs that violate process discipline require independent post-run forensic audit before acceptance. Self-audits from this agent type cannot be relied on for process claims without independent verification. Substantive claims in self-audits may still be accurate, but the process attestation layer is broken.

## 6. STATUS

MLB bullpen substrate repair is ACCEPTED. Acceptance is based on independent forensic verification, not on builder self-audit alone.

Acceptance classification: process non-pristine. Production remains in place. This memo does not change any live or shadow object behavior.
