# Capture Status — 2026-09-20 (updated by WO10b)

All feeds run on VM (root@142.93.242.4) via cron. Push daemon syncs to GitHub
every 30 min.

## Feed Table

| Feed            | Source          | Script                                       | Cron (UTC)                    | Output Path                                                     | Steady-state KB/pull | MB/month | Cost      | First Observed Firing |
|-----------------|-----------------|----------------------------------------------|-------------------------------|-----------------------------------------------------------------|---------------------|----------|-----------|---------------------|
| NFL lines       | Odds API        | shared/pipeline/multi_book_open_capture.py   | */30 14-23,0-5 * * *          | data/odds_archive/nfl/line_history/season=2026/snap_*.parquet   | ~15 KB              | (existing) | 6 cr/pull | Running (pre-WO10) |
| NCAAF lines     | Odds API        | shared/pipeline/multi_book_open_capture.py   | */30 14-23,0-5 * * *          | data/odds_archive/ncaaf/line_history/season=2026/snap_*.parquet | ~15 KB              | (existing) | 6 cr/pull | Running (pre-WO10) |
| NFL props (HR)  | Odds API        | nfl/pipeline/pull_hardrock_props.py          | See N28 (8 entries)           | data/odds_archive/nfl/props/season=2026/month=*/data_*.parquet  | varies              | varies   | ~1090/wk  | Not yet observed   |
| NFL news        | ESPN            | shared/pipeline/pull_espn_news.py --sport nfl| 10 0,6,12,18 * * *            | data/news_archive/nfl/season=2026/news_+index_*.json.gz         | 6 KB (de-duped)     | 0.7      | 0         | Not yet observed   |
| NCAAF news      | ESPN            | shared/pipeline/pull_espn_news.py --sport ncaaf| 20 0,6,12,18 * * *          | data/news_archive/ncaaf/season=2026/news_+index_*.json.gz       | 16 KB (de-duped)    | 1.9      | 0         | Not yet observed   |
| NFL injuries    | ESPN            | shared/pipeline/pull_espn_nfl_status.py      | 30 0,6,12,18 * * *; 40 16 * * 0 | data/injury_archive/nfl/season=2026/injuries_*.json.gz       | 0 (hash-skip) / 353 KB | ~1.4  | 0         | Not yet observed   |
| NFL depth       | ESPN            | shared/pipeline/pull_espn_nfl_status.py      | 30 0,6,12,18 * * *; 40 16 * * 0 | data/depth_archive/nfl/season=2026/depth_*.json.gz           | 0 (hash-skip) / 386 KB | ~1.2  | 0         | Not yet observed   |
| nflverse inputs | nflreadpy       | shared/pipeline/run_nflverse_with_archive.sh | 0 9 * * *                     | data/depth_archive/nfl/season=2026/nflverse_*.parquet           | 0 (hash-skip) / 11.5 MB | ~46-92 | 0       | Not yet observed   |
| Kalshi NFL      | Kalshi REST API | shared/pipeline/pull_kalshi_football.py --sport nfl | 5,35 0-5,14-23 * * *    | data/odds_archive/kalshi/nfl/season=2026/snap_*.parquet         | 55 KB               | 53       | 0         | **02:35:01 UTC**   |
| Kalshi NCAAF    | Kalshi REST API | shared/pipeline/pull_kalshi_football.py --sport ncaaf | 6 cron lines (N33)   | data/odds_archive/kalshi/ncaaf/season=2026/snap_*.parquet       | 95 KB               | 50       | 0         | **02:37:01 UTC**   |
| Health check    | local files     | shared/pipeline/capture_health.py            | 45 * * * *                    | logs/capture_health.log                                         | ~1 KB               | ~0.04    | 0         | **02:45:01 UTC**   |

**Total football capture: ~154-200 MB/month** (under 300 MB target, N33).

## WO10b Changes

