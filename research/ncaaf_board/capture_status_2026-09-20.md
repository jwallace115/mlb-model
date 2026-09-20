# Capture Status — 2026-09-20

All feeds run on VM (root@142.93.242.4) via cron. Push daemon syncs to GitHub
every 30 min.

## Feed Table

| Feed            | Source          | Script                                       | Cron (UTC)                    | Output Path                                                     | Size/Pull  | Cost      | First Sched. Firing |
|-----------------|-----------------|----------------------------------------------|-------------------------------|-----------------------------------------------------------------|------------|-----------|---------------------|
| NFL lines       | Odds API        | shared/pipeline/multi_book_open_capture.py   | */30 14-23,0-5 * * *          | data/odds_archive/nfl/line_history/season=2026/snap_*.parquet   | ~15 KB     | 6 cr/pull | Running (pre-WO10)  |
| NCAAF lines     | Odds API        | shared/pipeline/multi_book_open_capture.py   | */30 14-23,0-5 * * *          | data/odds_archive/ncaaf/line_history/season=2026/snap_*.parquet | ~15 KB     | 6 cr/pull | Running (pre-WO10)  |
| NFL props (HR)  | Odds API        | nfl/pipeline/pull_hardrock_props.py          | See N28 (8 entries)           | data/odds_archive/nfl/props/season=2026/month=*/data_*.parquet  | ~150 cr/wk | ~1090/wk  | Not yet observed    |
| NFL news        | ESPN            | shared/pipeline/pull_espn_news.py --sport nfl| 10 0,6,12,18 * * *            | data/news_archive/nfl/season=2026/news_*.json.gz                | ~1.1 MB    | 0         | Not yet observed    |
| NCAAF news      | ESPN            | shared/pipeline/pull_espn_news.py --sport ncaaf| 20 0,6,12,18 * * *          | data/news_archive/ncaaf/season=2026/news_*.json.gz              | ~10 MB     | 0         | Not yet observed    |
| NFL injuries    | ESPN            | shared/pipeline/pull_espn_nfl_status.py      | 30 0,6,12,18 * * *; 40 16 * * 0 | data/injury_archive/nfl/season=2026/injuries_*.json          | ~9 MB      | 0         | Not yet observed    |
| NFL depth       | ESPN            | shared/pipeline/pull_espn_nfl_status.py      | 30 0,6,12,18 * * *; 40 16 * * 0 | data/depth_archive/nfl/season=2026/depth_*.json              | ~7 MB      | 0         | Not yet observed    |
| nflverse inputs | nflreadpy       | shared/pipeline/run_nflverse_with_archive.sh | 0 9 * * *                     | data/depth_archive/nfl/season=2026/nflverse_*.parquet           | ~12 MB     | 0         | Not yet observed    |
| Kalshi NFL      | Kalshi REST API | shared/pipeline/pull_kalshi_football.py --sport nfl | 5,35 0-5,14-23 * * *    | data/odds_archive/kalshi/nfl/season=2026/snap_*.parquet         | ~55 KB     | 0         | **02:35:01 UTC**    |
| Kalshi NCAAF    | Kalshi REST API | shared/pipeline/pull_kalshi_football.py --sport ncaaf | 7,37 0-5,14-23 * * * | data/odds_archive/kalshi/ncaaf/season=2026/snap_*.parquet       | ~140 KB    | 0         | **02:37:01 UTC**    |
| Health check    | local files     | shared/pipeline/capture_health.py            | 45 * * * *                    | logs/capture_health.log                                         | ~1 KB      | 0         | **02:45:01 UTC**    |

## Observed Scheduled Firings (syslog evidence)

```
2026-09-20T02:35:01 CRON ... pull_kalshi_football.py --sport nfl >> kalshi_nfl.log
  -> snap_20260920T0235Z.parquet, 783 rows, 55 KB
2026-09-20T02:37:01 CRON ... pull_kalshi_football.py --sport ncaaf >> kalshi_ncaaf.log
  -> snap_20260920T0237Z.parquet, 2,382 rows, 136 KB
2026-09-20T02:45:01 CRON ... capture_health.py >> capture_health.log
  -> 9/10 OK, 1 STALE (nfl_props: 4225.8h, first scheduled pull is Sun 15:00 UTC)
```

## Notes

- NFL props D84 entries installed 2026-09-18; first scheduled slot is Sun 15:00 UTC 2026-09-20.
- ESPN feeds first scheduled at 06:10/06:20/06:30 UTC today.
- nflverse first scheduled at 09:00 UTC today.
- NFL lines and NCAAF lines are pre-existing (700+ snapshots each). Not touched.
- Storage projections: N29 (ESPN) and N30 (Kalshi).
