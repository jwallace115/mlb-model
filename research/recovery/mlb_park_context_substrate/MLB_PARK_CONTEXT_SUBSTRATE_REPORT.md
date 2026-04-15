# MLB PARK / GAME-CONTEXT SUBSTRATE — BUILD REPORT
Generated: 2026-04-15 11:43:30
Source: sim/data/game_table.parquet
Output: research/recovery/mlb_park_context_substrate/mlb_park_context_substrate.parquet

---

## 1. PURPOSE

The mlb_park_context_substrate provides the static and structural pregame context for every
MLB game in the model corpus. It captures venue identity, park environment factors,
game-structure metadata, and team schedule-rest — all knowable before a game begins.

This substrate deliberately EXCLUDES:
- Weather (temperature, wind) — reserved for a dedicated weather substrate
- Umpire assignments and ratings — reserved for a dedicated umpire substrate
- All postgame realized outcomes (scores, innings, completion flags)
- Same-season-performance-derived park factors (none found; confirmed static)

---

## 2. GRAIN AND COVERAGE

| Property              | Value         |
|----------------------|---------------|
| Row count            | 9,902         |
| Grain                | 1 row per game_pk |
| game_pk unique       | True (verified) |
| Duplicate rows       | 0             |
| Seasons covered      | 2022–2026     |
| Columns total        | 17            |

Season-by-season row counts:
  2022: 2,430
  2023: 2,430
  2024: 2,427
  2025: 2,428
  2026: 187

Note: 2026 contains 187 rows through April 15, 2026 (in-season).

---

## 3. FIELD CLASSIFICATION TABLE

### CARRIED_ONLY (5 fields — identity/join keys, not modeling features)

| Field       | Type   | Null% | Description |
|-------------|--------|-------|-------------|
| game_pk              | int64    | 0.0%  | Primary join key; MLB Stats API game_pk integer |
| date                 | object   | 0.0%  | Game date string (YYYY-MM-DD) |
| season               | int64    | 0.0%  | Season year (int) |
| home_team            | object   | 0.0%  | Home team abbreviation (MLB standard 3-letter) |
| away_team            | object   | 0.0%  | Away team abbreviation (MLB standard 3-letter) |

### APPROVED_CONTEXT_FEATURE (12 fields — pregame-safe modeling features)

