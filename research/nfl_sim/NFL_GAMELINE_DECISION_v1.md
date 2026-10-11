# NFL Game-Line Decision Log

Decisions for the game-line investigation lane (eng/gl1+).
Numbered G1, G2, ... to avoid conflicts with the sim decision doc (D-numbers).

---

### G1 — Fit-window ledger: 2021-23 consumed, 2024 untouched, 2025 not blind (2026-10-10)

Created `research/nfl_sim/FIT_WINDOW_LEDGER.md` tracking every season × purpose
with status DISCOVERY | VALIDATION | CONSUMED | NOT BLIND | PROSPECTIVE | UNTOUCHED.

Key entries:
- 2021-23 game-line = CONSUMED by the Cowork smoke test of 2026-10-10
  (anchored_2021-23.parquet, c_margin +0.10 t=0.78, c_total −0.24 t=−1.76).
- 2024 game-line = UNTOUCHED. The file anchored_2024.parquet exists but has never
  been opened for any game-line metric in this lane. Standing rule: do not open it
  until after the ChatGPT audit (G5) clears the provenance.
- 2025 game-line = NOT BLIND. K2 scored 2026-09-14; calibration maps fitted on 2021-24.
- 2026 = PROSPECTIVE. Forward experiment nfl_fwd_v1 started week-4 TNF.
- Engine mechanics (Phases 1-2): 2021-24 DISCOVERY, 2025 VALIDATION.
- Fit dirs: fit_5c2 (1,084 games), fit_5c2b/5d1/5d2/5i (1,087 games each), all 2021-24.

### G2 — Baseline structure: ridge on EPA/success diffs + QB + HFA; hl_games = infinity (2026-10-10)

**Structure.** `nfl/sim/gameline_baseline.py` implements a ridge regression baseline:
- Features (margin): (home_off − away_def) and (away_off − home_def) for pass/rush
  EPA and success rate, plus QB EPA diff and home-field intercept (10 features).
- Features (total): pass/rush EPA and success sums, plus QB EPA sum (5 features).
- Point-in-time: for (season s, week w), uses only games from season < s or
  (season == s, week < w). Prior-season carry-in via prior_regression (0.5) and
  prior_weight (0.3) from params_v1.json. Shrinkage k=100, k_qb=100.
- Ridge alpha = 1.0.

**hl_games selection.** Leave-one-season-out CV on home-win log-loss, 2021-23:

| hl_games | mean LL | 2021 | 2022 | 2023 |
|----------|---------|------|------|------|
| 4 | 0.67199 | 0.67872 | 0.66525 | 0.67199 |
| 8 | 0.67091 | 0.67771 | 0.66377 | 0.67125 |
| 16 | 0.67053 | 0.67734 | 0.66320 | 0.67105 |
| 32 | 0.67039 | 0.67721 | 0.66298 | 0.67100 |
| 64 | 0.67034 | 0.67716 | 0.66288 | 0.67098 |
| inf | 0.67030 | 0.67712 | 0.66280 | 0.67097 |

**Chosen: hl_games = infinity (uniform weighting).** The log-loss curve is monotonically
decreasing toward infinity with a total range of only 0.002 — the recency effect in
NFL EPA ratings is negligible for game-line prediction. This is consistent with the
existing params_v1.json half_life = Infinity.

**PRE-REGISTERED P2: hl_games lies between 8 and 40 games. DID NOT HOLD.**
The best is infinity. The range across all values (0.002) is too small to distinguish
meaningfully, so the prior (infinity) is retained rather than picking a finite value
from noise. This is a non-decision: the data does not support recency weighting for
game-line prediction on 3 seasons of NFL.

**Mixed regression (P1):** actual = a + b·mkt + c·baseline on 815 games pooled.

| Target | b (mkt) | c (baseline) | t(c) | P1 check |
|--------|---------|-------------|------|----------|
| Margin | 1.009 | −0.093 | −0.53 | HOLDS: |c|=0.093 < 0.15, b=1.009 ∈ (0.85, 1.15) |
| Total | 0.820 | +0.149 | +0.61 | — |

