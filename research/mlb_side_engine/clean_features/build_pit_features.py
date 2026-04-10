#!/usr/bin/env python3
"""
build_pit_features.py — Point-in-time clean baseball features for MLB Side Engine

Rebuilds SP FIP, bullpen FIP, and offense RPG using only data available
BEFORE each game (strict game_date < D filter). No end-of-season leakage.

Sources:
  - mlb/data/pitcher_game_logs.parquet (84K rows, 2022-2026)
  - sim/data/game_table.parquet (9.9K games, 2022-2026)

Output:
  - research/mlb_side_engine/clean_features/baseball_features_pit.parquet
"""

import pandas as pd
import numpy as np
import time
import warnings
warnings.filterwarnings("ignore")

t0 = time.time()

# ── Team name harmonization ─────────────────────────────────────────────
# pitcher_game_logs uses FanGraphs abbreviations; game_table uses MLB Stats API.
# Map PGL names → GT names so joins work.
TEAM_MAP = {
    "AZ": "ARI",
    "CWS": "CHW",
    "KC": "KCR",
    "SD": "SDP",
    "SF": "SFG",
    "TB": "TBR",
    "WSH": "WSN",
    "ATH": "OAK",   # Athletics rebrand; game_table still uses OAK
}

# ── Load data ───────────────────────────────────────────────────────────
print("Loading data...")
pgl = pd.read_parquet("mlb/data/pitcher_game_logs.parquet")
gt = pd.read_parquet("sim/data/game_table.parquet")

pgl["game_date"] = pd.to_datetime(pgl["game_date"])
gt["date"] = pd.to_datetime(gt["date"])

# Harmonize team names in PGL to match game_table
pgl["team"] = pgl["team"].replace(TEAM_MAP)
pgl["opponent"] = pgl["opponent"].replace(TEAM_MAP)

print(f"  pitcher_game_logs: {pgl.shape[0]:,} rows")
print(f"  game_table: {gt.shape[0]:,} rows")
print()

# ── FIP constant (league average): use 3.10 as standard ────────────────
FIP_CONSTANT = 3.10

# ═══════════════════════════════════════════════════════════════════════
# PART 1: SP QUALITY (per starter, point-in-time)
# ═══════════════════════════════════════════════════════════════════════
print("Building SP features...")

starters = pgl[pgl["starter_flag"] == 1].copy()
starters = starters.sort_values(["player_id", "game_date"]).reset_index(drop=True)

# Determine home/away by matching team to game_table (home_away flag is unreliable)
gt_sides = gt[["game_pk", "home_team", "away_team"]].copy()
starters = starters.merge(gt_sides, on="game_pk", how="left")
starters["side"] = np.where(
    starters["team"] == starters["home_team"], "home",
    np.where(starters["team"] == starters["away_team"], "away", "unknown")
)
n_unknown = (starters["side"] == "unknown").sum()
if n_unknown > 0:
    print(f"  WARNING: {n_unknown} starters could not be matched to home/away")
    # Show samples
    unk = starters[starters.side == "unknown"].head(3)
    for _, r in unk.iterrows():
        print(f"    game_pk={r.game_pk} team={r.team} home={r.home_team} away={r.away_team}")

# Cumulative stats using shift(1) so current game is excluded
# Group by (player_id, season) for season-to-date metrics
for col in ["innings_pitched", "earned_runs", "strikeouts", "walks", "home_runs_allowed"]:
    starters[f"cum_{col}"] = (
        starters.groupby(["player_id", "season"])[col]
        .transform(lambda x: x.shift(1).expanding().sum())
    )

# Count prior starts this season
starters["prior_starts"] = (
    starters.groupby(["player_id", "season"]).cumcount()  # 0-indexed = prior starts
)

# Compute FIP: ((13*HR + 3*BB - 2*K) / IP) + 3.10
starters["sp_fip_pit"] = np.where(
    (starters["prior_starts"] >= 3) & (starters["cum_innings_pitched"] > 0),
    ((13 * starters["cum_home_runs_allowed"] + 3 * starters["cum_walks"] - 2 * starters["cum_strikeouts"])
     / starters["cum_innings_pitched"]) + FIP_CONSTANT,
    np.nan
)

