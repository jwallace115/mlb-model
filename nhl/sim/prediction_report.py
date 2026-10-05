#!/usr/bin/env python3
"""S42/S44 prediction report: moneyline + totals, A1, reliability, A2 picks."""
import json, sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss, brier_score_loss

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
BOX_DIR = ROOT / "nhl" / "cache"
PRICES_DIR = ROOT / "nhl" / "data" / "sim" / "prices"
LINES_DIR = ROOT / "data" / "odds_archive" / "nhl" / "history" / "lines"
CROSSWALK_PATH = ROOT / "nhl" / "data" / "sim" / "crosswalk" / "game_event.parquet"
GAMES_PER = 1312

from nhl.sim.build_crosswalk import NAME


def implied_prob(a):
    return 100/(a+100) if a > 0 else -a/(-a+100)


def load_pinnacle_full(season):
    sd = LINES_DIR / f"season={season}"
    if not sd.exists(): return pd.DataFrame()
    df = pd.concat([pd.read_parquet(f) for f in sorted(sd.glob("snap_*.parquet"))], ignore_index=True)
    df["snap_dt"] = pd.to_datetime(df["snapshot_utc"]); df["ct_dt"] = pd.to_datetime(df["commence_time"])
    df = df[df["snap_dt"] < df["ct_dt"]]
    df["lead_h"] = (df["ct_dt"] - df["snap_dt"]).dt.total_seconds()/3600
    df = df[df["lead_h"] <= 6]
    last = df.groupby("event_id")["snap_dt"].transform("max"); df = df[df["snap_dt"] == last]
    df["home"] = df["home_team"].map(NAME); df["away"] = df["away_team"].map(NAME)
    try:
        df["et_date"] = df["ct_dt"].dt.tz_localize("UTC").dt.tz_convert("America/New_York").dt.strftime("%Y-%m-%d")
    except TypeError:
        df["et_date"] = pd.to_datetime(df["ct_dt"], utc=True).dt.tz_convert("America/New_York").dt.strftime("%Y-%m-%d")
    pin = df[df["bookmaker"] == "pinnacle"]
    results = []
    for eid, g in pin.groupby("event_id"):
        row = {"event_id": eid, "home": g.iloc[0]["home"], "away": g.iloc[0]["away"], "et_date": g.iloc[0]["et_date"]}
        h2h = g[g["market"] == "h2h"]; ht, at = g.iloc[0]["home_team"], g.iloc[0]["away_team"]
        hh, ah = h2h[h2h["outcome_name"] == ht], h2h[h2h["outcome_name"] == at]
        if len(hh) == 1 and len(ah) == 1:
            ph, pa = implied_prob(hh.iloc[0]["price"]), implied_prob(ah.iloc[0]["price"])
            row["pin_p_home_novig_mult"] = ph/(ph+pa)
            row["pin_home_price_raw"] = float(hh.iloc[0]["price"])
            row["pin_away_price_raw"] = float(ah.iloc[0]["price"])
        tot = g[g["market"] == "totals"]; ov = tot[tot["outcome_name"] == "Over"]; un = tot[tot["outcome_name"] == "Under"]
        if len(ov) == 1 and len(un) == 1:
            row["pin_total_line"] = ov.iloc[0]["point"]
            po, pu = implied_prob(ov.iloc[0]["price"]), implied_prob(un.iloc[0]["price"])
            row["pin_p_over_novig_mult"] = po/(po+pu)
            row["pin_over_price_raw"] = float(ov.iloc[0]["price"])
            row["pin_under_price_raw"] = float(un.iloc[0]["price"])
        # Median book prices for A2
        all_h2h = g[g["market"] == "h2h"]
        for t in [ht, at]:
            prices = all_h2h[all_h2h["outcome_name"] == t]["price"]
            if len(prices):
                row[f"med_price_{NAME.get(t, t)}"] = float(prices.median())
        results.append(row)
    return pd.DataFrame(results)


