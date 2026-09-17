# Phase 5A-11: overtime audit — three rule defects and the sudden-death state

**Executed by Cowork directly, 2026-09-17.** Real side: every 2021–2024 regular-season
overtime (70 games, 176 OT drives, 3 ties). Sim side: 12-game sample × 2,000 sims
(~1,250 overtimes) for the mechanics, then the full K1 protocol (1,087 games × N = 500,
drive log on, 3,095 s cloud) for the acceptance numbers.

## 1. Real overtime, 2021–2024 (rules of that era: first-possession TD wins, a
first-possession FG gives the other team one possession, then sudden death)

Drives per OT 2.51. First drive: TD 19%, FG 17%, missed FG 3%, punt 46%, turnover 16%.
Second drive: TD 11%, FG 25%, missed FG 11%, punt 27%, turnover 27%. Later drives: FG
31–57%. Of 12 first-drive FGs, 10 games ended after the second possession and 2 were
matched and went on. Ties 3 of 70 (4.3%; the 70-game sample's own uncertainty is wide,
roughly 1–12%). Inside the 35 on downs 1–3: the first-possession offence plays for the
TD (pass 51%, run 49%, no kicks, TD/snap 11%); after the first possession the offence
kicks on any down — 19% of those snaps are field-goal attempts — runs 54%, passes 21%,
kneels 5%.

## 2. What the engine did (5A-10 engine, sim OT drive sequences)

| sequence | share | ended tied |
|---|---|---|
| FG, FG | 3.6% | **100%** — matched FGs ended the game as a tie |
| punt, punt, FG, (4th drive) | 2.5% | no — a FG after both had possessed did **not** end the game |
| FG, downs, FG | 1.9% | no — the second team's empty possession did not end the game |
| punt-fests ending at 0:00 | ~9% | yes |

P(tie | OT) 18.7%; drives per OT 2.59; OT drives ending in a FG 13% (real 26%), in a TD
21% (13%), with the clock expiring 10% (1%).

**D38 — first-possession completion and the empty second possession.** Only a score or a
turnover on downs marked the first possession complete, so after a first-drive punt the
other team's field goal was treated as a first-possession score and the game went on; and
matched field goals ended the regular-season game as a tie instead of continuing in sudden
death. Now: the first possession is complete when the first team's drive ends for any
reason (evaluated on game state at every new drive — the drive-log fields are not
maintained when the log is off); a drive ending with both teams having possessed and the
score not tied ends the game; a FG after the first possession ends the game only if the
kicking team leads.

**D39 — overtime's last minutes are late-game.** The timeout policy, the late-Q4 runoff
cells and the kneel runoff were keyed `qtr == 4`; OT's last 3:00 now uses the same cells
(the period ends the game either way).

**D40 — the sudden-death in-range state.** After the first possession, inside the 35 on
downs 1–3: FG attempt on the snap at the measured 18.5% (any down), pass rate 29% of
non-kneel plays, kneel 5.2% (one cell, n = 135; `fg_setup.parquet` state `ot_sd`). The
first OT possession is explicitly excluded (played for the touchdown). Runs in this state
keep the normal outcome cells (real OT in-range runs average 4.1 yards, not the 2.7 of
the Q4 clock-kill runs).

## 3. Result

| | real | 5A-10 | 5A-11 |
|---|---|---|---|
| drives per OT | 2.51 | 2.59 | 2.54 |
| first drive TD / FG / punt | 19 / 17 / 46% | 19 / 16 / 45% | 19 / 16 / 45% |
| OT drives: FG / TD / punt / expiry | 26 / 13 / 36 / 1% | 13 / 21 / 34 / 10% | 24 / 15 / 38 / 4% |
| P(tie \| OT) | 4.3% (3/70) | 18.7% | **10.4%** |
| P(OT) | 6.4% | 3.7% | 4.9% |
| tie rate | 0.28% | 0.68% | 0.50% |
| P(\|final\| = 3) | 14.5% | 10.6% | **11.6%** |
| P(\|final\| = 7) | 7.3% | 9.1% | 8.7% |
| P(\|final\| = 6) | 7.5% | 4.5% | 4.4% |

The residual tie rate (10% of overtimes vs 4%) is the punt-fest-to-0:00 sequence; it sits
inside the real sample's uncertainty and is left alone. The OT frequency itself (4.9% vs
6.4%) is the 5A-9/5A-10 endgame residual (tied at 2:00 → tie the game / reach OT).

## 4. Tests

`test_engine_5a11.py` (3, green): the `ot_sd` cell exists with measured rates; rule tests
on ~1,250 sim overtimes — matched FGs always continue, a first-drive FG followed by an
empty possession always ends in two drives, a FG after both possessed always ends the
game, a first-possession TD ends it at once; structure — first-drive mix within 6pp,
drives per OT within 0.35, P(tie | OT) ≤ 0.123. The 5A tie-rate test (≤ 1%) is green
again (0.50%). Full suite on this commit: see `logs/agent_sessions.md`.

## 5. Next

The remaining 5A-10 list: placement of XP/two-point noise (real one-TD-apart games land on
6 in 24%, sim 11%), the shared game environment (corr of the two teams' TD counts 0.12 vs
0.01), Q4 FG count, 4th-down conversion 45% vs 57%, two-minute drill. Then 5B (usage
builder) and 5C (grader/pricer, maps).
