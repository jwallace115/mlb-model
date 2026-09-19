- **2026-09-13 Phase 1B-fix-2 VERIFIED, player layer ACCEPTED.** Mac checkout re-cloned
  (fsck clean; old checkout preserved at ~/mlb-model_corrupt_20260913; O3 closed). From the
  files: Barkley 0.649 / Hurts 0.158 / Gainwell 0.117 (PHI 2024 wk18); Henry 0.547 (BAL);
  shares sum to 1; zero-touch mass 0; 2026 wk2 = 32 teams / 520 players; active universe
  922 rows; active_flag 0.552 = DEV/RES/INA/Out/Doubtful. Usage params frozen:
  share_half_life=4, k_share=20 (boundary on k; extension rule not triggered).
  **D14 (documented deviation):** code applies a zero-evidence override — any player with
  zero cumulative touches while active for >0 team opportunities gets share 1e-8 before
  normalisation. Not in the spec; compensates for the constant prior_weight blend (Cowork's
  spec error) that otherwise leaks mass to zero-touch players. Practical effect on the board
  is nil (no props exist for such players). Revisit only if Phase 3 prop calibration flags it.
  Next: Step 4 attribute reliability audit (D11) on RAW per-game values.
- **2026-09-13 Phase 1B step 4 COMPLETE (e44c3407c) — D11 audit verified from the file.**
  Admitted (r8 ≥ 0.50): target_share 0.942, rz_target_share 0.733, adot 0.918, catch_rate
  0.546 (YoY 0.219 — weak), yac_per_rec 0.693, carry_share 0.980, gl_carry_share 0.837,
  yards_per_carry 0.590 (YoY 0.231 — weak). Excluded: yards_per_target 0.445,
  explosive_rec_rate 0.372, explosive_rush_rate 0.476. Recent form: +0.0009 RMSE (targets),
  +0.0048 (carries) — small, real for carries; already captured by share_half_life=4.
  Defense-type split: r8 = −0.097 — NOT a player trait; excluded (Jeff's matchup question
  answered: no). **Reading:** role attributes are stable, conversion attributes are noise;
  D2 confirmed. Engine v1 player layer uses target/rz/carry/gl shares, adot (depth bucket),
  catch_rate (log5 on completion). yac_per_rec and yards_per_carry admitted but held for v2
  (borderline YoY). Phase 1 CLOSED. Next: Phase 2A engine (team level) + K1.
- **2026-09-14 Phase 2A IN PROGRESS — K1 NOT PASSED.** Engine, 8 tables, diagnostics committed.
  Real bugs fixed: 3-quarter game; clock table scope; incomplete clock class; no matchup
  tilt (per-sim margin SD 1.5 → 12.9); missing penalty layer; missing pass fumbles;
  per-sim loops (K1 79 → 15 min). Still open: pts/team 17.5 vs 22.4; plays/drive high.
  Cowork findings: (1) `fourth_down_go_rate` regressed to 1.0 everywhere (Phase 1B step 0
  rebuild of tendencies) — fix in ratings.py, do not disable; (2) "RNG order sensitivity"
  (FD rate 35% → 22% from inserting one draw) is a symptom of a decision reusing another
  decision's uniform — suspect yards quantile drawn with the success uniform; (3) K1 "SD
  margin 2.74 vs 14.2" compares sim mean-margin spread to realised-margin spread — wrong
  metric; pooled simulated margin ≈ 13.2. Team differentiation (2.74 vs closing-spread SD
  ≈ 6) is informational; D7 anchoring supplies the mean.
- **2026-09-14 CORRECTION:** the 4th-down "regression" was not a code regression. The Mac
  working tree carried stale Phase 1 outputs (original 13 Sep 15:42 files: k=200, 4th-down
  = 1.0, old grid) on top of the correct committed versions (4th-down 0.681, k=100). Both
  Phase 2A engine sessions ran against the stale ratings. Restored with `git checkout`; the
  decision doc is now tracked in git for the first time. Possible dual-writer odds capture
  on the Mac (snapshots after the re-clone, not on origin) flagged to Jeff — credit burn.
- **2026-09-14 side finding (not nfl_sim):** Mac LaunchAgents `com.mlbmodel.capture.football`
  and `com.mlbmodel.capture.mlb` were still loaded after the 6 Sep migration of capture to the
  VM — dual writer, no Mac push chain, credits spent twice. Unloaded and plists renamed
  `.disabled`. Mac crontab also carries inert VM lines (`/root/mlb-model`) — cleanup later.

---

## 11. PHASE 2A CLOSE — K1 PROVISIONAL (2026-09-14)

**D15 — K1 accepted as PROVISIONAL.** Final engine commit `89a4d1696` (iteration 6). Sixteen
real bugs found and fixed across six sessions (3-quarter game, no randomness, RNG uniform
coupling, clock scope, penalty layer absent, play-call table dead code via key mismatch,
multiplicative tilt, stale inputs, …) — see `research/nfl_sim/phase2a_realism_report.md`.
Passing: plays/game 125.9 (124.5), drives 21.4 (21.9), pooled margin SD 14.06 (14.20),
P(|margin|=7/10/14), pass/rush yards, team differentiation (sim mean-margin SD 6.2 vs
closing-spread SD 5.9, corr 0.78). Failing: pts/team 19.5 vs 22.4 (−13%);
P(|margin|=3) 8.5% vs 14.5%; P(|margin|=6) 5.1% vs 7.5%.
**Why proceed:** D7 anchoring matches mean margin and total to the market by construction,
so the points mean is corrected downstream. **What stays wrong and where it shows:** the
3/6 key-number mass is under-generated — affects alt-spread pricing near 3 and 6 and 1H
shape; TD/FG mix affects team-total shape. **v2 item:** key-number calibration layer
(empirical reweighting of the margin histogram, fitted on 2021–24, scored on 2025), and the
success/fail split mechanism review. Both are Phase 3+ refinements, not engine rewrites.
K1 lines are reported in every downstream report until they pass.

Order from here: **Phase 2B** (player allocation inside the engine — needed for props) →
**Phase 3** (anchoring + pricer + calibration 2021–24, 2025 scored once) → **Phase 4**
(weekly run + parlay board). Target: a Week 2 board (2026 Week 1 ends Mon 14 Sep; Week 2 is 17–21 Sep).
- **2026-09-14 Phase 2B-fix + Phase 3 (19ee88142).** Player layer: Beta-binomial share
  dispersion fitted by position (WR φ 42.9, TE 85.0, RB 71.3; carries RB 7.9, QB 20.0),
  measured vacated-share redistribution (WR out → 58/28/14 WR/TE/RB), pool concentration
  matches; reliability now −10pp at low deciles / +10pp at high, ±3pp in the middle. Phase 3:
  anchoring converges to market mean (pts 22.7 vs 22.4); pricer for all families; isotonic
  maps for margin/total/team-total; 2025 K2 scored once, lock file written; anchored sim has
  no ATS edge by construction (2025 home-cover 44.1%, noise). **Gaps:** calibration backtest
  ran WITHOUT the player layer (Mac memory kills) and at 2 anchoring iterations — prop maps
  and K4 (real prices) NOT done; P(|margin|=3) 7.5% post-anchoring → alt spreads straddling
  3/6 must be flagged on the board until a key-number layer exists (v2).
  Next: Phase 3b (anchored+players 2021–24 in background, prop maps, K4 real prices, 2025 props
  scored once under a second lock entry) → Phase 4 board for Week 3.
- **2026-09-14 Phase 3b (c83c43d90).** Anchored+player backtest 2021–24 (streaming, 4-iteration
  rule restored). Prop isotonic maps fitted per (prop type × position): WR receptions 10/10
  deciles in-sample, 9/10 on 2025 holdout; WR anytime TD 8/10; TE receptions 6/10; WR rec yds
  7/10; RB rush yds 5/10 (FAIL). Real-price sign (2023–24 in-sample): receptions +2.1pp; rec
  yds −10.4pp, rush att −11.6pp, rush yds −17.1pp — sizes implausible → suspected leg-matching
  bug (x.5 vs integer ladder / vig), symmetric check not run; per-leg K4 ROI still not
  computed. Anchoring convergence: p90 |Δmargin| 3.95 at N=1,000 (MC SE 0.44) → ~10% of games
  effectively unanchored. 2025 props scored once, lock updated.
  **D16 — BOARD TRUST RULES (v1):** priced and rankable = WR/TE receptions (TE flagged), WR
  anytime TD, team markets anchored to Hard Rock; shown but UNTRUSTED = yardage props, rush
  attempts, until the ladder check passes; alt spreads straddling 3 or 6 flagged (key-number
  mass under-generated); games with |Δmargin| > 1.0 after anchoring flagged "not anchored".
- **2026-09-14 WEEK-NUMBER CORRECTION:** the Sept 13 session-log entries labelled the
  Sunday 13 Sep slate "Week 2". It was **Week 1** (season opened Thu 10 Sep; MNF 14 Sep closes
  Week 1). The next board is **Week 2** (17–21 Sep). run_week.py must detect the upcoming week
  from the nflverse schedule (first week with unplayed games), never from a typed number.
- **2026-09-14 Phase 4B (K4 re-run, grading, board upgrades).**
  **D17 — K4 SYMMETRY CHECK PASSED.** The Phase 3b "+2.1pp receptions edge" was an artifact of
  approximate name matching (last-name only). With player_id resolution via rosters_weekly:
  all 5 families pass the symmetry check (over_ROI + under_ROI ≈ -0.11 to -0.13, consistent
  with ~5% vig per side). **No family shows positive edge** on the over side. WR receptions
  mean edge is **-5.4pp** (was reported +2.1pp). D16 tiers UNCHANGED — trust assignments were
  based on reliability (decile pass rate), not K4 ROI, and remain valid. The K4 result means
  the sim does not beat closing prices on any individual prop family; its value remains in
  the joint distribution (SGP correlations, conditional structure).
  See `research/nfl_sim/phase4b_grading_k4.md` for full K4 tables and symmetry check.