def load_actuals(season):
    rows = []
    for i in range(1, GAMES_PER+1):
        gid = f"{season}02{i:04d}"
        bp = BOX_DIR / f"boxscore_{gid}.json"
        if not bp.exists(): continue
        with open(bp) as f: d = json.load(f)
        hs, as_ = d["homeTeam"]["score"], d["awayTeam"]["score"]
        outcome = d.get("gameOutcome",{}).get("lastPeriodType","REG")
        h, a = hs, as_
        if outcome == "SO":
            if h > a: h -= 1
            else: a -= 1
        rows.append({"game_id": gid, "home_win": int(hs > as_), "total": hs + as_, "total_no_so": h + a,
                      "home": d["homeTeam"]["abbrev"], "away": d["awayTeam"]["abbrev"]})
    return pd.DataFrame(rows)


def a1_test(y, p_eng, p_pin, label="ML"):
    logit_pin = np.log(np.clip(p_pin, 0.01, 0.99) / (1 - np.clip(p_pin, 0.01, 0.99)))
    logit_eng = np.log(np.clip(p_eng, 0.01, 0.99) / (1 - np.clip(p_eng, 0.01, 0.99)))
    disagree = logit_eng - logit_pin
    X = np.column_stack([logit_pin, disagree])
    lr = LogisticRegression(fit_intercept=True, max_iter=1000, C=1e9)
    lr.fit(X, y)
    coef = lr.coef_[0][1]
    rng = np.random.RandomState(42)
    coefs = []
    for _ in range(1000):
        idx = rng.choice(len(y), len(y), replace=True)
        try:
            lr_b = LogisticRegression(fit_intercept=True, max_iter=1000, C=1e9)
            lr_b.fit(X[idx], y[idx])
            coefs.append(lr_b.coef_[0][1])
        except: pass
    ci_lo, ci_hi = np.percentile(coefs, [5, 95])
    adds = ci_lo > 0
    print(f"  {label} A1 disagreement: {coef:.3f} (90% CI [{ci_lo:.3f}, {ci_hi:.3f}]) adds_info={adds}")
    return coef, ci_lo, ci_hi, adds


def reliability_table(y, p, label, bins=10):
    df = pd.DataFrame({"p": p, "y": y})
    df["bin"] = pd.qcut(df["p"], bins, duplicates="drop")
    t = df.groupby("bin", observed=True).agg(mean_p=("p", "mean"), mean_y=("y", "mean"), n=("y", "count"))
    print(f"  {label} reliability:")
    for _, r in t.iterrows():
        print(f"    {r.name}: pred={r.mean_p:.3f} actual={r.mean_y:.3f} n={int(r.n)}")


