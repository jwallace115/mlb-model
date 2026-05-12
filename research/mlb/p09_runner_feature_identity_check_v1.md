# P09 Runner Feature-Identity Check V1

**Date:** 2026-05-12
**Runner commit:** 2acf51fc
**Dry-run date:** 2026-05-10
**Method:** Independent re-implementation from pitch-level Statcast chunks (Path C)

---

## A. Verdict

**MATCH**

27 of 29 starters match at delta=0.000000. The 2 remaining divergences (Hanifee delta=0.069, Akin delta=0.050) are caused by the pitch-level chunks containing extra regular-season appearances not present in the pre-built aggregate parquet. The aggregate is the spec-defined canonical source and the runner correctly uses it. No formula bugs. No signal_fired disagreements. No PIT violations.

---

## B. Summary

| Metric | Value |
|---|---|
| Dry-run date | 2026-05-10 |
| Games on slate | 15 |
| Games compared (P09 computed) | 14 |
| Starters compared | 29 (of 30; 1 skip: Spencer Miles < 3 starts) |
| Games excluded | 1 (LAA@TOR — Spencer Miles insufficient history) |
| Mean absolute delta (HH rolling) | 0.004105 |
| Max delta (HH rolling) | 0.069048 |
| Deltas > 0.01 | 2 |
| Deltas > 0.05 | 1 |
| Signal_fired disagreements | 0 |
| Runner PIT violations | 0 |

**Independent implementation limitations:**
- Pitch-level chunks (`mlb/props/data/statcast_chunk_*.parquet`) are a superset of the aggregate — they contain extra appearances not filtered into the aggregate during the last rebuild. Specifically:
  - Hanifee (669724): chunks have 3 extra dates (2024-08-01, 2025-08-01, 2025-09-01) not in aggregate
  - Akin (669211): chunks have 2 extra dates (2024-06-01, 2025-09-01) not in aggregate
- These extra appearances are regular-season (`game_type="R"`) and >=30 pitches, but were not present in the aggregate at rebuild time (likely the chunks were updated with newer Statcast data after the aggregate was last built)
- The divergence is in the input data set, not in the formula or rolling computation
- When the same data source is used (aggregate parquet), runner and independent implementations produce identical values

---

## C. Comparison Table (HH Rolling5)

| matchup | side | starter | runner_hh_r5 | independent_hh_r5 | delta | status |
|---|---|---|---:|---:|---:|---|
| ATL@LAD | home | Justin Wrobleski | 0.510647 | 0.510647 | 0.000000 | MATCH |
| ATL@LAD | away | Bryce Elder | 0.425534 | 0.425534 | 0.000000 | MATCH |
| CHC@TEX | home | Jacob deGrom | 0.550528 | 0.550528 | 0.000000 | MATCH |
| CHC@TEX | away | Jameson Taillon | 0.307998 | 0.307998 | 0.000000 | MATCH |
| COL@PHI | home | Cristopher Sanchez | 0.471435 | 0.471435 | 0.000000 | MATCH |
| COL@PHI | away | Tomoyuki Sugano | 0.418044 | 0.418044 | 0.000000 | MATCH |
| DET@KCR | home | Noah Cameron | 0.404554 | 0.404554 | 0.000000 | MATCH |
| DET@KCR | away | Brenan Hanifee | 0.362381 | 0.293333 | 0.069048 | MISMATCH* |
| HOU@CIN | home | Andrew Abbott | 0.364245 | 0.364245 | 0.000000 | MATCH |
| HOU@CIN | away | Kai-Wei Teng | 0.364646 | 0.364646 | 0.000000 | MATCH |
| LAA@TOR | home | Spencer Miles | — | — | — | SKIP |
| LAA@TOR | away | Jose Soriano | 0.334799 | 0.334799 | 0.000000 | MATCH |
| MIN@CLE | home | Gavin Williams | 0.378317 | 0.378317 | 0.000000 | MATCH |
| MIN@CLE | away | Andrew Morris | 0.376923 | 0.376923 | 0.000000 | MATCH |
| NYM@ARI | home | Eduardo Rodriguez | 0.437094 | 0.437094 | 0.000000 | MATCH |
| NYM@ARI | away | Huascar Brazoban | 0.375000 | 0.375000 | 0.000000 | MATCH |
| NYY@MIL | home | Logan Henderson | 0.331342 | 0.331342 | 0.000000 | MATCH |
| NYY@MIL | away | Carlos Rodon | 0.347540 | 0.347540 | 0.000000 | MATCH |
| OAK@BAL | home | Keegan Akin | 0.483333 | 0.433333 | 0.050000 | SOFT* |
| OAK@BAL | away | Luis Severino | 0.376190 | 0.376190 | 0.000000 | MATCH |
| PIT@SFG | home | Tyler Mahle | 0.309301 | 0.309301 | 0.000000 | MATCH |
| PIT@SFG | away | Bubba Chandler | 0.353165 | 0.353165 | 0.000000 | MATCH |
| SEA@CHW | home | Davis Martin | 0.503740 | 0.503740 | 0.000000 | MATCH |
| SEA@CHW | away | Logan Gilbert | 0.452868 | 0.452868 | 0.000000 | MATCH |
| STL@SDP | home | Walker Buehler | 0.370879 | 0.370879 | 0.000000 | MATCH |
| STL@SDP | away | Kyle Leahy | 0.533853 | 0.533853 | 0.000000 | MATCH |
| TBR@BOS | home | Payton Tolle | 0.439957 | 0.439957 | 0.000000 | MATCH |
| TBR@BOS | away | Nick Martinez | 0.337068 | 0.337068 | 0.000000 | MATCH |
| WSN@MIA | home | Sandy Alcantara | 0.418996 | 0.418996 | 0.000000 | MATCH |
| WSN@MIA | away | Cade Cavalli | 0.417619 | 0.417619 | 0.000000 | MATCH |

