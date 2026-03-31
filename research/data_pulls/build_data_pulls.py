#!/usr/bin/env python3
"""
Two background data pulls:
  PULL 1 — Lineup batted ball profiles
  PULL 2 — Reliever role tracking
"""

import json
import os
import pandas as pd
import numpy as np
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")

BASE = Path(__file__).resolve().parent
SIM = BASE.parent.parent / "sim" / "data"
BOXSCORE_DIR = SIM / "cache" / "boxscores"

# =====================================================================
# PULL 1 — LINEUP BATTED BALL PROFILES
# =====================================================================
print("=" * 60)
print("PULL 1 — LINEUP BATTED BALL PROFILES")
print("=" * 60)

# Strategy:
# - contact_rate (H/AB), ISO (SLG-AVG), groundOut/flyOut ratio: from boxscores
# - hard_hit_rate, barrel_rate, avg_launch_angle: from Statcast per-start
#   (use opponent pitcher's allowed stats as proxy for what lineup produced)
# - pull_pct: derive from groundOuts vs flyOuts ratio as rough proxy
#   (not true pull%, but groundOut-heavy = more pull tendency)

gt = pd.read_parquet(SIM / "game_table.parquet")
gt["date"] = pd.to_datetime(gt["date"])

# ── Extract team batting from boxscores ──────────────────────────────
print("  Extracting team batting from boxscores...")
bat_rows = []
for fname in os.listdir(BOXSCORE_DIR):
    game_pk = int(fname.replace(".json", ""))
    try:
        with open(BOXSCORE_DIR / fname) as f:
            box = json.load(f)
    except Exception:
        continue
    for side in ["home", "away"]:
        td = box.get("teams", {}).get(side, {})
        team = td.get("team", {}).get("abbreviation", "")
        bat = td.get("teamStats", {}).get("batting", {})
        if not bat:
            continue

        ab = int(bat.get("atBats", 0))
        h = int(bat.get("hits", 0))
        doubles = int(bat.get("doubles", 0))
        triples = int(bat.get("triples", 0))
        hr = int(bat.get("homeRuns", 0))
        total_bases = int(bat.get("totalBases", 0))
        ground_outs = int(bat.get("groundOuts", 0))
        fly_outs = int(bat.get("flyOuts", 0))
        air_outs = int(bat.get("airOuts", 0))
        line_outs = int(bat.get("lineOuts", 0))
        pop_outs = int(bat.get("popOuts", 0))

        # Derived
        avg = h / max(ab, 1)
        slg = total_bases / max(ab, 1)
        iso = slg - avg
        contact_rate = avg  # H/AB
        # Pull proxy: ground outs / total outs (higher ground out ratio = more pull)
        total_outs = ground_outs + fly_outs + air_outs + line_outs + pop_outs
        pull_proxy = ground_outs / max(total_outs, 1)

        bat_rows.append({
            "game_pk": game_pk, "side": side, "team": team,
            "ab": ab, "h": h, "doubles": doubles, "triples": triples, "hr": hr,
            "total_bases": total_bases, "ground_outs": ground_outs,
            "fly_outs": fly_outs, "air_outs": air_outs,
            "contact_rate": contact_rate,
            "iso": iso,
            "pull_proxy": pull_proxy,
        })

tb = pd.DataFrame(bat_rows)
tb = tb.merge(gt[["game_pk", "date", "season"]], on="game_pk", how="left")
tb = tb.dropna(subset=["date"]).sort_values(["team", "date", "game_pk"]).reset_index(drop=True)
print(f"  Extracted: {len(tb)} team-game batting lines")

# ── Add Statcast batted-ball from opponent pitcher ───────────────────
# For a team's batting line, the "quality of contact" they produced
# is proxied by what the opposing pitcher allowed that game.
# Join: for home team batting, look at away pitcher's statcast.
print("  Joining Statcast pitcher-allowed as batting quality proxy...")

sc = pd.read_parquet(BASE.parent / "statcast_enrichment" /
                     "pitcher_statcast_per_start_starters_only.parquet")
sc["game_date"] = pd.to_datetime(sc["game_date"])

# For each game, get home and away pitcher statcast
# The game_starter_pairs file maps this
pairs = pd.read_parquet(BASE.parent / "statcast_enrichment" / "game_starter_pairs_clean.parquet")
pairs_cols = pairs.columns.tolist()
print(f"  game_starter_pairs cols: {pairs_cols[:10]}")

