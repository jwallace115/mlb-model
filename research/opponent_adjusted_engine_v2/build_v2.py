#!/usr/bin/env python3
"""
Opponent-Adjusted Engine V2 — Full data build.
Expands beyond K rate to contact suppression, walk control, run suppression.
"""

import json, os
import pandas as pd
import numpy as np
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")

BASE = Path(__file__).resolve().parent
SIM = BASE.parent.parent / "sim" / "data"
V1 = BASE.parent / "opponent_adjusted_engine"
STATCAST = BASE.parent / "statcast_enrichment"

# =====================================================================
# STEP 0 — AUDIT
# =====================================================================
print("=" * 60)
print("STEP 0 — SOURCE AUDIT")
print("=" * 60)

gt = pd.read_parquet(SIM / "game_table.parquet")
gt["date"] = pd.to_datetime(gt["date"])
ft = pd.read_parquet(SIM / "feature_table.parquet")
ft["date"] = pd.to_datetime(ft["date"])
br = pd.read_parquet(SIM / "bet_results.parquet")
br["date"] = pd.to_datetime(br["date"])
sim = pd.read_parquet(SIM / "phase5_sim_results.parquet")
sim["date"] = pd.to_datetime(sim["date"])
sc = pd.read_parquet(STATCAST / "pitcher_statcast_per_start_starters_only.parquet")
sc["game_date"] = pd.to_datetime(sc["game_date"])

# Reuse V1 boxscore extractions
v1_off = pd.read_parquet(V1 / "offense_expectation_table.parquet")
v1_off["date"] = pd.to_datetime(v1_off["date"])
v1_ps = pd.read_parquet(V1 / "pitcher_start_adjusted_metrics.parquet")
v1_ps["date"] = pd.to_datetime(v1_ps["date"])

boxscore_dir = SIM / "cache" / "boxscores"
n_box = len(os.listdir(boxscore_dir))

audit = [
    "# Source Audit — Opponent-Adjusted Engine V2",
    "",
    "## Primary Sources",
    f"| File | Rows | Seasons | Purpose |",
    f"|------|------|---------|---------|",
    f"| sim/data/game_table.parquet | {len(gt)} | 2022-2025 | Canonical game table |",
    f"| sim/data/feature_table.parquet | {len(ft)} | 2022-2025 | SP xFIP, park factors |",
    f"| sim/data/bet_results.parquet | {len(br)} | 2024-2025 | Closing lines, outcomes |",
    f"| sim/data/phase5_sim_results.parquet | {len(sim)} | 2024-2025 | V1 p_under |",
    f"| research/statcast_enrichment/pitcher_statcast_per_start_starters_only.parquet | {len(sc)} | 2022-2025 | HH%, barrel%, whiff% |",
    f"| sim/data/cache/boxscores/ | {n_box} JSON | 2022-2025 | Team batting + pitcher stats |",
    "",
    "## V1 Engine Reuse",
    f"| File | Rows | Purpose |",
    f"|------|------|---------|",
    f"| research/opponent_adjusted_engine/offense_expectation_table.parquet | {len(v1_off)} | Team K/BB/runs rolling 20g |",
    f"| research/opponent_adjusted_engine/pitcher_start_adjusted_metrics.parquet | {len(v1_ps)} | Pitcher K/BB/IP/ER per start |",
    "",
    "## Key Fields",
    "- game_pk: integer game ID (join key across all tables)",
    "- date: game date (datetime)",
    "- pitcher_id: MLB player ID",
    "- team/opponent: 3-letter abbreviation",
    "- side: home/away",
]
with open(BASE / "source_audit.md", "w") as f:
    f.write("\n".join(audit) + "\n")
print("  Saved source_audit.md")

# =====================================================================
# STEP 1 — OFFENSE EXPECTATION TABLE
# =====================================================================
print("\n" + "=" * 60)
print("STEP 1 — OFFENSE EXPECTATION TABLE")
print("=" * 60)

