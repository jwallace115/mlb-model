#!/usr/bin/env python3
"""
Opponent-Adjusted Pitcher Form — Full v1 Engine Build
Steps 0–4: data assembly
"""

import json, os
import pandas as pd
import numpy as np
from pathlib import Path
from collections import defaultdict
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)

BASE = Path(__file__).resolve().parent
SIM = BASE.parent.parent / "sim" / "data"
STATCAST = BASE.parent / "statcast_enrichment"

# =====================================================================
# STEP 0 — SOURCE AUDIT
# =====================================================================
print("=" * 60)
print("STEP 0 — SOURCE AUDIT")
print("=" * 60)

gt = pd.read_parquet(SIM / "game_table.parquet")
gt["date"] = pd.to_datetime(gt["date"])
ft = pd.read_parquet(SIM / "feature_table.parquet")
ft["date"] = pd.to_datetime(ft["date"])
bu = pd.read_parquet(SIM / "bullpen_usage.parquet")
bu["date"] = pd.to_datetime(bu["date"])
sc = pd.read_parquet(STATCAST / "pitcher_statcast_per_start_starters_only.parquet")
sc["game_date"] = pd.to_datetime(sc["game_date"])
br = pd.read_parquet(SIM / "bet_results.parquet")
br["date"] = pd.to_datetime(br["date"])
boxscore_dir = SIM / "cache" / "boxscores"
n_box = len(os.listdir(boxscore_dir))

audit = [
    "# Source Audit — Opponent-Adjusted Engine v1",
    "",
    "| # | File | Rows | Purpose |",
    "|---|------|------|---------|",
    f"| 1 | sim/data/game_table.parquet | {len(gt)} | Canonical game table (2022-2025) |",
    f"| 2 | sim/data/feature_table.parquet | {len(ft)} | SP xFIP/K%/BB%, park factors, weather |",
    f"| 3 | sim/data/bullpen_usage.parquet | {len(bu)} | Pitcher appearances (starter identification) |",
    f"| 4 | research/statcast_enrichment/pitcher_statcast_per_start_starters_only.parquet | {len(sc)} | HH%, barrel%, whiff% per start |",
    f"| 5 | sim/data/bet_results.parquet | {len(br)} | Closing lines + outcomes (2024-2025) |",
    f"| 6 | sim/data/cache/boxscores/ | {n_box} JSON | Team batting + pitcher K/BB/strikes per game |",
    "",
    "## Key Decisions",
    "- Team offense rolling: K_rate, BB_rate, runs/game from boxscore team batting lines (last 20 games)",
    "- CSW proxy: strikes/pitches from boxscores (strike percentage; best available without pitch-level classify)",
    "- Hard-hit/barrel: raw from Statcast per-start; adjustment uses opponent runs_per_game as quality proxy",
    "  (no team-level hard-hit data available from boxscores)",
    "- Evaluation: 2024+2025 with closing lines (4,855 games)",
]
with open(BASE / "source_audit.md", "w") as f:
    f.write("\n".join(audit) + "\n")
print("  Saved source_audit.md")

# =====================================================================
# STEP 1 — OFFENSIVE EXPECTATION LAYER
# =====================================================================
print("\n" + "=" * 60)
print("STEP 1 — OFFENSIVE EXPECTATION TABLE")
print("=" * 60)

print("  Extracting team batting from boxscores...")
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
        })

tb = pd.DataFrame(team_bat_rows)
tb = tb.merge(gt[["game_pk", "date", "season"]], on="game_pk", how="left")
tb = tb.dropna(subset=["date"]).sort_values(["team", "date", "game_pk"]).reset_index(drop=True)

# Per-game rates
tb["k_rate"] = tb["k"] / tb["ab"].clip(lower=1)
tb["bb_rate"] = tb["bb"] / tb["ab"].clip(lower=1)

# Rolling last 20 games (shift to exclude current game — strict pregame)
def _rolling_offense(grp):
    grp = grp.sort_values("date").copy()
    for col, new in [("k_rate", "k_rate_r20"), ("bb_rate", "bb_rate_r20"), ("r", "runs_r20")]:
        grp[new] = grp[col].shift(1).rolling(20, min_periods=10).mean()
    return grp

tb = tb.groupby("team", group_keys=False).apply(_rolling_offense)

off_table = tb[["game_pk", "side", "team", "date", "season",
                "k_rate", "bb_rate", "r",
                "k_rate_r20", "bb_rate_r20", "runs_r20"]].copy()
off_table.to_parquet(BASE / "offense_expectation_table.parquet", index=False)

