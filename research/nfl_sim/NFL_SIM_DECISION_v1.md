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
