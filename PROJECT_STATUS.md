# MLB Totals Model — Project Status
**Last updated:** 2026-03-12
**Sessions completed:** 3

---

## What This Is

A fully automated MLB run-totals betting model that runs daily, pulls live data
from free APIs, projects game totals using a weighted factor model, compares
projections to market lines (DraftKings/FanDuel), and outputs a daily card with
star-rated plays, natural language summaries, and a parlay suggestion.

Two output modes:
- **Terminal:** `python3 run_model.py`
- **Browser dashboard:** `streamlit run dashboard.py`

---

## File Structure

```
mlb-model/
├── run_model.py          ← Main daily runner + all output logic
├── dashboard.py          ← Streamlit browser dashboard (NEW)
├── refresh.py            ← Pre-game refresh (~90 min before first pitch)
├── results_tracker.py    ← Logs final scores, computes W/L record
├── setup_launchd.py      ← Sets up Mac automation (run once)
├── config.py             ← All weights, stadium data, API keys, constants
├── db.py                 ← SQLite read/write layer
├── requirements.txt      ← pip dependencies
│
├── modules/
│   ├── schedule.py       ← MLB Stats API: games, pitchers, umpires
│   ├── pitchers.py       ← FanGraphs xFIP/SIERA + Savant xERA fallback
│   ├── offense.py        ← FanGraphs wRC+ (PA-weighted by team)
│   ├── weather.py        ← Open-Meteo API: wind factor, temp factor
│   ├── bullpen.py        ← Reliever innings logged in last 2 days
│   ├── umpires.py        ← Static umpire runs_factor ratings (~50 umps)
│   ├── projections.py    ← Core engine: combines all factors into totals
│   └── odds.py           ← The Odds API: DK/FD lines, edge calculation
│
├── data/
│   ├── mlb_model.db      ← SQLite database (projections + results tables)
│   └── cache/            ← Daily JSON caches (pitchers, offense, odds)
│
└── logs/                 ← Daily run logs + launchd stdout/stderr
```

---

## Data Sources (All Free)

| Source | What We Pull | Module |
|---|---|---|
| MLB Stats API | Schedule, probable pitchers, umpires, boxscores | schedule.py, bullpen.py |
| FanGraphs API | xFIP, SIERA per pitcher; wRC+ per batter | pitchers.py, offense.py |
| Baseball Savant | xERA, xwOBA (fallback when FanGraphs 403s) | pitchers.py, offense.py |
| Open-Meteo | Hourly wind + temp forecast at stadium coordinates | weather.py |
| The Odds API | DraftKings + FanDuel totals lines + F5 lines | odds.py |

**API keys in config.py:**
- `ODDS_API_KEY = "c4c1933ac34bb48b7a4f26a04e1cd94f"` (~500 req/month free tier)
- All other APIs: free, no key required

---

## Projection Model

### Formula
```
runs = base_runs × sp_factor × offense_factor × park_factor
                 × weather_factor × umpire_factor × bullpen_factor
```

### Weights (`config.py`)
```python
MODEL_WEIGHTS = {
    "sp_quality": 0.35,   # Starting pitcher xFIP/SIERA blend
    "offense":    0.30,   # Team wRC+
    "park":       0.15,   # Park factor (normalized to 1.0)
    "weather":    0.08,   # Wind direction × speed + temperature
    "umpire":     0.07,   # Umpire runs_factor
    "bullpen":    0.05,   # Reliever fatigue multiplier
}
```

### F5 Weights (bullpen irrelevant, redistributed)
```python
F5_WEIGHTS = {"sp_quality": 0.40, "offense": 0.32, "park": 0.14,
              "weather": 0.08, "umpire": 0.06, "bullpen": 0.00}
```

### Key Constants
- `LEAGUE_AVG_RUNS_PER_TEAM = 4.50` (2024 MLB average)
- `F5_RUN_FRACTION = 0.56` (starter allows ~56% of game runs in 5 inn)
- `EDGE_MIN_RUNS = 0.5` (minimum proj vs line gap to flag as value)

---

## Output Format

### Terminal Card (`python3 run_model.py`)

