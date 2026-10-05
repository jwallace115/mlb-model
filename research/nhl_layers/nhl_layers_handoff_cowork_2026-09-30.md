# NHL Layers — handoff (read this first in any NHL chat)

Last updated: 2026-09-30 ~12:30Z by Cowork (edge-hunt chat) — **NHL WO1 RAN and is VERIFIED from origin (branch nhl/wo1, 7 commits, NOT merged — Jeff's merge command below).** H3 freeze tool (date slates, drivers, Pinnacle book of record), H4/H4b outcomes loader + score with CLV vs Pinnacle close and baselines (a)/(c), H5 packet hashed beside every frozen file, H6 goalie-source measurement (no free pre-game starter API). The layers logbook now exists; the reader method file does not. Earlier today: branch E (in-play) and the sim tests — see below.
Previous: 2026-09-30 09:50Z by Cowork (edge-hunt chat) — BRANCH E RAN: E-WO1 bought 800 in-play snapshots of 2023-24 (16k credits; no Pinnacle — Cowork's regions=us error); live engine from StartState == soft-book live consensus (ML log-loss 0.511 vs 0.512); the first-pass +64% ROI was stale quotes + mybookieag's broken feed; one LEAD (live UNDER picks +21% on 71 games, post-hoc) pre-registered as E-03 for a 2024-25 pull in October. Still nothing FOUND. Earlier today: C-01 goalie-swap defect, S48-ML-R6 confirmation FAILED, A/B tests dead. See the edge-hunt section and `claude/nhl_sim_edge_hunt_ledger.md`.
Previous: 2026-09-30 05:10Z by Cowork (edge-hunt chat) — ENGINE DEFECT C-01 (goalie ratings swapped between teams in game_inputs.py; every S41-S48 number came from that object); S48-ML-R6 confirmation on 2024-25 FAILED; fixed-engine tests A-01..A-06, B-01 (3-way) all dead as bets; nothing bettable found; C-WO1 (fix) and D-WO1 (2010-21 pull) written, not run. See the "NHL SIM EDGE HUNT — session 2026-09-30" section below and `claude/nhl_sim_edge_hunt_ledger.md`.
Previous: 2026-09-30 03:45Z by Cowork (NHL chat) — S-WO4d verified; Cowork ran the full 12-test S48 family: ONE BH survivor (ML, both goalies below avg, 2023-24) — candidate only, did not exist in 2022-23. Edge-hunt prompt for a new chat saved (claude/nhl_sim_edge_hunt_prompt_2026-09-30.md).
Plan of record: `claude/LAYERS_GAMEPLAN_2026-09-27.md` (repo `research/layers/`). Decisions: repo
`research/nhl_layers/NHL_LAYERS_DECISION_v1.md` (H1, H2, ...). Hashes of frozen files go in
`claude/capture_status_2026-09-20.md`, NHL section (create it at the first freeze).

## Dates
- NHL regular season opens **Tue 2026-09-29** (NHL.com). Tape already sees CAR-FLA 2026-09-29T21:00:47Z and
  TOR-MTL 23:10Z (legacy opening-lines pull, 06:05Z today). Game count for the night: NOT verified (the NHL API is
  unreachable from Cowork's sandbox and bridge); WO1 checks it.
- **Pilot: slates 2026-09-29 .. 2026-10-04 (ET dates), `--pilot`, never pooled. Record from Mon 2026-10-05.** (H1)

## State at end of session 1
- H1 (scope, dates, metrics, baselines, P1-P3, checkpoints) and H2 (paths, season rule, slate date, book-of-record
  rule, settlement, pre-check findings) WRITTEN in the Mac's `~/mlb-model/research/nhl_layers/`, **UNCOMMITTED**.
  sha256 H-doc `b8dd4536…`, WO1 `d8b0b5d6…`.
- **Capture belongs to the main Layers chat's capture work order 12** (`research/layers/capture_workorder12_nhl_2026-09-27.md`,
  branch `eng/cap12`, written 14:00Z): NHL on the 30-min tape, multi-book NHL event markets (props + every game
  market, 10 books) at `data/odds_archive/nhl/event_markets/`, VM cron after Jeff says "deploy". NHL work orders do
  not edit `shared/pipeline/` while it is open. The NHL tape does NOT exist until WO12 merges and deploys.
- **NHL work order 1 written, NOT run:** repo `research/nhl_layers/workorder_1_2026-09-27.md`, project
  `claude/nhl_layers_workorder1_2026-09-27.md`. Branch `nhl/wo1`, worktree `~/mlb-model-nhl1`, four items:
  (1, H3) freeze tool NHL entry + date-keyed slates + drivers field + book of record; (2, H4) NHL outcomes loader +
  score with CLV and baselines (a)/(c); (3, H5) packet builder, hashed beside each frozen file; (4, H6) starting-goalie
  source measurement (no cron — proposed lines only). STOPs unless H2 is on origin/main. Session log goes to
  `logs/_log_nhl_wo1.txt`; Cowork appends it to agent_sessions.md at merge.
- The NBA chat's WO1 (nba/wo1) deliberately leaves `log_ai_opinions.py` and `shared/layers/` to NHL WO1; NBA WO2
  (its tape/freeze entry/packet) waits for NHL WO1 to merge — and must land before NBA preseason tests (from 10-03).
- **Book of record for NHL = Pinnacle (H2 addendum, 14:35Z).** Capture WO12 ran items 0-2 (eng/cap12, 4 commits on
  origin, NOT merged, NOT deployed): its NHL dry run returned 33 games from 9 books with Hard Rock absent on every
  game; /markets on FLA@CAR and MTL@TOR (regular-season openers — its log calls them "preseason", which is wrong)
  showed Hard Rock 0 markets, Pinnacle 22 game-level markets, no player props from anyone yet. Why Hard Rock is
  absent is unknown. Pilot runs on Pinnacle; only a named H-decision before 10-05, from pilot-week coverage, can
  change it for the record. Credits after WO12: 99,842 of 100,000. Event markets cost 1 credit per market per
  event (19 markets on one NHL game = 19), so two NHL slots/day on ~15 games is ~570/day, not WO12's ~400.
- **H1-H2 + WO1 ON ORIGIN (d79111f4b).** WO12 items 0-2 merged (eed0d02), including an "L2 amendment" (6120751b2) to
  `log_ai_opinions.py`: conf/conf_rank required on every new freeze, edge, conf bands + postfreeze cut in score, and
  a first `SPORTS['nhl']` entry {book pinnacle, lines nhl/line_history, out nhl/board, outcomes None,
  require_side True}. Verified by Cowork from origin 14:50Z. NHL WO1 NOT started as of 14:50Z (no worktree/branch).
  Amendment note for WO1 (paste with the launch prompt): extend that entry, don't add a second; use require_side as
  the no_view refusal (no extra flag); leave outcomes None in item 1, set 'nhle' in item 2 with the loader; item 2
  fixes edge_rank — score ranks edge across ALL scored rows of ALL files, conf_rank is 1..n within each freeze, so
  the conf-vs-edge band comparison compares different populations once a slate has two files.
- **Mac main tree is stuck (found 13:55Z):** an autostash re-apply conflicted at ~11:14-11:41Z on
  `golf/shadow/golf_daily_best_board.parquet`, `golf/shadow/golf_shadow_log.parquet`, `shared/last_updated.json`
  (golf dual-writer again, as on 09-20). HEAD = origin/main at 11:30Z; no Mac commit since. The autostash is kept
  as `stash@{0}`. Until cleared, nothing commits from the Mac tree and the Mac's copy of the tape goes stale — a
  freeze run on the Mac would read old prices. Jeff's command (below) takes origin's copy of the 3 files.

## NHL edge hunt (2026-09-29, Cowork) — NOTHING SURVIVES
Repo `research/layers/nhl_edge_hunt_2026-09-29/` (README, pre-registration sha256 `37ba3a17…`, scripts, full results
table) — written to the Mac, NOT committed yet. 123 pre-game conditions + pairs = 4,115 cells (moneyline 2,128 at real
SBRO closing prices 2007-23; totals 1,987, line-only triage then DK real prices 2023-26). Moneyline p<0.01: 21 observed
vs 21 expected, 0 BH passes. Totals: 5 BH passes, all artifacts of the discovery-era over-rate being 48% (juice-shaded,
unpriced lines); 1 reached holdout (under, away team lost last game by 3+, divisional): 50.9% vs 51.7% break-even at DK
prices, ROI -1.2% -> fails. Survivors 0. Descriptive leads (NOT bets): games won by 2+ rose from ~53% (2005-16) to
~60-62% (2021-25) -> favourite -1.5 fair price moved ~+187 -> +140 at a .60-.65 fav; untestable without puck-line
prices (forward: Pinnacle PL on the tape from 2026-27; or Odds API history ~12.6-25k credits). 60-min ties 21-25%.
Data defects found: 2025-26 `game_markets` backfill lost team identity on h2h / spreads / team totals (only totals
usable); `nhl/cache/odds_nhl_*.json` holds in-play/alt totals (1.5..51.5). Not missing any Hard Rock data — none exists.

## Edge hunt phase 2 (props) + Odds API history pull (2026-09-29)
- Props 2025-26 (7 books, 134,982 player-game-lines, graded from boxscores; pre-reg sha256 `3eb95b79…`, discovery
  Oct-Dec / validation Jan-Mar): two-way props 0 BH passes in-family; 8 assist-under cells passed the pooled rule but
  LOSE 3-5% at the median book price in both halves -> 0 bettable survivors. AVOID: 2+ goal (-64%) and hat-trick
  (-84%) Overs. Files: `research/layers/nhl_edge_hunt_2026-09-29/phase2_props/` (on the Mac, uncommitted).
- **NHL WO2 written, NOT run:** `research/nhl_layers/workorder_2_odds_history_2026-09-29.md` (project
  `claude/nhl_layers_workorder2_2026-09-29.md`). Claude Code pulls, stores only: (1) game lines h2h/spreads/totals
  with team names 2022-23..2025-26 (~40-52k credits), (2) 3-way 2024-25 (~13k), (3) props 2024-25 (~52k, likely
  next credit cycle). RESERVE 20k. Then Cowork runs the pre-registered scans: game lines D 2022-23+2023-24 / V 2024-25
  / H 2025-26; props D 2024-25 / V 2025-26; puck-line and anything first seen in shape tables -> 2026-27 forward only.

## Edge hunt phase 3 — game lines at real 9-book prices (2026-09-29 ~08:00Z)
- NHL WO2 RAN (branch nhl/wo2: script + test + log committed; DATA NOT COMMITTED, lives in the worktree
  `~/mlb-model-nhl2/data/odds_archive/nhl/history/` — 25 MB lines 2022-26 + 170 3-way files). Credits 96,269 -> 19,996
  (lines 62,538; 3-way 13,724). Props 2024-25 NOT pulled (~52,500). Verified from files: 2,005 snapshots, team names
  kept, Pinnacle on every game, Hard Rock absent; 771/5,608 events had no snapshot within 6 h of puck (afternoon starts).
- Scan `research/layers/nhl_edge_hunt_2026-09-29/phase3_lines/` (Mac, uncommitted): 1,335 cells, p<.01 14 vs 13 by
  chance, 0 BH, 0 survivors. H_PL (fav -1.5 underpriced?) NO: 37.9% vs Pinnacle 38.4%, -5.4% ROI. H_XG (declared
  deviation: top-xG team -> under; +5%/+9% in D/V) FAILED on 2025-26: 44.3% under, -15.0% ROI. 60-min draw 2024-25:
  20.1% vs 21.8% priced, -12.5% ROI.
- **Credits warning:** balance ~20k after WO2; daily captures burn ~1,100-1,400/day -> ~2 weeks before the 3,000
  floor unless the cycle resets first. Confirm the reset date on the Odds API account page.

## NHL simulation engine (started 2026-09-29) — the L4 model layer
Jeff: build a game-state hockey sim like the NFL engine. His choices: game-state sim; game lines first (props later);
must beat-or-match Pinnacle on a locked historical holdout before it gets weight. Decisions S1-S2 in
`research/nhl_sim/NHL_SIM_DECISION_v1.md`; plan `research/nhl_sim/NHL_SIM_PLAN_2026-09-29.md` (project
`claude/nhl_sim_plan_2026-09-29.md`). Seasons: 2021-22 warm-up, 2022-23 fit, 2023-24 validate, holdout 2024-25 +
2025-26 (lock file). **S-WO1 written, NOT run** (`research/nhl_sim/workorder_S1_2026-09-29.md`, project
`claude/nhl_sim_workorder_S1_2026-09-29.md`): play-by-play pull (6,560 games, free, ~66 min), event + strength-state
tables with null controls vs box scores, own xG model frozen on 2021-23, measured league constants JSON. Next: S-WO2
ratings, S-WO3 engine, S-WO4 pricing/validate, S-WO5 holdout. Files on the Mac, uncommitted until Jeff's command.

- **S-WO1 RAN** (branch nhl/sim-s1, 5 commits to 025494252; data in worktree ~/mlb-model-nhlsim1, gitignored).
  Verified from files (`research/nhl_sim/nhl_sim_s1_verification_2026-09-29.md`): holds — 6,560 pbp files, goals
  6,558/6,560 vs canonical, shot score state right, xG pre-regs held. WRONG — state_time score state = FINAL score on
  every span; shootout games carry up to 15 min phantom time; penalties_per_60 = 225.9 (units); "score effects" are
  state frequencies not rates; pull/EN constants 0 (sign bug); rush flag always False; pull hazard + shootout not
  measured. **constants_v1 withdrawn; do NOT merge nhl/sim-s1 yet.**
- **S-WO2 written, NOT run** (`research/nhl_sim/workorder_S2_2026-09-29.md`): rebuild the state timeline with exact
  null controls, constants v2 as rates (score effects, penalties, pull hazard, empty net, 3v3, shootout), real rush
  flag + xG v2, SOG-mismatch and 2025-26 scoring-drift reports. Continues on nhl/sim-s1. Next: S-WO3 ratings.

- **S-WO2 RAN and VERIFIED** (nhl/sim-s1 a1b02e7f6..f8fc2d24a; `research/nhl_sim/nhl_sim_s2_verification_2026-09-29.md`):
  state timeline fixed (3,600-3,900 s/game, score state right), constants_v2 as rates (penalties 3.77/team/game;
  5v5 3rd-period attempts/60 per team -1: 44.1, tied 41.0, +1: 37.2 — recomputed independently, identical; pulls at -1
  93.9% in last 3:00; SO conversion 32.3%), xG v2 with real rush (AUC 0.746 on 2023-24). 2025-26 goals ran ~6.8% BELOW
  xG (xG/goals = 1.068; earlier notes said 'above' — wrong direction, corrected 13:30Z) -> engine needs a point-in-time league finishing term. OK to merge nhl/sim-s1.
- **S-WO3 written, NOT run** (`research/nhl_sim/workorder_S3_2026-09-29.md`): point-in-time team + goalie ratings with
  measured shrinkage, leakage truncation test, league finishing term, ratings-only check vs Pinnacle on 2022-24 only.
  Next: verify S-WO3 -> S-WO3b (A1 as first S-entry + team modifiers) -> S-WO4 engine.

- **S-WO3 STARTED by Jeff ~11:30Z (running, not verified).** Let it finish — nothing in it conflicts with A1.
- **Amendment A1 (11:41Z, before any holdout; COMMITTED + pushed to main as fd4947d27 ~12:00Z):** `research/nhl_sim/amendment_A1_2026-09-29.md` (project
  `claude/nhl_sim_amendment_A1_2026-09-29.md`). (1) The engine is fit to outcomes only; any Pinnacle correlation is a
  one-time floor, never tuned toward. (2) The pass rule gains an incremental-information test: outcome ~
  logit(Pinnacle) + (logit(engine) - logit(Pinnacle)), and the engine earns weight only if the disagreement coefficient's
  90% CI is above 0. (3) Team-specific modifiers (score-state response, pull aggressiveness, PP style, rest/B2B/travel,
  goalie workload), each kept only if it improves 2023-24 log-loss on actual outcomes. These go in as the first S-entry of
  S-WO3b, written after S-WO3 is verified.

- **Amendment A2 (11:59Z, pre-holdout):** `research/nhl_sim/amendment_A2_2026-09-29.md` — grade the engine on its
  best picks: A pick = engine prob minus the median price's break-even >= 0.04; confident A pick = also engine >= 0.70;
  real only if holdout ROI > 0 with z >= 1.64 AND >= 0 in each holdout season, no band/month carrying it. Context: Pinnacle
  72%+ favourites hit 79.1% vs 78.3% break-even (2022-24); realistic skill = a few points over break-even, not 80% at -110.
- **Goalie-news layer WO G1 written, NOT run:** `research/nhl_layers/workorder_G1_goalie_news_2026-09-29.md` (project
  `claude/nhl_workorder_G1_goalie_news_2026-09-29.md`; supersedes NHL WO1 item 4): measure free starter sources (NHL
  API, ESPN) + lead time; alert on changes via existing Pushover (nba.modules.notify, import only) with a 3-credit price
  snapshot; 7-day "is there time to act" report. Decisions H3-H5.
- Hard Rock price reader NOT written: an automated scraper of Jeff's only legal book risks its terms and his account;
  default stays "alert -> Jeff checks the app". Jeff to decide.
- Still unbuilt: NHL WO1 (freeze-tool date slates, outcomes loader, packet) — the NHL pilot (Sep 29 - Oct 4) has no
  NHL-specific freeze tooling yet.

- **S-WO3 RAN, VERIFIED -> 7 defects, do NOT merge nhl/sim-s3** (`research/nhl_sim/nhl_sim_s3_verification_2026-09-29.md`,
  project `claude/nhl_sim_s3_verification_2026-09-29.md`). Holds: reproducible; split-half r/K (5v5 0.932/K 6.0, 0.798/20.7;
  PP 0.211; goalie 0.207/K 229); shuffled null ~0. WRONG: (1) league prior computed over ALL seasons incl. holdout;
  (2) no season boundaries / no carry-over (log's "each season starts at league mean" is false); (3) truncation test +
  "<=" mutation not run; (4) goalie ratings same issues, starter agreement unchecked; (5) PP/PK ratings + score adjustment
  missing; (6) S12 run with a simplified 5v5-only formula (totals -11.8%) and Pinnacle marked "not measurable" despite
  build_lines.py; (7) finishing term monthly, not point-in-time. Branch was cut from pre-rebase history (2,212-file diff,
  4.7 MB .bak) -> cherry-pick 97ded6c11, 2c6cad87a, 99556de37 onto a fresh branch instead.
- **S-WO3r written, NOT run** (`research/nhl_sim/workorder_S3r_2026-09-29.md`, project `claude/nhl_sim_workorder_S3r_2026-09-29.md`):
  worktree ~/mlb-model-nhlsim3r, branch nhl/sim-s3r off origin/main + the 3 cherry-picks. S13 point-in-time ratings
  (prior strictly before D, per-season accumulation, carry-over w measured 2021->2022 only, 5v5 score-adjusted + PP/PK +
  penalties, goalie fixes, starter agreement > 99%, null controls incl. "deleting 2024-26 rows must not change 2022-23
  ratings" which must FAIL on 97ded6c11); S14 point-in-time 30-day finishing term; S15 S12 as specified with Pinnacle via
  build_lines.py (bars unchanged: Pinnacle logit corr > 0.60, totals > 0.30, mean within +/-3% on 2023-24; single run).
  Next: verify S3r -> S-WO3b (A1/A2 S-entries + team modifiers) -> S-WO4 engine (start from any game state).

- **S-WO3r RAN, VERIFIED 14:43Z** (`research/nhl_sim/nhl_sim_s3r_verification_2026-09-29.md`, project copy same name
  under claude/). Branch origin/nhl/sim-s3r is clean (5 files off main). Reproduced exactly: Pinnacle logit corr 0.851/0.810,
  totals 0.480/0.433, mean total -8.2%/-9.3% (NOT HELD), null 0.049/0.011, actual-gd corr 0.308/0.263. Cowork measured:
  starter agreement 99.94% (box `starter` flag exists — CC said it didn't); Pinnacle's own actual-gd corr 0.333/0.287 on
  same games; engine incremental OLS t 0.63 fit / 1.52 validate (descriptive only). FIXED: per-season league prior strictly
  before D, season resets, goalie per-season. NOT FIXED: carry-over (measured w 0.784/0.805 unused, hardcoded 0.5, game 1
  only -> team SD 2.05 at game 1 collapses to 1.42 at game 2); truncation + mutation tests; old-code failures only
  "read from source"; PP/PK/penalties/score-adjust; PIT finishing term; S15 formula still simplified. **Hold the merge.**
- **S-WO3c written, NOT run** (`research/nhl_sim/workorder_S3c_2026-09-29.md`): same worktree/branch. S16 carry-over used
  as season-long shrink target (w from JSON), S17 PP/PK/penalties + score-adjusted 5v5, S18 truncation/mutation/old-code/
  starter tests, S19 PIT finishing + full S15 once. Vectorise + cache team_game_stats first (null: identical output).

- **S-WO3c RAN, VERIFIED 15:47Z** (`research/nhl_sim/nhl_sim_s3c_verification_2026-09-29.md`). Cowork RAN the deferred
  tests on the Mac: vectorised per-game stats == old (12,850 rows, max 1.8e-15); truncation + same-day-garbage test on 20
  dates of 2023-24 passes on new code (0/20) and FAILS on a mutant (20/20, 3.30) and on e17ace021 (20/20, 0.010) — one
  rebuild takes 1.4 s, not the claimed ~52 s. Carry-over now a season-long shrink target (team SD 3.05/3.34/3.25/3.41 at
  0/1/2/10 games; S16a HELD). S19 reproduced (Pin 0.842, totals 0.474, mean -8.9%, actual gd 0.256). S16b NOT HELD:
  carry-over raised Pinnacle agreement (0.810->0.842) but not outcome corr (0.263->0.256 validate). WRONG: goalie rating
  code deleted (stale parquet used; CHECK 3 fail), goalie w literal 0.3, .get(...,0.5) fallbacks; PP/PK/penalty ratings,
  score adjust, PIT finishing, full S19 formula all not done; branch history has duplicate/auto commits (27-file diff).
- **NEW DEFECT (Cowork): constants_v2 averages both sides of uneven states** — 5v4 "per team" 41.3/60 = (PP + SH)/2; PP
  side really ~71-73/60 at 0.103 xG/att; PP min per team-game 5.31 (formula 3.8); 5v5 47.6 min (formula 50). Arithmetic
  +0.6 goals/game ~= the whole -8.9% miss. Would have poisoned the S-WO4 sim. Caveat: diagnosed on 2023-24 aggregates, so
  the 2023-24 +/-3% mean-total bar is no longer blind.
- **S-WO3d written, NOT run** (`research/nhl_sim/workorder_S3d_2026-09-29.md`; 3 small items, "deferred" not allowed):
  rebase + commit S18 tests (port of `research/nhl_sim/cowork_checks/truncation_check_2026-09-29.py`) + starter test;
  restore goalie ratings with measured w, no literal weights, ratings manifest; constants_v3 side-specific. Next after:
  S-WO3e = PP/PK/penalty ratings + score adjust + PIT finishing + final formula run; then merge; then S-WO3b/S-WO4.

- **S-WO3d RAN, VERIFIED 16:30Z** (`research/nhl_sim/nhl_sim_s3d_verification_2026-09-29.md`). Holds: manifest sha256 match
  on disk; pytest re-run by Cowork (truncation pass, mutant caught, starter 12,842/12,844 = 99.98%); goalie code restored,
  PIT by code review, w measured 0.144, no default fallbacks; constants_v3 PP side 70.35/60, SH 12.30, PP 5.30 min/team-game,
  5v5 48.13 min (4/4 pre-regs HELD, nulls pasted). Open: constants "xg_per_attempt" is actually goals/attempt (v2 too);
  PP split home-PP only; goalie not in truncation test ("NOT DONE: empty" inaccurate); mutant is a re-implementation;
  branch history messy (58-file diff) but content = 9 sim paths, +1,917 lines, main untouched there. **Decision: squash
  the 9 paths onto main (command in chat), retire nhl/sim-s3r.**
- **S-WO3e written, NOT run** (`research/nhl_sim/workorder_S3e_2026-09-29.md`; new worktree ~/mlb-model-nhlsim3e, branch
  nhl/sim-s3e from main): S23 constants_v4 (goals vs xG per attempt separately, pooled orientations, nulls) + goalie in
  truncation test + real-file mutant; S24 PP/PK/penalty ratings + score-adjusted 5v5 (pre-reg r >= 0.907). Then S-WO3f:
  PIT finishing term + the one full-formula run (2023-24 mean bar non-blind), then S-WO3b (A1/A2 + modifiers), S-WO4 engine.

- **Squash of S13-S22 landed on main (5d535bc93).**
- **S-WO3e RAN, VERIFIED 17:12Z** (`research/nhl_sim/nhl_sim_s3e_verification_2026-09-29.md`). Holds: sha check, real-file
  mutant, 23 pass/0 skip, constants_v4 goals vs xG split + pooled PP (69.8/60; 5.11 PP min/team-game pooled). NEW DEFECT
  (Cowork): xG attached via merge on (game, period, second, team) double-counts same-second shots (1,036/1,072/712/716/628
  key-sharing rows per season); 2023-24 5v5 attempts tgs 89,944 vs events 89,391, goals 5,336 vs 5,332 — affects all
  team ratings since S-WO3r (goalie path unaffected); also explains v4 5v5 numerator 179,636 vs v2 178,012. constants_v3
  AND v4 have NO committed generator anywhere in git history (Cowork missed v3 at S3d; v3 is on main). S24 ~20%: PP/PK/pen
  ratings raw running totals, literal 7.0/3.8 defaults, penalties / 5v5 seconds; score adjustment skipped 3rd time; goalie
  truncation test skipped 2nd time. **Do not merge nhl/sim-s3e.**
- **S-WO3f written, NOT run** (`research/nhl_sim/workorder_S3f_2026-09-29.md`; same worktree ~/mlb-model-nhlsim3e/branch):
  S25 row-wise xG fix + exact event-count null test (must fail first) + build_constants_v5.py generator (5v5 numerator must
  = 178,012); S26 total_seconds, score-adjusted 5v5 with given code + pre-reg (adj r >= unadj r), PP/PK/penalty ratings with
  K/carry-over/shrink, goalie truncation test via goalie_ratings_from_games. Hard rule: STOP rather than "deferred".
  Next: S-WO3g = PIT finishing term + the one full-formula run (constants_v5), then S-WO3b, S-WO4.

- **S-WO3f RAN, VERIFIED + Cowork S27, 17:58Z** (`research/nhl_sim/nhl_sim_s3f_verification_2026-09-29.md` in the
  nhl/sim-s3e worktree). CC Item 1 held (row-wise xG; event-count test fails-then-passes; build_constants_v5.py; 5v5
  178,012). Score-adj pre-reg HELD (0.925 vs 0.908). CC broke the hard rule and made 2 false claims ("goalie in test";
  "ratings use adjusted columns"); PP/PK/pen target was a global 2021-23 league mean computed inside the build (within-fit
  leak: new fit-season truncation test fails 20/20 on a3a7bcecb, worst 0.71); compute_K(r, 82) doubled K since S-WO3
  (Cowork missed it before). **Cowork wrote S27 directly** (4th skip in a row): generic PIT structure for 8 team ratings,
  frozen hyperparameters (shrinkage_K.json, carryover_w.json via --measure-hyper), K = n_half(1-r)/r, ratio-of-sums r for
  PP/PK/pen, adjusted 5v5 actually used, goalie split (goalie_games.parquet + goalie_ratings_from_games), lg_* columns,
  manifest expanded, .gitignore for ratings parquets. r/K/w: share 0.925/3.34; xG/att 0.654/21.7; PP 0.703/17.3 (w .76);
  PK 0.630/24.1 (w .61); pen taken 0.658/21.3; drawn 0.504/40.4; goalie 0.185/87.1 (w .144). Tests 10+2 pass (old-code
  test Mac-only). Written to the worktree, NOT committed — commit command in chat (runs pytest first).
- **S-WO3g written, NOT run** (`research/nhl_sim/workorder_S3g_2026-09-29.md` in the worktree): Item 1 CC reviews S27
  (tests-first disagreements); S28 PIT 30-day finishing term + truncation/mutant; S29 sanity_check_v2.py — one run of the
  full formula (lg_-relative ratings, constants_v5, PP minutes from penalty ratings, SH, 4v4/3v3, goalie, F(D), 6v5/EN),
  actual total excludes SO goal, bars as S12 (2023-24 mean bar non-blind), CHECK 5 by month + n_prior bucket.

- **S-WO3g RAN, VERIFIED 18:53Z** (`research/nhl_sim/nhl_sim_s3g_verification_2026-09-29.md`). S30 one-run (2023-24):
  engine gd vs actual 0.274 (Pinnacle 0.287); engine total vs actual 0.032 (Pinnacle 0.116); corr w/ Pinnacle logit 0.898
  HELD; w/ Pinnacle total 0.295 NOT HELD (bar 0.30); mean total -0.7% (non-blind). WRONG: S29 finishing_term.parquet had
  NO generator and used in-season windows of 38+ games (Cowork's 300-game rule was unreachable: 30-day window median 210
  games — Cowork spec error, CC deviated silently); F truncation test/mutant not written; S28 review wrote no tests;
  unrequested goalie clip (never binds). **Cowork S31:** finishing_term_from_games in ratings.py (min 150 games else prev
  season's last 30 days), truncation + mutant + rules tests (15 pass). S30 NOT re-run. Fit-season diagnostic: totals
  signal only in 5v5 (0.076); PP minutes (SD 1.4) and PP xG add noise; goalie sum right sign. **Decision: squash
  nhl/sim-s3e sim paths onto main (command in chat).**
- **S-WO4a written, NOT run** (`research/nhl_sim/workorder_S4a_2026-09-29.md`; new worktree ~/mlb-model-nhlsim4, branch
  nhl/sim-s4): S32 engine.py (1-s steps vectorised, penalties/PP end on goal, score effects, home, pull hazard measured
  properly into constants_v6, EN, 3v3 OT, shootout +1, start_state API, no literal rates, 6 tests) ; S33 realism report
  league-average vs actual 2022-23 with 9 pre-registered bands. Runtime pre-check: 20 games x 10k sims first; Item 2 < 1 h.
  Next: S-WO4b team inputs + prices + 2023-24 validate (A1 incremental test, A2 picks descriptive), S-WO5 holdout.

- **Squash S23-S31 on main (0a0783aa3).**
- **S-WO4a RAN, VERIFIED + Cowork engine rewrite S34/S35, 19:37Z** (`research/nhl_sim/nhl_sim_s4a_verification_2026-09-29.md`,
  in worktree ~/mlb-model-nhlsim4). CC's S32 engine: only HOME could pull (away trailing -> home EN goals 0.000/g), every
  penalty (majors/misconducts) made a PP, home q effect doubled, no OT penalties, ~20 .get(literal) defaults ("no literals"
  claim false), constants_v6 + realism script had NO generator (4th time). Realism S33 4/9. **Cowork S34:** build_constants_v7.py
  (v5 + pull hazard re-measured 1,821 pulls + PP-creating penalties 2.88/team-game, shares 2/4/5-min .973/.012/.015),
  engine.py rewritten (symmetric pulls, PP-creating penalties, PP goal ends minor/half double, OT 4v3, sqrt home q, no
  .get), realism_report.py (100k sims one matchup, 66 s), test_engine 11 pass. **S35 realism 6/9 HELD:** goals -2.4%,
  SO, PP opps (2.85 vs 2.96), EN, 1-goal +1.4pt, home +1.0pt HELD; NOT: ties -3.0pt, PP goals -12.5%, dist 0.017 (k=7).
  **Root cause of PP miss:** build_events state spans hold a play's situationCode until the NEXT play, so PPs outlive
  their penalty (actual PP span median 124 s, 46% > 125 s) -> PP seconds inflated, all PP rates per 60 understated
  (since S-WO1; ratings pp/pk seconds too). Not merged.
- **S-WO4a2 written, NOT run** (`research/nhl_sim/workorder_S4a2_2026-09-29.md`): S36 fix PP expiry in build_events +
  nulls (shots/penalties byte-identical, game seconds unchanged, single-minor PP <= 121 s, strength-label agreement not
  worse) + rebuild whole chain (events, ratings --measure-hyper, v5, v7); S37 realism re-run (pre-reg PP goals within
  +-8%, PP minutes +-5%); S38 tie trajectory table sim vs actual (descriptive, no engine change).

- **S-WO4a2 RAN, VERIFIED + Cowork S39, 21:25Z** (`research/nhl_sim/nhl_sim_s4a2_verification_2026-09-29.md`). S36 PP-expiry
  fix correct (merged PP spans median 120 s, ~5% > 125 s; CC mis-reported per-play median 12 s); S37 PP goals -5% HELD;
  CC skipped null (d), S38 sim side never measured ("implied"), r/K/w not pasted. **Cowork S39:** measured tie trajectory
  (sim ties low from P1 and in last 10 min); constants_v8 (build_constants_v7.py --v8) = 5v5 attempts/60 and goals/att by
  time bin (P1, P2, P3 >10, 10-5, last 5) x own score diff (+-3), fit 2021-23; engine uses it (replaces base x v2 score
  mults, which were relative to per-period tied rates but applied to the all-state average). **Realism 2022-23: 9/9;
  2023-24 (first OOS): 8/9** (1-goal +2.1pt vs 2.0 bar). Caveat: structure chosen after seeing 2022-23 trajectory; 2023-24
  run once. PP r 0.703->0.713, K 17.3->16.5 after rebuild. **Decision: squash nhl/sim-s4 sim paths to main (not v6).**
- **S-WO4b written, NOT run** (`research/nhl_sim/workorder_S4b_2026-09-29.md`; new worktree ~/mlb-model-nhlsim4b): S40
  game_inputs.py (ratings/goalie/F -> TeamMultipliers, raise on missing, q added to v8), S41 price_games.py (2022-23 +
  2023-24, seed=game_id, P(ML), reg 3-way, O/U at Pinnacle line, PL), S42 2023-24 prediction test: log-loss/Brier vs
  Pinnacle, reliability, **A1 incremental test** (disagreement coef 90% CI > 0?), totals same, CHECK 5 breakdowns, A2 picks
  descriptive at real median prices. No calibration fit on 2023-24; holdout locked until S-WO5.

- **Squash S32-S39 on main.** S-WO4b ran in ~/mlb-model-nhlsim4b (branch nhl/sim-s4b, 8 clean files, NOT merged).
- **S-WO4b VERIFIED 23:53Z** (`research/nhl_sim/nhl_sim_s4b_verification_2026-09-29.md`, decision S43). Reproduced: 2023-24 ML
  (n=1,138) log-loss engine 0.6647 vs Pinnacle 0.6567, Brier 0.2361 vs 0.2326; **A1 disagreement 0.375, 90% CI [-0.105, 0.854]
  -> engine adds no significant info, no layer weight.** 2022-23 (fit): LL 0.6669 vs 0.6568, A1 0.231 [-0.163, 0.624].
  **Engine under-confident:** logit SD 0.363 vs Pinnacle 0.514; calibration slope 1.32 (2023-24), 1.15 (2022-23); deficit
  all in |eng-pin| > 5 pt games. **A2 ML picks at real median prices: 2023-24 n=488 ROI -3.7% (SE 5.8%); 2022-23 n=587 -1.0%.
  No edge.** WRONG: totals priced with a normal approximation (p_push 0.16 on x.5 lines) -> all S42 totals invalid; totals A1,
  reliability, fav/dog, A2 not done (hard rule broken again).
- **S-WO4c written, NOT run** (`research/nhl_sim/workorder_S4c_2026-09-29.md`): S44 total-goals pmf per game from sims (null: ML
  columns identical on re-price), totals A1/LL, reliability, fav/dog, disagreement buckets, A2 picks ML+totals; S45 calibration
  map fit on 2022-23 only, applied once to 2023-24 (pre-reg: improves raw 0.6647, still worse than Pinnacle 0.6567).
  After: A1.3 team modifiers (rest/B2B/travel/goalie workload), then S-WO5 holdout.

- **S-WO4c VERIFIED 2026-09-30 01:40Z** (`research/nhl_sim/nhl_sim_s4c_verification_2026-09-30.md`). Totals now from sim pmf
  (re-price null max diff 0). 2023-24: ML LL 0.6647 vs Pin 0.6567 (A1 0.376 [-0.103, 0.869]); totals LL 0.7001 vs 0.6942, A1
  -0.006 [-0.439, 0.458]; totals reliability flat (no info), engine mean P(over) 0.449 vs actual 0.487 (under-lean; CC called
  totals slope 0.16 "under-confident" — it means OVER-extreme). Calibration fit 2022-23 -> ML 0.6642 (pre-reg HELD). CC's
  "NOT DONE empty" false: A2 had hit rates only. **Cowork A2 at real median prices: ML 2023-24 n=488 -3.7% (SE 5.8), 2022-23
  -1.0%; totals 2023-24 n=217 +0.8% (SE 6.7) but 194/217 unders, 2022-23 -6.1% (315/319 unders) -> one-sided bias, not signal.**
  **Conclusion: pre-game engine does not beat the market.**
- **Jeff's decision (2026-09-30):** the engine is a LAYER, not the whole system; assume the edge exists and find where the
  engine produces something meaningful -> one more pre-game push (option 2).
- **S-WO4d written, NOT run** (`research/nhl_sim/workorder_S4d_2026-09-30.md`): S46 game-level pace factor Gamma(k) fit by
  method of moments on 2021-23 total-goal variance (skip if variance gap not confirmed); S47 A1.3 modifiers (rest/B2B,
  backup goalie) estimated on 2022-23 by Poisson offset regression on engine expected goals, kept only if 2023-24 ML
  log-loss improves; S48 full report + pre-registered regime family (R1 early season, R2 B2B, R3 backup goalie, R4
  |diff|>5, R5 engine-dog, R6 goalie-quality) x ML/totals, A1 coefficient + ROI, BH 10% -> survivors only go to holdout.

- **EDGE HUNT 2026-09-30 (Cowork; after Jeff's "find it, its there")** — repo `research/nhl_sim/edge_hunt_2026-09-30/`
  (on the Mac, UNTRACKED; NHL-L1 item 1 commits it), project `claude/nhl_edge_hunt_clv_ev_alt_2026-09-30.md`.
  - PREREG_CLV (engine predicts Pinnacle's move?): FAILED. Clean-set slope 2023-24 -0.004 [-0.032, 0.024]; 2022-23
    -0.027; all-games 2022-23 significantly NEGATIVE. The engine is not an opinion edge (4th independent failure).
  - PREREG_EV (sha d1957cb6; best of 8 books >= 2% vs Pinnacle fair, same snapshot, 2022-24): CLOSE H1 FAILED (131
    bets, -16.6%, bigger EV = worse -> at close Pinnacle is the stale one). EARLY (~25 h, secondary): CLV +1.28% (SE
    0.38), both seasons.
  - PREREG_EV2 (sha 7923c858; early rule unchanged, 2024-26, one run): **HELD. CLV +2.70% (SE 0.76), 90% lo +1.44%;
    +2.5% / +2.9% by season. ROI -3.2% (SE 15%, 55 bets = noise).** First NHL lead to keep its sign out of sample.
    Price edge, not a model edge. Volume ~27/season at one early snapshot; forward 30-min tape will show real volume.
  - PREREG_ALT (sha 17993818): engine conditioned on Pinnacle ML + total (strength s, pace m; grid 9x7x20k,
    market_grid_v1_cowork.npz sha 98333c7c) prices off-point soft totals. H3 FAILED (35 bets, CLV +0.9% SE 0.83).
    **Structure check: engine puck line vs Pinnacle's own PL log-loss 0.6605 vs 0.6606 (n 2,283) -> engine game
    structure is Pinnacle-grade; use it to price derivatives Pinnacle doesn't hang.**
  - Engine speed measured: ~770 sims/s per core (20k sims = 26 s).
  - Worktree constants_v8 differs from main's only by q_league_xg_per_non_en_attempt (unused by league-average grid).
- **NHL-L1 written, NOT run** (`research/nhl_sim/edge_hunt_2026-09-30/workorder_NHL_L1_2026-09-30.md`, project
  `claude/nhl_workorder_L1_price_layer_2026-09-30.md`; worktree ~/mlb-model-nhlL1, branch nhl/price-layer-l1, 0 credits):
  L1a commit record + nhl/sim/market_grid.py reproducing the npz exactly; L1b shadow on WO12's live tape
  (line_history/season=2026, 30-min, 9 books, NO Hard Rock) -> flags.parquet (EV2 + ENGINE_ALT), Hard Rock
  price-to-beat CSV, nightly CLV grader, parity tests vs ev_test/alt_test logs; proposes cron lines only; L1c report +
  pre-registered forward bar (EV2, 8 books, first snapshot >= 12 h, n >= 150, CLV 90% lo > 0; dead at n = 400).

- **S-WO4d RAN, VERIFIED 03:45Z** (`research/nhl_sim/nhl_sim_s4d_verification_2026-09-30.md` in ~/mlb-model-nhlsim4b,
  project copy). S46 engine OVER-disperses totals (within-game var 5.44/5.54 > actual across-game 5.18/5.34) -> no pace
  factor (right); team-input mean total 6.08 vs 6.36 (2022-23), 6.19 vs 6.23 (2023-24); the 2023-24 under-lean is shape.
  S47 B2B coefs (-10.8% own, +8.1% opp) estimated with offset mean_total/2 (team split ignored), NOT re-priced/validated.
  S48: CC ran 5 of 12 tests; no generators committed for S46-S48 (hard rule broken again). **Cowork ran all 12
  (cowork_checks/s48_complete/): ONE BH survivor — ML R6 both starting goalies below league average, n 133, A1 coef
  3.78 [1.57, 5.98], p 0.0024 (thr 0.0083); ML R5 engine-underdog p 0.018 just misses.** Cautions: same regime in
  2022-23 (descriptive) coef -0.05 (n 212); A2 ROI inside regime -4.0% (SE 21%). Candidate "S48-ML-R6" goes to the
  edge-hunt ledger, frozen; confirmation needs 2024-25 engine prices; 2025-26 stays locked. Do not merge nhl/sim-s4b
  until S46-S48 generators are committed.
- **NHL WO1 RAN 2026-09-30 (two fresh Claude Code sessions), VERIFIED by Cowork from origin/nhl/wo1 (7 commits
  1075895bb..f831c88e8, 1,846 insertions):** one `SPORTS['nhl']` entry (extended, not duplicated), `slate='date'`,
  `drivers_required`, `require_side` as the refusal; `nhl/pipeline/nhl_outcomes.py` (agreement 1,177/1,177 vs the
  canonical CSV, SO rule changes the totals grade); `score()` now has CLV vs Pinnacle close (last tape snapshot
  before commence; moved lines → NaN, never imputed), baselines (a) Brier freeze-vs-close and (c) follow-the-move,
  `--from/--to` for date-keyed sports, edge_rank per freeze file; `shared/layers/packet.py` +
  `nhl/layers/build_packet_nhl.py` (L1 market, L2 news, L3 history point-in-time, L4 model absent; `--packet`
  required on NHL freezes, hashed in the manifest); `nhl/pipeline/probe_goalie_sources.py` (NHL API and ESPN
  give NO pre-game starter — HELD; DailyFaceoff / LeftWingLock / MoneyPuck are HTML candidates → G1's default of
  "alert → Jeff checks the app" stands). Proof-of-run on 2026-09-29: 8/9 lines got CLV (mean −1.4%), close
  snapshots named. Football null controls byte-identical. 104 pass / 1 pre-existing red
  (test_score_first_side_and_units: D236(a) changed `_first_side_won` to require snap_played — the test was
  never updated; football chat's to fix). Gaps: H4b added no tests; ESPN abbrevs LA/NJ/TB/SJ ≠ LAK/NJD/TBL/SJS
  (Cowork's E work already has the alias map: NJ→NJD, TB→TBL, LA→LAK, SJ→SJS); packet source scan reads every
  parquet (74 snaps for 5 games — fine for now). **Merge:** `git checkout main && git merge --no-ff nhl/wo1`.
- **Edge-hunt chat (new Cowork chat, started by Jeff ~03:00Z)** runs from `claude/nhl_sim_edge_hunt_prompt_2026-09-30.md`;
  it owns `claude/nhl_sim_edge_hunt_ledger.md`. Inputs copied to ~/mlb-model/research/nhl_sim/edge_hunt_2026-09-30/inputs/.

## NHL SIM EDGE HUNT — session 2026-09-30 (mandate chat; Cowork, 02:30-05:10Z) — READ THIS BEFORE ANY SIM WORK
Ledger of record: `claude/nhl_sim_edge_hunt_ledger.md` (44 p-values so far; BH across all of them). Files:
`research/nhl_sim/edge_hunt_2026-09-30/hunt_2026-09-30/` on the Mac (scripts, logs, work orders; untracked until
NHL-L1 item 1 or C-WO1 commits the folder), plus `prices_fixed_goalie_2022_2023_cowork.parquet` (sha256 3bbf36f5…) and
`market_grid_v2_cowork.npz` (6f9fe1ce…) beside it; 2024-25 swapped-engine prices in `logs/cowork_stage/prices2024/`.
- **ENGINE DEFECT C-01: goalie ratings swapped between teams in `nhl/sim/game_inputs.py` (S40).** `h_mult.goalie_save
  = 1 - a_gsax/q`; the engine applies `opp.goalie_save` when the other team attacks, so each team's scoring was scaled
  by its OWN goalie. Every S41-S48 number and PREREG_CLV came from that object (CHECK 3). Fixed re-price (same seeds,
  2,000 sims, null: unfixed re-pricer reproduces S41 to max diff 0): 2022-23 ML log-loss 0.6669 → 0.6594 (Pinnacle
  0.6568), 2023-24 0.6647 → 0.6646; A1 2023-24 −0.05. Fix is real; the engine still trails Pinnacle out of sample.
  **C-WO1 written, NOT run** (`claude/nhl_sim_workorder_C1_2026-09-30.md`): test-first fix, re-price, reports, S46-S48
  generators, 16-regime family. Branch nhl/sim-s4b stays unmerged until it lands.
- **S48-ML-R6 confirmation (2024-25, one run, frozen swapped engine): FAILED** — n 205, A1 coef −0.58 [−1.90, +0.74],
  99 picks ROI −15% (SE 13%), CLV at close −1.6%, negative every month. Dead, not re-thresholded.
- Fixed-engine regime family (16 tests incl. R7 pace / R8 penalties, 2023-24): NO survivors (min p 0.0064 = ML R6,
  vs thr 0.0063; its 2022-23 coef 0.20). Descriptive lead only: ML R8 (both teams > 1.05 × league penalties) coef
  +3.4 / +2.9 in both seasons, n 75 / 60 → branch D for power.
- A-01 / A-03: the fixed engine with the ACTUAL starter predicts Pinnacle's opener→close move (ML in strict backup
  games, slope 0.064 / 0.066, p 0.0035 / 0.0020, clean-set null ≈ 0.02 ns; totals slope 0.066 / 0.036, p < 0.002).
  Worth < 1 pt of price: A-01 H2 CLV −0.9%; A-05 (early best-of-8 + engine, ML) −0.5 / −0.6%; A-06 (totals) −0.6 /
  −1.2%, 84-94% unders. Dead as bets. The engine's goalie/lineup knowledge is real and too small to beat soft vig.
- B-01 3-way 2024-25 (exploratory; season-role rule pending): engine conditioned on Pinnacle ML + total reproduces
  Pinnacle's 3-way (3-class log-loss 1.0186 both; |diff| 0.5 pt); 2 flags in 20,820 soft quotes. Dead. Pinnacle
  3-way overround 1.044, soft 1.05-1.12. Third demonstration that structure = Pinnacle-grade and structure ≠ edge
  wherever Pinnacle hangs the market. Grid v2 (`market_grid_v2_cowork.npz`: final + regulation + P1 + P1-2 joint
  pmfs; final pmf identical to v1) is ready for team totals / period markets on the forward tape.
- A-04 (soft books lag a Pinnacle move): 0 stale quotes at the hours-apart cadence → forward 30-min tape only.
- C-02 totals over-dispersion: not penalties (actual var/mean 1.4-1.8 vs engine 1.0, but PP goals match), not EN;
  ~5-8% excess sits in 5v5 dispersion / between-team correlation (−0.10 engine vs −0.12 actual). C-03: team-specific
  score-state responses have split-half r ≈ 0 (trail −0.07 / −0.01) — do NOT build A1.3 score-state modifiers.
- **Branch E (2026-09-30 06:30-09:40Z):** E-WO1 (Cowork order) pulled 800 sport-level historical snapshots, 80 nights
  of 2023-24, T0+2:00..+2:45 at 5-min steps (verified 800 DISTINCT timestamps; CC's "~15-min granularity" was
  wrong), h2h + totals, 16,000 credits → balance 2,088 before the reset. **No Pinnacle: `regions=us` excludes it
  (Cowork's error).** 15 US soft feeds. ESPN pbp for 732 games, `wallclock` on every play; Cowork built the
  state table (`hunt_2026-09-30/e/`): ESPN wall-clock → game clock validated 99.7% against state_time; 174 games
  with live rows (only ~3.9 started games per snapshot). E-02: engine (league-average, conditioned on the pre-game
  Pinnacle close, started from the snapshot state) vs live median: first pass +64% ROI = ARTEFACT (stale quotes
  median 35 s old, tails to 11 min; mybookieag re-stamps off-market prices; barstool too). On fresh quotes with no
  event in 120 s and those feeds excluded: ML engine == market (0.5110 vs 0.5118, A1 ns). LEAD only: engine live
  UNDER picks +21% ROI (clustered SE 11%) on 71 games, 96% unders, post-hoc → **E-03 pre-registered** for the
  2024-25 in-play pull (~16k, October). Live under hit 56-59% at the majors vs 52-54% fair in 2023-24; blind
  per-game ROI −1.2%. Exclude mybookieag / barstool from any live rule forever.
- Credits: 100,000 reset at 2026-10-01 00:00Z (Jeff's account page). October plan: reserve ~40k for the tape;
  E-WO2 (2024-25 in-play, ~16k) → E-03 one-shot; D-WO1/C-WO1 cost 0; no props, no derivative history.
- **D-WO1 written, NOT run** (`claude/nhl_sim_workorder_D1_2026-09-30.md`): probe 6 old games for fields, pull
  2010-11..2020-21 pbp + boxscores (~11,900 games, ~1.8 h each, 0 credits), event tables with pre-registered bands,
  xG v2 calibration by season, written walk-forward plan. D-WO2 (fit windows + pricing, ~9 core-hours) after Cowork
  verifies D-WO1. Real SBRO closing ML/totals 2007-2023 already in `edge_hunt_2026-09-30/inputs/games.parquet`.
- Branch E (live): no historical in-play prices exist and NHL pbp has no wall-clock → forward-only. Proposed probe
  (not ordered): VM poller for games in the last 6 min of P3 within one goal — NHL live pbp (free) + Odds API event
  odds (h2h + totals) every 30 s ≈ 24 credits/game, ~250/night, ~7.5k/month. Not before the credit cycle resets.
- Open decisions for Jeff: season roles for markets with no 2022-24 history (proposal in the ledger); whether the
  fixed ML R6 (p 0.0064, 2022-23 coef 0.20) gets a confirmation despite failing the both-dev-seasons rule; credits
  balance + reset date (Cowork cannot reach the Odds API: 403 from the bridge); paste order: C-WO1 (small) then D-WO1.
- Bridge notes: `~/mlb-model/logs/cowork_stage/` holds Cowork's staging tarballs and the chunked 2024-25 pricer
  (`price_2024_chunk.py`); `logs/` is gitignored. Background jobs do NOT survive a bridge call (≤ 180 s each); the
  Mac VM prices 2,000 sims in 1.2 s vs 3.9 s in the container — chunk long runs through the bridge, 300 games/call.

- **Golf single-writer fix (2026-09-29 ~16:05Z, ops, not NHL):** Mac `com.mlbmodel.golf.odds.refresh` (daily 7am ET = 11:00Z)
  and the VM cron (11:00Z) both ran golf_daily_runner -> dual writer on golf/shadow parquets (the recurring pull conflicts);
  only the Mac ran push_golf.py (golf_results.json). VM cron (root@142.93.242.4, backup /root/crontab_backup_2026-09-29.txt)
  now runs `(runner --capture X && python3 push_golf.py)` on all 5 golf lines; test push_golf on VM OK (16:02Z, 24,262 bytes).
  Step B (Mac: unload + rename 5 golf plists .disabled — 3 were malformed and never loaded; strip 51 dead /root lines from
  Mac crontab, backup ~/crontab_backup_2026-09-29.txt; reset dirty golf files) CONFIRMED by Jeff ~16:15Z: 5 plists .disabled, Mac crontab 0 /root lines (only SHELL= + comments left), golf tree clean. Record in
  ops doc: golf VM_CANONICAL. Also: shared/git_push.sh SAFE_FILES lists golf files — revisit (single writer now).

- **Situation hunter (Jeff: "assume 80% is possible, subset of situations"):** `research/nhl_sim/SITUATION_HUNTER_2026-09-29.md`
  (project `claude/nhl_situation_hunter_2026-09-29.md`). 80% at -110 needs a ~28-pt information gap; only time
  (live state, news), book mechanics (stale lines, SGP correlation) or structure can hold one. Ranked hunts: A live
  pulled-goalie/empty-net, B live power plays/after goals, C goalie/scratch news (WO G1), D prop promotions (PP1/top line),
  E SGP correlation vs engine joint sims, F Hard Rock stale vs Pinnacle. **Engine requirement added for S-WO4: simulate
  from any mid-game state** (live pricing).
- **Rink scorer bias on SOG props — tested and DEAD** (`research/nhl_layers/rink_bias_2026-09-29/`, pre-reg sha256
  b80eb9e3…): rink factors +/-5-8% but unstable (season r 0.40 / 0.17 / 0.02; pre-reg > 0.4 NOT HELD); 2025-26 SOG props
  at top rinks (Over) 50.3% vs 50.5% fair, -7.0%; bottom rinks (Under) 48.8% vs 49.1%, -7.1%.

## NHL SIM EDGE HUNT — session 2026-09-30 continued (Cowork, 09:40-21:00Z) — what landed, what is on disk, what is next
Ledger of record unchanged: `claude/nhl_sim_edge_hunt_ledger.md` (54 p-values; whole-ledger BH 10% survivors unchanged;
NOTHING FOUND). Read its final STATUS block first.
- **C-WO1 DONE and VERIFIED from origin** (nhl/sim-s4b: S49 56d006f1a, S50 28e9f834a, S51 79ba839c6, S52 1583dedfc,
  log 5deaac141). Goalie direction fixed in `nhl/sim/game_inputs.py` with a failing-then-passing test; 2022-24 re-priced
  (matches Cowork's fixed parquet to 0.0000 on 2,624 games); the 2023-24 pre-registration HELD on none (LL 0.6646 vs
  Pin 0.6567; A1 −0.05); 16-regime family on the fixed engine NO SURVIVORS (reproduces `a02_regimes_fixed.csv`).
  S46/S47/S48 generators committed as code. **The fixed engine is the only engine from here; branch still unmerged.**
- **D-WO1 DONE and VERIFIED from origin** (nhl/sim-d1: 2e7c718c5..94a74f349; worktree ~/mlb-model-nhlD, pbp symlinked
  to ~/mlb-model-nhlsim1/nhl/cache/pbp/). 2010-11..2020-21 pbp + boxscores + event tables; goals 100% vs boxscores;
  xG v2 valid across eras. **Cowork found the real cause of CC's "state time issue pre-2019": the old NHL API
  play-by-play is not chronological** (plays with earlier timeInPeriod listed after later ones); build_events.py
  makes strength spans from consecutive plays → overlapping spans → 2015-16 per-game state-time median 3,699 s
  (p90 4,292 s) vs 3,600. All 2010-2018 per-60 rates / PP seconds / pull flags / shot score-states are contaminated
  until the sort fix. Also open: D2 headline 12,592 games vs per-season sum 12,502; 2021-25 byte-identity null not run.
- **D-WO2 WRITTEN, NOT RUN** (`claude/nhl_sim_workorder_D2_2026-10-01.md`; on the Mac in `~/mlb-model/…/hunt_2026-09-30/`
  and `~/mlb-model-nhlD/…/hunt_2026-09-30/`). Item 0 D5 sort fix (test first, 3 nulls, rebuild 11 seasons); Item 1 D6
  walk-forward windows {T−2, T−1} for T=2012..2020 with the engine's r/K/w measured per era and 4v4/3v3 OT handling;
  Item 2 D7 price ~10,850 games (~55 min on the Mac); Item 3 D8 evaluation at the SBRO close with three pre-
  registrations, the lead being regime R8 (both teams' penalties > 1.05× league) pooled over 9 seasons → if its ML A1
  90% lower bound > 0 it is frozen as D-R8 for CONFIRM on 2022-24 at Pinnacle's close (not to be looked at in D-WO2).
- **E-WO2 DONE (data acquisition, ~2.51M credits; E4 + E5 complete, E6 props + E7 hourly NOT pulled).** On disk in
  ~/mlb-model-nhlE (gitignored): `data/odds_archive/nhl/history/inplay/season={2022,2023,2024,2025}` = 15,986 / 16,545 /
  16,466 / 14,234 five-minute snapshots, 10 books INCLUDING PINNACLE, `book_last_update` column (1.2 GB);
  `event_markets/season={2023,2024,2025}` = 2,686 / 2,678 / 2,664 files at T−24h and T−1h (h2h_3_way, totals_p1,
  h2h_p1, spreads_p1, team_totals, alternate_totals, alternate_spreads, h2h_ot; 126 MB). E-WO1's 800 `regions=us`
  snapshots quarantined at `inplay/_quarantine_e1_regions_us/season=2023` and gap-filled (752 calls) — one schema
  across all four seasons. The order's spend cap was tracked per run, so a resume overran it by ~110k: future bulk
  orders must track cumulative spend across resumes. The NBA chat's NBA-D1 ran on the same account concurrently;
  its result is in that chat.
- **E-03 is now runnable** (2024-25 in-play with Pinnacle; pre-registration unchanged, one shot). Needs the 2024-25
  state table (ESPN wallclock, `hunt_2026-09-30/e/build_state_table.py`) then `e02_live.py` on the pre-registered
  cut. ~1 h in Cowork. Not run.
- **V-01 (Jeff's arena/ice idea) DEAD at Gate 1**: rink scoring effects do not persist season to season (r −0.02),
  no climate pattern, closing total has nothing to miss (ledger V-01). Same verdict as the scorekeeper test.
- Discussion with Jeff recorded in chat, not as findings: a perfect sim would beat Pinnacle; this one does not because
  its inputs are the public season-to-date aggregates Pinnacle already prices; the way to a Panthers "−3.5 vs −1.5"
  gap is information Pinnacle lacks or a structurally better player/goalie model (C-04 diagnostic → player layer via
  shift-chart RAPM + DailyFaceoff lineups, or goalie model + K tuning); referee crews; fantasy numbers are the same
  box-score inputs the props books already price (a layer, not an edge, until the tape says otherwise); the layers
  idea is forward-only and lives in the WO1 pilot.
- **Fun parlays (N54, not research):** two NHL 5-leg parlays + one 5-leg NHL player-prop parlay placed at Hard Rock
  for 2026-09-30/10-01 slates; logged pre-kick with the slips at `research/nhl_layers/pilot_picks/
  2026-09-30_cowork_fun_parlays.md`; lines from `live_lines_2026-09-30_2044Z.md` (15 credits). Multi-sport slip NOT
  played. GRADE on 2026-10-01 (PHI@NJD Over 5.5 after Thu) vs results and Pinnacle close; append to the log.
- NHL-L1 (price layer on the tape) still NOT run; reader method file still not written (main Layers chat).

## Defects found in the pre-check (all in H2)
1. Capture script folder rule would write NHL to `data/odds_archive/icehockey_nhl/` (MLB already sits in
   `baseball_mlb/`) — also found by the main chat; fixed in WO12.
2. Its season rule (month >= 3) would split an NHL season at 1 March -> NHL uses start year (WO12 fixes the tape;
   NHL WO1 item 1 applies the same rule when reading).
3. `data/odds_archive/nhl/props/` is last season's 7-book historical backfill (no Hard Rock, no Pinnacle,
   calendar-year partitions) — live multi-book NHL markets go to `nhl/event_markets/` (WO12).
4. No NHL model output exists for 2026-27 (outputs end 2025-04-17) -> baseline (b) `absent` for now.
5. For the football chat, not fixed here: NFL props puller saves a run into the LAST event's month and hardcodes
   15 credits/event; `log_ai_opinions.py score` grades a player missing from PBP as 0.

## Readiness checklist (plan §8) — ticked only from files, with the date
Capture
- [x] NHL on the 30-min tape: 94 snapshots at 30-min cadence through 2026-09-30 05:30Z (Cowork, from files)
- [x] Hard Rock among NHL books returned? NO (WO12 dry run 14:12Z, 0/33 games) -> book of record Pinnacle (H2 addendum, 2026-09-27)
- [ ] Props pull: markets listed from the API, cost per pull printed, --floor present (capture WO12 item 1)
- [x] Goalie source measured (H6, 2026-09-30): no free pre-game API; capture with timestamps NOT built (G1)
Log and scoring
- [x] `nhl` in SPORTS, date-keyed (H3, 2026-09-30, origin/nhl/wo1 — unmerged)
- [ ] Freeze refuses without --reader-model, refuses started games, reads prices from the tape (tests extended)
- [x] Packet written + hashed beside every frozen file; drivers required on every row (H3 + H5, 2026-09-30)
- [x] Outcomes loader grades real finished games end to end; OT/SO rules stated (H4, 2026-09-30)
- [ ] Hard Rock FL hockey settlement rules VERIFIED (H2 lists them as assumed) — Jeff: check the app's rules page,
      or Cowork reads Hard Rock's published house rules
- [x] Baseline (c) logged on the same lines (H4b); (b) absent until a model layer exists
Discipline
- [x] Pilot dates and record start written into the decision doc before the pilot (H1, 2026-09-27) — commit pending
- [ ] Reader method file frozen for the pilot (`research/layers/reader_method_v1.md` — not written yet; main
      Layers chat or this chat before Tue)
- [ ] Hash posted in capture status before first puck, every slate

## Open (named decisions, not momentum)
- Props in the scored universe? Default NO for the pilot (H1); decide before 2026-10-05 from measured line counts.
- Props capture times — set by capture WO12 (16:00Z and 22:30Z).
- Which goalie source to trust — after the pilot, from WO1 item 4's measurement.
- NHL model for 2026-27 (baseline b) — needs its own audit before it counts as a layer.

## Next steps
0. PRICE LAYER: Jeff runs NHL-L1 in Claude Code (prompt in chat); Cowork verifies; Jeff installs the proposed cron lines.
0b. SIM: C-WO1 and D-WO1 are done and verified. Next in Claude Code: **D-WO2** (fresh session, ~/mlb-model-nhlD,
   `research/nhl_sim/edge_hunt_2026-09-30/hunt_2026-09-30/workorder_D2_walkforward_2026-10-01.md`). Cowork verifies
   from origin, then E-03 one-shot (Cowork), then C-04 diagnostic, then the WO1 packet amendment (lineups, engine fair
   prices for derivatives from the E5 tape, EV2 flags) and the props price rule on the forward tape.
0c. Grade the 2026-09-30 fun parlays on 10-01 and append to the pilot_picks log.
1. Jeff: merge nhl/wo1 (`git checkout main && git merge --no-ff nhl/wo1`); main Layers chat freezes `research/layers/reader_method_v1.md`; pilot slates 09-29..10-04 can be frozen by hand with `--date` + `--packet`.
2. Capture WO12 (main chat) must merge and deploy for the NHL tape to exist before Tue; without it the pilot
   freezes from a manual pull.
3. Cowork verifies WO1 from files on origin (skill: research-work-order), then the Tue 09-29 pilot runs by hand if
   tooling is not finished: game lines from the tape, goalies from news with URL + time in the packet.