# Compute ERA: (ER / IP) * 9
starters["sp_era_pit"] = np.where(
    (starters["prior_starts"] >= 3) & (starters["cum_innings_pitched"] > 0),
    (starters["cum_earned_runs"] / starters["cum_innings_pitched"]) * 9,
    np.nan
)

# Thin flag: fewer than 3 prior starts
starters["sp_thin"] = starters["prior_starts"] < 3
starters["sp_thin_reason"] = np.where(
    starters["sp_thin"],
    "fewer than 3 prior starts (had " + starters["prior_starts"].astype(str) + ")",
    ""
)

# Deduplicate: if multiple starters per (game_pk, side), keep the one
# with the most IP in that game (the "true" starter, not an opener)
sp_df = starters[starters.side.isin(["home", "away"])].copy()
sp_df = (
    sp_df.sort_values("innings_pitched", ascending=False)
    .drop_duplicates(subset=["game_pk", "side"], keep="first")
)

print(f"  SP rows (after dedup): {len(sp_df):,}")
print(f"  Home starters: {(sp_df.side == 'home').sum():,}")
print(f"  Away starters: {(sp_df.side == 'away').sum():,}")
print(f"  SP thin: {sp_df.sp_thin.sum():,} ({sp_df.sp_thin.mean()*100:.1f}%)")
print(f"  SP FIP non-null: {sp_df.sp_fip_pit.notna().sum():,}")
print()

# ═══════════════════════════════════════════════════════════════════════
# PART 2: BULLPEN QUALITY (per team, point-in-time)
# ═══════════════════════════════════════════════════════════════════════
print("Building bullpen features...")

relievers = pgl[pgl["starter_flag"] == 0].copy()
relievers = relievers.sort_values(["team", "season", "game_date"]).reset_index(drop=True)

# Aggregate per team-game first (a team may use multiple relievers per game)
bp_game = (
    relievers.groupby(["team", "season", "game_date", "game_pk"])
    .agg(
        bp_ip=("innings_pitched", "sum"),
        bp_er=("earned_runs", "sum"),
        bp_k=("strikeouts", "sum"),
        bp_bb=("walks", "sum"),
        bp_hr=("home_runs_allowed", "sum"),
    )
    .reset_index()
    .sort_values(["team", "season", "game_date"])
)

# Cumulative season-to-date with shift(1) — excludes current game
for col in ["bp_ip", "bp_er", "bp_k", "bp_bb", "bp_hr"]:
    bp_game[f"cum_{col}"] = (
        bp_game.groupby(["team", "season"])[col]
        .transform(lambda x: x.shift(1).expanding().sum())
    )

# Count prior team bullpen games
bp_game["bp_prior_games"] = bp_game.groupby(["team", "season"]).cumcount()

# Compute bullpen FIP
MIN_BP_IP = 20  # ~20 IP minimum for bullpen aggregate
bp_game["bp_fip_pit"] = np.where(
    (bp_game["cum_bp_ip"] >= MIN_BP_IP),
    ((13 * bp_game["cum_bp_hr"] + 3 * bp_game["cum_bp_bb"] - 2 * bp_game["cum_bp_k"])
     / bp_game["cum_bp_ip"]) + FIP_CONSTANT,
    np.nan
)

bp_game["bp_thin"] = bp_game["cum_bp_ip"] < MIN_BP_IP
bp_game["bp_thin_reason"] = np.where(
    bp_game["bp_thin"],
    "bullpen IP < 20 (had " + bp_game["cum_bp_ip"].fillna(0).astype(int).astype(str) + " IP)",
    ""
)

bp_cols = ["team", "season", "game_pk", "bp_fip_pit", "bp_thin", "bp_thin_reason"]
bp_df = bp_game[bp_cols].copy()
bp_df = bp_df.drop_duplicates(subset=["team", "game_pk"], keep="first")

print(f"  BP rows: {len(bp_df):,}")
print(f"  BP thin: {bp_df.bp_thin.sum():,} ({bp_df.bp_thin.mean()*100:.1f}%)")
print(f"  BP FIP non-null: {bp_df.bp_fip_pit.notna().sum():,}")
print()

# ═══════════════════════════════════════════════════════════════════════
# PART 3: OFFENSE QUALITY (per team, point-in-time)
# ═══════════════════════════════════════════════════════════════════════
print("Building offense features...")

