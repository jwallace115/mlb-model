#!/usr/bin/env python3
"""
Opponent-Adjusted Pitcher Form — Full Research Pipeline

Steps 0-4: Build all data tables
Steps 5-7: Run in separate analysis script
"""

import json
import os
import pandas as pd
import numpy as np
from pathlib import Path
from collections import defaultdict

BASE = Path(__file__).resolve().parent
SIM = BASE.parent.parent / "sim" / "data"
STATCAST = BASE.parent / "statcast_enrichment"

# =====================================================================
# STEP 0 — AUDIT
# =====================================================================
print("=" * 60)
print("STEP 0 — SOURCE AUDIT")
print("=" * 60)

audit_lines = [
    "# Source Audit — Opponent-Adjusted Pitcher Form",
    "",
    "## Files Used",
    "",
    "| # | File | Rows | Purpose |",
    "|---|------|------|---------|",
]

gt = pd.read_parquet(SIM / "game_table.parquet")
gt["date"] = pd.to_datetime(gt["date"])
audit_lines.append(f"| 1 | sim/data/game_table.parquet | {len(gt)} | Game-level canonical table |")

ft = pd.read_parquet(SIM / "feature_table.parquet")
ft["date"] = pd.to_datetime(ft["date"])
audit_lines.append(f"| 2 | sim/data/feature_table.parquet | {len(ft)} | SP xFIP, K%, BB%, park factors |")

bu = pd.read_parquet(SIM / "bullpen_usage.parquet")
bu["date"] = pd.to_datetime(bu["date"])
starters = bu[bu["is_starter"]].copy()
audit_lines.append(f"| 3 | sim/data/bullpen_usage.parquet | {len(bu)} ({len(starters)} starters) | Starter IP, pitches, K |")

sc = pd.read_parquet(STATCAST / "pitcher_statcast_per_start_starters_only.parquet")
sc["game_date"] = pd.to_datetime(sc["game_date"])
audit_lines.append(f"| 4 | research/statcast_enrichment/pitcher_statcast_per_start_starters_only.parquet | {len(sc)} | HH%, barrel%, whiff%, chase% |")

br = pd.read_parquet(SIM / "bet_results.parquet")
br["date"] = pd.to_datetime(br["date"])
audit_lines.append(f"| 5 | sim/data/bet_results.parquet | {len(br)} | Closing lines, results (2024-2025) |")

boxscore_dir = SIM / "cache" / "boxscores"
n_box = len(os.listdir(boxscore_dir))
audit_lines.append(f"| 6 | sim/data/cache/boxscores/ | {n_box} JSON files | Team batting K/BB/AB per game |")

audit_lines.extend([
    "",
    "## Key Decisions",
    "- CSW proxy: strikes / total_pitches from boxscores (called+swinging strikes as proportion)",
    "  This is strike% not true CSW, but is the best available proxy without pitch-level data per game.",
    "- Team offense rolling: K_rate, BB_rate, runs/game from boxscore team batting lines",
    "- Hard-hit, barrel, whiff from Statcast per-start (coverage varies by season)",
    "- Evaluation: 2024+2025 games with closing lines (4,855 games from bet_results)",
])

with open(BASE / "source_audit.md", "w") as f:
    f.write("\n".join(audit_lines) + "\n")
print(f"  Saved source_audit.md")

# =====================================================================
# STEP 1 — EXTRACT TEAM BATTING FROM BOXSCORES + BUILD OFFENSE TABLE
# =====================================================================
print("\n" + "=" * 60)
print("STEP 1 — TEAM OFFENSE EXPECTATION TABLE")
print("=" * 60)

# Extract team batting from cached boxscores
print("  Extracting team batting stats from boxscores...")
team_batting_rows = []

for fname in os.listdir(boxscore_dir):
    game_pk = int(fname.replace(".json", ""))
    try:
        with open(boxscore_dir / fname) as f:
            box = json.load(f)
    except:
        continue

    for side in ["home", "away"]:
        team_data = box.get("teams", {}).get(side, {})
        team_abbr = team_data.get("team", {}).get("abbreviation", "")
        bat = team_data.get("teamStats", {}).get("batting", {})
        if not bat:
            continue

        team_batting_rows.append({
            "game_pk": game_pk,
            "side": side,
            "team": team_abbr,
            "strikeouts": int(bat.get("strikeOuts", 0)),
            "base_on_balls": int(bat.get("baseOnBalls", 0)),
            "at_bats": int(bat.get("atBats", 0)),
            "hits": int(bat.get("hits", 0)),
            "runs": int(bat.get("runs", 0)),
            "home_runs": int(bat.get("homeRuns", 0)),
        })

