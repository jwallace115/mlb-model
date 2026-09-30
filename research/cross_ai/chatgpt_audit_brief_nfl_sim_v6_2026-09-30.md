# ChatGPT audit brief #7 (v6) — re-audit of the forward experiment before its first live freeze (2026-09-30)

This is a read-only audit, and a follow-up to your audit #6 on `145a1fee0`, whose findings were A1-A7 and Q1-Q9. Cowork
adjudicated every one of them and accepted them (`research/cross_ai/chatgpt_audit6_adjudication_2026-09-29.md`,
D223). Four fix orders followed: FWD2, FWD2b, FWD2c and the item-0 re-work. Cowork verified each round and rejected the
first three. **Posture: guilty until proven innocent**, including for the verifier: Cowork's acceptance note D238
already contains at least one claim that is false (see §3).

**Repo:** `jwallace115/mlb-model` (public). **Pin: `main` @ `0792fd122`.** That is the merge of eng/fwd2 (`8ff8770b1`)
plus the refreshed week-4 rating inputs. Later "auto:" commits do not touch `nfl/`.

**Deadline.** The first live freeze of experiment `nfl_fwd_v1` (reader `nfl_sim_v1_156cd057`) is the week-4 TNF run:
**Thu 2026-10-01 23:30Z**, PIT@CLE kicking 10-02 00:15Z.
- Code that the experiment manifest hashes cannot change after that run without declaring a new version.
- Findings that must change hashed code are therefore only useful **before about Thu 15:00Z**.
- The hashed code includes `log_ai_opinions.py`, which holds the scoring.

## 1. What is on main now (claims — verify them)

- **Decisions D223-D238**, in `research/nfl_sim/NFL_SIM_DECISION_v1.md`. The verification notes are in
  `research/nfl_sim/`:
  - `fwd2_item0_check_2026-09-30.md`;
  - `fwd2_verification_2026-09-30.md` (D228);
  - `fwd2b_verification_…` (D233);
  - `fwd2c_verification_…` (D238).
- **Experiment identity:** `research/nfl_sim/FWD_EXPERIMENT_v1.json`. It holds the hashes of 42 files and the usage
  fingerprint, plus the eligibility, settlement and scoring rules as text. The harness halts on any mismatch
  (`nfl/sim/run_forward_v1.py`).
- **The harness** (`run_forward_v1.py`, `main(argv, root, run_week_fn)`) runs these steps in order:
  1. test_freeze_v1, the manifest, the calibration stamp and the usage fingerprint;
  2. `build_bundle` at cutoff T (`nfl/data/board/week=2026_WW/sim_runs/<run_id>/`: events, props, lines,
     freshness, sha256 manifest), with a quote age of at most 3 h and fresh ratings (at least W−1);
  3. an in-process `build_sheet` from the bundle;
  4. run_week, using `--lines-json`/`--games` from the bundle;
  5. `fill_sheet` keyed on (game_id, player, market, line) and side;
  6. price and source_utc validation against the bundle sheet;
  7. the anchor sidecar, built from the lines used, before the freeze;
  8. an in-process `freeze()`, with cross-week refusal for the canonical reader and a canonicalized reader string;
  9. publication time, which must be before the first kick.
- **Settlement** (`nfl/pipeline/log_ai_opinions.py`):
  - participation from nflreadpy `load_snap_counts`, matched by GSIS→PFR id;
  - no snap data → unresolved;
  - no "END GAME" row → unresolved.
- **Scoring:** `score-experiment`, using `primary_cohort` and `primary_statistic`. The statistic is
  Δ = mean[(p−y)² − (q−y)²], with a 50,000-resample whole-game bootstrap and seed 20261004. P2 is on |p−q| > 0.08.
- **Tests:**
  - `nfl/sim/tests/test_fwd2*_*.py`;
  - `test_forward_v1.py`;
  - `test_freeze_v1.py`;
  - the live test `test_live_freeze_no_pilot` (no --pilot, no --as-of).

  Cowork ran 55 of them on Linux and they passed.
