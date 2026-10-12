# ChatGPT audit of ON-1 — reply saved verbatim (received 2026-10-12, pinned to c23e62419919b2da6d43df5dfe8b8ce5c2c3cc2e)

**NO-GO for treating 2024 as a clean, one-shot out-of-sample test.** The reported historical direction score reproduces, but the experiment uses future-informed engine inputs, does not implement Monday-noon availability, and overstates what its scoring and null establish.

Audited **`c23e62419919b2da6d43df5dfe8b8ce5c2c3cc2e`**. I ran the pinned scorer, independent recomputations, simulation counterexamples, and runner tests without external API calls. All **395 extracted committed files** passed the final unchanged-content check. I did not generate or score ON-1's 2024 holdout predictions.

**1. As-of — Q1: FAIL**

- **Blocker — "previous week" is not "available Monday noon."** Ratings include every play with `week < game_week`, without an observation or publication timestamp. For example, the week-2 numbers for Baltimore and Las Vegas incorporate their week-1 Monday-night game, which had not happened at the week-2 Monday-noon cutoff. From the committed game dates, **100/815 target games** have at least one participating team with such an unavailable prior-week game. This counts affected games; it does not estimate their prediction changes. build_monday_number.py:3, ratings.py:191.

- **Blocker — executed future-row counterexample changes the Monday number.** I used the pinned special-teams builder with a small synthetic PBP fixture, then added one week-18 play following a kickoff. Its season-wide kickoff estimate changed from yardline 75 to 40. Installing that derived value changed the pinned week-2 simulation:

  | `2021_02_CIN_CHI`, identical seeds and 5,000 simulations | Home margin | Total |
  |---|---:|---:|
  | Before future row | 2.3736 | 41.2976 |
  | After future row | 2.2700 | 72.5540 |
  | Original bytes restored | 2.3736 | 41.2976 |

  **This is a synthetic dependency proof, not an estimate of real-world leakage magnitude.** As a control, appending an extreme week-99 team-rating row left the prediction unchanged. Weekly lookup filtering works; the global mechanics boundary does not. tables.py:1117, engine.py:835.

- **High — the actual call path contains no Monday injury/depth/usage state.** ON-1 calls `simulate_game()` without `player_usage`, `active_uni`, or `qb_ratings`; the engine disables its player layer. It loads prebuilt team, tendency, situational-tendency, kicker, and league tables. It does **not** invoke the ratings/usage builders during each prediction. Therefore final injuries are not an active leak into these ON-1 predictions—the availability feature is absent. If connected unchanged, `usage.py` joins same-week injury status without `date_modified`, joins same-week historical depth charts, and uses a first-kickoff cutoff for newer depth data rather than Monday noon. build_monday_number.py:52, engine.py:743, usage.py:443.

- **High — the live runner does not enforce the stated experiment time.** It accepts any Monday or Tuesday, does not ensure the requested games are still upcoming, checks only the latest snapshot's maximum timestamp, and uses the first historical quote rather than the executable quote at prediction time. A future timestamp also passes its age check. Matching uses an unordered pair of teams without date or kickoff identity: my two-fixture counterexample selected the earlier meeting. run_monday.py:50, run_monday.py:110.

- **High — "pre-kick close" accepts in-play quotes.** Executing the pinned `get_first_and_last_line()` on quotes at 16:00Z and 19:00Z for a 17:00Z kickoff returned the **19:00Z quote as the close**. The function never applies its documented pre-kick restriction. Committed examples include CAR–ATL moving from +1 to +30.5. That is consistent with contamination, but the saved output lacks close timestamps needed to establish the provenance of each actual row. build_2026_interim.py:46.

**Qualified pass:** ordinary league shrink targets use the previous season; team ratings, tendency accumulations and kicker statistics use earlier week numbers. But the engine falls back to the **latest available season** if the required prior-season league row is missing. That fallback is unsafe, although the necessary prior-season rows exist in this pin. ratings.py:114, engine.py:632.

**Publication lag: could not verify.** No historical publication receipts establish which Sunday PBP version was available by each Monday noon. The session log itself labels its "approximately 4am" claim unverified. Regardless of publication speed, Monday-night results cannot be available Monday afternoon. agent_sessions.md:4340.

**2. Calibration — Q2: direct prior-season calculation HOLDS; end-to-end independence FAILS**

