# Line-movement cell registry v1 — FROZEN 2026-10-11 (Jeff + Cowork)

Purpose: Jeff's question — can we identify the subsets where the book's correction is wrong? Six cells, each with a
mechanism, written BEFORE any outcome is graded. No cell is added, split, or re-thresholded after this date. Data
touched before freezing: fire rates only (counts of triggers), never results.

## What the data is (measured 2026-10-11 from data/odds_archive/{nfl,ncaaf}/line_history/season=2026)

- One snapshot every ~35 min since 2026-09-06 (NFL 1,385 snaps, NCAAF 1,376), ten books including `pinnacle` and
  Hard Rock (`hardrockbet_fl` for NFL, `hardrockbet` for NCAAF), markets h2h / spreads / totals, with `point`,
  `price` (American) and `book_last_update`.
- Kicked-off games with ≥20 Pinnacle snapshots: NFL 65 (weeks 1-5), NCAAF 351 (weeks 2-7).
- Pinnacle pre-kick spread point changes: NFL 92 (1.4/game), NCAAF 908 (2.6/game). Open→close |move| at Pinnacle:
  NFL mean 0.80 (43% ≥1.0, 9% ≥2.0); NCAAF mean 1.23 (56% ≥1.0, 25% ≥2.0).
- Hard Rock's point differs from Pinnacle's in ~50% of same-snapshot rows (NFL) / 55% (NCAAF); by ≥1 full point in
  8.6% / 13.4%. At the same point, Hard Rock's raw implied probability on the home side runs +0.96 pp (NFL) /
  +0.55 pp (NCAAF) above Pinnacle's — mostly Pinnacle's lower vig, so every price comparison below is DE-VIGGED on
  both sides before it counts.
- When Pinnacle changed its point, Hard Rock showed the same point in the same snapshot 61% of the time (NFL) and
  never matched before kick 8%; NCAAF 12% / 86% (the NCAAF figure needs a coverage check — Hard Rock may list fewer
  NCAAF games or different half-points; treat as UNVERIFIED until item 2 of LM-1 reports it).
- Worked example (DEN@KC, 2026-09-14): Pinnacle sat on KC −3 for five days while its price walked +107 → +104 → +111,
  then crossed to −2.5 −106 and later −2.0; Hard Rock sat on −2.5 −115 throughout. The key number held; the juice
  moved. That is cell C1's mechanism, visible in one game.

## The sample-size wall (applies to every cell)

Break-even at −110 is 52.4%. Distinguishing a 55% cell from break-even at conventional power needs ~1,000 bets;
58% needs ~250. The NFL has 65 graded games so far and ~210 more this season. So: NO NFL cell reaches a verdict on
ATS record this season. Each cell is graded on CLV first (cents vs the Pinnacle de-vigged close — needs far fewer
observations because the outcome is the close, not the game) and on ATS second, and the ATS read for NFL is
labelled INTERIM until the minimum N is met. NCAAF is where cells can reach N this season.

Two looks only: an INTERIM look now (LM-1) and a FINAL look at season end. Nothing changes in between.

Multiple comparisons: six cells × two sports × two metrics = 24 tests. At p < 0.05, about one passes by luck.
Pass bar is therefore t ≥ 2.5 on CLV with N ≥ 100, AND the same sign in both sports, AND the permutation null (side
labels shuffled within the cell) must sit at zero. A cell that passes one sport and fails the other is "mixed", not
"passed".

## The cells

Grading conventions for all cells: the bet is placed at Hard Rock's price in the FIRST snapshot after the trigger
(the earliest a human could act on it; also graded at the trigger snapshot as an upper bound), CLV is measured
against Pinnacle's de-vigged price for the same side at the last pre-kick snapshot ≤ 60 min before kick, ATS uses
the Hard Rock point taken. Pushes are pushes. Joins on event_id only.

### C1 — Key-number crossing (structural)
- Trigger: Pinnacle's spread crosses 3 or 7 (either direction) between consecutive snapshots. The side that now
  holds the key number (e.g. −3 → −3.5: the dog at +3.5; −3.5 → −3: the favourite at −3) is the bet.
- Mechanism: a continuous signal corrected in a discrete full-point step; the book over-shoots to get off the number.
- Fire rate: to be recomputed on kicked-off games in LM-1 (the pre-freeze count included lookahead games).
- Min N for CLV verdict: 100 crossings. Expect NCAAF to reach it this season; NFL not.
- Cowork prior: 30% that CLV is positive at the bar; 10% that ATS beats break-even at the bar.

