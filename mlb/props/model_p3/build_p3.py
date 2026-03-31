#!/usr/bin/env python3
"""
MLB Props Phase P3 — Baseline Model Build
Simple distribution-driven projections for K, Hits, TB.
No ML. No tuning. Just correct distributions.
"""

import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

warnings.filterwarnings("ignore")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR = PROJECT_ROOT / "mlb" / "data"
PROPS_DIR = PROJECT_ROOT / "mlb" / "props"
PROC_DIR = PROPS_DIR / "processed"
OUT_DIR = Path(__file__).resolve().parent

LEAGUE_AVG_K9 = 8.5
LEAGUE_AVG_IP = 5.5
LEAGUE_AVG_HIT_RATE = 0.245
LEAGUE_AVG_TB_PER_PA = 0.38
LEAGUE_AVG_K_PCT_BATTER = 0.224

# Expected PA by lineup slot (empirical from ~4 PA average, top of order gets more)
PA_BY_SLOT = {1: 4.5, 2: 4.4, 3: 4.3, 4: 4.2, 5: 4.1, 6: 4.0, 7: 3.9, 8: 3.8, 9: 3.7, 0: 3.5}


def roi_110(hits, n):
    if n == 0: return np.nan
    return (hits * (100/110) - (n - hits)) / n * 100


# ══════════════════════════════════════════════════════════════
# COMPONENT 1 — PROJECTION ENGINE
# ══════════════════════════════════════════════════════════════

def build_pitcher_k_projections(pitcher_logs, market_view):
    """Project strikeout totals for each pitcher start."""
    print("  Building pitcher K projections...")

    p = pitcher_logs[pitcher_logs["starter_flag"] == 1].copy()
    p["game_date"] = pd.to_datetime(p["game_date"])
    p = p.sort_values(["player_id", "game_date"])

    # Rolling features (shifted = pregame)
    def sp_rolling(g):
        g = g.copy()
        g["ip_L5"] = g["innings_pitched"].rolling(5, min_periods=3).mean().shift(1)
        g["ip_L10"] = g["innings_pitched"].rolling(10, min_periods=5).mean().shift(1)
        g["ip_szn"] = g["innings_pitched"].expanding(min_periods=3).mean().shift(1)

        g["k_per_ip"] = np.where(g["innings_pitched"] > 0,
                                  g["strikeouts"] / g["innings_pitched"], 0)
        g["k_per_ip_L5"] = g["k_per_ip"].rolling(5, min_periods=3).mean().shift(1)
        g["k_per_ip_L10"] = g["k_per_ip"].rolling(10, min_periods=5).mean().shift(1)
        g["k_per_ip_szn"] = g["k_per_ip"].expanding(min_periods=3).mean().shift(1)

        g["bf_per_ip"] = np.where(g["innings_pitched"] > 0,
                                   g["batters_faced"] / g["innings_pitched"], 3.0)
        g["bf_per_ip_szn"] = g["bf_per_ip"].expanding(min_periods=3).mean().shift(1)

        # Days rest
        g["days_rest"] = g["game_date"].diff().dt.days
        g["start_num"] = range(1, len(g) + 1)
        return g

    p = p.groupby(["player_id", "season"], group_keys=False).apply(sp_rolling)

    # Projected IP: weighted blend
    ip_l10_fill = p["ip_L10"].fillna(p["ip_szn"])
    p["proj_ip"] = np.where(
        p["ip_L5"].notna(),
        0.5 * p["ip_L5"] + 0.3 * ip_l10_fill + 0.2 * p["ip_szn"],
        p["ip_szn"]
    )
    p["proj_ip"] = pd.Series(p["proj_ip"]).fillna(LEAGUE_AVG_IP).clip(2.0, 8.0).values

    # Projected K rate
    kl10_fill = p["k_per_ip_L10"].fillna(p["k_per_ip_szn"])
    p["proj_k_rate"] = np.where(
        p["k_per_ip_L5"].notna(),
        0.5 * p["k_per_ip_L5"] + 0.3 * kl10_fill + 0.2 * p["k_per_ip_szn"],
        p["k_per_ip_szn"]
    )
    p["proj_k_rate"] = pd.Series(p["proj_k_rate"]).fillna(LEAGUE_AVG_K9 / 9).values

    # Projected Ks
    p["proj_k"] = (p["proj_k_rate"] * p["proj_ip"]).clip(0, 18)

    # K ceiling: estimated batters faced (physical constraint)
    p["bf_per_ip_est"] = p["bf_per_ip_szn"].fillna(4.3)
    p["k_ceiling"] = (p["proj_ip"] * p["bf_per_ip_est"]).clip(6, 35).round().astype(int)

    return p[["game_pk", "player_id", "player_name", "team", "season", "game_date",
              "proj_ip", "proj_k_rate", "proj_k", "k_ceiling",
              "strikeouts", "innings_pitched", "start_num"]]


