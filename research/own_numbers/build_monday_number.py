"""
ON-1 ITEM 1: Build Monday number (unanchored engine sim) for every REG game 2021-23.
As-of: Monday 12:00 ET before kickoff (= ratings from week < game_week in the same season,
plus prior season as prior). HFA applied via epa_home_offset/epa_away_offset.

N = 5,000 per game, split into 2 × 2,500 chunks for Monte-Carlo SE.
"""
import os, sys, json, time, hashlib
import numpy as np
import pandas as pd

os.environ["SSL_CERT_FILE"] = __import__("certifi").where()
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from nfl.sim.engine import simulate_game

ROOT = os.path.join(os.path.dirname(__file__), "../..")
TARGET_SEASONS = [2021, 2022, 2023]
N_SIMS = 5000
CHUNK_SIZE = 2500
N_CHUNKS = 2

# ─── HFA ─────────────────────────────────────────────────────────────
with open(os.path.join(ROOT, "nfl/sim/hfa_v1.json")) as f:
    hfa = json.load(f)
H = hfa["h"]  # 0.1719 EPA units
print(f"HFA h = {H}")

# ─── LOAD SCHEDULES ─────────────────────────────────────────────────
import nflreadpy as nfl
sched = nfl.load_schedules(TARGET_SEASONS).to_pandas()
games = sched[sched["game_type"] == "REG"].copy()
assert sorted(games["season"].unique()) == TARGET_SEASONS
print(f"Games: {len(games)}")

# ─── LOAD SPREAD OPENS ──────────────────────────────────────────────
opens = pd.read_parquet(os.path.join(ROOT, "nfl/data/info/spread_opens_2021_23.parquet"))
# Negate bet365 opens to nflverse margin convention (work order: "negate to home-margin convention")
opens["open_spread"] = -opens["bet365_spread_open"]
opens["open_total"] = opens["bet365_total_open"]
print(f"Spread opens: {len(opens)}")


def sim_one_game(args):
    """Run one game: 2 chunks of 2500, return means and SEs."""
    game_id, home, away, season, week = args
    chunk_margins = []
    chunk_totals = []
    for ci in range(N_CHUNKS):
        seed = hash((game_id, ci)) % (2**31)
        try:
            result = simulate_game(
                home, away, season, week,
                n_sims=CHUNK_SIZE, seed=seed,
                epa_home_offset=H,      # +h for home (HFA via EPA offset)
                epa_away_offset=-H,     # -h for away
            )
            margins = (result["home_score"] - result["away_score"]).values
            totals = (result["home_score"] + result["away_score"]).values
            chunk_margins.append(margins.mean())
            chunk_totals.append(totals.mean())
        except Exception as e:
            return {"game_id": game_id, "error": str(e)}

    ours_m = np.mean(chunk_margins)
    ours_t = np.mean(chunk_totals)
    # MC SE from the 2 chunk means
    mc_se_m = np.std(chunk_margins, ddof=1) / np.sqrt(N_CHUNKS) if N_CHUNKS > 1 else 0
    mc_se_t = np.std(chunk_totals, ddof=1) / np.sqrt(N_CHUNKS) if N_CHUNKS > 1 else 0

    return {
        "game_id": game_id,
        "ours_m": ours_m,
        "ours_t": ours_t,
        "mc_se_m": mc_se_m,
        "mc_se_t": mc_se_t,
        "n_games_home": max(week - 1, 0),  # games into ratings for home team
        "n_games_away": max(week - 1, 0),  # same for away (week-1 in REG)
    }


# ─── RUN ALL GAMES (with caching) ────────────────────────────────────
SIM_CACHE = os.path.join(ROOT, "nfl/data/own/_sim_cache_2021_23.parquet")

if os.path.exists(SIM_CACHE):
    print(f"\nLoading cached sim results from {SIM_CACHE}")
    sim_df = pd.read_parquet(SIM_CACHE)
    t0 = t1 = time.time()
    print(f"Cached sim results: {sim_df.shape}")
else:
    print(f"\nRunning {len(games)} games at N={N_SIMS} ({N_CHUNKS}×{CHUNK_SIZE})...")
    t0 = time.time()

    game_args = [
        (row["game_id"], row["home_team"], row["away_team"], row["season"], row["week"])
        for _, row in games.iterrows()
    ]

    results = []
    for i, args in enumerate(game_args):
        result = sim_one_game(args)
        results.append(result)
        if (i + 1) % 50 == 0:
            elapsed = time.time() - t0
            rate = elapsed / (i + 1)
            eta = rate * (len(game_args) - i - 1) / 60
            print(f"  {i+1}/{len(games)} done ({elapsed:.0f}s, eta {eta:.0f}m)")

    t1 = time.time()
    print(f"\nWall time: {t1-t0:.0f}s ({(t1-t0)/60:.1f} min)")

    # Check for errors
    errors = [r for r in results if "error" in r]
    if errors:
        print(f"ERRORS: {len(errors)}")
        for e in errors[:5]:
            print(f"  {e['game_id']}: {e['error']}")
        results = [r for r in results if "error" not in r]

    sim_df = pd.DataFrame(results)
    sim_df.to_parquet(SIM_CACHE, index=False)
    print(f"Saved sim cache: {sim_df.shape}")