# V1 already has k_rate_r20, bb_rate_r20, runs_r20
# V2 adds: contact_rate, hard_hit_rate (from boxscore H/AB and Statcast)

# Extract H from boxscores (already in V1 pipeline via team batting)
# Recompute with contact_rate = H / AB
# We need to re-extract hits from boxscores since V1 offense_table doesn't have H
print("  Extracting team batting for contact rate...")
team_bat_rows = []
for fname in os.listdir(boxscore_dir):
    game_pk = int(fname.replace(".json", ""))
    try:
        with open(boxscore_dir / fname) as f:
            box = json.load(f)
    except Exception:
        continue
    for side in ["home", "away"]:
        td = box.get("teams", {}).get(side, {})
        team = td.get("team", {}).get("abbreviation", "")
        bat = td.get("teamStats", {}).get("batting", {})
        if not bat:
            continue
        team_bat_rows.append({
            "game_pk": game_pk, "side": side, "team": team,
            "k": int(bat.get("strikeOuts", 0)),
            "bb": int(bat.get("baseOnBalls", 0)),
            "ab": int(bat.get("atBats", 0)),
            "h": int(bat.get("hits", 0)),
            "r": int(bat.get("runs", 0)),
            "hr": int(bat.get("homeRuns", 0)),
            "hbp": int(bat.get("hitByPitch", 0)),
        })

tb = pd.DataFrame(team_bat_rows)
tb = tb.merge(gt[["game_pk", "date", "season"]], on="game_pk", how="left")
tb = tb.dropna(subset=["date"]).sort_values(["team", "date", "game_pk"]).reset_index(drop=True)

# Per-game rates
tb["k_rate"] = tb["k"] / tb["ab"].clip(lower=1)
tb["bb_rate"] = tb["bb"] / tb["ab"].clip(lower=1)
tb["contact_rate"] = tb["h"] / tb["ab"].clip(lower=1)  # batting average as contact proxy
tb["runs_per_game"] = tb["r"]

# Hard-hit at team level: not available from boxscores.
# Use runs_per_game as quality proxy (same as V1).
# Mark hard_hit as NaN — will use Statcast pitcher-level instead.

# Rolling 20 games (shift to exclude current)
def _rolling(grp):
    grp = grp.sort_values("date").copy()
    for col, new in [("k_rate", "team_k_rate"), ("bb_rate", "team_bb_rate"),
                      ("contact_rate", "team_contact_rate"),
                      ("runs_per_game", "team_runs_per_game")]:
        grp[new] = grp[col].shift(1).rolling(20, min_periods=10).mean()
    return grp

print("  Computing rolling offensive features...")
tb = tb.groupby("team", group_keys=False).apply(_rolling)

# Hard-hit rate at team level: use NaN placeholder
tb["team_hard_hit_rate"] = np.nan

off_table = tb[["game_pk", "side", "team", "date", "season",
                "team_k_rate", "team_bb_rate", "team_contact_rate",
                "team_hard_hit_rate", "team_runs_per_game"]].copy()
off_table.to_parquet(BASE / "offense_expectation_table.parquet", index=False)

cov_2425 = off_table[off_table["season"].isin([2024, 2025])]
print(f"  Saved: {len(off_table)} rows")
print(f"  2024-2025 coverage: k={cov_2425['team_k_rate'].notna().mean():.1%}, "
      f"contact={cov_2425['team_contact_rate'].notna().mean():.1%}, "
      f"hard_hit=N/A (team-level not available from boxscores)")

# =====================================================================
# STEP 2 — PITCHER START PERFORMANCE TABLE
# =====================================================================
print("\n" + "=" * 60)
print("STEP 2 — PITCHER START PERFORMANCE TABLE")
print("=" * 60)

