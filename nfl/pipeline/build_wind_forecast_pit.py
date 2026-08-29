#!/usr/bin/env python3
"""
NFL PIT-SAFE WIND — rebuild the wind feature from ARCHIVED FORECASTS, not observations.

WHY THIS EXISTS
---------------
`nfl/build_canonical.py` sources wind from (a) nflreadpy's reported game conditions and
(b) Open-Meteo's ARCHIVE api (observed actuals). Both are what the wind *was*, not what
was *forecast*. Any signal built on them fails Check 1a — the information was not
available at bet time.

Measured on that (unbettable) observed wind, the market underprices wind ~4x:
    book moves the total  -0.053 pts/mph
    true effect           -0.216 pts/mph
    unpriced residual     -0.163 pts/mph   (t=-2.20, N=1,168, survives controls)

WHAT THIS SCRIPT DOES
---------------------
The Previous Runs API archive only reaches back to ~Jan 2024 for most models, so a full
2019-2024 forecast rebuild is impossible. Instead this uses the 2024 season as a
CALIBRATION SAMPLE:

  1. pull wind forecasts at 24h / 48h / 72h lead for every 2024 outdoor game
  2. measure real forecast error vs the observed wind already in the canonical
  3. apply the errors-in-variables correction to the full 1,168-game slope
     to get the BETTABLE effect size

Estimating forecast error needs far less data than estimating ROI, which is why 187
games is enough for step 2 but would be useless for a backtest.

COST: free. Open-Meteo needs no API key for non-commercial use.
RUNTIME: ~22 API calls, one per outdoor stadium. Under 2 minutes.

    python3 nfl/pipeline/build_wind_forecast_pit.py
    python3 nfl/pipeline/build_wind_forecast_pit.py --season 2024 --hour-utc 17
"""

import argparse, json, logging, sys, time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("wind_pit")

API = "https://previous-runs-api.open-meteo.com/v1/forecast"
CANON = ROOT / "nfl" / "data" / "nfl_canonical.parquet"
STAD  = ROOT / "nfl" / "data" / "stadium_info.json"
OUT   = ROOT / "nfl" / "data" / "nfl_wind_forecast_pit_2024.parquet"

# 17:00 UTC matches what build_canonical.py used, so forecast and observed are read at
# the SAME timestamp. That keeps the forecast-error measurement valid even though 17:00
# UTC is not the true kickoff hour for late-window games.
DEFAULT_HOUR_UTC = 17
LEADS = [1, 2, 3]          # previous_dayN => forecast issued N*24h before valid time


