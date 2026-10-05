#!/usr/bin/env python3
"""D8: evaluate walk-forward prices at SBRO closing lines.

Joins engine prices (from price_walkforward.py) to SBRO closing lines
(from inputs/games.parquet) by game_id. Reports unmatched per season.

Metrics per season and pooled:
  - ML log-loss: engine vs SBRO close
  - A1 disagreement coefficient with 90% CI
  - Totals log-loss at the SBRO line
  - Totals A1
  - A2 picks (engine - 1/decimal_close >= 0.04) ROI at SBRO close
  - 16-regime family with BH 10%

Pre-registrations (written before running):
  (i) Engine ML log-loss within 0.012 of close pooled
  (ii) Pooled A1 90% CI includes 0
  (iii) R8 (both teams' pen-taken > 1.05 × league): ML A1 > 0, 90% lower > 0

Usage:
  python3 nhl/sim/evaluate_walkforward.py
"""
import json, sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as sp_stats

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

PRICES_DIR = ROOT / "nhl" / "data" / "sim" / "prices"
SBRO_PATH = ROOT / "research" / "nhl_sim" / "edge_hunt_2026-09-30" / "inputs" / "games.parquet"
WF_DIR = ROOT / "nhl" / "data" / "sim" / "walkforward"
TARGETS = list(range(2012, 2021))


def log_loss(p, y):
    """Binary log-loss, clipped."""
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return -np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))


def a1_disagreement(p_engine, p_close, outcome):
    """A1 disagreement coefficient: outcome ~ logit(close) + (logit(engine) - logit(close)).
    Returns (coef, lower_90, upper_90)."""
    from scipy.special import logit as sp_logit
    p_e = np.clip(p_engine, 1e-4, 1 - 1e-4)
    p_c = np.clip(p_close, 1e-4, 1 - 1e-4)
    logit_e = sp_logit(p_e)
    logit_c = sp_logit(p_c)
    delta = logit_e - logit_c

    import statsmodels.api as sm
    X = np.column_stack([logit_c, delta])
    X = sm.add_constant(X)
    model = sm.Logit(outcome.astype(float), X)
    result = model.fit(disp=0)
    coef = result.params[2]
    se = result.bse[2]
    ci_lo = coef - 1.645 * se
    ci_hi = coef + 1.645 * se
    p_val = result.pvalues[2]
    return coef, ci_lo, ci_hi, p_val


def load_data():
    """Load and join engine prices with SBRO lines."""
    sbro = pd.read_parquet(SBRO_PATH)
    all_prices = []
    for T in TARGETS:
        pf = PRICES_DIR / f"season={T}.parquet"
        if not pf.exists():
            print(f"WARNING: {pf} not found, skipping season {T}")
            continue
        df = pd.read_parquet(pf)
        all_prices.append(df)
    prices = pd.concat(all_prices, ignore_index=True)

    # Join on game_id (convert types if needed)
    prices["game_id"] = prices["game_id"].astype(str)
    sbro["game_id"] = sbro["game_id"].astype(str)

    # Report unmatched per season
    for T in TARGETS:
        p_gids = set(prices[prices["season"] == T]["game_id"])
        s_gids = set(sbro[sbro["season"] == T]["game_id"].astype(str))
        in_prices_not_sbro = p_gids - s_gids
        in_sbro_not_prices = s_gids - p_gids
        matched = p_gids & s_gids
        print(f"  {T}: {len(matched)} matched, {len(in_prices_not_sbro)} in prices only, "
              f"{len(in_sbro_not_prices)} in SBRO only")

    merged = prices.merge(sbro[["game_id", "ml_h", "ml_a", "p_h", "tl", "tot", "home_win"]],
                          on="game_id", how="inner")
    print(f"\nTotal matched: {len(merged)} games")
    return merged


def evaluate_ml(df, label=""):
    """Evaluate moneyline performance."""
    df = df[df["p_h"].notna() & df["home_win"].notna()].copy()
    eng_ll = log_loss(df["p_home_win"], df["home_win"])
    sbro_ll = log_loss(df["p_h"], df["home_win"])
    coef, lo, hi, pval = a1_disagreement(df["p_home_win"].values, df["p_h"].values, df["home_win"].values)
    adds_info = lo > 0
    print(f"  {label}ML ({len(df)} games): engine LL={eng_ll:.4f} SBRO={sbro_ll:.4f} "
          f"(diff={eng_ll-sbro_ll:+.4f})")
    print(f"    A1: coef={coef:.3f} 90% CI [{lo:.3f}, {hi:.3f}] p={pval:.4f} adds_info={adds_info}")
    return eng_ll, sbro_ll, coef, lo, hi, pval


