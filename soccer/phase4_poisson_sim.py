#!/usr/bin/env python3
"""
Phase 4: Poisson Simulation.

Reads lambda_home_calibrated and lambda_away_calibrated from
soccer_model_outputs.parquet. Runs 50,000 independent Poisson
simulations per match (home and away drawn SEPARATELY).
Computes P(over/under) for 1.5, 2.5, and 3.5 goal lines.

Memory management: processes in batches of BATCH_SIZE games
to avoid 3+ GB peak allocation from int64 Poisson draws.
Each batch clips to uint8 (0-10) immediately after drawing.

Usage:
    python3 -m soccer.phase4_poisson_sim
"""

import io
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)

import numpy as np
import pandas as pd

from soccer.config import DATA_DIR

logger = logging.getLogger(__name__)

MODEL_OUTPUTS_PATH = os.path.join(DATA_DIR, "soccer_model_outputs.parquet")
SIM_OUTPUTS_PATH   = os.path.join(DATA_DIR, "soccer_simulation_outputs.parquet")
AUDIT_PATH         = os.path.join(os.path.dirname(DATA_DIR), "phase4_sim_audit.txt")

N_SIMS     = 50_000
MAX_GOALS  = 10
BATCH_SIZE = 512    # games per batch; 512×50000×8 bytes ≈ 200 MB peak (int64)
SEED       = 42

SEP  = "═" * 72
SEP2 = "─" * 72


# ─────────────────────────────────────────────────────────────────────────────
# Simulation
# ─────────────────────────────────────────────────────────────────────────────