- **2026-09-15 Phase 4B-fix (anchoring solver, grading, ATD correction).**
  **D18 — SOLVER MISMATCH (documented deviation).** The Phase 3b calibration maps were
  fitted with the fixed-Jacobian 4-step loop at N=1,000 (`run_cal_players.py`), which left
  p90 |Δmargin| = 3.95 (~10% of games effectively unanchored). The live board now uses an
  8-step damped Newton at N=10,000 with best-iteration selection, achieving 10/16 within
  0.5 pts margin, 11/16 within 1.0 pts total. This is the direction the maps assume (fully
  anchored), and the improvement is real: 4B had 0/16 converged. But the research object
  and live object now differ in anchoring precision. **v2 must re-fit calibration maps with
  the same 8-step solver before the identity claim is restored.** Do not re-fit now.
  ATD note corrected: `actual_atd = 0` shortcut was in `_score_player_props` (unused path),
  not in `run_cal_players.py` (which produced the maps correctly). WR ATD stays TRUSTED.
- **2026-09-15 Phase 5A engine repair.**
  **D19 — PLAYER ATTRIBUTES ARE ALLOCATION-ONLY IN v2.** The player layer had two
  outcome-shaping paths: (1) completion probability tilted by player catch_rate via
  logit-additive shift; (2) depth-split pass yards tables selected by receiver aDOT.
  Both removed. Same game/seed/offsets: team-level outcomes now identical with and without
  players (T4 verified at N=4,000 via KS test and SE comparison). Any player-level outcome
  shaping is a v3 question behind a new reliability gate.
  **D20 — 5A ENGINE REPAIRS.** Seven fixes: (1) game termination — all sims now reach a
  valid terminal state; (2) reproducible seeds via zlib.crc32; (3) PIT filtering for
  lg_pace/lg_4th_go; (4) player allocation-only; (5) playcall fallback counter; (6) NFL
  rules: 2pt decisions from table, season-aware OT, random opening possession, kickoff from
  table, negative yards unclipped, dead punt-touchback removed; (7) offset-response
  continuity via float game state + stochastic EPA rounding.
  **All prior K-numbers, calibration maps, and boards are superseded.** Maps to be re-fit
  in 5C on 2021-2024 only. 2025 treated as inspected; 2026 prospective is the only OOS.
  K1 post-5A: 9 PASS, 3 FAIL (same 3 as D15: pts/team, P(|m|=3), P(|m|=6)). New passes:
  corr 0.800 (was 0.769), pass yds 222.8 (was 227.5, actual 221), tie rate 0.90%.
  See `research/nfl_sim/phase5a_engine_repair.md`.
- **2026-09-15 Phase 5A-2 scoring-conversion diagnostic.**
  Per-drive log added to engine (byte-identical when off; T8 verified at N=2,000).
  K1 re-run (1,087 games, N=500, 555s) with per-drive instrumentation.
  **Finding:** 3.5 pts/team deficit is 77% TD/drive gap (-4.0pp, -2.7 pts), 14% FG
  gap (-1.8pp, -0.5 pts). Three table gaps identified, zero engine bugs.
  (1) Excess end_half/end_game drives: 9.5% vs 3.7% actual — clock table hurry flag
  only activates when trailing <=8, but real teams hurry at end-of-half regardless.
  (2) 4th-down go rate 3.4pp too high (23.2% vs 19.8%) from team aggressiveness
  override — converts FG opportunities to failed go attempts, reducing FG att/game
  from 3.92 to 3.41 and turnover-on-downs 7.5% vs 5.8%.
  (3) Key-number |margin|=3 deficit (7.9% vs 14.5%) is downstream of fewer FGs.
  **D22 proposed (not decided):** End-of-half clock urgency table (hurry regardless
  of score in final 2:00 of each half).
  **D23 proposed (not decided):** Cap team 4th-down aggressiveness override at 1.15.
  See `research/nfl_sim/phase5a2_scoring_diagnostic.md`.