# Use game_table actual scores for rolling team runs-per-game
# Build both home and away perspectives
home_runs = gt[["game_pk", "date", "season", "home_team", "home_score"]].rename(
    columns={"home_team": "team", "home_score": "runs_scored"}
)
away_runs = gt[["game_pk", "date", "season", "away_team", "away_score"]].rename(
    columns={"away_team": "team", "away_score": "runs_scored"}
)
team_runs = pd.concat([home_runs, away_runs], ignore_index=True)
team_runs = team_runs.sort_values(["team", "season", "date"]).reset_index(drop=True)

# Drop rows with null scores (future games, incomplete)
team_runs = team_runs.dropna(subset=["runs_scored"])

# Rolling 20-game runs per game, shifted by 1 (pregame-safe)
# Use expanding for early season (< 20 games), then rolling
team_runs["rpg_20"] = (
    team_runs.groupby(["team", "season"])["runs_scored"]
    .transform(lambda x: x.shift(1).rolling(20, min_periods=5).mean())
)

team_runs["offense_thin"] = team_runs["rpg_20"].isna()
team_runs["prior_team_games"] = team_runs.groupby(["team", "season"]).cumcount()
team_runs["offense_thin_reason"] = np.where(
    team_runs["offense_thin"],
    "fewer than 5 prior team games (had " + team_runs["prior_team_games"].astype(str) + ")",
    ""
)

off_cols = ["team", "season", "game_pk", "rpg_20", "offense_thin", "offense_thin_reason"]
off_df = team_runs[off_cols].copy()
off_df = off_df.rename(columns={"rpg_20": "offense_rpg_pit"})

print(f"  Offense rows: {len(off_df):,}")
print(f"  Offense thin: {off_df.offense_thin.sum():,} ({off_df.offense_thin.mean()*100:.1f}%)")
print(f"  Offense RPG non-null: {off_df.offense_rpg_pit.notna().sum():,}")
print()

# ═══════════════════════════════════════════════════════════════════════
# PART 4: JOIN TO GAME TABLE
# ═══════════════════════════════════════════════════════════════════════
print("Joining features to game table...")

games = gt[["game_pk", "date", "season", "home_team", "away_team"]].copy()

# ── Join SP features ──
# Use side column (determined from team match to game_table) rather than home_away flag
home_sp = sp_df[sp_df.side == "home"][["game_pk", "sp_fip_pit", "sp_era_pit", "sp_thin", "sp_thin_reason"]].rename(
    columns={"sp_fip_pit": "home_sp_fip_pit", "sp_era_pit": "home_sp_era_pit",
             "sp_thin": "home_sp_thin", "sp_thin_reason": "home_sp_thin_reason"}
)
away_sp = sp_df[sp_df.side == "away"][["game_pk", "sp_fip_pit", "sp_era_pit", "sp_thin", "sp_thin_reason"]].rename(
    columns={"sp_fip_pit": "away_sp_fip_pit", "sp_era_pit": "away_sp_era_pit",
             "sp_thin": "away_sp_thin", "sp_thin_reason": "away_sp_thin_reason"}
)

games = games.merge(home_sp, on="game_pk", how="left")
games = games.merge(away_sp, on="game_pk", how="left")

# ── Join BP features ──
games = games.merge(
    bp_df[["team", "game_pk", "bp_fip_pit", "bp_thin", "bp_thin_reason"]].rename(columns={
        "bp_fip_pit": "home_bp_fip_pit", "bp_thin": "home_bp_thin",
        "bp_thin_reason": "home_bp_thin_reason"
    }),
    left_on=["home_team", "game_pk"], right_on=["team", "game_pk"], how="left"
).drop(columns=["team"])

games = games.merge(
    bp_df[["team", "game_pk", "bp_fip_pit", "bp_thin", "bp_thin_reason"]].rename(columns={
        "bp_fip_pit": "away_bp_fip_pit", "bp_thin": "away_bp_thin",
        "bp_thin_reason": "away_bp_thin_reason"
    }),
    left_on=["away_team", "game_pk"], right_on=["team", "game_pk"], how="left"
).drop(columns=["team"])