# Reuse V1 pitcher starts and extend with H (hits allowed)
# Need to re-extract hits from boxscores for each pitcher
print("  Extracting pitcher hits allowed from boxscores...")
pitcher_hits = []
for fname in os.listdir(boxscore_dir):
    game_pk = int(fname.replace(".json", ""))
    try:
        with open(boxscore_dir / fname) as f:
            box = json.load(f)
    except Exception:
        continue
    for side in ["home", "away"]:
        td = box.get("teams", {}).get(side, {})
        pitchers = td.get("pitchers", [])
        if not pitchers:
            continue
        starter_id = pitchers[0]
        pdata = td.get("players", {}).get(f"ID{starter_id}", {})
        pit = pdata.get("stats", {}).get("pitching", {})
        if not pit:
            continue
        pitcher_hits.append({
            "game_pk": game_pk,
            "pitcher_id": starter_id,
            "h_allowed": int(pit.get("hits", 0)),
            "hr_allowed": int(pit.get("homeRuns", 0)),
            "runs_allowed": int(pit.get("runs", 0)),
        })

ph = pd.DataFrame(pitcher_hits)

# Merge with V1 pitcher starts
ps = v1_ps.copy()
ps = ps.merge(ph, on=["game_pk", "pitcher_id"], how="left")

# Merge Statcast hard-hit (already in V1 as raw_hard_hit_start)
# Compute per-start rates
ps["k_rate"] = ps["k"] / ps["bf"].clip(lower=1)
ps["bb_rate"] = ps["bb"] / ps["bf"].clip(lower=1)
ps["contact_rate"] = ps["h_allowed"] / ps["bf"].clip(lower=1)
ps["hard_hit_rate"] = ps["raw_hard_hit_start"]  # from Statcast
ps["runs_per_ip"] = ps["runs_allowed"] / ps["ip"].clip(lower=0.1)

# Rename for clarity
ps_out = ps[["pitcher_id", "game_pk", "date", "season", "team", "opponent", "side",
             "pitcher_name", "ip", "k", "bb", "h_allowed", "hr_allowed", "runs_allowed",
             "bf", "pitches", "strikes",
             "k_rate", "bb_rate", "contact_rate", "hard_hit_rate", "runs_per_ip"]].copy()
ps_out.rename(columns={"game_pk": "game_id", "date": "game_date", "opponent": "team_faced"}, inplace=True)

ps_out.to_parquet(BASE / "pitcher_start_performance.parquet", index=False)
print(f"  Saved: {len(ps_out)} rows")
print(f"  Coverage: k_rate={ps_out.k_rate.notna().mean():.1%}, "
      f"contact_rate={ps_out.contact_rate.notna().mean():.1%}, "
      f"hard_hit_rate={ps_out.hard_hit_rate.notna().mean():.1%}")

# =====================================================================
# STEP 3 — OPPONENT ADJUSTMENTS
# =====================================================================
print("\n" + "=" * 60)
print("STEP 3 — OPPONENT ADJUSTMENTS")
print("=" * 60)

# Join offense expectation to each start (opponent = team_faced)
# Use game_pk + opponent to find the right offense row
opp = off_table.rename(columns={"team": "team_faced_join"})[
    ["game_pk", "team_faced_join",
     "team_k_rate", "team_bb_rate", "team_contact_rate",
     "team_hard_hit_rate", "team_runs_per_game"]
].copy()

# Join on game_pk + opponent team
ps_adj = ps.copy()
ps_adj = ps_adj.merge(
    opp.rename(columns={"team_faced_join": "opponent"}),
    on=["game_pk", "opponent"], how="left"
)

# V2 adjustment formulas:
# adj = pitcher_performance - team_expected (for K, BB)
# adj = team_expected - pitcher_performance (for contact, hard_hit → higher = more suppression)
# adj = team_expected_runs - actual_runs_allowed (higher = more suppression)