def build_hitter_projections(hitter_logs, lineups):
    """Project hits and TB for each hitter-game."""
    print("  Building hitter projections...")

    h = hitter_logs[hitter_logs["starter_flag"] == 1].copy()
    h["game_date"] = pd.to_datetime(h["game_date"])
    h = h.sort_values(["player_id", "game_date"])

    h["total_bases"] = h["singles"] + 2*h["doubles"] + 3*h["triples"] + 4*h["home_runs"]
    h["hit_rate"] = np.where(h["at_bats"] > 0, h["hits"] / h["at_bats"], 0)
    h["tb_per_pa"] = np.where(h["plate_appearances"] > 0,
                               h["total_bases"] / h["plate_appearances"], 0)

    # Per-PA outcome rates for TB distribution
    h["single_rate"] = np.where(h["plate_appearances"] > 0, h["singles"] / h["plate_appearances"], 0)
    h["double_rate"] = np.where(h["plate_appearances"] > 0, h["doubles"] / h["plate_appearances"], 0)
    h["triple_rate"] = np.where(h["plate_appearances"] > 0, h["triples"] / h["plate_appearances"], 0)
    h["hr_rate"] = np.where(h["plate_appearances"] > 0, h["home_runs"] / h["plate_appearances"], 0)
    h["out_rate"] = np.where(h["plate_appearances"] > 0,
                              1 - (h["hits"] + h["walks"] + h["hit_by_pitch"]) / h["plate_appearances"], 0)

    def hitter_rolling(g):
        g = g.copy()
        for stat in ["hit_rate", "tb_per_pa", "single_rate", "double_rate",
                      "triple_rate", "hr_rate", "out_rate"]:
            g[f"{stat}_L15"] = g[stat].rolling(15, min_periods=5).mean().shift(1)
            g[f"{stat}_L30"] = g[stat].rolling(30, min_periods=10).mean().shift(1)
            g[f"{stat}_szn"] = g[stat].expanding(min_periods=5).mean().shift(1)

        # Platoon splits
        for hand in ["L", "R"]:
            mask = g["opp_pitcher_hand"] == hand
            g_hand = g[mask].copy()
            if len(g_hand) > 0:
                g[f"hit_rate_vs{hand}"] = np.nan
                cum_h = g_hand["hits"].expanding().sum().shift(1)
                cum_ab = g_hand["at_bats"].expanding().sum().shift(1)
                vals = np.where(cum_ab >= 20, cum_h / cum_ab, np.nan)
                g.loc[g_hand.index, f"hit_rate_vs{hand}"] = vals
                g[f"hit_rate_vs{hand}"] = g[f"hit_rate_vs{hand}"].ffill()

                g[f"tb_rate_vs{hand}"] = np.nan
                cum_tb = g_hand["total_bases"].expanding().sum().shift(1)
                cum_pa = g_hand["plate_appearances"].expanding().sum().shift(1)
                vals_tb = np.where(cum_pa >= 20, cum_tb / cum_pa, np.nan)
                g.loc[g_hand.index, f"tb_rate_vs{hand}"] = vals_tb
                g[f"tb_rate_vs{hand}"] = g[f"tb_rate_vs{hand}"].ffill()

        return g

    h = h.groupby(["player_id", "season"], group_keys=False).apply(hitter_rolling)

    # Expected PA from lineup slot
    h["expected_pa"] = h["batting_order_position"].map(PA_BY_SLOT).fillna(3.8)

    # Hit projection: platoon-adjusted rate × expected PA
    opp_hand = h["opp_pitcher_hand"]
    hl30_fill = h["hit_rate_L30"].fillna(h["hit_rate_szn"])
    h["platoon_hit_rate"] = pd.Series(np.where(
        (opp_hand == "L") & h["hit_rate_vsL"].notna(), h["hit_rate_vsL"],
        np.where(
            (opp_hand == "R") & h["hit_rate_vsR"].notna(), h["hit_rate_vsR"],
            np.where(h["hit_rate_L15"].notna(),
                      0.5 * h["hit_rate_L15"] + 0.3 * hl30_fill + 0.2 * h["hit_rate_szn"],
                      h["hit_rate_szn"])
        )
    ), index=h.index).fillna(LEAGUE_AVG_HIT_RATE)

    h["proj_hits"] = h["platoon_hit_rate"] * h["expected_pa"]

    # TB projection
    tbl30_fill = h["tb_per_pa_L30"].fillna(h["tb_per_pa_szn"])
    h["platoon_tb_rate"] = pd.Series(np.where(
        (opp_hand == "L") & h["tb_rate_vsL"].notna(), h["tb_rate_vsL"],
        np.where(
            (opp_hand == "R") & h["tb_rate_vsR"].notna(), h["tb_rate_vsR"],
            np.where(h["tb_per_pa_L15"].notna(),
                      0.5 * h["tb_per_pa_L15"] + 0.3 * tbl30_fill + 0.2 * h["tb_per_pa_szn"],
                      h["tb_per_pa_szn"])
        )
    ), index=h.index).fillna(LEAGUE_AVG_TB_PER_PA)

    h["proj_tb"] = h["platoon_tb_rate"] * h["expected_pa"]

    # Outcome rates for TB distribution simulation
    for rate in ["single_rate", "double_rate", "triple_rate", "hr_rate", "out_rate"]:
        col = f"{rate}_L15"
        szn = f"{rate}_szn"
        l30_fill = h[f"{rate}_L30"].fillna(h[szn])
        default = 0.15 if "out" in rate else 0.05
        h[f"proj_{rate}"] = pd.Series(np.where(
            h[col].notna(),
            0.5 * h[col] + 0.3 * l30_fill + 0.2 * h[szn],
            h[szn]
        ), index=h.index).fillna(default)

    return h[["game_pk", "player_id", "player_name", "team", "season", "game_date",
              "opp_pitcher_hand", "batting_order_position",
              "expected_pa", "platoon_hit_rate", "proj_hits",
              "platoon_tb_rate", "proj_tb",
              "proj_single_rate", "proj_double_rate", "proj_triple_rate",
              "proj_hr_rate", "proj_out_rate",
              "hits", "total_bases"]]