def evaluate_totals(df, label=""):
    """Evaluate totals performance at SBRO line."""
    has_line = df["tl"].notna() & df["tot"].notna()
    d = df[has_line].copy()
    if len(d) == 0:
        print(f"  {label}Totals: no games with lines")
        return None

    # Engine P(over) at SBRO line
    def eng_p_over(row):
        line = row["tl"]
        line_int = int(line)
        is_half = (line % 1) != 0
        if is_half:
            p_over = sum(row.get(f"p_tot_{k}", 0) for k in range(line_int + 1, 16))
        else:
            p_over = sum(row.get(f"p_tot_{k}", 0) for k in range(line_int + 1, 16))
        return p_over

    d["eng_p_over"] = d.apply(eng_p_over, axis=1)
    d["actual_over"] = (d["tot"] > d["tl"]).astype(int)
    # Exclude pushes
    d = d[d["tot"] != d["tl"]]

    eng_ll = log_loss(d["eng_p_over"], d["actual_over"])

    # SBRO doesn't give totals probabilities directly; use a flat 0.5 as baseline
    sbro_ll = log_loss(np.full(len(d), 0.5), d["actual_over"])

    print(f"  {label}Totals ({len(d)} non-push): engine LL={eng_ll:.4f} coin-flip={sbro_ll:.4f}")
    return eng_ll


def evaluate_a2_picks(df, label=""):
    """A2 picks: engine - 1/decimal_close >= 0.04."""
    # Convert SBRO ML to implied prob (already have p_h)
    d = df.copy()
    d["edge"] = d["p_home_win"] - d["p_h"]

    # Home picks
    home_picks = d[d["edge"] >= 0.04].copy()
    home_picks["bet_won"] = home_picks["home_win"]
    home_picks["decimal"] = 1 / home_picks["p_h"]

    # Away picks
    d["edge_away"] = (1 - d["p_home_win"]) - (1 - d["p_h"])
    away_picks = d[d["edge_away"] >= 0.04].copy()
    away_picks["bet_won"] = 1 - away_picks["home_win"]
    away_picks["decimal"] = 1 / (1 - away_picks["p_h"])

    picks = pd.concat([home_picks[["game_id", "season", "bet_won", "decimal", "date"]],
                        away_picks[["game_id", "season", "bet_won", "decimal", "date"]]])
    if len(picks) == 0:
        print(f"  {label}A2: no picks at edge >= 0.04")
        return

    picks["pnl"] = picks["bet_won"] * (picks["decimal"] - 1) - (1 - picks["bet_won"])
    roi = picks["pnl"].mean()
    se = picks["pnl"].std() / np.sqrt(len(picks))
    hit = picks["bet_won"].mean()

    print(f"  {label}A2 picks: n={len(picks)}, hit={hit:.1%}, ROI={roi:+.1%} (SE={se:.1%})")

    # By season
    for s in sorted(picks["season"].unique()):
        sp = picks[picks["season"] == s]
        r = sp["pnl"].mean()
        print(f"    {s}: n={len(sp)}, hit={sp['bet_won'].mean():.1%}, ROI={r:+.1%}")

    # By month
    picks["month"] = pd.to_datetime(picks["date"]).dt.month
    for m in sorted(picks["month"].unique()):
        mp = picks[picks["month"] == m]
        r = mp["pnl"].mean()
        print(f"    month {m}: n={len(mp)}, ROI={r:+.1%}")

    # By fav/dog
    fav = picks[picks["decimal"] < 2.0]
    dog = picks[picks["decimal"] >= 2.0]
    if len(fav):
        print(f"    favourite: n={len(fav)}, ROI={fav['pnl'].mean():+.1%}")
    if len(dog):
        print(f"    underdog: n={len(dog)}, ROI={dog['pnl'].mean():+.1%}")