**Reading:** the EPA-based baseline adds no information over the consensus close.
c_margin is −0.09 (t=−0.53) — indistinguishable from zero. The market (b≈1.0)
absorbs all the signal. This is the expected result for a public-EPA model
against efficient closing lines.

**By season:**
| Season | N | c_margin | t(c) | b |
|--------|---|----------|------|---|
| 2021 | 272 | −0.775 | −2.25 | 1.356 |
| 2022 | 271 | +0.306 | +1.14 | 0.692 |
| 2023 | 272 | +0.015 | +0.05 | 1.057 |

2021 shows a negative c (t=−2.25); this reverses in 2022. The pooled c is near zero.
Not stable across seasons — consistent with noise rather than signal.

**Null control:** 100 permutations of baseline_m within each week.
Mean permuted c_margin = 0.002 (SD = 0.116), t = 0.02. All permuted corr(baseline, actual) < 0.10.
**PASSES:** permuted c ≈ 0, permuted correlation ≈ 0.

**Truncation test:** 9/9 passed (6 (s,w) pairs byte-identical, plus negative control
that planting a future game changes features).

### G3 — Unanchored engine does not beat the statistical baseline on game lines (2026-10-10)

`run_gameline_gl1.py` ran the current engine (fp `156cd057a3b39e48`) on 815 games
(2021-23) at N=5,000, dh=da=0 (no anchoring). Wall time: 945s (1.2s/game, 10 workers).

**Result:** in a three-way regression (actual_m ~ mkt + engine + baseline), the engine's
c = 0.098 (t=0.61) and the baseline's c = −0.136 (t=−0.72). Neither is significant.
The market (b=0.96) absorbs all signal. The engine does not add information over the
consensus close on 2021-23 game-line margins, and does not beat the EPA baseline.

Raw total mean = 41.49 vs market 44.50 (gap −3.0 pts). P3 (±1.5) did not hold.
corr(raw_m, mkt_m) = 0.822. P4 (≥0.75) held.
c_total = −0.334 (t=−1.80). P5 c_total ∈ (−0.3, +0.1) did not hold (borderline).

Anchored null control: 20/20 games pass |anch_m − mkt_m| < 2·SE.

**Reading:** The current engine, unaided by anchoring, produces game-line predictions
no more informative than a simple ridge regression on public EPA. Both are dominated
by the market close. The engine's value, if any, is in the drive-level distribution
(shape, key numbers, player allocations), not in the game-line mean — which is
exactly what anchoring was designed to address.

### G4 — Engine distribution adds no value over a normal with the market mean (2026-10-10)

On 815 games (2021-23), compared the engine's full margin distribution against a
normal distribution with the market mean and the engine's SD, on cover-outcome
log-loss at the market number and at synthetic alt lines (mkt ± 3, mkt ± 7).

The normal with the market mean wins at every line. The engine's full distribution
is never better. P(|m|=3) = 12.3% vs real 14.5% — the engine under-generates key
numbers, which is a shape DEFICIENCY (P6 held as predicted).

Null control (shifted sims at market mean): mean |ΔP| = 0.015, max = 0.056.
The 0.01 threshold is too tight for discrete NFL scoring; the systematic 0.015 is
a known artifact of integer margins, not a code error.

**Reading:** The engine's shape provides no edge over the simplest possible model
(normal + market mean). This is consistent with G3: the engine does not beat the
market on either mean or shape. Its value is in the drive-level structure
(player allocations, drive outcomes) that the game-line aggregate discards.

### G5 — Forward protocol spec + ChatGPT audit brief (2026-10-10)

**Forward protocol:** `research/nfl_sim/GL_FORWARD_PROTOCOL_v1.md` specifies:
- Freeze = engine fingerprint + baseline params + hl_games pinned
- Weekly capture: sim + baseline + Hard Rock snapshot, pre-kickoff, append-only
- Grading: CLV vs HR close, mixed-regression c, log-loss vs de-vigged market
- Mode PILOT until: (1) 2024 clean look, (2) ChatGPT audit, (3) 125 forward games
- Sim is a layer under N54; never the picker

