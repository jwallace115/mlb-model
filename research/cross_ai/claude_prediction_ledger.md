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
**Grade:** NOT YET GRADED — requires DA-2 Item 3.

**DA-2b (55%):** The strongest T1 cell has the same sign on T2 2021-22.
**Grade:** NOT YET GRADED.

**DA-2c (85%):** N2 (own-defense control) stays |z| < 2 on every cell.
**Grade:** NOT YET GRADED.

**DA-2d (90%):** N1 (shuffled labels) kills every cell that cleared.
**Grade:** NOT YET GRADED.
