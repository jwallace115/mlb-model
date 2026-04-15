# MLB WEATHER SUBSTRATE — BUILD REPORT
Generated: 2026-04-15 14:23:10
Source: sim/data/game_table.parquet
Output: research/recovery/mlb_weather_substrate/mlb_weather_substrate.parquet

---

## PURPOSE

The MLB Weather Substrate is the canonical, single-grain weather observation
table for all modeled MLB games. It provides raw, pregame-safe weather inputs
(temperature, wind speed, wind direction) plus roof context (roof_status) at
one row per game_pk. It is a raw observation layer only — no derived interaction
features, no weather-performance multipliers.

---

## SOURCE + LINEAGE

Source table : sim/data/game_table.parquet
Rows in source: 9,902
Seasons covered: 2022, 2023, 2024, 2025, 2026
Build timestamp: 2026-04-15 14:23:10

Weather data provenance:
- Historical rows (2022–2025 completed season): Open-Meteo archive API, fetched
  at the game-start hour for the home venue location. Retroactive fetch but
  aligned to pregame conditions (the weather at first pitch, not mid-game).
- Live/forward rows (2026 in-season): Open-Meteo forecast API, fetched pregame.
  Genuine pregame data, no future leakage possible.
- Dome/retractable-roof rows: temperature=72, wind_speed=0, wind_direction=0
  by documented neutralization policy (indoor climate control assumed).

---

## FIELD INVENTORY + DISPOSITION

### IDENTITY (5 fields)
| Field      | Type    | Notes                         |
|------------|---------|-------------------------------|
| game_pk    | int64   | MLB Stats API primary key     |
| date       | object  | YYYY-MM-DD string             |
| season     | int64   | Calendar year                 |
| home_team  | object  | 3-letter team abbreviation    |
| away_team  | object  | 3-letter team abbreviation    |

### APPROVED WEATHER FEATURES (3 fields)
| Field         | Type    | Range          | Notes                              |
|---------------|---------|----------------|------------------------------------|
| temperature   | float64 | 27.4 – 111.9 F | Open-Meteo temp at game start      |
| wind_speed    | float64 | 0.0 – 32.9 mph | Open-Meteo wind at game start      |
| wind_direction| float64 | 0.0 – 360.0 deg| Meteorological degrees (0=N, 90=E) |

### CARRIED FIELD (1 field)
| Field       | Type   | Values                    | Notes                                        |
|-------------|--------|---------------------------|----------------------------------------------|
| roof_status | object | open/retractable/dome     | Redundant with park substrate; carried here  |
|             |        |                           | for weather-context joins and filtering      |

### EXCLUDED FIELDS (not present in source, would be excluded if added)
| Field                | Reason for Exclusion                                         |
|----------------------|--------------------------------------------------------------|
| wind_factor          | Derived: cosine projection × speed — not a raw observation  |
| wind_factor_effective| Derived + historically buggy implementation; downstream fix  |
|                      | pending in kp04_shadow.py; excluded until fixed and audited  |
| flyball_wind         | Interaction feature (flyball% × wind); belongs in feature    |
|                      | engineering layer, not raw weather substrate                 |

---

## GRAIN CHECK

- Grain: one row per game_pk (unique MLB Stats API game identifier)
- game_pk unique: TRUE (9,902 distinct values, 0 duplicates)
- Full-row duplicates: 0
- Row count matches source: TRUE (9,902 = 9,902)

---

## COVERAGE / NULL / VALUE CHECKS

### Null rates
All 9 columns: 0 nulls across all 9,902 rows and all seasons.

### Temperature
- Global range: 27.4°F – 111.9°F
- Global mean: 71.9°F, std: 9.9°F
- Extreme cold (<35°F): 4 games (CLE, DET, CHC 2025; CLE 2026) — all open-roof, plausible April dates
- Extreme hot (>105°F): 3 games (LAA, LAD Sep 2022; LAD Sep 2024) — California heat wave dates, plausible
- No implausible values detected

### Wind Speed
- Global range: 0.0 – 32.9 mph
- No negative values
- Zero-wind count: 2,318 (23.4%) — 2,316 are dome/retractable neutralized; 2 are open-air games
  with genuinely calm conditions (Open-Meteo returned 0.0 mph)
- Max wind (32.9 mph): COL vs TBR 2024-04-06, open-roof — Coors Field in April, plausible

### Wind Direction
- Encoding: meteorological degrees (0=North, clockwise)
- Range: 0–360 (full circle)
- 361 unique values
- 0-degree count: 2,316 (all dome/retractable neutralized rows)
- 360-degree count: 32 (due North, open-air, genuine)

### Roof Status
- dome: 327 games — all neutralized to (72°F, 0 mph, 0°): 100.0%
- retractable: 1,989 games — all neutralized to (72°F, 0 mph, 0°): 100.0%
- open: 7,586 games — 0 neutralized, real weather values

### Season Coverage
| Season | Games | Temp Mean | Wind Mean |
|--------|-------|-----------|-----------|
| 2022   | 2,430 | 72.4°F    | 6.8 mph   |
| 2023   | 2,430 | 71.4°F    | 6.5 mph   |
| 2024   | 2,427 | 72.4°F    | 6.6 mph   |
| 2025   | 2,428 | 72.0°F    | 5.3 mph   |
| 2026   |   187 | 63.2°F    | 6.5 mph   |
| TOTAL  | 9,902 | 71.9°F    | 6.3 mph   |

2026 temp mean (63.2°F) is lower than prior seasons as expected — early-season
games in northern stadiums before summer warmth.

---

## PIT-SAFETY VERDICT

PASS — All fields are pregame-safe:
- temperature, wind_speed, wind_direction: Open-Meteo readings at game-start
  hour. These reflect conditions at first pitch and are either fetched from
  historical archive (retroactive but aligned to gametime) or from forecast
  (genuinely pregame). No in-game or post-game weather contamination.
- roof_status: Static venue characteristic. Fully pregame-safe.
- No derived interaction features included (wind_factor, flyball_wind excluded).
- No actual game score or outcome fields carried into this substrate.
- Identity fields (game_pk, date, season, team names) are all pregame-known.

---

## CARRY-FORWARD NOTES

1. roof_status is redundant with the park substrate (already present there) but
   is carried here to make the weather substrate self-contained for filtering
   (e.g., "open-roof games only" without a join to park substrate).

2. wind_factor_effective is excluded pending a bug fix in mlb_sim/pipeline/kp04_shadow.py.
   Once the cosine projection formula is corrected and audited, it should be added
   to the FEATURE ENGINEERING layer, not to this raw substrate.

3. The 72°F / 0 mph neutralization policy for dome and retractable-roof venues
   is a documented modeling convention, not a measured value. Any downstream
   feature that uses temperature or wind for these venues will receive these
   neutral values. This is intentional and correct.

4. Open-Meteo historical archive fetches temperatures at the game-start UTC hour.
   For twilight doubleheaders, both games share the same game_start_hour weather
   snapshot (the first-game start). This is acceptable for totals modeling but
   should be noted for fine-grained park factor research.

5. This substrate contains no lagged or rolling weather features. Those belong
   in a weather feature engineering layer built on top of this substrate.