ps_adj["adj_k_rate"] = ps_adj["k_rate"] - ps_adj["team_k_rate"]
ps_adj["adj_bb_rate"] = ps_adj["bb_rate"] - ps_adj["team_bb_rate"]
ps_adj["adj_contact_rate"] = ps_adj["team_contact_rate"] - ps_adj["contact_rate"]
# Hard-hit: use runs proxy since team HH not available
ps_adj["adj_hard_hit_rate"] = np.nan  # placeholder — will use Statcast directly
# For pitchers with Statcast: adj_hh = league_avg_hh - pitcher_hh (higher = more suppression)
lg_hh = ps_adj["hard_hit_rate"].dropna().mean()
ps_adj.loc[ps_adj["hard_hit_rate"].notna(), "adj_hard_hit_rate"] = \
    lg_hh - ps_adj.loc[ps_adj["hard_hit_rate"].notna(), "hard_hit_rate"]

# Run suppression: expected runs (team_runs/game * pitcher_IP/9) - actual runs
ps_adj["expected_runs"] = ps_adj["team_runs_per_game"] * (ps_adj["ip"] / 9)
ps_adj["adj_run_suppression"] = ps_adj["expected_runs"] - ps_adj["runs_allowed"]

ps_adj_out = ps_adj[["pitcher_id", "game_pk", "date", "season", "team", "opponent", "side",
                      "pitcher_name", "ip", "k_rate", "bb_rate", "contact_rate", "hard_hit_rate",
                      "runs_per_ip", "runs_allowed",
                      "team_k_rate", "team_bb_rate", "team_contact_rate", "team_runs_per_game",
                      "adj_k_rate", "adj_bb_rate", "adj_contact_rate",
                      "adj_hard_hit_rate", "adj_run_suppression"]].copy()

ps_adj_out.to_parquet(BASE / "pitcher_start_adjusted.parquet", index=False)

cov_2425 = ps_adj_out[ps_adj_out["season"].isin([2024, 2025])]
print(f"  Saved: {len(ps_adj_out)} rows")
for c in ["adj_k_rate", "adj_bb_rate", "adj_contact_rate", "adj_hard_hit_rate", "adj_run_suppression"]:
    cov = cov_2425[c].notna().mean()
    print(f"    {c}: {cov:.1%}")

# =====================================================================
# STEP 4 — RECENT FORM FEATURES
# =====================================================================
print("\n" + "=" * 60)
print("STEP 4 — RECENT FORM FEATURES")
print("=" * 60)

ps_rf = ps_adj_out.sort_values(["pitcher_id", "date"]).copy()

metrics = {
    "adj_k_rate": "adj_k_rate",
    "adj_bb_rate": "adj_bb_rate",
    "adj_contact_rate": "adj_contact_rate",
    "adj_hard_hit": "adj_hard_hit_rate",
    "adj_run_suppression": "adj_run_suppression",
}

print("  Computing rolling features...")
for prefix, src_col in metrics.items():
    for w in [3, 5]:
        feat = f"{prefix}_last{w}"
        minp = 2 if w == 3 else 3
        ps_rf[feat] = ps_rf.groupby("pitcher_id")[src_col].transform(
            lambda x: x.shift(1).rolling(w, min_periods=minp).mean()
        )

# Select output columns
form_cols = ["pitcher_id", "game_pk", "date", "season", "side"]
form_cols += [f"{p}_last{w}" for p in metrics.keys() for w in [3, 5]]

ps_form = ps_rf[form_cols].copy()
ps_form.rename(columns={"date": "game_date"}, inplace=True)
ps_form.to_parquet(BASE / "pitcher_recent_adjusted_features.parquet", index=False)

cov_2425 = ps_form[ps_form["season"].isin([2024, 2025])]
print(f"  Saved: {len(ps_form)} rows")
for c in [f"{p}_last3" for p in metrics.keys()]:
    cov = cov_2425[c].notna().mean()
    print(f"    {c}: {cov:.1%}")

# =====================================================================
# STEP 5 — GAME LEVEL DATASET
# =====================================================================
print("\n" + "=" * 60)
print("STEP 5 — GAME LEVEL DATASET")
print("=" * 60)

# Start from feature table (2024+2025)
game_df = ft[ft["season"].isin([2024, 2025])].copy()

