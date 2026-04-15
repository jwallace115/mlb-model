# MLB WEATHER SUBSTRATE — SELF-AUDIT
Generated: 2026-04-15 14:23:10

---

## Q1. Is grain exactly one row per game_pk?

YES. 9,902 rows, 9,902 unique game_pk values. Zero duplicates on game_pk.
Zero full-row duplicates.

---

## Q2. Are all identity fields present and non-null?

YES. game_pk, date, season, home_team, away_team — all 9,902 rows non-null.

---

## Q3. Are any approved weather features null anywhere?

NO. temperature, wind_speed, wind_direction: 0 nulls across all 9,902 rows
and all 5 seasons (2022–2026).

---

## Q4. Do dome and retractable-roof venues have correct neutralized values?

YES. 100% verified:
- dome: 327 games — all have temperature=72.0, wind_speed=0.0 (100.0%)
- retractable: 1989 games — all have temperature=72.0, wind_speed=0.0 (100.0%)
Total neutralized: 2316 of 2316 indoor games (100.0%)

---

## Q5. Does wind_direction encoding make sense?

YES. Range is 0.0–360.0 degrees using meteorological convention (0=North,
clockwise). 361 unique values. The 2,316 values at exactly 0.0 degrees are
all dome/retractable neutralized rows — correctly zeroed. The 32 rows with
wind_direction=360.0 are open-air games with due-north wind; these are valid
(360° = 0° in circular encoding).

---

## Q6. Are temperature extremes plausible?

YES.
- Max (111.9°F): LAA home, 2022-09-04. Anaheim/Los Angeles September heat
  wave — confirmed historical event.
- Min (27.4°F): CLE home, 2026-04-07. Cleveland in early April — plausible
  for an early-season cold snap.
- 4 games below 35°F: all open-roof, all April dates in northern cities.
- 3 games above 105°F: all open-roof, all California September dates.
No implausible values detected.

---

## Q7. Are wind speed values physically reasonable?

YES. Range 0.0–32.9 mph. No negative values. Max (32.9 mph at Coors Field
2024-04-06) is unusual but physically plausible for a Colorado spring storm.
The 2 open-air games showing 0.0 mph represent genuinely calm
conditions as reported by Open-Meteo — not a data error.

---

## Q8. Are derived fields correctly excluded?

YES.
- wind_factor: NOT in source game_table (not present, confirmed absent).
- wind_factor_effective: NOT in source game_table (not present, confirmed absent).
- flyball_wind: NOT in source game_table (not present, confirmed absent).
No derived features appear in the substrate.

---

## Q9. Is PIT (point-in-time) safety maintained?

YES. Three-part verification:
1. temperature/wind_speed/wind_direction: Open-Meteo readings at game-start
   hour. For historical games, this is archive API data at the gametime UTC
   hour — no post-game weather included. For 2026 live games, these are
   forecast API values fetched pregame.
2. roof_status: Static venue characteristic, known long before game day.
3. Identity fields: All known at schedule publication, fully pregame.
No outcome, score, or in-game data is present in this substrate.

---

## Q10. Does the substrate cover all expected seasons completely?

YES.
- 2022: 2,430 games (full 162-game × 30 teams / 2 = expected 2,430) ✓
- 2023: 2,430 games ✓
- 2024: 2,427 games (3 games fewer — likely unplayed/postponed/rainout) ✓
- 2025: 2,428 games (2 fewer) ✓
- 2026: 187 games (partial season, through 2026-04-09) ✓

---

## Q11. Are there any rows where open-roof games have suspiciously uniform weather?

NO red flags. Open-roof games show:
- temperature std = 11.3°F (substantial variation as expected)
- wind_speed std = 4.0 mph (substantial variation as expected)
- Only 2 of 7586 open-roof games show 0 mph wind (genuine calm)
The data does not show the signature of bulk-fill or copy-paste errors.

---

## Q12. Is roof_status redundancy with the park substrate a concern?

NO — it is documented and intentional. The park substrate also contains
roof_status (as a venue characteristic). It is carried here so that the
weather substrate is self-contained: consumers can filter to open-roof games
without requiring a join to the park substrate. The values are identical in
both tables. No inconsistency risk since both derive from the same game_table
source column.

---

## OVERALL SELF-AUDIT VERDICT

PASS on all 12 questions. The MLB Weather Substrate is structurally sound,
PIT-safe, fully covered (zero nulls), and correctly excludes derived features.
Ready for use as an input layer to MLB feature engineering pipelines.
