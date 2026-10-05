# ChatGPT audit brief #17 (v16): FWD7d (D274), for a primary Sunday week 4 (2026-10-02)

Your audit #16 of `9c7bf9dfa` (NO-GO for both primary Sunday windows) is at
`~/mlb-model/research/cross_ai/chatgpt_audit16_reply_2026-10-02.md`. Cowork accepted it in **D274**
(`research/nfl_sim/NFL_SIM_DECISION_v1.md`). Read D274 in full first. Cowork then implemented **FWD7d**. Posture:
guilty until proven innocent.

**Pin: `2afe33878` on branch `eng/fwd6`** ("FWD7d Mac run: …"). Below it, in order:
- `e93dc3da9`: the refreshed tables under 2 MB;
- `b9bae4830`: FWD7d, D274 (code, tests, D274);
- `9c7bf9dfa`: the pin of your audit #16.

The code at `b9bae4830` is byte-identical to the tree Cowork tested (Cowork re-checked it from GitHub). The Mac run's
full output is in `research/nfl_sim/fwd7d_mac_run.md`. Put the full SHA you audit on line 2.

**The real constraint:** the first Sunday window, IND@WAS: manual props pull at 12:15Z and harness at 12:45Z on
2026-10-04. The main + SNF harness is at 16:15Z. Nothing else is a deadline.

## How to work

1. **Create the reply file first.** Write `research/cross_ai/chatgpt_audit17_reply_2026-10-02.md` in `~/mlb-model`
   with line 1 a title, line 2 the SHA, and INCOMPLETE. Rewrite it after every check.
2. **Each command must finish in under 10 minutes.** For long jobs, use `nohup … &` and poll the logs.
3. **If a tool is blocked, say which check it blocked and move on.**

## What FWD7d claims (verify each)

1. **Your A1 (historical cutoffs).**
   - `usage._pbp_game_dates` validates EVERY season's PBP. Every row needs a valid game_date, each game_id exactly
     one date and one week, and every row the file's season. Anything else HALTs.
   - `build_active_universe` requires a valid cutoff for every season-week it builds, not only the newest season's.
     A roster week that the PBP lacks also HALTs.
   - The carry-forward rows are added after this check, by their explicit rule.
2. **Your A2 (contradictions).**
   - For a season with a snapshot, every PBP game must be in the snapshot with the same week and date, compared by
     game_id. Otherwise the build HALTs: earlier, later, missing, or a different week.
   - The cutoff is the earliest snapshot gameday of the week, so a partly played week is not rejected, and the live
     and rebuilt weeks agree by rule.
3. **On valid inputs nothing changes.**
   - D274's clean build is byte-identical to D273's on Cowork's staged inputs.
   - Real PBP for 2020-2026 has 0 null dates, 0 games with two dates or weeks, and 0 snapshot contradictions.
4. **Smaller items.**
   - Input version `D274-v4`.
   - The refresh docstring's last sentence is fixed.
   - 5J-2's QB-cutoff test owns its fixture: PBP weeks 1-3 and a full snapshot. It passes on D274 and fails on D271.
   - Your N1-N4 survivors are killed. The test_fwd7c null-date tests now expect a HALT.
   - Cowork's T1-T14 mutations are all killed except T7 (the "missing from snapshot" arm). T7 is argued equivalent,
     because NaN snapshot week and date already fail the week and date comparisons. Challenge it.
   - Two of Cowork's numbers were wrong, as you noted: PIT/CLE `_last_played_weeks(pbp, 4)` = 3, and "35.3%" was a
     different comparison.

**Results reported.** Claude Code ran these on the Mac at Fri 18:31-18:50Z; Cowork re-checked the committed record.
- **Tests:** forward 298 passed per file, 0 skipped (also 298 on Linux 3.11 and standalone 3.13.7); usage 22 passed,
  1 deselected. Selftest ok.
- **Refresh at 18:31Z:**
  - backup `~/mlb-model-archive/nfl_ratings_backups/20261002T183144Z`, archived as `D274-v4`;
  - fingerprint `3638769c89030de0`;
  - freshness PASS for 32 teams.
  - **This was NOT the post-final-report refresh.** injury_game_statuses is 0 for every team except CLE, PIT and
    WAS. The Friday reports were not yet in, and the run note's "post-report" label is wrong. Another refresh is
    planned after the final reports and again Sunday morning.
