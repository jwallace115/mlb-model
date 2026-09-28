# Phase 5Y verification — Cowork, 2026-09-28

Branch `eng/5y` @ `d62d2b0` (4 item commits + session log; base = the 5X merge). Verified in Linux worktrees at
5Y head and at main (5X engine). Numbers recomputed here unless marked "read".

## Item 0 (D172) — accepted
Pooled `first_down` rows are written at every level (main, Q4_mid, parent, legacy, eoh, fgs), read in the diff; the
eoh/fgs lookup goes split -> pooled -> all. Both 5X reds pass again (read; Cowork's own 5X measurement with the
pooled rows appended gave P(tie|OT) 0.111 / tied late FG 0.189, same direction).

## Item 1 (D173) — the fix is right; the pre-registered effect was too big
- The exclusion is applied AFTER each play's elapsed is computed (tables.py:503-513), so the play before a touchdown
  still measures the time to the touchdown snap. Correct. Same in the eoh and fgs builders.
- Reported cell changes (+3.3 fd_pass, +3.5 fd_rush) are on a different pooling than the pre-registration
  (+3.45 / +3.85, "normal" period, all states); the builder logic is identical to Cowork's derivation, so this is a
  reporting difference, not a defect. The order's "before/after table" was not printed as specified.
- Sim plays on the sample -2.8 vs pre-registered -3.5 to -5.5: FAILED, reported plainly. My estimate used real
  play counts and a flat 27 s per play; the sim's cell mix differs. The miss is mine.

## Item 2 (D174) — the class-by-class comparison was not done, for the third order running
5W, 5X and 5Y each carried it; each report says "not completed" (5Y: "due to time constraints"). The report's
arithmetic also does not close: items 0+1 are said to close 4.2 plays, the per-item numbers add to 2.7, and the real
side is "~125.8" (not computed on the sample). Prediction (2) HELD (+3.2) and stands; the diagnosis paragraph does not.

## Item 3 (D175) — K1 reproduces; the new red is misattributed
- From `phase5y_k1_after_rows.parquet`: plays **128.29**, drives **23.29**, pts/team **21.55** — as reported. K1 gap
  **+2.5** plays (was +6.6 at 5X). The K1 header again says `-dirty` (the order required a clean tree).
- `test_safety_share`, same 80 games x 500 sims as the test: **main (5X) 0.319% (0.0784 safeties/game, 24.54
  drives/game) — passes by 0.005; 5Y 0.324% (0.0774/game, 23.87 drives/game) — fails by 0.000.** Safeties per game did
  not rise; the share rose because drives fell. D175's mechanism ("longer per-play clock -> more plays at extreme
  field position") is not what happened. The real finding: the sim makes **~0.078 safeties a game vs 0.049 real**
  (53 in 1,087 K1 games) — about 60% too many, and it has been so since before 5Y. The test was sitting 0.005 from
  its limit; the drives fix pushed it over.
- Points: 21.55/team vs 22.39 real (-0.84), as pre-registered. Points per drive: sim 43.1 / 23.29 = **1.85**, real
  44.77 / 21.74 = **2.06**. The sim still has 1.55 extra drives a game that score less.

## What stands
Items 0-1 and the K1 numbers go to main. The plays gap is down to +2.5 (from +6.6 two orders ago). Three things are
now the open engine questions, all measurable without a re-fit: the per-class clock residual (never measured),
safeties (60% too many), and points per drive (1.85 vs 2.06). 5Z measures all three and changes nothing.