def evaluate_regimes(df):
    """16-regime family: 8 regimes x 2 markets (ML, TOT), BH 10%."""
    # Load team ratings for regime classification
    results = []

    # For regimes, we need team ratings at game time
    # R8: both teams' penalties_taken_per60 > 1.05 * league
    # R6: both goalies below league average
    # Load from walkforward ratings
    regime_data = []
    for T in TARGETS:
        wf = WF_DIR / f"season={T}"
        tr = pd.read_parquet(wf / "team_ratings.parquet")
        gr = pd.read_parquet(wf / "goalie_ratings.parquet")
        tr_t = tr[tr["season"] == T]
        gr_t = gr[gr["season"] == T]

        # Get home/away pairs
        for _, row in tr_t[tr_t["role"] == "home"].iterrows():
            gid = str(row["game_id"])
            h_pen = row["penalties_taken_per60"] / row["lg_penalties_taken_per60"] if row["lg_penalties_taken_per60"] > 0 else 1.0
            h_att_for = row["ev_att_for_per60"] / row["lg_ev_att_for_per60"] if row["lg_ev_att_for_per60"] > 0 else 1.0

            a_row = tr_t[(tr_t["game_id"] == row["game_id"]) & (tr_t["role"] == "away")]
            if len(a_row) == 0:
                continue
            a_row = a_row.iloc[0]
            a_pen = a_row["penalties_taken_per60"] / a_row["lg_penalties_taken_per60"] if a_row["lg_penalties_taken_per60"] > 0 else 1.0
            a_att_for = a_row["ev_att_for_per60"] / a_row["lg_ev_att_for_per60"] if a_row["lg_ev_att_for_per60"] > 0 else 1.0

            h_gr_row = gr_t[(gr_t["game_id"] == row["game_id"]) & (gr_t["role"] == "home")]
            a_gr_row = gr_t[(gr_t["game_id"] == row["game_id"]) & (gr_t["role"] == "away")]
            h_gsax = float(h_gr_row.iloc[0]["gsax_per_att_rating"]) if len(h_gr_row) else 0.0
            a_gsax = float(a_gr_row.iloc[0]["gsax_per_att_rating"]) if len(a_gr_row) else 0.0

            n_games = row["n_prior_games"]

            regime_data.append({
                "game_id": gid,
                "h_pen_ratio": h_pen, "a_pen_ratio": a_pen,
                "h_att_ratio": h_att_for, "a_att_ratio": a_att_for,
                "h_gsax": h_gsax, "a_gsax": a_gsax,
                "n_prior_games": n_games,
            })

    rdf = pd.DataFrame(regime_data)
    df_r = df.merge(rdf, on="game_id", how="left")

    # Filter out games without valid regime data
    valid = df_r["n_prior_games"].notna() & df_r["h_pen_ratio"].notna() & df_r["p_h"].notna()
    df_v = df_r[valid].copy()

    # Define 8 regimes
    regimes = {
        "R1_early": df_v["n_prior_games"] <= 10,
        "R2_mid": (df_v["n_prior_games"] > 10) & (df_v["n_prior_games"] <= 40),
        "R3_late": df_v["n_prior_games"] > 40,
        "R4_high_disagree": abs(df_v["p_home_win"] - df_v["p_h"]) > 0.05,
        "R5_engine_underdog": df_v["p_home_win"] < 0.5,
        "R6_weak_goalies": (df_v["h_gsax"] < 0) & (df_v["a_gsax"] < 0),
        "R7_high_5v5_att": (df_v["h_att_ratio"] > 1.02) & (df_v["a_att_ratio"] > 1.02),
        "R8_high_pen": (df_v["h_pen_ratio"] > 1.05) & (df_v["a_pen_ratio"] > 1.05),
    }

    print(f"\n{'='*60}")
    print("16-regime family (BH 10%)")
    print(f"{'='*60}")

    family = []
    for rname, mask in regimes.items():
        mask = mask.fillna(False)
        rd = df_v[mask]
        if len(rd) < 20:
            print(f"  {rname}: n={len(rd)}, too few")
            continue

        # ML
        try:
            coef, lo, hi, pval = a1_disagreement(rd["p_home_win"].values, rd["p_h"].values, rd["home_win"].values)
            family.append({"regime": rname, "market": "ML", "n": len(rd),
                          "coef": coef, "lo90": lo, "hi90": hi, "p": pval})
            print(f"  {rname} ML: n={len(rd)}, A1={coef:.3f} [{lo:.3f}, {hi:.3f}] p={pval:.4f}")
        except Exception as e:
            print(f"  {rname} ML: error {e}")

        # Totals (skip if too few lines)
        has_line = rd["tl"].notna() & rd["tot"].notna()
        rd_t = rd[has_line & (rd["tot"] != rd["tl"])]
        if len(rd_t) >= 20:
            def eng_p_over(row):
                line = row["tl"]
                line_int = int(line)
                return sum(row.get(f"p_tot_{k}", 0) for k in range(line_int + 1, 16))
            rd_t = rd_t.copy()
            rd_t["eng_p_over"] = rd_t.apply(eng_p_over, axis=1)
            rd_t["actual_over"] = (rd_t["tot"] > rd_t["tl"]).astype(int)
            try:
                coef, lo, hi, pval = a1_disagreement(rd_t["eng_p_over"].values,
                                                      np.full(len(rd_t), 0.5),
                                                      rd_t["actual_over"].values)
                family.append({"regime": rname, "market": "TOT", "n": len(rd_t),
                              "coef": coef, "lo90": lo, "hi90": hi, "p": pval})
                print(f"  {rname} TOT: n={len(rd_t)}, A1={coef:.3f} [{lo:.3f}, {hi:.3f}] p={pval:.4f}")
            except Exception as e:
                print(f"  {rname} TOT: error {e}")

    # BH correction
    if family:
        fam_df = pd.DataFrame(family).sort_values("p")
        m = len(fam_df)
        fam_df["rank"] = range(1, m + 1)
        fam_df["bh_threshold"] = fam_df["rank"] / m * 0.10
        fam_df["survives_bh"] = fam_df["p"] <= fam_df["bh_threshold"]
        survivors = fam_df[fam_df["survives_bh"]]
        print(f"\n  BH 10% survivors: {len(survivors)}")
        if len(survivors):
            for _, r in survivors.iterrows():
                print(f"    {r['regime']} {r['market']}: p={r['p']:.4f} < threshold={r['bh_threshold']:.4f}")
        else:
            print(f"    None. Min p={fam_df['p'].min():.4f}, threshold={fam_df['bh_threshold'].iloc[0]:.4f}")

    return family


