#!/usr/bin/env python3
"""WNBA Model Runner — generates daily signals."""
import argparse, json, pickle, sys, os
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import date

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=date.today().isoformat())
    args = parser.parse_args()
    target_date = args.date

    # Load frozen model
    model = pickle.load(open("wnba/models/ridge_wnba.pkl", "rb"))
    scaler = pickle.load(open("wnba/models/scaler_wnba.pkl", "rb"))
    config = json.load(open("wnba/models/feature_config_wnba.json"))
    features = config["feature_list"]
    RESIDUAL_STD = 16.693

    # Load feature table
    feat = pd.read_parquet("wnba/data/canonical/wnba_feature_table.parquet")
    today = feat[feat['game_date'].astype(str).str[:10] == target_date]

    if len(today) == 0:
        print(f"No games found for {target_date}")
        return

    # Load existing signals
    sig_path = ROOT / "wnba" / "data" / "signals" / "wnba_signals_2025.json"
    existing = json.load(open(sig_path)) if sig_path.exists() else []
    existing_ids = {s["game_id"] for s in existing}

    X = scaler.transform(today[features].fillna(0))
    preds = model.predict(X)

    np.random.seed(42)
    new_sigs = []
    for i, (idx, row) in enumerate(today.iterrows()):
        if row["game_id"] in existing_ids:
            continue
        pred = preds[i]
        sims = pred + np.random.normal(0, RESIDUAL_STD, 10000)
        model_total = float(np.median(sims))
        line = row.get("closing_total")
        if pd.notna(line):
            p_over = float((sims > line).mean())
            edge = round(model_total - line, 1)
        else:
            p_over = 0.5; edge = 0
        p_under = 1 - p_over

        if edge > 3.0 and p_over > 0.57: tier = "MODEL_STRONG_OVER"
        elif edge > 1.5 and p_over > 0.53: tier = "MODEL_LEAN_OVER"
        elif edge < -3.0 and p_under > 0.57: tier = "MODEL_STRONG_UNDER"
        elif edge < -1.5 and p_under > 0.53: tier = "MODEL_LEAN_UNDER"
        else: tier = "NO_SIGNAL"

        new_sigs.append({
            "game_id": row["game_id"], "game_date": target_date,
            "home_team": row["home_team"], "away_team": row["away_team"],
            "model_total": round(model_total, 1),
            "closing_total": round(float(line), 1) if pd.notna(line) else None,
            "model_edge": edge, "p_over": round(p_over, 4), "p_under": round(p_under, 4),
            "signal_tier": tier, "confidence": round(abs(p_over - 0.5), 4),
            "home_rolling_pts": round(float(row.get("home_rolling_pts", 0)), 1),
            "away_rolling_pts": round(float(row.get("away_rolling_pts", 0)), 1),
            "home_rolling_opp_pts": round(float(row.get("home_rolling_opp_pts", 0)), 1),
            "away_rolling_opp_pts": round(float(row.get("away_rolling_opp_pts", 0)), 1),
            "rest_differential": int(row.get("rest_diff", 0)),
            "home_b2b": int(row.get("home_b2b", 0)), "away_b2b": int(row.get("away_b2b", 0)),
            "signal_overlays": [], "status": "PRELIMINARY", "result": None,
        })

    existing.extend(new_sigs)
    with open(sig_path, "w") as f:
        json.dump(existing, f, indent=2)

    tiers = pd.Series([s["signal_tier"] for s in new_sigs]).value_counts()
    print(f"WNBA model: {len(new_sigs)} games for {target_date}")
    print(f"Tiers: {dict(tiers)}")

if __name__ == "__main__":
    main()