# ─── CALIBRATION ─────────────────────────────────────────────────────
print("\n=== CALIBRATION ===")
# Join sim results with closes
sim_df = sim_df.merge(
    games[["game_id", "season", "week", "home_team", "away_team", "spread_line", "total_line"]],
    on="game_id", how="left"
)
# Join with opens
sim_df = sim_df.merge(
    opens[["game_id", "open_spread", "open_total"]],
    on="game_id", how="left"
)

# Calibration variance: as-of variance of (ours_m - close) fitted on PRIOR seasons
# as a function of min(n_games_home, n_games_away) in 4 buckets
sim_df["n_games_min"] = sim_df[["n_games_home", "n_games_away"]].min(axis=1)
sim_df["ours_minus_close_m"] = sim_df["ours_m"] - sim_df["spread_line"]
sim_df["ours_minus_close_t"] = sim_df["ours_t"] - sim_df["total_line"]

BUCKETS = [(0, 3, "≤3"), (4, 8, "4-8"), (9, 13, "9-13"), (14, 99, "14+")]

def bucket_label(n):
    for lo, hi, label in BUCKETS:
        if lo <= n <= hi:
            return label
    return "14+"

sim_df["n_bucket"] = sim_df["n_games_min"].apply(bucket_label)

# Build calibration table: for each season, use PRIOR seasons to estimate cal_var
# 2021: use flat prior (no prior season in data → state the flat value)
# 2022: use 2021
# 2023: use 2021-22
# The flat prior for 2021: variance of (ours_m - close) across ALL 2021 games (a circular
# estimate, but stated as such). A better approach: use the overall SD from the literature
# (~13.5 for NFL margin) as the flat prior.
FLAT_MARGIN_VAR = 13.5 ** 2  # ~182.25 — from NFL margin SD ≈ 13.5 points
FLAT_TOTAL_VAR = 13.2 ** 2   # ~174.24 — from NFL total SD ≈ 13.2 points
print(f"Flat prior: margin_var={FLAT_MARGIN_VAR:.1f} (SD≈13.5), total_var={FLAT_TOTAL_VAR:.1f} (SD≈13.2)")

cal_table = []

for target_season in TARGET_SEASONS:
    if target_season == 2021:
        # Flat prior — no prior season available in our data
        for lo, hi, label in BUCKETS:
            cal_table.append({
                "target_season": target_season,
                "bucket": label,
                "cal_var_m": FLAT_MARGIN_VAR,
                "cal_var_t": FLAT_TOTAL_VAR,
                "n_games_in_cal": 0,
                "source": "flat_prior",
            })
    else:
        prior_seasons = [s for s in TARGET_SEASONS if s < target_season]
        prior_data = sim_df[sim_df["season"].isin(prior_seasons)]
        for lo, hi, label in BUCKETS:
            bucket_data = prior_data[(prior_data["n_games_min"] >= lo) &
                                     (prior_data["n_games_min"] <= hi)]
            if len(bucket_data) >= 5:
                cal_var_m = bucket_data["ours_minus_close_m"].var()
                cal_var_t = bucket_data["ours_minus_close_t"].var()
            else:
                # Too few games — fall back to flat prior
                cal_var_m = FLAT_MARGIN_VAR
                cal_var_t = FLAT_TOTAL_VAR
            cal_table.append({
                "target_season": target_season,
                "bucket": label,
                "cal_var_m": cal_var_m,
                "cal_var_t": cal_var_t,
                "n_games_in_cal": len(bucket_data),
                "source": f"seasons {prior_seasons}",
            })

cal_df = pd.DataFrame(cal_table)
print("\nCalibration table:")
print(cal_df.to_string(index=False))

# Save calibration table
cal_df.to_parquet(os.path.join(ROOT, "nfl/data/own/calibration_table.parquet"), index=False)

# Apply calibration to compute error bars
def get_cal_var(season, n_games_min, target="m"):
    bucket = bucket_label(n_games_min)
    row = cal_df[(cal_df["target_season"] == season) & (cal_df["bucket"] == bucket)]
    if len(row) == 0:
        return FLAT_MARGIN_VAR if target == "m" else FLAT_TOTAL_VAR
    col = "cal_var_m" if target == "m" else "cal_var_t"
    return row[col].values[0]

sim_df["cal_var_m"] = sim_df.apply(
    lambda r: get_cal_var(r["season"], r["n_games_min"], "m"), axis=1)
sim_df["cal_var_t"] = sim_df.apply(
    lambda r: get_cal_var(r["season"], r["n_games_min"], "t"), axis=1)

