#!/usr/bin/env python3
"""
5P Item 2: What is the sim-vs-book gap made of?

Decomposes the sim-vs-book SD(raw) 0.149 on Week 2 receptions into:
- mean error vs spread error
- by position, 2025-season status, team-change status, team pass-attempt error

No engine, usage, table or parameter change. Zero API credits.
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import poisson
from scipy.optimize import brentq

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from nfl.sim.calibration import engine_fingerprint


def fit_poisson_lambda(q_over, line):
    """Fit Poisson lambda from P(X >= ceil(line + 0.5)) = q_over.
    For line=4.5, this is P(X >= 5) = q_over."""
    k = int(line + 0.5)  # e.g. line 4.5 -> k=5

    def f(lam):
        return 1 - poisson.cdf(k - 1, lam) - q_over

    try:
        lam = brentq(f, 0.01, 50.0)
    except ValueError:
        # If q_over is too extreme, use median approximation
        lam = line + 1.0 / 3.0
    return lam


def compute_sim_mean_sd(player_rungs):
    """Compute sim's implied mean and SD from rung probabilities.

    Method: E[X] = sum_{k=1}^{inf} P(X >= k). The picks_log records
    sim_p at line k-0.5 = P(X >= k) for k in {2,3,4,5,6,7}, filtered
    to [0.05, 0.95]. Missing low-end rungs (P > 0.95) are set to 0.975.
    P(X >= 1) is set to 1.0 (virtually all active skill players catch
    at least once per game). Missing high-end rungs (P < 0.05) contribute
    at most 0.025 each; we add one tail term at 0.025.

    E[X^2] = sum_{k=1}^{inf} (2k-1) * P(X >= k).
    Var(X) = E[X^2] - E[X]^2.
    """
    # Build full survival function S(k) for k=1..8
    available = {}
    for _, row in player_rungs.iterrows():
        k = int(row["line"] + 0.5)  # line 1.5 -> k=2, etc.
        available[k] = row["sim_p"]

    S = {}
    # k=1: P(X >= 1) = 1.0
    S[1] = 1.0

    # k=2..7: use available or fill
    for k in range(2, 8):
        if k in available:
            S[k] = available[k]
        elif k < min(available.keys(), default=8):
            # Below lowest available rung: P > 0.95
            S[k] = 0.975
        else:
            # Above highest available rung: P < 0.05
            S[k] = 0.025

    # k=8: tail term
    if 7 in available and available[7] > 0.05:
        S[8] = 0.025  # one more tail term
    else:
        S[8] = 0.0

    mean = sum(S.values())
    e_x2 = sum((2 * k - 1) * S[k] for k in S)
    var = max(e_x2 - mean ** 2, 0.01)  # floor at small positive
    sd = np.sqrt(var)

    return mean, sd, S


def main():
    fp = engine_fingerprint()
    print(f"engine_fingerprint: {fp}")
    assert fp == "02fbcab6e6ed042e"

    # ---- Load inputs ----
    picks = pd.read_parquet(ROOT / "research" / "nfl_sim" / "phase5m_boards" / "picks_log_mac.parquet")
    board = pd.read_parquet(ROOT / "nfl" / "data" / "board" / "week=2026_02" / "nfl_prop_candidates_20260920T1614Z.parquet")
    pbp26 = pd.read_parquet(ROOT / "nfl" / "data" / "pbp" / "pbp_2026.parquet")
    usage = pd.read_parquet(ROOT / "nfl" / "data" / "sim" / "ratings" / "player_usage_weekly.parquet")

    # ---- Receptions: board (two-way) ----
    board_rec = board[(board["two_way"] == True) & (board["market_key"] == "player_receptions")].copy()

    # ---- Receptions: picks_log ----
    rec_picks = picks[picks["family"] == "receptions"].copy()

    # ---- Actuals from PBP 2026 Week 2 ----
    w2 = pbp26[pbp26["week"] == 2]
    completions = w2[(w2["play_type"] == "pass") & (w2["complete_pass"] == 1)]
    actual_rec = completions.groupby("receiver_player_id").size().reset_index(name="actual_receptions")
    actual_rec.rename(columns={"receiver_player_id": "player_id"}, inplace=True)

    # Also get actual rush attempts
    rushes = w2[w2["play_type"] == "run"]
    actual_rush = rushes.groupby("rusher_player_id").size().reset_index(name="actual_rush_att")
    actual_rush.rename(columns={"rusher_player_id": "player_id"}, inplace=True)

    # ---- 2025 season status ----
    u25 = usage[usage["season"] == 2025]
    # Last team in 2025 for each player
    u25_last = u25.sort_values("week").groupby("player_id").agg(
        team_2025=("team", "last"),
        had_2025=("player_id", "count"),
    ).reset_index()
    u25_last["had_2025"] = True

    # ---- QB pass attempt lines (for team pass-attempt error) ----
    board_pass_att = board[(board["two_way"] == True) & (board["market_key"] == "player_pass_attempts")]
    # Map QB pass attempt line to team
    qb_pass_lines = board_pass_att[["player_name", "team", "line"]].rename(
        columns={"line": "qb_pass_att_line"}
    ).drop_duplicates(subset=["team"])

    # ---- Build matched rows ----
    rows = []
    for _, br in board_rec.iterrows():
        pname = br["player_name"]
        bline = br["line"]
        bteam = br["team"]
        bpos = br["position"]

        # Find this player's sim rungs
        pr = rec_picks[rec_picks["player_name"] == pname]
        if len(pr) == 0:
            continue

        pid = pr.iloc[0]["player_id"]

        # Check match at the book's line
        at_line = pr[pr["line"] == bline]
        if len(at_line) == 0:
            # Sim_p was filtered (< 0.05 or > 0.95); estimate from adjacent rungs
            # If bline is above all available rungs, sim_p < 0.05
            # If bline is below all available rungs, sim_p > 0.95
            available_lines = sorted(pr["line"].values)
            if bline < available_lines[0]:
                sim_p_at_line = 0.975  # very high
            elif bline > available_lines[-1]:
                sim_p_at_line = 0.025  # very low
            else:
                # Interpolate between adjacent rungs
                below = pr[pr["line"] < bline].sort_values("line").iloc[-1]
                above = pr[pr["line"] > bline].sort_values("line").iloc[0]
                frac = (bline - below["line"]) / (above["line"] - below["line"])
                sim_p_at_line = below["sim_p"] + frac * (above["sim_p"] - below["sim_p"])
        else:
            sim_p_at_line = at_line.iloc[0]["sim_p"]

        # Sim mean and SD from all available rungs
        sim_mean, sim_sd, surv = compute_sim_mean_sd(pr)

        # Book mean and SD from Poisson fit
        book_lambda = fit_poisson_lambda(br["q_over"], bline)
        book_mean = book_lambda  # Poisson mean = lambda
        book_sd = np.sqrt(book_lambda)  # Poisson SD = sqrt(lambda)

        # Actual receptions
        act = actual_rec[actual_rec["player_id"] == pid]
        actual = int(act["actual_receptions"].iloc[0]) if len(act) > 0 else 0

        # 2025 status
        u_row = u25_last[u25_last["player_id"] == pid]
        had_2025 = len(u_row) > 0
        same_team = False
        if had_2025:
            same_team = u_row.iloc[0]["team_2025"] == bteam

        # Team pass attempt error
        qb_line = qb_pass_lines[qb_pass_lines["team"] == bteam]
        qb_pass_att_line = qb_line.iloc[0]["qb_pass_att_line"] if len(qb_line) > 0 else np.nan

        # Sim team pass attempts: sum of sim_p at rec >= 1 for all players on this team
        # Actually, we don't have that directly. Use the sim's implied team total targets
        # from the picks_log: sum of sim means for all players on this team.
        team_players = rec_picks[rec_picks["player_name"].isin(
            board_rec[board_rec["team"] == bteam]["player_name"]
        )]["player_name"].unique()
        sim_team_rec_total = 0
        for tp in team_players:
            tp_rungs = rec_picks[rec_picks["player_name"] == tp]
            tm, _, _ = compute_sim_mean_sd(tp_rungs)
            sim_team_rec_total += tm

        # Adjusted sim_p: shift sim mean to book line, keep dispersion
        # Method: under Poisson approximation, replace sim lambda with book lambda
        # and compute P(X >= ceil(bline + 0.5))
        k_threshold = int(bline + 0.5)
        adjusted_sim_p = 1 - poisson.cdf(k_threshold - 1, book_lambda)

        # Alternative: non-parametric shift via survival function interpolation
        # Shift = sim_mean - bline. Evaluate S(k + shift) by interpolation.
        shift = sim_mean - bline
        # Interpolate S at k_threshold + shift
        surv_keys = sorted(surv.keys())
        target_k = k_threshold + shift
        if target_k <= surv_keys[0]:
            adjusted_sim_p_np = 1.0
        elif target_k >= surv_keys[-1]:
            adjusted_sim_p_np = 0.0
        else:
            below_k = max(k for k in surv_keys if k <= target_k)
            above_k = min(k for k in surv_keys if k > target_k)
            frac = (target_k - below_k) / (above_k - below_k)
            adjusted_sim_p_np = surv[below_k] + frac * (surv[above_k] - surv[below_k])

        rows.append({
            "player_name": pname,
            "player_id": pid,
            "position": bpos,
            "team": bteam,
            "book_line": bline,
            "book_q_over": br["q_over"],
            "book_mean": book_mean,
            "book_sd": book_sd,
            "sim_p_at_line": sim_p_at_line,
            "sim_mean": sim_mean,
            "sim_sd": sim_sd,
            "actual_receptions": actual,
            "had_2025": had_2025,
            "same_team": same_team,
            "qb_pass_att_line": qb_pass_att_line,
            "sim_team_rec_total": sim_team_rec_total,
            "adjusted_sim_p_np": adjusted_sim_p_np,
            "gap": sim_p_at_line - br["q_over"],
            "mean_error": sim_mean - bline,
        })

    df = pd.DataFrame(rows)
    print(f"Matched rows: {len(df)}")

    # ---- Save parquet ----
    out_path = ROOT / "research" / "nfl_sim" / "phase5p_gap_rows.parquet"
    df.to_parquet(out_path, index=False)
    print(f"Saved {out_path}")

    # ---- Report ----
    print(f"\n{'='*80}")
    print("OVERALL")
    print(f"{'='*80}")
    print(f"  N = {len(df)}")
    print(f"  mean(sim_mean - book_line) = {df['mean_error'].mean():.3f}")
    print(f"  SD(sim_mean - book_line) = {df['mean_error'].std():.3f}")
    print(f"  mean(gap = sim_p - book_q) = {df['gap'].mean():.4f}")
    print(f"  SD(gap) = {df['gap'].std():.4f}")

    # ---- By position ----
    print(f"\n{'='*80}")
    print("BY POSITION")
    print(f"{'='*80}")
    print(f"{'pos':5s} {'n':>4s} {'mean_err':>10s} {'sd_err':>10s} {'mean_gap':>10s} {'sd_gap':>10s}")
    for pos, g in df.groupby("position"):
        print(f"{pos:5s} {len(g):4d} {g['mean_error'].mean():10.3f} {g['mean_error'].std():10.3f} "
              f"{g['gap'].mean():10.4f} {g['gap'].std():10.4f}")

    # ---- By 2025 status ----
    print(f"\n{'='*80}")
    print("BY 2025 SEASON STATUS")
    print(f"{'='*80}")
    print(f"{'status':20s} {'n':>4s} {'mean_err':>10s} {'sd_err':>10s}")
    for label, mask in [("had 2025 season", df["had_2025"]),
                         ("no 2025 season", ~df["had_2025"])]:
        g = df[mask]
        if len(g) > 0:
            print(f"{label:20s} {len(g):4d} {g['mean_error'].mean():10.3f} {g['mean_error'].std():10.3f}")

    # ---- By same team ----
    print(f"\n{'='*80}")
    print("BY SAME TEAM AS 2025")
    print(f"{'='*80}")
    print(f"{'status':20s} {'n':>4s} {'mean_err':>10s} {'sd_err':>10s}")
    had25 = df[df["had_2025"]]
    for label, mask in [("same team", had25["same_team"]),
                         ("changed team", ~had25["same_team"])]:
        g = had25[mask]
        if len(g) > 0:
            print(f"{label:20s} {len(g):4d} {g['mean_error'].mean():10.3f} {g['mean_error'].std():10.3f}")
    no25 = df[~df["had_2025"]]
    if len(no25) > 0:
        print(f"{'no 2025 season':20s} {len(no25):4d} {no25['mean_error'].mean():10.3f} {no25['mean_error'].std():10.3f}")

    # ---- By team pass-attempt error ----
    print(f"\n{'='*80}")
    print("BY TEAM PASS-ATTEMPT ERROR (thirds)")
    print(f"{'='*80}")
    df["team_pass_err"] = df["sim_team_rec_total"] - df["qb_pass_att_line"]
    valid = df[df["qb_pass_att_line"].notna()].copy()
    if len(valid) > 0:
        valid["pass_err_tercile"] = pd.qcut(valid["team_pass_err"], 3, labels=["low", "mid", "high"])
        print(f"{'tercile':10s} {'n':>4s} {'team_pass_err':>14s} {'mean_err':>10s} {'sd_err':>10s}")
        for t, g in valid.groupby("pass_err_tercile", observed=True):
            print(f"{t:10s} {len(g):4d} {g['team_pass_err'].mean():14.1f} "
                  f"{g['mean_error'].mean():10.3f} {g['mean_error'].std():10.3f}")

    # ---- Closer to actual: sim mean vs book line ----
    print(f"\n{'='*80}")
    print("WHO IS CLOSER TO ACTUAL? (MAE)")
    print(f"{'='*80}")
    df["sim_ae"] = (df["sim_mean"] - df["actual_receptions"]).abs()
    df["book_ae"] = (df["book_line"] - df["actual_receptions"]).abs()
    print(f"  Overall: sim MAE = {df['sim_ae'].mean():.3f}, book MAE = {df['book_ae'].mean():.3f}")
    print(f"  Sim closer: {(df['sim_ae'] < df['book_ae']).sum()}, Book closer: {(df['sim_ae'] > df['book_ae']).sum()}, Tied: {(df['sim_ae'] == df['book_ae']).sum()}")

    for pos, g in df.groupby("position"):
        print(f"  {pos}: sim MAE = {g['sim_ae'].mean():.3f}, book MAE = {g['book_ae'].mean():.3f}, n = {len(g)}")

    for label, mask in [("had 2025", df["had_2025"]), ("no 2025", ~df["had_2025"])]:
        g = df[mask]
        if len(g) > 0:
            print(f"  {label}: sim MAE = {g['sim_ae'].mean():.3f}, book MAE = {g['book_ae'].mean():.3f}, n = {len(g)}")

    # ---- Mean vs spread decomposition ----
    print(f"\n{'='*80}")
    print("MEAN vs SPREAD DECOMPOSITION")
    print(f"{'='*80}")
    original_sd = df["gap"].std()
    # Replace sim mean with book line, keep sim dispersion:
    # Use non-parametric shift: adjusted_sim_p_np
    adjusted_gap = df["adjusted_sim_p_np"] - df["book_q_over"]
    adjusted_sd = adjusted_gap.std()
    fraction_removed = 1 - adjusted_sd / original_sd
    print(f"  Original SD(sim_p - book_q): {original_sd:.4f}")
    print(f"  Adjusted SD (mean replaced): {adjusted_sd:.4f}")
    print(f"  Fraction removed: {fraction_removed:.3f} ({fraction_removed*100:.1f}%)")
    print(f"  Interpretation: {'MEAN problem' if fraction_removed > 0.5 else 'SPREAD problem'}")

    # Also check sim SD vs book SD
    print(f"\n  Sim SD (mean across players): {df['sim_sd'].mean():.3f}")
    print(f"  Book SD (Poisson, mean across players): {df['book_sd'].mean():.3f}")
    print(f"  Ratio sim_sd / book_sd: {(df['sim_sd'] / df['book_sd']).mean():.3f}")

    print(f"\nFingerprint at end: {engine_fingerprint()}")


if __name__ == "__main__":
    main()