```
⭐⭐⭐       MIL @ CLE  ·  06:05 PM MST (09:05 PM ET)  ·  33°F  ·  Wind 16mph R to L
          UNDER  Proj 7.7  ·  No line yet  │  F5: 4.3
          Cold conditions at first pitch (33°F) are the primary drag on
          scoring ... model still leans under.
```

**Ratings:**
- `⭐⭐⭐` = HIGH confidence + strong edge (or high score without line)
- `⭐⭐` = MEDIUM confidence + edge ≥ 0.5, or HIGH + edge ≥ 0.3
- `⭐` = some edge, lower conviction
- `NO PLAY` = NEUTRAL lean, conflicting factors, or thin edge

**Natural language summary logic:**
1. Sentence 1: strongest factor (ranked by deviation from 1.0 baseline)
2. Sentence 2: aligned supporting factors; if a factor opposes the lean, generates "X — but Y outweighs that, model still leans under"
3. Sentence 3: edge vs line, or "watch when odds post" if no line

### Dashboard (`streamlit run dashboard.py`)
- Same data, card-based browser UI
- Green left border = ⭐⭐⭐, yellow = ⭐⭐, gray = ⭐
- No-plays collapsed in expander
- Parlay card highlighted in indigo
- Auto-refreshes every 5 minutes via JS

---

## Automation (Mac launchd)

Three jobs loaded in `~/Library/LaunchAgents/`:

| Job | Time | Command |
|---|---|---|
| `com.mlbmodel.daily` | 7:00 AM | `python3 run_model.py` |
| `com.mlbmodel.refresh` | 11:00 AM | `python3 refresh.py` |
| `com.mlbmodel.results` | 11:30 PM | `python3 results_tracker.py` |

Logs: `~/mlb-model/logs/com.mlbmodel.*.stdout.log`

---

## Database Schema

```sql
-- projections: one row per game per date (upserted on re-run)
CREATE TABLE projections (
    game_date, game_pk, home_team, away_team,
    home_sp, away_sp, home_sp_xfip, away_sp_xfip, home_sp_siera, away_sp_siera,
    home_wrc_plus, away_wrc_plus, park_factor,
    wind_speed, wind_direction, temperature,
    umpire_name, umpire_factor,
    home_bp_fatigue, away_bp_fatigue,
    proj_total_full, proj_total_f5, confidence, confidence_score,
    factors_json, created_at
);

-- results: filled in by results_tracker.py after games complete
CREATE TABLE results (
    projection_id, game_date, game_pk, home_team, away_team,
    actual_total, actual_f5_total, line_full, line_f5,
    result_full, result_f5, updated_at
);
```

