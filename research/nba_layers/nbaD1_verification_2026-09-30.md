# NBA-D1 verification — Cowork (NBA chat), 2026-09-30 ~19:10Z

Checked from the files on the Mac (data root `data/odds_archive/nba/history/`, 1.2 GB) and origin/nba/data-d1
(5 commits 931b88e6f..05664f207; the report said 4). Not re-read from the report: every number below was
recomputed here.

## Holds
- Git safety: `data/odds_archive/nba/history/` is in `.git/info/exclude` (check-ignore prints it) and in the branch's
  .gitignore; `git ls-files` under it = 0. Nothing reached the public repo.
- File counts equal the report: lines 4,775/4,626/4,743/4,785 (2022-25, parquet = json.gz), in-play
  13,768/14,171/7,370, props and event_markets 2,548/2,494/2,468 (2023/2024/2025).
- Hard Rock key `hardrockbet` returns rows; Pinnacle returns in every season.
- Close (A4): events with a pre-tip row in a close file 1,242/1,254 (2022), 1,271/1,274 (2023), 1,245/1,247 (2024),
  1,234/1,234 (2025). Gap from the last pre-tip snapshot to the actual tip (the API moves commence_time to the real
  tip, ~10 min after the scheduled time): median 9.4 min, p90 19.4 min (11.4 in 2025). Pinnacle present in that last
  snapshot on 98.7% / 95.5% / 97.4% / 99.7% of events.
- In-play: 19.1% of rows in a 60-file 2024 sample are live (snapshot after commence), 10 books present live.
- Null control (a): not re-run here; the method (match on DK last_update, exact price) is the right one.

## Wrong or missing in the report
1. **Hard Rock is NOT absent in 2023-24.** B-D1 and B-D2 say "Absent" for season 2023. The data has it: first seen in
   the close file of 2023-11-28; share of close files with Hard Rock by month Oct 0/31, Nov 15/149, Dec 95/125,
   Jan 144/150, Feb-Apr 100%. Last pre-tip snapshot has Hard Rock on 74.1% of 2023-24 events (98.8% 2024-25, 97.7%
   2025-26). Props 2023: Hard Rock rows present (3,874 of 43,519 in a 60-file sample). The probe used one early
   slot per season, before Hard Rock's late-November listing.
2. **Null control (b) was never reported, and as specified it fails for item 1 by design.** 8 of 50 sampled files
   had fewer parquet rows than json outcomes — all in lines_hourly, none in in-play. Every mismatch checked equals
   the live games' outcomes exactly (e.g. 190 json - 28 live = 162 parquet): item 1 drops games already started;
   the raw json keeps them. Not data loss; must be stated.
3. **T-24h props and derivative snapshots are mostly empty.** Empty files, 150 sampled per cell: props T-24h
   87 / 108 / 96 (58-72%), T-1h 4 / 1 / 2; event_markets T-24h 57 / 58 / 74, T-1h 3 / 1 / 1. Books had not posted
   player props a day out. In practice D1 holds ONE props snapshot per game (T-1h); there is no props opening line
   or props movement. Charged cost on those calls appears ~0 (per-call average 51-54, not 80).
4. **"Regular season only" is not exact.** events_2023 has 10 games after 2024-04-15 and events_2024 has 8 after
   2025-04-14 (play-in / first playoff days inside the date range). Label or drop them in any analysis.
5. In-play 2023-24 is the FIRST half only: Oct 553, Nov 2,438, Dec 2,216, Jan 2,163 snapshots; nothing Feb-Apr.

## Not verified
- Cost per call from headers (the log's numbers are taken as reported; ~876k remaining at end, not re-read).
- Item 0 schedule files against an external schedule.
- Whether the pinnacle rows at close are fresh (book_last_update) or stale quotes carried in the snapshot.

## Addendum 2026-09-30 ~19:45Z — duplicated calls (Jeff asked)
Method: same requested timestamp in two folders = same API snapshot (checked: 20/20 sampled pairs have identical
raw json, timestamp and data). Counted from file names, season by season.

| season | close == hourly | in-play == hourly | in-play == close | duplicate calls | credits (x30) |
|---|---|---|---|---|---|
| 2022-23 | 0 | — | — | 0 | 0 |
| 2023-24 | 2 | 600 | 427 | 1,027 | 30,810 |
| 2024-25 | 0 | 1,071 | 831 | 1,902 | 57,060 |
| 2025-26 | 0 | 1,121 | 821 | 1,942 | 58,260 |
| total | | | | **4,871** | **~146,000 (~6% of 2.4M)** |

Cause: item 3's 5-minute in-play grid runs from first tip - 5 min, so it lands on every hourly slot and every close
slot inside the game window. The parquets differ (item 1 drops games already started, in-play keeps them); the raw
json.gz files are byte-for-byte the same responses. Any loader must de-duplicate on snapshot_utc across
lines_hourly/ and inplay/. Fix for any future pull: in-play skips request times already on disk in lines_hourly/.
Not a duplicate: overlap with the March-2026 backfill (`data/odds_archive/nba/{game_markets,props}`, 2025-26,
8 shared books) — Pinnacle and Hard Rock are new, and extra books inside the 10-book slot cost nothing.
Not checked: requests at different times that resolve to the same 5-minute snapshot (all D1 requests sit on the
5-minute grid, so this should be rare).