# Use Statcast per-start directly: each pitcher's allowed hard-hit/barrel/launch angle
# For the batting team: their contact quality = what the opposing pitcher allowed
# home batting quality = away pitcher's hard_hit_rate, barrel_rate, avg_launch_angle
# away batting quality = home pitcher's hard_hit_rate, barrel_rate, avg_launch_angle

sc_game = sc[["game_pk", "pitcher_id", "hard_hit_rate", "barrel_rate", "avg_launch_angle"]].copy()

# Identify which pitcher was home vs away using bullpen_usage
bu = pd.read_parquet(SIM / "bullpen_usage.parquet")
bu["date"] = pd.to_datetime(bu["date"])
starters = bu[bu["is_starter"]][["game_pk", "pitcher_id", "team"]].copy()

# Merge team info onto statcast
sc_team = sc_game.merge(starters[["game_pk", "pitcher_id", "team"]], on=["game_pk", "pitcher_id"], how="left")

# For home team batting: use away pitcher's stats
# Need to know which team is home/away
sc_team = sc_team.merge(gt[["game_pk", "home_team", "away_team"]], on="game_pk", how="left")
sc_team["pitcher_side"] = np.where(sc_team["team"] == sc_team["home_team"], "home", "away")

# Home team batting quality = away pitcher's allowed stats
away_pitchers = sc_team[sc_team["pitcher_side"] == "away"][
    ["game_pk", "hard_hit_rate", "barrel_rate", "avg_launch_angle"]].rename(
    columns={"hard_hit_rate": "opp_hard_hit", "barrel_rate": "opp_barrel",
             "avg_launch_angle": "opp_launch_angle"})
away_pitchers["bat_side"] = "home"

home_pitchers = sc_team[sc_team["pitcher_side"] == "home"][
    ["game_pk", "hard_hit_rate", "barrel_rate", "avg_launch_angle"]].rename(
    columns={"hard_hit_rate": "opp_hard_hit", "barrel_rate": "opp_barrel",
             "avg_launch_angle": "opp_launch_angle"})
home_pitchers["bat_side"] = "away"

opp_stats = pd.concat([away_pitchers, home_pitchers], ignore_index=True)
opp_stats.rename(columns={"bat_side": "side"}, inplace=True)

tb = tb.merge(opp_stats, on=["game_pk", "side"], how="left")
statcast_cov = tb["opp_hard_hit"].notna().mean()
print(f"  Statcast proxy coverage: {statcast_cov:.1%}")

# ── Rolling 20 games (shift to exclude current) ─────────────────────
print("  Computing rolling 20-game features...")

def rolling_lineup(grp):
    grp = grp.sort_values("date").copy()
    for col, new in [
        ("contact_rate", "team_lineup_contact_rate"),
        ("opp_hard_hit", "team_lineup_hard_hit_rate"),
        ("opp_barrel", "team_lineup_barrel_rate"),
        ("pull_proxy", "team_lineup_pull_pct"),
        ("opp_launch_angle", "team_lineup_avg_launch_angle"),
        ("iso", "team_lineup_iso"),
    ]:
        grp[new] = grp[col].shift(1).rolling(20, min_periods=10).mean()
    return grp

tb = tb.groupby("team", group_keys=False).apply(rolling_lineup)

# ── Save ─────────────────────────────────────────────────────────────
out_cols = ["game_pk", "side", "team", "date", "season",
            "team_lineup_contact_rate", "team_lineup_hard_hit_rate",
            "team_lineup_barrel_rate", "team_lineup_pull_pct",
            "team_lineup_avg_launch_angle", "team_lineup_iso"]
lineup_out = tb[out_cols].copy()
lineup_out.to_parquet(BASE / "lineup_batted_ball_profiles.parquet", index=False)

print(f"\n  Saved: {len(lineup_out)} rows")
print(f"  Coverage (2024-2025):")
out_2425 = lineup_out[lineup_out["season"].isin([2024, 2025])]
for c in out_cols[5:]:
    n = out_2425[c].notna().sum()
    print(f"    {c}: {n}/{len(out_2425)} ({100*n/len(out_2425):.1f}%)")

