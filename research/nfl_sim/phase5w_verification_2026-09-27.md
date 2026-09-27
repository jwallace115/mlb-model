# Phase 5W verification — Cowork, 2026-09-27

Branch `eng/5w` @ `4728337` (base = the 5V merge). Verified in a Linux worktree. Targeted checks only (no full
suite re-run): the numbers the decisions rest on were recomputed, the log's test and the hash test were run.

## Item 0 (D163) — accepted
`compute_k1_actuals()` prints drives 21.74 on Linux, same as the Mac now; D159's 21.92 was a typed number.
Row counts pinned (1,087 games / 136,727 plays / 23,635 drives). Plays 125.78 unchanged.

## Item 1 (D164) — the log is right; the diagnosis of its failing test is wrong
- One row per clock-consuming event at all nine `ev_clock_used` sites, with class, score state, clock period and
  pace multiplier. Player-OFF hash `afdb11999d5b12bf` for `e00483d173495210` (hash test passes on Linux). The
  quarter-sum test fails, as reported (39.8 s off in the first failing sim here), and was NOT weakened. Good.
- D164 says the fix is to log a boundary-crossing play as two rows. That would make the test pass and hide an
  ENGINE behaviour: at the end of a quarter the engine keeps the overshoot (`clock += 900`, "carry over negative
  clock so time isn't lost"), so the next quarter really starts short. Measured here on the D144 sample
  (200 games x 100): Q2 starts on average **19.9 s short, Q3 9.8 s** (across halftime), **Q4 19.8 s** — about
  **50 s of game clock a game that real games do not lose** (a real quarter restarts at 15:00; the runoff table's
  real elapsed for a last-second snap is capped by the time left). Fixing it gives the sim MORE time (~+1.7
  plays): the right correction, in the wrong direction for the gap.
- Also noted: D163-D165 were inserted ABOVE D162 in the decision doc; order is cosmetic, content is intact.

## Item 2 (D165) — the headline reproduces, the mechanism it names does not
- By-margin table accepted (sim ~129-131 flat, real 127.4 -> 122.7; gap +3.9 -> +8.4).
- The sim side of prediction (2) was not measured: "sim lead-9+ elapsed 29.08 s (from 5V)" comes from 5V's
  rejected log, and sim run share was never computed although the new log has the class. The report's
  diagnosis ("the sim does NOT increase its run share when leading") is therefore an assertion.
- **Cowork measured it (pre-registered at 01:00:29Z, before the run)** on the D144 sample with the 5W log (a
  local, uncommitted tag separating rush-site from pass-site events):

| offence state | sim snaps/g | real snaps/g | sim run share | real run share | sim s/snap | real s/snap |
|---|---|---|---|---|---|---|
| lead 9+ | 17.8 | 16.8 | 53.8% | 53.2% | 29.8 | 33.1 |
| lead 1-8 | 25.5 | 23.4 | 46.1% | 46.0% | 29.6 | 31.2 |
| tied | 22.4 | 22.9 | 44.5% | 44.6% | 31.3 | 32.1 |
| trail 1-8 | 31.1 | 28.7 | 40.7% | 40.0% | 28.9 | 30.0 |
| trail 9+ | 23.9 | 25.7 | 31.6% | 29.8% | 25.5 | 26.1 |

  (non-scoring, non-turnover scrimmage snaps; real = time to the next scrimmage snap, capped at quarter end —
  the runoff table's own definition.)
  P1 (sim run share leading 9+ >= 5 pts below real) **FAILED** — play calling by state is right to within 1-2
  points everywhere. P2 (sim leads-9+ snaps >= 2 over real) **FAILED** (+1.0). P3 (>= 10 s/game carried across
  quarter ends) **HELD** (~50 s). What is wrong is the **time per snap**: short in every state, worst when
  leading (-3.3 s at 9+, -1.7 s at 1-8).
- By class (first 100 K1 games): the sim's **rushing first downs run 32.6 s vs 37.0 s real** (leading 9+: 33.1 vs
  **42.9**). The runoff table has ONE `first_down` outcome type pooling rush and pass first downs; pass first
  downs stop more often (27% out of bounds vs 12%) and run shorter, so every rushing first down in the sim gets
  pass-contaminated runoff: about -48 s a game at ~11 rushing first downs. Everything else is close
  (run 36.9/36.6, complete 36.0/35.6, incomplete 8.1/8.0); pass first downs 31.0 vs 32.7 is a smaller second
  effect. The sim's "incomplete"-class runs (1.5/g) are runs followed by a timeout (`_apply_timeouts`
  stop_code), not a defect — a like-for-like check needs a timeout class on the real side too.
- Caveat on the sample: the D144 sample is the first 200 games by game_id, i.e. 2021 weeks 1-13, where the K1
  plays gap is smallest (+3.9; 2024 is +6.9). Class counts on the first 100 games match real within ~1 snap. The
  next order uses a season-stratified sample.

## Verdict
Items 0-1 accepted (log instrumentation, targets). Item 2's table stands; its mechanism is replaced by the
measurement above. Two engine defects are now concrete and small: the quarter-boundary overshoot (~50 s a game
too little time) and the pooled first-down runoff (~48 s a game too much time). They roughly cancel — fixing
both is correct and is expected to leave the plays gap about where it is, which is the honest prediction for 5X.