cov_2425 = off_table[off_table["season"].isin([2024, 2025])]
print(f"  Saved: {len(off_table)} rows")
print(f"  2024-2025 rolling coverage: k_rate_r20={cov_2425['k_rate_r20'].notna().mean():.1%}")

# Notes
notes = [
    "# Offense Expectation Layer — Notes",
    "",
    "## Method",
    "- Source: MLB Stats API boxscores (team batting lines)",
    "- Rolling window: last 20 completed games per team",
    "- Shift(1): excludes current game (strict pregame lookback)",
    "- Min periods: 10 games",
    "",
    "## Features",
    "- `k_rate_r20`: team K/AB rolling 20g (high = strikeout-prone)",
    "- `bb_rate_r20`: team BB/AB rolling 20g (high = patient)",
    "- `runs_r20`: team runs/game rolling 20g",
    "",
    "## Limitations",
    "- No team-level hard-hit or barrel from boxscores",
    "- No handedness split (would require pitch-level data per game)",
    "- Early-season gap (~first 10 games per team per year)",
]
with open(BASE / "offense_expectation_notes.md", "w") as f:
    f.write("\n".join(notes) + "\n")

# =====================================================================
# STEP 2 — START-LEVEL RAW + ADJUSTED METRICS
# =====================================================================
print("\n" + "=" * 60)
print("STEP 2 — RAW + ADJUSTED PITCHER START METRICS")
print("=" * 60)

print("  Extracting per-start pitcher stats from boxscores...")
ps_rows = []
for fname in os.listdir(boxscore_dir):
    game_pk = int(fname.replace(".json", ""))
    try:
        with open(boxscore_dir / fname) as f:
            box = json.load(f)
    except Exception:
        continue
    for side in ["home", "away"]:
        opp_side = "away" if side == "home" else "home"
        td = box.get("teams", {}).get(side, {})
        od = box.get("teams", {}).get(opp_side, {})
        team = td.get("team", {}).get("abbreviation", "")
        opp = od.get("team", {}).get("abbreviation", "")
        pitchers = td.get("pitchers", [])
        if not pitchers:
            continue
        starter_id = pitchers[0]
        pdata = td.get("players", {}).get(f"ID{starter_id}", {})
        pit = pdata.get("stats", {}).get("pitching", {})
        if not pit:
            continue
        bf = int(pit.get("battersFaced", 0))
        pitches = int(pit.get("pitchesThrown", 0) or pit.get("numberOfPitches", 0))
        strikes = int(pit.get("strikes", 0))
        ip_str = str(pit.get("inningsPitched", "0"))
        try:
            parts = ip_str.split(".")
            ip = int(parts[0]) + (int(parts[1]) / 3 if len(parts) > 1 else 0)
        except Exception:
            ip = 0.0
        ps_rows.append({
            "game_pk": game_pk, "pitcher_id": starter_id, "team": team,
            "opponent": opp, "side": side,
            "k": int(pit.get("strikeOuts", 0)),
            "bb": int(pit.get("baseOnBalls", 0)),
            "bf": bf, "pitches": pitches, "strikes": strikes,
            "ip": ip, "er": int(pit.get("earnedRuns", 0)),
            "pitcher_name": pdata.get("person", {}).get("fullName", ""),
        })

ps = pd.DataFrame(ps_rows)
ps = ps.merge(gt[["game_pk", "date", "season"]], on="game_pk", how="left")
ps = ps.dropna(subset=["date"]).sort_values(["pitcher_id", "date"]).reset_index(drop=True)
print(f"  Extracted: {len(ps)} pitcher starts")

# Raw per-start rates
ps["raw_k_rate_start"] = ps["k"] / ps["bf"].clip(lower=1)
ps["raw_bb_rate_start"] = ps["bb"] / ps["bf"].clip(lower=1)
ps["raw_csw_start"] = ps["strikes"] / ps["pitches"].clip(lower=1)  # strike% proxy

# Merge Statcast for hard-hit / barrel
sc_m = sc[["game_pk", "pitcher_id", "hard_hit_rate", "barrel_rate", "whiff_rate"]].copy()
ps = ps.merge(sc_m, on=["game_pk", "pitcher_id"], how="left")
ps.rename(columns={
    "hard_hit_rate": "raw_hard_hit_start",
    "barrel_rate": "raw_barrel_start",
    "whiff_rate": "raw_whiff_start",
}, inplace=True)

# Merge opponent offensive expectation
opp_cols = off_table[["game_pk", "team", "k_rate_r20", "bb_rate_r20", "runs_r20"]].rename(columns={
    "team": "opponent",
    "k_rate_r20": "opp_k_rate_r20",
    "bb_rate_r20": "opp_bb_rate_r20",
    "runs_r20": "opp_runs_r20",
})
ps = ps.merge(opp_cols, on=["game_pk", "opponent"], how="left")

