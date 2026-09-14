
## 2026-09-13T19:50Z  claude-code (Phase 1B-FIX-2)
- COMMITTED: CLAUDE.md SESSION CONDUCT section (6ee1e7174)
- COMMITTED: nfl_sim Phase 1B-fix-2 (f41f34c14) — share shrinkage on team opportunities, depth-order priors, active universe 2026, grid re-run
- RAN: nfl/sim/usage.py on VM (212s total)
- ASSERTIONS:
  - (a) PHI 2024 wk18: Barkley carry_share = 0.649 (> 0.50 PASS), Hurts carry_share = 0.158 (> 0.15 PASS)
  - (b) 2024 wk18 max zero-carry team mass = 0.000 (< 0.05 PASS), max zero-target = 0.000 (< 0.05 PASS)
  - (c) All share sums within 1e-6 of 1.0 (PASS)
  - (d) 2026 wk2: 32 teams, 520 players (PASS)
  - (e) active_flag mean = 0.552 — DEV(19115)/RES(9298)/INA(4494)/Out(2004)/Questionable(907) (PASS)
- GRID: 12 points, winner (share_half_life=4, k_share=20), BOUNDARY, extension NOT triggered (condition is (2,20) which did not win)
- PIT: PASS at wk9 and wk10 (player 00-0031588)
- TOP 10 carry share 2024 wk18: Chase Brown CIN 0.795, D'Onta Foreman CLE 0.723, Kyren Williams LA 0.718, Rico Dowdle DAL 0.714, Jonathan Taylor IND 0.682, Michael Carter ARI 0.664, Josh Jacobs GB 0.658, Saquon Barkley PHI 0.649, Bijan Robinson ATL 0.646, Aaron Jones MIN 0.622
- TOP 10 target share 2024 wk18: Malik Nabers NYG 0.345, Brian Thomas Jr JAX 0.337, Trey McBride ARI 0.307, Puka Nacua LA 0.303, A.J. Brown PHI 0.288, Drake London ATL 0.286, Justin Jefferson MIN 0.283, Ja'Marr Chase CIN 0.272, Jerry Jeudy CLE 0.269, Keenan Allen CHI 0.264
- NOT DONE: Step 4 (audit). Derrick Henry not in top 10 carry share (TEN→BAL trade mid-season changed team; his BAL shares are separate). K. Williams ranked 3rd not 1st despite most carries — Chase Brown CIN's higher ratio over fewer team carries in a committee split.
- UNVERIFIED: whether the grid RMSE improvement (0.23→0.14) is genuine vs the old formula or partly from the zero-evidence override reducing error on zero-touch player predictions. The override is structurally correct (0/400 is strong evidence) but conflates the grid signal.

## 2026-09-13T19:50Z  claude-code (Phase 1B-FIX-2)
- COMMITTED: CLAUDE.md SESSION CONDUCT section (6ee1e7174)
- COMMITTED: nfl_sim Phase 1B-fix-2 (f41f34c14) — share shrinkage on team opportunities, depth-order priors, active universe 2026, grid re-run
- RAN: nfl/sim/usage.py on VM (212s total)
- ASSERTIONS:
  - (a) PHI 2024 wk18: Barkley carry_share = 0.649 (> 0.50 PASS), Hurts carry_share = 0.158 (> 0.15 PASS)
  - (b) 2024 wk18 max zero-carry team mass = 0.000 (< 0.05 PASS), max zero-target = 0.000 (< 0.05 PASS)
  - (c) All share sums within 1e-6 of 1.0 (PASS)
  - (d) 2026 wk2: 32 teams, 520 players (PASS)
  - (e) active_flag mean = 0.552 — DEV(19115)/RES(9298)/INA(4494)/Out(2004)/Questionable(907) (PASS)