def main():
    # Load crosswalk for ID-only join
    cw = pd.read_parquet(CROSSWALK_PATH)
    for season in [2022, 2023]:
        label = "2022-23 (fit)" if season == 2022 else "2023-24 (validate)"
        prices = pd.read_parquet(PRICES_DIR / f"season={season}.parquet")
        act = load_actuals(season)
        pin = load_pinnacle_full(season)

        m = prices.merge(act, on="game_id")
        if not pin.empty:
            # ID-only join: game_id -> crosswalk -> event_id -> Pinnacle
            cw_s = cw[cw["season"] == season][["game_id", "event_id"]]
            m = m.merge(cw_s, on="game_id", how="left")
            m = m.merge(pin, on="event_id", how="left", suffixes=("", "_pin"))
        n_pin = int(m["pin_p_home_novig_mult"].notna().sum())
        mp = m[m["pin_p_home_novig_mult"].notna()].copy()
        mp["price_scale"] = "pinnacle_novig_multiplicative"

        print(f"\n{'='*60}\n{label}: {len(mp)} games with Pinnacle\n{'='*60}")

        # --- MONEYLINE ---
        y = mp["home_win"].values
        p_eng = mp["p_home_win"].values
        p_pin = mp["pin_p_home_novig_mult"].values
        ll_eng = log_loss(y, np.clip(p_eng, 0.01, 0.99))
        ll_pin = log_loss(y, np.clip(p_pin, 0.01, 0.99))
        br_eng = brier_score_loss(y, p_eng)
        br_pin = brier_score_loss(y, p_pin)
        print(f"  ML log-loss: engine={ll_eng:.4f} Pinnacle={ll_pin:.4f} (diff={ll_eng-ll_pin:+.4f})")
        print(f"  ML Brier:    engine={br_eng:.4f} Pinnacle={br_pin:.4f}")
        a1_test(y, p_eng, p_pin, "ML")
        reliability_table(y, p_eng, "Engine ML")
        reliability_table(y, p_pin, "Pinnacle ML")

        # Favourite / underdog
        fav = p_eng >= 0.5
        for lbl, mask in [("Favourite (engine)", fav), ("Underdog (engine)", ~fav)]:
            if mask.sum() < 20: continue
            ll = log_loss(y[mask], np.clip(p_eng[mask], 0.01, 0.99))
            print(f"  {lbl}: log-loss={ll:.4f} n={mask.sum()}")

        # |engine - Pinnacle| buckets
        diff_pts = np.abs(p_eng - p_pin) * 100
        for lbl, lo, hi in [("<2 pts", 0, 2), ("2-5 pts", 2, 5), (">5 pts", 5, 100)]:
            mask = (diff_pts >= lo) & (diff_pts < hi)
            if mask.sum() < 20: continue
            ll_e = log_loss(y[mask], np.clip(p_eng[mask], 0.01, 0.99))
            ll_p = log_loss(y[mask], np.clip(p_pin[mask], 0.01, 0.99))
            print(f"  |diff| {lbl}: engine={ll_e:.4f} Pinnacle={ll_p:.4f} n={mask.sum()}")

        # --- TOTALS ---
        has_tot = mp["pin_total_line"].notna() & mp["p_over"].notna()
        if has_tot.sum() > 100:
            mt = mp[has_tot].copy()
            y_over = (mt["total"] > mt["pin_total_line"]).astype(int)
            push = mt["total"] == mt["pin_total_line"]
            mt_np = mt[~push].copy()
            y_np = y_over[~push].values
            p_over_eng = mt_np["p_over"].values / (mt_np["p_over"].values + mt_np.get("p_under", 1 - mt_np["p_over"]).values)
            p_over_eng = np.clip(p_over_eng, 0.01, 0.99)

            print(f"\n  TOTALS: {len(mt_np)} games (pushes={push.sum()})")
            if "pin_p_over_novig_mult" in mt_np.columns:
                p_over_pin = mt_np["pin_p_over_novig_mult"].values
                ll_tot_eng = log_loss(y_np, p_over_eng)
                ll_tot_pin = log_loss(y_np, np.clip(p_over_pin, 0.01, 0.99))
                br_tot_eng = brier_score_loss(y_np, p_over_eng)
                br_tot_pin = brier_score_loss(y_np, np.clip(p_over_pin, 0.01, 0.99))
                print(f"  Totals log-loss: engine={ll_tot_eng:.4f} Pinnacle={ll_tot_pin:.4f}")
                print(f"  Totals Brier:    engine={br_tot_eng:.4f} Pinnacle={br_tot_pin:.4f}")
                a1_test(y_np, p_over_eng, p_over_pin, "Totals")
                reliability_table(y_np, p_over_eng, "Engine Totals")

        # --- A2 PICKS (descriptive) ---
        print(f"\n  A2 PICKS (moneyline, edge >= 0.04 vs median price break-even):")
        # For each game, check if engine edge >= 0.04 over the break-even
        # We need median book prices — use pin as proxy
        picks = []
        for _, r in mp.iterrows():
            p = r["p_home_win"]
            be = r["pin_p_home_novig_mult"]  # using Pinnacle as proxy for median break-even
            edge = p - be
            if abs(edge) >= 0.04:
                side = "home" if edge > 0 else "away"
                won = (r["home_win"] == 1) if side == "home" else (r["home_win"] == 0)
                picks.append({"side": side, "edge": abs(edge), "won": int(won), "month": r["date"][:7]})
        if picks:
            pdf = pd.DataFrame(picks)
            hit = pdf["won"].mean()
            print(f"    n={len(pdf)}, hit={hit:.1%}, by month:")
            for mo, g in pdf.groupby("month"):
                print(f"      {mo}: n={len(g)}, hit={g['won'].mean():.1%}")


if __name__ == "__main__":
    main()
