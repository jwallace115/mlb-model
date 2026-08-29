#!/usr/bin/env python3
"""
NFL WIND — DECISIVE SOURCE TEST (pre-registered kill condition)

THE QUESTION
------------
The wind->totals effect measured -0.163 pts/mph (t=-2.20, N=1,168) using the
`wind_speed` column in nfl_canonical, which is ~98% nflreadpy reported conditions.

On the 187 games of 2024 where a second source was available, the two measures of
the SAME wind correlated only 0.707 and produced OPPOSITE SIGNS:
    nflreadpy   +0.0907 pts/mph
    Open-Meteo  -0.0872 pts/mph
A real physical effect does not flip sign with the data vendor.

This script re-measures the full 2019-2024 sample using a SINGLE consistent source
(Open-Meteo archive) and decides the branch.

PRE-REGISTERED DECISION RULE — fixed before running, do not renegotiate after:
    SURVIVES  : archive-source slope <= -0.10 pts/mph AND t <= -2.00
    DEAD      : slope > -0.05, or t > -1.00, or the sign is positive
    AMBIGUOUS : anything between. Treated as DEAD for deployment purposes;
                may be revisited only with a new season of forward data.

COST: free. Open-Meteo archive needs no API key for non-commercial use.
RUNTIME: ~23 stadiums x 6 seasons = ~138 calls at 1.2s = under 5 minutes.

    python3 nfl/pipeline/rebuild_wind_archive_source.py
"""

import json, logging, sys, time
from pathlib import Path
import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent.parent
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("wind_src")

API   = "https://archive-api.open-meteo.com/v1/archive"
CANON = ROOT / "nfl" / "data" / "nfl_canonical.parquet"
STAD  = ROOT / "nfl" / "data" / "stadium_info.json"
OUT   = ROOT / "nfl" / "data" / "nfl_wind_archive_allseasons.parquet"
HOUR_UTC = 17          # same hour build_canonical.py used, so it is a like-for-like swap


def fetch(lat, lon, d0, d1):
    p = {"latitude": lat, "longitude": lon, "start_date": d0, "end_date": d1,
         "hourly": "wind_speed_10m", "wind_speed_unit": "mph", "timezone": "UTC"}
    try:
        r = requests.get(API, params=p, timeout=60)
    except requests.RequestException as e:
        log.error(f"HARD STOP: network error: {type(e).__name__}: {e}")
        log.error("Nothing written. Safe to re-run."); sys.exit(1)
    if r.status_code != 200:
        log.error(f"HARD STOP: HTTP {r.status_code} — {r.text[:200]}"); sys.exit(1)
    j = r.json()
    if "error" in j:
        log.error(f"HARD STOP: API error — {j.get('reason')}"); sys.exit(1)
    h = j.get("hourly", {})
    if "wind_speed_10m" not in h:
        log.error("HARD STOP: no wind_speed_10m returned"); sys.exit(1)
    ts = pd.to_datetime(pd.Series(h["time"]), utc=True)
    df = pd.DataFrame({"ts": ts, "arch_wind": h["wind_speed_10m"]})
    df = df[df["ts"].dt.hour == HOUR_UTC].copy()
    df["date"] = df["ts"].dt.date.astype(str)
    return df[["date", "arch_wind"]]


def main():
    d = pd.read_parquet(CANON)
    d = d.dropna(subset=["closing_total_line", "home_score", "away_score", "wind_speed"])
    d["tp"] = d["home_score"] + d["away_score"]
    d["resid"] = d["tp"] - d["closing_total_line"]
    o = d[d["is_dome"] != 1].copy()
    o["date"] = o["date"].astype(str)
    log.info(f"outdoor games to re-measure: {len(o)}  seasons {sorted(o['season'].unique())}")

    stad = json.loads(STAD.read_text())
    frames = []
    jobs = [(t, s) for t in sorted(o["home_team"].unique()) for s in sorted(o["season"].unique())]
    for i, (t, s) in enumerate(jobs, 1):
        sub = o[(o["home_team"] == t) & (o["season"] == s)]
        if sub.empty:
            continue
        info = stad.get(t) or {}
        if info.get("lat") is None:
            log.warning(f"  {t}: no coords, skipped"); continue
        f = fetch(info["lat"], info["lon"], str(sub["date"].min()), str(sub["date"].max()))
        f["home_team"] = t; f["season"] = s
        frames.append(f)
        if i % 20 == 0:
            log.info(f"  [{i}/{len(jobs)}] fetched")
        time.sleep(1.2)

    fc = pd.concat(frames, ignore_index=True).drop_duplicates(["home_team", "date"])
    m = o.merge(fc[["home_team", "date", "arch_wind"]], on=["home_team", "date"], how="inner")
    m = m.dropna(subset=["arch_wind"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    m.to_parquet(OUT)
    log.info(f"joined {len(m)} of {len(o)} games; wrote {OUT}")
    if len(m) < 700:
        log.error("HARD STOP: join too thin to decide the branch"); sys.exit(1)

    A = m["wind_speed"].astype(float).values     # nflreadpy (original)
    B = m["arch_wind"].astype(float).values      # Open-Meteo archive (single source)
    y = m["resid"].values

    def slope_t(x, yy):
        s = np.cov(x, yy, ddof=0)[0, 1] / x.var(ddof=0)
        r = np.corrcoef(x, yy)[0, 1]
        t = r * np.sqrt((len(x) - 2) / max(1e-12, 1 - r * r))
        return s, t, r

    print("\n" + "=" * 74)
    print(f"SOURCE AGREEMENT, N={len(m)} (was 0.707 on the 187-game 2024 subsample)")
    print("=" * 74)
    print(f"  corr(nflreadpy, archive) = {np.corrcoef(A, B)[0,1]:.3f}   "
          f"RMSE {np.sqrt(((A-B)**2).mean()):.2f} mph")
    print(f"  SD: nflreadpy {A.std():.2f}   archive {B.std():.2f}   "
          f"mean diff {(A-B).mean():+.2f}")

    print("\n" + "=" * 74)
    print("THE TEST — same games, same outcome, only the wind source changes")
    print("=" * 74)
    sA, tA, _ = slope_t(A, y)
    sB, tB, _ = slope_t(B, y)
    print(f"  nflreadpy wind (original): slope {sA:+.4f}  t={tA:+.2f}")
    print(f"  ARCHIVE wind  (the test) : slope {sB:+.4f}  t={tB:+.2f}")
    num = np.cov(B, y, ddof=0)[0, 1]; den = np.cov(B, A, ddof=0)[0, 1]
    print(f"  IV (archive instruments nflreadpy): {num/den:+.4f}")

    mk, _, _ = slope_t(B, m["closing_total_line"].values)
    print(f"\n  what the book prices (archive wind): {mk:+.4f} pts/mph")

    print("\n" + "=" * 74)
    print("PRE-REGISTERED VERDICT")
    print("=" * 74)
    if sB <= -0.10 and tB <= -2.00:
        v = "SURVIVES — effect holds under a source change. Proceed to forward capture."
    elif sB > -0.05 or tB > -1.00 or sB > 0:
        v = "DEAD — does not survive a source change. Close the branch."
    else:
        v = "AMBIGUOUS — treated as DEAD for deployment. Revisit only with new forward data."
    print(f"  criterion: SURVIVES needs slope <= -0.10 AND t <= -2.00")
    print(f"  observed : slope {sB:+.4f}, t {tB:+.2f}")
    print(f"\n  >>> {v}")
    print("\n  This rule was fixed before the run. Do not renegotiate it now.")


if __name__ == "__main__":
    main()