tb = pd.DataFrame(team_batting_rows)
print(f"  Extracted: {len(tb)} team-game batting lines")

# Join date from game_table
tb = tb.merge(gt[["game_pk", "date", "season"]], on="game_pk", how="left")
tb = tb.dropna(subset=["date"]).copy()

# Compute per-game rates
tb["k_rate"] = tb["strikeouts"] / tb["at_bats"].clip(lower=1)
tb["bb_rate"] = tb["base_on_balls"] / tb["at_bats"].clip(lower=1)

# Sort by team + date for rolling
tb = tb.sort_values(["team", "date", "game_pk"]).reset_index(drop=True)

# Rolling last 20 games (more robust than 30 days which varies by schedule)
print("  Computing rolling offensive features (last 20 games)...")

def rolling_team_offense(group):
    group = group.sort_values("date").copy()
    # Shift to exclude current game (strict pre-game)
    group["k_rate_r20"] = group["k_rate"].shift(1).rolling(20, min_periods=10).mean()
    group["bb_rate_r20"] = group["bb_rate"].shift(1).rolling(20, min_periods=10).mean()
    group["runs_per_game_r20"] = group["runs"].shift(1).rolling(20, min_periods=10).mean()
    return group

tb = tb.groupby("team", group_keys=False).apply(rolling_team_offense)

# Save team offense expectation table
offense_cols = ["game_pk", "side", "team", "date", "season",
                "k_rate", "bb_rate", "runs",
                "k_rate_r20", "bb_rate_r20", "runs_per_game_r20"]
offense_table = tb[offense_cols].copy()
offense_table.to_parquet(BASE / "team_offense_expectation_table.parquet", index=False)

# Coverage
off_2425 = offense_table[offense_table["season"].isin([2024, 2025])]
cov_k = off_2425["k_rate_r20"].notna().mean()
cov_bb = off_2425["bb_rate_r20"].notna().mean()
print(f"  Saved team_offense_expectation_table.parquet: {len(offense_table)} rows")
print(f"  2024-2025 rolling coverage: k_rate={cov_k:.1%}, bb_rate={cov_bb:.1%}")

# Write notes
notes = [
    "# Team Offense Expectation — Data Notes",
    "",
    "## Method",
    "- Source: MLB Stats API boxscores (9,715 cached JSON files)",
    "- Extracted team batting: K, BB, AB, H, R, HR per game-side",
    "- Rolling window: last 20 completed games per team (shift(1) to exclude current game)",
    "- Min periods: 10 games",
    "",
    "## Features",
    "- `k_rate_r20`: team K/AB rolling 20 games (higher = more strikeout-prone offense)",
    "- `bb_rate_r20`: team BB/AB rolling 20 games (higher = more patient offense)",
    "- `runs_per_game_r20`: team runs/game rolling 20 games",
    "",
    "## Coverage (2024-2025)",
    f"- k_rate_r20: {cov_k:.1%}",
    f"- bb_rate_r20: {cov_bb:.1%}",
    "- Gaps are early-season (first ~10 games per team per season)",
]
with open(BASE / "team_offense_expectation_notes.md", "w") as f:
    f.write("\n".join(notes) + "\n")

# =====================================================================
# STEP 2 — BUILD START-LEVEL RAW + ADJUSTED PITCHER METRICS
# =====================================================================
print("\n" + "=" * 60)
print("STEP 2 — RAW + ADJUSTED PITCHER START METRICS")
print("=" * 60)

# Extract per-start pitching stats from boxscores
print("  Extracting per-start pitcher stats from boxscores...")

# We need: starter's K, BB, batters_faced, pitches, strikes per start
# Also need to know which team the starter faces
pitcher_start_rows = []

