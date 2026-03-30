#!/usr/bin/env python3
"""
NHL Totals Model — Phase 5: Market Architecture + Signal Generation + Grading
=============================================================================
Builds four-layer market architecture and performance report.
Does NOT modify any Phase 1-4 outputs.

Outputs
  nhl/nhl_model_outputs.parquet
  nhl/nhl_market_snapshots.parquet
  nhl/nhl_decisions.parquet
  nhl/nhl_results.parquet
  nhl/nhl_performance_report.txt
"""

from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
NHL_DIR = Path(__file__).parent

SIM_FILE      = NHL_DIR / "nhl_sim_results_calibrated.parquet"
FT_FILE       = NHL_DIR / "nhl_feature_table.parquet"
CANONICAL_CSV = NHL_DIR / "nhl_games_canonical.csv"

OUT_MODEL   = NHL_DIR / "nhl_model_outputs.parquet"
OUT_MARKET  = NHL_DIR / "nhl_market_snapshots.parquet"
OUT_DEC     = NHL_DIR / "nhl_decisions.parquet"
OUT_RESULTS = NHL_DIR / "nhl_results.parquet"
OUT_REPORT  = NHL_DIR / "nhl_performance_report.txt"

THRESHOLD = 0.12
WIN_PER_UNIT = 100.0 / 110.0   # profit per unit at -110

_report_lines: list[str] = []

# ---------------------------------------------------------------------------
def rlog(msg: str = "") -> None:
    _report_lines.append(msg)

def american_to_implied(price: float) -> float:
    if pd.isna(price):
        return np.nan
    return abs(price) / (abs(price) + 100.0) if price < 0 else 100.0 / (100.0 + price)

def edge_bucket_label(edge: float) -> str:
    if pd.isna(edge) or edge < THRESHOLD:
        return "below_threshold"
    if edge < 0.12:
        return "0.10-0.12"
    if edge < 0.15:
        return "0.12-0.15"
    return "0.15+"

def confidence_tier(edge: float, home_confirmed: bool, away_confirmed: bool,
                    vol_bucket: str) -> str:
    if edge >= 0.15 and home_confirmed and away_confirmed and vol_bucket != "high":
        return "HIGH"
    if edge >= 0.12:
        return "MEDIUM"
    return "LOW"

def record_and_roi(df: pd.DataFrame) -> tuple:
    W = int((df["result"] == "WIN").sum())
    L = int((df["result"] == "LOSS").sum())
    P = int((df["result"] == "PUSH").sum())
    total = W + L + P
    if total == 0:
        return 0, 0, 0, np.nan, np.nan
    hit = W / (W + L) if (W + L) > 0 else np.nan
    roi = (W * WIN_PER_UNIT - L) / total * 100
    return W, L, P, hit, roi

def flag_segment(hit: float, n: int) -> str:
    if n < 30 or pd.isna(hit):
        return ""
    if hit >= 0.53:
        return " ← potentially actionable — monitor"
    if hit < 0.48:
        return " ← structural concern"
    return ""

# ---------------------------------------------------------------------------
# Load base data
# ---------------------------------------------------------------------------
def load_data():
    sim = pd.read_parquet(SIM_FILE)
    ft  = pd.read_parquet(FT_FILE)
    can = pd.read_csv(CANONICAL_CSV, usecols=[
        "game_id", "over_price", "under_price",
        "home_goalie_starter", "away_goalie_starter",
    ])
    # Goalie flags from feature table
    ft_flags = ft[["game_id", "home_backup_flag", "away_backup_flag",
                   "home_goalie_b2b", "away_goalie_b2b"]].copy()

    # Fair probs from odds prices
    can["imp_o"] = can["over_price"].apply(american_to_implied)
    can["imp_u"] = can["under_price"].apply(american_to_implied)
    can["vig"]   = can["imp_o"] + can["imp_u"]
    can["fair_over"]  = can["imp_o"] / can["vig"]
    can["fair_under"] = can["imp_u"] / can["vig"]

    # Join everything onto sim
    base = (sim
            .merge(ft_flags, on="game_id", how="left")
            .merge(can,      on="game_id", how="left"))

    # goalie_confirmed = True for all historical (post-game boxscore)
    base["goalie_confirmed_home"] = base["home_goalie_starter"].fillna(True).astype(bool)
    base["goalie_confirmed_away"] = base["away_goalie_starter"].fillna(True).astype(bool)

    print(f"Base data: {len(base):,} rows")
    return base

