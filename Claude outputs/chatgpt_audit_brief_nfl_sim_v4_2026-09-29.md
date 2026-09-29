# ChatGPT audit brief #6 — the NFL simulation engine after 30 calibration orders, and a proposed finish line (2026-09-29)

Fourth external audit of the NFL sim (audits #1 2026-09-14, #2 09-18, #3 brief 09-19; #4-#5 were the parlay
board). Read-only audit. **Posture: guilty until proven innocent** — every past audit found real defects, and
one finding from audit #1 ("unreachable punt-touchback branch") came back this week as the cause of the sim's
safety excess (see 3.3). Assume the same classes of error are still present.

Repo: `jwallace115/mlb-model` (public). Pins:
- `main` @ `4d8d97298` — decisions D01-D180 (`research/nfl_sim/NFL_SIM_DECISION_v1.md`), verification notes.
- `eng/6b` @ `e432be7d6` — the engine under audit (6A + 6B, NOT merged): D181-D194 in the same decision doc on
  that branch. `eng/6c` is being built now; ignore it.
Handoff (history in one file): `claude/nfl_sim_handoff_2026-09-18.md` in the project; in the repo the verification
notes are `research/nfl_sim/phase*_verification_*.md`.

---

## 1. What it is, and what it is for

A play-by-play Monte Carlo of an NFL game (`nfl/sim/engine.py`, ~3,000 lines, vectorised over N sims). Inputs:
team ratings and tendencies (`ratings.py`), measured outcome / clock / 4th-down / timeout / kneel / punt tables built
from nflverse PBP 2021-24 REG (`tables.py` -> `nfl/data/sim/tables/*.parquet`), a player-usage layer
(`usage.py`), anchoring to the market spread/total (`anchor.py`), isotonic calibration maps (`calibration_v1.json`),
a pricer and SGP raking (`pricer.py`). **It gates nothing.** Standing rule N54: picks are an AI reader's own opinion;
the sim is one logged layer, currently skipped by the owner's choice until "ready".

## 2. What has been done since audit #3 (D59-D194), in one paragraph

Realism work against the K1 table (1,087 REG games 2021-24, N=500): usage and PIT fixes (D59-D72), drive and
volume diagnostics (5N-5Q), week-1 pace carry-forward (5R), INT spotting (5S), return tables (5U), a like-for-like
plays target derived from PBP (125.78, 5V), then eight orders on the game clock (5W-6B): quarter boundaries, a
first-down runoff split, drive-ending plays out of the clock cells, a per-class clock comparison, a measured
timeout-followed runoff class, measured kneels, same-period pooled fallbacks. K1 plays went 131 -> 126.9.

## 3. What we measured (recomputed by the verifier from committed files unless marked "read")

### 3.1 K1 on fit_6b (in-sample by construction — every table and the fit use 2021-24)
plays 126.89 vs 125.78; drives 23.05 vs 21.74; pts/team 21.28 vs 22.39; go_rate / offence and defence penalties /
FG attempts pass tolerance; first downs by penalty 1.27 vs 1.73 per team (fails); safeties 0.071/game vs 0.041
real on pass/run plays; tied-drive expiry in range fails. Suite on eng/6b: 8 red (read) — fd_pen, tied expiry,
dead_clock (a test-selection artefact), OT structure P(tie|OT), timeouts/kneels, tied-offence FG late, kneel
runoff, own 1-2 snaps.

### 3.2 Points per drive (verifier, 200-game sample, N=100, 6A engine)
Offensive points/game 41.14 vs 42.83 real; split START MIX +2.99, EFFICIENCY -4.28, interaction -0.40. The deficit is
long-field efficiency (own 21-40: TD 18.7% vs 21.5%, drives ending on the clock 8.6% vs 5.6%). Candidate (unmeasured):
the first-down-by-penalty shortfall.