# Scanner dataset coverage
br = pd.read_parquet(SIM / "bet_results.parquet")
scanner_pks = set(br["game_id"])
lineup_pks = set(lineup_out[lineup_out["team_lineup_contact_rate"].notna()]["game_pk"])
overlap = scanner_pks & lineup_pks
print(f"\n  Scanner dataset overlap: {len(overlap)}/{len(scanner_pks)} ({100*len(overlap)/len(scanner_pks):.1f}%)")


# =====================================================================
# PULL 2 — RELIEVER ROLE TRACKING
# =====================================================================
print("\n" + "=" * 60)
print("PULL 2 — RELIEVER ROLE TRACKING")
print("=" * 60)

bu = pd.read_parquet(SIM / "bullpen_usage.parquet")
bu["date"] = pd.to_datetime(bu["date"])
bp = bu[~bu["is_starter"]].copy()

print(f"  Reliever appearances: {len(bp)}")

# ── Identify roles by season ─────────────────────────────────────────
# Closer: pitcher with most games_finished per team-season
# Setup: pitcher with 2nd most IP in high-leverage (use games_finished as proxy for leverage)
print("  Identifying closer and setup by team-season...")

role_stats = bp.groupby(["team", "season", "pitcher_id"]).agg(
    total_gf=("games_finished", "sum"),
    total_ip=("innings_pitched", "sum"),
    total_games=("game_pk", "nunique"),
).reset_index()

# Closer = max games_finished
closers = role_stats.sort_values("total_gf", ascending=False).drop_duplicates(
    subset=["team", "season"], keep="first")[["team", "season", "pitcher_id"]].rename(
    columns={"pitcher_id": "closer_id"})

# Setup = 2nd most games_finished (excluding closer)
role_no_closer = role_stats.merge(closers, on=["team", "season"], how="left")
role_no_closer = role_no_closer[role_no_closer["pitcher_id"] != role_no_closer["closer_id"]]
setups = role_no_closer.sort_values("total_gf", ascending=False).drop_duplicates(
    subset=["team", "season"], keep="first")[["team", "season", "pitcher_id"]].rename(
    columns={"pitcher_id": "setup_id"})

# Top 3 relievers by IP per team-season
top3 = role_stats.sort_values(["team", "season", "total_ip"], ascending=[True, True, False])
top3_ids = top3.groupby(["team", "season"]).head(3)[["team", "season", "pitcher_id"]].copy()
top3_ids["is_top3"] = True

print(f"  Closers identified: {len(closers)} team-seasons")
print(f"  Setups identified: {len(setups)} team-seasons")

# ── Tag appearances ──────────────────────────────────────────────────
bp = bp.merge(closers, on=["team", "season"], how="left")
bp = bp.merge(setups, on=["team", "season"], how="left")
bp = bp.merge(top3_ids, on=["team", "season", "pitcher_id"], how="left")

bp["is_closer"] = bp["pitcher_id"] == bp["closer_id"]
bp["is_setup"] = bp["pitcher_id"] == bp["setup_id"]
bp["is_top3"] = bp["is_top3"].fillna(False)

# ── Per team-date aggregations ───────────────────────────────────────
bp_daily = bp.sort_values(["team", "date"]).copy()

# Daily closer appearances
closer_daily = bp_daily[bp_daily["is_closer"]].groupby(["team", "date"]).agg(
    closer_appeared=("game_pk", "size")
).reset_index()
closer_daily["closer_appeared"] = 1

# Daily setup appearances
setup_daily = bp_daily[bp_daily["is_setup"]].groupby(["team", "date"]).agg(
    setup_appeared=("game_pk", "size")
).reset_index()
setup_daily["setup_appeared"] = 1

# Daily top-3 relievers IP
top3_daily = bp_daily[bp_daily["is_top3"]].groupby(["team", "date"]).agg(
    top3_ip=("innings_pitched", "sum")
).reset_index()

# Daily total bullpen IP (for high-leverage proxy)
bp_ip_daily = bp_daily.groupby(["team", "date"]).agg(
    total_bp_ip=("innings_pitched", "sum")
).reset_index()

# ── Merge into single daily table ────────────────────────────────────
# Build full team-date grid
all_team_dates = bp_daily[["team", "date"]].drop_duplicates().sort_values(["team", "date"])
daily = all_team_dates.merge(closer_daily, on=["team", "date"], how="left")
daily = daily.merge(setup_daily, on=["team", "date"], how="left")
daily = daily.merge(top3_daily, on=["team", "date"], how="left")
daily = daily.merge(bp_ip_daily, on=["team", "date"], how="left")

