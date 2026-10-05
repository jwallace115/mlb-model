# ChatGPT audit brief #18 (v17): FWD7e (D275), for a primary Sunday week 4 (2026-10-02)

Your audit #17 of `2afe33878` (NO-GO) is at `~/mlb-model/research/cross_ai/chatgpt_audit17_reply_2026-10-02.md`.
Cowork accepted it in **D275** (`research/nfl_sim/NFL_SIM_DECISION_v1.md`). Read D275 in full first. Cowork then
implemented **FWD7e**. Posture: guilty until proven innocent.

**Pin: `e875c0f62` on branch `eng/fwd6`** ("FWD7e Mac run: …"). Below it:
- `fcff24ce6`: FWD7e, D275;
- `2afe33878`: your audit #17 pin.

No tables changed, so no table commit was made. The code at `fcff24ce6` is byte-identical to the tree Cowork tested
(Cowork re-checked it from GitHub). The Mac run's output is in `research/nfl_sim/fwd7e_mac_run.md`. Put the full SHA
you audit on line 2.

**The real constraint:** the first Sunday window, IND@WAS: manual props pull at 12:15Z and harness at 12:45Z on
2026-10-04. The main + SNF harness is at 16:15Z.

## How to work

1. **Create the reply file first.** Write `research/cross_ai/chatgpt_audit18_reply_2026-10-03.md` in `~/mlb-model`
   with line 1 a title, line 2 the SHA, and INCOMPLETE. Rewrite it after every check.
   - **Note:** `~/mlb-model` was briefly switched to `nhl/live-lines` on 2026-10-02 by another session; it is back
     on `main` (repaired at 13bbb04f1).
   - Read code ONLY from the pinned `eng/fwd6` tree (`git show`/archive extraction), never from the `~/mlb-model`
     working tree.
   - Do not commit the reply file, and do not check out any branch in `~/mlb-model`.
2. **Each command must finish in under 10 minutes.** For long jobs, use `nohup … &` and poll the logs.
3. **If a tool is blocked, say which check it blocked and move on.**

## What FWD7e claims (verify each)

1. **Your A1.** `usage._pbp_game_dates` checks EVERY raw row BEFORE any grouping, whatever the dtype or row order.
   - Every row needs a present, non-blank `game_id`, `season == s`, and a `week` that is an integer in 1-22.
   - `<NA>` and NaN are caught through float conversion.
   - Nothing is filtered: a bad row HALTs, naming the row index. Then come D274's date and one-date/one-week checks.
2. **Every aggregated season.** `usage.load_pbp` runs the validator on every season file it reads (2020-2026), and so
   does `ratings.load_all_pbp`. The team-rating, tendency and kicker aggregations therefore cannot drop a play on a
   null key either. The refresh runs usage.py before ratings.py and restores everything on failure.
3. **Your two requirement survivors** get tests: a rostered postseason week (19) and an older season (2023).
4. **Input version `D275-v5`.** Clean output is byte-identical to D274-v4. The D274 docstring wording is corrected,
   as you noted.