### 3.3 Safeties — traced to punts clipped at the 1
Sim zone snaps/game at own 1-2: 1.31 vs 0.385 real; sim safeties = zone snaps x measured per-snap rates exactly. 74%
of the sim's 0.83 own-1/2 drive starts a game (real 0.255) follow punts from the opponent's 40-50: the punt net draw
comes from a table pooled over LOS 21-60 and `engine.py:1809` clips a landing past the goal line to the 1 instead of
a touchback (real touchbacks 14-26% from the opponent's 35-50). The comment on that line reads "FIX 6f: removed
unreachable touchback branch ... touchbacks are encoded in the punt net yards distribution" — the fix of your
audit-#1 finding silenced the symptom.

### 3.4 K4 at real closing prices, current engine (fit_6b), recomputed by the verifier today
`research/nfl_sim/phase6b_k4.parquet` (eng/6b): 72,978 prop legs 2023-24 vs six-book consensus close (in-sample: the
calibration maps are fitted on these seasons). **The sim's calibrated probability has a worse Brier score than the
de-vigged market in all 8 families** (e.g. receptions 0.2345 vs 0.2232; rush_yds 0.2541 vs 0.2343); an 80/20
market/sim blend is equal to the market within 0.001. Bets where |cal_p - market| > 3pp: ROI -1.7% (2023, n=29,071),
-2.9% (2024, n=30,064) at the raw closing price (convention in D63). This repeats D57 (fit_5c2b) on the new engine.

### 3.5 Data
2025 is CONSUMED (scored once in Phase 3, tiers chosen with it in view; `HOLDOUT_2025_SCORED.lock`). The only
out-of-sample data is prospective 2026. Every clock/volume fix since 5V was chosen after looking at K1 on 2021-24.

## 4. The proposed finish line (DRAFT — attack it)

**Gate A — realism (labelled an in-sample fit check, not evidence):** K1 plays 125.8 +- 1.5; drives 21.74 +- 0.6;
pts/team 22.39 +- 0.5; safeties 0.030-0.050; P(|m|=3) 13-16%; tie rate <= 1%; P(tie|OT) <= 0.12; fd_pen within
0.3; all engine tests green except ones retired with a written reason. Time box: if Gate A is not met after 3 more
orders, freeze anyway and record which lines failed.
**Gate B — freeze:** engine fingerprint, tables, fit, calibration maps and usage params hashed into one manifest;
any change after the freeze is a new version and restarts the forward count.
**Forward test (2026, weeks after the freeze):** for every Hard Rock prop and game line in the capture, the sim's
calibrated probability is frozen pre-kick (same blind-log tool as the AI reader, `nfl/pipeline/log_ai_opinions.py`,
reader = "sim"). Scored against the Pinnacle no-vig close (probability CLV) and outcomes. Checkpoints at 500 and 1,500
legs. Success = mean probability CLV > 0 with the 95% CI excluding 0 at 1,500, AND no single family/regime carrying
it. Second use scored separately: SGP joints — the sim's joint probability vs the Hard Rock SGP price for logged
tickets (prices from slips; the API has no SGP prices).
**Kill criterion:** at 1,500 legs with CLV <= 0, the sim is retired as a picker: it stays a correlation tool for
building parlays (joint structure only, marginals taken from the market), and no further calibration orders are
written.

## 5. Questions — answer directly, in this order

**Q1 — Is the whole realism programme overfit?** Eight orders tuned clock and volume by looking at K1 on the same
2021-24 games the tables are built from. Is there any sense in which K1 is still informative, or is it a fit check
only? What cheap, honest out-of-sample realism check exists given 2025 is consumed (e.g. 2026 weeks 1-3 as they
finish, 2020 PBP which the tables never used, a season-by-season leave-one-out of the table builders)?

**Q2 — Is Gate A the right gate?** Given 3.4 (the sim is worse than the market on every prop family even
in-sample), does further realism work have any expected value for betting? Would you drop Gate A to "no known
structural bugs" and go straight to the forward test? Which K1 lines matter for pricing and which are cosmetic?

**Q3 — The forward test design.** Is probability CLV vs the Pinnacle close the right primary metric for a sim whose
marginals are anchored to the market spread/total? Is 1,500 legs enough given leg-level correlation within a game
(many legs per game)? What should the unit of independence be — the game? How should the SGP-joint use be scored
with only slip prices?

**Q4 — Identity and leakage (Checks 1b, 3).** Walk the path from `tables.py` builders to the Sunday board
(`run_week.py`): is every table built point-in-time for a 2026 week, or do 2026 boards use tables that include
2026 PBP? Is the object in K1/K4 the object `run_week.py` runs (same fit, maps, usage params, fingerprint)?

**Q5 — Silenced symptoms.** 3.3 was a fix that removed a branch instead of implementing it. Search for the same
class: branches removed or bypassed with a comment claiming a table "encodes" the case; clips to 1 / 99 / 0 that
turn a real event (touchback, safety, return TD, turnover on downs) into a field position; fallbacks that jump
from a period-specific cell to an all-game parent. List file:line.

**Q6 — Late game.** The remaining reds are late-game (kneel timing: the sim's final kneel of a half comes with 6.7 s
left vs 22.1 s real; team timeouts 4.2/game vs 7.7 because the measured timeout policy only covers the last 5
minutes of each half). Is a measured policy for the whole game the right fix, or is there a simpler structural
error in how kneels and timeouts are decided?

**Q7 — What would you stop doing?** One paragraph: given 3.4 and 3.5, what is the most valuable use of the next
week of work on this project (the owner also runs a forward-only "Layers" pick log across NFL, NCAAF, NHL, NBA)?

A reply is most useful as: (A) a verdict on the finish line with concrete edits; (B) a ranked list of defects with
file:line; (C) one paragraph on whether this engine should continue.
