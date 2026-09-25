# Phase 5P verification (Cowork, 2026-09-25T00:58Z)

Branch `eng/5p` @ `67e437b` (D132-D133 + log), base `6b9a2ee` (main after D131). Diagnosis only; fingerprint
`02fbcab6e6ed042e` unchanged. Both items committed their row-level parquet as ordered. `git merge-tree` vs main: clean.

## Verdict: MERGE. Item 1 reproduces exactly from the parquet and an independent real-side derivation and
names a real cause. Item 2's numbers reproduce but its headline compares the sim's mean to the book's
LINE, not the book's mean, which overstates the bias; and one of its listed candidates is impossible.

## Item 1 (D132) - rebuilt from `phase5p_drives_by_game.parquet` (1,087 games) vs Cowork's own PBP derivation
| ending | per game sim / real | plays | yards per play | start yardline (yds to EZ) | drives starting inside the 40, per game |
|---|---|---|---|---|---|
| TD | 4.81 / 4.73 | 7.22 / 7.89 | 8.53 / 8.17 | 62.7 / 66.3 | 0.84 / 0.54 |
| FG | 3.42 / 3.33 | 7.68 / 7.97 | 5.68 / 5.76 | 64.1 / 65.7 | 0.54 / 0.42 |
| punt | 8.85 / 7.86 | 4.21 / 4.18 | 2.67 / 2.67 | 75.8 / 75.7 | 0.05 / 0.04 |
| turnover | 2.52 / 2.25 | 4.36 / 4.67 | 4.62 / 4.88 | 72.7 / 73.3 | 0.11 / 0.07 |
TD-drive length buckets (share): 1-3 plays sim 0.180 vs real 0.118; 10+ plays 0.271 vs 0.325.
All three pre-registrations graded as D132 says (3.6 yards closer HELD; +0.36 YPP FAILED upward; +6.2 pts
in the 1-3-play bucket HELD); null (punt drives 4.21 vs 4.18) HELD.
**What it means.** Summed over every ending, the sim starts 1.86 drives per game inside the opponent's 40
against 1.22 real: +0.64 short fields per game, and they show up as TDs and FGs in 1-3 plays. Punt drives
start in the right place (75.8 vs 75.7), so the ordinary kickoff/punt exchange is fine; the extra short fields
come from the events that produce them - turnovers (sim has +0.27 per game, and their return yardage is
untested), interception/fumble return spots, missed-FG and blocked-kick spots, onside/late-half situations.
5Q item 1 decomposes drive STARTS by the event that preceded them. The +0.36 YPP on TD drives is real but
smaller; it may be partly selection (a short field makes any drive that scores look efficient per play).

## Item 2 (D133) - recomputed from `phase5p_gap_rows.parquet` (131 receptions player-lines, Week 2 board)
- SD(sim_p - q) = 0.1465: reproduced. Replacing the sim's mean with the book's mean and keeping the sim's
  spread leaves 0.089: 39% removed, reproduced. Team pass-volume share ~11%: not re-derived.
- **Correction 1:** the report's "+0.41 receptions" is `sim_mean - book_LINE`. The book's line is its median,
  ~0.16 below its mean for these counts. Against the book's implied mean the sim is +0.25 (WR +0.32, TE +0.20,
  RB +0.16); against the realised Week 2 receptions the sim is +0.28 and the book +0.03. The sim over-projects
  receptions for the players the book quotes - a global bias, largest at WR (+0.41 vs realised).
- **Correction 2:** D133 lists "sim sampling noise (N=100 draws)" as a candidate for the 61% residual. The board
  runs N = 5,000 (two chunks of 2,500). Sampling noise at the rung is ~0.007 in probability; it is not a
  candidate.
- Dispersion: the book side was modelled as Poisson (book_sd / sqrt(book_mean) = 1.000 by construction), the sim's
  sd is 0.93 x sqrt(mean); realised squared error around the book mean was 3.8 vs the book's 3.2 (one week, 131
  rows - a note, not a finding).
- Pre-registrations (1) and (2) FAILED, (3) HELD, as reported. (2)'s numbers: players with no 2025 season or on a
  new team carry +0.58 mean error vs +0.36 for the rest - a +0.2 difference, below the 0.5 threshold I set, but
  in the direction predicted and on n = 29.
- **What it means.** A uniform +0.25-0.3 over-projection for QUOTED players, with team volume explaining little,
  points at how team receptions are divided: the sim gives the named players (the ones the book quotes) a
  larger share of the team's catches than they get in real life, i.e. too little goes to the unquoted depth
  players. That is exactly what a renormalisation over ACTIVE players does when the active list is short or the
  redistribution weights are off. Testable without the book: for 2024 (or the 2026 weeks played), the share of
  team receptions going to the top-N quoted-type players, sim vs real. 5Q item 2.

## Checks
Provenance: item 1 is PBP 2021-24 vs the engine's own log; item 2 reads a pre-kick board and Week 2 actuals.
Leakage: nothing tuned; every number is a read. Identity: the Week 2 board is the live object. Economics: none.
Aggregates: by ending and by position / prior-season / team-change. Sim gates nothing (N54).

## NOT done / UNVERIFIED
- Item 2's "team pass error ~11%" was not re-derived. Usage rebuild bit-identity (carried since 5J).