- **Real runs** (on the owner's Mac; the outputs are pasted in D231/D234 and in §4):
  - a week-3 pilot freeze (14 games, 162 matched, 0 unanchored);
  - a week-4 live dry run: PIT@CLE, 70 lines, 43 two-way, 11 matched (9 receptions and 2 rush attempts), anchored
    −2.408 / 38.137 against −2.5 / 38.0.

## 2. What we need from you

**R1 — Re-test every audit-#6 finding against the fix.** For each of A1-A7, rerun your original counterexample, or a
stronger one, on `0792fd122`, and mark it FIXED, PARTIAL or NOT FIXED with file:line:

| Finding | Subject |
|---|---|
| A1 | scoring population |
| A2 | one immutable bundle; game lines capped at T |
| A3 | full identity and a halting calibration/usage check |
| A4 | no second "first opinion" (whitespace, another week directory, another reader string) |
| A5 | event and player identity in matching; props loader books |
| A6 | anchor targets and the returned iteration |
| A7 | settlement: exact event, completed game, participation, void |

**R2 — What could invalidate Thursday's freeze?** Walk one live run end to end at the pin (the TNF command is
`python3 nfl/sim/run_forward_v1.py --week 4 --window-hours 2`, run at about 23:30Z Thu). List anything that would:
- freeze a wrong or stale price;
- freeze a probability from the wrong game or market;
- let later information in;
- fail to halt when it should;
- halt when it should not;
- or make the frozen record impossible to reproduce later: the bundle contents, run_id on rows, what is and is not
  committed, and gitignored inputs (ratings, PBP, snap counts).

**R3 — Scoring before the first grading.** Read `score_experiment`, `primary_cohort`, `primary_statistic`, `score`,
`_first_side_won`, `_load_snap_participants` and the crosswalk. Cowork has already found one defect it missed in D238,
in §3. Find the others.

**R4 — Tests.** Which tests would still pass if the property they claim to protect were broken? Give one mutation per
test file that survives.

**R5 — Verdict.** Is the experiment valid to start at Thursday's TNF window? If not, what is the minimum set of
changes, ranked, with file:line, that makes it valid? Name them so that they can be done and verified before about
Thu 15:00Z.

## 3. Defects the verifier already knows about (confirm, size, or refute)

1. **The sidecar join by run_id is not implemented.**
   - `score_experiment` builds the sidecar frame and then has `if "run_id" in pooled.columns ...: pass` /
     `elif ...: pass`, so it joins nothing.
   - `primary_cohort` builds the anchored set from the `game` column pooled across ALL runs and weeks. It silently
     treats every game as anchored when the sidecar frame is empty.
   - The order required a join by run_id + event and a HALT when a cohort row has no sidecar.
   - **D238 accepted this without noticing.**
2. **`bundle_manifest.json` is rewritten after the freeze** to add `publication_utc` (run_forward_v1.py:~640). So the
   manifest file inside the "immutable" bundle changes after its hashes were written.
3. **The Sunday runbook is wrong.** `research/nfl_sim/make_runbook.py` uses the VM props slots on every day of the
   week, and merges London with the main slate into one 12 h run. A fix order (FWD2d) is written, and those files are
   not experiment-hashed.
4. **The freshness check reports kickers as "missing".** It looks for `kicker_ratings.parquet`; the file is
   `kicker_weekly.parquet`, which has 2026 rows through week 3. Cosmetic.
5. **run_week's props loader still uses tag precedence** (close > mid > open) for the rungs it prices. The frozen
   prices come from the bundle, so this affects coverage only. Is that true?

## 4. Numbers you can check

- The week-3 AI blind-log re-grade under the new settlement: 2,025 settled, 40 VOID, 5 unresolved (D236).
- The week-3 sim pilot diagnostic: Δ = +0.0148 on 162 legs, 95% CI (−0.0039, +0.0341), P2 +2.26 units (D236).

  The pilot file from FWD2b may not be committed. If it is not reproducible from the pin, say so. Cowork's earlier
  FWD1b pilot (committed, 174 legs) gave +0.0157, and you confirmed that.
- The week-4 dry-run anchor: target −2.5 / 38.0, anchored −2.408 / 38.137, 3 iterations.

A reply is most useful as:
- **(A)** the must-fix list before Thu 15:00Z, ranked, with file:line;
- **(B)** R1 as a table, A1-A7 each FIXED, PARTIAL or NOT FIXED, with the evidence;
- **(C)** §3 items confirmed, sized or refuted;
- **(D)** surviving test mutations;
- **(E)** one paragraph: start Thursday or not.