- **On the refreshed inputs:**
  - the installed rows equal the rebuild; week-4 depth is 724/802 non-null.
  - **All three counterexamples HALT:** 2025 week-3 null dates, a week-5 game dated a week early, and the same game a
    day late.
  - **D273 controls:**
    - `hist_null` builds and changes 100% of 2026 target shares.
    - `conflict_early` builds UNCHANGED. On these inputs the target is week 5, whose rows are carry-forward copies,
      so the moved cutoff touches nothing consumed. The control is vacuous here.
    - Cowork's pre-TNF control (week 4, PBP weeks 1-3) changes 10% of target shares and 5.4% of depths under D273.
    - Your own DEN@SF case is the discriminating one, so P1.2 repeats it.
  - Point-in-time is OK for W = 2, 3 and 4 in both tables.
  - The gate PASSes the 28 Sunday teams.
  - Spot-check: 5 players match the PBP. 291 injury rows; 7 Out/Doubtful; 2 skill players, both inactive.
  - The runbook matches.
  - Sunday smoke: 14/14 converged, read set 45 files, 0 unproven, 66/257 matched.

## P1: decides GO or NO-GO for a primary Sunday

1. **Baseline.** The forward files, each separately, and the four usage files with `--tune` deselected:
   `nohup sh -c 'for f in $(ls nfl/sim/tests/test_fwd*.py) nfl/sim/tests/test_forward_v1.py nfl/sim/tests/test_freeze_v1.py; do python3 -m pytest -q -p no:cacheprovider "$f" > /private/tmp/a17-$(basename $f .py).txt 2>&1; echo "$f $?" >> /private/tmp/a17-index.txt; done' > /dev/null 2>&1 &`
2. **Your two audit-16 counterexamples, on the pinned code, in the shapes you used.**
   - Historical null dates in the ordinary multi-season build.
   - The PIT@CLE row dated 2026-09-30 on the D272-v2 archive (PBP weeks 1-3).
   Each must HALT before any table is written. Confirm the refresh restores the previous tables when its usage step
   HALTs. Repeat your real-worker comparisons as negative controls on 9c7bf9dfa, to show they still discriminate.
3. **Variants.** Each must HALT, or leave the clean result byte-identical:
   - a partially null historical game;
   - a game with two dates;
   - a PBP row with the wrong season;
   - a snapshot game in a different week;
   - a PBP game missing from the snapshot;
   - a week with only later games in the PBP (must NOT HALT, and its cutoff must equal the live cutoff);
   - schedule-only versus schedule-plus-PBP for week 4 on the current inputs (identical rows and QB maps).
4. **Clean identity.** On the D274-v4 archive (`…/20261002T183144Z/refreshed`), the installed tables must equal an
   independent rebuild. D274 and D273 clean builds must be byte-identical for both full tables. Point-in-time must
   hold for W = 2-4, including the layer-3 QB maps.
5. **Smoke and procedure.** Check the saved smoke artifact, and run one independent IND@WAS bootstrap dry run.
   Confirm the runbook, the quote-age arithmetic and the refresh deadlines. The remaining refreshes are after Friday's
   final reports, then Sunday morning finished by 12:15Z; judge them as operational prerequisites.

## P2: if time remains

6. Re-run your audit-16 N1-N4 and Cowork's T1-T14 (operators at the end of D274), each isolated and re-stamped. Try
   to break the T7 equivalence. Look for new survivors in `_pbp_game_dates`, the snapshot comparison and the
   every-season requirement.
7. Look for any remaining way for a bad input to reach the worker past the gate, or for a value other than the
   worker's to reach a primary frozen file. The D269 L4 native-I/O boundary is out of scope.

## Reply format

Use:
- **(A)** must-fix before a primary Sunday (ranked, file:line);
- **(B)** the P1 table;
- **(C)** P2 and any bypasses;
- **(D)** survivors;
- **(E)** GO or NO-GO for a primary Sunday at this pin, per window (IND@WAS; main + SNF).

Distinguish what you executed from what you read in the source. Write nothing else to the repository.