# BP FIP diff
games["bp_fip_diff_pit"] = games["home_bp_fip_pit"] - games["away_bp_fip_pit"]

# ── Join offense features ──
games = games.merge(
    off_df[["team", "game_pk", "offense_rpg_pit", "offense_thin", "offense_thin_reason"]].rename(columns={
        "offense_rpg_pit": "home_offense_rpg_pit", "offense_thin": "home_offense_thin",
        "offense_thin_reason": "home_offense_thin_reason"
    }),
    left_on=["home_team", "game_pk"], right_on=["team", "game_pk"], how="left"
).drop(columns=["team"])

games = games.merge(
    off_df[["team", "game_pk", "offense_rpg_pit", "offense_thin", "offense_thin_reason"]].rename(columns={
        "offense_rpg_pit": "away_offense_rpg_pit", "offense_thin": "away_offense_thin",
        "offense_thin_reason": "away_offense_thin_reason"
    }),
    left_on=["away_team", "game_pk"], right_on=["team", "game_pk"], how="left"
).drop(columns=["team"])

# ── Composite thin flags ──
games["sp_sample_thin"] = games["home_sp_thin"].fillna(True) | games["away_sp_thin"].fillna(True)
games["bp_sample_thin"] = games["home_bp_thin"].fillna(True) | games["away_bp_thin"].fillna(True)
games["offense_sample_thin"] = games["home_offense_thin"].fillna(True) | games["away_offense_thin"].fillna(True)

# Build composite thin reason
def _combine_reasons(row, prefix):
    parts = []
    for side in ["home", "away"]:
        thin_val = row.get(f"{side}_{prefix}_thin", None)
        reason_val = row.get(f"{side}_{prefix}_thin_reason", "")
        if pd.isna(thin_val):
            parts.append(f"{side}: no data in source")
        elif thin_val and pd.notna(reason_val) and str(reason_val).strip():
            parts.append(f"{side}: {reason_val}")
    return "; ".join(parts)

games["sp_sample_thin_reason"] = games.apply(lambda r: _combine_reasons(r, "sp"), axis=1)
games["bp_sample_thin_reason"] = games.apply(lambda r: _combine_reasons(r, "bp"), axis=1)
games["offense_sample_thin_reason"] = games.apply(lambda r: _combine_reasons(r, "offense"), axis=1)

# ── Final schema ──
output_cols = [
    "game_pk", "date", "home_team", "away_team",
    "home_sp_fip_pit", "away_sp_fip_pit",
    "home_sp_era_pit", "away_sp_era_pit",
    "home_bp_fip_pit", "away_bp_fip_pit", "bp_fip_diff_pit",
    "home_offense_rpg_pit", "away_offense_rpg_pit",
    "sp_sample_thin", "bp_sample_thin", "offense_sample_thin",
    "sp_sample_thin_reason", "bp_sample_thin_reason", "offense_sample_thin_reason",
]

out = games[output_cols].copy()
# Safety dedup: if any join expanded rows, keep first per game_pk
pre_dedup = len(out)
out = out.drop_duplicates(subset=["game_pk"], keep="first")
if len(out) < pre_dedup:
    print(f"  WARNING: dropped {pre_dedup - len(out)} duplicate game_pk rows after join")
out = out.sort_values(["date", "game_pk"]).reset_index(drop=True)
assert len(out) == out.game_pk.nunique(), "FATAL: game_pk not unique in output"

outpath = "research/mlb_side_engine/clean_features/baseball_features_pit.parquet"
out.to_parquet(outpath, index=False)
print(f"Saved {outpath}: {out.shape}")
print()

# ═══════════════════════════════════════════════════════════════════════
# PART 5: COVERAGE REPORT
# ═══════════════════════════════════════════════════════════════════════
print("=" * 70)
print("COVERAGE REPORT")
print("=" * 70)

total = len(out)
print(f"\nTotal games in output: {total:,}")
print(f"Total games in game_table: {len(gt):,}")
print()