| Field               | Type    | Null% | Description |
|--------------------|---------|-------|-------------|
| venue_id                  | int64    | 0.0%  | MLB Stats API venue integer ID; unique per physical ballpark |
| venue_name                | object   | 0.0%  | Human-readable venue name; static per venue_id |
| park_id                   | int64    | 0.0%  | Alias for venue_id in game_table; same integer; retained for back |
| park_factor_runs          | int64    | 0.0%  | Preseason static run-environment factor per home_team; confirmed  |
| park_factor_hr            | int64    | 0.0%  | Preseason static HR-environment factor per home_team; same confir |
| roof_status               | object   | 0.0%  | Venue roof type: open / retractable / dome; static structural pro |
| game_number               | int64    | 0.0%  | Doubleheader game number: 1 (first game or single game) or 2 (nig |
| doubleheader_flag         | int64    | 0.0%  | Binary 0/1: 1 if any doubleheader game, 0 otherwise; derived from |
| game_hour_utc             | int64    | 0.0%  | Scheduled start hour in UTC (0-23); from MLB Stats API schedule;  |
| local_start_hour          | float64  | 23.4%  | Scheduled local start hour (float); null for ~23% of rows due to  |
| home_rest_days            | int64    | 0.0%  | Days since home team last played; computed via shift from prior r |
| away_rest_days            | int64    | 0.0%  | Days since away team last played; same computation as home_rest_d |

### EXCLUDED (13 fields — not in substrate)

| Field               | Category  | Reason |
|--------------------|-----------|--------|
| temperature               | EXCLUDED   | WEATHER: realized game-time temperature; belongs in separate |
| wind_speed                | EXCLUDED   | WEATHER: realized wind speed; separate weather substrate |
| wind_direction            | EXCLUDED   | WEATHER: realized wind direction; separate weather substrate |
| umpire_name               | EXCLUDED   | UMPIRE: HP umpire name; separate umpire substrate |
| umpire_id                 | EXCLUDED   | UMPIRE: HP umpire MLB ID; separate umpire substrate |
| umpire_over_rate          | EXCLUDED   | UMPIRE: umpire historical over rate; separate umpire substra |
| umpire_k_rate             | EXCLUDED   | UMPIRE: umpire historical K rate; separate umpire substrate |
| home_score                | EXCLUDED   | POSTGAME: realized home team runs scored |
| away_score                | EXCLUDED   | POSTGAME: realized away team runs scored |
| actual_total              | EXCLUDED   | POSTGAME: realized total runs in game |
| actual_f5_total           | EXCLUDED   | POSTGAME: realized F5 total runs |
| innings_played            | EXCLUDED   | POSTGAME: innings played (9 for completed; >9 for extras; <9 |
| completed_early           | EXCLUDED   | POSTGAME: True if game suspended/shortened; False otherwise |

---

## 4. PARK FACTOR SOURCE LINEAGE

park_factor_runs and park_factor_hr are confirmed to be static preseason lookups:
- Zero variation across seasons for any team (verified: groupby home_team + season → nunique == 1 for all)
- These values match the static config.py PARK_FACTORS table
- They are NOT derived from same-season scoring (which would be retroactive/PIT-unsafe)
- COL=117 (Coors Field) is highest; NYM=94, LAD=95, SEA=94 are lowest

All 30 team park factors (runs = HR for this substrate):
home_team  park_factor_runs  park_factor_hr
      ARI                98              98
      ATL               102             102
      BAL               106             106
      BOS               104             104
      CHC               103             103
      CHW               100             100
      CIN               107             107
      CLE                98              98
      COL               117             117
      DET                99              99
      HOU               100             100
      KCR               100             100
      LAA                97              97
      LAD                95              95
      MIA                98              98
      MIL               102             102
      MIN                99              99
      NYM                94              94
      NYY               103             103
      OAK                95              95
      PHI               104             104
      PIT               101             101
      SDP                95              95
      SEA                94              94
      SFG                96              96
      STL                97              97
      TBR                97              97
      TEX               107             107
      TOR               105             105
      WSN               101             101

Note: park_id has up to 2 unique values per (home_team, season) in 15 team-season pairs.
This reflects neutral-site special games (e.g., Field of Dreams, London Series, Little League Classic).
The park_factor fields are NOT affected — they remain static per home_team as these games
are mapped to the home team's standard park factor.

---

## 5. ROOF STATUS DISTRIBUTION

| roof_status   | Count | Pct   |
|--------------|-------|-------|
| open           | 7,586 | 76.6%  |
| retractable    | 1,989 | 20.1%  |
| dome           |   327 | 3.3%  |

Dome venues: TBR (Tropicana Field), HOU (Minute Maid), MIA (loanDepot Park), and a small
number of MIL games (American Family Field has retractable).

---

## 6. REST DAYS NOTES

- home_rest_days / away_rest_days capped at 5 (value 5 = "5 or more days rest")
- 162 games where both teams have rest_days=0: these are doubleheader game 2
- Distribution is heavily concentrated at 1 (next-day games in series): ~83.8%
- PIT-SAFE: computed from prior-game dates only (shift logic); no forward leakage

---

## 7. LOCAL_START_HOUR NULLS

local_start_hour has 2,316 nulls (23.4%).
Season distribution of nulls: {2022: 567, 2023: 567, 2024: 567, 2025: 567, 2026: 48}
Cause: timezone resolution was missing for these games in the source build.
Mitigation: game_hour_utc (0 nulls) is always available as fallback.
Recommendation: when using local_start_hour, fill with (game_hour_utc - 4) % 24 as ET approximation.

---

## 8. DOUBLEHEADER LOGIC

- doubleheader_flag=1: 328 games (3.3%)
- game_number=2: 162 games — nightcap of a doubleheader
- Note: doubleheader_flag counts both games in the pair; game_number=2 identifies only the second game
- Both are pregame-safe from the MLB schedule API

---

## 9. PIT-SAFETY VERDICT

ALL 12 APPROVED_CONTEXT_FEATURE fields are PIT-safe:
- Venue/park fields: static structural properties; no temporal information
- Park factors: confirmed static preseason lookup; no same-season scoring derivation
- Roof status: static per venue; does not change within a season
- game_number / doubleheader_flag / game_hour_utc / local_start_hour: schedule-derived; published before games
- home_rest_days / away_rest_days: computed from prior-game dates using shift logic; no future leakage

EXCLUDED fields correctly remove all postgame realized outcomes, weather, and umpire data.

PIT-SAFETY: PASS — no information from the future is encoded in any APPROVED field.