def fetch_stadium(lat, lon, d0, d1, hour_utc):
    """One call per stadium covering the whole season date range."""
    vars_ = ["wind_speed_10m"] + [f"wind_speed_10m_previous_day{n}" for n in LEADS]
    p = {"latitude": lat, "longitude": lon, "start_date": d0, "end_date": d1,
         "hourly": ",".join(vars_), "wind_speed_unit": "mph", "timezone": "UTC"}
    try:
        r = requests.get(API, params=p, timeout=60)
    except requests.RequestException as e:
        log.error(f"HARD STOP: network error reaching Open-Meteo: {type(e).__name__}: {e}")
        log.error("Nothing was written. Safe to re-run once connectivity returns.")
        sys.exit(1)
    if r.status_code != 200:
        log.error(f"HARD STOP: HTTP {r.status_code} — {r.text[:200]}")
        sys.exit(1)
    j = r.json()
    if "error" in j:
        log.error(f"HARD STOP: API error — {j.get('reason')}")
        sys.exit(1)
    h = j.get("hourly", {})
    missing = [v for v in vars_ if v not in h]
    if missing:
        log.error(f"HARD STOP: API did not return {missing}. Archive may not cover this range.")
        sys.exit(1)
    idx = pd.to_datetime(pd.Series(h["time"]), utc=True)
    df = pd.DataFrame({v: h[v] for v in vars_})
    df["ts"] = idx
    df = df[df["ts"].dt.hour == hour_utc].copy()
    df["date"] = df["ts"].dt.date.astype(str)
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=2024)
    ap.add_argument("--hour-utc", type=int, default=DEFAULT_HOUR_UTC)
    a = ap.parse_args()

    if not CANON.exists():
        log.error(f"HARD STOP: {CANON} not found"); sys.exit(1)
    d = pd.read_parquet(CANON)
    d = d.dropna(subset=["closing_total_line", "home_score", "away_score"])
    d["tp"] = d["home_score"] + d["away_score"]
    d["resid"] = d["tp"] - d["closing_total_line"]

    g = d[(d["is_dome"] != 1) & (d["season"] == a.season)].copy()
    if g.empty:
        log.error(f"HARD STOP: no outdoor {a.season} games"); sys.exit(1)
    log.info(f"{a.season} outdoor games: {len(g)}  stadiums: {g['home_team'].nunique()}")

    stad = json.loads(STAD.read_text())
    d0, d1 = str(min(g["date"])), str(max(g["date"]))

    frames = []
    teams = sorted(g["home_team"].unique())
    for i, t in enumerate(teams, 1):
        info = stad.get(t) or {}
        lat, lon = info.get("lat"), info.get("lon")
        if lat is None:
            log.warning(f"  {t}: no coordinates, skipped"); continue
        f = fetch_stadium(lat, lon, d0, d1, a.hour_utc)
        f["home_team"] = t
        frames.append(f)
        log.info(f"  [{i:>2}/{len(teams)}] {t}: {len(f)} daily rows")
        time.sleep(1.2)

    if not frames:
        log.error("HARD STOP: nothing fetched"); sys.exit(1)
    fc = pd.concat(frames, ignore_index=True)

    g["date"] = g["date"].astype(str)
    m = g.merge(fc, on=["home_team", "date"], how="inner")
    log.info(f"\njoined {len(m)} of {len(g)} games to a forecast")
    if len(m) < 50:
        log.error("HARD STOP: join too thin to calibrate"); sys.exit(1)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    m.to_parquet(OUT)
    log.info(f"wrote {OUT}")

    # ---------- CALIBRATION ----------
    print("\n" + "=" * 74)
    print("FORECAST SKILL — how much wind information is actually available pre-game")
    print("=" * 74)
    obs = m["wind_speed"].astype(float)
    print(f"  observed wind (from canonical): mean {obs.mean():.2f}  SD {obs.std():.2f}  N={len(m)}")
    rel = {}
    print(f"\n  {'lead':>6} {'bias':>8} {'RMSE':>8} {'corr':>8} {'reliability':>12}")
    for n in LEADS:
        col = f"wind_speed_10m_previous_day{n}"
        sub = m[[col]].join(obs.rename("obs")).dropna()
        if len(sub) < 40:
            print(f"  {n*24:>4}h  too few rows ({len(sub)})"); continue
        err = sub[col] - sub["obs"]
        r = np.corrcoef(sub[col], sub["obs"])[0, 1]
        # Attenuation factor = OLS slope of regressing TRUE wind on FORECAST wind.
        # This is the exact multiplier on the observed-wind slope when the forecast is
        # substituted for the actual, and unlike var(X)/(var(X)+var_e) it stays correct
        # when the forecast is shrunk toward climatology (var(fc) < var(actual)).
        lam = float(np.cov(sub[col], sub["obs"], ddof=0)[0, 1] / sub[col].var(ddof=0))
        rel[n] = lam
        vratio = sub[col].var(ddof=0) / sub["obs"].var(ddof=0)
        flag = "  <-- CHECK: forecast variance exceeds observed; correction unreliable" \
               if vratio > 1.15 else ""
        print(f"  {n*24:>4}h {err.mean():>+8.2f} {np.sqrt((err**2).mean()):>8.2f} "
              f"{r:>8.3f} {lam:>12.2f}  var_ratio={vratio:.2f}{flag}")

    # ---------- ERRORS-IN-VARIABLES CORRECTION ----------
    o_all = d[d["is_dome"] != 1].dropna(subset=["wind_speed"])
    slope_obs = np.polyfit(o_all["wind_speed"], o_all["resid"], 1)[0]
    print("\n" + "=" * 74)
    print("BETTABLE EFFECT SIZE — observed-wind slope corrected for forecast error")
    print("=" * 74)
    print(f"  slope on OBSERVED wind (unbettable): {slope_obs:+.4f} pts/mph  N={len(o_all)}")
    print(f"\n  {'lead':>6} {'reliability':>12} {'bettable slope':>16} {'edge @15mph':>13} {'clears 0.78?':>13}")
    for n, lam in rel.items():
        bs = slope_obs * lam
        edge = abs(bs) * 15
        print(f"  {n*24:>4}h {lam:>12.2f} {bs:>+16.4f} {edge:>12.2f}p "
              f"{'YES' if edge > 0.78 else 'no':>13}")
    print("\n  0.78 pts is the NFL-totals break-even threshold at -110.")
    print("  A 15 mph game is roughly the 90th percentile of observed wind.")
    print("\n  CAVEATS: calibration is one season at 17:00 UTC, not true kickoff time.")
    print("  Nothing here is a backtest — the bettable slope must still be forward-tested.")


if __name__ == "__main__":
    main()