# ---------------------------------------------------------------------------
# LAYER 1 — Model outputs
# ---------------------------------------------------------------------------
def build_layer1(base: pd.DataFrame) -> pd.DataFrame:
    print("\nBuilding Layer 1: nhl_model_outputs.parquet")
    df = base.copy()

    df["edge_bucket_over"]  = df["edge_over"].apply(edge_bucket_label)
    df["edge_bucket_under"] = df["edge_under"].apply(edge_bucket_label)
    df["line_6_5_caution"]  = (df["closing_total_bucket"] == "6.5").astype(int)

    cols = [
        "game_id", "game_date", "home_team", "away_team", "season_year",
        "lambda_home_calibrated", "lambda_away_calibrated", "lambda_total_calibrated",
        "seasonal_drift",
        "sim_over_prob_closing", "sim_under_prob_closing", "sim_push_prob_closing",
        "closing_total", "closing_total_bucket",
        "edge_over", "edge_under",
        "edge_bucket_over", "edge_bucket_under",
        "volatility_score", "volatility_bucket",
        "goalie_confirmed_home", "goalie_confirmed_away",
        "home_backup_flag", "away_backup_flag",
        "line_6_5_caution",
        "total_goals", "market_available", "split",
    ]
    out = df[cols].copy()
    out.to_parquet(OUT_MODEL, index=False)
    print(f"  Saved: {OUT_MODEL}  ({len(out):,} rows)")
    return df

# ---------------------------------------------------------------------------
# LAYER 2 — Market snapshots
# ---------------------------------------------------------------------------
def build_layer2(base: pd.DataFrame) -> pd.DataFrame:
    print("\nBuilding Layer 2: nhl_market_snapshots.parquet")
    mkt = base[base["market_available"].astype(bool) & base["closing_total"].notna()].copy()

    mkt["opening_total"]  = np.nan    # not captured in historical data
    mkt["line_movement"]  = np.nan    # requires opening line
    mkt["book_source"]    = "DK/FD"   # canonical priority; exact book not stored per-game

    cols = [
        "game_id", "game_date", "home_team", "away_team",
        "closing_total", "closing_total_bucket",
        "over_price", "under_price",
        "opening_total", "line_movement",
        "fair_over", "fair_under",
        "book_source",
    ]
    out = mkt[cols].rename(columns={
        "over_price":  "closing_over_price",
        "under_price": "closing_under_price",
    })
    out.to_parquet(OUT_MARKET, index=False)
    print(f"  Saved: {OUT_MARKET}  ({len(out):,} rows with market lines)")
    return mkt