# League averages
lg_k = ps["raw_k_rate_start"].mean()
lg_bb = ps["raw_bb_rate_start"].mean()
lg_csw = ps["raw_csw_start"].mean()
lg_runs = off_table["r"].mean()
lg_hh = ps["raw_hard_hit_start"].dropna().mean()
lg_barrel = ps["raw_barrel_start"].dropna().mean()

print(f"  League avgs: K_rate={lg_k:.4f}, BB_rate={lg_bb:.4f}, CSW={lg_csw:.4f}, "
      f"HH={lg_hh:.4f}, barrel={lg_barrel:.4f}")

# Adjusted metrics
# adj = raw - (opponent_rolling - league_avg)
ps["adj_k_rate_start"] = ps["raw_k_rate_start"] - (ps["opp_k_rate_r20"] - lg_k)
ps["adj_bb_rate_start"] = ps["raw_bb_rate_start"] - (ps["opp_bb_rate_r20"] - lg_bb)
ps["adj_csw_start"] = ps["raw_csw_start"] - (ps["opp_k_rate_r20"] - lg_k)

# Hard-hit/barrel adjustment: use opponent runs quality as proxy
# Weaker offense → deflated HH allowed → adjust upward
# adj_hh = raw_hh + (lg_runs - opp_runs_r20) * scaling_factor
# Scaling: 1 run difference ≈ ~2pp HH (rough calibration)
HH_RUNS_SCALE = 0.02
BARREL_RUNS_SCALE = 0.005
ps["adj_hard_hit_start"] = ps["raw_hard_hit_start"] + (lg_runs - ps["opp_runs_r20"]) * HH_RUNS_SCALE
ps["adj_barrel_start"] = ps["raw_barrel_start"] + (lg_runs - ps["opp_runs_r20"]) * BARREL_RUNS_SCALE

ps.to_parquet(BASE / "pitcher_start_adjusted_metrics.parquet", index=False)
print(f"  Saved: {len(ps)} rows")

# Coverage
ps_2425 = ps[ps["season"].isin([2024, 2025])]
for c in ["adj_k_rate_start", "adj_bb_rate_start", "adj_csw_start",
          "adj_hard_hit_start", "adj_barrel_start"]:
    cov = ps_2425[c].notna().mean()
    print(f"    {c}: {cov:.1%}")

# Methodology
method = [
    "# Adjustment Methodology — v1 Engine",
    "",
    "## Core Formula",
    "```",
    "adj_metric = raw_metric - (opponent_rolling_20g - league_avg)",
    "```",
    "",
    "## Specific Definitions",
    "",
    f"**K rate:** adj_k_rate = raw_k_rate - (opp_k_rate_r20 - {lg_k:.4f})",
    f"**BB rate:** adj_bb_rate = raw_bb_rate - (opp_bb_rate_r20 - {lg_bb:.4f})",
    f"**CSW (strike%):** adj_csw = raw_strike_pct - (opp_k_rate_r20 - {lg_k:.4f})",
    "",
    "**Hard-hit allowed:** adj_hh = raw_hh + (league_avg_runs - opp_runs_r20) × 0.02",
    "- Weaker offenses deflate HH allowed → adjust upward",
    f"- League avg runs/game: {lg_runs:.3f}",
    "",
    "**Barrel allowed:** adj_barrel = raw_barrel + (league_avg_runs - opp_runs_r20) × 0.005",
    "",
    "## Opponent Features",
    "- k_rate_r20: team K/AB, last 20 games (pregame only)",
    "- bb_rate_r20: team BB/AB, last 20 games",
    "- runs_r20: team runs/game, last 20 games",
    "",
    "## Data Sources",
    "- K, BB, BF, pitches, strikes: MLB Stats API boxscores",
    "- Hard-hit, barrel: Statcast per-start (17,906 starters)",
    "- Team batting: boxscore team batting lines",
]
with open(BASE / "adjustment_methodology.md", "w") as f:
    f.write("\n".join(method) + "\n")

# =====================================================================
# STEP 3 — ROLLING RECENT FORM
# =====================================================================
print("\n" + "=" * 60)
print("STEP 3 — ROLLING RECENT FORM FEATURES")
print("=" * 60)

