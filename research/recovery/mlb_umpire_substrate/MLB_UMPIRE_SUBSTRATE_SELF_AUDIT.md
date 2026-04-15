# MLB UMPIRE SUBSTRATE -- SELF-AUDIT
**Build ID:** MLB_UMPIRE_SUBSTRATE_v1
**Audit date:** 2026-04-15

---

## 13-QUESTION SELF-AUDIT

**Q1. Is game_pk the grain -- one row per game, no duplicates?**
PASS. Substrate rows: 9,902. game_pk unique: True. Duplicates: 0.

**Q2. Are all 9,902 game_table rows represented?**
PASS. substrate rows (9,902) == game_table rows (9,902). Zero rows dropped or added.

**Q3. Is the repair verdict confirmed -- no 2026 outcomes used in ratings?**
PASS. Repair registry (MLB_UMPIRE_RATINGS_2026_REPAIR) confirms:
- seasons_used: [2022, 2023, 2024, 2025]
- seasons_excluded: [2026]
- pit_safety.no_2026_data_in_ratings: true
- eligible_umpires: 92, ineligible_umpires: 19
- coverage_before (game): 50.8%, coverage_after (game): 97.2%

**Q4. Does Lance Barrett resolve correctly (was the primary bug)?**
PASS. Lance Barrett: 125 games in substrate, umpire_over_rate=1.0193, umpire_matched=True.
Repair added Lance Barrett to UMPIRE_RATINGS with runs_factor=1.0193 (122 qualifying games,
2022-2025). Prior bug: last-name fallback mapped Lance Barrett -> Ted Barrett (-2.5pp error).

**Q5. Does Alfonso Marquez (accented) resolve correctly?**
PASS. Alfonso Marquez (accented): 121 games in substrate, umpire_over_rate=1.0700,
umpire_matched=True. Repair added NFKD normalization to handle both accented and ASCII
spellings deterministically.

**Q6. Is Ted Barrett correctly on neutral fallback?**
PASS. Ted Barrett: 29 games in substrate, umpire_over_rate=1.0000, umpire_matched=False.
Below 30-game threshold => neutral. Prior bug: Lance Barrett fallback collision assigned
Ted Barrett's stale rf=0.975 to Lance Barrett games.

**Q7. Is umpire_over_rate correctly classified and scoped?**
PASS. Classification: APPROVED_UMPIRE_FEATURE. Scope: 2026 live model only. NOT PIT-safe
for 2022-2025 historical backtests (full 4-year outcome window baked into all ratings).

**Q8. Is umpire_k_rate correctly classified?**
PASS. Classification: CARRIED_ONLY_SUPPORT_FIELD. All 9,902 values are 0.000. Not
rebuildable from game_table alone (pitch-level ball/strike data required). Not promoted.

**Q9. Is overall coverage at or above 97%?**
PASS. 9,626 / 9,902 = 97.2% non-neutral. Neutral fallback: 276 games (19 umpires below
30-game threshold). Coverage improved from 50.8% (pre-repair) to 97.2% (post-repair).

**Q10. Are there zero nulls in the substrate?**
PASS. All 8 fields have null count = 0. umpire_id is int64 (0% null) from game_table.

**Q11. Is umpire_over_rate distribution reasonable?**
PASS. mean=1.000877 (near 1.000 as expected for a multiplicative factor), std=0.049,
min=0.900 (clamp floor), max=1.100 (clamp ceiling). Distribution is symmetric and
plausible for a run-scoring environment factor.

**Q12. Were only the 4 authorized files written?**
PASS. Files written:
  1. mlb_umpire_substrate.parquet
  2. MLB_UMPIRE_SUBSTRATE_REPORT.md
  3. MLB_UMPIRE_SUBSTRATE_REGISTRY.json
  4. MLB_UMPIRE_SUBSTRATE_SELF_AUDIT.md
No other files created. modules/umpires.py not modified. No commits. No pushes.
No background tasks used.

**Q13. Is the carry-forward scope warning explicit and unambiguous?**
PASS. Both REPORT and REGISTRY contain explicit statements that:
  (a) umpire_over_rate is 2026-frozen and approved for live 2026 use only.
  (b) Using this substrate for 2022-2025 backtests is a look-ahead violation.
  (c) Historical backtests require a separate PIT-safe rebuild.
  (d) umpire_k_rate is all zeros and must not be promoted.
  (e) 19 umpires remain on neutral fallback with full list documented.

---

## SUMMARY

All 13 questions PASS. Substrate is valid for 2026 live model deployment.

| Check | Result |
|---|---|
| Grain (1 row/game_pk, no dups) | PASS |
| All game_table rows present | PASS |
| Repair verdict confirmed (no 2026 in ratings) | PASS |
| Lance Barrett bug resolved | PASS |
| Alfonso Marquez unicode resolved | PASS |
| Ted Barrett correctly neutral | PASS |
| umpire_over_rate scope correct | PASS |
| umpire_k_rate correctly CARRIED_ONLY | PASS |
| Coverage >=97% | PASS |
| Zero nulls | PASS |
| Distribution plausible | PASS |
| Only 4 authorized files written | PASS |
| Carry-forward warnings explicit | PASS |

**OVERALL VERDICT: PASS -- substrate approved for 2026 live model use.**

---

*Audit completed: 2026-04-15*