for fname in os.listdir(boxscore_dir):
    game_pk = int(fname.replace(".json", ""))
    try:
        with open(boxscore_dir / fname) as f:
            box = json.load(f)
    except:
        continue

    for side in ["home", "away"]:
        opp_side = "away" if side == "home" else "home"
        team_data = box.get("teams", {}).get(side, {})
        opp_data = box.get("teams", {}).get(opp_side, {})

        team_abbr = team_data.get("team", {}).get("abbreviation", "")
        opp_abbr = opp_data.get("team", {}).get("abbreviation", "")

        # Find starter (first pitcher listed, or gamesStarted=1)
        pitchers_order = team_data.get("pitchers", [])
        if not pitchers_order:
            continue

        starter_id = pitchers_order[0]
        pid_key = f"ID{starter_id}"
        pdata = team_data.get("players", {}).get(pid_key, {})
        pitching = pdata.get("stats", {}).get("pitching", {})
        if not pitching:
            continue

        k = int(pitching.get("strikeOuts", 0))
        bb = int(pitching.get("baseOnBalls", 0))
        bf = int(pitching.get("battersFaced", 0))
        pitches = int(pitching.get("pitchesThrown", 0) or pitching.get("numberOfPitches", 0))
        strikes = int(pitching.get("strikes", 0))
        ip_str = pitching.get("inningsPitched", "0")
        try:
            ip_parts = str(ip_str).split(".")
            ip = int(ip_parts[0]) + int(ip_parts[1]) / 3 if len(ip_parts) > 1 else float(ip_str)
        except:
            ip = 0.0
        er = int(pitching.get("earnedRuns", 0))

        pitcher_start_rows.append({
            "game_pk": game_pk,
            "pitcher_id": starter_id,
            "pitcher_name": pdata.get("person", {}).get("fullName", ""),
            "team": team_abbr,
            "opponent": opp_abbr,
            "side": side,
            "k": k,
            "bb": bb,
            "bf": bf,
            "pitches": pitches,
            "strikes": strikes,
            "ip": ip,
            "er": er,
        })

ps = pd.DataFrame(pitcher_start_rows)
ps = ps.merge(gt[["game_pk", "date", "season"]], on="game_pk", how="left")
ps = ps.dropna(subset=["date"]).copy()
ps = ps.sort_values(["pitcher_id", "date", "game_pk"]).reset_index(drop=True)
print(f"  Extracted: {len(ps)} pitcher starts from boxscores")

# Compute raw per-start rates
ps["raw_k_rate_start"] = ps["k"] / ps["bf"].clip(lower=1)
ps["raw_bb_rate_start"] = ps["bb"] / ps["bf"].clip(lower=1)
ps["raw_strike_pct_start"] = ps["strikes"] / ps["pitches"].clip(lower=1)  # CSW proxy

# Merge Statcast per-start for hard-hit and barrel
sc_merge = sc[["game_pk", "pitcher_id", "hard_hit_rate", "barrel_rate", "whiff_rate"]].copy()
ps = ps.merge(sc_merge, on=["game_pk", "pitcher_id"], how="left")
ps.rename(columns={
    "hard_hit_rate": "raw_hard_hit_start",
    "barrel_rate": "raw_barrel_start",
    "whiff_rate": "raw_whiff_start",
}, inplace=True)

# Now join opponent expectation to each start
# Opponent is the batting team — look up their rolling stats
# The opponent's batting stats are in offense_table where team=opponent and side=opp_side
opp_lookup = offense_table[["game_pk", "team", "k_rate_r20", "bb_rate_r20", "runs_per_game_r20"]].copy()
opp_lookup.rename(columns={
    "team": "opponent",
    "k_rate_r20": "opp_k_rate_r20",
    "bb_rate_r20": "opp_bb_rate_r20",
    "runs_per_game_r20": "opp_runs_r20",
}, inplace=True)

ps = ps.merge(opp_lookup, on=["game_pk", "opponent"], how="left")

# Compute league averages for normalization
league_k_rate = ps["raw_k_rate_start"].mean()
league_bb_rate = ps["raw_bb_rate_start"].mean()
league_strike_pct = ps["raw_strike_pct_start"].mean()

print(f"  League averages: K_rate={league_k_rate:.4f}, BB_rate={league_bb_rate:.4f}, "
      f"strike%={league_strike_pct:.4f}")

# Opponent-adjusted metrics
# Formula: adj_metric = raw_metric - (opp_rolling - league_avg)
# If opponent K rate is ABOVE league avg, that inflates pitcher's K rate,
# so we subtract the excess.
ps["adj_k_rate_start"] = ps["raw_k_rate_start"] - (ps["opp_k_rate_r20"] - league_k_rate)
ps["adj_bb_rate_start"] = ps["raw_bb_rate_start"] - (ps["opp_bb_rate_r20"] - league_bb_rate)
# For strike%/CSW proxy: if opponent has high K rate (swings and misses more),
# that inflates strike%. Adjust same way.
ps["adj_strike_pct_start"] = ps["raw_strike_pct_start"] - (ps["opp_k_rate_r20"] - league_k_rate)

