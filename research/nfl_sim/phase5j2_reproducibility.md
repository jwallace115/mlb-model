# Phase 5J-2 Item 4: Board reproducibility diagnosis

Date: 2026-09-21. Branch `eng/5j`. NO engine file edited.

## Symptom

Identical code, ratings, rosters, lines, props. Anchoring offsets agree to 3
decimals in 15/15 games. Yet 621 of 1,237 legs differ between the Mac's 15:50Z
board and a Linux re-run, by up to 0.60 (Ashton Jeanty O14.5 rush att:
0.756 Mac vs 0.275 cloud). Two Linux runs agree exactly.

## Library versions

| Platform | Python | numpy | pandas | pyarrow |
|----------|--------|-------|--------|---------|
| Mac      | 3.13.1 | 2.4.3 | 2.3.3  | 23.0.1  |
| Linux    | 3.11   | (from Cowork note) | 3.0.2 | ? |

## Root cause: unstable sort on tied shares

`engine.py` line 474:
```python
renormed = renormed.sort_values("target_share", ascending=False).reset_index(drop=True)
```

Default `sort_values` uses quicksort, which is **not stable**. When multiple
players have the same `target_share` (e.g. all 8 bench players at 9.48e-9),
their relative order is implementation-defined and varies between:
- platforms (ARM vs x86)
- numpy versions (2.4.3 vs whatever Linux runs)
- pandas versions (2.3.3 vs 3.0.2)

### Measured: LV has 7 exact ties

Eight players share `target_share = 9.476234e-9`: Kirk Cousins, Ian Thomas,
Dareke Young, Connor Heyward, Dylan Laube, Mike Washington Jr., Fernando
Mendoza, Aidan O'Connell. Seven adjacent pairs are exactly tied.

Among these, **Mike Washington Jr. has carry_share = 0.2189** (the team's RB2).
His position in the sort order determines which RNG draw he receives in
`_disperse()`, which changes the renormalized carry shares for ALL players.

Default quicksort (Mac) places Washington at index 12 of 15. Stable sort +
player_id tiebreak places him at index 13. The per-player Beta draws shift,
and after carry-share renormalization:

| Sort method | Jeanty carries | Washington carries |
|-------------|---------------:|-----------------:|
| Mac default | 16.62 | 9.25 |
| Stable + pid | 23.70 | 1.97 |
| Linux default | 21.43 (Cowork) | 4.77 (Cowork) |

Three different orderings produce three different results. The cause is confirmed.

## Every place where ORDER or a LIBRARY default can change a result

1. **`sort_values("target_share")` at line 474** (CONFIRMED, reachable, causes the
   measured difference). Default quicksort on near-tied shares.

2. **`_disperse()` inner loop (line 507-514)**: draws `rng.beta(a, b)` for each
   player `j` in order. Different player order = different RNG stream position =
   different draws. THIS is the mechanism through which (1) propagates.

3. **`np.cumsum` on share arrays (lines 527-530)**: cumulative sums determine
   player assignment via `np.searchsorted`. Same values in a different order
   change which player receives each carry/target/TD.

4. **`top_tgt.nlargest(6, "mean_tgt")` and `top_car.nlargest(2, "mean_car")` in
   `build_board` (lines 639-640)**: `nlargest` with tied values can return
   different player sets. This affects which players are PRICED, not their sim_p.

5. **`set(top_tgt["player_id"]) | set(top_car["player_id"])` (line 641)**: set
   iteration order is arbitrary in Python >= 3.7 (insertion-ordered dicts, but
   sets are hash-ordered). However, since `selected_pids` is only used for
   membership tests (line 643: `for pid in selected_pids`), iteration order
   affects only which player's legs appear first in the board, not their values.

6. **`merge` in the sim engine (various)**: pandas merge preserves left-frame
   order; not directly reachable as a cause.

7. **numpy Generator stream across versions**: numpy 2.x guarantees stream
   compatibility with the same Generator type and seed. But the Beta distribution
   implementation could theoretically differ between 2.4.3 and whatever Linux
   runs. NOT tested.

## Why anchored Jeanty has ~12 carries vs unanchored ~21

Measured for LV@LAC (Mac, default sort):
- **Unanchored**: margin = -2.38 (LV wins by ~2), Jeanty 16.62 carries
- **Anchored**: offsets dh=+0.73, da=-0.94; margin = +6.78 (LAC wins by ~7),
  Jeanty 18.29 carries

(Cowork's Linux: unanchored 21.43, anchored 12.26.)

The raw sim has LV favoured, but the market has LV as a 7-point dog. Anchoring
pushes LV's EPA down (da = -0.94) so the sim matches the market. Under that
offset, LV trails more often, game script shifts from rushing to passing, and
total team carries drop. Jeanty's carry SHARE stays high (~59%), but the
denominator (total team carries) falls sharply.

The different per-machine carry values (Mac Jeanty 18.29 vs Linux 12.26 anchored)
come from the same ordering bug: the player-level carry distribution differs,
even though team-level anchoring offsets are identical (verified:
dh=+0.7261, da=-0.9378 for both default and stable sort on the Mac).

## Pre-registered prediction assessment

> "the cause is an ordering dependence" -- **CORRECT**.

> "forcing a total order (share, then player_id, stable) makes the Mac reproduce
> Linux to within 0.02 on >= 99% of legs" -- **WRONG**.

Stable sort + player_id tiebreak produces a THIRD ordering, not the same as
Linux's quicksort. Jeanty carries move from 16.62 (Mac default) to 23.70 (Mac
stable), neither of which matches Linux's 21.43. To make machines agree, BOTH
must use the same deterministic sort. This requires an engine edit (changes
fingerprint, needs its own work order with a re-fit decision).

## Null control

Team-level anchoring offsets do NOT move between sort methods:
dh=+0.7261, da=-0.9378 for both default and stable sort (Mac, LV@LAC).
The ordering only affects the player-level distribution within team totals.

## Fix path (NOT implemented here — diagnosis only)

`engine.py` line 474: change to
```python
renormed = renormed.sort_values(
    ["target_share", "player_id"], ascending=[False, True], kind="stable"
).reset_index(drop=True)
```
This changes the engine fingerprint and requires a re-fit decision + test suite
re-baselining. Separate work order.