metrics_map = {
    "raw_k_rate": "raw_k_rate_start",
    "adj_k_rate": "adj_k_rate_start",
    "raw_bb_rate": "raw_bb_rate_start",
    "adj_bb_rate": "adj_bb_rate_start",
    "raw_csw": "raw_csw_start",
    "adj_csw": "adj_csw_start",
    "raw_hard_hit": "raw_hard_hit_start",
    "adj_hard_hit": "adj_hard_hit_start",
    "raw_barrel": "raw_barrel_start",
    "adj_barrel": "adj_barrel_start",
    "raw_whiff": "raw_whiff_start",
}

ps = ps.sort_values(["pitcher_id", "date"]).reset_index(drop=True)

print("  Computing rolling features...")
for prefix, src_col in metrics_map.items():
    for w in [3, 5]:
        feat = f"{prefix}_last{w}"
        minp = 2 if w == 3 else 3
        ps[feat] = ps.groupby("pitcher_id")[src_col].transform(
            lambda x: x.shift(1).rolling(w, min_periods=minp).mean()
        )

# Coverage
ps_2425 = ps[ps["season"].isin([2024, 2025])]
print("  Coverage (2024-2025):")
for feat in ["raw_k_rate_last3", "adj_k_rate_last3", "raw_csw_last3", "adj_csw_last3",
             "raw_hard_hit_last3", "adj_hard_hit_last3", "raw_barrel_last3", "adj_barrel_last3"]:
    cov = ps_2425[feat].notna().mean()
    print(f"    {feat}: {cov:.1%}")

ps.to_parquet(BASE / "pitcher_recent_form_features.parquet", index=False)
print(f"  Saved: {len(ps)} rows")

# =====================================================================
# STEP 4 — GAME-LEVEL ENGINE DATASET
# =====================================================================
print("\n" + "=" * 60)
print("STEP 4 — GAME-LEVEL ENGINE DATASET")
print("=" * 60)

eval_df = ft[ft["season"].isin([2024, 2025])].copy()
eval_df = eval_df.merge(
    br[["game_id", "close_total"]].rename(columns={"game_id": "game_pk"}),
    on="game_pk", how="inner"
)
eval_df.rename(columns={"close_total": "closing_total"}, inplace=True)

# Rolling features to join
roll_cols = [c for c in ps.columns if "last" in c]
join_cols = ["game_pk", "pitcher_id"] + roll_cols

# Home SP
home_form = ps[ps["side"] == "home"][join_cols].copy()
home_form.columns = ["game_pk", "home_sp_id_box"] + [f"home_sp_{c}" for c in roll_cols]

# Away SP
away_form = ps[ps["side"] == "away"][join_cols].copy()
away_form.columns = ["game_pk", "away_sp_id_box"] + [f"away_sp_{c}" for c in roll_cols]

eval_df = eval_df.merge(home_form, on="game_pk", how="left")
eval_df = eval_df.merge(away_form, on="game_pk", how="left")

# Combined features (avg home + away)
for metric in ["raw_k_rate", "adj_k_rate", "raw_bb_rate", "adj_bb_rate",
               "raw_csw", "adj_csw", "raw_hard_hit", "adj_hard_hit",
               "raw_barrel", "adj_barrel", "raw_whiff"]:
    for w in ["last3", "last5"]:
        hc = f"home_sp_{metric}_{w}"
        ac = f"away_sp_{metric}_{w}"
        cc = f"combined_{metric}_{w}"
        if hc in eval_df.columns and ac in eval_df.columns:
            eval_df[cc] = (eval_df[hc] + eval_df[ac]) / 2

# Targets
eval_df["is_push"] = (eval_df["actual_total"] == eval_df["closing_total"])
eval_df["actual_result_under"] = (eval_df["actual_total"] < eval_df["closing_total"]).astype(int)
eval_df["implied_under"] = 0.50
eval_df["market_residual"] = eval_df["actual_result_under"] - eval_df["implied_under"]

eval_df.to_parquet(BASE / "game_level_engine_dataset.parquet", index=False)

print(f"\n  Row count: {len(eval_df)}")
print(f"  Non-push: {(~eval_df['is_push']).sum()}")
print(f"\n  Coverage (combined features):")
for c in ["combined_raw_k_rate_last3", "combined_adj_k_rate_last3",
          "combined_raw_csw_last3", "combined_adj_csw_last3",
          "combined_raw_hard_hit_last3", "combined_adj_hard_hit_last3",
          "combined_raw_barrel_last3", "combined_adj_barrel_last3"]:
    if c in eval_df.columns:
        n = eval_df[c].notna().sum()
        print(f"    {c}: {n}/{len(eval_df)} ({100*n/len(eval_df):.1f}%)")

print("\n  Steps 0-4 complete.")