- **2026-09-16 Phase 5A-3 scoring-conversion fix.**
  **D22 — Clock runoff conditioned on (score_state × clock_period).** The D22 proposal
  ("hurry regardless of score") was REJECTED: the 5.8pp end-of-half excess was a
  definitional artifact (kneel-only drives excluded from actuals; corrected gap is 2.7pp).
  Clock table now conditioned on 5 score states × 3 clock periods × outcome_type, with
  100-play minimum and parent fallback. The binary hurry flag is REMOVED from the engine;
  clock behaviour comes entirely from the empirical table. Leading teams in Q4_late now
  consume 32s/rush play (from data, reflecting kneeling pace) vs 16s for trailing teams.
  **D23 — 4th-down GOE override replaces multiplicative ratio.** The D23 proposal ("cap
  at 1.15") was REJECTED as a fudge constant. The root cause: `fourth_down_go_rate` was
  measured on 4th-and-≤2 between the 40s only, then applied multiplicatively to ALL
  situations. Classification: engine bug (mis-scoped multiplier). Fix: GOE = mean(observed
  go − table expected go) over ALL of a team's 4th-down situations, shrunk with
  k_tendency=200, applied logit-additively like PROE. Additional bug: `int(dist[i])`
  truncated float distances (FIX 7), biasing toward "1-2" bucket; fixed to `round()`.
  Result: go rate 23.2% → 22.1% (target 19.8%, residual 2.3pp from table granularity);
  FG att 3.41 → 3.44; P(|m|=3) 7.86% → 8.50%; P(|m|=7) 6.79% → 7.28% (matches actual
  7.27%). pts/team unchanged at 18.9 (3.5 gap remains; best hypothesis: 5-zone table
  granularity near the goal line). 34 tests, all passing.
  See `research/nfl_sim/phase5a3_scoring_fix.md`.
  See `research/nfl_sim/phase5a2_scoring_diagnostic.md`.
- **2026-09-15 Phase 5A-6 — GOAL-LINE CENSORING FOUND AND FIXED (Cowork-executed, no relay).**
  Root cause of the 3.4 pts/team K1 deficit: yardage tables were built from RECORDED gains,
  which are right-censored at the goal line (a scoring play from the 8 records 8). Pooling
  censored plays into 5 field zones biased every zone's deeper end downward — TD rate per
  completion from the 5–10 was 26% in the sim vs 53% real; 40+ completions 0.73 vs 0.97/game.
  5A-5's "5-zone granularity" hypothesis was directionally right and Cowork's rejection of
  it (on the drive-entry red-zone table) was wrong; the per-play TD-rate-by-yardline table
  is the decisive diagnostic and is now the standard for this question.
  **D24 — Kaplan–Meier yardage quantiles.** `tables._km_quantiles`: scoring plays are
  censored at yardline_100; the unobservable tail borrows shape from the next zone out
  (rz10 ← opp20 ← midfield; midfield/own ← open-field gains of the same situation),
  conditional on gain > last observed value; sentinel 99 (capped by the engine at the
  goal line) only when no reference qualifies. Applied to pass and rush success/fail/all
  quantiles; `n_censored` recorded per cell. No constants.
  **D25 — End-of-half FG on downs 1–3** from empirical table J (`eoh_fg_decision`):
  state × seconds-left × yardline, min cell 30. Leading teams in Q4 never kick (measured 0).
  **D26 — Q2<2 clock bucket** in the play-call and 4th-down tables (two-minute drill:
  pass rate 0.80 vs 0.58; FG rate in range ~10pp higher).
  K1 after (1,087 games, N=500): pts/team 19.0 → **21.79** (actual 22.39; by season
  21.6/22.0/21.5/22.2 vs 23.0/21.9/21.8/22.9); off TDs 3.94 → 4.80 (4.73); TDs from ≥ 20
  out 0.76 → 1.13 (1.13); go rate 20.7% (19.8, within 1pp for the first time); drives 22.1
  (21.9). New FAILs: pass yds/team 232.5 (221; KM inside 40-yard zones still averages the
  compression gradient), SD margin 14.84 (14.20). Unchanged FAILs: FG att 3.32 (3.92),
  P(|m|=3) 8.1% (14.5%), tie rate 0.73% (0.28%). 8 new tests at spec, all passing; 5A-3
  spec tests still red as reported. Next (5A-7): KM inside 10-yard zones with the same
  tail chain; late-half possession count (8.2 vs 9.0 snaps in Q2's last 2:00, 4.5 vs 5.6
  in Q4 — timeouts not modelled); then FG count and key-number mass re-measured.
  Flagged, not changed: `constants.json` carries hand-written safety constants (5A-4) the
  builder does not produce, and the engine scales deep sack yardage by 0.687 (5A-4) —
  both violate the no-constants rule. See `research/nfl_sim/phase5a6_goalline_censoring.md`.
- **2026-09-16 Phase 5A-7 — 10-yard zones, timeouts/kneel policy, safety rates in the builder
  (Cowork-executed).** K1 pts/team 21.79 → **22.49** (actual 22.39); completion yards, yards per
  completion, yards per rush, late-half snaps, timeouts and offensive TDs now match reality.
  **D27 — Ten-yard-zone outcome tables with KM.** `pass/rush_outcomes_z10.parquet` (down × dist ×
  10 zones; KM tail chained zone-by-zone toward the goal line; z5 parent is the thin-cell
  fallback in `engine._fill_zone_arrays`). The 5A-4 ×0.687 deep-sack scale is removed (the
  y90/y100 cells carry measured sack yardage).
  **D28 — Empirical timeout policy and kneel decision.** `timeout_policy.parquet` (side × qtr ×
  seconds × offence state × clock running) and `kneel_decision.parquet` (qtr × seconds × defence
  timeouts remaining × down × situation). Timeouts are state (3/half, 2 in OT); a timeout makes
  the runoff the stopped-clock kind. The 40-second / "opponent has ~1.5 timeouts" kneel
  heuristic is deleted. Late-Q2 snaps 9.08 (9.03), late-Q4 6.20 (5.61), TO 1.85/2.16 (1.78/2.08).
  **D29 — Safety rates measured in `build_constants`** (raw per-play rates by own-goal-line
  bucket); the 5A-4 hand-typed values scaled by 1/1.84 and two unused constants are gone.
  **K1 DEFINITION CORRECTION:** the "pass yds/team" line compared nflverse pass yards (sacks
  included) with engine completion yards (sacks excluded) since Phase 2A; on one definition the
  sim is right (476.7 vs 474.2 completion yards/game). New FAILs are volume: plays 129.8 (124.5),
  drives 22.8 (21.9), rush plays 55.5 (52.5). UNCHANGED FAIL: key-number mass — P(|m|=3) 7.7%
  (14.5%), |m| ≤ 7 in 41.6% of games (49.0%) — structural and independent of every scoring fix.
  Next (5A-8): margin distribution conditional on the margin at 5:00 / 2:00 remaining, sim vs
  actual, to locate where close-game mass is lost; then volume (+4% drives), FG count.
  Tests: 59/61 pass (FG att 3.65 vs 3.92 and offence penalties 6.19 vs 5.51 red).
  See `research/nfl_sim/phase5a7_zones_timeouts.md`.
- **2026-09-16 Phase 5A-8 — close-game diagnostic (Cowork-executed; no engine behaviour change).**
  Where is the key-number mass lost? Score state when the Q4 clock first reads ≤ 5:00 is nearly
  right (one-score share 41.9% vs 43.9%; the 2.0pp is all "tied"); reweighting the sim's own
  endgame to the real 5:00 states recovers only 1.8 of the 7.5pp |final| ≤ 7 gap and 0.6 of the
  6.9pp gap at 3. **~90% of the missing mass at 3 is created after 5:00.** Tied at 2:00 ends at
  exactly 3 in 80% of real games vs 34% of sims; the sim endgame is TD-shaped (+7 6.9% vs 2.0%,
  −7 10.4% vs 7.2% after the 2:00 snapshot) where reality is FG-shaped (+3 11.8% vs 7.0%).
  Drive decomposition (drives starting ≤ 5:00): trailing by 4–8 the sim punts 24.7% (real 3.7%)
  and goes on downs 5.9% (25.8%); leading by 1–8 it turns it over on downs 15% (2%); tied it
  scores TDs 13.5% (4.8%) and FGs 11.5% (25.1%); 14% of tied drives starting ≤ 2:00 end with the
  clock expiring inside the 35 without a kick (1.6%). OT: 23% of sim OT games end tied (4.3%).
  **ROOT CAUSE (verified):** the 4th-down fallback levels 2 and 3 are unreachable — the builder
  prefixes every grouped column (`yl_b = "c_opp21-30"`, `score_b = "z_trail4-8"`) and the engine
  looks up unprefixed ones; replaying the chain on all 15,589 real 4th downs, levels 2/3 hit 0.0%,
  and 51.7% of Q4 (99.1% of OT) 4th downs resolve at the coarsest `zc_` cell, which pools a team
  down 6 with a team up 6 and all of Q4 with its last 2:00 (trail 4–8 late: table p_go 0.34 /
  p_punt 0.42 vs real 0.83 / 0.14). Dead since the table was introduced. Second mechanism: the
  game-winning-FG setup (tied / trail ≤ 3, in range, ≤ 40 s) draws its runoff from the pooled
  Q4_late clock cell, so the drive skips the kicking window. Instrumentation added: `m_q4_300`,
  `m_q4_120`, `poss_q4_*`, `yl_q4_120` outputs; drive-log `sd_start`, `opp_points`;
  `nfl/sim/close_game_diagnostic.py`; actual tables `actual_close_games_2021_2024.parquet`,
  `actual_late_drives_2021_2024.parquet`. Tests `test_engine_5a8.py`: 2 pass, **4 red by design**
  (T3 fallback reachability; T4 late-drive punt/downs/FG rates) = the 5A-9 acceptance spec.
  **PROPOSED D30 (needs go, 5A-9):** fix the key mismatch and rebuild the 4th-down fallback so it
  never pools across the sign of the score (coarsen distance → zone → clock first; Q4_2-5 pools
  with Q4<2 before Q4>5; min cell from measured variance); EOH-state clock/play-call cells
  measured from real snaps in that state; re-run K1 with the 5A-8 conditionals as acceptance;
  re-measure OT ties only after. See `research/nfl_sim/phase5a8_close_games.md`.
- **2026-09-16 Phase 5A-9 — endgame repair (Cowork-executed).** Acceptance: full K1 (1,087 × 500,
  drive log) with the 5A-8 conditionals. **D30 — 4th-down table rebuilt** as a complete
  1,680-cell grid (ydstogo × 10-yard zone × 7 score states × 6 clock buckets incl. OT); one shared
  key function (`tables.fourth_down_keys`) for builder and engine; hierarchical Dirichlet shrinkage
  toward the parent with k measured per level by method of moments (`fourth_down_meta.json`);
  parent chain coarsens field, then clock (Q4_2-5/Q4<2/OT pool first), then score, and the coarse
  score grouping is structural — in range: need_td / fg_useful / lead; outside: trail / tied / lead.
  Hand defaults `(0.1, 0.1, 0.8)` removed; a missing key raises. **D31 — EOH runoff cells** (Q2 vs
  Q4/OT split, KM-censored, no pace, no floor, timeouts inside the data); EOH FG hook covers OT.
  **D32 — kneel-then-play defect:** `alive = ~game_over` before the scrimmage block discarded the
  kneel/expired-clock exclusions since 5A-7, so every kneel was followed by a snap in the same
  iteration (3rd-down kneel → 4th-down play with no decision → turnover on downs: leaders ended
  15% of late drives on downs, real 2%). **D33 — FG-setup state** (Q4/OT, tied or trail ≤ 3, inside
  the 35, ≤ 3:00, downs 1–3): empirical kneel (by seconds × defence timeouts), pass rate (by state ×
  seconds), in-state rush yardage (KM, n = 322; 2.5–2.9 yds, 4–7% TD vs 3.7 / 10%), and in-state
  runoff cells where the ≤ 40 s cells store the time left at the next snap (the kneel-to-the-kick
  fact: 22 of 22 real in-state kneels with ≤ 40 s were followed by the FG at 1–4 s). **D34 —
  spikes** (`eoh_spike.parquet`: Q4 4–10 s 29–37%, 1 s, a down; EOH FG rate applied conditional on
  not spiking). RESULT: late-drive behaviour now matches at the drive level (trail 4–8 punt 24.7 →
  7.9% vs 3.7; leaders on downs 15 → 2% vs 2; tied FG 11.5 → 18.5% vs 25.1; tied TD 13.5 → 7.8% vs
  4.8); tied at 2:00 → |final| = 3: 34 → 54% (real 80); tied at 5:00 → 3: 31.5 → 42.3% (62.3).
  **HEADLINE UNCHANGED: P(|final| = 3) 7.7 → 8.1% (14.5); |final| ≤ 7 41.4% (49.0).** The full
  |margin| histogram is a smoothed version of reality already at 5:00 (mass at 3 within the 1–3
  bucket 42.6% vs 56.5% real; off-numbers 1/2/4/9/11/13 +7pp; team scores 10/17/20 under, 13/23/26
  over): the scoring-event COMPOSITION (joint TDs × FGs per team and across teams) is the next
  diagnostic, not another endgame fix. Also surfaced: 4th-down conversion 44.9% vs ~57%; trailing
  two-minute drives from own territory expire 24% vs 0.9% (61–120 s starts); trailing offences
  turn it over 12% vs 35% at ≤ 2:00. Tests: 86 pass / 3 red (5A-3 go rate 21.2 vs 19.8 ± 1.0;
  5A-4 offence penalties 6.17 vs 5.51 ± 0.5; 5A-9 tied-drive expiry 12.4% vs ≤ 5%); three tests
  updated for changed premises (dead-table z10 per D27, kneel liveness per D33, D32 string).
  See `research/nfl_sim/phase5a9_endgame.md`. Next 5A-10: scoring-event composition diagnostic.
- **2026-09-16 Phase 5A-10 — scoring-event composition (Cowork-executed).** Per-team scoring
  events match reality on average (TDs 2.45 vs 2.38, XP-miss share 10.7 vs 10.2%, two-point 4.7 vs
  4.7%, FGs 1.59 vs 1.67, Q4-drive TDs 0.54 vs 0.55) but not in structure: given equal TD counts and
  a one-FG difference the real margin is exactly 3 in 71% of games, the sim's was 45% (off by one
  29% vs 10%). **D35 — two-point decision keyed by the EXACT post-TD differential** (period Q1-3 /
  Q4+ × −16…+16, complete grid, k by method of moments): the real decision is near-deterministic
  (down 2 / down 5 / up 1 / down 10 → ~97%; down 3 / down 7 / down 4 / tied → ≤ 4%) and the old
  7-bucket table smeared it (Q4 trail1-8 = 34% everywhere). **D36 — PAT uniform reuse:** `u_pat`
  decided the two-point question and then the XP make, so conditional on kicking the XP draw was
  biased (effective make ~92% in trailing Q4 states; K1 miss rate 6.2% vs 5.1%); the two-point
  conversion borrowed the OT coin-flip uniform. Own draws now. K1 (1,087 × 500): P(|m| = 3) 8.1 →
  **10.6%** (14.5); 3-composition exactness 45 → 61% (71); mass moved to 3/7/10/14 (7 and 10 now
  over: 9.1 vs 7.3, 6.2 vs 5.1), 6 short (4.5 vs 7.5), ties 0.88% (0.28). Measured, not fixed:
  corr(td_home, td_away) 0.12 real vs 0.01 sim (no shared game environment); Q4-drive FGs −13%
  (all in close games); OT ends tied 19% of OT games vs 4.3%; real one-TD-apart games land on 6
  in 24% (sim 11%). **D37 — test-cache pollution:** `test_dead_tables_5a5._run` left its last
  perturbation in the engine cache for every module that ran after it (the DPI-always-40-yards
  table before 5A-10; the all-two-point table in the first 5A-10 run, which read P(|m| = 3) 0.083),
  so full-suite results for `test_engine_5a*` from any run that included the dead-table module
  were contaminated; standalone module runs were clean. Fixed (restore after each run); the
  `assert True` two-point placeholder is a real perturbation test. Clean suite: 89 pass / 4 red
  (5A tie rate 1.04% > 1%; 5A-3 go rate 21.1 vs 19.8 ± 1.0; 5A-4 offence penalties 6.21 vs 5.51
  ± 0.5 — real, not pollution; 5A-9 tied-drive expiry 11.5% vs ≤ 5%). See
  `research/nfl_sim/phase5a10_scoring_composition.md`. Next 5A-11: OT behaviour (ties), placement
  of XP/two-point noise, shared game factor, Q4 FG count, 4th-down conversion, two-minute drill.
