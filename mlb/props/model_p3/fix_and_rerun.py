#!/usr/bin/env python3
"""
MLB Props P3 — Fix 1/2/3 + Rerun
Fixes: market_view odds, devig, PA projection.
Then reruns full P3 backtest.
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

def roi_110(hits, n):
    if n == 0: return np.nan
    return (hits * (100/110) - (n - hits)) / n * 100


# ══════════════════════════════════════════════════════════════
# FIX 1 — REBUILD MARKET VIEW WITH ODDS
# ══════════════════════════════════════════════════════════════

def fix1_rebuild_market_view():
    """Rebuild market_view with best_over_odds and best_under_odds."""
    print("FIX 1 — Rebuilding market_view with odds propagation...")

    pl = pd.read_parquet(PROC_DIR / "props_lines.parquet")
    # Need game_pk — merge from props_results
    pr = pd.read_parquet(PROC_DIR / "props_results.parquet")
    gpk = pr[["event_id", "game_pk"]].dropna(subset=["game_pk"]).drop_duplicates(subset="event_id")

    # Also get actual outcomes from props_results (one per event+player+prop)
    actuals = pr.groupby(["event_id", "player_id", "prop_type"]).first()[
        ["actual_value", "over_hit", "under_hit"]
    ].reset_index()

    # Group props_lines by player/event/prop
    grouped = pl.groupby(["event_id", "player_id", "player_name", "prop_type",
                           "game_date", "season"])

    rows = []
    for key, group in grouped:
        event_id, player_id, player_name, prop_type, game_date, season = key

        lines = group["line"].dropna()
        if len(lines) == 0:
            continue

        # Best over: lowest line, get odds from that book
        over_rows = group[group["over_odds"].notna()].copy()
        under_rows = group[group["under_odds"].notna()].copy()

        # Best over line = lowest line (easiest to go over)
        if len(over_rows) > 0:
            best_over_idx = over_rows["line"].idxmin()
            best_over_line = over_rows.loc[best_over_idx, "line"]
            best_over_odds = over_rows.loc[best_over_idx, "over_odds"]
            best_over_book = over_rows.loc[best_over_idx, "bookmaker"]
        else:
            best_over_line = lines.min()
            best_over_odds = np.nan
            best_over_book = ""

        # Best under line = highest line (easiest to go under)
        if len(under_rows) > 0:
            best_under_idx = under_rows["line"].idxmax()
            best_under_line = under_rows.loc[best_under_idx, "line"]
            best_under_odds = under_rows.loc[best_under_idx, "under_odds"]
            best_under_book = under_rows.loc[best_under_idx, "bookmaker"]
        else:
            best_under_line = lines.max()
            best_under_odds = np.nan
            best_under_book = ""

        # Consensus line: also get consensus odds (median book's odds)
        # For over: at consensus line, get median over odds
        consensus_line = round(lines.median(), 1)
        cons_over = group[(group["line"] == consensus_line) & group["over_odds"].notna()]
        cons_under = group[(group["line"] == consensus_line) & group["under_odds"].notna()]
        consensus_over_odds = cons_over["over_odds"].median() if len(cons_over) > 0 else np.nan
        consensus_under_odds = cons_under["under_odds"].median() if len(cons_under) > 0 else np.nan

        rows.append({
            "event_id": event_id,
            "player_id": player_id,
            "player_name": player_name,
            "prop_type": prop_type,
            "game_date": game_date,
            "season": season,
            "consensus_line": consensus_line,
            "consensus_over_odds": consensus_over_odds,
            "consensus_under_odds": consensus_under_odds,
            "best_over_line": best_over_line,
            "best_over_odds": best_over_odds,
            "best_over_book": best_over_book,
            "best_under_line": best_under_line,
            "best_under_odds": best_under_odds,
            "best_under_book": best_under_book,
            "line_std": round(lines.std(), 2) if len(lines) > 1 else 0.0,
            "n_books": group["bookmaker"].nunique(),
        })

    mv = pd.DataFrame(rows)

    # Add game_pk
    mv = mv.merge(gpk, on="event_id", how="left")

    # Add actuals
    mv = mv.merge(actuals, on=["event_id", "player_id", "prop_type"], how="left")

    # Add dataset_split
    SPLIT = {"2023": "TRAIN", "2024": "VALIDATION", "2025": "OOS"}
    mv["dataset_split"] = mv["season"].astype(str).str[:4].map(SPLIT).fillna("OOS")

    mv.to_parquet(PROC_DIR / "props_market_view.parquet", index=False)

    # Verify
    has_over_odds = mv["consensus_over_odds"].notna().sum()
    has_under_odds = mv["consensus_under_odds"].notna().sum()
    print(f"  Market view: {len(mv):,} rows")
    print(f"  consensus_over_odds: {has_over_odds:,}/{len(mv):,} ({has_over_odds/len(mv)*100:.1f}%)")
    print(f"  consensus_under_odds: {has_under_odds:,}/{len(mv):,} ({has_under_odds/len(mv)*100:.1f}%)")
    print(f"  best_over_odds: {mv['best_over_odds'].notna().sum():,} ({mv['best_over_odds'].notna().mean()*100:.1f}%)")
    print(f"  best_under_odds: {mv['best_under_odds'].notna().sum():,} ({mv['best_under_odds'].notna().mean()*100:.1f}%)")

    # Sample 20 rows
    sample = mv[mv["consensus_over_odds"].notna() & mv["consensus_under_odds"].notna()].head(20)
    print(f"\n  Sample (20 rows with valid odds):")
    print(f"  {'player':<22s} {'type':<6s} {'line':>5s} {'ov_odds':>8s} {'un_odds':>8s} {'books':>5s}")
    for _, r in sample.iterrows():
        print(f"  {str(r['player_name'])[:21]:<22s} {r['prop_type']:<6s} {r['consensus_line']:>5.1f} "
              f"{r['consensus_over_odds']:>8.0f} {r['consensus_under_odds']:>8.0f} {r['n_books']:>5.0f}")

    return mv


# ══════════════════════════════════════════════════════════════
# FIX 3 — EMPIRICAL PA BY LINEUP SLOT
# ══════════════════════════════════════════════════════════════

def fix3_empirical_pa():
    """Compute empirical PA by lineup slot from actual data."""
    print("\nFIX 3 — Computing empirical PA by lineup slot...")

    h = pd.read_parquet(DATA_DIR / "hitter_game_logs.parquet")
    starters = h[h["starter_flag"] == 1]

    pa_by_slot = starters.groupby("batting_order_position")["plate_appearances"].mean()
    print(f"  Empirical PA by slot:")
    for slot in range(1, 10):
        print(f"    Slot {slot}: {pa_by_slot.get(slot, 3.5):.2f}")

    # Home vs away
    pa_home = starters[starters["home_away"] == "H"].groupby("batting_order_position")["plate_appearances"].mean()
    pa_away = starters[starters["home_away"] == "A"].groupby("batting_order_position")["plate_appearances"].mean()
    print(f"\n  Home vs Away (slot 1): home={pa_home.get(1, 0):.2f}, away={pa_away.get(1, 0):.2f}")
    print(f"  Home vs Away (slot 9): home={pa_home.get(9, 0):.2f}, away={pa_away.get(9, 0):.2f}")

    return pa_by_slot.to_dict()


# ══════════════════════════════════════════════════════════════
# DEVIG FUNCTIONS (FIX 2)
# ══════════════════════════════════════════════════════════════

def american_to_implied(odds):
    if pd.isna(odds) or odds == 0:
        return np.nan
    if odds > 0:
        return 100 / (odds + 100)
    else:
        return abs(odds) / (abs(odds) + 100)


def devig(over_odds, under_odds):
    """Devig two-way market. Returns (implied_over, implied_under) or (nan, nan)."""
    raw_over = american_to_implied(over_odds)
    raw_under = american_to_implied(under_odds)
    if pd.isna(raw_over) or pd.isna(raw_under):
        return np.nan, np.nan
    total = raw_over + raw_under
    if total <= 0:
        return np.nan, np.nan
    return raw_over / total, raw_under / total


# ══════════════════════════════════════════════════════════════
# PROJECTION ENGINE (same as P3 but with PA fix)
# ══════════════════════════════════════════════════════════════

def build_pitcher_k_projections(pitcher_logs):
    p = pitcher_logs[pitcher_logs["starter_flag"] == 1].copy()
    p["game_date"] = pd.to_datetime(p["game_date"])
    p = p.sort_values(["player_id", "game_date"])

    p["k_per_ip"] = np.where(p["innings_pitched"] > 0, p["strikeouts"] / p["innings_pitched"], 0)
    p["bf_per_ip"] = np.where(p["innings_pitched"] > 0, p["batters_faced"] / p["innings_pitched"], 3.0)

    def sp_rolling(g):
        g = g.copy()
        g["ip_L5"] = g["innings_pitched"].rolling(5, min_periods=3).mean().shift(1)
        g["ip_L10"] = g["innings_pitched"].rolling(10, min_periods=5).mean().shift(1)
        g["ip_szn"] = g["innings_pitched"].expanding(min_periods=3).mean().shift(1)
        g["k_per_ip_L5"] = g["k_per_ip"].rolling(5, min_periods=3).mean().shift(1)
        g["k_per_ip_L10"] = g["k_per_ip"].rolling(10, min_periods=5).mean().shift(1)
        g["k_per_ip_szn"] = g["k_per_ip"].expanding(min_periods=3).mean().shift(1)
        g["bf_per_ip_szn"] = g["bf_per_ip"].expanding(min_periods=3).mean().shift(1)
        g["start_num"] = range(1, len(g) + 1)
        return g

    p = p.groupby(["player_id", "season"], group_keys=False).apply(sp_rolling)

    ip_l10_fill = p["ip_L10"].fillna(p["ip_szn"])
    p["proj_ip"] = pd.Series(np.where(
        p["ip_L5"].notna(),
        0.5 * p["ip_L5"] + 0.3 * ip_l10_fill + 0.2 * p["ip_szn"],
        p["ip_szn"]
    ), index=p.index).fillna(LEAGUE_AVG_IP).clip(2.0, 8.0)

    kl10_fill = p["k_per_ip_L10"].fillna(p["k_per_ip_szn"])
    p["proj_k_rate"] = pd.Series(np.where(
        p["k_per_ip_L5"].notna(),
        0.5 * p["k_per_ip_L5"] + 0.3 * kl10_fill + 0.2 * p["k_per_ip_szn"],
        p["k_per_ip_szn"]
    ), index=p.index).fillna(LEAGUE_AVG_K9 / 9)

    p["proj_k"] = (p["proj_k_rate"] * p["proj_ip"]).clip(0, 18)
    p["bf_per_ip_est"] = p["bf_per_ip_szn"].fillna(4.3)
    p["k_ceiling"] = (p["proj_ip"] * p["bf_per_ip_est"]).clip(6, 35).round().astype(int)

    return p[["game_pk", "player_id", "player_name", "team", "season", "game_date",
              "proj_ip", "proj_k_rate", "proj_k", "k_ceiling", "strikeouts", "innings_pitched"]]


def build_hitter_projections(hitter_logs, empirical_pa):
    h = hitter_logs[hitter_logs["starter_flag"] == 1].copy()
    h["game_date"] = pd.to_datetime(h["game_date"])
    h = h.sort_values(["player_id", "game_date"])

    h["total_bases"] = h["singles"] + 2*h["doubles"] + 3*h["triples"] + 4*h["home_runs"]
    h["hit_rate"] = np.where(h["at_bats"] > 0, h["hits"] / h["at_bats"], 0)
    h["tb_per_pa"] = np.where(h["plate_appearances"] > 0, h["total_bases"] / h["plate_appearances"], 0)
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

        for hand in ["L", "R"]:
            mask = g["opp_pitcher_hand"] == hand
            g_hand = g[mask].copy()
            g[f"hit_rate_vs{hand}"] = np.nan
            g[f"tb_rate_vs{hand}"] = np.nan
            if len(g_hand) > 0:
                cum_h = g_hand["hits"].expanding().sum().shift(1)
                cum_ab = g_hand["at_bats"].expanding().sum().shift(1)
                g.loc[g_hand.index, f"hit_rate_vs{hand}"] = np.where(cum_ab >= 20, cum_h / cum_ab, np.nan)
                g[f"hit_rate_vs{hand}"] = g[f"hit_rate_vs{hand}"].ffill()

                cum_tb = g_hand["total_bases"].expanding().sum().shift(1)
                cum_pa = g_hand["plate_appearances"].expanding().sum().shift(1)
                g.loc[g_hand.index, f"tb_rate_vs{hand}"] = np.where(cum_pa >= 20, cum_tb / cum_pa, np.nan)
                g[f"tb_rate_vs{hand}"] = g[f"tb_rate_vs{hand}"].ffill()
        return g

    h = h.groupby(["player_id", "season"], group_keys=False).apply(hitter_rolling)

    # FIX 3: Empirical PA by lineup slot
    h["expected_pa"] = h["batting_order_position"].map(empirical_pa).fillna(3.8)

    opp_hand = h["opp_pitcher_hand"]
    hl30 = h["hit_rate_L30"].fillna(h["hit_rate_szn"])
    h["platoon_hit_rate"] = pd.Series(np.where(
        (opp_hand == "L") & h["hit_rate_vsL"].notna(), h["hit_rate_vsL"],
        np.where(
            (opp_hand == "R") & h["hit_rate_vsR"].notna(), h["hit_rate_vsR"],
            np.where(h["hit_rate_L15"].notna(),
                      0.5 * h["hit_rate_L15"] + 0.3 * hl30 + 0.2 * h["hit_rate_szn"],
                      h["hit_rate_szn"])
        )
    ), index=h.index).fillna(LEAGUE_AVG_HIT_RATE)
    h["proj_hits"] = h["platoon_hit_rate"] * h["expected_pa"]

    tbl30 = h["tb_per_pa_L30"].fillna(h["tb_per_pa_szn"])
    h["platoon_tb_rate"] = pd.Series(np.where(
        (opp_hand == "L") & h["tb_rate_vsL"].notna(), h["tb_rate_vsL"],
        np.where(
            (opp_hand == "R") & h["tb_rate_vsR"].notna(), h["tb_rate_vsR"],
            np.where(h["tb_per_pa_L15"].notna(),
                      0.5 * h["tb_per_pa_L15"] + 0.3 * tbl30 + 0.2 * h["tb_per_pa_szn"],
                      h["tb_per_pa_szn"])
        )
    ), index=h.index).fillna(LEAGUE_AVG_TB_PER_PA)
    h["proj_tb"] = h["platoon_tb_rate"] * h["expected_pa"]

    for rate in ["single_rate", "double_rate", "triple_rate", "hr_rate", "out_rate"]:
        l30f = h[f"{rate}_L30"].fillna(h[f"{rate}_szn"])
        default = 0.15 if "out" in rate else 0.05
        h[f"proj_{rate}"] = pd.Series(np.where(
            h[f"{rate}_L15"].notna(),
            0.5 * h[f"{rate}_L15"] + 0.3 * l30f + 0.2 * h[f"{rate}_szn"],
            h[f"{rate}_szn"]
        ), index=h.index).fillna(default)

    return h[["game_pk", "player_id", "player_name", "team", "season", "game_date",
              "opp_pitcher_hand", "batting_order_position",
              "expected_pa", "platoon_hit_rate", "proj_hits",
              "platoon_tb_rate", "proj_tb",
              "proj_single_rate", "proj_double_rate", "proj_triple_rate",
              "proj_hr_rate", "proj_out_rate",
              "hits", "total_bases", "plate_appearances"]]


# ══════════════════════════════════════════════════════════════
# DISTRIBUTION FUNCTIONS (same as P3)
# ══════════════════════════════════════════════════════════════

def compute_k_distribution(proj_k, k_ceiling):
    lam = max(0.5, proj_k)
    cap = max(1, int(k_ceiling))
    probs = np.array([scipy_stats.poisson.pmf(k, lam) for k in range(cap + 1)])
    probs = probs / probs.sum()
    return probs

def compute_hits_distribution(expected_pa, hit_prob):
    n = max(1, round(float(expected_pa)))
    p = max(0.01, min(0.5, float(hit_prob)))
    return np.array([scipy_stats.binom.pmf(k, n, p) for k in range(n + 1)])

def compute_tb_distribution(expected_pa, s_rate, d_rate, t_rate, hr_rate, out_rate, n_sims=5000):
    def _safe(v, d):
        try:
            v = float(v)
            return d if np.isnan(v) else v
        except: return d
    try: n = max(1, round(float(expected_pa)))
    except: n = 4
    s_rate, d_rate = _safe(s_rate, 0.15), _safe(d_rate, 0.04)
    t_rate, hr_rate, out_rate = _safe(t_rate, 0.005), _safe(hr_rate, 0.03), _safe(out_rate, 0.65)
    total = s_rate + d_rate + t_rate + hr_rate + out_rate
    if total <= 0: total = 1.0
    weights = np.array([out_rate/total, s_rate/total, d_rate/total, t_rate/total, hr_rate/total])
    weights = np.nan_to_num(weights, nan=0.2)
    weights = np.maximum(weights, 0.001)
    weights = weights / weights.sum()
    rng = np.random.default_rng(42)
    outcomes = rng.choice(np.array([0,1,2,3,4]), size=(n_sims, n), p=weights)
    totals = outcomes.sum(axis=1)
    probs = np.bincount(totals, minlength=int(totals.max()) + 1) / n_sims
    return probs

def prob_over(probs, line):
    threshold = int(np.floor(line)) + 1
    return float(probs[threshold:].sum()) if threshold < len(probs) else 0.0

def prob_under(probs, line):
    threshold = int(np.floor(line))
    return float(probs[:threshold + 1].sum()) if threshold >= 0 else 0.0


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════

def main():
    lines = []
    def log(s=""):
        lines.append(s)
        print(s)

    log("=" * 70)
    log("MLB PROPS P3 — FIXES + RERUN")
    log("=" * 70)
    log()

    # ── FIX 1 ──
    mv = fix1_rebuild_market_view()
    log()

    # ── FIX 3 ──
    empirical_pa = fix3_empirical_pa()
    log()

    # ── FIX 2 verification ──
    log("FIX 2 — Devig verification...")
    has_both_odds = mv["consensus_over_odds"].notna() & mv["consensus_under_odds"].notna()
    pct_valid = has_both_odds.mean() * 100
    log(f"  Plays with valid consensus odds (both sides): {has_both_odds.sum():,}/{len(mv):,} ({pct_valid:.1f}%)")

    if pct_valid < 80:
        log(f"  STOPPING: odds coverage {pct_valid:.1f}% < 80% threshold")
        with open(OUT_DIR / "p3_audit_fixes.txt", "w") as f:
            f.write("\n".join(lines))
        return

    # Sample devig
    sample = mv[has_both_odds].head(10)
    log(f"\n  Sample devigged probabilities:")
    log(f"  {'player':<20s} {'ov_odds':>8s} {'un_odds':>8s} {'imp_ov':>7s} {'imp_un':>7s}")
    for _, r in sample.iterrows():
        io, iu = devig(r["consensus_over_odds"], r["consensus_under_odds"])
        log(f"  {str(r['player_name'])[:19]:<20s} {r['consensus_over_odds']:>8.0f} {r['consensus_under_odds']:>8.0f} {io:>6.1%} {iu:>6.1%}")
    log()

    # ── BUILD PROJECTIONS ──
    log("Building projections...")
    pitcher_logs = pd.read_parquet(DATA_DIR / "pitcher_game_logs.parquet")
    hitter_logs = pd.read_parquet(DATA_DIR / "hitter_game_logs.parquet")

    k_proj = build_pitcher_k_projections(pitcher_logs)
    h_proj = build_hitter_projections(hitter_logs, empirical_pa)
    log(f"  K projections: {len(k_proj):,}")
    log(f"  Hitter projections: {len(h_proj):,}")

    # ── FIX 3 VALIDATION ──
    log("\nFIX 3 VALIDATION — PA accuracy:")
    val_h = h_proj[h_proj["season"] == 2024]
    pa_err = val_h["expected_pa"] - val_h["plate_appearances"]
    log(f"  Projected PA avg: {val_h['expected_pa'].mean():.2f}")
    log(f"  Actual PA avg:    {val_h['plate_appearances'].mean():.2f}")
    log(f"  Delta:            {pa_err.mean():+.3f}")
    log(f"  Correlation:      {val_h['expected_pa'].corr(val_h['plate_appearances']):.4f}")
    log()

    # ── JOIN PROJECTIONS TO MARKET VIEW ──
    log("Joining projections to market...")
    k_market = mv[mv["prop_type"] == "K"].copy()
    k_market["player_id"] = k_market["player_id"].astype("Int64")
    k_market["game_pk"] = k_market["game_pk"].astype("Int64")
    k_proj["player_id"] = k_proj["player_id"].astype("Int64")

    k_joined = k_market.merge(
        k_proj[["game_pk", "player_id", "proj_k", "proj_ip", "k_ceiling", "strikeouts"]],
        on=["game_pk", "player_id"], how="inner")

    hits_market = mv[mv["prop_type"] == "HITS"].copy()
    hits_market["player_id"] = hits_market["player_id"].astype("Int64")
    hits_market["game_pk"] = hits_market["game_pk"].astype("Int64")
    h_proj["player_id"] = h_proj["player_id"].astype("Int64")

    hits_joined = hits_market.merge(
        h_proj[["game_pk", "player_id", "platoon_hit_rate", "expected_pa", "proj_hits", "hits"]],
        on=["game_pk", "player_id"], how="inner")

    tb_market = mv[mv["prop_type"] == "TB"].copy()
    tb_market["player_id"] = tb_market["player_id"].astype("Int64")
    tb_market["game_pk"] = tb_market["game_pk"].astype("Int64")

    tb_joined = tb_market.merge(
        h_proj[["game_pk", "player_id", "platoon_tb_rate", "expected_pa", "proj_tb",
                "proj_single_rate", "proj_double_rate", "proj_triple_rate",
                "proj_hr_rate", "proj_out_rate", "total_bases"]],
        on=["game_pk", "player_id"], how="inner")

    log(f"  K: {len(k_joined):,}, Hits: {len(hits_joined):,}, TB: {len(tb_joined):,}")

    # ── COMPUTE DISTRIBUTIONS + EDGES ──
    log("\nComputing distributions and edges...")

    all_plays = []

    for _, row in k_joined.iterrows():
        probs = compute_k_distribution(row["proj_k"], row["k_ceiling"])
        p_over = prob_over(probs, row["consensus_line"])
        p_under = prob_under(probs, row["consensus_line"])
        imp_over, imp_under = devig(row["consensus_over_odds"], row["consensus_under_odds"])
        missing_odds = pd.isna(imp_over)
        if missing_odds:
            imp_over, imp_under = 0.5, 0.5

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
            "actual_value": row["actual_value"], "n_books": row["n_books"],
            "missing_odds": missing_odds,
        })

    for _, row in hits_joined.iterrows():
        probs = compute_hits_distribution(row["expected_pa"], row["platoon_hit_rate"])
        p_over = prob_over(probs, row["consensus_line"])
        p_under = prob_under(probs, row["consensus_line"])
        imp_over, imp_under = devig(row["consensus_over_odds"], row["consensus_under_odds"])
        missing_odds = pd.isna(imp_over)
        if missing_odds: imp_over, imp_under = 0.5, 0.5

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
            "actual_value": row["actual_value"], "n_books": row["n_books"],
            "missing_odds": missing_odds,
        })

    log("  Computing TB distributions...")
    for _, row in tb_joined.iterrows():
        probs = compute_tb_distribution(
            row["expected_pa"], row["proj_single_rate"], row["proj_double_rate"],
            row["proj_triple_rate"], row["proj_hr_rate"], row["proj_out_rate"])
        p_over = prob_over(probs, row["consensus_line"])
        p_under = prob_under(probs, row["consensus_line"])
        imp_over, imp_under = devig(row["consensus_over_odds"], row["consensus_under_odds"])
        missing_odds = pd.isna(imp_over)
        if missing_odds: imp_over, imp_under = 0.5, 0.5

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
            "actual_value": row["actual_value"], "n_books": row["n_books"],
            "missing_odds": missing_odds,
        })

    plays_df = pd.DataFrame(all_plays)

    # Bet outcomes
    plays_df["bet_win"] = np.where(
        plays_df["lean"] == "OVER",
        (plays_df["actual_value"] > plays_df["line"]).astype(float),
        np.where(plays_df["lean"] == "UNDER",
                  (plays_df["actual_value"] < plays_df["line"]).astype(float), np.nan))

    abs_edge = plays_df["edge"].abs()
    plays_df["edge_bucket"] = np.where(abs_edge >= 0.05, "5%+",
                               np.where(abs_edge >= 0.02, "2-5%",
                               np.where(abs_edge > 0, "0-2%", "NO_PLAY")))

    # Exclude plays with missing odds from edge analysis
    plays_df["valid_odds"] = ~plays_df["missing_odds"]

    plays_df.to_parquet(OUT_DIR / "backtest_results.parquet", index=False)
    plays_df.to_csv(OUT_DIR / "backtest_results.csv", index=False)

    log(f"\n  Total plays: {len(plays_df):,}")
    log(f"  With valid odds: {plays_df['valid_odds'].sum():,} ({plays_df['valid_odds'].mean()*100:.1f}%)")
    log(f"  With outcomes: {plays_df['actual_value'].notna().sum():,}")

    # ══════════════════════════════════════════════════════════
    # SECTION 1 — CORRECTED RESULTS
    # ══════════════════════════════════════════════════════════
    log()
    log("=" * 70)
    log("SECTION 1 — CORRECTED P3 RESULTS")
    log("=" * 70)

    # Filter to valid odds + actionable + has outcome
    for split_label, split_val in [("VALIDATION (2024)", "VALIDATION"), ("OOS (2025)", "OOS")]:
        log(f"\n{split_label}:")
        val = plays_df[(plays_df["dataset_split"] == split_val) &
                        (plays_df["lean"] != "NO_PLAY") &
                        plays_df["bet_win"].notna() &
                        plays_df["valid_odds"]].copy()
        log(f"  Total plays (valid odds): {len(val):,}")

        # By prop type
        log(f"\n  BY PROP TYPE:")
        log(f"  {'Type':<8s} {'N':>6s} {'Hit%':>7s} {'ROI':>8s} {'AvgEdge':>8s}")
        log(f"  {'-'*40}")
        for pt in ["K", "HITS", "TB"]:
            sub = val[val["prop_type"] == pt]
            if len(sub) == 0: continue
            w = sub["bet_win"].sum(); n = len(sub)
            log(f"  {pt:<8s} {n:>6d} {w/n*100:>6.1f}% {roi_110(w,n):>+7.1f}% {sub['edge'].mean():>+7.1%}")

        # OVER vs UNDER
        log(f"\n  BY DIRECTION:")
        for d in ["OVER", "UNDER"]:
            sub = val[val["lean"] == d]
            if len(sub) == 0: continue
            w = sub["bet_win"].sum(); n = len(sub)
            log(f"  {d}: N={n:,}, hit={w/n*100:.1f}%, ROI={roi_110(w,n):+.1f}%")

        # By prop type + direction
        log(f"\n  BY PROP TYPE × DIRECTION:")
        for pt in ["HITS", "TB", "K"]:
            for d in ["OVER", "UNDER"]:
                sub = val[(val["prop_type"] == pt) & (val["lean"] == d)]
                if len(sub) == 0: continue
                w = sub["bet_win"].sum(); n = len(sub)
                log(f"  {pt} {d}: N={n:,}, hit={w/n*100:.1f}%, ROI={roi_110(w,n):+.1f}%")

        # Edge buckets
        log(f"\n  BY EDGE BUCKET:")
        log(f"  {'Bucket':<8s} {'N':>6s} {'Hit%':>7s} {'ROI':>8s}")
        for bucket in ["0-2%", "2-5%", "5%+"]:
            sub = val[val["edge_bucket"] == bucket]
            if len(sub) == 0: continue
            w = sub["bet_win"].sum(); n = len(sub)
            log(f"  {bucket:<8s} {n:>6d} {w/n*100:>6.1f}% {roi_110(w,n):>+7.1f}%")

        # Probability comparison
        log(f"\n  PROBABILITY COMPARISON:")
        log(f"  {'Type':<8s} {'model_p':>8s} {'impl_p':>8s} {'edge':>8s}")
        for pt in ["HITS", "TB", "K"]:
            sub = val[val["prop_type"] == pt]
            if len(sub) == 0: continue
            mp = np.where(sub["lean"]=="OVER", sub["model_prob_over"], sub["model_prob_under"]).mean()
            ip = np.where(sub["lean"]=="OVER", sub["implied_prob_over"], sub["implied_prob_under"]).mean()
            log(f"  {pt:<8s} {mp:>7.1%} {ip:>7.1%} {mp-ip:>+7.1%}")

    # ── SECTION 2 — RECOMMENDATION ──
    log()
    log("=" * 70)
    log("SECTION 2 — PRODUCTION RECOMMENDATION")
    log("=" * 70)
    log()

    val = plays_df[(plays_df["dataset_split"] == "VALIDATION") &
                    (plays_df["lean"] != "NO_PLAY") &
                    plays_df["bet_win"].notna() &
                    plays_df["valid_odds"]].copy()

    for pt in ["K", "HITS", "TB"]:
        sub = val[val["prop_type"] == pt]
        if len(sub) < 50:
            log(f"  {pt}: SKIPPED (N={len(sub)})")
            continue
        w = sub["bet_win"].sum(); n = len(sub)
        val_roi = roi_110(w, n)
        n_ok = n >= 200
        roi_ok = val_roi >= 3.0

        # Monotonicity
        prev = -999; mono = True
        for bucket in ["0-2%", "2-5%", "5%+"]:
            b = sub[sub["edge_bucket"] == bucket]
            if len(b) > 10:
                r = roi_110(b["bet_win"].sum(), len(b))
                if r < prev - 5: mono = False
                prev = r

        if n_ok and roi_ok and mono:
            log(f"  {pt}: READY FOR SHADOW (N={n}, ROI={val_roi:+.1f}%)")
        elif n_ok and val_roi > 0:
            failed = []
            if not roi_ok: failed.append(f"ROI={val_roi:+.1f}%<3%")
            if not mono: failed.append("not monotonic")
            log(f"  {pt}: NEAR-MISS (N={n}, ROI={val_roi:+.1f}%, {', '.join(failed)})")
        else:
            log(f"  {pt}: NOT READY (N={n}, ROI={val_roi:+.1f}%)")

    # ── SECTION 3 — OBSERVATIONS ──
    log()
    log("=" * 70)
    log("SECTION 3 — PATTERN OBSERVATIONS")
    log("=" * 70)
    log()

    log("1. Edge monotonicity with corrected devig:")
    for pt in ["HITS", "TB", "K"]:
        sub = val[val["prop_type"] == pt]
        rois = []
        for bucket in ["0-2%", "2-5%", "5%+"]:
            b = sub[sub["edge_bucket"] == bucket]
            if len(b) > 10: rois.append(f"{bucket}={roi_110(b['bet_win'].sum(), len(b)):+.1f}%")
        if rois: log(f"   {pt}: {', '.join(rois)}")

    log()
    log("2. UNDER asymmetry persistence:")
    for d in ["OVER", "UNDER"]:
        sub = val[val["lean"] == d]
        if len(sub) > 0:
            log(f"   {d}: N={len(sub):,}, ROI={roi_110(sub['bet_win'].sum(), len(sub)):+.1f}%")

    log()
    log("3. True edge magnitude (corrected):")
    for pt in ["HITS", "TB"]:
        sub = val[val["prop_type"] == pt]
        log(f"   {pt}: avg edge = {sub['edge'].mean():+.1%}")

    log()
    log("4. Highest-value P4 refinement:")
    log("   - Opponent K% adjustment for pitcher Ks (currently not competitive)")
    log("   - Park factor adjustment for TB (outdoor vs dome, altitude)")
    log("   - Game total context (high-total games → more PA, more opportunities)")

    # Save
    with open(OUT_DIR / "p3_summary.txt", "w") as f:
        f.write("\n".join(lines))
    with open(OUT_DIR / "p3_audit_fixes.txt", "w") as f:
        f.write("\n".join(lines))

    log()
    log("=" * 70)
    log("Files saved:")
    log(f"  mlb/props/processed/props_market_view.parquet (rebuilt)")
    log(f"  mlb/props/model_p3/backtest_results.parquet")
    log(f"  mlb/props/model_p3/backtest_results.csv")
    log(f"  mlb/props/model_p3/p3_summary.txt")
    log(f"  mlb/props/model_p3/p3_audit_fixes.txt")
    log("=" * 70)


if __name__ == "__main__":
    main()
