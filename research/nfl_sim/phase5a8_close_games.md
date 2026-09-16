# Phase 5A-8: where the sim loses its close games

**Executed by Cowork directly, 2026-09-16.** Diagnostic only — no engine behaviour was
changed. Two additions to the engine are pure observation (verified seed-identical
against HEAD on two games × 500): the score state when the Q4 clock first reads ≤ 5:00
and ≤ 2:00 (`m_q4_300`, `m_q4_120`, possession and yardline), and two drive-log columns
(`sd_start`, `opp_points`). Script: `nfl/sim/close_game_diagnostic.py`. Actual side built
from the 2021–2024 regular-season pbp (1,087 games, same population as K1); sim side is
the full K1 protocol (1,087 games × N = 500, `stable_seed((game_id, 42))`), run twice —
once for the snapshots (1,676 s cloud) and once with the drive log on, keeping only
drives that start in the last 5:00 or in OT (1,843 s).

## 1. The question

After 5A-7 every scoring aggregate is near reality (22.49 vs 22.39 pts/team, TDs 4.90 vs
4.73, FG att 3.56 vs 3.92), yet the sim has too few close games: |final| ≤ 7 in 41.5%
of sims vs 49.0% of games, |final| = 3 in 7.7% vs 14.5%, OT 3.1% vs 6.4%. Is the deficit
generated before the last five minutes or during them?

## 2. Answer: during them. The state at 5:00 is nearly right; the endgame is wrong

Score-state distribution the first time the Q4 clock reads ≤ 5:00 (|home − away|):

| state | actual | sim |
|---|---|---|
| tied | 5.6% | 3.6% |
| 1–3 | 16.3% | 16.6% |
| 4–7 | 22.0% | 21.7% |
| 8–14 | 27.2% | 27.2% |
| 15+ | 28.9% | 30.9% |

One-score games at 5:00: 43.9% actual vs 41.9% sim. Reweighting the sim's own
conditional outcomes to the actual state shares gives P(|final| ≤ 7) = 43.3% and
P(|final| = 3) = 8.3%: the state at 5:00 explains 1.8 of the 7.5-point |final| ≤ 7 gap
and 0.6 of the 6.9-point key-number-3 gap. **Roughly 90% of the missing mass at 3 is
created after 5:00.**

Conditional on the state at 5:00 / at 2:00 (actual → sim):

| state at 5:00 | P(final \|m\| = 3) | P(\|m\| ≤ 3) | P(\|m\| ≤ 7) | P(OT) | P(tie) |
|---|---|---|---|---|---|
| tied | 62.3% → 31.5% | 65.6 → 42.1 | 100 → 91.1 | 31.1 → 25.9 | 1.6 → 6.0 |
| 1–3 | 34.5% → 19.4% | 62.7 → 51.5 | 91.0 → 83.7 | 10.2 → 5.4 | 0.0 → 1.3 |
| 4–7 | 13.4% → 9.8% | 30.1 → 27.6 | 82.0 → 75.6 | 7.9 → 4.6 | 0.8 → 1.1 |
| 8–14 | 8.4% → 4.2% | 14.9 → 10.8 | 37.2 → 27.7 | 4.4 → 1.0 | 0.0 → 0.2 |

| state at 2:00 | P(final \|m\| = 3) | P(\|m\| ≤ 7) | P(OT) | P(tie) | mean \|Δ\| |
|---|---|---|---|---|---|
| tied | 80.0% → 34.2% | 100 → 94.0 | 30.8 → 38.7 | 1.5 → 9.1 | 3.48 → 4.81 |
| 1–3 | 34.4% → 25.7% | 95.2 → 91.9 | 11.3 → 5.1 | 0.0 → 1.2 | 2.42 → 2.43 |
| 4–7 | 12.8% → 7.5% | 92.4 → 87.2 | 9.2 → 3.8 | 0.8 → 0.9 | 2.29 → 2.30 |

Net change after the 2:00 snapshot in one-score games, signed toward the leader
(+ = leader extends, − = trailer closes): +3 is 11.8% actual vs 7.0% sim; +7 is 2.0% vs
6.9%; −7 is 7.2% vs 10.4%; −4 is 3.4% vs 1.3%; 0 is 48.3% vs 53.2%. **The sim's endgame
is TD-shaped where reality is FG-shaped**, in both directions.