# ══════════════════════════════════════════════════════════════
# COMPONENT 2 — DISTRIBUTION LAYER
# ══════════════════════════════════════════════════════════════

def compute_k_distribution(proj_k, k_ceiling):
    """Truncated Poisson for pitcher Ks."""
    lam = max(0.5, proj_k)
    cap = max(1, int(k_ceiling))
    probs = np.array([scipy_stats.poisson.pmf(k, lam) for k in range(cap + 1)])
    probs = probs / probs.sum()  # renormalize
    return probs


def compute_hits_distribution(expected_pa, hit_prob):
    """Binomial for batter hits."""
    n = max(1, round(expected_pa))
    p = max(0.01, min(0.5, hit_prob))
    probs = np.array([scipy_stats.binom.pmf(k, n, p) for k in range(n + 1)])
    return probs


def compute_tb_distribution(expected_pa, s_rate, d_rate, t_rate, hr_rate, out_rate, n_sims=5000):
    """Monte Carlo simulation for total bases."""
    try:
        n = max(1, round(float(expected_pa)))
    except (TypeError, ValueError):
        n = 4
    # Normalize rates
    total = s_rate + d_rate + t_rate + hr_rate + out_rate
    if total <= 0:
        total = 1.0
    # Handle NaN — replace with league-average defaults
    def _safe(v, default):
        try:
            if v is None or (isinstance(v, float) and np.isnan(v)):
                return default
            return float(v)
        except (TypeError, ValueError):
            return default
    s_rate = _safe(s_rate, 0.15)
    d_rate = _safe(d_rate, 0.04)
    t_rate = _safe(t_rate, 0.005)
    hr_rate = _safe(hr_rate, 0.03)
    out_rate = _safe(out_rate, 0.65)
    total = s_rate + d_rate + t_rate + hr_rate + out_rate
    if total <= 0:
        total = 1.0
    weights = np.array([out_rate/total, s_rate/total, d_rate/total, t_rate/total, hr_rate/total])
    weights = np.nan_to_num(weights, nan=0.2)
    weights = np.maximum(weights, 0.001)
    weights = weights / weights.sum()
    bases = np.array([0, 1, 2, 3, 4])

    rng = np.random.default_rng(42)
    outcomes = rng.choice(bases, size=(n_sims, n), p=weights)
    totals = outcomes.sum(axis=1)

    max_tb = int(totals.max()) + 1
    probs = np.bincount(totals, minlength=max_tb) / n_sims
    return probs