# ---------------------------------------------------------------------------
# LAYER 3 — Decisions (one row per qualified signal)
# ---------------------------------------------------------------------------
def build_layer3(base: pd.DataFrame) -> pd.DataFrame:
    print("\nBuilding Layer 3: nhl_decisions.parquet")

    rows = []
    for g in base[base["market_available"].astype(bool) &
                  base["closing_total"].notna()].itertuples(index=False):

        home_conf = bool(g.goalie_confirmed_home)
        away_conf = bool(g.goalie_confirmed_away)
        vol_bkt   = str(g.volatility_bucket)

        for side, edge_val, sim_prob, fair_prob in [
            ("OVER",  g.edge_over,  g.sim_over_prob_closing,  g.fair_over),
            ("UNDER", g.edge_under, g.sim_under_prob_closing, g.fair_under),
        ]:
            if pd.isna(edge_val) or edge_val < THRESHOLD:
                continue

            caution = 1 if (side == "OVER" and g.closing_total_bucket == "6.5") else 0
            tier    = confidence_tier(edge_val, home_conf, away_conf, vol_bkt)
            ebkt    = edge_bucket_label(edge_val)

            rows.append({
                "game_id":                    g.game_id,
                "game_date":                  g.game_date,
                "home_team":                  g.home_team,
                "away_team":                  g.away_team,
                "season_year":                g.season_year,
                "split":                      g.split,
                "signal_side":                side,
                "closing_total":              g.closing_total,
                "closing_total_bucket":       g.closing_total_bucket,
                "edge":                       edge_val,
                "edge_bucket":                ebkt,
                "sim_prob":                   sim_prob,
                "fair_prob":                  fair_prob,
                "lambda_total_calibrated":    g.lambda_total_calibrated,
                "lambda_vs_line":             g.lambda_total_calibrated - g.closing_total,
                "volatility_bucket":          vol_bkt,
                "confidence_tier":            tier,
                "caution_flag":               caution,
                "backup_flag_home":           int(g.home_backup_flag),
                "backup_flag_away":           int(g.away_backup_flag),
                "goalie_confirmed_home":      home_conf,
                "goalie_confirmed_away":      away_conf,
                "actual_total_goals_final":   g.total_goals,
            })

    dec = pd.DataFrame(rows)
    dec.to_parquet(OUT_DEC, index=False)
    print(f"  Saved: {OUT_DEC}  ({len(dec):,} signal rows)")
    return dec

# ---------------------------------------------------------------------------
# LAYER 4 — Results and grading
# ---------------------------------------------------------------------------
def build_layer4(dec: pd.DataFrame) -> pd.DataFrame:
    print("\nBuilding Layer 4: nhl_results.parquet")

    def grade(row) -> str:
        act   = row["actual_total_goals_final"]
        line  = row["closing_total"]
        side  = row["signal_side"]
        if pd.isna(act) or pd.isna(line):
            return "UNGRADED"
        if act == line:
            return "PUSH"
        if side == "OVER":
            return "WIN" if act > line else "LOSS"
        else:
            return "WIN" if act < line else "LOSS"

    res = dec.copy()
    res["result"] = res.apply(grade, axis=1)
    res["graded"]  = (res["result"] != "UNGRADED").astype(int)

    res.to_parquet(OUT_RESULTS, index=False)
    print(f"  Saved: {OUT_RESULTS}  ({len(res):,} rows, {res['graded'].sum():,} graded)")
    return res

