# Work order FWD1b — fix the forward harness, fix the week labels, run the week-3 pilot (2026-09-29)

Written by Cowork after verifying FWD1 (`fwd1_verification_2026-09-29.md`, D213). eng/fwd1 is NOT merged; FWD1b
continues on it. **Deadline: Cowork must verify this before the week-4 TNF kick, Fri 2026-10-02 00:15Z** (Thu 8:15 pm
ET). No engine change: FREEZE_v1 must stay green.

Pre-check (Cowork):
- **Runtime.**
  - Items 0, 1 and 3 are code, tests and file moves: minutes.
  - Item 2:
    - PBP refresh with the existing `nfl/pipeline/pull_pbp.py`: seconds to a minute.
    - One run_week for 15 games: about 3.5 min (the week-2 log shows 209 s for 17 games at N=10,000).
    - Scoring: seconds.
  - Total well under an hour.
- **Credits.** Zero. nflverse is free, the Odds API is not called, and everything else reads the tape.
- **Paths.** All exist. `nfl/data/board/week=2026_03/` and `week=2026_04/` are tracked. The manifest is a JSON list of
  entries `{file, sha256, logged_utc, …}`.
- **The week fact.** From the `pbp_2026` game dates, nflverse week 1 = 09-09 to 09-14 and week 2 = 09-17 to 09-21.
  Week 3 is therefore 09-24 to 09-28 and week 4 is 10-01 to 10-05. The Sep 27 blind log sits in week=2026_04, which
  is wrong.
- **Week-4 kicks on the tape:**
  - TNF PIT@CLE: 10-02 00:15Z.
  - London IND@WAS: 10-04 13:30Z.
  - 1 pm games: 17:00Z.
  - Late games: 20:05 and 20:25Z.
  - SNF DET@CAR: 10-05 00:20Z.
  - MNF: not on the 09-27 snapshot yet.

