# Claude Prediction Ledger — repo copy

Predictions registered before data examination. Each is graded HELD / DID NOT HOLD
with the measured number after the run.

## PM-1 through PM-6 (registered 2026-10-11, PM-1 Item 2)

**PM-1:** Graded ai_nfl prop LOSSES with a chain: primary link = efficiency on 45%
(90% range 30–60%).
**Grade:** NOT YET GRADED — requires item 2 real-data run from main.

**PM-2:** ... primary link = plays or pass/run rate (game script) on 25% (15–35%).
**Grade:** NOT YET GRADED.

**PM-3:** ... primary link = share on 20% (10–30%); AVAILABILITY auto-code on ≤ 10%.
**Grade:** NOT YET GRADED.

**PM-4:** ≥ 15% of graded yardage-prop LOSSES are one_play_decided (removing the
player's longest play flips the result).
**Grade:** NOT YET GRADED.

**PM-5:** Tag-mapped thesis on non-price ai_nfl prop picks: held 40% / failed 30% /
flat 30%; the real held rate is NOT more than 5 pp above the tag-shuffled null.
**Grade:** NOT YET GRADED.

**PM-6:** ≥ 30% of graded WINS with a checkable thesis are thesis-failed (won for the
wrong reason).
**Grade:** NOT YET GRADED.

## DA-0a through DA-0d (registered 2026-10-25, DA-0 Item 0; graded by: Claude Code DA-0)

**DA-0a (70%):** Coverage labels (man/zone, pass rushers, defenders in box) usable from 2022, not 2023.
**Grade:** PARTIALLY HELD — FTN charting from 2022 at 100%; participation man/zone from 2023 only (37.8% in 2022).

**DA-0b (60%):** Exact normalized name + team resolves >= 95% of prop player-games to a player_id.
**Grade:** HELD — 97.3% resolution rate (from da0_name_resolution.parquet).

**DA-0c (55%):** 2023, 2024 and 2025 EACH have >= 8,000 player-games with a receptions/rec-yds/rush-yds close.
**Grade:** HELD if combined across 3 markets (8,541-9,291); DID NOT HOLD per individual market (max 3,965).

**DA-0d (75%):** Official weekly stats join the resolved prop rows at >= 97% by player_id + game_id.
**Grade:** PARTIALLY HELD — passing/rush 95-97%; reception 91-94% (gap is event→game_id mapping, fixable).

## DA-2a through DA-2d (registered 2026-10-27, DA-2 Item 1; DA_HYPOTHESES_v1.md sha d1ed065e514ad9bd)

**DA-2a (60%):** >= 1 cell clears |z| >= 2 on T1 (2023 line residual).
**Grade:** HELD — H1 t1_z=2.81, H5 t1_z=4.63 (graded by: Claude Code DA-2).

**DA-2b (55%):** The strongest T1 cell has the same sign on T2 2021-22.
**Grade:** HELD — H5 (strongest T1 z=4.63) has T2 z=1.41 same sign (graded by: Claude Code DA-2).

**DA-2c (85%):** N2 (own-defense control) stays |z| < 2 on every cell.
**Grade:** HELD — all N2 |z| < 2 (graded by: Claude Code DA-2).

**DA-2d (90%):** N1 (shuffled labels) kills every cell that cleared.
**Grade:** DID NOT HOLD — N1 did NOT kill H2_rb_funnel (graded by: Claude Code DA-2).
Note: DA-2d's N1 was a within-defense permutation that preserves >=60% of labels (a non-null).
The corrected cross-defense N1 (DA-D12) was not re-run on discovery.

## DA-3a through DA-3c (registered 2026-10-28, DA-3 Item 1c; BEFORE any 2024-25 row is read)

**DA-3a (20%):** H2's CENTERED T1 effect on 2024-25 is same-sign with z >= 1.
**Grade:** DID NOT HOLD — centered z = 0.41 (graded by: Claude Code DA-3).

**DA-3b (10%):** H2 over at the DK close has positive ROI on 2024-25.
**Grade:** DID NOT HOLD — DK ROI over = -13.1% (graded by: Claude Code DA-3).

**DA-3c (70%):** Own-defense control on H2 is |z| < 2.
**Grade:** HELD — own-defense z = -1.09 (graded by: Claude Code DA-3).