- **Verified:** all **12 season/bucket rows**, including margin and total variances, reproduce within `1e-12`. The 2021 constants are **182.25** and **174.24**, with zero calibration observations. The code uses those literals rather than fitting 2021, despite a contradictory preceding comment. For example, early-season margin variance is **17.775022880625** for 2022 from 2021, and **19.1138438528248** for 2023 from 2021–22. Every stored `err_m` exactly reproduces `sqrt(mc_se_m² + cal_var_m)`. build_monday_number.py:154.

- **Answer to "does err_m use the close?": yes, prior-season closes.** Its calibration target is `ours_m − close`. The target game's close is not directly used in its error-bar calculation. The ≥1-point rule is fixed in code. Nevertheless, the predictions underlying both calibration and scoring come from future-informed engine fits; the prior-season filter does not remove that dependence. build_monday_number.py:138.

- **High — "games into ratings" is fabricated from calendar week.** Both teams receive `week − 1`, ignoring byes and cancellations. Against completed prior-week games, this is wrong for **798/1,630 team-game entries**, affecting **461/815 games** and assigning **82 games to the wrong minimum-sample bucket**. These counts precede correction for Monday-night availability. build_monday_number.py:77.

- **Medium — the error bar has no demonstrated coverage interpretation.** It is a standard deviation of historical disagreement with the market, not a validated confidence interval for the true margin or a cover probability. It omits squared systematic bias, uses only two chunk means to estimate Monte Carlo error, and starts with an outcome-scale flat prior whose cited literature source is unspecified. That flat prior produces **zero confident 2021 games**: the advertised three-season confident result comes entirely from 2022–23.

- **High — the forward implementation changes the calibration policy.** Every 2026 week uses the **2023 "14+" bucket**, itself calibrated on 2021–22, regardless of current sample depth. That is not the historical bucket-dependent filter. run_monday.py:34.

**3. Engine tables — Q3: FAIL; 2024 is included in model development**

**Blocker:** the mechanics builder explicitly loads 2021–24, with no prediction-date cutoff. A league-level statistic can carry individual games' information through its empirical rates, quantiles, sparse cells and selected parameters. Pooling reduces individual influence; it does not establish independence.

The inventory below distinguishes verified fit declarations from unverified provenance:

| Inputs | Fit-window evidence and ON-1 relevance |
|---|---|
| `pass_outcomes`, `rush_outcomes`, both `_z10` tables | Built from pooled 2021–24; used for team simulation. |
| `playcall_xpass`, `clock_runoff`, `fourth_down`, associated fourth-down shrinkage metadata | Pooled 2021–24. |
| `fg_make_rate`, `punt_net`, `twopt_decision` | Pooled 2021–24; `punt_net` supplies the legacy/fallback path. |
| `kickoff` | Separate full-season rows, including 2024; engine selects the simulated season's row. Direct same-season look-ahead. |
| `turnover_returns`, `int_spot`, `int_ez` | Empirical return distributions, touchdown probabilities and interception-location/end-zone rates from 2021–24. |
| `timeout_policy`, `kneel_decision`, `fg_setup`, `fg_setup_rush`, `eoh_spike`, `eoh_fg_decision` | Pooled 2021–24 decisions and timing/outcome distributions. |
| `scalars.json`, `constants.json` | 2021–24 XP/2-point rates, penalty summaries, safety rates by field position and inter-drive timing. Some stored fields are legacy or player-only. |
| `penalty_detail.json` | Separate builder explicitly loads 2021–24. |
| `pass_depth_outcomes`, position catch constants | 2021–24 provenance in builder; player path is inactive for ON-1. |
| `punt_landing` | Read and used by the engine. **Could not independently verify its fit window:** no generating implementation was found at this pin; the decision log records the table and sample size. |

Sources: tables.py:24, tables.py:1691, build_penalty_table.py:23, engine.py:75, decision log:3483.

Additional fitted constants and dependencies:

- **Active:** `S_EPA = 5.20`; live defensive-first-down penalty probability **0.00766** and mean yardage **8**; the quarter/time-specific non-scrimmage timeout-rate dictionary. Their source comments explicitly identify 2021–24. engine.py:669, engine.py:864.
- **Indirect through weekly ratings:** selected half-life, prior weight and shrinkage parameter are tuned against 2021–24. `ratings.main()` reruns that tuning even without `--write-params`; the flag controls writing the parameter file, not whether freshly tuned parameters generate ratings. ratings.py:906.
- **Inactive player dependencies:** share parameters, `PHI_TARGET`, `PHI_CARRY`, and measured redistribution weights include 2024. They should not be blamed for the current player-off ON-1 number. usage.py:1150, engine.py:383.
- **Calibration maps:** `calibration_v1.json` explicitly lists 2021–24, but ON-1 does **not** apply those maps to its means. Their existence alone is not the demonstrated leakage path. calibration_v1.json:8590.
- **HFA requires a qualification:** its home-margin target is genuinely 2021–23; I recomputed **2.1251533742**, agreeing with stored **2.1252**. However, its note derives `h=0.1719` from `J_FWD`, and the committed Jacobian estimator uses 2024 games. Thus the target is not a 2024 fit, but the conversion cannot be certified independent of 2024. hfa_v1.json:14, anchor.py:41.

**4. Conventions — Q4: historical signs HOLD; forward signs FAIL**

The committed historical conversion is consistent:

| Game | Raw home opener | Converted home-margin opener | Closing home margin | Actual home margin |
|---|---:|---:|---:|---:|
| 2021_01_ARI_TEN | −3.0 | +3.0 | +2.5 | −25 |
| 2021_01_DAL_TB | −6.5 | +6.5 | +10.0 | +2 |
| 2023_18_BUF_MIA | +3.0 | −3.0 | −2.5 | −7 |

The brief's TEN −2.5 example corresponds to the stored **close**, not its bet365 opener. These are checks against committed records, not independent verification of the original bookmaker quotes. `ours_m` is home score minus away score. Historical scoring uses points; I found no raw/no-vig price mixing in that calculation. build_monday_number.py:37.

- **High — forward Hard Rock signs are reversed.** The runner stores the raw home handicap but computes `ours_m − raw_handicap`. Correct home-margin conversion requires negating that handicap. Recomputing the committed 75 usable 2026 rows changes **46 confidence flags**, confident games **50→30**, and moving-confident agreement **24/40 = 60% → 11/25 = 44%**. The corrected percentage still uses suspect closes and is **not** a valid forward estimate. run_monday.py:127, build_2026_interim.py:198.

- **High — the advertised ATS and movement statistics condition on a future event: whether the line moved.** Excluding unchanged lines is permissible for a clearly labelled direction statistic; it is not the prospective betting population. score_monday_numbers.py:47.

  | Verifier claim | Independent result |
  |---|---|
  | Direction 92/125 = 73.6% | **HOLDS**, among moving confident games |
  | Wilson approximately 0.65–0.81 | **HOLDS:** 0.652524–0.805403, nominal interval |
  | Mean movement +1.60 | **HOLDS conditionally:** +1.604; **+1.44245** across all 139 selections |
  | Open ATS 56.5% | **HOLDS conditionally:** 70–54–1; all selections **75–63–1 = 54.35%** excluding pushes |
  | Close ATS 50.0% | **HOLDS conditionally:** 59–59–7 using the close-based pick; all selections **64–68–7 = 48.48%** |
  | Outside subset 55.0% | **HOLDS:** 312/567 = 55.026%; contradicts the registered 48–52% prediction |

- **Medium — movement mixes books.** The nflverse close differs from the sign-corrected bet365 close in **290/815 games**. Replacing it with bet365's own close still yields **91/123 = 73.98%** direction agreement. Cross-book differences therefore do not explain away the result, but the original metric is not pure bet365 movement.

- **Low — favorite labels are backwards.** Positive home margin means home favored; the scorer labels negative values `home_fav`. score_monday_numbers.py:92.

The four runner tests print success, but the stale-snapshot test has no assertion, the unmapped-team test only counts mappings, and the confidence test repeats the wrong sign formula while checking only that both flag values occur. Their green result does not challenge these counterexamples. test_run_monday.py:33.

**5. Looks — Q5: "before any number" is unverified; "untouched 2024" is false**

- **High — the spec already contains historical movement results.** It reports 2021–23 mean absolute movement **1.54** and the ≥1-point frequency before stating its hypotheses. Thus historical spread movement was in view. This does not prove that the precise confidence thresholds were optimized against direction results. ON_SPEC_v1.md:17.

- **Medium — the claimed hash identifies the original spec, not the pinned file.** Original SHA-256 is the stated `f77c747e…682ab6`; pinned SHA-256 is `186a256c…e3c`. The difference is an appended running-instructions section, not rewritten hypotheses. Git first records the spec **together with the 815 predictions** in `9838ada70`; scoring follows in `5ed4920ac`. That supports "committed before the scoring script," not independently timestamped registration before generating any predictions.

