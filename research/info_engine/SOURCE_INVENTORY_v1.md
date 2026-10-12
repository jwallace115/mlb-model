# SOURCE INVENTORY v1 (IE-D1) — 2026-10-11

Pulled via `nfl_data_py` + existing on-disk files. One season (2023) saved to
`nfl/data/info/<source>_2023.parquet` for each API source. Season probes: 2016-2026.

## API Sources (nfl_data_py)

| # | Source | Rows (2023) | Cols | Seasons Available | PIT Status | PIT Column | Revised After Pub? | Market Under-weight Mechanism |
|---|--------|-------------|------|-------------------|------------|------------|-------------------|-------------------------------|
| 1 | **ftn_charting** | 48,225 | 29 | 2022-2026 | TIMESTAMPED | `date_pulled` | UNVERIFIABLE (no prior copy on disk) | Play-level pre-snap reads (motion, RPO, screen, play-action, blitzer count) — charted by humans, not in box scores; market may treat offense/defense scheme tendencies as stable when they shift week-to-week |
| 2 | **ngs_passing** | 620 | 29 | 2016-2026 | WEEK-KEYED | `week` | UNVERIFIABLE (no prior copy; NGS is known to revise completion probability models across seasons) | Next Gen air-yards, time-to-throw, aggressiveness, CPOE — granular efficiency beyond box-score passer rating; market may under-weight short-term CPOE streaks |
| 3 | **ngs_rushing** | 623 | 22 | 2016-2026 | WEEK-KEYED | `week` | UNVERIFIABLE | Rush yards over expected (RYOE), time to LOS, efficiency vs stacked boxes — separates scheme from talent; market may anchor on raw rushing yards |
| 4 | **ngs_receiving** | 1,473 | 23 | 2016-2026 | WEEK-KEYED | `week` | UNVERIFIABLE | Cushion, separation, YAC above expectation — receiver skill vs scheme; market may over-weight target volume |
| 5 | **snap_counts** | 26,540 | 16 | 2016-2026 | WEEK-KEYED | `week` | UNVERIFIABLE (PFR-sourced; PFR corrects snap counts occasionally) | Offense/defense/ST snap share by player — reveals usage changes before stat lines do; market may miss a backup getting 40% snaps as a leading indicator |
| 6 | **pfr_weekly_pass** | 700 | 24 | 2018-2026 | WEEK-KEYED | `week` | UNVERIFIABLE (PFR revises advanced stats; known to correct sack/pressure attribution) | Pressure rate, blitz rate, drop rate, bad throw % — pass-protection and accuracy quality not visible in box scores; market may anchor on yards/TDs |
| 7 | **officials** | 1,993 | 5 | 2016-2026 | WEEK-KEYED | `game_id` | UNVERIFIABLE | Referee crew assignment — some crews' penalty rates shift game pace/scoring systematically; market may under-weight crew-specific effects |
| 8 | **injuries** | 5,599 | 16 | 2016-2026 | TIMESTAMPED | `date_modified` | YES — by definition: injury reports update Wed/Thu/Fri/Sat with practice status changes. `date_modified` tracks the latest update. A Wednesday "Limited" can become Friday "Full" or "Out". Point-in-time requires filtering to the LATEST report before kickoff. | Market prices injuries but may under-weight the trajectory (Limited→Full = positive signal vs static "Questionable") |
| 9 | **rosters_weekly** | 45,655 | 37 | 2016-2026 | WEEK-KEYED | `week` | YES — roster status changes (IR, Practice Squad, Active) get updated retroactively within the week. The `week` key gives the snapshot as of that week's roster deadline. | Roster moves (activations, elevations) signal game-plan intent; market may not fully price a Tuesday PS elevation |
| 10 | **depth_charts** | 37,327 | 15 | 2016-2026 | WEEK-KEYED | `week` | YES — depth charts are updated multiple times per week. The nflverse snapshot is taken at some point during the week. Earlier weeks' data may be revised. **This is the source that silently breaks PIT** (see note below). | Depth chart position reveals starter changes before game day; market may lag on a mid-week QB switch |
| 11 | **schedules** | 285 | 46 | 2016-2026 | WEEK-KEYED | `week` | YES — scores, QBs, weather filled in post-game. Pre-game fields (rest days, roof, surface, spread_line, total_line) are stable after Tuesday. `spread_line` and `total_line` are **CLOSING** lines (verified: 201/201 match closing_total_line from line_movement.parquet, only 37/201 match open). | Rest days, surface, roof, referee — all in one table; market prices these but aggregation across crews/surfaces may find residual |

