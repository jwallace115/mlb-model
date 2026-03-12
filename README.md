# MLB Totals Model

A data-driven MLB over/under projection system with a Streamlit dashboard deployed on Streamlit Cloud.

## How It Works

```
Local machine (each morning)          Streamlit Cloud (always on)
──────────────────────────────        ────────────────────────────
python push_results.py                reads results.json from GitHub
  └─ runs full model pipeline         renders card-based dashboard
  └─ serializes output → results.json
  └─ git push → GitHub
```

The model runs locally where it has access to live APIs and a local SQLite database. The dashboard is a static viewer — it reads the pre-built `results.json` that gets pushed to GitHub each morning.

## Model Components

| Module | Description |
|--------|-------------|
| `modules/schedule.py` | Fetches today's games from MLB Stats API |
| `modules/pitchers.py` | Starting pitcher xFIP/SIERA from pybaseball (Statcast) |
| `modules/offense.py` | Team wRC+ from Baseball Reference |
| `modules/weather.py` | Game-time weather from Open-Meteo |
| `modules/bullpen.py` | Bullpen fatigue from recent game logs |
| `modules/umpires.py` | Umpire over/under tendencies |
| `modules/projections.py` | Combines factors into total projection + confidence |
| `modules/odds.py` | Market lines from The Odds API |
| `run_model.py` | Main pipeline — runs all modules, prints card |
| `push_results.py` | Runs model + serializes output + git pushes |
| `dashboard.py` | Streamlit dashboard (reads results.json only) |
| `db.py` | SQLite persistence — projections, results, season record |

## Local Setup

```bash
# 1. Clone the repo
git clone https://github.com/jwallace115/mlb-model
cd mlb-model

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set your Odds API key
cp .env.example .env
# edit .env and paste your key from https://the-odds-api.com

# 4. Run the model (prints to terminal)
python run_model.py

# 5. Run model + push results to dashboard
python push_results.py
```

## Daily Workflow

```bash
# Each morning during the season:
python push_results.py
```

This runs the full model, writes `results.json`, commits it, and pushes to GitHub. Streamlit Cloud picks up the new file automatically.

Options:
```bash
python push_results.py --no-push    # run model + save JSON locally, don't push
python push_results.py --no-odds    # skip Odds API (model only, no lines/edges)
python push_results.py --date 2025-04-15  # run for a specific date
```

## Dashboard (local)

```bash
streamlit run dashboard.py
```

## Deploying to Streamlit Cloud

1. Push this repo to GitHub (public or private)
2. Go to [share.streamlit.io](https://share.streamlit.io) → New app
3. Select `jwallace115/mlb-model` → branch `main` → file `dashboard.py`
4. No secrets required — the dashboard reads `results.json` from the repo

## API Keys

- **The Odds API** (`ODDS_API_KEY`): Required for market lines/edges. Get a free key at [the-odds-api.com](https://the-odds-api.com). Free tier: ~500 requests/month. Goes in your local `.env` file — never committed.
- **Streamlit Cloud**: No secrets needed. The dashboard is read-only and doesn't call any APIs.

## Data Sources

- MLB Stats API (schedule, rosters) — free, no key
- [pybaseball](https://github.com/jldbc/pybaseball) → Baseball Reference / FanGraphs (pitcher/offense stats)
- [Open-Meteo](https://open-meteo.com) (weather) — free, no key
- [The Odds API](https://the-odds-api.com) (market lines) — free tier

## Output Format

Each game card shows:
- Star rating: ⭐⭐⭐ strong play / ⭐⭐ play / ⭐ lean / NO PLAY
- Lean: OVER or UNDER
- Projected total (full game + first 5 innings)
- Market line + edge vs projection
- Natural language summary of key factors (pitching, weather, park, offense, bullpen, umpire)
- Suggested parlay from top 2–3 plays