- **Blocker — 2024 was already used and examined.** The prior session log explicitly says the engine was developed using 2024 and describes earlier 2024 evaluation. The new ON-1 movement endpoint may remain unopened, but that cannot make the engine out-of-sample for 2024. agent_sessions.md:2375.

- **Medium — the invariant was changed after predictions existed.** The session records replacing the prediction-minus-close correlation gate with an outcome-minus-close gate. The new gate reproduces: margin correlation **−0.01536879**, total correlation **−0.04384130**. It checks target consistency; it cannot detect leaked predictions because the prediction is absent from its formula. agent_sessions.md:4304.

- **Medium — reproducibility is not frozen.** Seeds use process-randomized Python `hash()`. The same game/chunk produced seed **1998463955** under `PYTHONHASHSEED=0` and **1026244845** under `1`. Existing simulation caches are accepted solely because the file exists, without validating inputs, code or seed identity; simulation exceptions can also remove games without enforcing complete coverage. build_monday_number.py:50, build_monday_number.py:83.

**6. Baseline — Q6: COULD NOT VERIFY**

**High — the ridge comparison is not auditable at this pin.** The named `nfl/data/sim/outputs/gl1/baseline_2021_23.parquet` is absent. I did not substitute another branch. Consequently, **55.3% / +0.67 / 55.4%**, the error-bar substitution, fold construction and sample policy remain unverified.

A concrete admissible comparison must freeze:

1. Identical cutoff, quote convention, eligible games and push/no-movement rules.
2. Predictions trained only on information preceding each prediction date. "Out-of-fold" alone is insufficient if training includes later seasons.
3. Either the same engine-error threshold for both, labelled a **common threshold**, or separately estimated prior-season error bars, labelled **method-specific confidence**.
4. Counts for every selection and every moving selection, plus paired comparisons on common games. Neither method may earn an advantage by silently dropping different rows.

**7. Null — Q7: reported interpretation FAILS; a tighter comparator was computed**

- **High — "close + noise" is an oracle-contaminated comparator, not an as-of ceiling.** It receives the target close. Its performance depends on the chosen noise and filter; **82.6% is not a meaningful maximum** for an operational forecast. I could not independently reproduce that particular number from a committed implementation.

- **High — the shuffle claim describes the wrong population.** Running the pinned scorer reproduces **null mean 48.40%, SD approximately 1.37 percentage points, Z=7.28** against **404/692 = 58.38%**. It does not test **92/125 = 73.6%**. It shuffles predictions across all moving games and does not reconstruct the confident subset in each permutation. Thus "null 50%, Z 7.3 for the confident effect" fails. score_monday_numbers.py:116.

**Executed alternative:** fit closing-line-implied team ratings by least squares, with home-minus-away team indicators and a home intercept. For each prediction, use only previous-season/current-prior-week closes dated strictly before that game-week Monday; require at least 32 training games. No outcomes, future games or 2024 rows entered fitting. I specified this procedure before reading its performance.

| Comparator | Eligible | Confident, including unchanged | Moving confident | Direction | Mean signed move, moving subset |
|---|---:|---:|---:|---:|---:|
| Prior-close ratings, engine's error threshold | 767 | 151 | 129 | **71/129 = 55.04%** | **+0.442** |
| Same ratings, own prior-season error calibration | 767 | 160 | 138 | **75/138 = 54.35%** | **+0.388** |

The engine retains all its 125 moving confident games within the common eligible population. This particular trivial comparator **does not reach approximately 70%**. That result does not establish an engine advantage under honest timing: the engine still has the leakage documented above. This comparator also lacks historical publication receipts, although its game-date restriction is conservative.

**8. Economics — Q8: expected Hard Rock value is NOT IDENTIFIED**

**High:** direction accuracy and an unconditional average absolute move do not determine captured value. The required quantity is:

`E[pick_direction × (valid pre-kick close − executable quote at prediction time) | selected]`

It must include unchanged lines. Neither the selected Hard Rock movement distribution nor executable Monday quotes is established here.

The committed interim artifact does not reproduce the claimed **0.76**: its weeks-2–5 rows give **8.4683 points across 63 usable games**, with the close-selection defect above. That does not refute a separate clean-tape calculation of 0.76; it means this artifact cannot verify it. ON_SPEC_v1.md:9, build_2026_interim.py:46.

For an explicitly hypothetical calculation, assume a fair closing line, no pushes and normally distributed margin residuals with SD 13.5:

