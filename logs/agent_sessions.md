
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