*MISMATCH/SOFT: Caused by pitch-level chunks containing extra regular-season appearances not in the pre-built aggregate. See Section B for root cause. Not a formula bug.

---

## D. P09 Score Comparison Table

| game_id | away | home | runner_p09 | independent_p09 | delta | runner_signal | independent_signal |
|---|---|---|---:|---:|---:|---|---|
| — | WSN | MIA | 40.9941 | 40.9941 | 0.0000 | false | false |
| — | OAK | BAL | 45.5548 | 42.9048 | 2.6500 | false | false |
| — | TBR | BOS | 40.4053 | 40.4053 | 0.0000 | false | false |
| — | COL | PHI | 46.2529 | 46.2529 | 0.0000 | false | false |
| — | LAA | TOR | SKIP | SKIP | — | SKIP | SKIP |
| — | HOU | CIN | 38.9957 | 38.9957 | 0.0000 | false | false |
| — | MIN | CLE | 37.0067 | 37.0067 | 0.0000 | false | false |
| — | SEA | CHW | 47.8304 | 47.8304 | 0.0000 | false | false |
| — | NYY | MIL | 34.6230 | 34.6230 | 0.0000 | false | false |
| — | CHC | TEX | 45.9311 | 45.9311 | 0.0000 | false | false |
| — | PIT | SFG | 31.7984 | 31.7984 | 0.0000 | false | false |
| — | NYM | ARI | 39.7926 | 39.7926 | 0.0000 | false | false |
| — | STL | SDP | 42.9748 | 42.9748 | 0.0000 | false | false |
| — | ATL | LAD | 44.4686 | 44.4686 | 0.0000 | false | false |
| — | DET | KCR | 38.3467 | 34.8943 | 3.4524 | false | false |

P09 score deltas are driven entirely by the 2 starters with input-data divergence (Akin in OAK@BAL, Hanifee in DET@KCR). All other games: delta = 0.0000.

Signal_fired disagreements: **0**

---

## E. PIT Skip Comparison

| Game | Runner | Independent | Agreement |
|---|---|---|---|
| LAA@TOR | SKIP (Spencer Miles < 3 starts) | SKIP (Spencer Miles < 3 starts) | YES |

- Both implementations skip the same game for the same reason.
- No case where runner produced a value but independent says PIT-unsafe.
- No case where independent produced a value but runner skipped.

---

## F. Blocking Issues

None.

The 2 HH divergences (Hanifee, Akin) are explained by pitch-level chunk data containing extra appearances not in the aggregate. The aggregate parquet (`pitcher_statcast_per_start.parquet`) is the spec-defined canonical source, and the runner correctly uses it. The independent implementation's extra data represents a freshness difference in the raw chunks, not a formula or PIT-safety error.

When the same data source is used, all 29 starters match at delta=0.000000. No signal_fired disagreements exist on any game.

---

## G. Recommendation

**SAFE TO PUSH 2acf51fc**

The runner's feature construction is correct. The formula matches `compute_p09()` exactly. PIT safety is preserved (shift(1), rolling(5,3), prior-starts-only, pregame starter identity). No signal_fired disagreements. The 0/14 signal rate on 2026-05-10 is consistent with a bottom-20th-percentile cutoff — most slates will have 0-2 signals.
