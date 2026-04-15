# MLB UMPIRE HISTORICAL LAYER — SELF-AUDIT

**Build timestamp:** 2026-04-15T18:39:53Z  
**Auditor:** Automated build script (deterministic, reproducible)

---

## Q1. Does any season's rating use data from that season or later?

**NO.** The filter `completed[completed['season'] < target_season]` is applied strictly
before any statistic is computed. For target_season=2022, the prior pool is empty and all
ratings are NULL. For 2023, only 2022 games are included. Verified by inspecting
`prior_seasons_used` field: values are exactly `""`, `"2022"`, `"2022,2023"`,
`"2022,2023,2024"`, `"2022,2023,2024,2025"` respectively.

---

## Q2. Was actual_total from game_table the sole outcome field used?

**YES.** Only `game_table['actual_total']` was used for both the per-umpire mean and the
league mean. No other outcome field (home_score, away_score, actual_f5_total, etc.) was
accessed in the rating computation.

---

## Q3. Are there any NULL rows for actual_total in the source?

**NO.** Source audit confirmed `actual_total` null count = 0 across all 9,902 rows.

---

## Q4. Was the minimum sample threshold (30 games) applied before rating assignment?

**YES.** Any umpire with fewer than 30 prior-season completed games receives
`has_prior_rating = False` and `prior_season_umpire_over_rate = NULL`. No exception
was made. Lance Barrett (29 prior games entering 2023) and Alfonso Márquez (27 prior
games entering 2023) both correctly received NULL for season 2023.

---

## Q5. Are there duplicate (season, umpire) rows?

**NO.** `layer.duplicated(['season', 'umpire_name_normalized']).sum() == 0`. Each
umpire appears at most once per target season.

---

## Q6. Was umpire_k_rate computed or included?

**NO.** `umpire_k_rate` was explicitly excluded. It is not rebuildable from
`game_table.parquet` and was not approximated or imputed.

---

## Q7. Does the formula match the declared spec?

**YES.** `runs_factor = umpire_avg_total_prior / league_avg_total_prior`, clamped
[0.900, 1.100]. This matches the PRE-DECLARED RULE: `runs_factor = umpire_avg_total / league_avg_total (from same prior-season pool)`.

---

## Q8. Is unicode normalization consistent with the 2026 forward-use repair?

**YES.** Both layers use `unicodedata.normalize('NFKD', name)` followed by
combining-character stripping and whitespace collapsing. `Alfonso Márquez` normalizes
to `Alfonso Marquez` in both layers — confirmed by spot check showing the same game
counts across both.

---

## Q9. Is 2022 handled correctly (all NULL, no fallback invented)?

**YES.** For target_season=2022, `len(prior) == 0` branches and all 96 umpires
receive `prior_season_umpire_over_rate = NULL`, `has_prior_rating = False`,
`prior_seasons_used = ""`, `league_avg_total_prior = NULL`. No neutral value (1.000)
was silently assigned; the NULL is explicit for downstream models to handle.

---

## Q10. Are the clamp bounds [0.900, 1.100] symmetric and pre-declared?

**YES.** Bounds were declared in the build spec before computation began. 31 rows
reached a clamp boundary. The mean rated runs_factor = 1.001 (near-neutral), std = 0.056,
confirming the distribution is sensible and not dominated by outliers.

---

## Q11. Are there any umpires in the 2026 target set not covered by prior ratings?

**3 umpires** in the 2026 target set have `has_prior_rating = False` due to
insufficient prior games (<30). None have zero prior games (not_in_prior=0 for 2026).
Coverage is 96.3% — the highest of any season, as expected with 4 years of prior data.

---

## Q12. Does league_avg_total_prior vary by season as expected?

**YES.** Values are:
- 2022: NULL (no prior)
- 2023: 8.567 (from 2022 only — 2430 games)
- 2024: 8.899 (from 2022+2023 — 4860 games)
- 2025: 8.862 (from 2022+2023+2024 — 7287 games)
- 2026: 8.870 (from 2022+2023+2024+2025 — 9715 games)

The mild increase from 2022 to 2024 and stabilization afterward is consistent with
known MLB run-environment trends. Values are plausible.

---

## Q13. Were any files other than the 4 authorized outputs created?

**NO.** Only these files were written to disk in `research/recovery/mlb_umpire_historical_layer/`:
1. `mlb_umpire_prior_season_ratings.parquet`
2. `MLB_UMPIRE_HISTORICAL_LAYER_REPORT.md`
3. `MLB_UMPIRE_HISTORICAL_LAYER_REGISTRY.json`
4. `MLB_UMPIRE_HISTORICAL_LAYER_SELF_AUDIT.md`

No other files were created. `modules/umpires.py` was not modified.

---

## Q14. Is this layer safe to use as a training feature for seasons 2023–2026?

**YES, with caveats:**

- **2022:** Not usable as a rated feature. Must use neutral (1.000) or drop.
- **2023:** 36.2% coverage. The 60 NULL umpires should be handled with a neutral
  fallback in model code, not dropped. The low coverage is structurally unavoidable
  given only 1 prior season of data.
- **2024–2026:** Coverage 83–96%; safe for direct feature use. The `has_prior_rating`
  boolean flag provides a clean mask for downstream imputation logic.
- **General:** No PIT contamination detected. The layer is cleared for use as a
  lagged feature in any ML pipeline that respects the season boundary.

---

**SELF-AUDIT VERDICT: ALL 14 QUESTIONS PASS**
