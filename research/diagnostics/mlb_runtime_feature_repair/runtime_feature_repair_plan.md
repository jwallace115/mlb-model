# MLB Runtime Feature Repair Plan

## What Is Broken

### Feature Status Table

| Feature | Source | Status | Fallback | Severity |
|---------|--------|--------|----------|----------|
| **SP xFIP** | Savant 2025 xERA | STALE — prior season | Using 2025 values for all pitchers | MEDIUM — reasonable proxy early in season |
| **SP K%** | FanGraphs API | BROKEN — 403 | **None (NULL)** | **CRITICAL — feature missing entirely** |
| **SP BB%** | FanGraphs API | BROKEN — 403 | **None (NULL)** | **CRITICAL — feature missing entirely** |
| **SP avg_IP** | FanGraphs API | BROKEN — 403 | **None (NULL)** | MEDIUM — affects short-starter risk |
| **Team wRC+** | FanGraphs API | BROKEN — 403 | **100.0 for 28/30 teams** | **CRITICAL — no offensive differentiation** |
| SP CSW% | Per-start CSV (pybaseball) | **WORKING** but CSV file missing | 27.0 (league median) | MEDIUM — falls back to static |
| Bullpen fatigue | MLB Stats API (live) | **WORKING** | N/A | OK |
| Weather | Open-Meteo (live) | **WORKING** | N/A | OK |
| Umpire | Static UMPIRE_RATINGS | **WORKING** | N/A | OK |
| Park factors | Static config.py | **WORKING** | N/A | OK |

### Impact on Ridge Model

The Phase 9 Ridge model was trained with 25 features. Currently:
- **SP K% and BB% are NULL** → the model receives zeros or NaN for 2 of its 25 features
- **wRC+ is 100 for nearly all teams** → 2 features (home/away wRC+) carry zero information
- **xFIP is 2025 season-level** → reasonable early-season proxy but doesn't update game-by-game
- Effectively **4-6 of 25 features are broken or uninformative**

### Impact on Overlay Logic

