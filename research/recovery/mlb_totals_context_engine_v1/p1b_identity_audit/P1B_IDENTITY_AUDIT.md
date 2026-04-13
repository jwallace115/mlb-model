# P1B IDENTITY AUDIT
## mlb_p1b_coldwarm_earlyheavy_over_v1

**Audit date:** 2026-04-13  
**Auditor:** Inspection-only — no code changes, no testing, no activation  
**Status statement:** P1B remains SHADOW ONLY. This audit documents the current implementation and its identity implications only. No signals have been tested, no pipeline changes have been made, and no decision-time variants have been frozen.

---

## 1. Audit Scope

This audit inspects the P1B cold-warm EARLY_HEAVY over signal as currently deployed in shadow mode. It covers:
- Implementation footprint (all files that reference p1b, coldwarm, or EARLY_HEAVY)
- Temperature field identity (source, semantics, parity monitoring)
- Price gate identity (field, source, timing relative to decision windows)
- Object-identity implications for DT0700/DT1000/DT1200 decision-time variants
- Frozen vs unresolved dimensions
- Readiness verdict for decision-time evaluation

This audit does NOT test the signal, backtest performance, or propose any modifications.

---

## 2. Implementation Footprint

### Primary script
- `mlb/pipeline/mlb_totals_p1b_shadow.py` (18,498 bytes, last modified 2026-04-13 01:08)
- `object_id`: `mlb_p1b_coldwarm_earlyheavy_over_v1`
- `ruleset_version`: `frozen_v1`

### Tracker log
- `mlb/logs/mlb_p1b_coldwarm_earlyheavy_over_shadow_2026.json` (137 bytes)
- Current state: 0 signals recorded (season starts June 2026; April is outside month window)

### Supporting data paths (referenced in script)
- `mlb_sim_f5/data/f5_lines_2026.parquet` — F5 total lines (438 rows as of audit date)
- `mlb_sim/data/line_snapshots_2026.json` — FG line snapshots (630 snapshots, labels: OPEN/2AM/5PM/CLOSING)
- `data/cache/odds_full_{date}.json` — fallback Odds API cache

### Cron schedule (crontab)
- **Signal generation:** `20 15 * * *` → 15:20 UTC (11:20 AM ET) daily
- **Grading:** `10 6 * * *` → 06:10 UTC (2:10 AM ET) daily

### Dashboard reference
- `dashboard.py` lines 412–427: loads P1B tracker for display; read-only reference

### Upstream research files
- `research/recovery/mlb_totals_p1b_shadow_deploy/` — deployment spec and exec summary
- `research/recovery/mlb_totals_p1b_coldwarm_child/` — original thesis and build script
- `research/recovery/mlb_totals_p1_fg_f5_path_engine/` — parent P1 engine docs
- `research/recovery/mlb_totals_p1_hardening/` — hardening phase docs

---

## 3. Temperature Identity

### Field name
`forecast_temp_f` — stored per signal in the tracker JSON

### Source
Open-Meteo hourly forecast API (`api.open-meteo.com/v1/forecast`), via `modules/weather.py::fetch_weather()`.

### Fetch semantics
- The script calls `fetch_weather(home_team, game_time_et)` for each qualifying game at **signal-generation time** (11:20 AM ET when run via cron).
- `fetch_weather` makes a **live API call** to Open-Meteo at run time — it is NOT read from a pre-cached file.
- Open-Meteo returns an hourly forecast array with `timezone=auto` (stadium local time).
- The function targets the **game's local start hour** (e.g., 19:00 for a 7:05 PM game) on **today's ET date**.
- The returned `temperature_f` is therefore: **the Open-Meteo forecast for the game's first-pitch hour, as of the time the script runs (11:20 AM ET).**

### Forecast vs realized
- There is **no parity monitor** comparing forecast-at-signal-time to realized temperature at first pitch. The tracker JSON stores `weather_timestamp` (the UTC time the forecast was fetched) but does not store any post-game verification.
- Open-Meteo accuracy over a ~7-hour window (11:20 AM → 7:05 PM ET) is generally high for temperature, but no audit trail exists.

### Decision-time temperature implications
- At DT0700 (07:00 ET): forecast would be fetched ~4–7 hours earlier than first pitch. Open-Meteo 7-hour-ahead temperature forecasts are stable for most conditions but are NOT identical to the 11:20 AM forecast.
- The temperature object at DT0700 would need a separate fetch — it cannot reuse the 11:20 AM result without introducing a timing inconsistency.
- **Temperature is NOT currently decision-time compatible across DT windows without per-window fetching.**

### Dome exclusion
- `fetch_weather` returns `is_dome=True` for dome stadiums; the script skips these games entirely. This is consistent across all run times.

---

## 4. Price Gate Identity

### Field name
`over_price` — the full-game over vig, integer (e.g., -105, -110)

### Gate rule
`over_price <= -105` (OVER_PRICE_MAX = -105 constant in script)

### Source hierarchy
The `load_fg_lines()` function uses a **two-source hierarchy**:

**Primary: `mlb_sim/data/line_snapshots_2026.json`**
- If this file exists and contains entries for the target date, the function selects the **latest `snapshot_time`** entry per home team.
- Snapshot labels in file: `OPEN` (UTC 00–06), `2AM` (UTC 00–06), `5PM` (UTC 17), `CLOSING` (UTC 17)

**Fallback: `data/cache/odds_full_{date}.json`**
- Used only if no snapshots are found for the date.