daily["closer_appeared"] = daily["closer_appeared"].fillna(0).astype(int)
daily["setup_appeared"] = daily["setup_appeared"].fillna(0).astype(int)
daily["top3_ip"] = daily["top3_ip"].fillna(0)
daily["total_bp_ip"] = daily["total_bp_ip"].fillna(0)

# ── Rolling lookbacks ────────────────────────────────────────────────
print("  Computing rolling reliever tracking features...")

def rolling_reliever(grp):
    grp = grp.sort_values("date").copy()
    dates = grp["date"].values
    closer = grp["closer_appeared"].values
    setup = grp["setup_appeared"].values
    top3_ip_arr = grp["top3_ip"].values
    total_bp_arr = grp["total_bp_ip"].values

    closer_last2d = []
    setup_last2d = []
    top3_ip_last3d = []
    bp_hlev_last3d = []

    for i, d in enumerate(dates):
        d_ts = pd.Timestamp(d)
        m2 = (dates < d) & (dates >= (d_ts - pd.Timedelta(days=2)).to_numpy())
        m3 = (dates < d) & (dates >= (d_ts - pd.Timedelta(days=3)).to_numpy())

        closer_last2d.append(1 if closer[m2].sum() > 0 else 0)
        setup_last2d.append(1 if setup[m2].sum() > 0 else 0)
        top3_ip_last3d.append(top3_ip_arr[m3].sum())
        bp_hlev_last3d.append(total_bp_arr[m3].sum())  # total BP IP as high-leverage proxy

    grp["closer_pitched_last2days"] = closer_last2d
    grp["setup_pitcher_pitched_last2days"] = setup_last2d
    grp["top_3_relievers_ip_last3d"] = top3_ip_last3d
    grp["bullpen_high_leverage_ip_last3d"] = bp_hlev_last3d
    return grp

daily = daily.groupby("team", group_keys=False).apply(rolling_reliever)

# ── Join to game table for game_pk ───────────────────────────────────
# Each game has home + away
gt_slim = gt[["game_pk", "date", "home_team", "away_team"]].copy()

# Home team reliever tracking
home_rel = daily.rename(columns={"team": "home_team"})[
    ["home_team", "date", "closer_pitched_last2days", "setup_pitcher_pitched_last2days",
     "top_3_relievers_ip_last3d", "bullpen_high_leverage_ip_last3d"]]
home_rel.columns = ["home_team", "date"] + [f"home_{c}" for c in [
    "closer_pitched_last2days", "setup_pitcher_pitched_last2days",
    "top_3_relievers_ip_last3d", "bullpen_high_leverage_ip_last3d"]]

away_rel = daily.rename(columns={"team": "away_team"})[
    ["away_team", "date", "closer_pitched_last2days", "setup_pitcher_pitched_last2days",
     "top_3_relievers_ip_last3d", "bullpen_high_leverage_ip_last3d"]]
away_rel.columns = ["away_team", "date"] + [f"away_{c}" for c in [
    "closer_pitched_last2days", "setup_pitcher_pitched_last2days",
    "top_3_relievers_ip_last3d", "bullpen_high_leverage_ip_last3d"]]

reliever_out = gt_slim.merge(home_rel, on=["home_team", "date"], how="left")
reliever_out = reliever_out.merge(away_rel, on=["away_team", "date"], how="left")

# Add season
reliever_out = reliever_out.merge(gt[["game_pk", "season"]], on="game_pk", how="left")

reliever_out.to_parquet(BASE / "reliever_role_tracking.parquet", index=False)

print(f"\n  Saved: {len(reliever_out)} rows")
print(f"  Coverage (2024-2025):")
rel_2425 = reliever_out[reliever_out["season"].isin([2024, 2025])]
for c in [col for col in reliever_out.columns if col.startswith("home_") or col.startswith("away_")]:
    n = rel_2425[c].notna().sum()
    print(f"    {c}: {n}/{len(rel_2425)} ({100*n/len(rel_2425):.1f}%)")

# Scanner dataset coverage
rel_pks = set(reliever_out[reliever_out["home_closer_pitched_last2days"].notna()]["game_pk"])
overlap2 = scanner_pks & rel_pks
print(f"\n  Scanner dataset overlap: {len(overlap2)}/{len(scanner_pks)} ({100*len(overlap2)/len(scanner_pks):.1f}%)")

print("\nDone. Both pulls complete.")
