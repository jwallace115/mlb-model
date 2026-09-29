NHL SIM — WORK ORDER S2: repair the state timeline and the league constants before any ratings are built
(written 2026-09-29 by Cowork after verifying S-WO1 from the files). Repo ~/mlb-model.

Read first: CLAUDE.md (WORK ORDERS — especially "A diff is not evidence that code runs" and "Measure, do not
assume"), research/nhl_sim/NHL_SIM_DECISION_v1.md (S1-S6), and — from main, since they were committed there —
`git show origin/main:research/nhl_sim/nhl_sim_s1_verification_2026-09-29.md` (the seven defects this order fixes;
read the code lines it quotes) and `git show origin/main:research/nhl_sim/workorder_S2_2026-09-29.md` (this order).

SETUP
- Continue on branch nhl/sim-s1 in the existing worktree ~/mlb-model-nhlsim1 (`git pull --rebase` first). Touch only
  nhl/sim/, nhl/sim/tests/, nhl/data/sim/, research/nhl_sim/. Commit AND push each item before the next.
- Each item appends its `### S<n>` entry at the END of research/nhl_sim/NHL_SIM_DECISION_v1.md in the same commit
  (expected S7, S8, S9). Do not edit S3-S6; S7 states which of their claims were wrong.
- Tests import production code, use fixtures cut from REAL play-by-play, and every new test must FAIL on the
  S-WO1 code (run it at commit 025494252 and report the failure). Pre-registered bands are written in the report
  before the numbers; say HELD / NOT HELD; tune nothing to rescue one. A red is reported red.
- Runtime: local compute on 6,560 cached files (~81 MB gz) — minutes. Credits: 0.

ITEM 1 (S7) — state timeline rebuilt (nhl/sim/build_events.py).
- Walk each game's plays in order, keeping the RUNNING score (updated when a goal play is passed), and emit
  spans with: game, period, start/end game-seconds, home/away skaters and goalie-in flags (situationCode), score
  difference AT THE SPAN (home view), duration.
- Spans end at the next play OR the period's end (period-end play / 1,200 s in regulation; OT ends at the
  winning goal or 300 s). The shootout (periodType SO) contributes NO time, and no span may cross into it.
- NULL CONTROLS, all 6,560 games, asserted in tests and reported:
  (a) seconds per game == 3,600 + OT seconds actually played (winning-goal time, or 300 if a shootout followed),
      within 2 s — 100%;
  (b) the score difference on the first span of every game is 0 — 100%;
  (c) the score difference on the last span equals the final regulation+OT score difference (shootout +1
      removed) — 100%;
  (d) seconds with the home goalie out while the home team is NOT trailing are reported (expected: small —
      delayed penalties); report the count and the median length of such spans.
- Tests (each must fail on 025494252): the opening span of game 2024020001 has score diff 0; per-game seconds of a
  shootout game from the fixture equal 3,900; a span at the -1 state exists before that game's third goal.

ITEM 2 (S8) — constants v2, as RATES (nhl/sim/build_constants.py -> nhl/data/sim/constants_v2.json; v1 kept and
marked withdrawn in the manifest). Fit on 2021-22 + 2022-23 only; 2023-24 as `validate_drift`. Every entry has n,
the numerator, the denominator and its units.
- Attempt rate per 60 PER TEAM, and xG per attempt, by strength state named from the SHOOTING team's view (5v5,
  5v4 = on the power play, 4v5 = shorthanded, 4v4, 3v3 in OT, 6v5 = own goalie pulled, 5v6 = shooting at an empty
  net) — numerator: that team's unblocked attempts in the state; denominator: seconds in the state.
- Score effects: for each score difference -3..+3 (shooting team's view) x period 1-3, attempts per 60 at 5v5
  divided by attempts per 60 at 5v5 when tied, and the same for xG per attempt.
- Penalties per team per 60 (by score state too), minor / double-minor / major shares, and the share of minors
  that ended early on a power-play goal.
- Pulled goalie: hazard per 30-s bin of the last 5:00 of the 3rd, by score difference -1 / -2 / -3, from the
  goalie-out transitions in the S7 timeline (re-entries and delayed-penalty pulls excluded and counted).
- Empty net: attempts and goals per 60 FOR the leading team and FOR the trailing (6-skater) team while the
  trailing team's net is empty.
- 3-on-3 OT: attempts per 60 per team, goals per xG; share of OT games decided in OT.
- Shootout: per-attempt conversion (parse periodType SO plays), share of shootouts that go past round 3.
- PRE-REGISTER (write before looking): penalties per team per game 2.8-4.5; at 5v5 in the 3rd, the trailing-by-1
  team's attempt multiplier > 1.05 and the leading-by-1 team's < 0.95; > 80% of pulls at -1 fall in the last 3:00;
  shootout conversion 28-35%; share of OT games decided in OT (not shootout) 55-75%.
- NULL CONTROL: the same derivations run on the S-WO1 state_time must give a first-span score state that is not 0 in
  most games, and a penalty rate outside the band. Show both, so the repair is shown to move the numbers.

ITEM 3 (S9) — rush feature, xG v2, and the two loose ends (nhl/sim/fit_xg.py -> nhl/data/sim/xg_v2.json).
- Rush = the previous event (any type) was in the neutral or the shooting team's defensive zone (details.zoneCode)
  <= 4 s before the attempt. Report its rate (expected a few % of attempts) and its goal rate vs non-rush.
- Refit xG exactly as S5 (2021-22 + 2022-23 only, same features now including a real rush flag), same four
  pre-registrations on 2023-24 plus: the rush coefficient is positive. Keep xg_v1.json; mark it superseded.
- SOG mismatches: list every game where table SOG != box-score SOG with the play types involved (penalty shots,
  shootout, shot types) and say which rule makes them match — or why they cannot.
- League scoring drift: goals / xG_v2 by month for 2021-22 .. 2025-26 (REPORTED only; 2025-26 was 1.068 on v1).
  Nothing is fitted on 2024-25 or 2025-26.

CLOSING
- Append to logs/_log_nhl_sim_s1.txt (`git add -f`) a section "S-WO2": RETURNED vs MEANS; every null control
  with counts; every pre-registration HELD / NOT HELD; NOT DONE; UNVERIFIED; commit shas; ONE merge command. Stop —
  Cowork verifies before S-WO3 (point-in-time team and goalie ratings).