# For hard-hit: if opponent has low runs/game (weak offense), that deflates HH
# So no direct proxy from team batting. Leave hard-hit unadjusted for now.

print(f"  Adjustment coverage (2024-2025):")
ps_2425 = ps[ps["season"].isin([2024, 2025])]
for col in ["adj_k_rate_start", "adj_bb_rate_start", "adj_strike_pct_start"]:
    cov = ps_2425[col].notna().mean()
    print(f"    {col}: {cov:.1%}")

ps.to_parquet(BASE / "pitcher_start_adjusted_metrics.parquet", index=False)
print(f"  Saved pitcher_start_adjusted_metrics.parquet: {len(ps)} rows")

# Write methodology
method = [
    "# Adjustment Methodology",
    "",
    "## Concept",
    "Raw per-start metrics are inflated/deflated by opponent quality.",
    "A pitcher facing a strikeout-prone offense gets artificially high K rates.",
    "",
    "## Formula (v1 — simple league-relative subtraction)",
    "",
    "```",
    "adj_metric_start = raw_metric_start - (opponent_rolling_20g - league_avg)",
    "```",
    "",
    "### Specific Definitions",
    "",
    f"**K rate:** adj_k_rate = raw_k_rate - (opp_k_rate_r20 - {league_k_rate:.4f})",
    "- If opponent K rate is above league average, raw K rate is inflated → subtract excess",
    "",
    f"**BB rate:** adj_bb_rate = raw_bb_rate - (opp_bb_rate_r20 - {league_bb_rate:.4f})",
    "- If opponent BB rate is above league average, raw BB rate is inflated → subtract excess",
    "",
    f"**Strike% (CSW proxy):** adj_strike_pct = raw_strike_pct - (opp_k_rate_r20 - {league_k_rate:.4f})",
    "- Strike% correlates with opponent swing-and-miss tendency → adjust via K rate proxy",
    "",
    "## Opponent Rolling Features",
    "- Window: last 20 completed games per team (excluding current game)",
    "- Min periods: 10 games",
    "- Source: team batting from MLB Stats API boxscores",
    "",
    "## Limitations",
    "- No handedness split (would require pitch-level data per game)",
    "- Hard-hit / barrel not adjusted (no suitable team-level proxy available)",
    "- Strike% is an imperfect CSW proxy (includes foul balls, called strikes on takes)",
    "- Adjustment assumes linear opponent effect (v1 simplification)",
]
with open(BASE / "adjustment_methodology.md", "w") as f:
    f.write("\n".join(method) + "\n")

# =====================================================================
# STEP 3 — ROLLING RECENT FORM FEATURES
# =====================================================================
print("\n" + "=" * 60)
print("STEP 3 — ROLLING RECENT FORM FEATURES")
print("=" * 60)

# For each pitcher, compute rolling last-3 and last-5 starts
# Using only prior starts (shift(1))
metrics = {
    "raw_k_rate": "raw_k_rate_start",
    "adj_k_rate": "adj_k_rate_start",
    "raw_bb_rate": "raw_bb_rate_start",
    "adj_bb_rate": "adj_bb_rate_start",
    "raw_strike_pct": "raw_strike_pct_start",
    "adj_strike_pct": "adj_strike_pct_start",
    "raw_hard_hit": "raw_hard_hit_start",
    "raw_barrel": "raw_barrel_start",
    "raw_whiff": "raw_whiff_start",
}

ps_sorted = ps.sort_values(["pitcher_id", "date"]).copy()

print("  Computing rolling features...")
for prefix, col in metrics.items():
    for window in [3, 5]:
        feat_name = f"{prefix}_last{window}"
        ps_sorted[feat_name] = (
            ps_sorted.groupby("pitcher_id")[col]
            .transform(lambda x: x.shift(1).rolling(window, min_periods=max(2, window - 1)).mean())
        )

# Coverage check
print("  Coverage (2024-2025 starts):")
ps_2425 = ps_sorted[ps_sorted["season"].isin([2024, 2025])]
for feat in ["raw_k_rate_last3", "adj_k_rate_last3", "raw_k_rate_last5", "adj_k_rate_last5",
             "raw_strike_pct_last3", "adj_strike_pct_last3",
             "raw_hard_hit_last3", "raw_hard_hit_last5"]:
    if feat in ps_sorted.columns:
        cov = ps_2425[feat].notna().mean()
        print(f"    {feat}: {cov:.1%}")

ps_sorted.to_parquet(BASE / "pitcher_recent_form_features.parquet", index=False)
print(f"  Saved pitcher_recent_form_features.parquet: {len(ps_sorted)} rows")