# By season
print("By season:")
for szn in sorted(out.date.dt.year.unique()):
    sub = out[out.date.dt.year == szn]
    n = len(sub)
    sp_ok = sub.home_sp_fip_pit.notna().sum()
    bp_ok = sub.home_bp_fip_pit.notna().sum()
    off_ok = sub.home_offense_rpg_pit.notna().sum()
    print(f"  {szn}: {n:,} games | SP FIP: {sp_ok}/{n} ({sp_ok/n*100:.0f}%) | BP FIP: {bp_ok}/{n} ({bp_ok/n*100:.0f}%) | Offense: {off_ok}/{n} ({off_ok/n*100:.0f}%)")

print()

# By month (all seasons combined)
print("By month (all seasons):")
for m in range(3, 11):
    sub = out[out.date.dt.month == m]
    if len(sub) == 0:
        continue
    n = len(sub)
    sp_ok = sub.home_sp_fip_pit.notna().sum() + sub.away_sp_fip_pit.notna().sum()
    sp_total = n * 2
    print(f"  Month {m:2d}: {n:,} games | SP FIP fill: {sp_ok}/{sp_total} ({sp_ok/sp_total*100:.0f}%)")

print()

# April coverage (where thin flags matter most)
print("April coverage (thin flags):")
for szn in sorted(out.date.dt.year.unique()):
    apr = out[(out.date.dt.year == szn) & (out.date.dt.month == 4)]
    if len(apr) == 0:
        continue
    n = len(apr)
    sp_thin = apr.sp_sample_thin.sum()
    bp_thin = apr.bp_sample_thin.sum()
    off_thin = apr.offense_sample_thin.sum()
    print(f"  April {szn}: {n} games | SP thin: {sp_thin}/{n} ({sp_thin/n*100:.0f}%) | BP thin: {bp_thin}/{n} ({bp_thin/n*100:.0f}%) | Offense thin: {off_thin}/{n} ({off_thin/n*100:.0f}%)")

print()

# Non-null rates
print("Non-null rates (overall):")
for col in ["home_sp_fip_pit", "away_sp_fip_pit", "home_sp_era_pit", "away_sp_era_pit",
            "home_bp_fip_pit", "away_bp_fip_pit",
            "home_offense_rpg_pit", "away_offense_rpg_pit"]:
    nn = out[col].notna().sum()
    print(f"  {col}: {nn}/{total} ({nn/total*100:.1f}%)")

print()

# ═══════════════════════════════════════════════════════════════════════
# PART 6: VALIDATION CHECKS
# ═══════════════════════════════════════════════════════════════════════
print("=" * 70)
print("VALIDATION CHECKS")
print("=" * 70)

# ── Check 1: Spot check 5 random mid-2024 games ──
print("\n--- CHECK 1: Spot check 5 mid-2024 games (manual FIP verification) ---")
mid24 = out[(out.date >= "2024-06-01") & (out.date < "2024-08-01") & out.home_sp_fip_pit.notna()]
np.random.seed(42)
sample_gpks = mid24.sample(min(5, len(mid24))).game_pk.values

for gpk in sample_gpks:
    row = out[out.game_pk == gpk].iloc[0]
    print(f"\n  game_pk={gpk} | {row.date.date()} | {row.away_team} @ {row.home_team}")
    print(f"    home SP FIP: {row.home_sp_fip_pit:.3f}" if pd.notna(row.home_sp_fip_pit) else "    home SP FIP: NaN")
    print(f"    away SP FIP: {row.away_sp_fip_pit:.3f}" if pd.notna(row.away_sp_fip_pit) else "    away SP FIP: NaN")

    # Manual recompute for home starter
    home_starter_rows = sp_df[(sp_df.game_pk == gpk) & (sp_df.side == "home")]
    if len(home_starter_rows) > 0:
        hs = home_starter_rows.iloc[0]
        pid = hs.player_id
        szn = hs.season
        prior = starters[(starters.player_id == pid) & (starters.season == szn) & (starters.game_date < hs.game_date)]
        if len(prior) >= 3:
            ip = prior.innings_pitched.sum()
            hr = prior.home_runs_allowed.sum()
            bb = prior.walks.sum()
            k = prior.strikeouts.sum()
            manual_fip = ((13*hr + 3*bb - 2*k) / ip) + 3.10
            print(f"    manual recompute home SP FIP: {manual_fip:.3f} (from {len(prior)} starts, {ip:.1f} IP)")
            delta = abs(manual_fip - row.home_sp_fip_pit)
            print(f"    MATCH: {'YES' if delta < 0.001 else 'NO'} (delta={delta:.6f})")
        else:
            print(f"    manual: only {len(prior)} prior starts — should be thin")