| Overlay | Dependency | Status |
|---------|-----------|--------|
| **S12** | csw_pct (per-start CSV) + xFIP (Savant 2025) | **PARTIALLY WORKING** — but S12 columns not being saved to signal output (bug: SIGNAL_COLS doesn't include overlay fields) |
| **P09** | hard_hit_rate (Statcast 2025) + park_factor (static) | **WORKING with 2025 data** — same pitcher HH rates as training period |

**Critical S12/P09 bug:** The overlay code runs and modifies `sig["stake_units"]`, but the overlay columns (s12_overlay_active, p09_overlay_active, combined_overlay_tier) are dropped when the DataFrame is created because SIGNAL_COLS doesn't include them. The stake adjustment IS applied but the overlay metadata is lost.

### Are Today's Plays Trustworthy?

Today's 2 live plays:
- **KCR@ATL 0.625u UNDER** — p_under=0.597
- **ARI@LAD 1.25u UNDER** — p_under=0.607

These are based on:
- xFIP: 2025 season values (reasonable early-season proxy)
- wRC+: 100.0 for both teams in both games (NO offensive differentiation)
- K%/BB%: NULL (missing from Ridge input)
- Bullpen: LIVE (correct)
- Weather: LIVE (correct)

**Assessment: PARTIALLY TRUSTWORTHY.** The directional lean (UNDER) comes primarily from pitcher xFIP quality + weather/park, which are reasonable. But the confidence calibration is degraded because wRC+ and K%/BB% are missing. The 0.625u/1.25u sizing may not accurately reflect true edge.

The overlays (S12/P09) may be running but their output is not visible in the signal log.

---

## Replacement Sources (Local Data Only)

### For SP K% and BB%
**Immediate source: MLB Stats API boxscores (already used by bullpen module)**

The bullpen module already calls `_get_boxscore(game_pk)` for every recent game. Each boxscore contains pitcher K/BB/BF per start. We can extract K% = K/BF and BB% = BB/BF for starters and build rolling averages.

This is the SAME data source used by `research/opponent_adjusted_engine/pitcher_start_adjusted_metrics.parquet` — but that file only goes to 2025-09-28. The live boxscore API has 2026 data right now.

### For Team wRC+
**Immediate source: MLB Stats API team batting lines (from boxscores)**

Each boxscore has team batting totals: H, AB, 2B, 3B, HR, BB, K, totalBases. We can compute:
- team batting average = H/AB
- team SLG = totalBases/AB
- team OBP proxy = (H+BB+HBP) / (AB+BB+HBP)
- wRC+ proxy = (team_OBP × team_SLG_factor / league_avg) × 100

This gives team-level offensive differentiation from game 1 of 2026.

### For SP xFIP
**Current source (Savant 2025) is acceptable short-term.**

xFIP is a park-neutral metric that changes slowly. Using 2025 season values for the first 2-3 weeks of 2026 is standard practice — the market does the same thing. The Savant 2025 values are a reasonable proxy.

Longer-term: derive xFIP from per-start K%, BB%, FB% using the formula:
xFIP = ((13*(lgHR/lgFB)*FB - 2*K + 3*BB) / IP) + constant

### For CSW%
**The per-start CSV pipeline exists but the CSV file is missing.**

`refresh_daily_csw()` in `modules/pitchers.py` should create/append to the CSV. The function exists but the file doesn't. Likely needs an initial bootstrap run.

---

## Repair Plan

### Bucket A — Immediate Hotfix (today)

**A1. Fix wRC+ by computing from 2025 Savant batting xwOBA**

The Savant xwOBA endpoint for 2025 is available (confirmed: 711 pitchers loaded from Savant 2025). The team batting equivalent should also be available. The `_fetch_savant_team_offense()` function already exists but may be failing silently.

Fix: ensure the Savant team batting fallback (`_fetch_savant_team_offense(2025)`) actually runs and returns data when FanGraphs fails. If Savant 2025 works, all teams get 2025-season-level wRC+ (much better than 100.0 for everyone).

**A2. Fix SIGNAL_COLS to include overlay fields**

Add S12/P09 overlay columns to SIGNAL_COLS so they're preserved in the parquet and JSON exports:
```python
SIGNAL_COLS = [
    ...,  # existing columns
    "s12_overlay_active", "s12_value",
    "p09_overlay_active", "p09_value", "p09_data_available",
    "combined_overlay_tier", "base_stake", "final_stake",
]
```

**A3. Bootstrap K% and BB% from 2025 Savant pitcher data**

The Savant pitcher endpoint already loads 711 pitchers with xERA. Check if the same endpoint also provides K% and BB%. If so, extract them. If not, compute from the pitcher start boxscores (already cached in sim/data/cache/boxscores/).

### Bucket B — Near-Term Robust Replacement (this week)

**B1. Build live boxscore-derived pitcher feature refresh**

Create a function that runs daily after games complete:
1. Pull boxscores for yesterday's games from MLB Stats API
2. Extract starter K/BB/BF/IP per start
3. Compute rolling K%, BB%, ERA for each pitcher (last 5 starts)
4. Store in a lightweight JSON/parquet lookup
5. Use this lookup in `build_pitcher_db()` when FanGraphs fails

This replaces the FanGraphs dependency for K% and BB% entirely.

**B2. Build live boxscore-derived team offense refresh**

Same approach for teams:
1. Pull team batting from yesterday's boxscores
2. Compute rolling H/AB, OBP, SLG, runs/game (last 20 games)
3. Derive wRC+ proxy
4. Use this when FanGraphs/Savant fail

**B3. Bootstrap the CSW per-start CSV**

Run `refresh_daily_csw()` for the first 2026 game dates to create the CSV file. Then the daily 7AM refresh will keep it current.

### Bucket C — Longer-Term Architecture (next 2 weeks)

**C1. Remove FanGraphs API dependency entirely**

FanGraphs has been intermittently returning 403 since early 2025. Build a fully local feature pipeline:
- SP features from boxscore + Statcast per-start (already have the code)
- Team offense from boxscore team batting (already have the code)
- CSW from pybaseball daily refresh (already exists)

**C2. Build incremental feature table**

Instead of rebuilding from scratch each morning, append yesterday's game data to a running feature store. This gives the Ridge model truly current rolling-window features.

**C3. Add feature quality monitoring**

Log which features are NULL or defaulted at inference time. Alert if >3 features are missing.

---

## What Should Be Fixed First

**Priority 1 (today): A1 — Fix wRC+ fallback**
This is the highest-impact fix. Going from 100.0 for all teams to 2025 season values restores offensive differentiation. The code path exists (`_fetch_savant_team_offense`) but may be failing.

**Priority 2 (today): A2 — Fix SIGNAL_COLS**
Without this, S12/P09 overlay data is lost from the signal log. Simple addition of column names.

**Priority 3 (this week): B1 — Boxscore-derived pitcher K%/BB%**
Restores the two most critical missing features. Uses MLB Stats API already proven to work.

---

## Should Today's Overlay Signals Be Trusted?

| Question | Answer |
|----------|--------|
| Are S12/P09 overlays running? | YES — code executes, adjusts stakes |
| Are overlay cutoffs applied against stale inputs? | PARTIALLY — S12 uses 2025 xFIP (stale) + CSW (working). P09 uses 2025 HH rates (stale) + park factor (correct). |
| Are overlay columns in the signal log? | **NO** — columns dropped by SIGNAL_COLS bug |
| Is the 1.25u play trustworthy? | **MODERATELY** — if overlay boosted to 1.25u, the boost logic ran correctly against 2025 data. The directional UNDER lean is reasonable. The sizing confidence is approximate. |
| Should we halt live plays? | **NO** — the model degradation is real but not catastrophic. 2025 xFIP is a reasonable early-season proxy. The main risk is wRC+=100 missing team differentiation, which affects edge calibration but not direction. |

**Bottom line: today's plays are directionally reasonable but sizing confidence is reduced. Fix wRC+ first.**