def prob_over(probs, line):
    """P(X > line) from discrete distribution."""
    threshold = int(np.floor(line)) + 1
    if threshold >= len(probs):
        return 0.0
    return float(probs[threshold:].sum())


def prob_under(probs, line):
    """P(X < line) from discrete distribution."""
    threshold = int(np.floor(line))
    if threshold < 0:
        return 0.0
    return float(probs[:threshold + 1].sum())


# ══════════════════════════════════════════════════════════════
# COMPONENT 3 — MARKET LAYER
# ══════════════════════════════════════════════════════════════

def american_to_implied(odds):
    """Convert American odds to implied probability."""
    if pd.isna(odds) or odds == 0:
        return 0.5
    if odds > 0:
        return 100 / (odds + 100)
    else:
        return abs(odds) / (abs(odds) + 100)


def devig_two_way(imp_over, imp_under):
    """Remove vig by normalizing two-way market."""
    total = imp_over + imp_under
    if total <= 0:
        return 0.5, 0.5
    return imp_over / total, imp_under / total


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════

def main():
    lines_out = []
    def log(s=""):
        lines_out.append(s)
        print(s)

    log("=" * 70)
    log("MLB PROPS PHASE P3 — BASELINE MODEL BUILD")
    log("=" * 70)
    log()

    # Load data
    pitcher_logs = pd.read_parquet(DATA_DIR / "pitcher_game_logs.parquet")
    hitter_logs = pd.read_parquet(DATA_DIR / "hitter_game_logs.parquet")
    lineups = pd.read_parquet(DATA_DIR / "lineups.parquet")
    market_view = pd.read_parquet(PROC_DIR / "props_market_view.parquet")
    props_results = pd.read_parquet(PROC_DIR / "props_results.parquet")

    log(f"Market view: {len(market_view):,} rows")
    log(f"Props results: {len(props_results):,} rows")
    log()

    # ── Build projections ──
    log("COMPONENT 1 — PROJECTIONS")
    k_proj = build_pitcher_k_projections(pitcher_logs, market_view)
    h_proj = build_hitter_projections(hitter_logs, lineups)
    log(f"  K projections: {len(k_proj):,} starts")
    log(f"  Hitter projections: {len(h_proj):,} starter-games")
    log()

    # ── Match projections to market lines ──
    # K props — game_pk already in market_view from P2 processing
    k_market = market_view[market_view["prop_type"] == "K"].copy()
    k_market["player_id"] = k_market["player_id"].astype("Int64")
    k_market["game_pk"] = k_market["game_pk"].astype("Int64")
    k_proj["player_id"] = k_proj["player_id"].astype("Int64")

    k_joined = k_market.merge(
        k_proj[["game_pk", "player_id", "proj_k", "proj_ip", "k_ceiling", "strikeouts"]],
        on=["game_pk", "player_id"], how="inner"
    )
    log(f"  K market+projection join: {len(k_joined):,} rows")

    # Hits props
    hits_market = market_view[market_view["prop_type"] == "HITS"].copy()
    hits_market["player_id"] = hits_market["player_id"].astype("Int64")
    hits_market["game_pk"] = hits_market["game_pk"].astype("Int64")
    h_proj["player_id"] = h_proj["player_id"].astype("Int64")
    hits_joined = hits_market.merge(
        h_proj[["game_pk", "player_id", "platoon_hit_rate", "expected_pa", "proj_hits", "hits"]],
        on=["game_pk", "player_id"], how="inner"
    )
    log(f"  Hits market+projection join: {len(hits_joined):,} rows")

    # TB props
    tb_market = market_view[market_view["prop_type"] == "TB"].copy()
    tb_market["player_id"] = tb_market["player_id"].astype("Int64")
    tb_market["game_pk"] = tb_market["game_pk"].astype("Int64")
    tb_joined = tb_market.merge(
        h_proj[["game_pk", "player_id", "platoon_tb_rate", "expected_pa", "proj_tb",
                "proj_single_rate", "proj_double_rate", "proj_triple_rate",
                "proj_hr_rate", "proj_out_rate", "total_bases"]],
        on=["game_pk", "player_id"], how="inner"
    )
    log(f"  TB market+projection join: {len(tb_joined):,} rows")
    log()

    # ── COMPONENT 2+3+4: Distributions, market layer, edge ──
    log("COMPONENT 2-4 — Distributions, market, edge...")

    all_plays = []

    # K props
    for _, row in k_joined.iterrows():
        probs = compute_k_distribution(row["proj_k"], row["k_ceiling"])
        p_over = prob_over(probs, row["consensus_line"])
        p_under = prob_under(probs, row["consensus_line"])

        imp_over_raw = american_to_implied(row.get("best_over_odds", -110))
        imp_under_raw = american_to_implied(row.get("best_under_odds", -110))
        imp_over, imp_under = devig_two_way(imp_over_raw, imp_under_raw)

        edge_over = p_over - imp_over
        edge_under = p_under - imp_under

        lean = "OVER" if edge_over > edge_under and edge_over > 0 else \
               "UNDER" if edge_under > 0 else "NO_PLAY"
        edge = edge_over if lean == "OVER" else edge_under if lean == "UNDER" else 0

        all_plays.append({
            "prop_type": "K", "player_id": row["player_id"],
            "player_name": row["player_name"], "game_date": row["game_date"],
            "season": row["season"], "dataset_split": row["dataset_split"],
            "line": row["consensus_line"], "projection": row["proj_k"],
            "model_prob_over": round(p_over, 4), "model_prob_under": round(p_under, 4),
            "implied_prob_over": round(imp_over, 4), "implied_prob_under": round(imp_under, 4),
            "edge_over": round(edge_over, 4), "edge_under": round(edge_under, 4),
            "lean": lean, "edge": round(edge, 4),
            "actual_value": row["actual_value"],
            "n_books": row["n_books"],
        })

    # Hits props
    for _, row in hits_joined.iterrows():
        probs = compute_hits_distribution(row["expected_pa"], row["platoon_hit_rate"])
        p_over = prob_over(probs, row["consensus_line"])
        p_under = prob_under(probs, row["consensus_line"])

        imp_over_raw = american_to_implied(row.get("best_over_odds", -110))
        imp_under_raw = american_to_implied(row.get("best_under_odds", -110))
        imp_over, imp_under = devig_two_way(imp_over_raw, imp_under_raw)

        edge_over = p_over - imp_over
        edge_under = p_under - imp_under
        lean = "OVER" if edge_over > edge_under and edge_over > 0 else \
               "UNDER" if edge_under > 0 else "NO_PLAY"
        edge = edge_over if lean == "OVER" else edge_under if lean == "UNDER" else 0

        all_plays.append({
            "prop_type": "HITS", "player_id": row["player_id"],
            "player_name": row["player_name"], "game_date": row["game_date"],
            "season": row["season"], "dataset_split": row["dataset_split"],
            "line": row["consensus_line"], "projection": row["proj_hits"],
            "model_prob_over": round(p_over, 4), "model_prob_under": round(p_under, 4),
            "implied_prob_over": round(imp_over, 4), "implied_prob_under": round(imp_under, 4),
            "edge_over": round(edge_over, 4), "edge_under": round(edge_under, 4),
            "lean": lean, "edge": round(edge, 4),
            "actual_value": row["actual_value"],
            "n_books": row["n_books"],
        })

    # TB props (with MC simulation)
    log("  Computing TB distributions (Monte Carlo)...")
    for _, row in tb_joined.iterrows():
        probs = compute_tb_distribution(
            row["expected_pa"], row["proj_single_rate"], row["proj_double_rate"],
            row["proj_triple_rate"], row["proj_hr_rate"], row["proj_out_rate"])
        p_over = prob_over(probs, row["consensus_line"])
        p_under = prob_under(probs, row["consensus_line"])

        imp_over_raw = american_to_implied(row.get("best_over_odds", -110))
        imp_under_raw = american_to_implied(row.get("best_under_odds", -110))
        imp_over, imp_under = devig_two_way(imp_over_raw, imp_under_raw)

        edge_over = p_over - imp_over
        edge_under = p_under - imp_under
        lean = "OVER" if edge_over > edge_under and edge_over > 0 else \
               "UNDER" if edge_under > 0 else "NO_PLAY"
        edge = edge_over if lean == "OVER" else edge_under if lean == "UNDER" else 0

        all_plays.append({
            "prop_type": "TB", "player_id": row["player_id"],
            "player_name": row["player_name"], "game_date": row["game_date"],
            "season": row["season"], "dataset_split": row["dataset_split"],
            "line": row["consensus_line"], "projection": row["proj_tb"],
            "model_prob_over": round(p_over, 4), "model_prob_under": round(p_under, 4),
            "implied_prob_over": round(imp_over, 4), "implied_prob_under": round(imp_under, 4),
            "edge_over": round(edge_over, 4), "edge_under": round(edge_under, 4),
            "lean": lean, "edge": round(edge, 4),
            "actual_value": row["actual_value"],
            "n_books": row["n_books"],
        })

    plays_df = pd.DataFrame(all_plays)

    # Compute bet outcomes
    plays_df["bet_win"] = np.where(
        plays_df["lean"] == "OVER",
        (plays_df["actual_value"] > plays_df["line"]).astype(float),
        np.where(
            plays_df["lean"] == "UNDER",
            (plays_df["actual_value"] < plays_df["line"]).astype(float),
            np.nan
        )
    )

    # Edge bucket
    abs_edge = plays_df["edge"].abs()
    plays_df["edge_bucket"] = np.where(abs_edge >= 0.05, "5%+",
                               np.where(abs_edge >= 0.02, "2-5%",
                               np.where(abs_edge > 0, "0-2%", "NO_PLAY")))

    # Save
    plays_df.to_parquet(OUT_DIR / "backtest_results.parquet", index=False)
    plays_df.to_csv(OUT_DIR / "backtest_results.csv", index=False)

    log(f"\n  Total plays: {len(plays_df):,}")
    log(f"  With outcomes: {plays_df['actual_value'].notna().sum():,}")
    log()

    # ══════════════════════════════════════════════════════════
    # REPORTING
    # ══════════════════════════════════════════════════════════

    # ── SECTION 0: Projection quality ──
    log("=" * 70)
    log("SECTION 0 — PROJECTION QUALITY")
    log("=" * 70)
    log()

    for pt, proj_col, actual_col in [("K", "projection", "actual_value"),
                                       ("HITS", "projection", "actual_value"),
                                       ("TB", "projection", "actual_value")]:
        sub = plays_df[(plays_df["prop_type"] == pt) & plays_df["actual_value"].notna()]
        sub = sub.drop_duplicates(subset=["player_id", "game_date", "prop_type"])
        if len(sub) > 0:
            mae = (sub[proj_col] - sub[actual_col]).abs().mean()
            corr = sub[proj_col].corr(sub[actual_col])
            log(f"  {pt}: MAE={mae:.3f}, corr={corr:.4f}, N={len(sub):,}")

    # K ceiling distribution
    if len(k_joined) > 0:
        log(f"\n  K ceiling: mean={k_joined['k_ceiling'].mean():.1f}, "
            f"min={k_joined['k_ceiling'].min()}, max={k_joined['k_ceiling'].max()}")
        log(f"  Projected IP: mean={k_joined['proj_ip'].mean():.2f}")
    log()

    # ── SECTION 1: Calibration ──
    log("=" * 70)
    log("SECTION 1 — DISTRIBUTION CALIBRATION")
    log("=" * 70)
    log()

    actionable = plays_df[(plays_df["lean"] != "NO_PLAY") & plays_df["actual_value"].notna()]
    log("Model P(over) vs actual over rate by bucket:")
    log(f"{'Bucket':<15s} {'N':>6s} {'Model P':>8s} {'Actual':>8s} {'Delta':>8s}")
    log("-" * 50)
    for lo, hi, label in [(0, 0.3, "0-30%"), (0.3, 0.4, "30-40%"), (0.4, 0.5, "40-50%"),
                           (0.5, 0.6, "50-60%"), (0.6, 0.7, "60-70%"), (0.7, 1.01, "70%+")]:
        mask = (actionable["model_prob_over"] >= lo) & (actionable["model_prob_over"] < hi)
        sub = actionable[mask]
        if len(sub) < 10:
            continue
        model_p = sub["model_prob_over"].mean()
        actual_p = (sub["actual_value"] > sub["line"]).mean()
        log(f"{label:<15s} {len(sub):>6d} {model_p:>7.1%} {actual_p:>7.1%} {actual_p-model_p:>+7.1%}")
    log()

    # ── SECTION 2: Validation backtest ──
    log("=" * 70)
    log("SECTION 2 — BACKTEST RESULTS (VALIDATION 2024)")
    log("=" * 70)
    log()

    val = plays_df[(plays_df["dataset_split"] == "VALIDATION") &
                    (plays_df["lean"] != "NO_PLAY") &
                    plays_df["bet_win"].notna()].copy()

    log(f"Total validation plays: {len(val):,}")
    log()

    # By prop type
    log("BY PROP TYPE:")
    log(f"{'Type':<8s} {'N':>6s} {'Hit%':>7s} {'ROI':>8s}")
    log("-" * 30)
    for pt in ["K", "HITS", "TB"]:
        sub = val[val["prop_type"] == pt]
        if len(sub) == 0: continue
        wins = sub["bet_win"].sum()
        n = len(sub)
        log(f"{pt:<8s} {n:>6d} {wins/n*100:>6.1f}% {roi_110(wins,n):>+7.1f}%")
    log()

    # By direction
    log("BY DIRECTION:")
    for d in ["OVER", "UNDER"]:
        sub = val[val["lean"] == d]
        if len(sub) == 0: continue
        wins = sub["bet_win"].sum()
        n = len(sub)
        log(f"  {d}: N={n}, hit={wins/n*100:.1f}%, ROI={roi_110(wins,n):+.1f}%")
    log()

    # By edge bucket
    log("BY EDGE BUCKET:")
    log(f"{'Bucket':<8s} {'N':>6s} {'Hit%':>7s} {'ROI':>8s}")
    log("-" * 30)
    for bucket in ["0-2%", "2-5%", "5%+"]:
        sub = val[val["edge_bucket"] == bucket]
        if len(sub) == 0: continue
        wins = sub["bet_win"].sum()
        n = len(sub)
        log(f"{bucket:<8s} {n:>6d} {wins/n*100:>6.1f}% {roi_110(wins,n):>+7.1f}%")
    log()

    # Combined best plays
    log("COMBINED BEST PLAYS:")
    for min_e in [0.03, 0.05]:
        sub = val[val["edge"] >= min_e]
        if len(sub) == 0: continue
        wins = sub["bet_win"].sum()
        n = len(sub)
        log(f"  edge >= {min_e:.0%}: N={n}, hit={wins/n*100:.1f}%, ROI={roi_110(wins,n):+.1f}%")
    log()

    # ── SECTION 3: OOS ──
    log("=" * 70)
    log("SECTION 3 — OOS RESULTS (2025)")
    log("=" * 70)
    log()

    oos = plays_df[(plays_df["dataset_split"] == "OOS") &
                    (plays_df["lean"] != "NO_PLAY") &
                    plays_df["bet_win"].notna()].copy()

    if len(oos) > 100:
        log(f"OOS plays: {len(oos):,}")
        for pt in ["K", "HITS", "TB"]:
            sub = oos[oos["prop_type"] == pt]
            if len(sub) == 0: continue
            wins = sub["bet_win"].sum()
            n = len(sub)
            log(f"  {pt}: N={n}, hit={wins/n*100:.1f}%, ROI={roi_110(wins,n):+.1f}%")
        log()
        for min_e in [0.03, 0.05]:
            sub = oos[oos["edge"] >= min_e]
            if len(sub) > 0:
                wins = sub["bet_win"].sum()
                log(f"  edge >= {min_e:.0%}: N={len(sub)}, ROI={roi_110(wins,len(sub)):+.1f}%")
    else:
        log(f"OOS plays: {len(oos)} (insufficient for analysis)")
    log()

    # ── SECTION 4: Recommendation ──
    log("=" * 70)
    log("SECTION 4 — PRODUCTION RECOMMENDATION")
    log("=" * 70)
    log()

    for pt in ["K", "HITS", "TB"]:
        sub_val = val[val["prop_type"] == pt]
        if len(sub_val) < 50:
            log(f"  {pt}: SKIPPED (N={len(sub_val)} < 200)")
            continue
        wins = sub_val["bet_win"].sum()
        n = len(sub_val)
        val_roi = roi_110(wins, n)
        n_ok = n >= 200
        roi_ok = val_roi >= 3.0

        # Monotonicity check
        mono = True
        prev_roi = -999
        for bucket in ["0-2%", "2-5%", "5%+"]:
            b_sub = sub_val[sub_val["edge_bucket"] == bucket]
            if len(b_sub) > 10:
                b_roi = roi_110(b_sub["bet_win"].sum(), len(b_sub))
                if b_roi < prev_roi - 5:
                    mono = False
                prev_roi = b_roi

        if n_ok and roi_ok and mono:
            log(f"  {pt}: READY FOR SHADOW (N={n}, ROI={val_roi:+.1f}%)")
        elif n_ok and val_roi > 0:
            log(f"  {pt}: NEAR-MISS (N={n}, ROI={val_roi:+.1f}%, "
                f"{'monotonic' if mono else 'not monotonic'})")
        else:
            log(f"  {pt}: NOT READY (N={n}, ROI={val_roi:+.1f}%)")
    log()

    # ── SECTION 5: Observations ──
    log("=" * 70)
    log("SECTION 5 — PATTERN OBSERVATIONS")
    log("=" * 70)
    log()

    # Best prop type
    best_pt = None
    best_roi = -999
    for pt in ["K", "HITS", "TB"]:
        sub = val[val["prop_type"] == pt]
        if len(sub) > 50:
            r = roi_110(sub["bet_win"].sum(), len(sub))
            if r > best_roi:
                best_roi = r
                best_pt = pt

    log(f"1. Strongest prop type: {best_pt} (ROI={best_roi:+.1f}% on validation)")
    log()

    # Edge monotonicity
    log("2. Edge monotonicity:")
    for pt in ["K", "HITS", "TB"]:
        sub = val[val["prop_type"] == pt]
        rois = []
        for bucket in ["0-2%", "2-5%", "5%+"]:
            b = sub[sub["edge_bucket"] == bucket]
            if len(b) > 10:
                rois.append((bucket, roi_110(b["bet_win"].sum(), len(b))))
        if rois:
            log(f"   {pt}: {', '.join(f'{b}={r:+.1f}%' for b, r in rois)}")
    log()

    # Direction
    log("3. OVER vs UNDER:")
    for d in ["OVER", "UNDER"]:
        sub = val[val["lean"] == d]
        if len(sub) > 0:
            log(f"   {d}: N={len(sub)}, ROI={roi_110(sub['bet_win'].sum(), len(sub)):+.1f}%")
    log()

    log("4. Single highest-value refinement for P4:")
    log("   - Opponent-adjusted K rates (pitcher vs specific team K tendency)")
    log("   - Park factor adjustment for TB")
    log("   - Innings projection improvement (the critical bottleneck for K props)")
    log()

    # Save
    with open(OUT_DIR / "p3_summary.txt", "w") as f:
        f.write("\n".join(lines_out))

    # Save projections
    proj_data = pd.concat([
        k_proj[["game_pk","player_id","player_name","season","game_date","proj_k","proj_ip","k_ceiling","strikeouts"]].rename(
            columns={"proj_k":"projection","strikeouts":"actual_value"}).assign(prop_type="K"),
        h_proj[["game_pk","player_id","player_name","season","game_date","proj_hits","hits"]].rename(
            columns={"proj_hits":"projection","hits":"actual_value"}).assign(prop_type="HITS"),
        h_proj[["game_pk","player_id","player_name","season","game_date","proj_tb","total_bases"]].rename(
            columns={"proj_tb":"projection","total_bases":"actual_value"}).assign(prop_type="TB"),
    ], ignore_index=True)
    proj_data.to_parquet(OUT_DIR / "projections.parquet", index=False)

    log()
    log("=" * 70)
    log("Files saved:")
    log(f"  mlb/props/model_p3/projections.parquet")
    log(f"  mlb/props/model_p3/backtest_results.parquet")
    log(f"  mlb/props/model_p3/backtest_results.csv")
    log(f"  mlb/props/model_p3/p3_summary.txt")
    log("=" * 70)


if __name__ == "__main__":
    main()