By season the picture is identical (|final| = 3: 14.0/16.6/14.0/13.6% actual vs
7.7/7.6/7.7/7.7% sim; one-score at 5:00: 37.9/47.2/47.4/43.0 vs 42.1/42.1/41.8/41.7).
The sim is also flat across seasons where reality varies — a separate note for the
ratings layer, not an endgame issue.

## 3. Drive-level decomposition: what each late drive does

Drives starting in Q4 with ≤ 5:00 left, result mix by the offence's score state at the
drive start (actual | sim; 1,050 real games with such drives, 543,500 sims):

| state | n act | TD | FG made | punt | turnover | downs | end of game |
|---|---|---|---|---|---|---|---|
| trail 9+ | 609 | 17.4 \| 13.9 | 6.6 \| 3.3 | **3.8 \| 12.5** | 20.0 \| 12.5 | 21.3 \| 16.3 | 29.1 \| 40.3 |
| trail 4–8 | 349 | **30.4 \| 15.4** | 0.3 \| 6.8 | **3.7 \| 24.7** | **28.1 \| 10.9** | **25.8 \| 5.9** | 11.2 \| 34.5 |
| trail 1–3 | 305 | 9.5 \| 13.1 | **23.9 \| 11.2** | **4.6 \| 22.9** | 19.0 \| 9.5 | 11.1 \| 4.4 | 21.3 \| 36.3 |
| tied | 187 | **4.8 \| 13.5** | **25.1 \| 11.5** | 33.2 \| 23.8 | 4.8 \| 8.6 | 1.6 \| 4.6 | 24.6 \| 35.3 |
| lead 1–3 | 204 | 5.4 \| 6.2 | 5.4 \| 4.0 | 27.5 \| 18.8 | 2.5 \| 4.8 | **2.0 \| 15.2** | 55.4 \| 49.7 |
| lead 4–8 | 412 | 3.4 \| 6.6 | 7.0 \| 4.3 | 26.9 \| 19.0 | 2.4 \| 4.7 | **2.2 \| 15.6** | 55.3 \| 48.5 |
| lead 9+ | 530 | 6.6 \| 9.1 | 5.7 \| 5.5 | 22.5 \| 17.7 | 1.9 \| 3.2 | 6.4 \| 12.2 | 55.8 \| 51.3 |

Drives starting with ≤ 2:00: a real offence trailing by 4–8 punts 0.0% of the time and
goes for it on downs 24.5% + throws it away 35.2%; the sim punts 17.2%, turns it over on
downs 3.6%. Trailing by 1–3: real punt 0.0%, FG 20.9% (+9.6% missed); sim punt 15.6%,
FG 8.8%. Tied at ≤ 2:00: real drives end in a made FG 18.7%, TD 3.3%; sim 9.3% and 8.6%,
and **14.0% of sim tied drives end with the clock expiring inside the 35 without a kick
(real: 1.6%)**.

OT: real OT drives (tied) end FG 26.2% / TD 13.4% / clock expires 1.2%; sim 13.3% /
21.3% / 10.2%. 23.4% of sim OT games end tied vs 4.3% real (3 of 70).

## 4. Mechanism — a dead fallback in the 4th-down lookup (found, verified)

`tables.build_fourth_down_table` writes four levels: fine (yd × 10-yard zone × 7 score
states × 5 clock buckets), `c_` (coarse score: trail9 / within8 / lead9), `z_` (coarse
zone), `zc_` (coarse zone × coarse score × Q1-3 / Q4). `_add_rows(prefix=…)` prefixes
**every** grouped column, so level-2 rows carry `yl_b = "c_opp21-30"` and level-3 rows
carry `score_b = "z_trail4-8"`. The engine (`engine.py` 4th-down loop) looks level 2 up
as `(yd, "opp21-30", "c_within8", qtr)` and level 3 as `(yd, "z_opp40", "trail4-8", qtr)`.
Neither key can ever exist. Replaying the engine's chain on every real 4th-down snap
2021–2024 (15,589):

| quarter | resolved at fine cell | resolved at `zc_` (coarsest) |
|---|---|---|
| Q1 | 99.4% | 0.6% |
| Q2 | 78.1% | 21.9% |
| Q3 | 98.8% | 1.2% |
| **Q4** | **48.3%** | **51.7%** |
| **OT** | **0.9%** | **99.1%** |