### Price timing at the 15:20 UTC cron run
- At 15:20 UTC (11:20 AM ET), the snapshots available in `line_snapshots_2026.json` are:
  - `OPEN` (captured UTC ~03–06) — yes
  - `2AM` (captured UTC 00–06) — yes
  - `5PM` (captured UTC 17) — **NOT YET AVAILABLE** at 15:20 UTC
  - `CLOSING` (captured UTC 17) — **NOT YET AVAILABLE** at 15:20 UTC
- Therefore: the price used at the 15:20 UTC run is the **2AM ET snapshot** (the most recent available), **not** the closing line or the 5PM line.
- This means `over_price` at signal-generation time represents the **~2AM ET line**, approximately 9–17 hours before first pitch for typical evening games.

### Intraday decision panel coverage
The panel `mlb_intraday_decision_panel_v1_2022_2025.parquet` (9,715 rows) contains:
- `dt_0700_selected_over_price`: 9,303 / 9,715 non-null (95.8%)
- `dt_1000_selected_over_price`: 9,578 / 9,715 non-null (98.6%)
- `dt_1200_selected_over_price`: 9,676 / 9,715 non-null (99.6%)

All three DT windows have over_price fields. The panel does NOT contain a temperature field — temperature is absent from the historical decision panel entirely.

### Price identity at each decision time
- **DT0700 (07:00 ET):** A 07:00 ET run would use the 2AM snapshot (same as 11:20 AM) since the 5PM snapshot is not available. The price identity is **equivalent** to the current 11:20 AM run if the line has not moved between 2AM and 7AM. Line movement between these windows is possible but typically small for totals.
- **DT1000 (10:00 ET):** Same as DT0700 — would still use 2AM snapshot. Equivalent price identity.
- **DT1200 (12:00 PM ET):** Same as DT0700/DT1000 unless an intraday snapshot is added at ~UTC 15–16. Currently equivalent.
- **Final close:** Would use the 5PM/CLOSING snapshot, which is a materially different price (could be -110 or -120 vs -105 at 2AM).

**Key finding:** The price gate in backtest research should be verified against which snapshot time was used. If the original research used closing prices (-110, -120), and the live deployment uses 2AM prices (-105, -110), there is a price definition mismatch that could affect signal rate and edge calculations.

---

## 5. Object-Identity Implications

### Would DT0700/DT1000/DT1200 require new objects?

**Temperature: YES — new object required**
The current implementation fetches a live Open-Meteo forecast at run time. A DT0700 variant would fetch a forecast ~12 hours before first pitch vs ~8 hours before for DT1200. These are semantically distinct temperature measurements. A DT decision-time variant must either:
(a) Store the temperature forecast fetched at each DT window (new fetch per window), or
(b) Accept that temperature is constant across windows (using a single 11:20 AM fetch for all variants, which is operationally simple but not truly DT-labeled).

**Price: AMBIGUOUS — depends on snapshot timing**
The current snapshot infrastructure delivers prices at OPEN (~2AM), 2AM, 5PM, and CLOSING. For DT0700, DT1000, and DT1200 variants, the available price is the 2AM snapshot in all three cases (5PM not yet available). The panel has per-DT price fields, but these likely reflect the same 2AM snapshot for morning decision times. A DT1200-close variant using the 5PM snapshot would be a distinct object.

**F5 ratio: likely stable across DT windows**
F5 lines typically do not move significantly between 2AM and noon. The `f5_lines_2026.parquet` file has a single canonical row per game — there is no per-DT-window F5 snapshot. A multi-window evaluation would need to determine whether F5 line movement is material to the gate.

**Park set and month gate: fully frozen, DT-invariant**
These are deterministic at the game level and do not vary by decision time.

---

## 6. Frozen vs Unresolved

### Frozen (7 items)
1. Object ID: `mlb_p1b_coldwarm_earlyheavy_over_v1`
2. Ruleset version: `frozen_v1`
3. Park set: 18 cold-climate outdoor parks (hardcoded set)
4. Month window: June–September (months 6–9)
5. F5 ratio threshold: > 0.5625
6. Over price gate: <= -105
7. Temperature threshold: >= 75.0 F

### Unresolved (5 items)
1. **Temperature DT semantics:** No decision-time temperature snapshots exist. Open-Meteo fetches are live-at-run-time only. A DT0700 temperature is semantically different from a DT1200 temperature.
2. **Price source alignment:** Whether research validation used 2AM prices, 5PM prices, or closing prices is undocumented in the audit trail. The live deployment uses 2AM prices. This must be verified before DT variant design.
3. **Parity monitor (temperature):** No mechanism exists to compare forecast_temp_f at signal time to realized first-pitch temperature. Forecast accuracy is assumed but unmeasured.
4. **F5 line DT snapshots:** The f5_lines parquet has one canonical row per game. Multi-window backtesting requires per-DT F5 line availability, which does not currently exist in the panel.
5. **Panel temperature absence:** The intraday_decision_panel_v1 has no temperature column. Temperature cannot be applied to panel-based backtests without an enrichment step.

---

## 7. Readiness Verdict

**P1B is NOT ready for decision-time evaluation.**

Blockers:
- Temperature has no DT-labeled historical values in the decision panel
- Price source alignment between research validation and live deployment is unverified
- No parity monitor exists for forecast vs realized temperature
- F5 line DT snapshots are not available

Pre-conditions required before DT variant design:
1. Confirm which price snapshot (2AM vs closing) was used in original P1B research validation
2. Enrich the intraday_decision_panel_v1 with temperature at each DT window (or accept that temperature uses a single daily fetch)
3. Document whether DT variants should use the same 2AM price for all windows or introduce a per-window price capture
4. Decide whether a parity monitor is required before freeze

---

## 8. Status Statement

P1B remains SHADOW ONLY. This audit documents the current implementation and its identity implications only. No signals have been tested, no pipeline changes have been made, and no decision-time variants have been frozen.