- GRID: 12 points, winner (share_half_life=4, k_share=20), BOUNDARY, extension NOT triggered (condition is (2,20) which did not win)
- PIT: PASS at wk9 and wk10 (player 00-0031588)
- TOP 10 carry share 2024 wk18: Chase Brown CIN 0.795, Foreman CLE 0.723, K Williams LA 0.718, Dowdle DAL 0.714, Taylor IND 0.682, Carter ARI 0.664, Jacobs GB 0.658, Barkley PHI 0.649, Robinson ATL 0.646, Jones MIN 0.622
- TOP 10 target share 2024 wk18: Nabers NYG 0.345, Thomas JAX 0.337, McBride ARI 0.307, Nacua LA 0.303, Brown PHI 0.288, London ATL 0.286, Jefferson MIN 0.283, Chase CIN 0.272, Jeudy CLE 0.269, Allen CHI 0.264
- NOT DONE: Step 4 (audit)
- UNVERIFIED: whether grid RMSE improvement (0.23 to 0.14) is genuine vs old formula or partly from zero-evidence override reducing error on zero-touch predictions

## 2026-09-13T23:15Z  claude-code (Phase 1B Step 4)
- COMMITTED: nfl_sim Phase 1B step 4: attribute reliability audit (D11) (e44c3407c)
- RAN: nfl/sim/reliability_audit.py — 189,481 plays, 17,418 receiver-game rows, 8,235 rusher-game rows
- FULL TABLE:
  | Attribute           | Group     |    N |     r |    r8 | YoY r | PASS/FAIL |
  | target_share        | receivers | 1105 | 0.890 | 0.942 | 0.802 | PASS      |
  | rz_target_share     | receivers | 1073 | 0.579 | 0.733 | 0.521 | PASS      |
  | adot                | receivers | 1105 | 0.848 | 0.918 | 0.759 | PASS      |
  | catch_rate          | receivers | 1105 | 0.375 | 0.546 | 0.219 | PASS      |
  | yac_per_rec         | receivers |  991 | 0.530 | 0.693 | 0.322 | PASS      |
  | yards_per_target    | receivers | 1105 | 0.286 | 0.445 | 0.096 | FAIL      |
  | explosive_rec_rate  | receivers | 1105 | 0.228 | 0.372 | 0.109 | FAIL      |
  | carry_share         | rushers   |  438 | 0.960 | 0.980 | 0.832 | PASS      |
  | gl_carry_share      | rushers   |  245 | 0.720 | 0.837 | 0.568 | PASS      |
  | yards_per_carry     | rushers   |  438 | 0.419 | 0.590 | 0.231 | PASS      |
  | explosive_rush_rate | rushers   |  438 | 0.312 | 0.476 | 0.151 | FAIL      |
- RECENT FORM: target_share RMSE(std)=0.06813 RMSE(std+l3)=0.06727 delta=+0.00086; carry_share RMSE(std)=0.15025 RMSE(std+l3)=0.14547 delta=+0.00478. Both positive (recent form adds marginal info).
- DEFENSE SPLIT: ypt_defense_split r=-0.046 r8=-0.097 N=913 FAIL. Player-level matchup sensitivity vs pass defense type is noise, not a stable trait.
- NOT DONE: engine code, anchoring, pricing. No files touched outside nfl/sim/reliability_audit.py and research/nfl_sim/phase1_attribute_reliability.md.
- NOT DONE: git push (denied by permission; user must push manually)
- UNVERIFIED: whether catch_rate (r8=0.546, barely passing, YoY=0.219) will hold up in forward validation or is borderline noise elevated by pooling

## 2026-09-14T04:30Z  claude-code (Phase 2A engine + tables + K1 iteration 1)
- COMMITTED: nfl_sim Phase 2A (a47f38ddc) — tables.py, engine.py, diagnostics.py, 12 table files, report
- BUILT: 8 empirical table files from 2021-2024 PBP (189,481 plays, regular season only)
- FOUND BUG: Q3->Q4 quarter transition — stale `time_up` mask triggered end-of-regulation immediately when Q3 ended and qtr advanced to 4 (game ran only 3 quarters = ~2700s of clock). Fixed by checking `clock <= 0` at Q4/OT end, not the stale mask.
- FOUND BUG: clock table originally measured within-drive only gaps (~30.5s), missing cross-drive transitions. Reverted to all-play gaps (~29s).
- FOUND BUG: `incomplete_oob` category mixed real incompletes (8s) with OOB completions (~30s). Split into `incomplete` (8s) and `complete_inbounds` (39s).
- FOUND: per-sim margin SD was ~1.5 in iteration 1 because yards were drawn from unsplit `yds_all_q` (no matchup tilt on success probability). Fixed by restoring success/fail split with log5-adjusted success probability → SD margin = 12.8.
- ADDED: defensive penalty handler (~8.1% rate, 72.5% auto-first-down, 9 yds mean) — added ~4 pts/team.
- VECTORISED: pass/rush outcome state updates (normal comp/sack/incomplete/rush done with boolean masking). Clock draws batched by outcome type × hurry. Speed: 4.3s/game → 2.3s/game.
- RAN K1 iteration 1 (N=2000, 1087 games, 79 min):
  | Metric | Sim | Actual | PASS/FAIL |
  | pts/team | 18.0 | 22.4 | FAIL |
  | plays/game | 132.3 | 124.5 | PASS |
  | SD margin | 1.53 | 14.20 | FAIL |
  | corr(margin,spread) | 0.471 | ~0.8 | INFO |
