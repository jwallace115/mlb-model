# Phase 5A-9: endgame repair — 4th-down table rebuild, FG-setup state, kneel defect, spikes

**Executed by Cowork directly, 2026-09-16.** Acceptance run: full K1 protocol (1,087 games
2021–2024 × N = 500, `stable_seed((game_id, 42))`, drive log on, 2,103 s cloud) with the
5A-8 conditional tables and the late-drive decomposition as the acceptance metrics.

## 1. What changed (D30–D34)

**D30 — 4th-down table rebuilt as a complete grid with measured shrinkage.** 5A-8 showed
the old fallback chain's levels 2–3 could never match (builder prefixed every grouped
column, engine looked up unprefixed keys), so 51.7% of Q4 and 99.1% of OT decisions used a
cell pooling trailing with leading offences. The table is now the complete fine grid —
ydstogo (4) × 10-yard zone (10) × score state (7) × clock (6: Q1-3, Q2<2, Q4>5, Q4_2-5,
Q4<2, **OT**) = 1,680 rows, every one present — so the engine does one exact lookup through
the same `tables.fourth_down_keys` the builder uses; the hand-written `(0.1, 0.1, 0.8)`
defaults are gone and a missing key raises. Each cell is its own counts blended with its
parent, p = (x + k·p_parent)/(n + k), with **k estimated per level by method of moments on
the go indicator** (never chosen): 31.5 / 171.5 / 27.6 / 7.5 / 15.2 / 17.7 / 2.5 overall,
per coarse-score group at levels 0–3 (`fourth_down_meta.json`). Parent chain coarsens field
position, then clock (Q4_2-5 ∪ Q4<2 ∪ OT pool together before anything else), then score —
and the coarse score grouping is structural: inside the opponent's 40 it is whether three
points help (need_td / fg_useful / lead), outside it is whether the offence can give the
ball back (trail / tied / lead). Two intermediate structures were tried and rejected on the
decision replay: `within3` (trail1-3 with tied everywhere) made a team down 3 in its own end
punt like a tied team; sign-only made a team down 3 in range go for it instead of kicking.

**D31 — EOH runoff cells.** Snaps in the end-of-half FG setup (Q2 / Q4 / OT, ≤ 40 s, inside
the 50) draw their runoff from cells measured in that state (elapsed to the next snap of
any type in the same half, KM-censored when the half ends first, elapsed 0 kept), split
fg_useful_Q2 (hurry-up) from fg_useful_Q4 (kneel-it-down) and Q4_lead / Q4_trail4+; no
pace scaling, no floor, no separate timeout draw. The EOH FG hook and table now include OT.

**D32 — the kneel-then-play defect (found while verifying D30).** `alive = ~game_over`
before the scrimmage block discarded the kneel and expired-clock exclusions, so every kneel
was followed by a scrimmage snap in the same iteration: a 3rd-down kneel became a 4th-down
play with no decision → turnover on downs (leading offences ended 15% of late drives on
downs; real 2%), and snaps ran with the clock at zero. Since 5A-7. One line.

**D33 — the field-goal-setup state** (Q4/OT, tied or trailing by 1–3, inside the 35, ≤ 3:00,
downs 1–3): the general tied/Q4<2 play-call cell passes 69% of the time; in this state real
offences pass 31% (tied) / 48% (trail 1–3), kneel to centre the ball 45–56% of snaps at
21–60 s when the defence is out of timeouts, run for 2.5–2.9 yards with a 4–7% TD rate
(vs 3.7 yards / 10% at the same field position earlier), and manage the clock to the kick
(every in-state kneel with ≤ 40 s left was followed by the field goal at 1–4 s; 22 of 22).
New empirical cells: `fg_setup.parquet` (P(kneel) by seconds × defence timeouts, pass rate
by state × seconds), `fg_setup_rush.parquet` (KM yardage for in-state runs, n = 322), and
in-state runoff cells in `clock_runoff.parquet` keyed by seconds bucket — for ≤ 40 s the
stored quantity is the **time left at the next snap** (kind `next_sec`), because that, not
the elapsed, is what the offence controls; the kneel cell is the same (next snap at 1–4 s).

**D34 — spikes.** The engine had no spike: at 4–10 s left in range a real Q4 offence spikes
29–37% of the time (Q2 5–20%) and kicks on the next snap; the engine ran a play and the half
expired. `eoh_spike.parquet` (half × seconds bucket, min cell 30); a spike takes 1 s (q90 of
240 real spikes = 1 s) and a down; the EOH FG rate, measured over all snaps including
spikes, is applied conditional on not spiking (p_fg / (1 − p_spike)).

Tables rebuilt: `fourth_down` (1,150 → 1,680 rows), `clock_runoff` (82 → 118 rows, all 82
original rows byte-identical in content), `eoh_fg_decision` (OT snaps added, +60 n, max
Δp_fg 0.016). New: `fg_setup`, `fg_setup_rush`, `eoh_spike`, `fourth_down_meta.json`.
Every other table untouched.

## 2. Decision replay (the direct test of D30)