| Additional transfer assumption | Captured points | Cover probability | Expected return per dollar risked at −110 |
|---|---:|---:|---:|
| Selected absolute moves average 0.76; equal move magnitudes when right/wrong; accuracy remains 73.6% | `0.76 × (2×0.736−1)` = **0.35872** | **51.06%** | **−2.52%** |
| Historical +1.60 scales proportionally with average movement, `0.76/1.54` | **0.78961** | **52.33%** | **−0.09%** |

These are assumption-driven scenarios, not estimates from verified Hard Rock data. At −110, break-even is **52.38095%** excluding pushes; this normal approximation requires approximately **0.8062 points**. Neither scenario clears it. NFL key-number probabilities and actual offered prices could materially change the conversion.

**GO / NO-GO: NO-GO.** Do not open 2024 under the label "clean one-shot OOS": the pinned model already incorporates 2024 information, and its historical and forward pipelines do not implement the promised observation-time boundaries.

**NOT DONE**

- No ON-1 2024 predictions generated or scored.
- No complete 815-game simulation rebuild or reconstruction of every empirical fit from raw PBP; the required raw sources are not committed at this pin.
- No alternate-branch ridge audit.
- No production odds retrieval, betting, scheduling or repository edits.

**UNVERIFIED**

- Historical nflverse publication/revision times and the data actually available at each Monday cutoff.
- Original bookmaker quote accuracy, opener availability at prediction time, and the separate 0.76-point Hard Rock measurement.
- Independent fit provenance for `punt_landing`, exact reproduction of the inherited Jacobian/HFA conversion, and the claimed 82.6% oracle-noise result.
- Registration before any predictions or private exploratory looks beyond what committed history documents.

---

## Repair brief (ChatGPT, same reply) — summary of priorities P0–P7 and the forward protocol

P0 freeze the research contract; 2024 is not a clean whole-system holdout; new versioned prospective spec with hash, frozen artifacts, hypotheses, selection rule, benchmarks, scoring and stopping rule; guard against targeting 2024.
P1 real Monday-noon boundary: timezone-aware prediction_cutoff; admit only games/source versions received by the cutoff (event time ≠ receipt time); immutable snapshots with hashes; frozen mechanics with recorded fit windows; no "latest season" fallback; frozen params on ordinary builds.
P2 signs/event identity/quote timing: q = −h at ingestion; gap = ours − q; match by season+fixture+orientation+kickoff+event_id; executable quote at the cutoff as benchmark; close strictly pre-kick with a frozen max-age; freshness on the selected quote; reject future-dated quotes.
P3 sample depth and calibration: actual admitted games per team; frozen bucket rule and calibration artifact; describe err_m honestly; fix the 2021 flat-prior comment; no unexplained late-season proxy in the forward runner.
P4 freeze the selected population: selection and side before outcomes; include unchanged lines; direction reported separately as conditional; same-side ATS at decision and close; count pushes/voids/missing; recorded prices for returns.
P5 reproducibility: stable versioned seeds; caches bound to code/experiment/model/input hashes, cutoff, game, N, seed scheme; one result or explicit failure per eligible game; atomic writes; replay with network off.
P6 nulls and baselines: earlier-close rating comparator frozen before forward outcomes; common vs method-specific thresholds labelled; permutation diagnostics must rebuild selection; no Z-validates claims; ridge claim only when auditable in the reviewed branch.
P7 tests and quarantine: behavioral fixtures replacing decorative tests; 2026 interim marked invalid and retained as an audit artifact; no Hard Rock profitability estimate from 73.6 % × 0.76.
Forward protocol: frozen team-level player-off model; Monday 12:00 America/New_York with UTC recorded; only still-upcoming fixtures; immutable snapshots and manifest; benchmark = active hardrockbet_fl quote at the cutoff in home-margin units; selection |ours − q| ≥ err_m and ≥ 1 pt with side and exclusions recorded; primary endpoint = mean signed decision-to-close movement over all selected games, paired vs the earlier-close comparator; secondary = direction among movers, same-side ATS at decision and close, returns at recorded prices; run first valid post-freeze Monday through the end of the 2026 regular season; ≥ 60 selected unique games and ≥ 12 weekly clusters for a confirmatory read else underpowered; analysis frozen, weekly dependence accounted, no efficacy-based early stopping, every look logged; any change = new experiment version; games are the units; placed vs hypothetical bets distinguished.
