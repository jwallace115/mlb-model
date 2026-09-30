# FWD2c verification — Cowork, 2026-09-30 (10:30Z)

Branch `eng/fwd2` @ `bcbd8f494` (D233 append; D234-D237). Read from the committed code, in a clean worktree on Linux.
**55 tests pass here.** A dry merge into main @ 5aeaeb519+ is clean.
**Verdict: accepted and merged.** The week-4 TNF window (PIT@CLE, Fri 10-02 00:15Z) is the **first primary window** of
experiment `nfl_fwd_v1`, reader `nfl_sim_v1_156cd057`. That holds provided the pre-run steps below are done on
~/mlb-model and the TNF dry run completes. The Sunday part of the runbook is wrong; FWD2d fixes it before Sunday.

## What stands (checked in the code)
- **Live mode is proven.** `test_live_freeze_no_pilot` (test_fwd2b_harness.py:211) calls `main(["--week","3"])` with
  no `--pilot` and no `--as-of`, on a fixture root with kick = now+2 h and the pull 30 min old. It freezes rows with
  pilot=False and the canonical reader, and prices equal to the bundle. A 4 h-old pull HALTs with nothing frozen.
- **A real week-4 live dry run completed** (D234): PIT@CLE, 67 lines, 11 matched, 0 unanchored.
- **Params are safe.** `ratings.py` writes `params_v1.json` only with `--write-params` (ratings.py:936-943).
- **Settlement**, for every reader:
  - participation by GSIS→PFR id against the nflverse snap counts;
  - no snap data → unresolved;
  - no END GAME row → unresolved;
  - the week-3 re-grade now settles 2,025 rows, with 40 VOID and 5 unresolved (it was 0 of 2,070).
- **The diagnostic on the week-3 pilot:** Δ = +0.0148 on 162 legs, 95% CI −0.0039 to +0.0341, P2 +2.26 units. Cowork's
  FWD1b figure on the older 174-leg pilot was +0.0157. The direction and size agree.
- **FWD_EXPERIMENT_v1.json** is re-stamped last.
- **The ChatGPT audit's A1-A7 are all addressed in code:**

  | Finding | Addressed by |
  |---|---|
  | A1 cohort | `score-experiment` |
  | A2 | one bundle at T |
  | A3 | manifest, stamp and usage HALTs |
  | A4 | canonical reader, cross-week refusal in `freeze()` |
  | A5 | event-keyed matching |
  | A6 | sidecar targets from the lines used |
  | A7 | settlement by id, void/unresolved, completed game |

## What does not (does not block TNF; blocks Sunday)
1. **`make_runbook.py` ignores the day of the week for VM props slots** (`VM_SLOTS = [2,14,15,16,22,23.75]`, every
   day). The deployed schedule is day-specific:
   - Tue 14:00 open;
   - Wed-Sat 14:00 and Tue-Sat 02:00 mid;
   - Thu 22:00 (TNF);
   - Sun 15:00 and 16:00 close;
   - Mon 23:45 (MNF).

   So TNF reads "23:45Z Thu" when it is really 22:00Z. That is still under 3 h at a 23:30Z run, so it is harmless.
2. **Sunday is merged into one window** (`--window-hours 12`, run 13:11Z) covering London and every 1 pm, 4 pm and SNF
   game. The only fresh pull before 13:11Z would be the manual London pull (window 2 h), so the other 13 games would
   HALT on quote age. Or, with a 12 h manual pull, they would freeze at 9 am ET, before inactives. It must be two runs:
   - London alone (about 12:45Z, after a manual pull);
   - the main slate (about 16:15Z, after the VM 16:00Z pull).
3. **The runbook's refresh block still says "ratings.py overwrites params_v1.json".** That is stale since D235.
4. **The latest safe start "00:02Z" for TNF** counts a 9-minute refresh that is weekly, not per window, and leaves 13
   minutes. Run at 23:30Z.
5. **Open, affects coverage only:** run_week's props loader (the rungs it prices) still reads the tape by tag
   precedence. The frozen prices come from the bundle, so correctness is unaffected.

### D238 — Cowork verification of FWD2c: accepted and merged; the primary forward count of nfl_fwd_v1 starts at week-4 TNF (2026-09-30)

FWD2c (eng/fwd2 @ bcbd8f494) is accepted, and eng/fwd2 (D223-D237) is merged to main.

What was verified:
- A true live test (no --pilot, no --as-of) completes a freeze with canonical rows and bundle prices.
- A real week-4 live dry run completed.
- params_v1.json is written only with --write-params.
- Settlement uses snap counts by GSIS→PFR id, with unresolved for missing snaps or an incomplete game.
- The week-3 re-grade settles 2,025 rows.
- The pilot diagnostic gives Δ +0.0148 (n=162; CI −0.0039 to +0.0341).
- 55 tests pass on Linux.

The ChatGPT audit's A1-A7 are addressed.

The primary count of experiment nfl_fwd_v1 (reader nfl_sim_v1_156cd057, FREEZE_v1 physics) starts at the week-4 TNF
window: PIT@CLE, run at 23:30Z Thu 10-01. Before it:
- inputs are refreshed once on ~/mlb-model;
- test_freeze_v1 passes;
- a TNF dry run completes.

Open before Sunday (FWD2d):
- make_runbook.py's day-specific VM slots;
- splitting London (manual pull, about 12:45Z) from the main slate (about 16:15Z);
- the stale refresh note.

run_week's tag-precedence props loader affects coverage only.
