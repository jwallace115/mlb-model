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
        except ValueError as e:
            print(f"HALT: game_inputs_for failed for game_id={gid}: {e}", file=sys.stderr)
            sys.exit(1)

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

        # Total-goals distribution from simulations
        totals = r["home_score"] + r["away_score"]
        tot_dist = {}
        for k in range(16):
            if k < 15:
                tot_dist[f"p_tot_{k}"] = round(float((totals == k).mean()), 6)
            else:
                tot_dist[f"p_tot_{k}"] = round(float((totals >= k).mean()), 6)

        row = {
            "game_id": gid, "season": season, "date": date, "home": home, "away": away,
            "p_home_win": round(p_home_win, 4),
            "p_reg_home": round(p_reg_home, 4),
            "p_reg_tie": round(p_reg_tie, 4),
            "p_reg_away": round(p_reg_away, 4),
            "p_home_m15": round(p_home_m15, 4),
            "p_away_p15": round(p_away_p15, 4),
            "mean_total": round(mean_total, 2),
            "mean_home_goals": round(float(r["home_score"].mean()), 4),
            "mean_away_goals": round(float(r["away_score"].mean()), 4),
            "n_sims": N,
            **tot_dist,
        }
        rows.append(row)

        if (i) % 200 == 0:
            print(f"  [{i}/{GAMES_PER_SEASON}] {time.time()-t0:.0f}s", flush=True)

    elapsed = time.time() - t0
    print(f"  Season {season}: {len(rows)} games priced, {skipped} skipped, {elapsed:.0f}s")
    return pd.DataFrame(rows)


def add_pinnacle_lines(df, season, allow_no_lines=False):
    """Join Pinnacle totals line. HALTs if no lines found unless --allow-no-lines."""
    pin = load_pinnacle(season)
    if pin.empty:
        if not allow_no_lines:
            print(f"HALT: no Pinnacle lines found for season {season}. "
                  f"Pass --allow-no-lines to proceed without lines.", file=sys.stderr)
            sys.exit(1)
        df["pin_total_line"] = np.nan
        return df
    df = df.merge(pin[["et_date", "home", "away", "pin_p_home", "pin_total_line"]],
                   left_on=["date", "home", "away"], right_on=["et_date", "home", "away"], how="left")
    return df


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-sims", type=int, default=2000)
    ap.add_argument("--allow-no-lines", action="store_true",
                    help="Allow pricing seasons with no Pinnacle lines")
    args = ap.parse_args()

    tr, gr, ft, q = load_all()
    base_inp = league_average_inputs()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    m = json.loads(MANIFEST.read_text())

    for season in [2022, 2023]:
        print(f"\nPricing season {season}-{season+1}...")
        df = price_season(season, args.n_sims, tr, gr, ft, q, base_inp)
        df = add_pinnacle_lines(df, season, allow_no_lines=args.allow_no_lines)

        # Totals over/under/push at Pinnacle's line — EXACT from the total-goals distribution
        has_line = df["pin_total_line"].notna()
        def exact_over_under(row):
            line = row["pin_total_line"]
            line_int = int(line)
            is_half = (line % 1) != 0
            p_over = sum(row.get(f"p_tot_{k}", 0) for k in range(line_int + 1, 16))
            if not is_half:
                p_push = row.get(f"p_tot_{line_int}", 0)
            else:
                p_push = 0.0
                p_over += row.get(f"p_tot_{line_int + 1}", 0) if line_int + 1 <= 14 else 0
                # For half lines: over = total > line = total >= line_int + 1
                p_over = sum(row.get(f"p_tot_{k}", 0) for k in range(line_int + 1, 16))
            p_under = 1.0 - p_over - p_push
            return pd.Series({"p_over": round(p_over, 6), "p_under": round(p_under, 6), "p_push_total": round(p_push, 6)})

        if has_line.any():
            ou = df.loc[has_line].apply(exact_over_under, axis=1)
            df.loc[has_line, "p_over"] = ou["p_over"].values
            df.loc[has_line, "p_under"] = ou["p_under"].values
            df.loc[has_line, "p_push_total"] = ou["p_push_total"].values

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