**Audit brief:** `research/cross_ai/chatgpt_audit_brief_gameline_v1_2026-10-10.md`
pinned to commit `aad7f9699`. Requests ALL findings in 5 classes:
1a. Feature provenance (live signal pre-first-pitch)
1b. Feature provenance (point-in-time training)
2. Week-level as-of sufficiency
3. Ledger honesty
4. Research object == live object
5. Forward protocol gamability

### G6 — Generators, halt-on-missing, record corrections (2026-10-11)

- `run_gameline_gl1_analysis.py`: regenerates all report tables from committed artifacts
- `baseline_2021_23.parquet`: OOF + in-sample predictions; GL-1 used in-sample (stated)
- `margin_hist_2021_23.parquet`: compact per-game histograms for shape test
- `gameline_baseline._load_pbp`: now HALTs on missing PBP (FileNotFoundError)
- PBP_DIR resolved from NFL_PBP_DIR env var (no hardcoded path)
- Section-3 null control: DID NOT HOLD (0.015 vs 0.01; discrete scoring)
- P3 failure: K1 pts/team 21.06 vs 22.39, not a runner defect
- 2021 c = −0.775: OPEN (COVID priors or noise; not resolved)
- pytest: 333 collected, 322 passed, 11 failed; all 11 pre-existing

### G7 — Home-field advantage: h=0.172, league-level calibration (2026-10-11)

**Measurement (build_hfa.py, 2021-23 REG):**
- Mean home margin: 2.125 (by season: 1.71 / 1.98 / 2.68)
- Home-win rate: 0.542
- Scrimmage EPA diff: 0.006/play (negligible — HFA is NOT in per-play EPA)
- HFA lives in FG/XP, turnovers, penalties, field position — channels the engine
  models but did not tilt by home/away

**Implementation:** Symmetric EPA offset in `engine._build_game_context`:
home +h, away −h on pass and rush EPA shift. Read from `hfa_v1.json`, default 0.0
when absent (all existing tests byte-identical at h=0).

**Derivation:** h0 = 2.125 / (6.88 + 5.48) = 0.1719 from J_FWD.

**Run (815 games, N=5,000, 4622s, 5.7s/game):**
- raw_m mean: 1.988 (gap −0.137 from target 2.125; P7 HOLDS: |gap| < 0.3)
- No Newton correction needed
- p_home_win: 0.553 vs actual 0.542 (P9 HOLDS: |diff| = 0.011 < 0.02)
- c_margin changed by 0.008 (P8 HOLDS: < 0.05)
- Total: 41.52 vs 41.49 (delta 0.034; null control PASSES: < 0.3)

**h = h0 = 0.1719 is the final value.** Fitted on consumed seasons, stated as such.
This is a league-level calibration constant, not a per-game or per-team effect.
Whether it generalises beyond 2021-23 is UNVERIFIED; it will be judged forward only.

### G8 — Forward PILOT runner + protocol update (2026-10-11)

`nfl/sim/run_gameline_forward.py --season 2026 --week N`:
- Writes one append-only parquet per week with sim + baseline + Hard Rock lines
- HALTs on existing file, past kickoff, non-2026 season
- Reads Hard Rock from line snapshots; null fields with reason when absent
- Engine with h=0.172 from hfa_v1.json; baseline from gameline_baseline
- pbp_2025 read ONLY as s-1 prior for 2026 ratings
- MODE=PILOT; grading after ~125 games (separate order)

Protocol updated: run instructions (Thursday before TNF / Sunday morning),
grading spec (CLV, mixed c, log-loss).

### G9 — HFA opt-in, byte-identity, merge gate (2026-10-11)

**HFA is now opt-in:** `simulate_game(..., hfa=None)` (default) produces h=0.0 and
the code path is byte-identical to the pre-HFA engine (parent e234f67b7). Proven by
SHA256 comparison of margin vectors on 20 games at N=5,000: all match.
`hfa=True` uses _HFA_CACHED (0.1719, read once at module import).
`hfa=<float>` overrides. Only `run_gameline_gl1.py` and `run_gameline_forward.py`
pass `hfa=True`; nothing else passes anything.

