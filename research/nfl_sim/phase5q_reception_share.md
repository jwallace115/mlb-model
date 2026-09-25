# Phase 5Q Item 2 — The quoted players' share of team receptions

Date: 2026-09-25. Engine fingerprint: `02fbcab6e6ed042e` (unchanged).
Runtime: 199s (3.3 min). Zero API credits.

## Pre-registered predictions (written before looking)

1. Team receptions per game sim vs real are within 0.5 (volume is not the problem).
2. The top-6 share is >= 3 points higher in the sim than real in BOTH samples (the division
   is the problem).
3. The gap is largest at WR.

If (1) fails, volume is back on the table.

## Derivation

**Sample A (2026 W1-2):** 32 games x N=500 with the player layer. Per-player sim mean
receptions from `player_df.groupby(['player_id','team']).mean()['receptions']`. Real from
PBP 2026, `play_type == "pass"` and `complete_pass == 1`, grouped by `receiver_player_id`
and `posteam`. 64 team-games.

**Sample B (2024, 100 games):** First 100 K1 games (sorted by game_id, seed 42), N=500,
player layer ON. Same per-player sim mean vs PBP 2024 real. 200 team-games.

**Top-6 rule:** For each team-game, the 6 players with the highest sim mean receptions.
"Quoted-type" because the book typically quotes receptions lines for ~6 skill players per team.

**Active universe vs actual receivers:** `active_universe_weekly.parquet`, season=2026, week=2,
`active_flag == True`, positions WR/TE/RB. Real receivers: unique `receiver_player_id` values
with at least 1 completion in PBP 2026 Week 2.

## Results

### Team receptions per game

| sample | sim | real | diff |
|--------|----:|-----:|-----:|
| A (2026 W1-2) | 28.3 | 20.5 | **+7.8** |
| B (2024 100g) | 25.0 | 21.0 | **+4.0** |

**Prediction (1): FAILED.** The sim over-projects team receptions by +7.8 (2026) and +4.0
(2024). Volume IS the problem — the sim produces far more completions per team than real.

### Top-6 share of team receptions

| sample | sim share | real share | diff |
|--------|----------:|-----------:|-----:|
| A (2026 W1-2) | 0.767 | 0.808 | **-0.041** |
| B (2024 100g) | 0.763 | 0.826 | **-0.063** |

**Prediction (2): FAILED in the OPPOSITE direction.** The sim's top-6 share is 4-6pp LOWER
than real, not higher. The sim spreads receptions too broadly across the roster.

**Prediction (3): N/A.** Since the direction reversed (top-6 gets less, not more), the "largest
at WR" prediction does not apply.

### Where the excess receptions go

| group | sim rec/game | real rec/game | excess | excess share |
|-------|------------:|-------------:|-------:|:-------------|
| Top-6 | 21.7 (A) / 19.0 (B) | 16.6 (A) / 17.3 (B) | +5.1 (A) / +1.8 (B) | 65% (A) / 44% (B) |
| Rest  |  6.6 (A) /  6.0 (B) |  3.9 (A) /  3.7 (B) | +2.7 (A) / +2.3 (B) | 35% (A) / 56% (B) |

Per-player excess: top-6 gets +0.85/player (A); rest gets +0.39/player (A). But relative to
their real base, the rest is inflated by +69% (2.7/3.9) while top-6 is inflated by +31%
(5.1/16.6). The bottom of the roster gets a disproportionate inflation.

### Top-6 per-position sim means

| sample | WR mean | WR count | TE mean | TE count | RB mean | RB count |
|--------|--------:|---------:|--------:|---------:|--------:|---------:|
| A (2026 W1-2) | 4.01 | 3.5 | 3.54 | 1.6 | 2.85 | 1.1 |
| B (2024 100g) | 3.57 | 3.5 | 2.93 | 1.5 | 2.49 | 1.2 |

### Active universe vs actual receivers (2026 Week 2)

| metric | value |
|--------|------:|
| Active skill (WR/TE/RB) per team | 12.9 (range 11-15) |
| Players who caught a pass per team | 7.2 (range 5-9) |
| **Gap: phantom receivers** | **5.7 per team** |
| Sim players per team | 13-15 |

5.7 active skill players per team get sim target shares and generate receptions but do NOT
catch a single pass in real games. At ~1 sim reception each, that accounts for ~5.7 of the
+7.8 excess team receptions in 2026.

### _renormalize_measured — read-only analysis

Code at `engine.py:381-435`. When inactive players are removed:
1. Their vacated `target_share` is redistributed to active players using `REDIST_TARGET`
   position-aware weights (line 410-420).
2. Any undistributed residual goes to same-position active players (line 422-426).
3. Final renormalize to sum=1 across ALL active players (line 428-433).

The renormalization guarantees that the total target share sums to 1.0 across active players.
With 13 active skill players, each player gets at minimum ~1/13 = 7.7% of team targets. But in
reality, only 7 players catch passes, so the effective floor is ~1/7 = 14.3%. The sim gives
non-zero shares to 6 extra players who produce phantom receptions.

The mechanism: the active list is broader than the actual receiving corps. Players who are
"active" (not injured/inactive) but don't get targeted in a given game — backup WRs, blocking
TEs, third-down RBs — all receive sim shares and generate receptions. In reality, their targets
are approximately zero. This is a concentration problem: the sim assumes every active skill
player participates in the passing game, when in practice ~45% of them don't.

## Diagnosis

**D134's "+0.25 over-projection for quoted players" hid a much larger problem: the sim
over-produces team receptions by +4 to +8 per game, and the excess is disproportionately at
the bottom of the roster.**

The mechanism is `_renormalize_measured` + the `active_uni` breadth:
1. ~13 skill players are marked active per team (WR/TE/RB).
2. The renormalization distributes ALL target share across these 13 players.
3. In reality, only ~7 of them catch passes. The other ~6 each generate ~1 phantom reception
   in the sim, adding ~6 excess receptions per team.
4. The remaining +2 per-team excess comes from the top-6 players being individually over-projected
   (consistent with D133's +0.25-0.3 per player for quoted players).

This explains why D133's gap decomposition found team pass volume explained only 11% of the
player-level mean error: the team-level error is driven by the BOTTOM of the roster (unquoted
players), while D133 only measured quoted players.

**The fix (not applied in this order):** either (a) narrow the active list to players who are
actual passing-game participants (top ~7-8 by target share), or (b) floor the target share at
some minimum and give the residual back to the top players, or (c) scale down the share of
bottom-ranked players. All three would reduce the phantom-receiver inflation.

No engine, usage, table, or parameter change.