print()

# ── Check 2: Early season — April 15 games, thin flags ──
print("--- CHECK 2: April 15 games, thin flag check ---")
apr15 = out[(out.date >= "2024-04-07") & (out.date <= "2024-04-15")]
n_apr = len(apr15)
sp_thin_apr = apr15.sp_sample_thin.sum()
print(f"  Games Apr 7-15, 2024: {n_apr}")
print(f"  SP thin: {sp_thin_apr}/{n_apr} ({sp_thin_apr/n_apr*100:.0f}%)")
print(f"  Expected: most games should have thin SP flags in first 2 weeks")
print(f"  PASS: {'YES' if sp_thin_apr / n_apr > 0.5 else 'NO'}")
print()

# ── Check 3: Late season — September values != season-final ──
print("--- CHECK 3: Late season vs season-final divergence ---")
# Pick a pitcher with many starts in 2024
top_pitchers = starters[starters.season == 2024].groupby("player_id").size().nlargest(5)
for pid in top_pitchers.index[:2]:
    pdata = starters[(starters.player_id == pid) & (starters.season == 2024)].sort_values("game_date")
    pname = pdata.iloc[0].player_name

    # September value (point-in-time)
    sept = pdata[pdata.game_date.dt.month == 9]
    if len(sept) == 0:
        continue
    sept_row = sept.iloc[0]
    pit_fip = sept_row.sp_fip_pit

    # Season-final (full season aggregate)
    full_ip = pdata.innings_pitched.sum()
    full_hr = pdata.home_runs_allowed.sum()
    full_bb = pdata.walks.sum()
    full_k = pdata.strikeouts.sum()
    final_fip = ((13*full_hr + 3*full_bb - 2*full_k) / full_ip) + 3.10

    print(f"  {pname} (id={pid}):")
    print(f"    Sept 1 PIT FIP: {pit_fip:.3f}" if pd.notna(pit_fip) else f"    Sept 1 PIT FIP: NaN")
    print(f"    Season-final FIP: {final_fip:.3f}")
    delta = abs(pit_fip - final_fip) if pd.notna(pit_fip) else float("nan")
    print(f"    Delta: {delta:.3f}")
    print(f"    Different (as expected): {'YES' if delta > 0.01 else 'NO'}")

print()

# ── Check 4: Idempotency — recompute a few rows, verify identical ──
print("--- CHECK 4: Idempotency (recompute, verify identical) ---")
check_gpks = sample_gpks[:3]
all_match = True
for gpk in check_gpks:
    row = out[out.game_pk == gpk].iloc[0]
    home_starter_rows = sp_df[(sp_df.game_pk == gpk) & (sp_df.side == "home")]
    if len(home_starter_rows) > 0 and pd.notna(row.home_sp_fip_pit):
        hs = home_starter_rows.iloc[0]
        pid = hs.player_id
        szn = hs.season
        prior = starters[(starters.player_id == pid) & (starters.season == szn) & (starters.game_date < hs.game_date)]
        if len(prior) >= 3:
            ip = prior.innings_pitched.sum()
            hr = prior.home_runs_allowed.sum()
            bb = prior.walks.sum()
            k = prior.strikeouts.sum()
            manual_fip = ((13*hr + 3*bb - 2*k) / ip) + 3.10
            if abs(manual_fip - row.home_sp_fip_pit) > 0.001:
                all_match = False
                print(f"  MISMATCH for game_pk={gpk}")

print(f"  Idempotency check: {'PASS' if all_match else 'FAIL'}")
print()

# ── Summary stats ──
print("=" * 70)
print("FEATURE SUMMARY STATISTICS")
print("=" * 70)
for col in ["home_sp_fip_pit", "away_sp_fip_pit", "home_bp_fip_pit", "away_bp_fip_pit",
            "home_offense_rpg_pit", "away_offense_rpg_pit"]:
    print(f"\n{col}:")
    print(out[col].describe().to_string())

elapsed = time.time() - t0
print(f"\n\nDone in {elapsed:.1f}s")
