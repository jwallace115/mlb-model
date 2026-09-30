# Work order FWD2 — make the forward experiment valid (audit #6, A1-A7) (2026-09-29)

Written by Cowork after adjudicating ChatGPT audit #6 (`research/cross_ai/chatgpt_audit6_adjudication_2026-09-29.md`,
D223). **No physics change:** every file FREEZE_v1 hashes stays byte-identical. **Target:** verified by Cowork before
the London window, 12:45Z Sun 10-04. If that is missed, the primary count starts at week 5.

Pre-check (Cowork):
- **Runtime.**
  - Items 0-3 are code and tests: an hour or two of agent time.
  - Item 1's input refresh runs the existing ratings/usage builders. Their runtime is **unknown: measure it and
    report it**. It must fit inside the gap between the props pull and kick; if it does not, say so.
  - One `--dry-run` for week 4 takes about 5 min (run_week at about 12 s a game × 16).
  - The bootstrap is 50,000 whole-game resamples on at most a few hundred legs. It must be vectorised (a per-game
    sum matrix); seconds, not minutes.
- **Credits.** Zero in this order. A Sunday pre-London props pull is about 10 credits for one event (10 books,
  measured 09-27), and Jeff runs it himself; this order only makes the bundle able to read it.
- **Paths.**
  - Existing: `nfl/sim/run_forward_v1.py`, `nfl/pipeline/log_ai_opinions.py`, `nfl/sim/run_week.py`, the manual
    props folder `data/odds_archive/nfl/props/season=2026/manual/` (09-28 precedent), and
    `nfl/data/board/week=2026_WW/ai_opinions/`.
  - New:
    - `research/nfl_sim/FWD_EXPERIMENT_v1.json`;
    - `nfl/sim/tests/test_fwd2_*.py`;
    - `nfl/data/board/week=2026_WW/sim_runs/<run_id>/`, one immutable bundle folder per run.
- **Participation data.** nflverse is free. Name the source used (snap counts or weekly roster game status) and cite
  the loader.