Engine 4th-down decisions on the 12-game sample (N = 500) vs real 2021–2024, same buckets:

| Q4 ≤ 5:00, state | side | real go / punt / fg | sim go / punt / fg (5A-9) |
|---|---|---|---|
| trail 1–3 | own half | 0.62–1.00 / 0.27–0.46 / 0 | 0.61–0.94 / 0.26–0.36 / ≤ 0.03 |
| trail 1–3 | opp half | 0.06–0.41 / 0–0.02 / 0.59–0.92 | 0.15–0.63 / 0–0.12 / 0.37–0.81 |
| tied | own half | 0–0.25 / 0.75–1.00 / 0 | 0–0.39 / 0.58–1.00 / ≤ 0.03 |
| tied | opp half | 0–0.56 / 0–0.25 / 0.44–0.94 | 0–0.55 / 0.10–0.32 / 0.29–0.76 |
| lead 1–3 | own half | 0–0.33 / 0.67–1.00 / 0 | 0.02–0.30 / 0.66–0.98 / ≤ 0.02 |

Q4<2 trailing by 4–8: real go 0.99 / punt 0.006, sim 0.82 / 0.11 (was 0.75 / 0.70 in the
table the engine actually consulted before). The residual in-range excess for trail 1–3
comes from 4th-and-1–2 cells with n = 0–4 shrunk toward the fg_useful parent, where tied
offences do go 56% of the time (n = 16): the data's answer, not a pooling error. Overall
4th downs/game 14.46 vs 14.33; go rate 21.8% vs 19.8% (K1).

## 3. K1 late-drive decomposition (drives starting Q4 ≤ 5:00; actual | 5A-8 | 5A-9)

| state | TD | FG made | punt | turnover | downs | end of game |
|---|---|---|---|---|---|---|
| trail 4–8 | 30.4 \| 15.4 \| 18.3 | 0.3 \| 6.8 \| 3.0 | 3.7 \| **24.7 \| 7.9** | 28.1 \| 10.9 \| 14.6 | 25.8 \| **5.9 \| 23.2** | 11.2 \| 34.5 \| 31.6 |
| trail 1–3 | 9.5 \| 13.1 \| 9.6 | 23.9 \| **11.2 \| 18.6** | 4.6 \| **22.9 \| 7.4** | 19.0 \| 9.5 \| 10.9 | 11.1 \| 4.4 \| 14.5 | 21.3 \| 36.3 \| 34.3 |
| tied | 4.8 \| **13.5 \| 7.8** | 25.1 \| **11.5 \| 18.5** | 33.2 \| 23.8 \| 26.3 | 4.8 \| 8.6 \| 7.5 | 1.6 \| 4.6 \| 2.0 | 24.6 \| 35.3 \| 33.9 |
| lead 1–3 | 5.4 \| 6.2 \| 6.9 | 5.4 \| 4.0 \| 7.6 | 27.5 \| 18.8 \| 20.6 | 2.5 \| 4.8 \| 2.7 | 2.0 \| **15.2 \| 1.9** | 55.4 \| 49.7 \| 58.9 |
| lead 4–8 | 3.4 \| 6.6 \| 6.8 | 7.0 \| 4.3 \| 7.8 | 26.9 \| 19.0 \| 22.4 | 2.4 \| 4.7 \| 2.6 | 2.2 \| **15.6 \| 2.0** | 55.3 \| 48.5 \| 56.9 |

Tied drives that reach the 35 (12-game sample): FG made 25 → 47%, TD 35 → 22%, clock
expires without a kick 24 → 15% (real 71% / 12.5% / 0%). Kneels 1.50/game (1.51), late-Q4
snaps 5.66 (5.61), spikes 0.105/game, in-state snaps 0.37/game (real 0.51).

## 4. K1 acceptance — the conditional tables (actual → 5A-8 → 5A-9)

| state at 5:00 | P(final \|m\| = 3) | P(\|m\| ≤ 7) | P(OT) |
|---|---|---|---|
| tied | 62.3 → 31.5 → **42.3** | 100 → 91.1 → 91.7 | 31.1 → 25.9 → 25.3 |
| 1–3 | 34.5 → 19.4 → 19.1 | 91.0 → 83.7 → 84.3 | 10.2 → 5.4 → 7.3 |
| 4–7 | 13.4 → 9.8 → 9.9 | 82.0 → 75.6 → 75.1 | 7.9 → 4.6 → 5.6 |
| 8–14 | 8.4 → 4.2 → 4.4 | 37.2 → 27.7 → 27.5 | 4.4 → 1.0 → 1.0 |

Tied at 2:00 → |final| = 3: 80.0 → 34.2 → **53.6%**; P(tie | tied at 2:00) 1.5 → 9.1 →
6.4%; net change after 2:00 in one-score games: +3 11.8 → 7.0 → 10.8%, +7 2.0 → 6.9 →
5.3%, −7 7.2 → 10.4 → 8.8%.