- **News de-duplication:** `_seen.json` state file; writes only new/changed articles + full index per pull
- **Injuries/depth gzip + hash-skip:** `.json` -> `.json.gz`; content-hash skip with `_pulls.jsonl` audit trail
- **nflverse hash-skip:** SHA-256 comparison; `_pulls.jsonl` for skipped copies
- **NCAAF Kalshi schedule:** 30-min during Fri 14:00-Sun 05:30 UTC, 3h otherwise (6 cron lines)
- **Health check rewrite:** filename timestamps (not st_mtime), tz-aware UTC, no bare except, _pulls.jsonl support

## Health Check Output (VM, 2026-09-20T03:33Z)

```
OK     nfl_lines: 0.1h old (max 0.8h)
OK     ncaaf_lines: 0.1h old (max 0.8h)
OK     kalshi_nfl: 0.2h old (max 0.8h)
OK     kalshi_ncaaf: 0.2h old (max 0.8h)
OK     nfl_news: 0.2h old (max 7.0h)
OK     ncaaf_news: 0.2h old (max 7.0h)
OK     nfl_injuries: 0.2h old (max 7.0h)
OK     nfl_depth: 0.2h old (max 7.0h)
OK     nflverse_inputs: 0.2h old (max 26.0h)
OK     nfl_props: 12.4h old (max 26.0h)
OK: all feeds fresh
```

## Health Check Output (fresh clone of origin, 2026-09-20T03:35Z)

```
OK     nfl_lines: 0.6h old (max 0.8h)
OK     ncaaf_lines: 0.6h old (max 0.8h)
OK     kalshi_nfl: 0.2h old (max 0.8h)
OK     kalshi_ncaaf: 0.2h old (max 0.8h)
OK     nfl_news: 0.3h old (max 7.0h)
OK     ncaaf_news: 0.3h old (max 7.0h)
OK     nfl_injuries: 0.2h old (max 7.0h)
OK     nfl_depth: 0.2h old (max 7.0h)
OK     nflverse_inputs: 0.2h old (max 26.0h)
OK     nfl_props: 12.4h old (max 26.0h)
OK: all feeds fresh
```

Both agree to within push delay. nfl_props at 12.4h, not 4,226h.

## WO11 Changes (2026-09-20)

- **Feed health per-feed filtering (N40):** `_newest_pulls_age_by_feed` filters
  `_pulls.jsonl` by `feed` field. ESPN depth and nflverse depth no longer share a
  pulse. Lines without explicit `feed` get it inferred from `file` key. Lines without
  both are ignored.
- **`__init__.py` removed from all three test directories:** `pytest shared/pipeline/tests
  nfl/pipeline/tests ncaaf/pipeline/tests` now collects and runs in ONE command (55 tests).
- **Thresholds:** unchanged from WO10b. nfl_depth checks `espn_depth` feed only;
  nflverse_inputs checks `nflverse_depth` feed only.

## Cowork verification of WO11 (2026-09-20T11:50Z) — N41, N42

- The grader never resolved an outcome for an event ticket (commence_time read from the leg);
  fixed, with neutral-site matching, explicit team names, `pending` for games CFBD has not
  completed, outcome independent of close, and the tape's last pre-kick kickoff.
  Real data: 71/71 kicked 09-19 events resolved, 284 legs, 0 disagreements.
- **Run `python3 ncaaf/pipeline/pull_cfbd_season.py --year 2026` before grading** — nothing
  refreshes the CFBD file on a schedule. Un-refreshed = `outcome_pending`, never a wrong grade.
- Every `_pulls.jsonl` line now carries `feed`; the ESPN hash-skip reads only its own feed.
  First proof on the VM: a line with `"feed"` after the next ESPN (:30 of 00/06/12/18Z) and
  nflverse (09:00Z) pulls that follow the push.
- Builder: abstains logged, input manifest per game, legs only from the event's newest
  snapshot, tape validation keyed on event + snapshot, 14-day news window applied, coverage
  halt 90%. Card builder repaired (fillers are real single-book rows; legs keep complements).
- Kalshi cadence is every 30 min inside 14:00-05:30Z only (NFL), plus 3-hourly outside it for
  NCAAF — not "every 30 min" round the clock.
- Build the Saturday NCAAF tickets AFTER the 14:00Z line pull: capture pauses 05:30-14:00Z, so an
  11:00Z build prices off 05:30Z quotes.
