# Recovery Manifest — data/mlb_model.db — 2026-08-29

## Root cause

`data/mlb_model.db` was truncated: header claims 799 pages but file contains
only 793 (6 pages / 24 KB missing). Consistent with an interrupted WAL
checkpoint on 2026-07-31 at 07:00. All three refresh LaunchAgents
(11am/noon/5pm) have been crashing on `sqlite3.DatabaseError: database disk
image is malformed` since that date, writing 0-byte logs.

## Source files

| File | Size | SHA-256 |
|---|---|---|
| `data/mlb_model.db.corrupt_20260828_224909` (original corrupt, Jul 31) | 3,248,128 | `4e031194f044330cc549bca5bbfc57fd50705551838aa65a0e19ce49820b3c7b` |
| `data/mlb_model.db` (prerecover snapshot, includes row-by-row recovery + April backup merge + 2026-08-29 pipeline rows) | 1,384,448 | `edb3609b376ccfba9405fad60ab85513f0e644a67a99a4cef6c233295ca19638` |
| `/tmp/recovered.db` (built from `sqlite3 .recover`) | 3,186,688 | `36fd2b942c7bb1df21204fe0b037698833134be149f9a321ab892767d3f2a053` |

Backup of pre-merge current DB: `data/mlb_model.db.prerecover_20260828_231731`

## Recovery method

`sqlite3 <corrupt> ".recover"` reads data pages directly (bypassing the
B-tree), producing a SQL dump that was loaded into `/tmp/recovered.db`. This
recovered 1,668 projections through 2026-07-31 — vs only 299–367 from
row-by-row `SELECT` which hits the broken B-tree and stops.

`.dump` was also run as a cross-check: 5,360 lines vs 8,549 from `.recover`
(`.dump` errored on the malformed pages; `.recover` did not).

## Merge rule

**`.recover` wins on overlap; current DB fills what `.recover` could not reach.**

1. **projections** — no UNIQUE constraint. Keyed on `(game_pk, game_date, created_at)`.
   All rows from both sources are kept (no dedup). Same-game revisions minutes
   apart are preserved — choosing a revision is a point-in-time decision.
2. **graded_results** — `UNIQUE(game_pk, game_date)`. On overlap, `.recover` row
   wins (from the newer original file).
3. **parlays** — `UNIQUE(game_date, parlay_type)`. Same rule.
4. **transactions** — `UNIQUE(game_date, transaction_id)`. Same rule.
5. **results, props, lineup_changes** — no UNIQUE constraint. Keyed on
   `(game_pk, game_date, updated_at/created_at/recorded_at)`. `.recover` wins
   on overlap.

## FK repair: results.projection_id

**Rule:** For each result, find the projection with the latest `created_at`
matching on `(game_pk, game_date)`. This is the revision the grading pipeline
would have used (latest projection before game time).

| Metric | Before | After |
|---|---|---|
| valid, same game | 297 | 1,661 |
| valid, wrong game | 1,368 | 0 |
| dangling (no such projection) | 0 | 0 |
| NULL (no matching projection) | 0 | 4 |

The 1,368 wrong-game FKs were caused by AUTOINCREMENT id reuse after the
earlier row-by-row recovery assigned new ids that collided with the original
numbering. All repaired.

4 results have no matching projection (NULLed):
- `id=300` 2026-04-08 SDP@PIT (gpk 823403)
- `id=301` 2026-04-08 KCR@CLE (gpk 824455)
- `id=1601` 2026-07-31 PIT@CIN (gpk 824486)
- `id=1602` 2026-07-31 PHI@BAL (gpk 824809)

## Revision duplicates

26 games have multiple projection revisions (same `game_pk` + `game_date`,
different `created_at`). All are from 2026-04-06 and 2026-04-07 — a 7:00am
run followed by a ~7:05am refresh.

- **1** flips lean: game_pk=822916, 2026-04-07, NEUTRAL → OVER
- **7** flip star_rating (confidence tier change between runs)

All revisions preserved. No dedup applied.

## Disagreement check (Step 1)

299 rows overlap on `(game_pk, game_date, created_at)` between `.recover` and
the current DB. **All 299 agree on every column.** Zero disagreements.

For tables with UNIQUE constraints:
- graded_results: 288 overlap, 0 disagree (`.recover` wins by rule)
- parlays: 27 overlap, 0 disagree
- transactions: 24 overlap, 0 disagree

The 14 "disagreements" found in the earlier id-based check were **not stale
rows** — they were entirely different games assigned the same AUTOINCREMENT id
after reconstruction. The natural-key check confirmed zero actual data
conflicts.

## Permanently truncated tables

**props** ends 2026-04-07 and **transactions** ends 2026-04-06. Both `.recover`
and the current DB have the same cutoff — the pipeline stopped writing to
these tables in early April 2026, well before the Jul 31 corruption. This is
not a recovery failure; the data was never written. The `props` and
`transactions` insert paths were likely disabled or broken by an earlier code
change. These rows are unrecoverable.

## Pipeline gap: 2026-08-01 through 2026-08-28

**projections** and **results** have a complete gap from 2026-08-01 to
2026-08-28 (last pre-gap `game_date` = 2026-07-31, next = 2026-08-29). This
is data that was never written — the pipeline was crashing on the corrupt DB
during this entire window. **graded_results** similarly ends 2026-07-30.

Any backtest, ROI calculation, or grading query over this window must treat
these dates as **missing data, not zero**. A `WHERE game_date BETWEEN ...`
will silently return an incomplete sample. Filter or flag accordingly.

## Per-table row counts

| Table | .recover | current | merged | date range | notes |
|---|---|---|---|---|---|
| projections | 1,668 | 384 | 1,753 | 2026-03-11 → 2026-08-29 | gap 08-01..08-28 |
| results | 1,602 | 1,665 | 1,665 | 2026-03-11 → 2026-08-29 | gap 08-01..08-28 |
| graded_results | 1,629 | 367 | 1,708 | 2026-03-11 → 2026-07-30 | gap 08-01..present |
| props | 1,929 | 1,929 | 1,929 | 2026-03-13 → 2026-04-07 | **permanently truncated** |
| lineup_changes | 993 | 993 | 993 | 2026-03-13 → 2026-07-28 | |
| transactions | 24 | 71 | 71 | 2026-03-14 → 2026-04-06 | **permanently truncated** |
| parlays | 27 | 36 | 36 | 2026-03-13 → 2026-08-29 | |

## Verification

- `PRAGMA integrity_check`: **ok**
- Zero duplicate primary keys across all 7 tables
- Zero UNIQUE constraint violations (graded_results, parlays, transactions)
- Zero dangling FKs, zero wrong-game FKs

## Output

`data/mlb_model.db.merged` — 3,297,280 bytes,
SHA-256 `bce8392acfbd2d3eaf0f29a9a4d627d0976e19f8ee8809145886af75ff41c04a`

**Promoted** to `data/mlb_model.db` on 2026-08-29. Previous DB preserved as
`data/mlb_model.db.prerecover_20260828_231731`.