```
Work order FWD1b (research/nfl_sim/workorder_FWD1b_2026-09-29.md). Continue on branch eng/fwd1 (worktree), from
origin/eng/fwd1. Gates (git fetch origin first): `git rev-parse --short=9 origin/eng/fwd1` prints 4c9802c93, and
`git show origin/main:research/nfl_sim/fwd1_verification_2026-09-29.md | grep -c "^### D213"` prints 1; if either
fails, STOP and print both. FIRST COMMIT: append the D213 block from that file VERBATIM at the end of
research/nfl_sim/NFL_SIM_DECISION_v1.md (after D212). Then items 0-3, ONE COMMIT PER ITEM, push each before the next;
decisions D214-D217 appended in the same commit as their code. Session log appended to logs/_log_fwd1.txt (git add
-f), timestamps from `date -u`. No file > 2 MB. Never weaken a test. When done, remove this order's worktree.

HARD RULES: (1) Do NOT modify any file FREEZE_v1 hashes; run test_freeze_v1 before every commit and paste the line.
(2) Every code claim cites file:line. (3) Every new test imports and calls the REAL function from
nfl/sim/run_forward_v1.py or nfl/pipeline/log_ai_opinions.py — no copies of logic in the test file — and must FAIL on
origin/eng/fwd1 @ 4c9802c93: run it there first and paste the failure. (4) No slip IDs, no raw exports from bets/.
(5) nflverse week numbers are the only week numbers; never infer a week from a folder name.

Item 0 (D214) — week labels. The files in nfl/data/board/week=2026_04/ are the Sep 27-28 slate = nflverse WEEK 3.
  Print `log_ai_opinions.py verify --week 3` and `--week 4` BEFORE. Then `git mv` every file in week=2026_04/ (the
  ai_opinions parquet, sun_cards*, sun_ticket_placements*, mnf_sgp*, mnf_script_model*) to the same name under
  week=2026_03/ (STOP if any name already exists there). Append the week-4 manifest entry to the END of
  week=2026_03/ai_opinions/manifest.json UNCHANGED (same sha256, same logged_utc) and set the week-4 manifest to [].
  No file's content changes except the two manifests. Print both verify commands AFTER: week 3 = 2 frozen files, no
  mismatch; week 4 = 0 files. List in D214 every committed doc or script that names week=2026_04 for this slate
  (grep), and change none of them — the decision records the move.

Item 1 (D215) — harness fixes, each with a test that calls the real function:
  (a) Move the fill into `fill_sheet(sheet_df, picks_log) -> DataFrame` in run_forward_v1.py; main() calls it. Match
      on (player_name, market, line), where market comes from an explicit map family -> sheet market_key
      {receptions: player_receptions, rush_attempts: player_rush_attempts}; any other family is not matched. Honour
      picks_log.side: an 'over' row gives p_first = cal_p, an 'under' row gives 1 - cal_p (the sheet's first side is
      always Over for props — log_ai_opinions.py build_sheet). More than one match for a key -> HALT, do not take the
      first. Test: a fixture where one player has rush_attempts 9.5 AND player_reception_yds 9.5 on the sheet and a
      rush_attempts 9.5 picks_log row — only the rush-attempts row gets the sim's p; a QB pass_tds 1.5 row with a
      rush_attempts 1.5 rung stays no_view; an 'under' picks_log row gives 1 - cal_p.
  (b) `anchor_sidecar(anchoring_log_df, lines) -> DataFrame` reading the REAL columns (game, iter, margin, total,
      err_m, err_t, converged). Best iteration = min |err_m| + |err_t|, the same rule run_week uses; the market spread
      and total come from the run's lines, not from defaults. A missing column raises. Test on the committed
      nfl/data/sim/outputs/week=2026_02/anchoring_log.parquet: 15 games, all anchored under the D210 rule, max
      |miss| <= 0.35.
  (c) Pass --pilot, --as-of, --window-hours and --events through to BOTH the sheet and the freeze calls (the same
      values). Test: main() with a stubbed subprocess records identical flags on both calls.
  (d) In log_ai_opinions.py newest_inputs, keep only props with pull_timestamp <= now (as well as < commence).
      Live runs are unaffected (every pull is <= now). Test: a fixture pull after now is excluded.
  (e) The halt: main() with FREEZE_v1.json pointed at a temp copy with one hash changed exits non-zero BEFORE the
      sheet step. Test it through main(), not through test_freeze_v1's functions.
  Delete the logic copy `_fill` in test_forward_v1.py; the five old tests are rewritten to call the real functions.

Item 2 (D216) — the pilot, nflverse week 3. Refresh PBP (`python3 nfl/pipeline/pull_pbp.py`, however it is invoked
  in the repo; print the weeks now present). Run `run_forward_v1.py --week 3 --pilot --as-of 2026-09-27T16:30:00+00:00`
  (TNF ATL@GB has kicked by then and is excluded by the logger). Then `log_ai_opinions.py verify --week 3` and
  `score --week 3 --include-pilot --out research/nfl_sim/fwd1_pilot_w3.md`. Deliver:
  - rows, two-way prop rows, matched rows by market (expect receptions and rush attempts only);
  - the anchor sidecar (15 games; how many unanchored);
  - Brier sim vs book de-vig with the game-cluster bootstrap interval, overall and by family;
  - the P2 units at real Hard Rock prices;
  - the reader_attribution for week 3, showing the AI log and the sim pilot are scored separately.
  This is a PILOT: never pooled, not evidence for or against P1/P2. Say so in D216.

Item 3 (D217) — the runbook, concrete for week 4 (rewrite research/nfl_sim/fwd1_runbook.md). One command per kick
  window with --week 4 and --window-hours so each run freezes ONLY its window:
  - TNF PIT@CLE: run at 23:30Z Thu 10-01, window 2 h.
  - London IND@WAS: run at 12:45Z Sun 10-04, window 1.5 h.
  - Sunday 1 pm / 4 pm / SNF: run at 16:15Z, window 9 h.
  - MNF: run at 23:30Z Mon, window 2 h.
  For each window, print the newest Hard Rock props pull the sheet will read. Name every window where the VM props
  cadence (capture_status: no Monday slots) leaves the newest pull more than 3 h old at run time. Scoring commands for
  the 500- and 1,500-leg checkpoints, pooled across weeks by reader_model nfl_sim_v1_156cd057.

Every item's report separates what the command RETURNED from what it MEANS and ends with NOT DONE and UNVERIFIED.
```
