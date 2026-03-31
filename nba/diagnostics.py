#!/usr/bin/env python3
"""
Phase 3 diagnostics — validation residual analysis.

Runs before Phase 4. No model changes made here — analysis only.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd

PRED_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "predictions.parquet")
SEP = "═" * 65


def load_val() -> pd.DataFrame:
    preds = pd.read_parquet(PRED_PATH)
    val = preds[preds["season"] == "2024-25"].copy()
    val["abs_err"] = val["error"].abs()
    print(f"Validation set: {len(val)} games (2024-25)\n")
    return val


# ── 1. MAE + bias by actual_total quintile ────────────────────────────────────

def diag_actual_quintile(val: pd.DataFrame) -> None:
    print(SEP)
    print("  1. MAE & BIAS BY actual_total QUINTILE")
    print(SEP)

    val = val.copy()
    val["actual_q"] = pd.qcut(
        val["actual_total"], q=5,
        labels=["Q1 (low)", "Q2", "Q3", "Q4", "Q5 (high)"]
    )
    tbl = (
        val.groupby("actual_q", observed=True)
        .agg(
            n=("abs_err", "count"),
            actual_mean=("actual_total", "mean"),
            pred_mean=("pred_total", "mean"),
            mae=("abs_err", "mean"),
            bias=("error", "mean"),
        )
    )
    print(f"\n{'Quintile':<12} {'n':>5} {'actual_mean':>12} {'pred_mean':>10} {'MAE':>8} {'Bias':>8}")
    print("-" * 60)
    for q, row in tbl.iterrows():
        flag = "  ⚠" if row["mae"] > 16 else ""
        print(f"   {str(q):<12} {row['n']:>5} {row['actual_mean']:>12.2f} {row['pred_mean']:>10.2f} "
              f"{row['mae']:>8.2f} {row['bias']:>+8.2f}{flag}")

    # Regression-to-mean summary
    low_bias  = tbl.loc["Q1 (low)",  "bias"]
    high_bias = tbl.loc["Q5 (high)", "bias"]
    print(f"\n   Regression-to-mean check: Q1 bias = {low_bias:+.2f}, Q5 bias = {high_bias:+.2f}")
    if low_bias > 1.0 and high_bias < -1.0:
        print("   ⚠  Classic regression-to-mean: model over-predicts low totals, under-predicts high totals")
    else:
        print("   ✓  No strong regression-to-mean pattern")


# ── 2. MAE + bias by proj_total_naive quintile ────────────────────────────────

def diag_proj_quintile(val: pd.DataFrame) -> None:
    print(f"\n{SEP}")
    print("  2. MAE & BIAS BY proj_total_naive QUINTILE")
    print(SEP)

    val = val.copy()
    val["proj_q"] = pd.qcut(
        val["proj_total_naive"], q=5,
        labels=["Q1 (low)", "Q2", "Q3", "Q4", "Q5 (high)"]
    )
    tbl = (
        val.groupby("proj_q", observed=True)
        .agg(
            n=("abs_err", "count"),
            proj_mean=("proj_total_naive", "mean"),
            actual_mean=("actual_total", "mean"),
            mae=("abs_err", "mean"),
            bias=("error", "mean"),
        )
    )
    print(f"\n{'Quintile':<12} {'n':>5} {'proj_mean':>10} {'actual_mean':>12} {'MAE':>8} {'Bias':>8}")
    print("-" * 60)
    for q, row in tbl.iterrows():
        flag = "  ⚠" if row["mae"] > 16 else ""
        print(f"   {str(q):<12} {row['n']:>5} {row['proj_mean']:>10.2f} {row['actual_mean']:>12.2f} "
              f"{row['mae']:>8.2f} {row['bias']:>+8.2f}{flag}")


# ── 3. MAE by team ────────────────────────────────────────────────────────────

def diag_by_team(val: pd.DataFrame) -> None:
    print(f"\n{SEP}")
    print("  3. MAE BY TEAM  (flagged if MAE > 16)")
    print(SEP)

    # Each game contributes to both home and away team
    home_rows = val[["home_team", "abs_err", "error", "actual_total"]].rename(columns={"home_team": "team"})
    away_rows = val[["away_team", "abs_err", "error", "actual_total"]].rename(columns={"away_team": "team"})
    by_team = pd.concat([home_rows, away_rows])

    tbl = (
        by_team.groupby("team")
        .agg(
            n=("abs_err", "count"),
            mae=("abs_err", "mean"),
            bias=("error", "mean"),
            actual_mean=("actual_total", "mean"),
        )
        .sort_values("mae", ascending=False)
    )

    flagged = tbl[tbl["mae"] > 16]
    print(f"\n   {len(flagged)} team(s) with MAE > 16 pts:\n")
    print(f"{'Team':<6} {'n':>5} {'MAE':>8} {'Bias':>8} {'avg_actual':>12}  flag")
    print("-" * 50)
    for team, row in tbl.iterrows():
        flag = "  ⚠  MAE > 16" if row["mae"] > 16 else ""
        print(f"   {team:<6} {row['n']:>5} {row['mae']:>8.2f} {row['bias']:>+8.2f} {row['actual_mean']:>12.2f}{flag}")


# ── 4. Grouped actual totals by schedule context ──────────────────────────────

def diag_schedule_context(val: pd.DataFrame) -> None:
    print(f"\n{SEP}")
    print("  4. GROUPED ACTUAL TOTALS BY SCHEDULE CONTEXT")
    print(SEP)

    print("\n  4a. Home B2B vs non-B2B:")
    g = val.groupby("b2b_flag_home")["actual_total"].agg(n="count", mean="mean", std="std")
    for flag, row in g.iterrows():
        label = "Home B2B" if flag else "Home non-B2B"
        print(f"   {label:<16}  n={row['n']:>4}  actual_mean={row['mean']:.2f}  std={row['std']:.2f}")

    home_b2b_delta = g.loc[True, "mean"] - g.loc[False, "mean"] if True in g.index and False in g.index else None
    if home_b2b_delta is not None:
        sign = "+" if home_b2b_delta > 0 else ""
        print(f"   → Home B2B effect on actual total: {sign}{home_b2b_delta:.2f} pts")
        coef_sign = "positive (+2.48)"
        print(f"   → Ridge coef b2b_flag_home = {coef_sign} — {'AGREES ✓' if home_b2b_delta > 0 else 'DISAGREES ⚠'} with grouped data")

    print("\n  4b. Away B2B vs non-B2B:")
    g = val.groupby("b2b_flag_away")["actual_total"].agg(n="count", mean="mean", std="std")
    for flag, row in g.iterrows():
        label = "Away B2B" if flag else "Away non-B2B"
        print(f"   {label:<16}  n={row['n']:>4}  actual_mean={row['mean']:.2f}  std={row['std']:.2f}")

    away_b2b_delta = g.loc[True, "mean"] - g.loc[False, "mean"] if True in g.index and False in g.index else None
    if away_b2b_delta is not None:
        sign = "+" if away_b2b_delta > 0 else ""
        print(f"   → Away B2B effect on actual total: {sign}{away_b2b_delta:.2f} pts")
        coef_sign = "negative (-0.78)"
        print(f"   → Ridge coef b2b_flag_away = {coef_sign} — {'AGREES ✓' if away_b2b_delta < 0 else 'DISAGREES ⚠'} with grouped data")

    print("\n  4c. Actual total by days_rest_home bucket (0, 1, 2, 3+):")
    val2 = val.copy()
    val2["rest_home_bucket"] = val2["days_rest_home"].clip(upper=3).astype(int).map(
        {0: "0 (B2B)", 1: "1", 2: "2", 3: "3+"}
    )
    g = val2.groupby("rest_home_bucket", sort=False)["actual_total"].agg(n="count", mean="mean")
    for bkt in ["0 (B2B)", "1", "2", "3+"]:
        if bkt in g.index:
            row = g.loc[bkt]
            print(f"   rest_home={bkt:<8}  n={row['n']:>4}  actual_mean={row['mean']:.2f}")

    # Show monotonicity
    vals_by_rest = [g.loc[b, "mean"] if b in g.index else np.nan
                    for b in ["0 (B2B)", "1", "2", "3+"]]
    print(f"   → Trend (0→3+): {' → '.join(f'{v:.1f}' for v in vals_by_rest)}")
    print(f"   → Ridge coef days_rest_home = +2.04 (more rest → higher total)")
    if not np.isnan(vals_by_rest[0]) and not np.isnan(vals_by_rest[-1]):
        raw_delta = vals_by_rest[-1] - vals_by_rest[0]
        print(f"   → Raw grouped delta (3+ minus 0): {raw_delta:+.2f} pts — "
              f"{'AGREES ✓' if raw_delta > 0 else 'DISAGREES ⚠'} with Ridge sign")

    print("\n  4d. Actual total by days_rest_away bucket (0, 1, 2, 3+):")
    val2["rest_away_bucket"] = val2["days_rest_away"].clip(upper=3).astype(int).map(
        {0: "0 (B2B)", 1: "1", 2: "2", 3: "3+"}
    )
    g = val2.groupby("rest_away_bucket", sort=False)["actual_total"].agg(n="count", mean="mean")
    for bkt in ["0 (B2B)", "1", "2", "3+"]:
        if bkt in g.index:
            row = g.loc[bkt]
            print(f"   rest_away={bkt:<8}  n={row['n']:>4}  actual_mean={row['mean']:.2f}")

    vals_by_rest = [g.loc[b, "mean"] if b in g.index else np.nan
                    for b in ["0 (B2B)", "1", "2", "3+"]]
    print(f"   → Trend (0→3+): {' → '.join(f'{v:.1f}' for v in vals_by_rest)}")
    print(f"   → Ridge coef days_rest_away = -1.12 (more away rest → lower total)")
    if not np.isnan(vals_by_rest[0]) and not np.isnan(vals_by_rest[-1]):
        raw_delta = vals_by_rest[-1] - vals_by_rest[0]
        print(f"   → Raw grouped delta (3+ minus 0): {raw_delta:+.2f} pts — "
              f"{'AGREES ✓' if raw_delta < 0 else 'DISAGREES ⚠'} with Ridge sign")


# ── 5. Correlation matrix for pace, rest, B2B features ───────────────────────

def diag_correlations(val: pd.DataFrame) -> None:
    print(f"\n{SEP}")
    print("  5. FEATURE CORRELATION MATRIX  (flagged if |r| > 0.5)")
    print(SEP)

    cols = [
        "home_pace", "away_pace",
        "days_rest_home", "days_rest_away",
        "b2b_flag_home", "b2b_flag_away",
        "games_l7_home", "games_l7_away",
        "home_ortg", "away_ortg",
        "home_drtg", "away_drtg",
    ]
    corr = val[cols].corr()

    flagged_pairs = []
    print(f"\n   Pairs with |r| > 0.5:")
    for i, c1 in enumerate(cols):
        for c2 in cols[i+1:]:
            r = corr.loc[c1, c2]
            if abs(r) > 0.5:
                flagged_pairs.append((c1, c2, r))
                print(f"   ⚠  {c1:<22} × {c2:<22}  r = {r:+.3f}")

    if not flagged_pairs:
        print("   ✓  No pairs exceed |r| = 0.5")

    print(f"\n   Pace × rest/B2B correlations (collinearity check):")
    check_pairs = [
        ("home_pace", "days_rest_home"),
        ("home_pace", "b2b_flag_home"),
        ("home_pace", "games_l7_home"),
        ("away_pace", "days_rest_away"),
        ("away_pace", "b2b_flag_away"),
        ("away_pace", "games_l7_away"),
        ("days_rest_home", "b2b_flag_home"),
        ("days_rest_away", "b2b_flag_away"),
        ("b2b_flag_home", "games_l7_home"),
        ("b2b_flag_away", "games_l7_away"),
        ("home_ortg", "away_ortg"),
        ("home_drtg", "away_drtg"),
        ("home_pace", "away_pace"),
    ]
    for c1, c2 in check_pairs:
        r = corr.loc[c1, c2]
        flag = "  ⚠ HIGH" if abs(r) > 0.5 else ("  ~ moderate" if abs(r) > 0.3 else "")
        print(f"   {c1:<22} × {c2:<22}  r = {r:+.3f}{flag}")


# ── 6. Signal assessment — additional features ────────────────────────────────

def diag_signal_assessment(val: pd.DataFrame) -> None:
    print(f"\n{SEP}")
    print("  6. SIGNAL ASSESSMENT — ADDITIONAL FEATURE CANDIDATES")
    print(SEP)

    # Interaction terms: home_ortg × away_drtg, away_ortg × home_drtg
    val2 = val.copy()
    val2["home_ortg_x_away_drtg"] = val2["home_ortg"] * val2["away_drtg"]
    val2["away_ortg_x_home_drtg"] = val2["away_ortg"] * val2["home_drtg"]
    val2["ortg_sum"]   = val2["home_ortg"] + val2["away_ortg"]
    val2["drtg_sum"]   = val2["home_drtg"] + val2["away_drtg"]
    val2["pace_avg"]   = (val2["home_pace"] + val2["away_pace"]) / 2

    candidates = {
        "home_ortg × away_drtg (interaction)": "home_ortg_x_away_drtg",
        "away_ortg × home_drtg (interaction)": "away_ortg_x_home_drtg",
        "ortg_sum (home+away)":                "ortg_sum",
        "drtg_sum (home+away)":                "drtg_sum",
        "pace_avg":                            "pace_avg",
        "proj_total_naive":                    "proj_total_naive",
    }

    print(f"\n   Pearson r vs actual_total (validation set):\n")
    print(f"   {'Feature':<40} {'r':>8}  {'|r| vs proj_naive':>18}")
    base_r = abs(val2["proj_total_naive"].corr(val2["actual_total"]))
    print("-" * 72)
    for label, col in candidates.items():
        r = val2[col].corr(val2["actual_total"])
        delta = abs(r) - base_r
        marker = "  ↑ stronger" if delta > 0.01 else ("  ≈ similar" if abs(delta) <= 0.01 else "  ↓ weaker")
        print(f"   {label:<40} {r:>+8.4f}  {delta:>+18.4f}{marker}")

    print(f"\n   Data-available feature candidates (no new source required):\n")
    candidates_info = [
        ("Recent scoring form (5-game pts scored)", "HIGH",
         "5-game rolling ORtg is derivable from box_stats; captures hot/cold streaks "
         "vs 15-game window which lags trend changes"),
        ("3PT attempt rate (3PA/FGA)", "MEDIUM",
         "Available in LeagueGameLog (FG3A column). High 3PT rate → higher variance "
         "but also higher ceiling; correlates with pace"),
        ("Free throw rate (FTA/FGA)", "LOW-MEDIUM",
         "Available in LeagueGameLog. FT attempts add possessions; more FTs = slower "
         "pace/more pts per possession — may already be captured by pace"),
        ("home_ortg × away_drtg interaction term", "HIGH",
         "Explicit product: captures non-linear matchup signal. Ridge can only model "
         "additive effects; this term lets it model 'elite offense vs elite defense'"),
        ("away_ortg × home_drtg interaction term", "HIGH",
         "Same as above for the away team's offensive matchup"),
        ("Blended ORtg (5-game) vs (15-game) delta", "MEDIUM",
         "Form delta = rolling5 - rolling15. Positive = team trending up. "
         "Should add directional signal orthogonal to level features"),
    ]

    for i, (name, priority, rationale) in enumerate(candidates_info, 1):
        print(f"   {i}. [{priority}] {name}")
        print(f"      {rationale}\n")

    # Residual autocorrelation by date — is there drift?
    print(f"   Residual drift over season (validation MAE by month):")
    val3 = val.copy()
    val3["month"] = pd.to_datetime(val3["date"]).dt.to_period("M")
    g = val3.groupby("month")["abs_err"].agg(n="count", mae="mean")
    for month, row in g.iterrows():
        bar = "█" * int(row["mae"] / 2)
        print(f"   {str(month):<8}  n={row['n']:>3}  MAE={row['mae']:.2f}  {bar}")


# ── Summary assessment ────────────────────────────────────────────────────────

def summary(val: pd.DataFrame) -> None:
    print(f"\n{SEP}")
    print("  DIAGNOSTIC SUMMARY — ASSESSMENT")
    print(SEP)
    print()


def main():
    val = load_val()

    diag_actual_quintile(val)
    diag_proj_quintile(val)
    diag_by_team(val)
    diag_schedule_context(val)
    diag_correlations(val)
    diag_signal_assessment(val)

    print(f"\n{SEP}\n")


if __name__ == "__main__":
    main()
