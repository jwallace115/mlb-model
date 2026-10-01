# Kill ledger v0 — working inventory of negative verdicts (2026-10-01)

Produced by a read-only sweep of the docs in `main` @ `022368d8a`. **Unverified, apart from the rows marked [checked]
in `kill_ledger_v0_2026-10-01.md`.**

Column meanings:
- **Gen:** the docs name a generator script.
- **Repro:** the docs record an independent reproduction.
- **[P]:** the source is a claude.ai Project doc only.

The docs-only checkout had no .py files, so no generator's existence was checked.

## MLB

| # | Killed | Where | Numbers / odds basis | Gen | Repro | Suspect signs |
|---|---|---|---|---|---|---|
| 1 | V1 Ridge PIT clean rebuild (Clean Kill #1) | `research/recovery/mlb_totals_reset_audit/PHASE7_CLEAN_KILLS.md:8-14`; `research/recovery/v1_clean_backtest/v1_clean_backtest_2022_2025.md:11-22` | 2024: N=175, 46.9%, −10.5%. 2025: N=55, −13.2%. Synthetic −110. | none | none | 2022-23 had 0 bets, so effectively 2 seasons with OOS N=55. Static 2024 park factors were used for 2022-23. |
| 2 | V2 Model_B (Clean Kill #2) | `PHASE7_CLEAN_KILLS.md:19-23`; `research/recovery/v2_engine/v2_engine_report.txt:91-100` | RMSE delta −0.0105 vs market (better). Over N=915, −10.2% at real price. Under N=162, +1.0%. | none | none | The kill text says "+0.01 vs market". The over bias comes from an intercept fit on the 2022-23 mean. |
| 3 | S12 overlay (Clean Kill #3) | `PHASE7_CLEAN_KILLS.md:27-33`; source `S12_STANDALONE_FINAL_VERDICT.md:11`, `s12_overlay_report.md` | Standalone N=2596, −0.8% vs −2.5% blind. OOS 2025 +4.7% (N=706). Overlay OOS active > inactive. | none | none | **The kill quotes P09's numbers [checked].** The sources say DIMINISHED. Registry v2 still says VALIDATED_SHADOW. |
| 4 | P09 overlay (Clean Kill #4, re-killed 08-28) | `PHASE7_CLEAN_KILLS.md:37-42`; `research/mlb/mlb_system_registry_v2.md:65,194-212`; `mlb_sim/pipeline/p09_overlay_config.json` | Cutoff 35.07: OOS active N=240, 50.9%, −2.9% vs inactive N=1858, +0.8%. Original cutoff 31.73: OOS N=60, +10.5% flat / +14.9% actual. | unnamed | none | Different object (cutoff). No significance test. |
| 5 | ST02 road-trip fatigue (Clean Kill #5) | `PHASE7_CLEAN_KILLS.md:46-51`; `research/mlb_shadow/st02_historical_audit.md`; `research/signal_scanner/st02_deep_analysis.md` | N=2,172, 52.21% vs 50.38%, p=0.031, permutation 99.5th. Synthetic −110. | none | numbers reused only | The kill text contradicts the source ("unpriced"). Missed the gate by 0.79pp. 2022-23 line source differs. |
| 6 | ADJ_BB_RATE (Clean Kill #6) | `PHASE7_CLEAN_KILLS.md:55-60` | 2026 shadow 50.0% on N=16 | none | none | A same-day backtest says RETAIN (VAL +3.0%, OOS +1.1%, real closing). The shadow tracker's `correct` field was never populated. |
| 7 | F5 RL Signal B away (Clean Kill #7) | `PHASE7_CLEAN_KILLS.md:64-69`; `research/f5_runline/f5_runline_research_report.md:29-43` | The B_away source shows N=316, +18.4%, 2025 +15.2%, permutation 98%. | none | none | **Numbers are from A_away [checked].** All of it used season-final xFIP. |
| 8 | Run-line comeback asymmetry (Clean Kill #8) | `PHASE7_CLEAN_KILLS.md:73-78` | 9,857 games, cover rate 35.8 vs 35.9% | none | none | No prices used. |
| 9 | Team totals away over (Clean Kill #9) | `PHASE7_CLEAN_KILLS.md:82-87` | "52-54%", no N or ROI | none | none | Rests on numbers its own document calls contaminated. |
| 10 | F5 totals D1/D2 VOID; TT E1/E2 VOID | `PHASE3_CLASSIFICATIONS.md` | signals 1033 → 160; TT fire rate 93.8% | none | none | Voided; never re-tested on clean inputs. |
| 11 | Signal B home F5 RL (archived) | `research/recovery/signal_b_clean_backtest/...`; `signal_b_archive/...` | N=724, 53.9% vs 57.4% break-even at an assumed flat −135 | none | none | FIP expanding-mean trigger (~180 fires per season) differs from the xFIP proof object (32-35 fires). |
| 12 | ADJ family VALIDATED_NEGATIVE_DEAD | `mlb_system_registry_v2.md:68,226`; `research/mlb/adj_family_formal_no_go_v1.md`; `ADJ_MASTER_KEEP_KILL_MEMO.md` | −0.6% to −3.6% at real closing; 4 of 5 positive in 2025 | none | **conflicting backtest** | Same-day backtest: ~30% larger N, best price, all OOS positive. The memo said MONITOR. |
| 13 | Over scanner wave 1 (0/8) | `OVER_SCANNER_STANDALONE_EXEC_SUMMARY.md:40-73` | OOS 2025 −1.6% to −10.8% at actual closing | none | none | N not given. Single OOS season. |
| 14 | MLB moneyline Phase 1 (0/8) | `MLB_MONEYLINE_PHASE1_EXEC_SUMMARY.md:17-55` | OOS +9.50% (N=254) and +7.31% (N=402), killed at validation | none | none | Kill rule requires all 3 stages; small validation N. |
| 15 | ML Phase 2/3 (C1-C10) | `MLB_MONEYLINE_PHASE2_DEEP_EXEC_SUMMARY.md`; `..._PHASE3_...` | C3 VAL N=84 −36% vs OOS N=162 +13.7% | none | none | Validation N of 84-168 decides the kills. |
| 16 | C8 command-vs-stuff | `C8_SHADOW_EXEC_SUMMARY.md` | Frozen-median OOS −12.06% on N=53 | none | same session | N=53. |
| 17 | W-family | `MLB_W_FAMILY_CLOSEOUT_MEMO.md` | Runs-gap metric only | orchestration | none | No price test. |
| 18 | E-family pass 02 | `MLB_E_FAMILY_PASS_02_CLOSEOUT_MEMO.md` | E01 flags 100% of rows; E02 never computed | — | — | E02 is a data gap. Report reconstructed after files were lost. |
| 19 | H03 family | `MLB_H03_FAMILY_PROVISIONAL_CLOSEOUT_MEMO.md` | H03 passed all 3 stages | none | none | Reconstructed from summaries. LOW_TOTAL OOS N=21. |
| 20 | Bounded discovery pass 04 | `MLB_BOUNDED_DISCOVERY_PASS_04_REPORT.md` | triage only | — | — | S3/S4 were data gaps. |
| 21 | F5 discovery pass 02 (53 dead) | `MLB_F5_DISCOVERY_PASS_02_REPORT.md` | 2 advanced, both reversed at validation | — | — | Benchmark is the 2am opening line. |
| 22 | Autonomous engines V1-V3 ("edge exhausted") | `MLB_AUTONOMOUS_ENGINE_V2/V3_REPORT.md`; `SESSION_LOG.txt` | V2: 639 Tier A at real ROI; V3: 4,297 Tier A | none | none | Dismissed by inspection with no artifact. V1 directory missing. |
| 23 | Logged-only MLB kills | `research/SESSION_LOG.txt` (04-22) | phase2a 0/39; lineup 0/63; F5 pass01 0/35; sim engine v1 | — | — | **Artifacts missing.** |
| 24 | Bullpen-leverage pass 01 ("data availability artifact") | `SESSION_LOG.txt`; [P] framework §VII.3 | 10/40 held direction across 3 stages | — | — | Bridge normalization fix (56% → 99.2%) and a data gap; unclear which data the pass used. |
| 25 | CLV salvage (FASTBALL_DOMINANCE_LOW_SLIDER) | `MLB_CLV_SALVAGE_V1_REPORT.md`; `..._PORTABILITY_V1_REPORT.md` | ON N=41, p=0.49 | none | v1 permutation 6/9 | "Approximate reconstruction", a different object. Noon-snapshot benchmark. |
| 26 | Surface consistency / copy lag | `MLB_SURFACE_CONSISTENCY_V1_REPORT.md`; `MLB_COPY_LAG_V1_REPORT.md` | tt_gap +9.65 at BetMGM | none | none | Probable parsing artifacts, never examined. |
| 27 | NRFI | `PHASE3_CLASSIFICATIONS.md` §H2 | 55.7%, −3.0% at an assumed −135 | none | none | Flat assumed price. |
| 28 | SEEP, bullpen correction, run volatility, sigma layer, TB model v2, first inning v1 | various (see sweep) | SEEP: 52 signals / 12 days | none | none | Preliminary or tiny N. First inning was archived for missing prices. |
| 29 | TB props | `dead_signal_rescore_2026-08-28.md:57,64` | −10% all books; BetOnline +22.6% (N=108) | — | — | "Historical prop odds not in archive." |
| 30 | MLB side engine | `research/mlb_side_engine/...` | Brier near-miss | — | — | The earlier ADVANCE used a contaminated feature. |

## Kalshi / execution

| # | Killed | Where | Numbers / odds basis | Gen | Repro | Suspect signs |
|---|---|---|---|---|---|---|
| 31 | Kalshi naive maker | `research/execution_edge/kalshi_adverse_selection_2026-08-28.md`; `CLAUDE.md` | −0.347c size-weighted / **+0.076c unweighted (t=5.22)**; 186,205 fills | none | ChatGPT accepted, no recompute | One day of MLB. Sign flips with weighting. |
| 32 | Line shopping +4.31% → +2.44% | `chatgpt_review_adjudication_2026-08-28.md`; `shopping_robustness_2026-08-28.md` | +2.44% (t=9.19, N=2,648) | `nfl/pipeline/shopping_robustness_audit.py` | rebuilt | One snapshot per week, about 4.5 days before kick. |
| 33 | Football demoted to a CLV box | `chatgpt_review_adjudication_2026-08-28.md`; `CLAUDE.md` | decision only | — | — | Its premise was rejected, yet the demotion was kept. |

## NFL

| # | Killed | Where | Numbers / odds basis | Gen | Repro | Suspect signs |
|---|---|---|---|---|---|---|
| 34 | Sim K4 vs book | `research/nfl_sim/NFL_SIM_DECISION_v1.md` (D17, D57, D63, D76, D103) | 72,850-72,978 legs. Brier book 0.2316 vs sim 0.2534. Worse in all 8 families. | `nfl/sim/run_k4.py` | Cowork (D63, D103, fit_6b) | In-sample, which flatters the sim. The blind-side ROI tables don't test the sim. |
| 35 | Week-2 sim vs book | `research/ncaaf_board/NCAAF_BOARD_DECISION_v1.md:1617-1621` (N60) | 146 rows, book 0.2519 vs sim 0.2993 | — | pre-registered | One-draw engine. |
| 36 | FWD1 week-3 pilot | `NFL_SIM_DECISION_v1.md` (D218) | Δ +0.0157, CI −0.002 to +0.034 | `run_forward_v1.py` | Cowork | Pilot; CI includes 0. |
| 37 | Game-line scan; Wong teasers | `research/layers/game_line_scan_2026-09-29/README.md` | 0 of 2,512 pass BH | — | — | Outcome rates, not prices. Holdout unopened. |
| 38 | "Weird" scan | `research/layers/weird_scan_2026-09-29/README.md` | 2 survived 2024 (+3.7%, +7.6%, se ≈5.4) | — | — | Triage −110. |
| 39 | Totals-miss buckets | `research/layers/nfl_totals_miss_2026-09-29/README.md` | 6 buckets reversed (validation n=448) | scratch paths | — | Season split during league drift. |

## NHL

| # | Killed | Where | Numbers / odds basis | Gen | Repro | Suspect signs |
|---|---|---|---|---|---|---|
| 40 | Pre-game engine (S42-S44, L-001 CLV) | `research/nhl_sim/edge_hunt_2026-09-30/...`; `claude/nhl_layers_handoff.md` [P] | Log-loss 0.6647 vs 0.6567. CLV slope −0.004, n=289. | `nhl/sim/price_games.py` | Cowork | **Goalie-swapped engine; CLV not re-run after the fix.** S40-S48 absent from the decision doc. |
| 41 | PREREG_EV | edge-hunt LEDGER | 131 bets, −16.6% (SE 10.8) | in folder | — | SE 10.8. |
| 42 | PREREG_ALT | edge-hunt LEDGER | 35 bets, CLV +0.90% | — | — | N=35, positive point estimate. |
| 43 | A-02/S48, A-05, A-06, B-01, A-04 | LEDGER | A-02 p 0.0064 vs threshold 0.0063 | work logs | — | 7 of 12 never computed. A-04 untestable. |
| 44 | A-01 H2, E-02 | LEDGER | CLV −0.9% | `e02_*.py` | Cowork | No Pinnacle in the in-play data. |
| 45 | Open search, 4,115 cells | `research/layers/nhl_edge_hunt_2026-09-29/README.md` | Holdout n=167, −1.24% at real DK | scripts listed | same author | Small holdout. |
| 46 | Props scan | `.../phase2_props/README_P2.md` | Assist-unders −3 to −5% at median price | — | — | One season. |
| 47 | Game lines, H_PL, H_XG | `.../phase3_lines/README_P3.md` | 0 of 1,335 pass BH | — | — | One-season holdout. |
| 48 | Autonomous engine V1 | `NHL_AUTONOMOUS_ENGINE_V1_REPORT.md` | 359 Tier A | — | — | Dismissed by inspection. |

## NBA

| # | Killed | Where | Numbers / odds basis | Gen | Repro | Suspect signs |
|---|---|---|---|---|---|---|
| 49 | Small-edge Ridge | `nba/docs/nba_small_edge_postmortem.md` | about −7% on 666 | none | — | 2 discovery seasons. PIT unverified. |
| 50 | Pregame totals (Phases 9-12, Model B) | `nba_small_edge_postmortem.md`; `nba/phase10/...`; `nba/model_b/...` | all fail | — | — | "Opening" was a 10:00Z snapshot. Injury data covers only 1 season. |
| 51 | ELITE_DEF2 collapse, etc. | `NBA_CURRENT_ARCHETYPES_KEEP_KILL.md`; `NBA_FIX_PASS_FINAL_VERDICT.md` | OOS N=122, −18% at flat −110 | — | — | The "TRUE OOS" label is invalid (CHECK 2). |
| 52 | Schedule fatigue (0/7) | `research/nba/schedule_fatigue/signal_board.json` | FA01H train +7.0%, val +6.1% | — | — | Missed the gate by 0.6 percentile points. Holdout never opened. |
| 53 | Props P3-P5 | `nba/props/model_p5/p5_summary.txt` | N=4,912, 56.7%; ROI_A +8.2% / ROI_B −4.7% | — | — | Undefined pricing conventions with opposite signs. |

## WNBA

| # | Killed | Where | Numbers / odds basis | Gen | Repro | Suspect signs |
|---|---|---|---|---|---|---|
| 54 | System C anchor | `research/wnba/wnba_system_registry_v2.md:120-135` | holdout N=93 / 275 | `run_anchor*_model.py` | "not independently verified" | v1 trained on 56 rows. The date fix (+449 games) came after the verdict. |
| 55 | System D ridge | `wnba_system_registry_v2.md:141-171` | N=93 | `wnba/pipeline/run_model.py` | — | The diagnostic recommended a rebuild, not a kill. |
| 56 | System A archetypes | `wnba_system_registry_v2.md:62` | ARCH_02 OOS +22.7% | — | — | Operational death (stubs), not evidential. Price basis disputed. |

## Golf

| # | Killed | Where | Numbers / odds basis | Gen | Repro | Suspect signs |
|---|---|---|---|---|---|---|
| 57 | Finish engine | `golf/research/finish_engine/final_report.md` | custom Brier worse than DataGolf | — | — | — |
| 58 | Finishing-market validation | `golf/reports/finishing_market_validation.md` | **OOS CLV +5.0% to +15.2% at every threshold**; ROI mixed | — | — | Killed on ROI despite CLV. CLV undefined. |
| 59 | Structural fit / BDL sim / putting drift | [P] framework only | rho −0.57 | — | — | **No repo artifact.** |

## Soccer

| # | Killed | Where | Numbers / odds basis | Gen | Repro | Suspect signs |
|---|---|---|---|---|---|---|
| 60 | V3 Poisson, LightGBM V2.2, over-1.5, totals ladder | `soccer/research/v3_evaluation.md`; `soccer/phase_v2_2_audit.txt`; ... | −1.5% to −18.5% | — | — | Production prices are "B365 only"; the price source per table is unknown. |

## NCAAF

| # | Killed | Where | Numbers / odds basis | Gen | Repro | Suspect signs |
|---|---|---|---|---|---|---|
| 61 | Coaching cascade, home-field erosion, portal overlay, front-loading | `research/ncaaf_base/phase3/4/6/7_*.md` | ATS rates, no prices | — | — | Cells of N=21-99. |

## Verdicts later reversed or reopened

- **P09:** killed → reinstated → killed again.
- **S12:** killed, but the kill was never honoured.
- **Signal B home:** keep → archive → shadow → archive.
- **ADJ:** retest → monitor → dead → the Kalshi rescore turns all five positive.
- **NCAAF N06:** "did not hold" → "held", after a bin-edge defect was fixed.
- **NFL Phase 3b and QB rush_att:** positives that turned negative after bugs were fixed.
- **Kalshi settlement +0.494c and line shopping +4.31%:** withdrawn.
- **NBA ROAD_WARRIOR:** failed CHECK 2, then re-tested alive.
- **Reopenings proposed in [P] framework §VI.8-9 and §VII:** none carried out.

## Bugs found after a negative verdict in the same pipeline

- NHL goalie swap; the CLV test was never re-run.
- NFL one-draw player share. K4 was re-run and still holds.
- NFL pace, phantom receivers, interception spot, and CLV on mixed vig scales.
- MLB PHASE7 transcription and identity errors (S12, F5 away, P09).
- ADJ: frozen live features and an unpopulated `correct` field.
- MLB bullpen-leverage normalization fix.
- WNBA date fix.
- NBA live features (overall instead of location splits) and an unused injury adjustment.
- NHL 2025-26 backfill lost team identity.
- NHL E-01 has no Pinnacle.
- NCAAF home-cover bug "withdrawn but not fixed".