- **2026-09-17 Phase 5A-11 — overtime audit (Cowork-executed).** Real 2021–2024 OT (70 games,
  176 drives): 2.51 drives per OT; first drive TD 19 / FG 17 / punt 46 / TO 16%; later drives
  FG-heavy (25–57%); 3 ties (4.3%). Sim (5A-10): P(tie | OT) 18.7%, OT drives FG 13% / TD 21% /
  expiry 10%. Three rule defects found in the sim's OT drive sequences: matched first-drive FGs
  ended the game as a TIE (3.6% of overtimes); after a first-drive punt the other team's FG did not
  end the game (only a score or turnover on downs marked the first possession complete); after a
  first-drive FG the second team's empty possession did not end the game (the first team kicked
  again). **D38:** first possession completes when the first team's drive ends for any reason;
  a drive ending with both teams having possessed and the score not tied ends the game; a FG after
  the first possession ends the game only if the kicker leads — all on game state, not the drive
  log. **D39:** OT's last 3:00 uses the Q4 late cells (timeouts, runoff, kneel runoff).
  **D40:** sudden-death in-range state (`fg_setup` state `ot_sd`, n = 135): after the first
  possession, inside the 35 on downs 1–3 the offence kicks on the snap 18.5% of the time, passes
  29% of non-kneel plays, kneels 5%; the first OT possession is played for the TD and excluded.
  **D41:** the drive-log attr is a DataFrame subclass whose frame-level equality is identity —
  pandas compared drive logs element-wise on `pd.concat` and raised whenever the other attr
  happened to match (latent flake; surfaced in the 5A-11 suite run and made two 5A-3 tests error).
  K1 (1,087 × 500): P(tie | OT) 10.4% (was 18.7; real 4.3 ± wide), OT drives FG 24 / TD 15 / punt
  38 / expiry 4% (real 26 / 13 / 36 / 1), drives per OT 2.54 (2.51), P(OT) 4.9% (6.4), ties 0.50%
  (0.28), P(|m| = 3) 10.6 → **11.6%** (14.5), |m| = 7 8.7 (7.3), |m| = 6 4.4 (7.5). Tests:
  `test_engine_5a11.py` 3 green; 5A tie-rate test green again; 5A-6 liveness test updated for D40;
  suite 93 pass / 3 red (5A-3 go rate 21.1 vs 19.8 ± 1.0; 5A-4 offence penalties 6.20 vs 5.51 ± 0.5;
  5A-9 tied-drive expiry 11.5% vs ≤ 5%). See `research/nfl_sim/phase5a11_overtime.md`. Next: the
  5A-10 list — XP/two-point placement, shared game factor, Q4 FG count, 4th-down conversion,
  two-minute drill; then 5B, 5C.
- **2026-09-17 Phase 5B — usage layer repair.**
  **D42 — Frozen usage params.** `params_v1.json` gains a `"usage"` block with
  `share_half_life=4`, `k_share=20`, `frozen_at=2026-09-17`. `build_player_usage()` raises
  `ValueError` if the block is missing — no default fallbacks. The values are the Phase 1B
  grid-search winners (boundary at k=20; extension grid showed k=10 and k=5 were worse).
  **D43 — Starting-QB identity.** `derive_starting_qbs(depth, plays)`: three-layer priority
  (old-schema per-week depth chart > PBP prev-game leading passer > new-schema static
  depth chart). Starting QB with 0 in-season opportunities retains its prior-based blend
  (exempt from D14 1e-8 override). Backup QBs get share only from observed attempts — no
  prior influence. `is_starting_qb` boolean column added to the usage output.
  **Root cause of the MNF Fields attribution:** all KC QBs had zero 2026 touches, D14 zeroed
  them all to 1e-8, normalization gave each 1/16 = 0.0625 target share. After fix: Mahomes
  1.0000, Fields 0.0000, Nussmeier 0.0000 (STARTER flag on Mahomes, source: depth_chart).
  **D44 — depth_cols expanded.** `load_roster_data()` was stripping new-schema columns
  (`pos_rank`, `pos_abb`, `team`, `dt`) from the depth chart DataFrame, making `derive_starting_qbs`
  layer 3 inert. Fixed.
  Tests: `test_usage_5b.py` 6/6 pass (params read, share sums, KC wk17 face validity,
  starting-QB identity 100%, CAR zero-opp below prior, PIT byte-identity).
  See `research/nfl_sim/phase5b_usage_repair.md`.
- **2026-09-17 Phase 5B-fix — tuner/builder split, layer-3 scope.**
  **D45 — Tuner separated from builder.** `main()` is now build-only: reads
  `params_v1.json`, requires the `"usage"` block (raises if absent), never writes
  the file. A `--tune` flag runs the existing 2021-2024 grid search and writes
  `share_half_life`, `k_share`, `frozen_at` (UTC date), `frozen_commit`
  (`git rev-parse --short HEAD`), and `grid_results` into the `"usage"` block.
  The defect: every plain `python usage.py` run re-ran the 12-point grid and
  unconditionally overwrote `params["usage"]`, dropping `frozen_at`/`frozen_commit`.
  D42 was enforced inside `build_player_usage` but not at the builder's own entry point.
  **Layer-3 scope restricted.** `derive_starting_qbs` layer 3 (static new-schema depth
  chart) now only fills team-weeks with `season >= 2026` (prospective). For 2025
  historical weeks the snapshot post-dates the games; the key is left unset and the
  count of unset keys is logged. No 2025 team-week carries a layer-3 starting QB.
  Tests: `test_usage_5b.py` 9/9 pass (added (g) params file unchanged after plain
  main, (h) --tune writes frozen_at/frozen_commit and best=(4,20), (i) no 2025
  layer-3 QB and every 2026 wk2 team has one).
  See `research/nfl_sim/phase5b_usage_repair.md`.
- **2026-09-17 Phase 5C-1 — grader/pricer coherence, CRPS, QB identity, shared solver.**
  **D46 — Shared anchoring solver.** `anchor.run_anchored_chunked()` is the single
  anchoring routine, reading params from the `"anchor"` block in `params_v1.json`
  (n_sims=10000, chunk_size=2000, max_iter=8, damp_limit_pts=6, J_INV, J_FWD).
  `run_week.py` imports it. The old 4-iteration loop in `run_cal_players.py` is superseded.
  **D47 — CRPS fix.** `_crps_sample` had `/ (2*n)` instead of `/ 2` on the pairwise
  term (the pairwise `np.mean` already averages over n^2 pairs). Every prior K2 CRPS
  number is void.
  **D48 — td_player_id for ATD labels.** `actuals.actual_player_game_stats()` uses
  `td_player_id` (nflfastR canonical scorer) for anytime TD, catching return TDs and
  lateral scores. 348 player-games change across 2021-2024.
  **D49 — Grader void rule.** A player with no stat rows but active (on roster, team
  played) grades actual=0, not void. Void only if inactive/not rostered.
  **D50 — Engine QB identity.** Engine uses `is_starting_qb` from `player_usage_weekly`.
  For 2026+ it raises if no starter is flagged (never falls back silently). For 2021-2025
  it falls back to depth_order (the column was not backfilled).
  Throughput: 500 sim-games/s (5 games, N=10000, players ON). Projected 1087-game backtest:
  N=10000 20.5h, N=4000 8.2h, N=2000 4.1h, N=1000 2.1h. Jeff chooses N.
  Tests: `test_5c1.py` 8/8 pass. See `research/nfl_sim/phase5c1_report.md`.
