#!/usr/bin/env python3
"""S41: simulate every 2022-23 and 2023-24 regular-season game and write prices."""
import json, sys, time, hashlib
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from nhl.sim.engine import simulate, league_average_inputs
from nhl.sim.game_inputs import game_inputs_for, load_all
from nhl.sim.sanity_check_v2 import load_pinnacle

BOX_DIR = ROOT / "nhl" / "cache"
OUT_DIR = ROOT / "nhl" / "data" / "sim" / "prices"
MANIFEST = ROOT / "nhl" / "data" / "sim" / "ratings" / "manifest.json"
GAMES_PER_SEASON = 1312


def price_season(season, n_sims, tr, gr, ft, q, base_inp):
    """Simulate every game in a season and compute prices."""
    rows = []
    skipped = 0
    t0 = time.time()

    for i in range(1, GAMES_PER_SEASON + 1):
        gid = f"{season}02{i:04d}"
        bp = BOX_DIR / f"boxscore_{gid}.json"
        if not bp.exists():
            continue
        with open(bp) as f:
            d = json.load(f)
        home = d["homeTeam"]["abbrev"]
        away = d["awayTeam"]["abbrev"]
        date = d.get("gameDate", "")

        try:
            inp = game_inputs_for(gid, tr, gr, ft, q, base_inp)
        except ValueError:
            skipped += 1
            continue

        seed = int(gid)
        r = simulate(inp, n_sims, seed=seed)

        N = n_sims
        p_home_win = (r["home_score"] > r["away_score"]).mean()
        p_reg_home = ((r["decided"] == "REG") & (r["home_score"] > r["away_score"])).mean()
        p_reg_tie = (r["decided"] != "REG").mean()  # includes OT/SO = tied after regulation
        p_reg_away = ((r["decided"] == "REG") & (r["away_score"] > r["home_score"])).mean()
        p_home_m15 = ((r["home_score"] - r["away_score"]) >= 2).mean()
        p_away_p15 = ((r["away_score"] - r["home_score"]) >= -1).mean()  # away +1.5 = away loses by 0 or 1 or wins
        # Actually puck line: home -1.5 = home wins by 2+; away +1.5 = away doesn't lose by 2+
        p_away_p15 = 1.0 - p_home_m15  # complementary
        mean_total = (r["home_score"] + r["away_score"]).mean()

        row = {
            "game_id": gid, "season": season, "date": date, "home": home, "away": away,
            "p_home_win": round(p_home_win, 4),
            "p_reg_home": round(p_reg_home, 4),
            "p_reg_tie": round(p_reg_tie, 4),
            "p_reg_away": round(p_reg_away, 4),
            "p_home_m15": round(p_home_m15, 4),
            "p_away_p15": round(p_away_p15, 4),
            "mean_total": round(mean_total, 2),
            "n_sims": N,
        }
        rows.append(row)

        if (i) % 200 == 0:
            print(f"  [{i}/{GAMES_PER_SEASON}] {time.time()-t0:.0f}s", flush=True)

    elapsed = time.time() - t0
    print(f"  Season {season}: {len(rows)} games priced, {skipped} skipped, {elapsed:.0f}s")
    return pd.DataFrame(rows)


def add_pinnacle_lines(df, season):
    """Join Pinnacle totals line."""
    pin = load_pinnacle(season)
    if pin.empty:
        df["pin_total_line"] = np.nan
        return df
    df = df.merge(pin[["et_date", "home", "away", "pin_p_home", "pin_total_line"]],
                   left_on=["date", "home", "away"], right_on=["et_date", "home", "away"], how="left")
    return df


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-sims", type=int, default=2000)
    args = ap.parse_args()

    tr, gr, ft, q = load_all()
    base_inp = league_average_inputs()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    m = json.loads(MANIFEST.read_text())

    for season in [2022, 2023]:
        print(f"\nPricing season {season}-{season+1}...")
        df = price_season(season, args.n_sims, tr, gr, ft, q, base_inp)
        df = add_pinnacle_lines(df, season)

        # Totals over/under at Pinnacle's line
        has_line = df["pin_total_line"].notna()
        df.loc[has_line, "p_over"] = df.loc[has_line].apply(
            lambda r: ((r["mean_total"] * np.ones(1)) > r["pin_total_line"]).mean(), axis=1)
        # Actually we need sim-level totals, not mean. Use the probability from the mean approximation:
        # p_over ≈ share of sims with total > line. We don't have per-sim data anymore.
        # Let's use a normal approximation: p_over = P(total > line) ≈ Φ((mean - line) / σ)
        # σ ≈ sqrt(mean) for Poisson-like totals
        from scipy.stats import norm
        df.loc[has_line, "p_over"] = df.loc[has_line].apply(
            lambda r: float(norm.sf(r["pin_total_line"], loc=r["mean_total"], scale=np.sqrt(max(r["mean_total"], 1)))), axis=1)
        df.loc[has_line, "p_push_total"] = df.loc[has_line].apply(
            lambda r: float(norm.pdf(r["pin_total_line"], loc=r["mean_total"], scale=np.sqrt(max(r["mean_total"], 1)))), axis=1)

        out_path = OUT_DIR / f"season={season}.parquet"
        df.to_parquet(out_path, index=False)
        sha = hashlib.sha256(out_path.read_bytes()).hexdigest()
        m[f"prices_{season}_sha256"] = sha
        m[f"prices_{season}_rows"] = len(df)
        print(f"  Saved: {out_path} ({len(df)} rows)")
        print(f"  Pinnacle matched: {has_line.sum()}")

    MANIFEST.write_text(json.dumps(m, indent=2) + "\n")
    print(f"\nManifest updated")


if __name__ == "__main__":
    main()
