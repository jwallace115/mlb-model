# Phase 5X verification — Cowork, 2026-09-27

Branch `eng/5x` @ `d932bfa` (4 item commits + session log, base = the 5W merge). Verified in Linux worktrees at
5W head `4728337`, 5X item 0 `a87133d` and 5X head. Numbers recomputed here unless marked "read".

## Item 0 (D167) — accepted
`clock[can_advance] = 900.0` (was `+= 900.0`), read in the diff; OT keeps its own 600. `test_engine_5m` +
`test_engine_5w` pass at head on Linux (4/4, incl. the quarter-sum test that failed at 5W, unchanged). Player-OFF
hash `f51a26c01b848aaa` (item 0) and `78e64f674e71be6d` (head, fingerprint `b2d76c7b3b232df6`): the change is
behavioural, as it should be. Plays +1.0 (read) — inside the pre-registered +1.0 to +2.5.

## Item 1 (D168) — the split is right; the table lost its fallbacks, and the reason it "did nothing" is elsewhere
1. **The pooled `first_down` rows are gone from the table.** 5W had 32 main + 3 eoh + 3 fgs pooled first-down
   cells; 5X has 0. D168 says the engine falls back to the pooled cell "(0 cells now)" — so every fallback it
   added is dead code, and the order's "report how many cells fall back" was answered with the wrong number.
   Split cells that are thin (< 100) — **rush: tied Q2_late / Q4_late / Q4_mid, trail9+ Q4_late / Q4_mid_b,
   trail1-8 Q4_mid_b, lead1-8 Q4_mid_b; pass: tied Q4_late / Q4_mid, lead1-8 Q4_mid_b, lead9+ Q4_mid_a** — now
   drop to the all-clock parent cell. A tied offence's first down in the last two minutes drew 15.5 s at 5W and
   draws **33.4 s (rush) / 31.9 s (pass)** now; trailing 9+ Q4_late rush 16.7 -> 29.8 s.
2. **The end-of-half and FG-setup lookups still ask for `first_down`** (`ot_names_p` / `ot_names_r` feed
   `_eoh_runoff`), which no longer exists in those cells, so those draws silently use the `all` cell.
3. **Why the split moved plays by -0.1:** not "similar quantiles". The runoff table's cells include the
   drive-ending plays (TD, interception, fumble lost), whose real elapsed to the next snap is 8.6 s (PAT +
   kickoff), while the engine charges those plays separately with its typed `max(16u, 3)` clock (drive_end
   branch, never the table). The short clock is counted twice: once typed, once by dragging down every cell the
   non-scoring plays draw from. Real, all 1,087 K1 games, "normal" period, table definition vs drive-ending
   excluded: first_down_pass 33.26 -> 36.71 (7.8% drive-ending), first_down_rush 33.95 -> 37.80 (7.9%),
   complete 38.93 -> 39.54, run 38.16 -> 38.43, incomplete 8.19 -> 8.11. Summed over every cell at real counts:
   **+122.6 s a game** (fd_pass +59, fd_rush +43, complete +13, run +9, incomplete -2) — about 4.5 plays. The
   5W rush-vs-pass difference I measured (37.0 vs 32.7) was on drive-ending-excluded plays; with the TDs left in,
   the two cells are nearly equal (34.2 vs 34.2 at lead 1-8), which is exactly what 5X saw. My 5W diagnosis named
   the right cells and the wrong cause.

## Item 2 (D169) — partly done
- Prediction (1), the class-by-class decomposition that was the item's purpose, was **not scored** (said so).
  The timeout class, the mix-vs-rate split and kickoff-to-next-snap by season were not done.
- Prediction (3) is scored on the sim only; the real side's reconciliation was not checked.
- Prediction (2) "2024 largest (+9.0 vs +6.9 to +7.9)": at 50 games a season the real mean's standard error is
  about 1 play, so 2024 is not distinguishable from 2021 (+7.9). HELD as stated, not evidence for the
  dynamic-kickoff story. The by-margin table (+6.9 -> +11.3) is accepted.

## Item 3 (D170) — K1 reproduces; the two new reds are item 1's, not item 0's
- From `phase5x_k1_after_rows.parquet`: plays **132.35**, drives 23.98, pts/team **22.291** — as reported. K1 gap
  132.35 - 125.78 = **+6.6**. The K1 header says `1203e0861-dirty`: run on an uncommitted tree.
- **D170 attributes the two new reds to item 0's extra Q4 clock. Measured, that is wrong.** Same fixtures and
  seeds as the tests (12 games; OT x 2000 sims, late drives x 500):

| engine | P(tie \| OT) (cap 0.123) | tied late FG (0.251 ± 0.08) |
|---|---|---|
| 5W head | 0.1145 (n 1,284) | 0.192 (n 952) |
| 5X item 0 only | 0.1155 (n 1,325) | 0.199 (n 974) |
| 5X head | **0.1302** (n 1,398) — red | **0.1696** (n 961) — red |
| 5X head + 5W's pooled first_down rows appended to the table | 0.1110 (n 1,315) | 0.189 (n 997) |

  The quarter fix leaves both where they were; the dead fallback (late tied first downs burning ~33 s instead of
  ~15 s) turns both red; restoring the pooled rows turns both green. The reds are real signals of a defect, not
  noise, and not a calibration effect.
- Suite 4 red (read): fd_pen and tied expiry (known) plus the two above.

## What stands
Item 0 is right and goes to main. Item 1's split is right in principle but ships with dead fallbacks (late-game
first downs and end-of-half first downs draw the wrong cells) and cannot show its effect while drive-ending plays
sit in the cells. Item 3's numbers reproduce; its explanation of the reds does not. Merged to main with this
record (the defect's aggregate effect is -0.1 plays; its late-game effect is what the two reds measure); 5Y
restores the fallbacks first, then removes the double-counted drive-ending clock.