- **2026-09-17 Phase 5C-1b — Cowork-verified gap closure.**
  **D46 amended.** `anchor_game` is now a thin wrapper around `run_anchored_chunked`
  (own loop deleted). `run_cal_players.py` rewritten to call `run_anchored_chunked`
  (4-iteration loop deleted). All three callers resolve to the same function object (test).
  **D50 amended.** QB identity tested on all 32 teams for 2026 wk2 (was KC only).
  For 2026+, raises if no `is_starting_qb`. For historical seasons with usage-table gaps
  (backup-QB weeks), warns and falls back to depth_order — not silent, but not blocking.
  **Sit-key rebuild.** `tendencies_situational_weekly.parquet` rebuilt with `int(down)` keys.
  Zero float-format keys on disk (asserting test). Engine playcall fallback raises KeyError
  instead of 0.55 literal. `ev_sit_proe_miss` counter added.
  **SGP.** `sgp_probability` alias deleted; only `sgp_probability_raw` and
  `sgp_probability_raked` exist. ESS returned as a count.
  **Usage hygiene.** `OUT_DIR` overridable by `NFL_USAGE_OUT_DIR`; tests (g)/(h) write
  to tmp_path. Layer-3 uses `current_season` from PBP files, not hardcoded 2026.
  **MNF re-grade.** v3: 30/30 graded (0 void, was >0 in v2); 9 hits, 21 misses.
  Tests: `test_5c1.py` 9/9, `test_usage_5b.py` 9/9.

### D51 — Anchor block N=5000, chunk_size=2500 (retro, 2026-09-17)
params_v1.json anchor block: n_sims=5000, chunk_size=2500, divisibility assertion
in anchor.py. run_week.py --n-sims CLI override deleted; N comes from anchor block
only. Rationale: consistent N across fit and live; 5000 gives SE ~0.2 pts.

### D52 — Dead-table clock metric (retro, 2026-09-17)
Clock test metric changed from ev_clock_used to plays per game (ev_pass+ev_rush).
Paired test: mean(d)<0, |mean(d)|>3*SE. The ev_clock_used counter was not a direct
clock measurement; plays-per-game is more interpretable and testable.

### D53 — opp==0 prior path (2026-09-17)
Deleted the 1e-8 override for opp==0 players. The shrinkage formula already returns
the D14 prior when opp=0 (own s-1 share if >= 50 team opp, else depth-order league
mean). Starting-QB exemption removed (unnecessary — all positions get the prior).
Week-1 QB carry share: 0.04-0.05 (was 0.996 before fix).

### D54 — QB starter: depth_order, no touches heuristic (2026-09-17)
derive_starting_qbs: roster-at-game-time validation added (active_universe param).
Builder re-flags by depth_order when starter is inactive (was "most touches").
Team-specific roster filter prevents cross-team QB leakage (e.g., Flacco on PHI
wk18 2021). Fixes 2021_13_PHI_NYJ, 2023_09_ARI_CLE, 2023_15_MIN_CIN.

### D55 — Runner halts on error (2026-09-17)
run_fit.py: no except-and-continue. Any exception propagates through the pool and
exits non-zero with the game_id. Error parquet path deleted.

### D56 — Calibration maps fitted on fit_5c2b (2026-09-18)
22 isotonic families fitted on 1087/1087 converged games (engine b86967a39, N=5000).
Game families: margin_side, total_side, team_total. Prop families: rec/rec_yds/
rush_yds/rush_att/atd per position (WR/TE/RB/QB) + pass_att/cmp/yds/td for QB.
A6: one-sided coherence enforced (cal_over + cal_under == 1 exactly).
A7: board trust filter (rankable = Hard Rock price AND converged).
All maps monotone. Synthetic identity test: max 0.015 < 0.02/decile.
K4: in-sample only (no Hard Rock closing prices). Symmetry check fails as expected.

### D57 — Real-price K4 from fit_5c2b (2026-09-18)
72,850 legs graded against 6-book consensus closing (2023-24). Symmetry check
(|sum - 2/total_imp + 2| < 2pp): 7/8 PASS; pass_yds FAIL at 2.7pp (matching
bug). No family has positive flat-over ROI (consistent with D17). Synthetic
-110 K4 deleted from calibration_v1.json. Reliability deciles relabelled as
in-sample fit check (isotonic reproduces its own deciles by construction).
OOS reference corrected: prospective 2026 only; 2025 consumed.

### D58 — MOVED-AGAINST flag, pre-registered (2026-09-18)
A leg whose Hard Rock line or price moved against the pick between the open
snapshot and pick time is flagged MOVED-AGAINST on the board. "Moved against"
means: for an over pick, implied_over at open < implied_over at pick time (the
market moved toward the over, making the pick less valuable); for an under pick,
implied_under at open < implied_under at pick time. The flag is displayed but
not acted on automatically. Its hit rate is reported prospectively by week.
Nothing about this filter is tuned on 2026 data — it is pre-registered before
any open/close captures are used.

### D59 — Depth provenance rule (2026-09-18)
New-schema depth chart (pos_rank, dt) fills depth_order ONLY from snapshots
with dt strictly before the week's first kickoff (from PBP game_date). Rows
with no eligible snapshot keep NaN depth_order and use the position-only league
prior. Eliminates class-1b leak of 2025+ depth data into 2021-24 usage.
Test: 2024 byte-identical with and without new-schema depth data.

### D60 — Traded-player rows (2026-09-18)
Roster insertion keys on (player_id, team) not player_id alone. A traded player
with old-team PBP history still gets a new-team row on debut. Tested with
McCaffrey SF wk7 2022, Hockenson MIN wk9 2022, Adams NYJ wk7 2024, Cooper BUF wk7 2024.

### D61 — s-1 aggregate prior (2026-09-18)
Prior is the player's opp-weighted aggregate share across all depth groups (not a
single depth-group row). Docstring updated to match code: pw_eff = prior_weight *
k_share / (n_eff + k_share) decays with evidence. 1,465/4,478 players had multi-
depth-group pss rows that were previously deduplicated arbitrarily.

### D62 — Official stat definitions in actuals.py (2026-09-18)
Rushing attempt universe is play_type in {run, qb_kneel} AND rusher_player_id
not null AND two_point_attempt != 1. Kneels are official rushing attempts and
their negative yardage is kept; two-point runs are not rushing attempts. Passing
attempt universe is play_type in {pass, qb_spike} AND down not null AND sack != 1
AND passer_player_id not null; a spike is an attempt with 0 yards and no
completion. Receiving and anytime-TD are unchanged — spikes have no receiver, so
the receiving universe stays on play_type=="pass".
Measured in 2024 PBP: +437 kneels, -38 two-point runs (net +399 carries), +75
spikes. Test: nfl/sim/tests/test_actuals_5d3.py asserts those exact deltas, plus
a null control that actual_rec, actual_rec_yds and actual_atd are unchanged.

### D63 — K4 is reproducible, and is re-graded on D62 (2026-09-18)
K4 had no committed generator; k4_rows_fit_5d1.parquet came from an ad-hoc
script, so the result was not reproducible (Check 3). nfl/sim/run_k4.py is now
the generator. It first regenerates the committed row file under the OLD actuals
and asserts a row-for-row match before re-grading under D62, so only grading can
change. Output: research/nfl_sim/k4_rows_fit_5d1_official.parquet.
Pricing convention, stated once: raw_side = devig_side * (1 + 2*vig); vig is the
per-side half margin and the two-way overround is ~1.069.
Result: exactly 158 rows change, in hit_over/hit_under only — rush_att 94,
rush_yds 58, pass_att 6, all other families 0. QB rush_att blind under goes from
+18.2% ROI / 63.3% hit / +13.2pp edge / t=+5.33 (N=722) to -4.5% / 51.5% /
+1.4pp / t=-1.28, collapsing independently in both seasons (2023 +19.9% -> -0.8%,
2024 +16.9% -> -7.1%). After D62 no family has a positive blind side. The
pre-registered prediction held; the continuous-market null control is
bit-identical. Independently recomputed from the two parquets by Cowork.
See research/nfl_sim/k4_official_actuals_2026-09-18.md and
research/nfl_sim/k4_fit5d1_actuals_contamination_2026-09-18.md.

### D64 — CLV on one scale, with game identity, and push = void (2026-09-18)
CLV is computed on the no-vig scale on both sides: implied_over/implied_under are
normalized to sum to 1 at pick time and again at close, and
CLV = close_devig[side] - pick_devig[side]. Previously both sides were raw
vig-inclusive, which returned about +2.4pp on an unchanged -110/-110 market.
The closing-price lookup now requires game identity (event_id / season+week+game)
instead of matching on player_name + market_key + line and taking the first row
across the whole season, which could match a different week. No match for that
game returns NaN rather than falling through. Family vocabulary is unified to one
set and an unmapped family raises instead of silently returning NaN. A leg whose
actual equals the line is graded VOID and excluded from both the ROI and hit-rate
denominators — never assigned to a side by complement. Note 72,893 of 72,897 prop
lines are half-point, so pushes bind mainly on whole-number and game markets.
Test: nfl/sim/tests/test_clv_5d3.py.

### D65 — Exact binary IPF in SGP raking (2026-09-18)
sgp_probability_raked scaled only the hit rows by t/m and then renormalized
globally, which leaves the leg's marginal at t/(t+1-m) rather than t, so every
pass undershot the target. The update is now the exact binary IPF step:
hits *= t/m, non-hits *= (1-t)/(1-m), which makes the marginal equal t after one
step and is exact for a single leg. The silent `if current_marginal < 1e-15:
continue` branch — which returned a joint as if an unhittable leg had been
honoured — now raises, as do unsupported targets: m == 0 with t > 0, m == 1 with
t < 1, and t outside (0, 1). The 200-iteration cap, the 1e-6 tolerance, the
RuntimeError on non-convergence and the ESS definition are unchanged.
Test: nfl/sim/tests/test_raking_5d3.py.

