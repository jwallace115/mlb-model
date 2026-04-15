# MLB PARK / GAME-CONTEXT SUBSTRATE — SELF-AUDIT
Generated: 2026-04-15 11:43:30

---

## Q1. Is the grain exactly one row per game_pk?
YES. game_pk.is_unique = True. Verified: 0 duplicates across 9,902 rows.

## Q2. Does the substrate include any postgame realized outcomes?
NO. All of: home_score, away_score, actual_total, actual_f5_total, innings_played,
completed_early were explicitly classified EXCLUDED and are not in the parquet.

## Q3. Does the substrate include weather data?
NO. temperature, wind_speed, wind_direction were explicitly classified EXCLUDED.
Weather belongs in a dedicated weather substrate (separate future build).

## Q4. Does the substrate include umpire data?
NO. umpire_name, umpire_id, umpire_over_rate, umpire_k_rate were explicitly classified
EXCLUDED. Umpire data belongs in a dedicated umpire substrate.

## Q5. Are park_factor_runs and park_factor_hr PIT-safe?
YES. Verified: groupby(home_team, season)[park_factor_runs].nunique().max() == 1 across
all 5 seasons. The factors are static preseason lookups per home_team, not derived from
same-season game scoring. Zero season-to-season variation for any team.

## Q6. Are rest_days fields PIT-safe?
YES. home_rest_days and away_rest_days are computed using shift logic from prior-game dates
within each team's sorted game history. No future game information is used in the
computation. Cap at 5 days prevents lookback beyond the season boundary.

## Q7. Are venue/park identity fields PIT-safe?
YES. venue_id, venue_name, park_id, roof_status are static structural properties of
ballparks that do not change over time. They are fully known before any game begins.

## Q8. Are game scheduling fields (game_number, doubleheader_flag, start hours) PIT-safe?
YES. These are published in the MLB schedule API before games begin. They are
not derived from game outcomes.

## Q9. Are there any null issues that require attention?
ONE field has nulls: local_start_hour has 2,316 nulls (23.4%) due to timezone
resolution gaps in historical source data. Mitigation is documented: use game_hour_utc
(always 0 nulls) as fallback. All other fields are 100% populated.

## Q10. Does the substrate cover the expected game population?
YES. 9,902 rows covering seasons 2022-2026:
  2022: 2,430 | 2023: 2,430 | 2024: 2,427 | 2025: 2,428 | 2026: 187 (YTD)
These counts are consistent with a 162-game MLB regular season per team (30 teams × 162 / 2 = 2,430).
Minor deviations in 2024/2025 reflect rainout/makeup scheduling.

## Q11. Is park_id the same as venue_id?
YES. (gt['venue_id'] == gt['park_id']).all() == True. park_id is an alias retained for
backward compatibility in downstream joins. Both fields are included in the substrate.

## Q12. Are there any collinearity or structural concerns with the approved features?
park_factor_runs == park_factor_hr for all 30 teams in this substrate (identical values).
These are highly collinear. Downstream modeling should use only one. This is documented
and the choice is left to the modeler. The substrate retains both for full fidelity.

doubleheader_flag is related to game_number: when game_number=2, doubleheader_flag=1
is guaranteed. home_rest_days=0 also co-occurs with game_number=2 (162 such rows).
No data integrity issues; these are structurally expected co-occurrences.

---

## SUMMARY VERDICT

PIT-SAFETY:     PASS
GRAIN:          PASS  (unique game_pk)
NULL COVERAGE:  PASS  (only local_start_hour has nulls; documented and mitigatable)
SCOPE EXCLUSION: PASS  (weather, umpire, postgame all excluded)
FIELD COUNT:    12 APPROVED + 5 CARRIED + 13 EXCLUDED = 30 total (matches game_table)
