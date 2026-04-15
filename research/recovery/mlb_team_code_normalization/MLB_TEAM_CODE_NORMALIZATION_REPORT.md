# MLB TEAM-CODE NORMALIZATION REPORT
Generated: 2026-04-15

---

## PURPOSE

Six parquet substrates feed the MLB simulation pipeline. Two distinct team-code
dialects exist across those substrates: Baseball Savant / pybaseball style and
MLB Stats API / game_table style. Unresolved, these dialects silently destroy
cross-substrate joins — rows that should match on (game_pk, team) fall through
because one side says "AZ" and the other says "ARI". This artifact documents
every mismatch, defines the canonical target, and verifies that applying the
normalization map achieves full join recovery.

---

## INPUTS — FILES AUDITED

| Substrate | Path | Team column |
|-----------|------|-------------|
| hitter | research/recovery/mlb_hitter_statcast_substrate/batter_game_statcast.parquet | team |
| lineup_state | research/recovery/mlb_lineup_state_substrate/team_game_lineup_state.parquet | team |
| per_start_sp | research/recovery/mlb_starting_pitcher_substrate/per_start_starter_substrate.parquet | team |
| rolling_sp | research/recovery/mlb_starter_profile_substrate/rolling_starter_profile.parquet | team |
| bullpen_features | sim/data/bullpen_features.parquet | team |
| bullpen_usage | sim/data/bullpen_usage.parquet | team |
| game_table | sim/data/game_table.parquet | home_team / away_team |

---

## OBSERVED SYSTEMS

### System A — Statcast style (Baseball Savant / pybaseball)
Substrates: hitter, per_start_sp, rolling_sp
Team count: 31 (includes both OAK and ATH during transition period)
Divergent codes vs canonical: ATH, AZ, CWS, KC, SD, SF, TB, WSH

### System B — Game-table style (MLB Stats API canonical)
Substrates: lineup_state, bullpen_features, bullpen_usage, game_table
Team count: 30
All codes match game_table exactly (verified: EXACT MATCH for all three substrates)

---

## CANONICAL TARGET

**game_table_style** — MLB Stats API abbreviations.

Rationale: game_table is the game spine. Every cross-substrate join flows
through game_pk, and game_pk originates in game_table. Choosing game_table
style as canonical means lineup_state, bullpen_features, and bullpen_usage
require zero transformation. Only the three Statcast-sourced substrates
(hitter, per_start_sp, rolling_sp) need remapping.

Canonical 30-team set:
ARI ATL BAL BOS CHC CHW CIN CLE COL DET HOU KCR LAA LAD MIA MIL MIN
NYM NYY OAK PHI PIT SDP SEA SFG STL TBR TEX TOR WSN

---

## NORMALIZATION MAP (8 pairs)

| Statcast code | Canonical code | Team |
|---------------|----------------|------|
| ATH | OAK | Oakland Athletics (transitional Savant code) |
| AZ  | ARI | Arizona Diamondbacks |
| CWS | CHW | Chicago White Sox |
| KC  | KCR | Kansas City Royals |
| SD  | SDP | San Diego Padres |
| SF  | SFG | San Francisco Giants |
| TB  | TBR | Tampa Bay Rays |
| WSH | WSN | Washington Nationals |

Map completeness: confirmed covers 100% of non-canonical codes observed in all substrates.
No residual non-canonical codes remain after map application (verified).

---

## JOIN VERIFICATION — 5 SCENARIOS

| Test | Join | Before | After | Total | Recovery |
|------|------|--------|-------|-------|----------|
| T1 | lineup_state x bullpen_features | 19,712 | 19,712 | 19,712 | +0 |
| T2 | lineup_state x rolling_sp | 14,939 | 19,712 | 19,712 | +4,773 |
| T3 | lineup_state x hitter (team-game) | 14,939 | 19,712 | 19,712 | +4,773 |
| T4 | rolling_sp x bullpen_features | 15,006 | 19,804 | 19,914 | +4,798 |
| T5 | hitter (team-game) x game_table (home) | 7,472 | 9,856 | 19,712 | +2,384 |

**T1 note:** Both substrates were already canonical — 100.0% match before normalization confirms
the baseline is clean.

**T2 / T3 note:** 75.8% match before normalization (24.2% silent loss) is consistent with
8 affected teams across a multi-season dataset. After normalization: 100.0% recovery.

**T4 note:** 75.4% before → 99.4% after. The 0.6% residual gap (110 rows) is NOT a team-code
problem — residual check confirmed zero non-canonical codes after normalization. The gap reflects
game-pk-level coverage differences between rolling_sp and bullpen_features substrates
(some game_pks present in rolling_sp have no bullpen entry; separate data-availability issue).

**T5 note:** 37.9% → 50.0%. Test 5 joins hitter team-game records against game_table using
home_team only, so a maximum 50% match rate is expected by construction (half the team-games
are away teams). Recovery of +2,384 rows confirms the mismatch was the binding constraint.

---

## CARRY-FORWARD RULE

1. **Any cross-substrate join using a team key MUST normalize Statcast-style codes to
   game_table_style BEFORE merging.** Failure to do so silently drops ~24% of rows.

2. **This artifact (mlb_team_code_normalization_map.json) is the canonical reference.**
   Do not hard-code the mapping inline in pipeline scripts; import it from this file.

3. **Standard normalization one-liner:**
   ```python
   NORM = {k: v for d in [nm['source_systems']['statcast_style']['mapping']] for k, v in d.items()}
   df['team'] = df['team'].map(lambda x: NORM.get(x, x))
   ```

4. **Scope:** This normalization resolves team-code dialect mismatches only. It does not
   address the rolling-starter partial-window averaging caveat (first N games of a season
   use fewer observations in the rolling window) — that is a separate documented limitation
   of the rolling_sp substrate and is not a normalization problem.

5. **OAK/ATH note:** The Statcast code ATH appears during the Oakland-to-Sacramento
   transition. It maps to canonical OAK. Both ATH and OAK may appear in the hitter /
   per_start_sp / rolling_sp substrates across different seasons; after normalization
   both collapse to OAK, consistent with game_table which never uses ATH.

---

## VERDICT

RESOLVED. The MLB team-code mismatch is a two-dialect problem with a clean 8-pair map.
Normalization achieves 100% join recovery for all cases where the team-code is the
binding constraint. The map is complete, verified, and ready for pipeline integration.