### D66 — OT Try rules: no PAT after walk-off TD (2026-09-18)
_handle_td determines the walk-off set BEFORE the PAT. Walk-off (no Try):
pre-2025 REG any OT TD; defensive OT TD (any season); sudden-death TD where
the scorer leads. A Try IS attempted on first/second-possession TDs under
2025+ REG and any postseason, because the Try decides ahead/tied/continue.
2025+ REG tying TD: after both possessions, a TD that only ties does NOT end
the game — play continues in sudden death (next score wins). This is NOT
another round of paired possessions (the postseason ot_sudden_tied reset is
correct for postseason, wrong for REG and is not copied).

### D67 — Kickoff start table: measured, not hardcoded (2026-09-18)
tables.py kickoff builder now measures start_yl100 as the median yardline_100
of the play immediately after each kickoff. The literal 75.0 is deleted.
Measured values: 2021=75 (N=2874, mode 60.4%), 2022=75 (N=2796, 61.8%),
2023=75 (N=2816, 77.7%), 2024=70 (N=2911, 64.7%), 2025=69 (N=2900, 20.0%).
SD: 8.6/8.2/6.5/7.5/9.6. 2024 was 5 yards wrong (table said 75, actual 70).
2025 modal coverage is 20% — one scalar describes a fifth of its drives.
touchback_rate is computed by the builder and never read by the engine;
left in place but noted here.
fit_5d1 used the wrong 2024 value (75 instead of 70); a re-fit is required.

### D68 — detect_week from schedule, not PBP alone (2026-09-18)
detect_week uses the nflverse schedule (all games, including unplayed) to find
the first week with incomplete games. A game is complete if its game_id appears
in PBP (any row exists), not a score threshold — a shutout (home_score==0) is
no longer misread as incomplete. Prevents advancing past a week once TNF is in
PBP but Sunday games are not. --week override behavior unchanged.

### D69 — Props snapshot selection by tag precedence (2026-09-18)
load_props_for_game selects by snapshot_tag: close > mid > open (highest
precedence tag PRESENT for that game). Within a tag, latest pull_timestamp wins.
Returns (DataFrame, chosen_tag, chosen_timestamp). Raises ValueError on an
unknown tag rather than falling through. Tag vocabulary: open, mid, close per
pull_hardrock_props.py.

### D70 — Pricer wired into the board with metadata gate (2026-09-18)
price_game and sgp_probability_raked imported into run_week. Before pricing,
_check_calibration_stamp compares calibration_v1.json stamps (engine_commit,
usage_file_sha256) against the running state. On mismatch: sim prices
suppressed, board still renders with stated reason. The gate FIRES after D66
(engine changed) — this is the correct outcome, not a bug to work around.
A multi-leg ticket's joint comes from sgp_probability_raked, not from a
product of marginals.

### D71 — Layer logging schema, pre-registered (2026-09-18)
Every leg on the board logs one row to nfl/data/sim/outputs/week=YYYY_WW/
layer_log.parquet with: season, week, game_id, player_id, player_name,
position, family, line, side, sim_p_raw, sim_p_calibrated, book_price,
book_implied, moved_against, snapshot_tag, snapshot_timestamp, tier,
status, rankable, sim_pricing_enabled, board_generated_utc.
All layers ON. Ablation is a QUERY against this log later — nothing is
tuned on 2026 data.

### D72 — Metadata gate on a content fingerprint, not a git commit (2026-09-18)
D70 compared `cal["engine_commit"]` against `git rev-parse HEAD`. That gate cannot
work here: the Mac dashboard auto-committer moves HEAD every 30 minutes, so the
stamp goes stale within half an hour of every re-fit, permanently, on commits that
never touched the engine — and a gate that is always red is a gate that gets
ignored. (HEAD moved twice during the session that wrote this entry.) A commit
comparison is also blind to UNCOMMITTED edits: fit_5d1 was produced by a
`run_fit.py` that was uncommitted at the time, so a commit-based stamp would have
recorded a hash that did not describe the code that ran.

`calibration.engine_fingerprint()` is sha256[:16] over the content of the files
that determine the simulated distribution: `nfl/sim/engine.py`,
`nfl/sim/anchor.py`, `nfl/sim/params_v1.json`, and every file in
`nfl/data/sim/tables/`. It raises if an input is missing — a fingerprint over a
partial set would compare equal across a real change. `engine_commit` is still
written, as information for humans, and is NOT gated on.

Boundary, chosen deliberately: `nfl/sim/pricer.py` is NOT in the fingerprint. The
raking and SGP code there does not change a leg's marginal probability, and
including it would fire the gate after a raking-only fix — the spurious-red
failure this decision exists to prevent. If `price_game`'s LEG CONSTRUCTION
changes, add it and record that here.

Second half of the defect: no committed code wrote the stamp at all.
`engine_commit` / `usage_file_sha256` / `fit_dir` / `fit_n_games` /
`unconverged_share` appeared in no `.py` file — the stamp on disk was written by
hand during 5D-1 item 4, the same reproducibility gap K4 had before D63. Worse,
`save_calibration()` wrote an older schema (`{"git_sha", "maps"}`) and would have
silently stripped the whole stamp if anyone had called it. `save_calibration()` is
now the writer: it computes both fingerprints, takes the fit metadata as
arguments, and merges into the existing file so a partial call cannot drop the
anchor block.

The stamp in the repo today carries no `engine_fingerprint`, so the gate fires
with "this stamp predates D72 and was written by hand; a re-fit is required to
produce a gateable stamp". That is correct and expected — it is also true that the
engine changed under D66/D67 and that fit_5d1 used the wrong 2024 kickoff value.
The re-fit resolves all three at once.

Tests (`test_board_5d2.py`): the fingerprint is deterministic; it moves when an
engine file or a table changes; a missing input raises; a matching stamp passes;
**a stamp with the correct fingerprint but a deliberately wrong `engine_commit`
still passes** — that test encodes the auto-committer case and fails against the
D70 gate; a wrong fingerprint fires; a pre-D72 stamp fires. The D70 test it
replaced asserted nothing when the gate passed and so could not fail.

Remaining gap, stated rather than hidden: `save_calibration()` is now the correct
writer but **nothing calls it yet**. The step that fits the isotonic maps and
writes `calibration_v1.json` does not exist as committed code — same gap K4 had
before D63 and the stamp had before this entry. Whoever runs the re-fit must call
`save_calibration(cal_maps, fit_dir=..., fit_n_games=..., unconverged_share=...,
anchor=...)` rather than hand-writing the JSON, or the new stamp will again be
ungateable. Wiring that call is part of the re-fit, not of this decision.

### D73 — run_fit.py --out-dir (required, no default) (2026-09-18)
OUT_DIR was hardcoded, which is why fit_5d1 was produced by an uncommitted
one-line edit. --out-dir is now required (no default). Refuses to write into
a directory with existing fit_census.parquet unless --force. GAMES_DIR
derived from --out-dir. Example:
  python3 nfl/sim/run_fit.py --seasons 2021 2022 2023 2024 --out-dir fit_5d2

