# NBA-S0 verification — Cowork (NBA chat), 2026-10-05 ~15:00Z

Read from origin/nba/s0 (105bb242b, 079606ccf, c8603bd83, a89288300, 771174b77; 10 files, +1,777/-52). NOT merged.
Main checkout on main.

## Holds
- NS1 (14 rules) and NS2 (fit-window ledger) in research/nba_sim/; B14 parser with two parsers, consumed-set compare,
  context binding, exit 2 on non-ok; 16 tests incl. 12 attack cases; the 10-01 PDF now yields the 5 rows.
- B15 de-dup on canonical JSON minus `timestamp`; prediction (<= 30 distinct) did NOT hold (43) — stated honestly;
  null held.
- B16 fetched 656 PDFs (163 + 165 dates, pre-tip + 5:30 pm each), raw PDFs excluded from git.

## RW@SH symmetry check — Cowork's band was wrong, not the grader
Recomputed from the D1 files (Pinnacle last pre-tip totals, same point on both sides 101/101 and 984/984):
signal over +16.33%, under -22.63%, sum -6.30%; non-signal sum -5.71%. With prices on both sides, over ROI + under ROI
equals the price-only quantity mean((d_over + d_under)/2) - 2 up to the outcome split: -5.68% (signal) and -5.64%
(null); mean overround 2.96% / 2.94%. So the expected sum is about -5.7%, not inside [-6.0, -2.0]. Cowork set that band
by assuming the sum is about one overround; it is about two. The -6.30% is 0.6 pp from the price-only value and is
explained by the 60/40 outcome split. No grader bug. Recommendation: accept; the RW@SH numbers stand. Jeff decides.

## Defects
1. **NOT YET SUBMITTED rows are discarded, not kept.** Parser A `continue`s on them (injury_report_parser.py ~183),
   Parser B skips them (~282), and the consumed set never sees them. A team that has not submitted looks identical to a
   team with no injuries; a report where everyone is NYS becomes `verified_empty` (~410). The order required NYS as
   its own status. The two `verified_empty` files on 2025-02-13 (a game day) are the likely case — UNVERIFIED until the
   PDF text is printed.
2. **The manifest was not committed.** B16 says "only parsed manifest committed"; the backfill writes
   `backfill_manifest.parquet` INSIDE the excluded `data/injury_archive/nba/history/`, and `git ls-tree` of
   origin/nba/s0 has 0 files under that path. Parsed rows are not saved at all (manifest only). The 656 PDFs exist only in
   the worktree ~/mlb-model-nbaS0 — pruning it destroys them (A11 custody).
3. **The pending_reason parser fix has no test.** 150/656 files went from parse_failed to ok after a parser change made
   during the run; no fixture from those 150 is in test_report_parser_b14.py.
4. **B16 pre-registration "A == B >= 99%" did NOT hold for 2025-26 (98.8%)**; the entry calls it "borderline" and
   attributes the 4 context_mismatch files (2025-12-20/21, legacy hourly era) to the format change without showing slot
   vs header times.
5. The capture fix is on the unmerged branch, so the live cron still logs official reports as `ok, 0 rows`.

Action: NBA-S0b (research/nba_layers/workorder_S0b_2026-10-05.md) on the same branch, then merge.
