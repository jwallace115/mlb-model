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