# =====================================================================
# STEP 4 — BUILD RESEARCH EVALUATION DATASET
# =====================================================================
print("\n" + "=" * 60)
print("STEP 4 — RESEARCH EVALUATION DATASET")
print("=" * 60)

# Start from feature_table (2024-2025)
eval_df = ft[ft["season"].isin([2024, 2025])].copy()

# Add closing lines
eval_df = eval_df.merge(
    br[["game_id", "close_total"]].rename(columns={"game_id": "game_pk"}),
    on="game_pk", how="inner"
)
eval_df.rename(columns={"close_total": "closing_total"}, inplace=True)
print(f"  Games with closing lines: {len(eval_df)}")

# Add home SP rolling form
home_form = ps_sorted[ps_sorted["side"] == "home"][[
    "game_pk", "pitcher_id",
    "raw_k_rate_last3", "raw_k_rate_last5", "adj_k_rate_last3", "adj_k_rate_last5",
    "raw_bb_rate_last3", "raw_bb_rate_last5", "adj_bb_rate_last3", "adj_bb_rate_last5",
    "raw_strike_pct_last3", "raw_strike_pct_last5", "adj_strike_pct_last3", "adj_strike_pct_last5",
    "raw_hard_hit_last3", "raw_hard_hit_last5",
    "raw_barrel_last3", "raw_barrel_last5",
    "raw_whiff_last3", "raw_whiff_last5",
]].copy()
home_form.columns = ["game_pk", "home_sp_id_box"] + [f"home_sp_{c}" for c in home_form.columns[2:]]

away_form = ps_sorted[ps_sorted["side"] == "away"][[
    "game_pk", "pitcher_id",
    "raw_k_rate_last3", "raw_k_rate_last5", "adj_k_rate_last3", "adj_k_rate_last5",
    "raw_bb_rate_last3", "raw_bb_rate_last5", "adj_bb_rate_last3", "adj_bb_rate_last5",
    "raw_strike_pct_last3", "raw_strike_pct_last5", "adj_strike_pct_last3", "adj_strike_pct_last5",
    "raw_hard_hit_last3", "raw_hard_hit_last5",
    "raw_barrel_last3", "raw_barrel_last5",
    "raw_whiff_last3", "raw_whiff_last5",
]].copy()
away_form.columns = ["game_pk", "away_sp_id_box"] + [f"away_sp_{c}" for c in away_form.columns[2:]]

eval_df = eval_df.merge(home_form, on="game_pk", how="left")
eval_df = eval_df.merge(away_form, on="game_pk", how="left")

# Compute targets
eval_df["is_push"] = (eval_df["actual_total"] == eval_df["closing_total"])
eval_df["actual_result_under"] = (eval_df["actual_total"] < eval_df["closing_total"]).astype(int)
eval_df["implied_under"] = 0.50  # market baseline
eval_df["market_residual"] = eval_df["actual_result_under"] - eval_df["implied_under"]

# Compute combined pitcher form features (avg of home + away)
for metric in ["raw_k_rate", "adj_k_rate", "raw_bb_rate", "adj_bb_rate",
               "raw_strike_pct", "adj_strike_pct"]:
    for window in ["last3", "last5"]:
        hcol = f"home_sp_{metric}_{window}"
        acol = f"away_sp_{metric}_{window}"
        ccol = f"combined_{metric}_{window}"
        eval_df[ccol] = (eval_df[hcol] + eval_df[acol]) / 2

# Save
eval_df.to_parquet(BASE / "opponent_adjusted_research_dataset.parquet", index=False)

# Print summary
print(f"\n  Final dataset: {len(eval_df)} games")
print(f"  Non-push: {(~eval_df['is_push']).sum()}")
print(f"\n  Missingness summary (key features):")
for col in ["combined_raw_k_rate_last3", "combined_adj_k_rate_last3",
            "combined_raw_k_rate_last5", "combined_adj_k_rate_last5",
            "combined_raw_strike_pct_last3", "combined_adj_strike_pct_last3",
            "combined_raw_bb_rate_last3", "combined_adj_bb_rate_last3",
            "home_sp_raw_hard_hit_last3", "away_sp_raw_hard_hit_last3"]:
    if col in eval_df.columns:
        n = eval_df[col].notna().sum()
        print(f"    {col}: {n}/{len(eval_df)} ({100*n/len(eval_df):.1f}%)")

print("\n  Done. Dataset ready for analysis.")