5. **Tests and mutations.**
   - `test_fwd7e.py` (7 tests). Forward 305 tests on Linux 3.11 and standalone 3.13.7; usage 22.
   - Cowork's V1-V12 are killed except V4 (the week `isna` arm), which is argued equivalent: NaN != NaN already fails
     `wk != wk.round()`. V10 (ratings validating usage's directory) survived the first round and is now killed.

**Results reported.** Claude Code ran these on the Mac at Fri ~21:10-21:45Z; Cowork re-checked the committed record.
- **Tests:** forward 305 passed per file, 0 skipped; usage 22 passed, 1 deselected. Selftest ok.
- **Refresh at 21:29Z:**
  - D275-v5, fingerprint `3638769c89030de0`, freshness PASS for 32 teams.
  - **It is NOT post-final-report in data terms.** The archived `sources/injuries.parquet` sha256 (`c3f34711…`) is
    identical to the 12:29Z and 18:31Z refreshes.
  - Only CLE, PIT and WAS have game statuses; the Friday final reports are not yet in the nflverse feed.
  - Cowork re-pulled `nflreadpy.load_injuries([2026])` afterwards: still 291 week-4 rows, 9 game statuses, 3 teams.
- **On the refreshed inputs:**
  - the installed rows equal the rebuild; week-4 depth is 724/802.
  - **All six counterexamples HALT:** null week, `Int64` `<NA>` season, historical null game_id, historical null
    dates, and a date one week early and one day late.
  - The D274 controls change 1.25%, 1.25% and 100% of target shares.
  - Point-in-time is OK for W = 2-4.
  - The gate PASSes the 28 Sunday teams.
- **Runbook** matches; **smoke** 14/14 converged, read set 45 files, 0 unproven.

## A declaration for you to judge (proposed D276, to be committed before any Sunday outcome)

D272 (ii) says Out/Doubtful from the FINAL injury report are applied. That is only true if the feed carries the final
report when the window freezes. Proposed rule:
- At the window's final refresh, count the window's teams whose week-4 injury report has at least one game status
  (`injury_game_statuses > 0`).
- If fewer than 3/4 of them have one, the final report is not in the feed, and that window runs as a declared
  **pilot**, never promoted. (For the 13-game main + SNF window that means at least 20 of 26 teams; for the
  single-game IND@WAS window, both teams.)
- The count is taken and committed BEFORE the window's harness start.

Judge:
- whether the threshold is sound (every team listing at least one designated player on a final report is the norm,
  but not guaranteed);
- whether a per-window rule is better than a slate rule;
- whether a different evidence source is better (for example the feed's own timestamps).

## P1: decides GO or NO-GO for a primary Sunday

1. **Baseline.** The forward files, each separately, and the four usage files with `--tune` deselected.
2. **Your A1 counterexamples on the pinned code.** Each must HALT before any table write, with the refresh restoring
   all eight tables:
   - the one-row null week;
   - the `Int64` `<NA>` season;
   - the historical null game_id.
   Repeat your IND@WAS worker comparison as a negative control on `2afe33878`.
3. **Variants.** Each must HALT:
   - a blank game_id;
   - a week of 2.5, 0 or 23;
   - season as a string;
   - game_id as an empty string inside an otherwise valid game;
   - a bad row in a season outside the built ones (e.g. 2020), through both `usage.load_pbp` and
     `ratings.load_all_pbp`.
   Confirm that clean `Int64`/float identity columns still pass and produce byte-identical output.
4. **Clean identity.** On the D275-v5 archive (`…/20261002T212948Z/refreshed`), the installed tables must equal an
   independent rebuild, and D275 must equal D274 for both full tables. Point-in-time must hold for W = 2-4.
5. **Smoke and procedure.**
   - Check the saved smoke artifact, and run one independent IND@WAS bootstrap dry run.
   - Judge the proposed D276 rule above.
   - Confirm the remaining operational prerequisites: a refresh once the feed carries the final reports, and the
     Sunday-morning refresh finished by 12:15Z.

## P2: if time remains

6. Re-run V1-V12 (operators at the end of D275), each isolated and re-stamped, and try to break V4. Look for any
   other aggregation key whose missing value a builder silently drops: `posteam`, `play_type`, player IDs. Judge
   which of those are legitimately null in real PBP.
7. Look for any remaining way for a bad input to reach the worker past the gate, or for a value other than the
   worker's to reach a primary frozen file. The D269 L4 native-I/O boundary is out of scope.

## Reply format

Use:
- **(A)** must-fix before a primary Sunday (ranked, file:line);
- **(B)** the P1 table;
- **(C)** P2 and any bypasses;
- **(D)** survivors;
- **(E)** GO or NO-GO for a primary Sunday at this pin, per window (IND@WAS; main + SNF), including your judgment of
  D276.

Distinguish what you executed from what you read in the source. Write nothing else to the repository.
