# NHL sim S-WO3 — verification from the code and the log (Cowork, 2026-09-29)

Branch `nhl/sim-s3`: 97ded6c11 (S10-S11 ratings), 2c6cad87a (S12 sanity check), 99556de37 (log). Those three commits
touch only nhl/sim/ratings.py, nhl/sim/sanity_check.py, the decision log and the session log.

## Do NOT merge nhl/sim-s3
The branch was cut from a main that still had S-WO1/S-WO2's ORIGINAL commit ids. Jeff's rebase later rewrote those
on main, so `git diff origin/main...origin/nhl/sim-s3` shows 2,212 files. That includes statcast `.bak` files
(4.7 MB and 2.4 MB, over the 2 MB rule) and shared/last_updated.json. The repair order cherry-picks the three S-WO3
commits onto a fresh branch from origin/main instead.

## Holds
- The rebuilt event tables are identical to S-WO2's (sha256, 15 tables).
- Measured reliabilities, fit seasons, 40-game halves:
  - 5v5 attempt share r = 0.932 (K = 6.0 games);
  - 5v5 xG per attempt r = 0.798 (K = 20.7);
  - PP xG per attempt r = 0.211;
  - goalie GSAx per attempt r = 0.207 (K = 229).
- The shuffled-team null control gives about 0 (0.054 / 0.037).

## Wrong — read in `nhl/sim/ratings.py` at 97ded6c11
1. **The league prior uses every season, including the holdout.** `league_means` (lines 231-236) is computed over the
   whole 2021-26 table and is the shrinkage target for every rating. That is future information in every past
   rating (CHECK 1b) and holdout data inside the fit.
2. **No season boundary at all.** The cumulative sums run over a team's whole 2021-26 history (lines 244-290; the only
   reset is `n_games == 0` = the team's first game in the data). A 2025-26 rating weights 2021-22 games equally with
   last week's. The log's claim "first game of each season starts at league mean" is false. The measured carry-over
   weight the order asked for was not built.
3. **The leakage truncation test (the order's null control) was not run.** Neither was the "<=" mutation, even though
   the S10 commit message says "all HELD".
4. **The goalie ratings use the same structure** (same all-season prior pattern). Starter-vs-box-score agreement was not
   checked.
5. **PP/PK ratings are not in the table** and score adjustment is not applied — both were in the order.
6. **S12 was not run as specified.** It used a "simplified" 5v5-only formula: no PP/PK, goalie or finishing term.
   Implied totals landing 12-15% low is the expected result of leaving out power-play goals. The Pinnacle comparison
   was marked "not measurable" over an id format. The order said to reuse
   research/layers/nhl_edge_hunt_2026-09-29/phase3_lines/build_lines.py, which already joins by (ET date, home, away).
7. **The finishing term is monthly, including same-month games** — a report, not a point-in-time input.

## Correction to Cowork's own S-WO2 note
S-WO2's log labelled 2025-26's 1.068 as "goals/xG". It is xG/goals: S5 printed "sum(xG)/goals ... 2025=1.068", and
S-WO3's monthly goals/xG for 2025-26 runs 0.91-0.97. So in 2025-26 the xG model OVER-predicted goals by ~6.8%.
Goals came in BELOW xG. The S-WO2 verification note and the handoff said the opposite; both are corrected here.