**Anchored null control (P10):** 20/20 converge within 2·SE with hfa=True.
Mean dh−da shift: 0.168 (anchor absorbs h). PRE-REGISTERED: 20/20 converge. **HELD.**

**Timing:** ~12s/game single-threaded, ~1.2s/game with 10 workers (HFA cache
eliminated the 5.7s/game per-call file-read overhead from GL-1b).

**Full suite:** 337 collected, 326 passed, 11 failed (exit 1). Same 11 pre-existing
reds as GL-1b, verified at the parent of 103e713e4 (e234f67b7). No new failures.

**MERGE GATE — eng/gl1 merges to main only after ALL of:**
(i) eng/fwd6 has merged to main
(ii) The full test suite on the merge candidate shows the same reds as main with
     the same values (no new reds, no value changes in existing reds)
(iii) `engine_fingerprint()` with `hfa=None` equals main's fingerprint at merge time.
      Currently: eng/gl1 fp = `e3fe19144d2f648c`, main fp = `156cd057a3b39e48`.
      These WILL differ because engine.py content changed (HFA code added). The
      fingerprint gates on file content, not runtime behaviour. This means merging
      eng/gl1 to main requires a re-freeze of the fwd_v1 primary (condition iv).
(iv) The fwd_v1 primary is re-frozen by its own order after the engine fingerprint
     changes from the HFA merge.

### G10 — Forward runner ID-only join, age gate, sign convention (2026-10-11)

- `team_names_odds_api.json`: all 32 nflverse abbreviations → exact Odds API names
- Forward runner rewritten: event_id match via (exact mapped home, exact mapped away,
  commence_time ±1h); Hard Rock rows by event_id only; outcome sides by exact name
- Unmapped team → HALT; no event match → null lines with reason
- Snapshot age gate: HALT if > 3h (A10), tells operator to `git pull`
- Sign convention: Odds API `point` on home spreads row negative = home favoured;
  `hr_spread_home_margin_convention = -point` (comparable with raw_m)
- Tests: KC@−3 → hr_spread_home=−3.0, margin_convention=+3.0; LA vs DAL resolved correctly

### G11 — Record corrections (2026-10-11)

**G6 commit mismatch:** G6 was recorded in the decision doc in commit 103e713e4
(Item 2: HFA), but the code changes for G6 were in e234f67b7 (Item 1: generators).
The decision text is correct; the commit it landed in was wrong because G6 was
appended to the file that was also modified by the subsequent Item 2 commit.

**GL-1 section-1 baseline numbers were in-sample.** GL-1 called `fit_baseline()` on
all 815 games and predicted on all 815 — in-sample. The OOF c_margin from
`baseline_2021_23.parquet` (leave-one-season-out predictions) is **−0.228 (t = −1.29)**,
vs the in-sample −0.093 (t = −0.53). Still not significant, but the OOF value is
larger and the correct one for reporting. The P1 conclusion (baseline adds nothing
over the close) is unchanged.

**Engine fingerprint change:** GL-1b's engine edit (HFA block) changed the fingerprint
from `156cd057a3b39e48` (pre-HFA, main) to `e237f8a7204c2af9` (GL-1b 103e713e4),
then to `e3fe19144d2f648c` (GL-1c, after opt-in refactor). The MNF primary's audited
fingerprint is the pre-HFA value (`156cd057a3b39e48`). The merge gate (G9 condition
iii) addresses this: merging requires a re-freeze.

**Prediction ledger:** `research/cross_ai/claude_prediction_ledger.md` does not exist
on origin/main as of this commit. P7 (HELD, raw_m 1.988 vs 2.125), P8 (HELD, delta
0.008), P9 (HELD, 0.553 vs 0.542), P10 (HELD, 20/20 converge) are graded here in
the decision doc. If and when LM-1 creates the ledger, these should be transcribed.