def simulate_all(
    lambda_home: np.ndarray,
    lambda_away: np.ndarray,
    n_sims: int = N_SIMS,
    seed: int   = SEED,
) -> dict:
    """
    Simulate home and away goals separately for N matches × n_sims.

    Returns dict of arrays, each of length N:
        simulated_mean_home, simulated_mean_away, simulated_mean_total
        P_over_1_5, P_over_2_5, P_over_3_5
        P_under_1_5, P_under_2_5, P_under_3_5
        score_00_freq, score_10_or_01_freq, score_11_freq  (for audit only)
        per_game_sim_std                                    (for audit only)
    """
    N   = len(lambda_home)
    rng = np.random.default_rng(seed)

    # Pre-allocate output arrays
    sim_mean_home  = np.empty(N, dtype=np.float32)
    sim_mean_away  = np.empty(N, dtype=np.float32)
    sim_mean_total = np.empty(N, dtype=np.float32)
    p_over_15      = np.empty(N, dtype=np.float32)
    p_over_25      = np.empty(N, dtype=np.float32)
    p_over_35      = np.empty(N, dtype=np.float32)
    per_game_std   = np.empty(N, dtype=np.float32)
    score_00       = np.empty(N, dtype=np.float32)
    score_10_01    = np.empty(N, dtype=np.float32)
    score_11       = np.empty(N, dtype=np.float32)

    n_batches = (N + BATCH_SIZE - 1) // BATCH_SIZE

    for b in range(n_batches):
        lo = b * BATCH_SIZE
        hi = min(lo + BATCH_SIZE, N)
        bs = hi - lo   # actual batch size

        lh = lambda_home[lo:hi]   # (bs,)
        la = lambda_away[lo:hi]   # (bs,)

        # Draw separately — NEVER combine into a single Poisson
        # Shape: (bs, n_sims). Generate int64 then clip+cast to uint8 immediately.
        h_draws = np.clip(
            rng.poisson(lam=lh[:, None], size=(bs, n_sims)),
            0, MAX_GOALS
        ).astype(np.uint8)

        a_draws = np.clip(
            rng.poisson(lam=la[:, None], size=(bs, n_sims)),
            0, MAX_GOALS
        ).astype(np.uint8)

        # total: uint8 max = 20 (10+10) — fits comfortably
        t_draws = h_draws.astype(np.uint16) + a_draws.astype(np.uint16)

        sim_mean_home[lo:hi]  = h_draws.mean(axis=1)
        sim_mean_away[lo:hi]  = a_draws.mean(axis=1)
        sim_mean_total[lo:hi] = t_draws.mean(axis=1)
        per_game_std[lo:hi]   = t_draws.std(axis=1)

        p_over_15[lo:hi] = (t_draws > 1).mean(axis=1)   # > 1.5 ↔ ≥ 2
        p_over_25[lo:hi] = (t_draws > 2).mean(axis=1)   # > 2.5 ↔ ≥ 3
        p_over_35[lo:hi] = (t_draws > 3).mean(axis=1)   # > 3.5 ↔ ≥ 4

        # Score frequencies (audit)
        score_00[lo:hi]    = ((h_draws == 0) & (a_draws == 0)).mean(axis=1)
        score_10_01[lo:hi] = (
            ((h_draws == 1) & (a_draws == 0)) |
            ((h_draws == 0) & (a_draws == 1))
        ).mean(axis=1)
        score_11[lo:hi] = ((h_draws == 1) & (a_draws == 1)).mean(axis=1)

        if b % 4 == 0:
            logger.info(f"  Batch {b+1}/{n_batches} ({lo}–{hi})")

    return {
        "simulated_mean_home":    sim_mean_home,
        "simulated_mean_away":    sim_mean_away,
        "simulated_mean_total":   sim_mean_total,
        "P_over_1_5":             p_over_15,
        "P_under_1_5":            1.0 - p_over_15,
        "P_over_2_5":             p_over_25,
        "P_under_2_5":            1.0 - p_over_25,
        "P_over_3_5":             p_over_35,
        "P_under_3_5":            1.0 - p_over_35,
        "_per_game_std":          per_game_std,
        "_score_00":              score_00,
        "_score_10_01":           score_10_01,
        "_score_11":              score_11,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Diagnostics
# ─────────────────────────────────────────────────────────────────────────────

def run_audit(df: pd.DataFrame, buf: io.StringIO) -> bool:
    """
    Run all Phase 4 diagnostics. Write to buf + stdout.
    Returns True if all checks pass.
    """
    all_pass = True

    def p(s=""):
        print(s, file=buf)
        print(s)

    def flag(cond, pass_msg="PASS", fail_msg=None):
        nonlocal all_pass
        if cond:
            return "PASS"
        else:
            all_pass = False
            return fail_msg or "FAIL"

    p(SEP)
    p("  PHASE 4 SIMULATION AUDIT")
    p(SEP)
    p(f"  Total rows: {len(df):,}  |  N_SIMS={N_SIMS:,}  |  MAX_GOALS={MAX_GOALS}")
    p()

    val = df[df["split"] == "validate"]

    # ── Diag 1: Mean check — simulated_mean_total vs lambda_total_calibrated ──
    p(f"  DIAGNOSTIC 1: simulated_mean_total vs lambda_total_calibrated")
    p(f"  {SEP2[:60]}")
    p(f"  Tolerance: ±0.05 per game")
    diff = (df["simulated_mean_total"] - df["lambda_total_calibrated"]).abs()
    violations = (diff > 0.05).sum()
    max_diff   = diff.max()
    mean_diff  = diff.mean()
    ok = flag(violations == 0)
    p(f"  Max  |sim_mean − lambda_cal|:  {max_diff:.6f}")
    p(f"  Mean |sim_mean − lambda_cal|:  {mean_diff:.6f}")
    p(f"  Violations (>0.05):            {violations}  →  {ok}")
    p()

    # ── Diag 2: Probability sanity ranges (validate) ──────────────────────────
    p(f"  DIAGNOSTIC 2: Probability sanity ranges (validate set, n={len(val)})")
    p(f"  {SEP2[:60]}")
    expected = {
        "P_over_1_5": (0.70, 0.80),
        "P_over_2_5": (0.45, 0.55),
        "P_over_3_5": (0.20, 0.30),
    }
    p(f"  {'Line':<14} {'mean_P':>8}  {'expected range':<22}  check")
    p(f"  {'-'*52}")
    for col, (lo, hi) in expected.items():
        mean_p = val[col].mean()
        # Allow ±5pp slack around expected range
        in_range = (lo - 0.05) <= mean_p <= (hi + 0.05)
        ok = flag(in_range)
        p(f"  {col:<14} {mean_p:>8.4f}  [{lo:.2f}–{hi:.2f}] (±0.05 slack)  {ok}")
    p()

    # ── Diag 3: Score distribution check (validate) ───────────────────────────
    p(f"  DIAGNOSTIC 3: Simulated score distribution (validate set)")
    p(f"  {SEP2[:60]}")
    p(f"  {'Score':<12} {'sim_freq':>10}  {'expected':>12}  check")
    p(f"  {'-'*48}")
    checks = [
        ("0-0",         "_score_00",     0.07, 0.09),
        ("1-0 + 0-1",   "_score_10_01",  0.10, 0.13),
        ("1-1",         "_score_11",     0.10, 0.12),
    ]
    for label, col, lo, hi in checks:
        freq = val[col].mean()
        # Allow ±3pp slack
        in_range = (lo - 0.03) <= freq <= (hi + 0.03)
        ok = flag(in_range)
        p(f"  {label:<12} {freq:>10.4f}  [{lo:.2f}–{hi:.2f}] (±0.03 slack)  {ok}")
    p()

    # ── Diag 4: Variance check (validate) ────────────────────────────────────
    p(f"  DIAGNOSTIC 4: Variance check (validate set)")
    p(f"  {SEP2[:60]}")
    actual_std = val["actual_total_goals"].std()
    mean_sim_std = val["_per_game_std"].mean()   # mean per-game Poisson std
    diff_std = abs(mean_sim_std - actual_std)
    ok = flag(diff_std <= 0.20)
    p(f"  std(actual total_goals):            {actual_std:.4f}")
    p(f"  mean per-game sim std (Poisson σ):  {mean_sim_std:.4f}")
    p(f"  Difference:                         {diff_std:.4f}  (threshold 0.20)  →  {ok}")
    p(f"  Note: per-game sim std = sqrt(λ_total) by Poisson theory.")
    p(f"        Actual cross-game std reflects outcome variation across matches.")
    p()

    # ── Diag 5: Calibration by line (validate, market_available) ─────────────
    p(f"  DIAGNOSTIC 5: Directional calibration by line (validate, market_available=True)")
    p(f"  {SEP2[:60]}")
    val_mkt = val[val["market_available"] == True]
    p(f"  Validate rows with market data: {len(val_mkt)}")
    p()
    for label, line in [("2.5", 2.5), ("1.5", 1.5), ("3.5", 3.5)]:
        col = f"P_over_{label.replace('.','_')}"
        under_games = val_mkt[val_mkt["actual_total_goals"] < line]
        over_games  = val_mkt[val_mkt["actual_total_goals"] > line]
        p_under_gp  = under_games[col].mean() if len(under_games) else np.nan
        p_over_gp   = over_games[col].mean()  if len(over_games)  else np.nan
        ok_under = flag(np.isnan(p_under_gp) or p_under_gp < 0.50, fail_msg=f"FAIL (under-games mean P_over={p_under_gp:.4f} ≥ 0.50)")
        ok_over  = flag(np.isnan(p_over_gp)  or p_over_gp  > 0.50, fail_msg=f"FAIL (over-games mean P_over={p_over_gp:.4f} ≤ 0.50)")
        p(f"  Line {label}:")
        p(f"    actual < {label}: n={len(under_games):>4}  mean P_over = {p_under_gp:.4f}  should be < 0.50  →  {ok_under}")
        p(f"    actual > {label}: n={len(over_games):>4}  mean P_over = {p_over_gp:.4f}  should be > 0.50  →  {ok_over}")
    p()

    # ── Diag 6: Probability symmetry ─────────────────────────────────────────
    p(f"  DIAGNOSTIC 6: Probability symmetry (P_over + P_under = 1.000)")
    p(f"  {SEP2[:60]}")
    for line in ["1_5", "2_5", "3_5"]:
        total = df[f"P_over_{line}"] + df[f"P_under_{line}"]
        violations = ((total - 1.0).abs() > 1e-5).sum()
        ok = flag(violations == 0)
        p(f"  Line {line}: max deviation = {(total-1.0).abs().max():.2e}  "
          f"violations = {violations}  →  {ok}")
    p()

    # ── Summary ───────────────────────────────────────────────────────────────
    p(SEP2)
    p(f"  Phase 4 audit: {'ALL CHECKS PASSED' if all_pass else 'ONE OR MORE CHECKS FAILED'}")
    p()

    return all_pass


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    # ── Load model outputs ────────────────────────────────────────────────────
    mo = pd.read_parquet(MODEL_OUTPUTS_PATH)
    logger.info(f"Model outputs: {len(mo):,} rows")

    lh = mo["lambda_home_calibrated"].values.astype(np.float64)
    la = mo["lambda_away_calibrated"].values.astype(np.float64)

    # ── Run simulation ────────────────────────────────────────────────────────
    logger.info(f"Running {N_SIMS:,} simulations × {len(mo):,} games (batches of {BATCH_SIZE})...")
    sims = simulate_all(lh, la, n_sims=N_SIMS, seed=SEED)
    logger.info("Simulation complete.")

    # ── Build output DataFrame ────────────────────────────────────────────────
    base_cols = [
        "game_id", "game_date", "league_id", "home_team", "away_team",
        "split", "sample_weight",
        "lambda_home_calibrated", "lambda_away_calibrated", "lambda_total_calibrated",
        "actual_home_goals", "actual_away_goals", "actual_total_goals",
    ]
    # market_available lives in the feature table, not model outputs — join it in
    ft = pd.read_parquet(os.path.join(DATA_DIR, "soccer_feature_table.parquet"),
                         columns=["game_id", "market_available"])
    mo = mo.merge(ft, on="game_id", how="left")
    output_cols = base_cols + ["market_available"]
    out = mo[output_cols].copy()

    # Simulation outputs (keep float32 for parquet efficiency)
    pub_keys = [
        "simulated_mean_home", "simulated_mean_away", "simulated_mean_total",
        "P_over_1_5", "P_under_1_5",
        "P_over_2_5", "P_under_2_5",
        "P_over_3_5", "P_under_3_5",
    ]
    for k in pub_keys:
        out[k] = sims[k].astype(np.float32)

    # Audit-only columns (prefixed with _; kept in parquet for reproducibility)
    for k in ["_per_game_std", "_score_00", "_score_10_01", "_score_11"]:
        out[k] = sims[k].astype(np.float32)

    # ── Diagnostics ───────────────────────────────────────────────────────────
    buf = io.StringIO()
    audit_pass = run_audit(out, buf)

    audit_text = buf.getvalue()
    with open(AUDIT_PATH, "w") as f:
        f.write(audit_text)
    logger.info(f"Audit saved → {AUDIT_PATH}")

    # Drop audit-only columns from saved parquet (keep output clean)
    audit_only = [c for c in out.columns if c.startswith("_")]
    out_save = out.drop(columns=audit_only)
    out_save.to_parquet(SIM_OUTPUTS_PATH, index=False)
    logger.info(f"Simulation outputs → {SIM_OUTPUTS_PATH}  ({len(out_save):,} rows × {len(out_save.columns)} cols)")

    print(f"\n  Simulation outputs: {SIM_OUTPUTS_PATH}")
    print(f"  Audit:              {AUDIT_PATH}")
    print(f"  Audit result:       {'PASS' if audit_pass else 'FAIL'}\n")


if __name__ == "__main__":
    main()
