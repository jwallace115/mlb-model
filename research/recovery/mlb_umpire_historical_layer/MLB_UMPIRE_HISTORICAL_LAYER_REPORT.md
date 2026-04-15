# MLB UMPIRE HISTORICAL PRIOR-SEASON RATINGS LAYER — BUILD REPORT

**Build timestamp:** 2026-04-15T 2026-04-15T18:39:53Z  
**Source file:** sim/data/game_table.parquet  
**Output file:** mlb_umpire_prior_season_ratings.parquet  
**Total rows:** 453 (season × umpire combinations)  
**Duplicates on (season, umpire_name_normalized):** 0

---

## PURPOSE

Provide PIT-safe, prior-season umpire ratings for each target season (2022–2026).
Each row represents the rating a downstream model MAY use for season Y, computed
exclusively from completed games played before season Y. No future information
enters any season's ratings.

---

## PIT-SAFE SEASON RULE

| Target Season | Prior Seasons Used | Notes |
|---|---|---|
| 2022 | None | No pre-2022 data in repo — all ratings NULL |
| 2023 | 2022 | Single year; 36.2% coverage due to thin sample per umpire |
| 2024 | 2022, 2023 | Coverage jumps to 83.3% with 2 years of prior data |
| 2025 | 2022, 2023, 2024 | 89.1% coverage |
| 2026 | 2022, 2023, 2024, 2025 | 96.3% coverage — near-complete |

The boundary is strict: season Y uses only completed games where `season < Y`.
There is zero leakage.

---

## SOURCE & IDENTITY

- **Source table:** `sim/data/game_table.parquet`
- **Outcome field:** `actual_total` (postgame realized total runs; 0 nulls in source)
- **Umpire identity:** `umpire_name` + `umpire_id`; normalized via `unicodedata.normalize('NFKD')`
  with combining-char stripping and whitespace normalization
- **Total rows in source:** 9,902 completed games (2022–2026 partial)
- **Distinct umpires:** 111

**Normalization example — diacritic repair:**
- `Alfonso Márquez` (accented) → `Alfonso Marquez` (normalized)
- Matching is deterministic and consistent with the 2026 forward-use repair layer

---

## FIELD DISPOSITION

| Field | Status | Notes |
|---|---|---|
| prior_season_umpire_over_rate | APPROVED | runs_factor = umpire_avg_total / league_avg_total from prior seasons; clamped [0.900, 1.100] |
| prior_season_games | APPROVED | Count of prior-season completed games for this umpire |
| prior_seasons_used | APPROVED | Comma-separated list of seasons contributing to this rating |
| league_avg_total_prior | APPROVED | League-wide mean actual_total from prior seasons pool |
| umpire_avg_total_prior | APPROVED | This umpire's mean actual_total from prior seasons pool |
| has_prior_rating | APPROVED | Boolean gate; False when NULL (no data, not-in-prior, or insufficient sample) |
| umpire_name_normalized | APPROVED | Unicode-stripped identity key for deterministic matching |
| umpire_k_rate | EXCLUDED | Not rebuildable from approved inputs (game_table.parquet does not carry K-rate) |

---

## FORMULA

```
runs_factor = umpire_avg_total_prior / league_avg_total_prior
runs_factor = clamp(runs_factor, 0.900, 1.100)
```

- `league_avg_total_prior` is computed from ALL completed games in prior seasons (not just
  this umpire's games), providing a stable denominator.
- Minimum sample threshold: **30 prior-season games**. Below this, `has_prior_rating = False`
  and `prior_season_umpire_over_rate = NULL`.
- Clamp bounds are symmetric ±10% around neutral. 31 rated rows reached a clamp boundary,
  all from earlier seasons with thinner data.

---

## COVERAGE BY SEASON

| Season | Rated | Total | Coverage | Null/Insufficient | Reason for Null |
|---|---|---|---|---|---|
| 2022 | 0 | 96 | 0.0% | 96 | No prior data in repo |
| 2023 | 34 | 94 | 36.2% | 60 | 53 insufficient (<30 games in 2022 only), 7 not in 2022 |
| 2024 | 75 | 90 | 83.3% | 15 | 12 insufficient, 3 not in prior seasons |
| 2025 | 82 | 92 | 89.1% | 10 | 5 insufficient, 5 not in prior seasons |
| 2026 | 78 | 81 | 96.3% | 3 | 3 insufficient, 0 not in prior seasons |
| **Total** | **269** | **453** | **59.4%** | **184** | (2022 structurally all-null) |

**Note on 2023:** Low 36.2% coverage is structurally expected. With only one year (2022)
of prior data, most umpires have fewer than 30 games (typical workload ~70 games/season,
but they are split across umpires). This is PIT-safe — the thin coverage is the honest
picture of what was knowable before 2023.

---

## REPRESENTATIVE UMPIRES — SPOT CHECK

| Umpire | Season | runs_factor | Prior Games | Has Rating |
|---|---|---|---|---|
| Lance Barrett | 2022 | NULL | 0 | False |
| Lance Barrett | 2023 | NULL | 29 | False (just below 30) |
| Lance Barrett | 2024 | 0.9889 | 60 | True |
| Lance Barrett | 2025 | 1.0231 | 91 | True |
| Lance Barrett | 2026 | 1.0193 | 122 | True |
| Alfonso Márquez | 2022 | NULL | 0 | False |
| Alfonso Márquez | 2023 | NULL | 27 | False (just below 30) |
| Alfonso Márquez | 2024 | 1.0655 | 56 | True |
| Alfonso Márquez | 2025 | 1.0558 | 87 | True |
| Alfonso Márquez | 2026 | 1.0700 | 118 | True (clamped) |

---

## PIT-SAFETY VERDICT

**PASS — No future data contamination present.**

Evidence:
1. Season rule enforced strictly: `prior = completed[completed['season'] < target_season]`
2. 2022 is structurally all-NULL (no pre-2022 data available)
3. Each season's `league_avg_total_prior` and `umpire_avg_total_prior` draw only from prior rows
4. Minimum sample threshold (30 games) applied before assigning any rating
5. No imputation of missing values from future seasons
6. Zero duplicate rows on (season, umpire_name_normalized)

---

## CARRY-FORWARD NOTES

1. Each season uses ONLY prior seasons' data — the strict `season < Y` boundary must be
   preserved in any downstream training pipeline.
2. 2022 is structurally NULL for all umpires. Models trained on 2022 should either drop
   umpire features for that season or use a neutral value (1.000).
3. League baselines differ by season (8.567 in 2023, 8.899/8.862/8.870 in 2024-2026) and
   are not directly poolable across years — use per-season `league_avg_total_prior`.
4. This layer is distinct from the 2026-frozen forward-use umpire repair layer. The two
   layers serve different purposes and must not be merged.
5. `umpire_k_rate` was intentionally excluded — it is not rebuildable from `game_table.parquet`
   inputs and cannot be validated without an additional approved source.
6. 2023 ratings are based on 1 year of prior data (2022 only) — thin but PIT-safe. Downstream
   models should apply additional regularization or weight 2023 umpire features accordingly.
7. Clamp bounds [0.900, 1.100] were applied to 31 rated rows. These bounds prevent extreme
   outliers from early thin-sample seasons from distorting model coefficients.
8. Unicode normalization (NFKD + combining-char strip) resolves diacritic variants. The
   `umpire_name` field retains the original spelling from game_table; `umpire_name_normalized`
   is the canonical match key.