Levels 2 and 3 are hit 0.0% of the time. On late-Q4 4th downs (≤ 5:00, 1,908 real snaps)
the table the engine actually consults gives an offence trailing by 4–8 p_go 0.34 /
p_punt 0.42 (real: 0.83 / 0.14); trailing by 1–3 p_fg 0.38 (real 0.51); leading by 1–8
p_go 0.23 (real 0.11). The `zc_within8` cell pools a team down 6 with a team up 6 and the
whole fourth quarter with its last two minutes. That is the punting trailer, the leader
turning it over on downs, and — through the extra possessions it hands the other side —
the surplus of ±7 endgames.

Even with the keys matched, level 2 would still pool `within8` across the sign of the
score; the fine cells for tied / trail1-3 / trail4-8 in Q4_2-5 do not exist at min-cell 10.
The fallback order must coarsen field position and distance before it coarsens the sign
of the score, and a decision table cannot run on cells of 10.

## 5. Second mechanism — the game-winning-FG drive is not a state the sim knows

A tied or trailing-by-≤ 3 offence in the last 2:00 in reality reaches range, burns the
clock, and kicks with ≤ 6 s left (EOH table, measured 5A-6: p_fg 0.80 at 0–3 s, 0.55 at
4–6 s, 0.003 at 11–20 s, 0 at 21–40 s). The sim reproduces the *decision* rates but not
the *clock*: a sim play at 11–40 s draws its runoff from the pooled `Q4_late` clock cell
(mean 20–35 s), so the drive skips past the kicking window and the clock expires in range
(14.0% of tied drives vs 1.6%), or the offence, still running the normal play-call mix,
scores a TD instead (13.5% vs 4.8% at 5:00). Real teams in that state spike, kneel to
centre the ball, or call timeout; the 5A-7 timeout table stops the clock on ~⅓ of those
snaps, which is the measured average over all late snaps, not the FG-setup state. The fix
is an empirical clock/play-call cell keyed on the EOH state (tied / trail ≤ 3, in range,
≤ 40 s), measured from real snaps in that state — no constant.

## 6. What 5A-8 did not find

The score at 5:00 is generated correctly enough (one-score share −2.0pp, all of it
"tied"). Scoring rates per play, drive starts, and yardage are not the problem — 5A-6/5A-7
closed those. The remaining ±1.0 SD-of-margin excess (15.19 vs 14.20) is consistent with
the endgame: real close games compress the margin (FG to tie/lead, kneel-outs), the sim
lets them drift.

Anomaly noted, not chased: 5 of 543,500 sims never had a play snapped with ≤ 2:00 in Q4
(one play's runoff carried the clock from > 120 s to ≤ 0; clock-table q100 is 118 s
before pace). Also a KC–BUF sim margin of −64 (SD-of-margin tail) — worth a glance in the
volume/clock audit.

## 7. Tests

`nfl/sim/tests/test_engine_5a8.py`: T1 snapshots populated, observation-only
(seed-identical), drive-log `sd_start` consistent with `score_state`, `opp_points` only
on turnover / safety / punt-return drives — **2 passed**. T3 (fallback levels 2 and 3
reachable) and T4 (12-game sample, N = 500: trailing-by-4–8 punt rate ≤ 0.117, trailing-
by-1–3 ≤ 0.126, leading-by-1–8 turnover-on-downs ≤ 0.071, tied-drive FG within 0.08 of
0.251 and TD ≤ 0.098) are **4 red by design** — measured 0.250 / 0.160 / 0.110 on the
5A-8 engine — and are the acceptance spec for 5A-9. Not widened.

## 8. Proposed next phase (5A-9) — needs a go

1. Fix the key mismatch and rebuild the 4th-down fallback: fine → coarse distance →
   coarse zone → coarse clock, **never** pooling across the sign of the score; Q4_2-5 and
   Q4<2 pool with each other before pooling with Q4>5; min cell raised (measure the
   variance, do not pick a number). Empirical rows only.
2. EOH-state clock and play-call cells (tied / trail ≤ 3 / in range / ≤ 40 s) measured
   from real snaps in that state; the timeout table gets the same state key.
3. Re-run K1 with the 5A-8 diagnostics: acceptance is the conditional table in §2, the
   drive mix in §3, T3/T4 green, and the 5A-3/5A-4 FG-attempt and penalty tests not
   regressing.
4. OT: after (1) the OT 4th-down decision resolves at fine cells for the first time;
   re-measure the OT tie rate before touching anything else there.