def main():
    print("Loading and joining data...")
    df = load_data()

    # Per-season evaluation
    for T in TARGETS:
        d = df[df["season"] == T]
        if len(d) == 0:
            continue
        print(f"\n{'='*60}")
        print(f"Season {T}-{T+1} ({len(d)} games)")
        print(f"{'='*60}")
        evaluate_ml(d, f"{T} ")
        evaluate_totals(d, f"{T} ")

    # Pooled
    print(f"\n{'='*60}")
    print(f"POOLED ({len(df)} games, {TARGETS[0]}-{TARGETS[-1]})")
    print(f"{'='*60}")
    eng_ll, sbro_ll, coef, lo, hi, pval = evaluate_ml(df, "POOLED ")
    evaluate_totals(df, "POOLED ")
    evaluate_a2_picks(df, "POOLED ")

    # Pre-registrations
    print(f"\n{'='*60}")
    print("PRE-REGISTRATION CHECK")
    print(f"{'='*60}")
    diff = eng_ll - sbro_ll
    print(f"  (i) Engine ML LL within 0.012 of close: diff={diff:.4f}, "
          f"{'HELD' if abs(diff) <= 0.012 else 'NOT HELD'}")
    print(f"  (ii) Pooled A1 90% CI includes 0: [{lo:.3f}, {hi:.3f}], "
          f"{'HELD' if lo <= 0 <= hi else 'NOT HELD'}")

    # Regimes
    family = evaluate_regimes(df)

    # R8 pre-registration
    r8_ml = [r for r in family if r["regime"] == "R8_high_pen" and r["market"] == "ML"]
    if r8_ml:
        r8 = r8_ml[0]
        held = r8["coef"] > 0 and r8["lo90"] > 0
        print(f"\n  (iii) R8 ML A1 > 0 with 90% lower > 0: coef={r8['coef']:.3f} "
              f"[{r8['lo90']:.3f}, {r8['hi90']:.3f}], {'HELD' if held else 'NOT HELD'}")
    else:
        print("\n  (iii) R8 not evaluated (insufficient data)")

    # R6 report
    r6_ml = [r for r in family if r["regime"] == "R6_weak_goalies" and r["market"] == "ML"]
    if r6_ml:
        r6 = r6_ml[0]
        print(f"  R6 ML: coef={r6['coef']:.3f} [{r6['lo90']:.3f}, {r6['hi90']:.3f}] p={r6['p']:.4f}")


if __name__ == "__main__":
    main()