## On-Disk Files (not from nfl_data_py)

| # | File | Rows | Seasons | Key Columns | PIT Status | Revised? | Mechanism |
|---|------|------|---------|-------------|------------|----------|-----------|
| 12 | **nfl_line_movement.parquet** | 775 | 2021-2024 | game_id, open_total_line, closing_total_line, line_move, total_points, actual_vs_open, actual_vs_close | WEEK-KEYED (snapshot_date ~5 days pre-game) | No — snapshot is point-in-time by construction | Opening total line captures early-week market; movement direction and magnitude are the signal |
| 13 | **opening_lines_raw.parquet** | 1,329 | 2021-2024 (no season col; inferred from commence_date) | home_team_odds, away_team_odds, open_total_line, n_books, snapshot_date | WEEK-KEYED (snapshot_date) | No | Consensus opening total across 13 books; **NO SPREAD OPENS** — totals only |
| 14 | **nfl_wind_archive_allseasons.parquet** | 1,160 | 2019-2024 | game_id, temperature, wind_speed, precipitation, closing_total_line, resid, arch_wind | WEEK-KEYED (game date) | No — post-game archive | Game-day weather + residual vs close; wind/precip affect outdoor scoring |
| 15 | **nfl_wind_forecast_pit_2024.parquet** | 187 | 2024 only | wind_speed_10m (+ 3 prior days), ts (forecast timestamp) | TIMESTAMPED | No — point-in-time forecast captures | Pre-game wind forecast vs actual; market may use stale forecasts |
| 16 | **pbp/pbp_20{20..25}.parquet** | ~50k rows/season | 2020-2025 | Full play-by-play: game_id, week, spread_line (CLOSING), total_line (CLOSING), EPA, WPA, etc. | WEEK-KEYED | YES — nflverse PBP is revised when charting corrections are applied (known to update EPA values retroactively). | Play-level data enables any derived feature; market may not decompose situational EPA |
| 17 | **research/ref_crew_aggregates.csv** | 83 | Multi-season aggregate | ref_name, total_games, avg_total_points, avg_ft_rate | END-OF-SEASON | N/A — aggregate | **EXCLUDED from feature table by construction** (end-of-season aggregate, no week key, no PIT guarantee) |
| 18 | **data/odds_archive/nfl/line_history/** | 1,418 snaps | 2026 only (Sep 6 – Oct 12) | snapshot_utc, bookmaker, market (h2h/spreads/totals), point, price | TIMESTAMPED | No — each snap is immutable | Live odds tape: spreads + totals + h2h across 10 books. **This is the only source of spread opens for any season on disk.** |

## Critical PIT Note

**depth_charts (#10)** is the source most likely to silently break point-in-time.
The nflverse depth chart data is a snapshot taken at an unspecified time during each
week. If a depth chart is pulled on Wednesday and the starter changes on Saturday,
the Wednesday pull is stale but the data shows `week=N` with no timestamp of when
the snapshot was taken. There is no `date_pulled` or `date_modified` column. A
feature built from depth charts using only the `week` key would be as-of "sometime
during that week" — good enough for a discovery filter, dangerous for a live signal.

**rosters_weekly (#9)** has the same issue: roster moves happen throughout the week
but are keyed only to `week`.

**injuries (#8)** is the cleanest — `date_modified` is a UTC timestamp, so features
can be filtered to "latest report before kickoff."

**NGS (#2-4) and PFR (#6)** are published after games and may be revised across
seasons (NGS has updated its CPOE model at least once). Within-season revision is
UNVERIFIABLE from this Mac — no prior weekly pull exists to diff against.

**ftn_charting (#1)** `date_pulled` is a batch timestamp (all 2023 rows show
`2024-09-06T23:50:14Z`) — it records when the nflverse pipeline scraped FTN, not
when FTN graded the play. The actual charting happens post-game but the exact
grading date per play is not in the data.
