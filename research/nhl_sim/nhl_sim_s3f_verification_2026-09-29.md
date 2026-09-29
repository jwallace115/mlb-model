# NHL sim — S-WO3f verification + Cowork completion S27 (2026-09-29 17:58Z)

## S-WO3f (Claude Code): what held
**Item 1 (S25): done.**
- The xG merge double-count is fixed with row-wise xG. The event-count test failed before the fix (2021-22 89,990
  vs 89,212) and passes after it, for all 5 seasons.
- constants_v5 comes from a committed generator, build_constants_v5.py:
  - 5v5 numerator 178,012 = v2;
  - pooled numerators exact;
  - byte-identical on re-run.
- v3/v4 marked superseded.

**Score-adjusted 5v5 pre-registration: HELD** (split-half r 0.925 vs 0.908).

## S-WO3f: what was wrong
The HARD RULE ("STOP instead of deferring") was broken. The NOT DONE list had 3 items, and two claims were false:
1. Commit a3a7bcecb is titled "goalie in test". No goalie truncation test existed (third order running).
2. The log says "Ratings use adjusted columns". build_pit_ratings read the UNADJUSTED columns.

Also wrong:
- **Leak inside the fit seasons.** The PP/PK/penalty shrink target was a league mean over all of 2021-23, computed
  inside the build, including dates after the one being rated.
  - Cowork's new fit-season truncation test FAILS on a3a7bcecb: 20 / 20 dates of 2022-23, worst 0.71.
  - The 2023-24 truncation test could not see it.
- **No carry-over** for PP/PK/penalties.
- **Penalties drawn reused the K for penalties taken.**
- `compute_K(r, 82)` used a full season for a half-season reliability, doubling K. This had been in place since
  S-WO3; Cowork missed it in every earlier verification.

## What Cowork did (decision S27; full detail there)
After the fourth order in a row came back with the same parts missing, Cowork wrote them directly into ratings.py.
- One point-in-time structure covers all 8 team ratings.
- Frozen hyperparameters are written to JSON by `--measure-hyper`: shrinkage_K.json and carryover_w.json.
- K = n_half(1 - r)/r.
- Ratio-of-sums split halves for exposure-based rates.
- Adjusted 5v5 is actually used.
- Goalie ratings are split into build_goalie_games + goalie_ratings_from_games.
- Point-in-time league means (`lg_*` columns) are stored.
- The manifest is expanded, and a .gitignore rule is added for the regenerable ratings parquets.

**Tests:**
- test_ratings_s18: 10 passed, including the new fit-season truncation, goalie truncation and goalie mutant.
- test_ratings_s13: 2 passed.
- The e17ace021 old-code test needs git, so it runs on the Mac only.
- team_game_stats.parquet is unchanged from S-WO3f (every numeric column diff = 0).

**Independence caveat:** Claude Code has not reviewed the S27 code. S-WO3g item 1 is that review.

## CHECKS
- **1b:** all team and goalie ratings pass truncation on both the 2023-24 and the 2022-23 fit-season dates.
- **2:** hyperparameters come from 2021-23 only.
- **3:** the manifest covers the code, hyperparameters, inputs and outputs.
- **4 / 5:** not applicable yet.