```
Work order FWD2 (research/nfl_sim/workorder_FWD2_2026-09-29.md). Branch eng/fwd2 from origin/main in a worktree.
Gates (git fetch origin first): `git show origin/main:research/cross_ai/chatgpt_audit6_adjudication_2026-09-29.md |
grep -c "^### D223"` prints 1, and test_freeze_v1 passes (4). FIRST COMMIT: append D223 VERBATIM from that file at the
end of research/nfl_sim/NFL_SIM_DECISION_v1.md. Then items 0-3, ONE COMMIT PER ITEM, push each before the next;
D224-D227 appended in the same commit as their code. Session log logs/_log_fwd2.txt (git add -f), timestamps from
`date -u`. Remove the worktree when done.

HARD RULES: (1) Every file FREEZE_v1 hashes stays byte-identical; test_freeze_v1 before every commit, paste it.
(2) file:line for every code claim. (3) Every new test calls the REAL function — for the harness that means main()
end to end on a fixture week directory — and FAILS on origin/main @ 145a1fee0: run it there first, paste the failure.
(4) Never edit or re-hash an existing frozen opinion file or manifest entry. (5) nflverse weeks only. (6) The audit's
counterexamples (research/cross_ai/chatgpt_audit6_adjudication_2026-09-29.md, table A1-A7) each become a test.

Item 0 (D224) — experiment identity (A3, A4).
  (a) research/nfl_sim/FWD_EXPERIMENT_v1.json: experiment id "nfl_fwd_v1"; canonical reader "nfl_sim_v1_156cd057";
      sha256 of every file on the live prediction and scoring path — engine.py, anchor.py, params_v1.json,
      calibration_v1.json, tables/*, run_week.py, names.py, calibration.py, tables.py, seed_util.py, usage.py,
      ratings.py, run_forward_v1.py, log_ai_opinions.py — plus the recorded usage_fingerprint, the python/numpy/
      pandas versions, N and seed rules, the eligible markets, and the eligibility, settlement and scoring rules
      (item 3) as text. A test recomputes every entry and fails on any change, INCLUDING the usage fingerprint
      (reproduce the audit's counterexample: one historical target-share value changed -> the test fails).
      Changing any hashed file = a declared amendment (FWD_EXPERIMENT_v2), never silently the same experiment.
  (b) The harness HALTs (non-zero, before anything is frozen) on: an experiment-manifest mismatch, a calibration-stamp
      mismatch (run_week.py:502-507 currently only suppresses ranking), or zero sim matches.
  (c) The reader string is canonicalized (strip; exact match to the manifest) BEFORE the revision lookup
      (log_ai_opinions.py:249/287). For reader nfl_sim_v1_156cd057, non-pilot, a contract (event_id, market, player,
      line) already frozen in ANY week directory is refused, not stored as revision 1; corrections go to a separate
      amendments file that scoring never reads. Tests: whitespace reader -> refused; a second freeze of the same
      contract in another week directory -> refused.

Item 1 (D225) — one immutable run bundle at cutoff T (A2, A5, Q2, Q7).
  At the start of each run fix T = now (or --as-of in a pilot) and a run_id. Build ONCE, and write to
  week=2026_WW/sim_runs/<run_id>/ with a sha256 manifest:
  - the event list for the window;
  - Hard Rock props per event — newest pull <= T from the monthly archive AND manual/, Hard Rock rows only;
  - Hard Rock game lines — newest snapshot <= T (fixes newest_inputs, which takes the newest file regardless of now);
  - the input freshness table.
  Every later step reads the bundle:
  - the sheet and freeze() take the bundle's quotes, and freeze() must not rebuild them;
  - run_week gets --as-of T and ONLY the window's events;
  - validate() compares the filled sheet's prices and source_utc to the bundle's, and any difference HALTs.
  Record publication time (freeze wall-clock) separately from T; HALT if publication >= the first kick in the window.
  Quote-age rule: HALT if any event's newest props pull is older than 3 h at T (a pilot may override with an explicit
  flag, recorded in the bundle).
  Input freshness: before the sim, run the existing ratings/usage/tendency builders for the week (measure the runtime);
  print the max week of team ratings, tendencies, usage and kickers. HALT unless each is >= W-1, or is an explicitly
  listed documented fallback (e.g. kickers with no 2026 rows -> engine default; write it into the bundle).
  Matching (fill_sheet): key = (event: away@home abbreviations from the bundle, player_id resolved with names.py for
  that event's teams, market, line). picks_log must carry game_id and player_id; a probability from another event can
  never match — test with the audit's week-2-into-week-4 counterexample. run_week's props loader: Hard Rock only,
  newest pull <= T, no tag precedence.
  Print coverage: sheet two-way props / matched / by market.

Item 2 (D226) — the anchor record (A6). run_anchored_chunked's RETURNED iteration and the actual market targets from
  the lines used (not reconstructed; the current sidecar has the sign wrong: CAR@ATL -3.0/43.5 came out
  -3.2572/43.9996) go into the bundle BEFORE the freeze: game, target spread, target total, returned mean margin and
  total, iteration, converged, anchored (D210 rule, 1.0). The sidecar becomes mandatory; the freeze HALTs without it.
  Test on the committed week=2026_02 anchoring log: CAR@ATL targets equal -3.0/43.5 exactly.

Item 3 (D227) — eligibility, settlement, scoring (A1, A7, Q3). All in log_ai_opinions.py, applied to every reader.
  Settlement (every reader):
  - the exact game, by event_id -> game_id, never a team pair;
  - the game completed (final in the PBP/schedule), otherwise unresolved;
  - player participation from the named nflverse source: a player who did not play -> VOID (Hard Rock's rule), not 0;
  - missing data -> unresolved, never a loss.
  Test: an inactive player's Under is VOID.
  Primary cohort for the experiment (one predicate, one function):
  - reader == canonical, non-pilot, first freeze of the contract;
  - tag sim_v1, two_way, market in {player_receptions, player_rush_attempts};
  - game anchored per the bundle;
  - settled (not void or unresolved).
  Report every exclusion by reason.
  Primary statistic: Δ = mean[(p−y)² − (q−y)²], with q = the bundle's de-vig. Whole-game bootstrap, 50,000
  resamples, seed 20261004, leg-weighted within a resampled game set. Report n legs, n games, Δ, the 95% interval,
  and verdict = superior / inferior / inconclusive.
  Secondary P2: units at the frozen Hard Rock price on |p−q| > 0.08, settled only, game-bootstrap interval.
  Breakouts: family, week, gap bucket, anchor status (reported, not in the cohort).
  500 legs is descriptive; 1,500 is the one confirmatory checkpoint, evaluated after the game or window that crosses
  it.
  The report prints the cohort predicate verbatim. Tests reproduce the audit's counterexample (another reader and an
  unanchored game must NOT enter the cohort).
  Then re-grade the AI blind-log weeks 2-3 under the new settlement rule, and report old vs new units and Brier per
  file (reporting only — frozen files are untouched).
  Finally rewrite research/nfl_sim/fwd1_runbook.md for weeks 4-5, with correct weekday labels (SNF Mon 10-05 00:20Z,
  MNF Tue 10-06 00:15Z). London needs a Sunday pull before 12:45Z: give Jeff's exact command, writing to manual/, and
  its credit cost. Then run one `--dry-run --week 4` end to end on the new path and paste the bundle manifest,
  freshness table, coverage and sidecar.

Every item's report separates what the command RETURNED from what it MEANS and ends with NOT DONE and UNVERIFIED.
```