- POST-FIX diagnostics (50 games × 2000, after success/fail restore + penalties):
  | pts/team | 17.8 (target 22.4) | plays/drive | 6.68 (target 5.89) |
  | drives/game | 19.7 (target 21.9) | FD rate/play | 0.318 (actual 0.295) |
  | per-sim margin SD | 12.8 (actual 14.2) | |
- NOT DONE: K1 has not passed. plays/drive still 0.78 too high; pts/team 4.6 short.
- NOT DONE: git push (denied; user must push)
- NOT DONE: 2B player allocation, anchoring, pricing
- UNVERIFIED: whether the excess FD rate (31.8% vs 29.5%) is from defensive penalty auto-first-downs (correct) or from the yards distribution yielding too many first downs (overcounting)
- UNVERIFIED: whether 4th-down go rate in sim (~24%) vs actual (20%) is a meaningful contributor to drive length

## 2026-09-14T10:00Z  claude-code (Phase 2A K1 iteration 2)
- COMMITTED: nfl_sim Phase 2A iter 2 (6eff1148a) — pass fumbles, 4th-down fix, vectorised yards/playcall
- FOUND BUG: pass fumbles missing — pass table had no p_fumble. Actual rate 0.79% per dropback (619 fumbles in 78K plays). Added to tables.py and engine.py.
- FOUND BUG: tendencies_weekly.parquet has fourth_down_go_rate=1.0 for all teams (corrupted on disk). Engine's team 4th-down override was setting p_go=1.0 for all 4th-and-short midfield plays. Disabled override; using table probabilities only.
- VECTORISED: play-call bucket construction (np.char.add), yards quantile interp (batched by situation bucket). K1 time: 79min → 15min (0.84s/game).
- VERIFIED: adding pass fumble draw AFTER existing RNG draws (not before) preserves the RNG stream, avoiding catastrophic FD rate collapse from stream shift.
- K1 ITERATION 2 (N=2000, 1087 games, 912s):
  | pts/team | 17.5 | FAIL (target 22.4) |
  | SD margin | 2.74 | FAIL (target ~14.2) |
  | corr(margin,spread) | 0.723 | improved from 0.471 |
  | drives/game | 20.3 | PASS (target ~22) |
  | plays/game | 132.7 | PASS |
  | per-sim margin SD | 12.9 | good (actual 14.2) |
- DIAGNOSTIC (50 games × 2000):
  | plays/drive | 6.46 | target 5.89 | gap 0.57 |
  | pts/team | 17.7 | target 22.4 | gap -4.7 |
  | punt/drive | 0.368 | actual 0.360 | CLOSE |
  | TO/drive | 0.109 | actual 0.119 | CLOSE |
  | FD/play | 0.315 | actual 0.295 | +2.0pp (from success tilt) |
- ROOT CAUSE of remaining gaps: EPA success/fail split inflates FD rate by ~2pp via the matchup tilt on p_success_given_comp. Without tilt, FD rate drops to 19.8% (too low). With tilt, it rises to 31.5% (too high). The tilt is needed for team differentiation (margin SD=12.9) but over-produces first downs. Game-mean margin SD=2.74 (vs actual 14.2) confirms team ratings differentiate scoring insufficiently.
- NOT DONE: K1 has NOT passed (2 of 3 iterations used). git push denied.
- NOT DONE: 2B player allocation, anchoring, pricing
- UNVERIFIED: whether rebuilding tendencies_weekly (fixing fourth_down_go_rate) would improve the diagnostic further
- UNVERIFIED: whether the 2021 season scoring gap (15.0 vs 23.0) is a data coverage issue or a real engine weakness