### C2 — Hard Rock lag (structural)
- Trigger: Pinnacle moves ≥0.5 and Hard Rock still shows the pre-move point at the next snapshot. Bet Pinnacle's
  direction at Hard Rock's stale number.
- Mechanism: a copier arrives late. This is CLV by construction; the real questions are whether the stale number is
  bettable (it may be pulled), whether Pinnacle reverses, and whether CLV converts to ATS.
- Fire rate: NFL ≈ 36% of 92 moves ≈ 33 per 5 weeks; NCAAF several hundred (after the coverage check).
- Min N: 100 for CLV. Reaches it in NCAAF now; NFL ~week 12.
- Cowork prior: 85% positive CLV; 50% ATS beats break-even. (If CLV is NOT positive here, the tape or the join is
  broken — treat as a data bug first.)

### C3 — Early-week over-correction (behavioural)
- Trigger: Pinnacle moves ≥1.0 before Wednesday 17:00 UTC of game week (low-limit window). The bet is the PRE-move
  side, at Hard Rock, at the next snapshot.
- Mechanism: openers are low-limit, so one sharp opinion moves the line a full point; one opinion is wrong ~45%
  of the time, and later full-limit money partially reverts it.
- Fire rate: to be measured (expect ~15-25% of NFL games).
- Min N: 100. NCAAF only this season.
- Cowork prior: 25% that early moves revert more than late moves by a measurable margin; 10% positive CLV at the
  bar; 5% ATS.

### C4 — Reversal / fake steam (behavioural)
- Trigger: Pinnacle moves ≥1.0 then moves back ≥0.5 within 3 hours (≤6 snapshots). The bet is the side favoured by
  the REVERSAL, at Hard Rock, at the next snapshot after the reversal.
- Mechanism: the first move was a head-fake or a copier over-shoot; the reversal is the informed money.
- Fire rate: to be measured (expect rare in NFL, tens in NCAAF).
- Min N: 100. Likely unreachable this season in either sport — carried as a season-end look only.
- Cowork prior: 15% positive CLV at the bar.

### C5 — Hard Rock shade (retail pricing)
- Trigger: same point at both books, and Hard Rock's DE-VIGGED probability on the public side (home favourite on
  spreads; Over on totals; favourite on moneylines) exceeds Pinnacle's de-vigged probability by ≥2.0 pp. The bet is
  the OTHER side at Hard Rock.
- Mechanism: a retail book taxes the side the public wants rather than balancing; the un-taxed side is mispriced
  relative to the sharp book.
- Fire rate: raw (not de-vigged) ≥2 pp gaps appear in ~20% of NFL same-point rows; de-vigged will be lower.
- Min N: 150 (the edge per instance is small). NFL may reach it by season end because it fires per snapshot, not
  per game — count one instance per game per market, at the first qualifying snapshot.
- Cowork prior: 60% that a directional shade exists (gap sign consistent with "public side taxed"); 30% positive CLV
  at the bar; 15% ATS.

### C6 — Totals narrative over-reaction (weather) (behavioural; the house pattern)
- Trigger: Pinnacle total falls ≥1.5 in the final 24 h before kick AND a weather input is present (forecast wind
  ≥15 mph or precipitation at kick). The bet is the OVER at Hard Rock at the next snapshot.
- Mechanism: the market over-adjusts for suppression narratives (Jeff's MLB/NBA findings pointed the same way; the
  repo's boxed "wind + execution" experiment is this cell's prior registration — LM-1 must find it and NOT create a
  second, conflicting spec).
- Fire rate: a handful of NFL games per season; more in NCAAF late season.
- Min N: 100. Unreachable this season; season-end and next-season look only.
- Cowork prior: 35% positive CLV at the bar.

## What is NOT a cell (and why)

- "Fade the public" from published bet-percentage sites: no trustworthy source; not measurable here.
- Anything keyed on team identity, coach, primetime, divisional, revenge: no mechanism beyond narrative; infinite
  cells; excluded by construction.
- Anything from the sim: separate lane (GL), separate ledger.

## Grading of the registry itself

- INTERIM look: LM-1 (now). FINAL look: after the NFL regular season (early January 2027). The registry text is
  committed and its sha256 recorded in the session log before LM-1 item 2 runs. Any change after that is a v2 with
  its own prior and a note that v1's data has been seen.
- Every cell's result is reported, including the ones that fail. A cell that fails stays in the file with its
  result. Nothing is tuned to rescue a cell.