# Add closing lines
game_df = game_df.merge(
    br[["game_id", "close_total"]].rename(columns={"game_id": "game_pk"}),
    on="game_pk", how="inner"
)
game_df.rename(columns={"close_total": "closing_total"}, inplace=True)

# Add V1 p_under
game_df = game_df.merge(sim[["game_pk", "p_under", "p_over"]], on="game_pk", how="left")

# Join home pitcher form
roll_feats = [c for c in ps_form.columns if "last" in c]
home_form = ps_form[ps_form["side"] == "home"][["game_pk"] + roll_feats].copy()
home_form.columns = ["game_pk"] + [f"{c}_home" for c in roll_feats]

away_form = ps_form[ps_form["side"] == "away"][["game_pk"] + roll_feats].copy()
away_form.columns = ["game_pk"] + [f"{c}_away" for c in roll_feats]

game_df = game_df.merge(home_form, on="game_pk", how="left")
game_df = game_df.merge(away_form, on="game_pk", how="left")

# Add SP identifiers
sp_ids = ps_rf[["game_pk", "pitcher_id", "pitcher_name", "side"]].drop_duplicates()
home_sp = sp_ids[sp_ids["side"] == "home"][["game_pk", "pitcher_id", "pitcher_name"]].rename(
    columns={"pitcher_id": "starting_pitcher_home", "pitcher_name": "sp_name_home"})
away_sp = sp_ids[sp_ids["side"] == "away"][["game_pk", "pitcher_id", "pitcher_name"]].rename(
    columns={"pitcher_id": "starting_pitcher_away", "pitcher_name": "sp_name_away"})
game_df = game_df.merge(home_sp, on="game_pk", how="left")
game_df = game_df.merge(away_sp, on="game_pk", how="left")

# Targets
game_df["total_runs"] = game_df["actual_total"]
game_df["market_implied_over"] = 0.50
game_df["market_error"] = game_df["actual_total"] - game_df["closing_total"]

# Select and save
keep_cols = ["game_pk", "date", "season", "home_team", "away_team",
             "starting_pitcher_home", "starting_pitcher_away",
             "sp_name_home", "sp_name_away",
             "home_sp_xfip", "away_sp_xfip", "park_factor_runs",
             "p_under", "p_over",
             "closing_total", "total_runs", "actual_total",
             "market_implied_over", "market_error"]

# Add all adjusted feature columns
for c in game_df.columns:
    if "last" in c and ("home" in c or "away" in c):
        keep_cols.append(c)

game_out = game_df[[c for c in keep_cols if c in game_df.columns]].copy()
game_out.rename(columns={"game_pk": "game_id", "date": "game_date"}, inplace=True)
game_out.to_parquet(BASE / "game_level_engine_dataset.parquet", index=False)

print(f"  Saved: {len(game_out)} games")
print(f"  Columns: {len(game_out.columns)}")

# =====================================================================
# STEP 6 — DATA QUALITY CHECKS
# =====================================================================
print("\n" + "=" * 60)
print("STEP 6 — DATA QUALITY CHECKS")
print("=" * 60)

dq = [
    "# Data Quality Report — V2 Engine",
    "",
    f"## Dataset Size",
    f"- Total games: {len(game_out)}",
    f"- 2024: {(game_out.season==2024).sum()}",
    f"- 2025: {(game_out.season==2025).sum()}",
    "",
    "## Coverage of Adjusted Metrics",
    "",
    "| Feature | Available | Coverage |",
    "|---------|-----------|----------|",
]

adj_cols = [c for c in game_out.columns if "adj_" in c and "last" in c]
for c in sorted(adj_cols):
    n = game_out[c].notna().sum()
    pct = 100 * n / len(game_out)
    dq.append(f"| {c} | {n} | {pct:.1f}% |")

dq.extend(["", "## Missing Recent Form"])
total_miss = game_out[adj_cols].isna().all(axis=1).sum()
dq.append(f"- Games with ALL adjusted features missing: {total_miss} ({100*total_miss/len(game_out):.1f}%)")