sim_df["err_m"] = np.sqrt(sim_df["mc_se_m"]**2 + sim_df["cal_var_m"])
sim_df["err_t"] = np.sqrt(sim_df["mc_se_t"]**2 + sim_df["cal_var_t"])


# ─── TARGETS AND RESIDUALS ──────────────────────────────────────────
# The target invariant applies to the OUTCOME residual (actual - close), not
# the prediction residual (ours - close). Our prediction naturally correlates
# with the close (both capture team quality). The invariant checks that the
# SCORING TARGET (actual margin - spread_line) is uncorrelated with the close.

# Add actual outcomes for the invariant check
sched_outcomes = games[["game_id", "home_score", "away_score"]].copy()
sched_outcomes = sched_outcomes.rename(columns={"home_score": "actual_home", "away_score": "actual_away"})
sim_df = sim_df.merge(sched_outcomes, on="game_id", how="left")
sim_df["actual_margin"] = sim_df["actual_home"] - sim_df["actual_away"]
sim_df["actual_total"] = sim_df["actual_home"] + sim_df["actual_away"]
sim_df["outcome_margin_resid"] = sim_df["actual_margin"] - sim_df["spread_line"]
sim_df["outcome_total_resid"] = sim_df["actual_total"] - sim_df["total_line"]

# Known-game assertion
g_ari = sim_df[sim_df["game_id"] == "2021_01_ARI_TEN"]
assert len(g_ari) == 1, "HALT: 2021_01_ARI_TEN not found"
assert g_ari["spread_line"].values[0] == 2.5, "HALT: ARI_TEN spread_line != 2.5"
assert g_ari["actual_margin"].values[0] == -25, "HALT: ARI_TEN actual_margin != -25"

# Outcome residual correlation gate (the invariant)
corr_mr_sl = np.corrcoef(sim_df["outcome_margin_resid"].values, sim_df["spread_line"].values)[0, 1]
print(f"\n|corr(outcome_margin_resid, spread_line)| = {abs(corr_mr_sl):.4f}")
assert abs(corr_mr_sl) < 0.05, f"HALT: |corr| = {abs(corr_mr_sl):.4f} >= 0.05"

corr_tr_tl = np.corrcoef(sim_df["outcome_total_resid"].values, sim_df["total_line"].values)[0, 1]
print(f"|corr(outcome_total_resid, total_line)| = {abs(corr_tr_tl):.4f}")
assert abs(corr_tr_tl) < 0.05, f"HALT: |corr| = {abs(corr_tr_tl):.4f} >= 0.05"

# Also report prediction-vs-close correlation (expected to be high, not a gate)
corr_ours_close = np.corrcoef(sim_df["ours_m"].values, sim_df["spread_line"].values)[0, 1]
print(f"corr(ours_m, spread_line) = {corr_ours_close:.4f} (expected high, not a gate)")

# Zero-variance check on ours_m, ours_t
for col in ["ours_m", "ours_t", "err_m", "err_t"]:
    assert sim_df[col].std() > 0, f"HALT: zero-variance {col}"

# Season assertion
assert sorted(sim_df["season"].unique()) == TARGET_SEASONS


# ─── SAVE ────────────────────────────────────────────────────────────
out_cols = [
    "game_id", "season", "week", "home_team", "away_team",
    "ours_m", "ours_t", "mc_se_m", "mc_se_t",
    "n_games_home", "n_games_away", "n_games_min", "n_bucket",
    "cal_var_m", "cal_var_t", "err_m", "err_t",
    "spread_line", "total_line",        # close
    "open_spread", "open_total",         # bet365 open (negated to nflverse conv)
    "actual_margin", "actual_total",     # actual outcomes
    "outcome_margin_resid", "outcome_total_resid",
]
out_df = sim_df[out_cols].copy()

os.makedirs(os.path.join(ROOT, "nfl/data/own"), exist_ok=True)
out_path = os.path.join(ROOT, "nfl/data/own/monday_numbers_2021_23.parquet")
out_df.to_parquet(out_path, index=False)
print(f"\nSaved to {out_path}")
print(f"Rows: {len(out_df)}, Cols: {len(out_df.columns)}")

# Summary stats
print("\n=== SUMMARY ===")
print(f"Mean ours_m: {sim_df['ours_m'].mean():.2f}")
print(f"Mean ours_t: {sim_df['ours_t'].mean():.2f}")
print(f"Mean err_m: {sim_df['err_m'].mean():.2f}")
print(f"Mean err_t: {sim_df['err_t'].mean():.2f}")
print(f"Mean mc_se_m: {sim_df['mc_se_m'].mean():.3f}")
print(f"Mean mc_se_t: {sim_df['mc_se_t'].mean():.3f}")
print(f"Open coverage: {sim_df['open_spread'].notna().sum()}/{len(sim_df)}")
print(f"Wall time: {t1-t0:.0f}s")