# ---------------------------------------------------------------------------
# Performance Report
# ---------------------------------------------------------------------------
def write_performance_report(res: pd.DataFrame) -> None:
    print("\nWriting performance report...")

    def section(title: str) -> None:
        rlog()
        rlog("=" * 70)
        rlog(title)
        rlog("=" * 70)

    def sub(title: str) -> None:
        rlog()
        rlog(f"  {title}")
        rlog("  " + "-" * 50)

    def print_record(label: str, df: pd.DataFrame, indent: str = "  ") -> None:
        if len(df) == 0:
            rlog(f"{indent}{label:<30} — no signals")
            return
        W, L, P, hit, roi = record_and_roi(df)
        n = W + L + P
        hit_str = f"{hit:.4f}" if not pd.isna(hit) else "N/A"
        roi_str = f"{roi:+.2f}%" if not pd.isna(roi) else "N/A"
        flg     = flag_segment(hit, n)
        rlog(f"{indent}{label:<30} n={n:>4}  W={W} L={L} P={P}  "
             f"hit={hit_str}  ROI={roi_str}{flg}")

    rlog("NHL TOTALS MODEL — PHASE 5 PERFORMANCE REPORT")
    rlog("=" * 70)
    rlog(f"Signal threshold: edge >= {THRESHOLD:.2f}")
    rlog(f"Juice: -110 (break-even hit rate: 52.38%)")
    rlog(f"Push correction: active for integer lines (6.0 / 7.0)")
    rlog(f"Known caveat: 6.5-line OVERs underpriced ~4pp in validate")
    rlog(f"Graded signals: {res['graded'].sum():,} of {len(res):,} total")

    for split_name in ("validate", "oos"):
        label = "2023-24 (Validate)" if split_name == "validate" else "2024-25 (OOS)"
        section(f"SPLIT: {label}")
        s = res[(res["split"] == split_name) & (res["graded"] == 1)]

        # Overall
        sub("OVERALL")
        print_record("All signals", s)

        # By signal side
        sub("BY SIGNAL SIDE")
        for side in ("OVER", "UNDER"):
            sd = s[s["signal_side"] == side]
            avg_vs_line = sd["lambda_vs_line"].mean() if len(sd) > 0 else np.nan
            print_record(f"{side}", sd)
            if len(sd) > 0:
                rlog(f"  {'':30}   mean(λ_total − line): {avg_vs_line:+.4f}")

        # By closing_total_bucket
        sub("BY CLOSING_TOTAL_BUCKET")
        for bkt in ["5.5", "6.0", "6.5", "other"]:
            print_record(f"Bucket {bkt}", s[s["closing_total_bucket"] == bkt])

        # By edge bucket
        sub("BY EDGE BUCKET")
        for ebkt in ["0.10-0.12", "0.12-0.15", "0.15+"]:
            print_record(f"Edge {ebkt}", s[s["edge_bucket"] == ebkt])

        # By confidence tier
        sub("BY CONFIDENCE TIER")
        for tier in ("HIGH", "MEDIUM", "LOW"):
            print_record(f"Tier {tier}", s[s["confidence_tier"] == tier])

        # By caution flag
        sub("BY CAUTION FLAG (6.5 OVER)")
        print_record("caution_flag=1 (6.5 OVER)", s[s["caution_flag"] == 1])
        print_record("caution_flag=0", s[s["caution_flag"] == 0])

        # By volatility bucket
        sub("BY VOLATILITY BUCKET")
        for vbkt in ("low", "medium", "high"):
            print_record(f"Volatility {vbkt}", s[s["volatility_bucket"] == vbkt])

        # Signal counts summary
        sub("SIGNAL DISTRIBUTION")
        over_n  = int((s["signal_side"] == "OVER").sum())
        under_n = int((s["signal_side"] == "UNDER").sum())
        high_n  = int((s["confidence_tier"] == "HIGH").sum())
        med_n   = int((s["confidence_tier"] == "MEDIUM").sum())
        low_n   = int((s["confidence_tier"] == "LOW").sum())
        caution_n = int((s["caution_flag"] == 1).sum())
        rlog(f"  Total signals:   {len(s)}")
        rlog(f"  OVER / UNDER:    {over_n} / {under_n}")
        rlog(f"  HIGH / MED / LOW:{high_n} / {med_n} / {low_n}")
        rlog(f"  6.5 OVER caution:{caution_n}")

    # Combined OOS + Validate
    section("COMBINED (Validate + OOS)")
    both = res[res["graded"] == 1]
    print_record("All signals", both)
    sub("BY SIGNAL SIDE (combined)")
    for side in ("OVER", "UNDER"):
        print_record(f"{side}", both[both["signal_side"] == side])

    rlog()
    rlog("=" * 70)
    rlog("NOTES")
    rlog("=" * 70)
    rlog("  - OOS hit rates are forward-looking (blind to 2024-25 season during training)")
    rlog("  - Validate hit rates are in-sample relative to calibration layer")
    rlog("  - 6.5-line overs underpriced by ~4pp per Phase 4.5 diagnostic 3D")
    rlog("  - UNDER signals dominate on validate; more balanced on OOS")
    rlog("  - Minimum 30 signals required to flag a segment as actionable")
    rlog("  - ROI = (W * (100/110) − L) / (W+L+P) * 100  [pushes included in denominator]")

    with open(OUT_REPORT, "w") as f:
        f.write("\n".join(_report_lines))
    print(f"  Saved: {OUT_REPORT}")

# ---------------------------------------------------------------------------
def main() -> None:
    print("=" * 70)
    print("NHL Phase 5: Market Architecture + Signal Generation + Grading")
    print("=" * 70)

    base = load_data()
    _    = build_layer1(base)
    _    = build_layer2(base)
    dec  = build_layer3(base)
    res  = build_layer4(dec)
    write_performance_report(res)

    print("\nPhase 5 market architecture complete.")

if __name__ == "__main__":
    main()