**Current state (2026-03-12):** 25 projections stored, 0 results (Spring Training — no lines posted yet so W/L tracking hasn't started)

---

## What's Working

- [x] Full daily projection pipeline end-to-end
- [x] All 30 stadiums with park factors, lat/lon, CF bearing for wind calc
- [x] FanGraphs pitcher data (xFIP, SIERA) with Savant xERA fallback
- [x] FanGraphs team wRC+ (PA-weighted from individual batter data)
- [x] Open-Meteo weather with correct stadium coordinates and game-time hour
- [x] Bullpen fatigue from last 2 days of MLB Stats API boxscores
- [x] ~50 umpire tendency ratings
- [x] The Odds API integration (DK + FD totals + F5 lines, cached daily)
- [x] Edge calculation and value identification
- [x] Star rating classification (⭐⭐⭐ / ⭐⭐ / ⭐ / NO PLAY)
- [x] Natural language summaries with factor-driven content
- [x] Counter-factor "outweigh" sentences when a factor opposes the lean
- [x] Per-game weather inline on card header (temp always, wind if ≥5mph)
- [x] Local stadium timezone display with ET in parentheses
  - Arizona venues: MST (no DST), correctly detected by venue keyword
  - Florida ST venues: EDT, correctly overrides team's home timezone
  - Regular season: auto from home team IANA timezone via `zoneinfo`
- [x] Pre-game refresh script (SP changes, weather shifts, total movement)
- [x] Results tracker (logs final scores, computes W/L)
- [x] Mac launchd automation (3 jobs)
- [x] SQLite results database
- [x] Streamlit browser dashboard with auto-refresh

---

## Known Limitations / Things to Watch

1. **Pre-season data:** FanGraphs returns 403 before the season starts (no
   current-year stats). Savant xERA fallback kicks in. Once the season begins
   (~late March), FanGraphs data will populate and model accuracy should
   improve significantly.

2. **Spring Training lines:** The Odds API may not offer lines for ST games.
   Odds module handles 422 responses gracefully; all ST projections show
   "No line yet" which is expected.

3. **Umpire data:** Assignments are often not posted until day-of. If no umpire
   is listed, the model uses a neutral factor (1.0). The pre-game refresh at
   11am catches confirmed assignments.

4. **Oakland/Athletics:** Team moved to Las Vegas. Config has `"OAK"` still
   mapped. If they formally rebrand/relocate mid-season, update `config.py`
   STADIUMS and TEAM_ID_TO_ABB.

5. **The Odds API quota:** ~500 requests/month on free tier. Caching per day
   means 2 requests/day (full + F5 market) = ~60/month. Plenty of headroom.

---

## Planned Next Steps

### High Priority
- [ ] **Backtest against 2024/2025 results** — pull historical game totals and
  lines, run the model on past data, measure actual O/U accuracy by confidence
  tier (HIGH/MEDIUM/LOW) and star rating
- [ ] **Unit tests for projection engine** — verify xFIP-to-factor math,
  park factor normalization, wind vector calculation
- [ ] **Season opener calibration** — when MLB regular season starts (~late
  March 2026), re-run and verify FanGraphs data is loading correctly, adjust
  weights if early results skew

### Medium Priority
- [ ] **Line movement tracking** — store market lines at time of projection
  AND at game time (via results_tracker), flag when line moves significantly
  from our projection
- [ ] **Alternate lines** — consider ½-run alt totals when edge is 0.3–0.5
  (currently below the 0.5 threshold for a play)
- [ ] **Dashboard date picker** — allow viewing any past date's card in the
  browser UI
- [ ] **Dashboard results tab** — show recent W/L history per day in the
  browser, not just the current day's projections

### Lower Priority
- [ ] **Team-specific park factors** — current factors are fixed 2024 values;
  could pull live 2026 rolling park factors as the season progresses
- [ ] **Starter IP depth** — adjust F5 projection based on starter's average
  innings pitched (some aces go 7+, some go 5); currently uses a flat 5.5
  inning assumption
- [ ] **Platoon splits** — wRC+ vs LHP vs RHP; relevant when a team faces an
  extreme same-handed starter

---

## Exact Next Steps for Next Session

1. **Wait for regular season** (~March 27 opener) and run:
   ```bash
   python3 run_model.py 2>/dev/null
   ```
   Verify FanGraphs data loads (no more 403 fallbacks), lines are posted,
   and edge calculations are working.

2. **First results check** (day after opener):
   ```bash
   python3 results_tracker.py
   ```
   Confirm actual scores log correctly and W/L updates in the DB.

3. **If lines are not matching games** — check `ODDS_API_TEAM_MAP` in
   `config.py` for any team name mismatches; add aliases as needed.

4. **Backtest setup** — create `backtest.py` that accepts a date range,
   replays the projection logic on historical data from `db.get_recent_projections()`,
   and outputs accuracy by confidence tier.

5. **Dashboard date picker** — add a `st.date_input` to `dashboard.py` to
   allow browsing past projections from the DB.

---

## How to Run

```bash
# Daily card (terminal)
cd ~/mlb-model
python3 run_model.py 2>/dev/null

# Browser dashboard
streamlit run dashboard.py

# Pre-game refresh (run ~90 min before first pitch)
python3 refresh.py

# Log final scores after games complete
python3 results_tracker.py

# Skip Odds API (saves quota)
python3 run_model.py --no-odds

# Specific date
python3 run_model.py 2026-04-01
```

---

## Key Config Touchpoints

To re-tune the model, edit `config.py`:

```python
# Adjust these weights as season data accumulates
MODEL_WEIGHTS = { "sp_quality": 0.35, "offense": 0.30, ... }

# Raise/lower to change what counts as a "value play"
EDGE_MIN_RUNS = 0.5

# Update park factors mid-season if run environments shift
STADIUMS = { "COL": {"park_factor": 117, ...}, ... }
```
