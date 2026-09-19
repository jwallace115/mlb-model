# NCAAF joint-outcome correlation — EXPLORATORY PROBE, 2026-09-18

**Status: EXPLORATORY. Not validated. Not a finding. Do not build on the numbers below
without reading §4.**

Run in a Cowork session against files already in the repo. No new data was pulled.

---

## 1. Why this was run

A parlay builder's core problem is that legs are not independent: it needs `P(A and B)`, not
`P(A) x P(B)`. The NFL side solves this with the sim — joint samples, then exact binary IPF
raking (D65). Jeff does not want a sim for NCAAF.

The alternative is to take the joint distribution empirically: pregame line + final score are
both plain observed facts, so the joint distribution of (margin, total) conditioned on the
line can be read off history without simulating anything.

## 2. Data

- `research/ncaaf/cfbd_betting_lines.parquet` — 10,554 rows, seasons **2022–2024 only**
  (2022: 4,310 / 2023: 3,072 / 2024: 3,172).
- Providers present: Bovada 2,517 · William Hill (NJ) 2,243 · ESPN Bet 2,020 ·
  DraftKings 1,574 · consensus 1,273 · teamrankings 818 · Caesars (CO) 109.
- **Bovada only** was used (largest single-provider coverage). Mixing providers was not
  attempted and is not obviously valid.
- Filtered to rows with `spread`, `overUnder`, `homeScore`, `awayScore` all present: 2,515 rows.
  After dropping pushes on either leg: **N = 2,426**.
- `cover` = home team covers (`margin + spread > 0`); `over` = `total > overUnder`.

Sanity: `P(home cover) = 0.4992`, `P(over) = 0.5111`. Both sit on 0.50, which is what an
efficient market should produce and confirms the sign convention is right.

## 3. What was measured

Pooled, all spreads:

| | value |
|---|---|
| independence would give `P(cover & over)` | 0.2551 |
| observed | 0.2692 |
| delta | **+0.0141** |
| phi | 0.0561 |
| t | ~2.76 |

Broken out by `|spread|` — **this is the part that matters**:

| \|spread\| | N | independence | observed | delta | phi | t |
|---|---|---|---|---|---|---|
| 0–3 | 504 | 0.2559 | 0.2619 | +0.0060 | 0.024 | 0.54 |
| 3–7 | 588 | 0.2690 | 0.2755 | +0.0065 | 0.026 | 0.63 |
| 7–14 | 607 | 0.2512 | 0.2488 | −0.0024 | −0.010 | −0.24 |
| 14–21 | 364 | 0.2391 | 0.2692 | +0.0301 | 0.121 | 2.31 |
| 21+ | 363 | 0.2541 | 0.3030 | **+0.0489** | 0.196 | 3.79 |

By season:

| season | N | phi | t |
|---|---|---|---|
| 2022 | 829 | 0.0326 | 0.94 |
| 2023 | 829 | 0.0332 | 0.95 |
| 2024 | 768 | **0.1061** | 2.95 |

Related quantity (not a true null control): `phi(favourite covers, over) = 0.069`, similar in
magnitude to the home-cover version, so the effect is not a home/away artifact.

## 4. Why none of this is a finding yet

**4a. The pooled number is an aggregate-hiding artifact.** It reads as a clean +1.4pp effect.
Broken out, three of five buckets are flat or negative (|t| < 0.7) and the whole thing lives
in `|spread| >= 14`, on N = 364 and 363. This is precisely the pathology Check 5 exists to
catch. Anyone quoting "phi = 0.056 across 2,426 games" is quoting a number that does not
describe most games.

**4b. It is concentrated in one season.** 2022 and 2023 are both phi ~= 0.033 with t < 1.
2024 alone carries t = 2.95. A structure that appears in one of three seasons is, by this
project's own standard, broken rather than validated.

**4c. Running this probe consumed 2022–2024 as discovery data.** This is the important one.
The hypothesis was formed and the buckets were chosen while looking at these seasons. Under
Check 2 that makes 2022–2024 in-sample contaminated evidence for this hypothesis from here
on, regardless of any split imposed later. **The only clean out-of-sample data for the
blowout-correlation hypothesis is 2025 and 2026, neither of which is in the repo.** That is
why the next work order pulls 2025 before anything is built.

**4d. The line's provenance is unknown.** `spread` and `spreadOpen` differ on **91%** of rows,
so they are genuinely distinct columns, but which one `spread` represents — close, current, or
something else — was not verified. If it is the closing line, every number above is
conditioned on information not available when a bet is placed early, and the table would have
to be rebuilt on `spreadOpen`.

**4e. Mechanism is plausible, which is not evidence.** Big favourite covers -> blowout ->
points -> over is a sensible story, and a sensible story attached to a one-season,
small-N result is how this project has lost weeks before.

## 5. What would make it real

1. Pull 2025 from CFBD into **separate files**, so the physical separation is the guarantee
   that it was untouched during the exploration above.
2. Resolve `spread` vs `spreadOpen` against CFBD's documentation and rebuild on whichever is
   actually available pre-game.
3. Pre-register, before looking at 2025: the `21+` bucket shows positive phi of roughly the
   same order; the `0–3`, `3–7`, `7–14` buckets stay flat at |t| < 2.
4. Null control on 2025: `P(home cover)` and `P(over)` must each come back near 0.50. If they
   do not, the data, the provider join, or the sign convention is wrong — not the market.
5. If 2025 does not hold, say so plainly and do not tune the buckets to rescue it.