**Headline: unchanged.** P(|final| = 3) 14.5% actual, 7.7% (5A-8) → **8.1%** (5A-9);
|final| ≤ 7 49.0% → 41.5% → 41.4%; OT 6.4% → 3.1% → 3.7%; ties 0.28% → 0.73% → 0.68%
(P(tie | OT) 23 → 19%); SD margin 15.19 → 15.12 (14.20). Full K1 table:

| metric | 5A-9 | actual | | metric | 5A-9 | actual |
|---|---|---|---|---|---|---|
| pts/team | 22.68 | 22.39 | | FG att | 3.70 | 3.92 |
| plays | 130.0 | 124.5 | | non-4th FG att | 0.241 | 0.33 |
| drives | 22.9 | 21.9 | | 4th go rate | 21.8% | 19.8% |
| P(\|m\|=1) | 5.59 | 4.69 | | 4th conversion | 44.9% | ~57% |
| P(\|m\|=6) | 5.34 | 7.54 | | off TDs | 4.91 | 4.73 |
| P(\|m\|=7) | 7.01 | 7.27 | | kneels | 1.50 | 1.51 |
| P(\|m\|=10) | 4.94 | 5.06 | | off / def TO | 1.47 / 1.96 | 1.78 / 2.08 |
| P(\|m\|=14) | 3.76 | 4.32 | | safeties | 0.066 | 0.049 |

(Offensive timeouts read low by construction: in the FG-setup and EOH states the timeout
is inside the measured runoff and is no longer counted.)

## 5. Where the key-number mass actually is (the finding of this phase)

The endgame mechanisms 5A-8 identified were real and are now fixed at the drive level, and
they moved the tied-game conditionals a long way — yet the unconditional mass at 3 barely
moved. The full |margin| histogram shows why:

| \|m\| | final actual | final 5A-9 | at 5:00 actual | at 5:00 5A-9 |
|---|---|---|---|---|
| 1 | 4.7 | 5.6 | 3.7 | 5.1 |
| 2 | 5.2 | 4.9 | 3.4 | 4.2 |
| **3** | **14.5** | **8.1** | **9.2** | **6.9** |
| 4 | 4.9 | 5.8 | 5.8 | 6.3 |
| 6 | 7.5 | 5.3 | 4.1 | 5.2 |
| 7 | 7.3 | 7.0 | 7.6 | 6.4 |
| 9 | 2.0 | 3.6 | 2.7 | 3.3 |
| 10 | 5.1 | 4.9 | 6.7 | 5.2 |
| 11 | 1.5 | 3.9 | 3.0 | 4.2 |
| 13 | 1.7 | 3.7 | 2.8 | 3.8 |

The sim is a **smoothed** version of reality across the whole margin range, already at
5:00: mass at 3 within the 1–3 bucket is 56.5% real vs 42.6% sim at 5:00 (59.4 vs 43.6 at
the final). The off-numbers 1, 2, 4, 9, 11, 13 carry ~7pp too much mass; 3, 6, 10 too
little. Team scores tell the same story: 10 / 17 / 20 (one or two TDs plus one or two FGs)
are 1.1–1.2pp under, 13 / 23 / 26 are 0.6–1.2pp over. So the sim's scoring-event
*composition* — how many FGs and TDs each team ends with, and how those combine across the
two teams — is less structured than the real game, independent of the last five minutes.
Per-team means are right (TDs 2.57 vs ~2.55 incl. non-offensive; FG made 1.59 vs ~1.67);
the joint distribution is not. That is the next diagnostic, not another endgame fix.

Also surfaced by this run: 4th-down conversion 44.9% vs ~57% real (the sim goes 21.8% and
converts less, which is where +1.0 drives/game and +5 plays/game now come from); trailing
drives in the last 2:00 end with the clock expiring 53–55% vs 24–36% real (the two-minute
drill from own territory manages the clock better than the sim's Q4_late cells: real drives
starting at 61–120 s reach the 35 in 43% of cases and expire 0.9%; sim 39% / 24%); real
trailing offences throw it away far more (turnover 35% vs 12% at ≤ 2:00).

## 6. Tests

`test_engine_5a8.py`: T3 rewritten as the complete-grid spec (1,680 cells, every
engine-constructable key present, shared key function, meta sidecar); T4 trailing punt and
leading downs now **green**; T4 tied FG rate 0.169 vs 0.251 ± 0.08 **red** (short by 0.002).
`test_engine_5a9.py` (9 tests): shared keys, k measured, late cells sensible, FG-setup
tables live, D32 gone, kneels/late snaps, tied-drives-reaching-range expiry ≤ 5% **red**
(14.8%). Full suite: see `logs/agent_sessions.md` for the run on this commit. Nothing
widened.

## 7. Next (5A-10)

1. Scoring-event composition: joint (TDs, FGs) per team and per game, sim vs real, by
   quarter and score state — the margin histogram in §5 is the acceptance metric.
2. 4th-down conversion 44.9% vs 57%: distance/field composition of goes, and the down-4
   outcome cells.
3. Two-minute drill from own territory: expiry 24% vs 0.9% for drives starting 61–120 s;
   the trailing offence's runoff, timeouts and interception rate in hurry-up.
4. Then 5B (usage builder) and 5C (grader/pricer, maps) as planned.