any_miss = game_out[adj_cols].isna().any(axis=1).sum()
dq.append(f"- Games with ANY adjusted feature missing: {any_miss} ({100*any_miss/len(game_out):.1f}%)")

dq.extend(["", "## Pitchers Per Season"])
for yr in [2024, 2025]:
    yr_starts = ps_adj_out[ps_adj_out["season"] == yr]
    n_pitchers = yr_starts["pitcher_id"].nunique()
    avg_starts = len(yr_starts) / n_pitchers
    dq.append(f"- {yr}: {n_pitchers} unique starters, avg {avg_starts:.1f} starts each")

dq.extend(["", "## Adjusted Metric Distributions (2024+2025)"])
dq.append("")
dq.append("| Metric | Mean | Std | p10 | p50 | p90 |")
dq.append("|--------|------|-----|-----|-----|-----|")
for c in ["adj_k_rate", "adj_bb_rate", "adj_contact_rate", "adj_hard_hit_rate", "adj_run_suppression"]:
    vals = ps_adj_out.loc[ps_adj_out["season"].isin([2024, 2025]), c].dropna()
    if len(vals) > 0:
        dq.append(f"| {c} | {vals.mean():.4f} | {vals.std():.4f} | "
                  f"{vals.quantile(0.1):.4f} | {vals.quantile(0.5):.4f} | {vals.quantile(0.9):.4f} |")

with open(BASE / "data_quality_report.md", "w") as f:
    f.write("\n".join(dq) + "\n")
print("  Saved data_quality_report.md")

# Print summary
for c in adj_cols[:6]:
    n = game_out[c].notna().sum()
    print(f"    {c}: {n}/{len(game_out)} ({100*n/len(game_out):.1f}%)")

# =====================================================================
# STEP 7 — SIGNAL SCANNER INPUT
# =====================================================================
print("\n" + "=" * 60)
print("STEP 7 — SIGNAL SCANNER INPUT")
print("=" * 60)

# Build scanner dataset with individual + interaction features
scanner = game_out.copy()

# Combined features (avg home + away)
for metric in ["adj_k_rate_last3", "adj_bb_rate_last3", "adj_contact_rate_last3",
               "adj_hard_hit_last3", "adj_run_suppression_last3"]:
    h_col = f"{metric}_home"
    a_col = f"{metric}_away"
    c_col = f"combined_{metric}"
    if h_col in scanner.columns and a_col in scanner.columns:
        scanner[c_col] = (scanner[h_col] + scanner[a_col]) / 2

# Interaction features
if "combined_adj_k_rate_last3" in scanner.columns and "combined_adj_contact_rate_last3" in scanner.columns:
    scanner["adj_k_x_contact_last3"] = scanner["combined_adj_k_rate_last3"] * scanner["combined_adj_contact_rate_last3"]

if "combined_adj_k_rate_last3" in scanner.columns and "combined_adj_run_suppression_last3" in scanner.columns:
    scanner["adj_k_x_runsup_last3"] = scanner["combined_adj_k_rate_last3"] * scanner["combined_adj_run_suppression_last3"]

# Targets
scanner["is_push"] = (scanner["total_runs"] == scanner["closing_total"])
scanner["went_under"] = (scanner["total_runs"] < scanner["closing_total"]).astype(int)
scanner["market_residual"] = scanner["went_under"] - 0.50

scanner.to_parquet(BASE / "signal_scanner_input.parquet", index=False)

# Summary
signal_cols = [c for c in scanner.columns if "combined_adj" in c or "adj_k_x" in c]
print(f"  Saved: {len(scanner)} games, {len(scanner.columns)} columns")
print(f"  Signal candidates: {len(signal_cols)}")
for c in signal_cols:
    n = scanner[c].notna().sum()
    print(f"    {c}: {n} ({100*n/len(scanner):.1f}%)")

print("\n  V2 engine build complete. Ready for signal scanning.")