### D74 — run_cal_maps.py: map generator from fit checkpoints (2026-09-18)
nfl/sim/run_cal_maps.py reads fit_<dir>/games/*.parquet, fits isotonic maps,
and writes calibration_v1.json via save_calibration (the D72 stamp writer).
Faithfulness against fit_5d1 with --legacy-actuals: 20/21 families reproduce
to 0.0 y_diff. The one mismatch (prop_rush_att_QB) is a precedence bug in the
original inline script: `int(val.iloc[0] if len(x) else 0 >= k)` returns the
raw carry count instead of a boolean, producing a map clipped to y=0.99 across
the domain. The generator's `int(actual_ra >= k)` is correct.
reliability_deciles.parquet exists in fit_5c2b, is missing from fit_5d1, and
has no writer in any .py file. It is UNOWNED — add it to a future generator
revision or delete the fit_5c2b copy.

### D75 — fit_5d2: re-fit on corrected engine (2026-09-18)
python3 nfl/sim/run_fit.py --seasons 2021 2022 2023 2024 --out-dir fit_5d2
Engine: D66 OT rules + D67 measured kickoff (2024=70, 2025=69).
1087/1087 converged, 0% unconverged, mean 3.0 iter, |err_m| 0.156,
|err_t| 0.135. Wall clock ~90 min (8 workers), mean 39.9s/game.
engine_commit: 7f5a808c5. Comparable to fit_5d1 (95 min, mean 3.0 iter).

### D76 — Maps from fit_5d2, gate green, K4 re-run (2026-09-18)
run_cal_maps.py --fit-dir fit_5d2 → calibration_v1.json via save_calibration.
21 families fitted. D72 gate GREEN (engine_fingerprint and usage_file_sha256
both match). K4 at real closing: all cells identical to fit_5d1 (post-D62)
within 0.1%. No positive blind side. Null control (2023 hits unchanged): PASS.

### D77 — Usage fingerprint covers the fit window only (2026-09-19)
D72 hashed the WHOLE usage file. Refreshing the nflverse inputs and rebuilding
usage on 2026-09-19 changed only 2026 rows, yet the whole-file hash moved and the
gate went red on a fit it cannot affect. Measured: the 2021-2024 block came out
BIT-IDENTICAL across that rebuild — 36,273 usage rows and 57,261 active-universe
rows, full-frame `.equals()` True — so the maps, fitted exclusively on 2021-2024,
could not have changed. A 90-minute re-fit would have produced byte-identical maps.

`usage_fingerprint(fit_seasons)` now hashes only the fit-window rows, sorted on
(season, week, team, player_id) and hashed column-wise so parquet re-encoding and
row order cannot move it. `save_calibration` records `fit_seasons` in the stamp, so
the gate is self-describing; a stamp without that key predates D77 and falls back
to [2021, 2022, 2023, 2024]. Verified: the narrowed fingerprint is `3194119bf5bc85cf`
on BOTH the pre-refresh and post-refresh usage files.

This is not a workaround to reach green. A gate that reddens on every routine data
refresh is the same spurious-red failure D72 was written to prevent — it trains
everyone to ignore it, which is how the pre-D72 gate would have died. The gate now
detects what it is for: did the data the maps were fitted on change.

`calibration_v1.json` was re-stamped through `save_calibration` (the D72 writer, not
by hand) with the existing 21 maps unchanged — asserted `after["maps"] == maps`.
No re-fit. Gate returns ok=True.

**Residual assumption, unchanged by this and still open:** maps fitted on 2021-2024
are assumed to transfer to the live season. D77 narrows what the gate watches; it
says nothing about that assumption, which remains untested.

Tests (`test_board_5d2.py`): a 2026-only change does NOT move the fingerprint (this
test fails against the pre-D77 whole-file hash — verified); a single 2021-2024 cell
DOES move it; row order does not.

### D78 — IPF convergence is judged after a full sweep (2026-09-19)
D65 implemented the exact binary update correctly but left the convergence check
INSIDE the per-leg loop, measuring each leg's error immediately after setting that
leg exactly. `max_err` was therefore ~0 by construction and the loop broke on the
first sweep every time, leaving earlier legs off target while the leg set last
looked perfect. ChatGPT audit #3 reproduced it: requested 60%/70%, final marginals
68.18%/70%, returned joint 60% against a correct 54.57%.

The check now runs after a complete sweep, across all legs. Also added: two legs
with identical indicator columns but different targets are unsatisfiable (if A and
B hit in exactly the same sims then P(A)==P(B) under any reweighting) and now
raise; and a marginal collapsing to 0 or 1 mid-rake raises rather than dividing.

Verified by execution on a frozen 4-leg fixture that needs 7 sweeps: the fix lands
every marginal within 4.3e-07 of target, while the old inside-the-sweep logic
misses by up to 3.36pp. `test_old_inside_sweep_check_would_fail_this_fixture`
guards that the fixture still discriminates.

**A prior test encoded the bug as its expected answer.** `test_two_correlated_legs`
built two IDENTICAL columns, asked for 0.7 and 0.5, and asserted the joint equals
min(t1,t2) — which only held because the broken loop exited after setting the
second leg. Replaced with the raise, plus a nested-threshold test (over 4.5 implies
over 3.5) which is the satisfiable case that actually occurs on a board.

### D79 — The calibration stamp enters the ranking decision (2026-09-19)
D70's gate was decorative. `if not sim_pricing_enabled:` appended the text
"**SIM PRICES SUPPRESSED**" to the markdown board and did nothing else; `rankable`
was `has_book and converged` and never consulted the stamp, so a red stamp shipped
calibrated, ranked legs into the cross-game top 20 exactly as a green one did.
ChatGPT audit #3 reproduced this on a real board run. A gate that announces
protection while providing none is worse than no gate, because it is trusted.

`is_rankable(has_book, converged, sim_pricing_enabled)` is now the single decision
point and the "Not rankable" line names the stamp when that is the cause. Tests
assert a red stamp yields zero rankable legs, a green stamp still ranks, and the
call site passes the stamp rather than recomputing the old expression.

### D80 — WITHDRAWN: D70 never wired the pricer into the board (2026-09-19)
D70 claimed "pricer + raked SGP wired into run_week". It added
`from nfl.sim.pricer import price_game, sgp_probability_raked` at run_week.py:28
and **no call site**. `grep -n "price_game(\|sgp_probability_raked("` on run_week.py
returns nothing; ChatGPT audit #3 instrumented a board run and recorded zero calls.
This is the SAME defect audit #2 found ("the raked function's only callers are
tests"), so it survived an entire phase that claimed to fix it — because
verification read the diff and saw the import.

It is withdrawn rather than patched, because the integration D70 described does not
exist as a small change:
  * the board is SINGLE-LEG. It writes `parlay_board.md` but builds no parlay — no
    leg matrix, no joint, no SGP anywhere. `sgp_probability_raked` has nothing to
    consume until multi-leg ticket construction exists, which is a feature, not a
    fix.
  * `price_game` prices TEAM markets (margin, total, 1H) from `team_df` and returns
    the SGP leg matrix. The board's player props are computed inline from player
    sims. They are complementary code paths, not duplicates, so there is no
    one-line call that makes the claim true.
Manufacturing a call site to close the finding would be worse than the finding.
A real SGP board is scoped as its own phase.

### D81 — Fingerprint covers every fit input, not usage alone (2026-09-19)
ChatGPT audit #3 showed the D77 fingerprint watched `player_usage_weekly` only:
removing a player from a HISTORICAL active lineup, and altering HISTORICAL team
passing EPA, both changed the simulated sample while the gate stayed green. The
fingerprint now covers all eight season-keyed ratings artifacts
(`FIT_INPUT_FILES`), each restricted to the fit window for the D77 reason, and
raises on a missing input.

Verified by execution against the real ratings files: perturbing a 2023 value in
`active_universe_weekly` (depth_order), `player_usage_weekly` (carry_share),
`team_ratings_weekly` (epa) and `tendencies_weekly` (proe) is CAUGHT in all four
cases, while the same perturbation on 2026 rows is IGNORED in all cases.
(A first attempt appeared to miss the active-universe case; the perturbation was
NaN*1.5+0.123 = NaN on a ~43%-null column, i.e. a no-op test, not a gate failure.)

**Still open, from the same audit:** `save_calibration` stamps the CURRENT
environment rather than verifying the environment that produced the checkpoints, so
a watched input can be changed, reddening the gate, and then re-stamped green
without fitting anything. The stamp should be derived from the fit run, not from
the moment of writing.

### D82 — MOVED-AGAINST: like-for-like scale, correct side, None when unmeasured (2026-09-19)
ChatGPT audit #3 flagged two defects in the D58 movement layer. Reading the code found
three, and all three meant the pre-registered flag was not measuring what it claimed.

**1. Scale mismatch — the flag could not fire.** `book_implied` was de-vigged
(`imp_o / (imp_o + imp_u)`) while the stored opening value was `implied_over`, RAW
and vig-inclusive. On an unchanged −110/−110 market the comparison was
`0.5000 > 0.5238` — False by construction — and no move smaller than the book's
margin (~2.4pp) could ever trip it. Same class of error as the CLV scale bug D64 fixed.

**2. Wrong side for unders.** The `over` and `under` branches were byte-identical
(`moved_against = book_implied > open_imp` in both). For an under leg that compared
the de-vigged UNDER probability against the RAW OVER implied — two different
quantities on two different scales.

**3. Absence recorded as a negative observation.** `moved_against` was initialised
to `False` and only overwritten when an opening snapshot existed, so "no open
captured" was indistinguishable from "measured, did not move against". **Every leg
on the Week 2 board was in that state**, since only one snapshot covers that slate.
An ablation cannot subtract a layer it believes it measured.

Fixed by `devig_side(imp_over, imp_under, side)` — one helper used for BOTH the
pick-time price and the opening price, so the comparison is like-for-like by
construction — and `compute_moved_against(...)`, extracted so it is testable rather
than inline in `build_board`. The opening snapshot now stores both raw sides so it
can be de-vigged per side at comparison time. A one-sided quote compared against a
two-sided one returns None rather than a number, because one carries the margin and
the other does not.

Verified by execution, seven cases: unchanged market → False on both sides; over
priced up → True for over and False for under; under priced up → True for under and
False for over; no snapshot → None. The old logic was run on the unchanged-market
case and returns False, confirming the tests discriminate.

**Consequence for the pre-registered design:** every `moved_against = False` already
written to a layer log predates this fix and is uninterpretable — it may mean "not
measured". Layer logs written before D82 should not be used to score this layer.

### D83 — The stamp describes the fit run, not the moment of writing (2026-09-19)
ChatGPT audit #3's sharpest finding: `save_calibration` computed the fingerprints
live, so a watched input could be changed (reddening the gate) and the unchanged
maps simply re-saved to get green again — without fitting anything. The audit
demonstrated it. So did the D77 re-stamp in this project, which was legitimate on
the evidence but used a mechanism that permits an illegitimate version.

`run_fit.py` now writes `fit_meta.json` into the fit directory at fit time,
recording `engine_fingerprint`, `fit_inputs_fingerprint`, `fit_seasons`,
`engine_commit` and `n_games` for the environment that actually produced those
checkpoints. `save_calibration` requires `fit_dir`, reads that file, and stamps
from it. A fit with no `fit_meta.json` cannot be stamped from at all.

The behavioural consequence, verified by reproducing the attack end to end:
perturb `kickoff.parquet` (a watched engine input) → gate red
(`cal=d929ad258504b275, live=e93213a3319da`); re-save the unchanged maps → **still
red**, because the stamp carries the fit's fingerprint and re-saving cannot launder
it; restore → green. Pre-D83, step two returned green.

**`fit_5d2` carries a backfilled `fit_meta.json`**, and this is the only fit
permitted to. It predates D83, so re-fitting was the alternative. The backfill is
justified because both fingerprints were VERIFIED unchanged between the fit commit
`7f5a808c5` and now, not assumed: `git diff 7f5a808c5..HEAD` over `engine.py`,
`anchor.py`, `params_v1.json` and `nfl/data/sim/tables/` is empty, and
`usage_fingerprint` computed against the ratings files as they were at that commit
equals the live value `840412f7295a8323`. The justification and the verification are
recorded inside the file itself under a `backfilled` key. Every fit from D83 onward
writes its own at fit time.

Tests: the stamp carries the FIT's fingerprints and not the live ones (with an
assertion that the fixture still discriminates); `fit_dir` is required; a fit
without `fit_meta.json` raises; and re-stamping cannot launder an environment
mismatch.

### D85 — PIT test for D59/D60; D61 coverage statement (2026-09-19)

`nfl/sim/tests/test_usage_pit_5f.py` — three tests, all green.

**D59 (depth provenance):** `test_d59_pit_depth_truncated` builds usage for
2025 wk5 twice: once with full depth data, once with all depth rows having
`dt >= kickoff(wk5)` removed. Both builds produce byte-identical week-5 output
(all float columns within 1e-12). This is the D59 claim: new-schema depth
snapshots with dt at or after the week's first kickoff are excluded.
Removed 934,141 depth rows in the truncation — the filter is not vacuous.

`test_d59_negative_control` injects a synthetic depth row with
`dt = kickoff + 1 hour` that promotes an ARI RB from depth > 1 to depth 1.
Verifies that: (a) the target player exists in the output, (b) the player's
pre-kickoff depth is NOT rank 1 (so the injection would be meaningful), and
(c) D59's filter makes both builds identical despite the injection. If D59
were broken (not filtering by dt), the injected row would change the player's
depth_order and hence their prior, producing different shares.

**D60 (traded players):** `test_d60_traded_player_debut` verifies McCaffrey
appears on SF with non-zero carry_share and target_share in 2022 wk7 (traded
from CAR), and Hockenson appears on MIN with non-zero target_share in 2022 wk9
(traded from DET).

**D61 (s-1 aggregate prior):** NOT DIRECTLY TESTED. D61 changed the prior from
a single depth-group row to an opp-weighted aggregate across all depth groups.
This affects shrinkage values but not PIT identity — a direct test would require
the old code path to compare against, which no longer exists. The D59 PIT test
implicitly covers structural correctness: if the aggregate prior introduced a
time leak, the PIT assertion would catch it.

### D86 — Three standing engine reds are ENGINE DEFECTS, not stale targets (2026-09-19)

All three hardcoded targets re-derived from `nfl/data/pbp/pbp_2021..2024.parquet`
by `nfl/sim/tests/derive_engine_targets.py` (committed script). All three match
their hardcoded values exactly.

**(1) test_engine_5a3.py:67 — 4th-down go rate.**
  Target: 0.198 (3,085 go / 15,579 4th-down decisions, weeks 1–18, 2021–2024).
  Re-derived: **0.1980** — matches the hardcoded value to 4 decimal places.
  Sim value (from prompt): 0.210. Delta: +0.012, spec: < 0.010.
  **Classification: ENGINE DEFECT.** The engine generates 4th-down go attempts
  1.2pp above the measured rate. The D23 GOE fix (5A-3) and the D30 table rebuild
  (5A-9) reduced this from 23.2% to ~21%, but the residual 1.2pp persists. The
  5A-2 diagnostic traced the excess to table granularity. Do NOT widen the
  tolerance — the target is correct. Fix requires finer table cells or a
  supplementary correction, which is a Phase 5A-12+ item.

**(2) test_engine_5a4.py:75 — offense penalties per game.**
  Target: 5.51 (5,993 offense no-play penalties / 1,087 games, weeks 1–18).
  Re-derived: **5.513** — 5,993/1,087 exactly as the test comment states.
  Sim value (from prompt): 6.20. Delta: +0.69, spec: < 0.5.
  **Classification: ENGINE DEFECT.** The engine overproduces offense penalties by
  ~12.5%. The penalty_detail table drives penalty generation; the rate or the
  game-context conditioning is too aggressive. Do NOT widen the tolerance. Fix
  requires auditing the penalty rate table and its draw frequency in the engine.

**(3) test_engine_5a9.py:143 — tied drives reaching the 35 that expire.**
  Target: 0.0 (0 of 329 tied Q4 drives that reached the opponent's 35 expired
  without a kick, 2021–2024).
  Re-derived: **0.0000** — confirmed 0/329.
  Sim value (from prompt): 0.111. Tolerance: ≤ 0.050 (= target + 0.05).
  **Classification: ENGINE DEFECT.** 11.1% of the sim's tied drives reaching
  range expire without a kick, vs 0% in reality. The D33 FG-setup state (5A-9)
  reduced this from ~14% but did not eliminate it. The remaining expiries likely
  come from: (a) the clock advancing past the kick window despite the kneel
  table, or (b) the FG-setup state not triggering for all qualifying situations.
  Do NOT widen the tolerance — 0/329 is not a coincidence. Fix requires
  instrumenting the engine's FG-setup state activation to find missed entries.

**Summary:** all three are ENGINE DEFECT (category b). All three targets are
correct for the current fit window. All three are left RED with this recorded
explanation. None requires a tolerance change. The derivation script is committed.

### D84 — Props cron was not firing: entries installed after all scheduled slots (2026-09-19)

**What was wrong.** The three `pull_hardrock_props.py` cron entries were installed
at `2026-09-18T02:50:32 UTC` (Friday). Every scheduled slot before that date
(Tue 10:00, Thu 22:00, Sun 15:00) predates the install — no firing opportunity
existed. Syslog confirms zero CRON lines matching `pull_hardrock_props` across
all rotated logs back to Sep 6. The four existing 2026-09 pulls
(Sep 13 11:28, Sep 14 18:10, Sep 17 12:50, Sep 18 02:50) were manual runs; only
the last carried a snapshot_tag (`mid`), the earlier three had `tag=None`.

**Secondary issues found.**
(a) Log path was relative (`logs/props_capture.log`), which works after `cd` but
every other cron entry uses absolute paths — inconsistency risk. Fixed to
`/root/mlb-model/logs/props_capture.log`.
(b) Thursday close used `--window-hours 4` (original crontab), but the documented
schedule specifies 12. At 4h only TNF games are captured; Sunday slate is missed.
Fixed to `--window-hours 12` to match the documented schedule.

**Fix.** Removed the three old entries, added three corrected ones with absolute
log paths and correct `--window-hours`. Interpreter path was already absolute
(`/root/mlb-model/venv/bin/python3`) — correct per CLAUDE.md cron trap.

**Execution trace.** Scheduled a one-off test entry at `6 15 19 9 *` (dry-run);
syslog shows `2026-09-19T15:06:01 CRON ... pull_hardrock_props.py ... --dry-run`;
log file created with 16 events listed, key fingerprint `ac6e89a0`, balance 8,698.
Then scheduled a real pull at `11 15 19 9 *`; syslog shows
`2026-09-19T15:11:01 CRON ... pull_hardrock_props.py --window-hours 168 --tag open`;
log shows 16 events pulled (150 credits used, remaining 8,548); archive at
`data/odds_archive/nfl/props/season=2026/month=09/data_2026_09.parquet` grew from
4,737 to 5,710 rows, with 973 new rows carrying `snapshot_tag='open'` and
`pull_timestamp='2026-09-19T15:11:02'`. Both one-off entries removed after
verification.

**Final crontab (UTC):**
```
0 10 * * 2  --window-hours 168 --tag open    # Tue 6am ET
0 22 * * 4  --window-hours 12  --tag close   # Thu 6pm ET
0 15 * * 0  --window-hours 12  --tag close   # Sun 11am ET
```

**Key fingerprint:** `ac6e89a0` (matches paid account `.env` on VM).
**Credits:** 8,548 remaining after this verification (threshold 3,000).

### D87 — The D59 negative control was not a control (2026-09-19)
D85 shipped `test_d59_negative_control` reporting "synthetic future rank-change row
correctly filtered out". It injected a future-dated row and asserted the output was
UNCHANGED — which is the same assertion as `test_d59_pit_depth_truncated`, so it
demonstrated nothing about whether the injected row could have mattered. The file
said so itself: *"the test needs to verify the MECHANISM differently"* — and then
did not, falling back to two sanity checks (player present in output; pre-kickoff
rank > 1), neither of which establishes potency.

Replacing it with a real control — same row, same rank change, differing only in
`dt` (one hour before vs after kickoff) — made it **FAIL**: the row was inert even
when validly dated. Cause: D59 fills only where `depth_order` is NaN
(`usage.py` ~440, `fill_mask = depth_order.isna() & new_depth.notna()`), and the
target had been selected *from* the depth data, so it already had an eligible
snapshot and could never be filled.

The control now selects a player with NO pre-kickoff snapshot (therefore NaN
`depth_order`, therefore fillable), asserts the before-kickoff injection CHANGES
week-W output, and then asserts the identical row dated after kickoff does NOT.
That isolates the D59 date filter rather than restating the main test. It skips with
a stated reason if no fillable target exists.

**This is the first test that actually exercises D59.** The prior evidence was a
2024 byte-identity check (which cannot exercise the 2025+ `dt` path at all) and a
control that could not fail.

Unchanged from D85 and correct: D60's traded-player assertions, and the plain
statement that D61 is not directly tested.
