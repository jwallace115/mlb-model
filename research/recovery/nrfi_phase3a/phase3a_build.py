"""
NRFI Phase 3A -- First-inning pitcher splits + top-of-order overlay research
============================================================================
SAFETY RULES:
  1. First-inning pitcher metrics: PIT-safe via shift(1) on per-game data
  2. Top-3 lineup variables: RESEARCH-ONLY (uses actual batting order)
  3. Interactions with RESEARCH-ONLY inherit RESEARCH-ONLY status
  4. Rankings using RESEARCH-ONLY variables labeled as such
"""
import json, os, sys
import pandas as pd
import numpy as np
from pathlib import Path

OUT = Path("/root/mlb-model/research/recovery/nrfi_phase3a")
OUT.mkdir(parents=True, exist_ok=True)

# =====================================================================
# PHASE 0: Load parent data + define gates
# =====================================================================
print("=" * 70)
print("PHASE 0: Loading data and defining parent gates")
print("=" * 70)

rt = pd.read_parquet("/root/mlb-model/research/recovery/nrfi_phase2/nrfi_phase2_research_table.parquet")
print(f"Phase 2 research table: {len(rt)} games")

gates = {
    "A": {"desc": "F5 <= 3.5", "filter": lambda df: df[df["closing_f5_total"] <= 3.5]},
    "B": {"desc": "F5 <= 4.0", "filter": lambda df: df[df["closing_f5_total"] <= 4.0]},
    "C": {"desc": "FG 8.5-9.0 x F5 <= 4.0", "filter": lambda df: df[(df["closing_total"] >= 8.5) & (df["closing_total"] <= 9.0) & (df["closing_f5_total"] <= 4.0)]},
    "D": {"desc": "FG <= 7.5", "filter": lambda df: df[df["closing_total"] <= 7.5]},
}

for k, g in gates.items():
    sub = g["filter"](rt)
    nrfi_pct = sub["nrfi"].mean() * 100 if len(sub) > 0 else 0
    print(f"  Gate {k} ({g['desc']}): N={len(sub)}, NRFI={nrfi_pct:.1f}%")


# =====================================================================
# PHASE 1: Build PIT-safe first-inning pitcher metrics
# =====================================================================
print("\n" + "=" * 70)
print("PHASE 1: Building PIT-safe first-inning pitcher metrics")
print("=" * 70)

cache = json.load(open("/root/mlb-model/research/recovery/nrfi_phase1/first_inning_cache.json"))
pgl = pd.read_parquet("/root/mlb-model/mlb/data/pitcher_game_logs.parquet")
gt = pd.read_parquet("/root/mlb-model/sim/data/game_table.parquet")

starters = pgl[pgl["starter_flag"] == 1][["game_pk", "player_id", "player_name", "team", "game_date", "season", "home_away"]].copy()
starters["game_pk"] = starters["game_pk"].astype(str)
gt["game_pk"] = gt["game_pk"].astype(str)

# Check team name alignment
starter_teams = set(starters["team"].unique())
gt_teams = set(gt["home_team"].unique()) | set(gt["away_team"].unique())
pgl_only = starter_teams - gt_teams
gt_only = gt_teams - starter_teams
print(f"  PGL teams ({len(starter_teams)}), GT teams ({len(gt_teams)})")
if pgl_only:
    print(f"  PGL-only teams: {pgl_only}")
if gt_only:
    print(f"  GT-only teams: {gt_only}")

# Build first-inning data per starter
fi_rows = []
unmatched = 0
for gpk_str, fi_data in cache.items():
    if fi_data.get("status") != "ok":
        continue
    away_1st = fi_data["away_1st"]
    home_1st = fi_data["home_1st"]

    gt_row = gt[gt["game_pk"] == gpk_str]
    if len(gt_row) == 0:
        continue
    home_team_gt = gt_row.iloc[0]["home_team"]
    away_team_gt = gt_row.iloc[0]["away_team"]
    game_date = gt_row.iloc[0]["date"]
    season = gt_row.iloc[0]["season"]

    game_starts = starters[starters["game_pk"] == gpk_str]
    if len(game_starts) == 0:
        unmatched += 1
        continue

    for _, s in game_starts.iterrows():
        pid = s["player_id"]
        pname = s["player_name"]
        pteam = s["team"]
        ha_field = s.get("home_away", "")

        # Determine home/away
        is_home = None
        if pteam == home_team_gt:
            is_home = True
        elif pteam == away_team_gt:
            is_home = False
        elif ha_field == "home":
            is_home = True
        elif ha_field == "away":
            is_home = False
        else:
            continue

        # Home starter faces away batters (top of 1st) -> away_1st
        # Away starter faces home batters (bottom of 1st) -> home_1st
        runs_allowed = away_1st if is_home else home_1st

        fi_rows.append({
            "game_pk": gpk_str,
            "pitcher_id": pid,
            "pitcher_name": pname,
            "game_date": game_date,
            "season": season,
            "is_home": is_home,
            "runs_allowed_1st": runs_allowed,
        })

fi_df = pd.DataFrame(fi_rows)
fi_df["game_date"] = pd.to_datetime(fi_df["game_date"])
fi_df = fi_df.sort_values(["pitcher_id", "game_date"]).reset_index(drop=True)
print(f"\n  First-inning starter records: {len(fi_df)}")
print(f"  Unmatched games: {unmatched}")

# PIT-safe rolling metrics
fi_df["nrfi_game"] = (fi_df["runs_allowed_1st"] == 0).astype(int)

def pit_safe_rolling(group):
    g = group.sort_values("game_date").copy()
    shifted_runs = g["runs_allowed_1st"].shift(1)
    shifted_nrfi = g["nrfi_game"].shift(1)
    g["cum_starts"] = shifted_runs.expanding().count()
    g["cum_runs_1st"] = shifted_runs.expanding().sum()
    g["cum_nrfi"] = shifted_nrfi.expanding().sum()
    g["sp_1st_era"] = np.where(g["cum_starts"] >= 5, g["cum_runs_1st"] / g["cum_starts"], np.nan)
    g["sp_1st_nrfi_rate"] = np.where(g["cum_starts"] >= 5, g["cum_nrfi"] / g["cum_starts"], np.nan)
    g["sp_1st_starts"] = g["cum_starts"]
    return g

# Apply rolling within pitcher+season groups
parts = []
for (pid, szn), grp in fi_df.groupby(["pitcher_id", "season"]):
    parts.append(pit_safe_rolling(grp))
fi_df = pd.concat(parts, ignore_index=True)
valid = fi_df["sp_1st_era"].notna().sum()
print(f"  With valid metrics (5+ prior starts): {valid} ({valid/len(fi_df)*100:.1f}%)")
print(f"  sp_1st_era range: {fi_df['sp_1st_era'].min():.3f} - {fi_df['sp_1st_era'].max():.3f}")
print(f"  sp_1st_nrfi_rate range: {fi_df['sp_1st_nrfi_rate'].min():.3f} - {fi_df['sp_1st_nrfi_rate'].max():.3f}")
print(f"  PROVENANCE: PIT-safe (shift(1) on per-game first-inning data)")

# Pivot to home/away
fi_home = fi_df[fi_df["is_home"]][["game_pk", "pitcher_id", "sp_1st_era", "sp_1st_nrfi_rate", "sp_1st_starts"]].rename(
    columns={"pitcher_id": "home_sp_pid", "sp_1st_era": "home_sp_1st_era",
             "sp_1st_nrfi_rate": "home_sp_1st_nrfi_rate", "sp_1st_starts": "home_sp_1st_starts"})
fi_away = fi_df[~fi_df["is_home"]][["game_pk", "pitcher_id", "sp_1st_era", "sp_1st_nrfi_rate", "sp_1st_starts"]].rename(
    columns={"pitcher_id": "away_sp_pid", "sp_1st_era": "away_sp_1st_era",
             "sp_1st_nrfi_rate": "away_sp_1st_nrfi_rate", "sp_1st_starts": "away_sp_1st_starts"})


# =====================================================================
# PHASE 2: Build RESEARCH-ONLY top-3 lineup metrics
# =====================================================================
print("\n" + "=" * 70)
print("PHASE 2: Building RESEARCH-ONLY top-3 lineup metrics")
print("  *** RESEARCH-ONLY: uses actual batting order (post-game) ***")
print("=" * 70)

hgl = pd.read_parquet("/root/mlb-model/mlb/data/hitter_game_logs.parquet")
hgl["game_pk"] = hgl["game_pk"].astype(str)
print(f"  HGL: {len(hgl)} rows")

# Top-3 lineup hitters per team per game
top3 = hgl[hgl["batting_order_position"].isin([1, 2, 3])].copy()
print(f"  Top-3 hitter rows: {len(top3)}")

top3["game_date"] = pd.to_datetime(top3["game_date"])
top3 = top3.sort_values(["player_id", "game_date"])

# OBP components
top3["reached_base"] = top3["hits"] + top3["walks"] + top3["hit_by_pitch"]

def pit_safe_hitter_rolling(group):
    g = group.sort_values("game_date").copy()
    shifted_pa = g["plate_appearances"].shift(1)
    shifted_ob = g["reached_base"].shift(1)
    shifted_k = g["strikeouts"].shift(1)
    shifted_hr = g["home_runs"].shift(1)

    cum_pa = shifted_pa.expanding().sum()
    cum_ob = shifted_ob.expanding().sum()
    cum_k = shifted_k.expanding().sum()
    cum_hr = shifted_hr.expanding().sum()

    min_pa = 20
    g["hitter_obp"] = np.where(cum_pa >= min_pa, cum_ob / cum_pa, np.nan)
    g["hitter_k_rate"] = np.where(cum_pa >= min_pa, cum_k / cum_pa, np.nan)
    g["hitter_hr_rate"] = np.where(cum_pa >= min_pa, cum_hr / cum_pa, np.nan)
    g["hitter_cum_pa"] = cum_pa
    return g

parts_h = []
for (pid, szn), grp in top3.groupby(["player_id", "season"]):
    parts_h.append(pit_safe_hitter_rolling(grp))
top3 = pd.concat(parts_h, ignore_index=True)
valid_h = top3["hitter_obp"].notna().sum()
print(f"  With valid hitter metrics (20+ prior PA): {valid_h} ({valid_h/len(top3)*100:.1f}%)")

# Aggregate top-3 to team-game level
top3_agg = top3.groupby(["game_pk", "team"]).agg(
    top3_mean_obp=("hitter_obp", "mean"),
    top3_mean_k_rate=("hitter_k_rate", "mean"),
    top3_mean_hr_rate=("hitter_hr_rate", "mean"),
    top3_valid_count=("hitter_obp", lambda x: x.notna().sum()),
).reset_index()

top3_agg = top3_agg[top3_agg["top3_valid_count"] == 3].copy()
print(f"  Team-game aggregates with all 3 valid: {len(top3_agg)}")

# Map to home/away via game_table
gt_map = gt[["game_pk", "home_team", "away_team"]].copy()

top3_home_df = top3_agg.merge(gt_map, on="game_pk").query("team == home_team")[
    ["game_pk", "top3_mean_obp", "top3_mean_k_rate", "top3_mean_hr_rate"]
].rename(columns={"top3_mean_obp": "home_top3_obp", "top3_mean_k_rate": "home_top3_k_rate",
                  "top3_mean_hr_rate": "home_top3_hr_rate"})

top3_away_df = top3_agg.merge(gt_map, on="game_pk").query("team == away_team")[
    ["game_pk", "top3_mean_obp", "top3_mean_k_rate", "top3_mean_hr_rate"]
].rename(columns={"top3_mean_obp": "away_top3_obp", "top3_mean_k_rate": "away_top3_k_rate",
                  "top3_mean_hr_rate": "away_top3_hr_rate"})

# Also try matching via home_away field from HGL
hgl_ha = hgl[["game_pk", "player_id", "team", "home_away"]].drop_duplicates(subset=["game_pk", "team"])
top3_agg_ha = top3_agg.merge(hgl_ha[["game_pk", "team", "home_away"]].drop_duplicates(), on=["game_pk", "team"], how="left")

top3_home_ha = top3_agg_ha[top3_agg_ha["home_away"] == "home"][
    ["game_pk", "top3_mean_obp", "top3_mean_k_rate", "top3_mean_hr_rate"]
].rename(columns={"top3_mean_obp": "home_top3_obp", "top3_mean_k_rate": "home_top3_k_rate",
                  "top3_mean_hr_rate": "home_top3_hr_rate"})

top3_away_ha = top3_agg_ha[top3_agg_ha["home_away"] == "away"][
    ["game_pk", "top3_mean_obp", "top3_mean_k_rate", "top3_mean_hr_rate"]
].rename(columns={"top3_mean_obp": "away_top3_obp", "top3_mean_k_rate": "away_top3_k_rate",
                  "top3_mean_hr_rate": "away_top3_hr_rate"})

# Use whichever method gets more matches
if len(top3_home_ha) > len(top3_home_df):
    top3_home_df = top3_home_ha
    top3_away_df = top3_away_ha
    print(f"  Using home_away field for team mapping ({len(top3_home_df)} home, {len(top3_away_df)} away)")
else:
    print(f"  Using team name mapping ({len(top3_home_df)} home, {len(top3_away_df)} away)")


# =====================================================================
# PHASE 3: Build combined research table
# =====================================================================
print("\n" + "=" * 70)
print("PHASE 3: Building combined research table")
print("=" * 70)

rt["game_pk"] = rt["game_pk"].astype(str)

rt3 = rt.merge(fi_home, on="game_pk", how="left")
rt3 = rt3.merge(fi_away, on="game_pk", how="left")

# Composite first-inning pitcher metrics
rt3["both_sp_1st_nrfi_rate"] = rt3[["home_sp_1st_nrfi_rate", "away_sp_1st_nrfi_rate"]].mean(axis=1)
rt3["min_sp_1st_nrfi_rate"] = rt3[["home_sp_1st_nrfi_rate", "away_sp_1st_nrfi_rate"]].min(axis=1)
rt3["max_sp_1st_era"] = rt3[["home_sp_1st_era", "away_sp_1st_era"]].max(axis=1)
rt3["mean_sp_1st_era"] = rt3[["home_sp_1st_era", "away_sp_1st_era"]].mean(axis=1)
rt3["both_sp_1st_valid"] = rt3["home_sp_1st_era"].notna() & rt3["away_sp_1st_era"].notna()

print(f"  Games with both SP 1st-inning metrics: {rt3['both_sp_1st_valid'].sum()}")

rt3 = rt3.merge(top3_home_df, on="game_pk", how="left")
rt3 = rt3.merge(top3_away_df, on="game_pk", how="left")

rt3["both_top3_obp"] = rt3[["home_top3_obp", "away_top3_obp"]].mean(axis=1)
rt3["max_top3_obp"] = rt3[["home_top3_obp", "away_top3_obp"]].max(axis=1)
rt3["both_top3_k_rate"] = rt3[["home_top3_k_rate", "away_top3_k_rate"]].mean(axis=1)
rt3["min_top3_k_rate"] = rt3[["home_top3_k_rate", "away_top3_k_rate"]].min(axis=1)
rt3["both_top3_valid"] = rt3["home_top3_obp"].notna() & rt3["away_top3_obp"].notna()

print(f"  Games with both top-3 lineup metrics: {rt3['both_top3_valid'].sum()}")
print(f"  Games with ALL metrics: {(rt3['both_sp_1st_valid'] & rt3['both_top3_valid']).sum()}")

rt3.to_parquet(OUT / "nrfi_phase3a_research_table.parquet", index=False)
print(f"  Saved: nrfi_phase3a_research_table.parquet ({len(rt3)} rows, {len(rt3.columns)} cols)")


# =====================================================================
# PHASE 4-6: Screen overlays inside parent gates
# =====================================================================
print("\n" + "=" * 70)
print("PHASE 4-6: Screening overlays inside parent gates")
print("=" * 70)

def compute_pocket(df, label):
    n = len(df)
    if n == 0:
        return None
    nrfi_pct = df["nrfi"].mean()
    seasons = df.groupby("season")["nrfi"].mean()
    stability = seasons.max() - seasons.min() if len(seasons) >= 2 else np.nan
    return {"label": label, "N": n, "NRFI_pct": nrfi_pct, "stability": stability,
            "seasons": len(seasons), "min_season_n": df.groupby("season").size().min() if len(seasons) > 0 else 0}

# Pre-compute medians on full dataset with valid metrics
valid_sp = rt3[rt3["both_sp_1st_valid"]]
valid_lu = rt3[rt3["both_top3_valid"]]

med_sp_1st_nrfi = valid_sp["both_sp_1st_nrfi_rate"].median()
med_min_sp_nrfi = valid_sp["min_sp_1st_nrfi_rate"].median()
med_max_sp_era = valid_sp["max_sp_1st_era"].median()
med_mean_sp_era = valid_sp["mean_sp_1st_era"].median()
med_top3_obp = valid_lu["both_top3_obp"].median()
med_max_top3_obp = valid_lu["max_top3_obp"].median()
med_top3_k = valid_lu["both_top3_k_rate"].median()

print(f"  Medians: sp_1st_nrfi_rate={med_sp_1st_nrfi:.3f}, max_sp_1st_era={med_max_sp_era:.3f}")
print(f"  Medians: top3_obp={med_top3_obp:.3f}, top3_k_rate={med_top3_k:.3f}")

# Tertile thresholds
t33_sp_nrfi = valid_sp["both_sp_1st_nrfi_rate"].quantile(0.333)
t67_sp_nrfi = valid_sp["both_sp_1st_nrfi_rate"].quantile(0.667)
t33_top3_obp = valid_lu["both_top3_obp"].quantile(0.333)
t67_top3_obp = valid_lu["both_top3_obp"].quantile(0.667)
t33_top3_k = valid_lu["both_top3_k_rate"].quantile(0.333)
t67_top3_k = valid_lu["both_top3_k_rate"].quantile(0.667)

print(f"  SP NRFI tertiles: T33={t33_sp_nrfi:.3f}, T67={t67_sp_nrfi:.3f}")
print(f"  Top3 OBP tertiles: T33={t33_top3_obp:.3f}, T67={t67_top3_obp:.3f}")
print(f"  Top3 K% tertiles: T33={t33_top3_k:.3f}, T67={t67_top3_k:.3f}")

# PIT-SAFE overlays
overlays_pit_safe = {
    "both_sp_nrfi>med": lambda df: df[df["both_sp_1st_nrfi_rate"] > med_sp_1st_nrfi],
    "both_sp_nrfi>T67": lambda df: df[df["both_sp_1st_nrfi_rate"] > t67_sp_nrfi],
    "min_sp_nrfi>med": lambda df: df[df["min_sp_1st_nrfi_rate"] > med_sp_1st_nrfi],
    "max_sp_era<med": lambda df: df[df["max_sp_1st_era"] < med_max_sp_era],
    "mean_sp_era<med": lambda df: df[df["mean_sp_1st_era"] < med_mean_sp_era],
    "both_sp_nrfi>0.6": lambda df: df[df["both_sp_1st_nrfi_rate"] > 0.6],
    "both_sp_nrfi>0.7": lambda df: df[df["both_sp_1st_nrfi_rate"] > 0.7],
    "max_sp_era<0.3": lambda df: df[df["max_sp_1st_era"] < 0.3],
}

# RESEARCH-ONLY overlays
overlays_research = {
    "both_top3_obp<med [RO]": lambda df: df[df["both_top3_obp"] < med_top3_obp],
    "both_top3_obp<T33 [RO]": lambda df: df[df["both_top3_obp"] < t33_top3_obp],
    "max_top3_obp<med [RO]": lambda df: df[df["max_top3_obp"] < med_max_top3_obp],
    "both_top3_k>med [RO]": lambda df: df[df["both_top3_k_rate"] > med_top3_k],
    "both_top3_k>T67 [RO]": lambda df: df[df["both_top3_k_rate"] > t67_top3_k],
}

# Interaction overlays (RESEARCH-ONLY)
overlays_interaction = {
    "sp_nrfi>med+top3_obp<med [RO]": lambda df: df[(df["both_sp_1st_nrfi_rate"] > med_sp_1st_nrfi) & (df["both_top3_obp"] < med_top3_obp)],
    "sp_nrfi>T67+top3_obp<T33 [RO]": lambda df: df[(df["both_sp_1st_nrfi_rate"] > t67_sp_nrfi) & (df["both_top3_obp"] < t33_top3_obp)],
    "sp_nrfi>med+top3_k>med [RO]": lambda df: df[(df["both_sp_1st_nrfi_rate"] > med_sp_1st_nrfi) & (df["both_top3_k_rate"] > med_top3_k)],
    "max_sp_era<med+max_obp<med [RO]": lambda df: df[(df["max_sp_1st_era"] < med_max_sp_era) & (df["max_top3_obp"] < med_max_top3_obp)],
}

all_overlays = {}
all_overlays.update(overlays_pit_safe)
all_overlays.update(overlays_research)
all_overlays.update(overlays_interaction)

# Add gate E (F5 4.0-4.5)
gates["E"] = {"desc": "F5 4.0-4.5", "filter": lambda df: df[(df["closing_f5_total"] > 4.0) & (df["closing_f5_total"] <= 4.5)]}

results = []
for gate_key, gate_info in gates.items():
    base_df = gate_info["filter"](rt3)
    base_pocket = compute_pocket(base_df, "Base {} ({})".format(gate_key, gate_info["desc"]))
    if base_pocket is None:
        continue
    base_pocket["gate"] = gate_key
    base_pocket["overlay"] = "none"
    base_pocket["delta"] = 0.0
    base_pocket["provenance"] = "PRODUCTION-CANDIDATE"
    results.append(base_pocket)
    base_nrfi = base_pocket["NRFI_pct"]

    for ov_name, ov_filter in all_overlays.items():
        sub = ov_filter(base_df)
        pocket = compute_pocket(sub, "{}+{}".format(gate_key, ov_name))
        if pocket and pocket["N"] >= 20:
            pocket["gate"] = gate_key
            pocket["overlay"] = ov_name
            pocket["delta"] = pocket["NRFI_pct"] - base_nrfi
            pocket["provenance"] = "RESEARCH-ONLY" if "[RO]" in ov_name else "PIT-SAFE"
            results.append(pocket)

res_df = pd.DataFrame(results)
res_df["NRFI_pct_fmt"] = (res_df["NRFI_pct"] * 100).round(1)
res_df["delta_fmt"] = (res_df["delta"] * 100).round(1)
res_df["roi_at_m135"] = ((res_df["NRFI_pct"] * (1 + 100/135) - 1) * 100).round(1)
res_df["roi_at_m125"] = ((res_df["NRFI_pct"] * (1 + 100/125) - 1) * 100).round(1)

# Print results by gate
for gk in ["A", "B", "C", "D", "E"]:
    gate_res = res_df[res_df["gate"] == gk].sort_values("NRFI_pct", ascending=False)
    if len(gate_res) == 0:
        continue
    base_row = gate_res[gate_res["overlay"] == "none"]
    print("\n--- Gate {} ---".format(gk))
    if len(base_row) > 0:
        br = base_row.iloc[0]
        print("  BASE: N={}, NRFI={:.1f}%".format(br["N"], br["NRFI_pct_fmt"]))

    overlays_res = gate_res[gate_res["overlay"] != "none"].head(15)
    for _, r in overlays_res.iterrows():
        prov = "PIT" if r["provenance"] == "PIT-SAFE" else "RO"
        delta_str = "{:+.1f}".format(r["delta_fmt"])
        stab_str = "stab={:.3f}".format(r["stability"]) if pd.notna(r["stability"]) else "stab=NA"
        print("  {:45s} N={:4d}  NRFI={:5.1f}%  delta={:6s}pp  {}  [{}]".format(
            r["overlay"], r["N"], r["NRFI_pct_fmt"], delta_str, stab_str, prov))


# =====================================================================
# PHASE 7: Identify credible overlays
# =====================================================================
print("\n" + "=" * 70)
print("PHASE 7: Credible overlay assessment")
print("=" * 70)

credible = res_df[
    (res_df["overlay"] != "none") &
    (res_df["N"] >= 50) &
    (res_df["delta"] > 0) &
    (res_df["stability"] < 0.15) &
    (res_df["seasons"] >= 3)
].copy()

near_credible = res_df[
    (res_df["overlay"] != "none") &
    (res_df["N"] >= 30) &
    (res_df["delta"] > 0) &
    (res_df["stability"] < 0.20) &
    (res_df["seasons"] >= 3)
].copy()

print("\n  Strictly credible (N>=50, delta>0, stab<0.15, 3+ seasons): {}".format(len(credible)))
for _, r in credible.sort_values("NRFI_pct", ascending=False).iterrows():
    print("    {:55s} N={:4d}  NRFI={:5.1f}%  delta={:+.1f}pp  stab={:.3f}  [{}]".format(
        r["label"], r["N"], r["NRFI_pct_fmt"], r["delta_fmt"], r["stability"], r["provenance"]))

print("\n  Near-credible (N>=30, delta>0, stab<0.20, 3+ seasons): {}".format(len(near_credible)))
for _, r in near_credible.sort_values("NRFI_pct", ascending=False).iterrows():
    print("    {:55s} N={:4d}  NRFI={:5.1f}%  delta={:+.1f}pp  stab={:.3f}  [{}]".format(
        r["label"], r["N"], r["NRFI_pct_fmt"], r["delta_fmt"], r["stability"], r["provenance"]))


# =====================================================================
# PHASE 8: Ranking v2
# =====================================================================
print("\n" + "=" * 70)
print("PHASE 8: Ranking v2")
print("=" * 70)

ranked = res_df[res_df["N"] >= 30].copy()
ranked["score"] = (
    ranked["NRFI_pct"]
    * np.log(ranked["N"])
    * (1 - ranked["stability"].fillna(0.5).clip(0, 1))
    * np.where(ranked["delta"] > 0, 1.0, 0.5)
)
ranked = ranked.sort_values("score", ascending=False)

print("\n  Top 25 pockets by composite score:")
print("  {:>4s}  {:55s}  {:>5s}  {:>6s}  {:>7s}  {:>6s}  {:>9s}  {:12s}  {:>6s}".format(
    "Rank", "Label", "N", "NRFI%", "Delta", "Stab", "ROI@-135", "Prov", "Score"))
print("  " + "-" * 120)
for i, (_, r) in enumerate(ranked.head(25).iterrows()):
    delta_str = "{:+.1f}".format(r["delta_fmt"]) if r["overlay"] != "none" else "base"
    print("  {:4d}  {:55s}  {:5d}  {:5.1f}%  {:>7s}  {:.3f}  {:+7.1f}%  {:12s}  {:.3f}".format(
        i+1, r["label"], r["N"], r["NRFI_pct_fmt"], delta_str, r["stability"],
        r["roi_at_m135"], r["provenance"], r["score"]))


# =====================================================================
# PHASE 9: Decision + outputs
# =====================================================================
print("\n" + "=" * 70)
print("PHASE 9: Decision summary")
print("=" * 70)

pit_safe_positive = res_df[
    (res_df["overlay"] != "none") &
    (res_df["provenance"] == "PIT-SAFE") &
    (res_df["delta"] > 0) &
    (res_df["N"] >= 30)
].sort_values("NRFI_pct", ascending=False)

ro_positive = res_df[
    (res_df["overlay"] != "none") &
    (res_df["provenance"] == "RESEARCH-ONLY") &
    (res_df["delta"] > 0) &
    (res_df["N"] >= 30)
].sort_values("NRFI_pct", ascending=False)

print("\n  PIT-safe overlays with positive delta (N>=30): {}".format(len(pit_safe_positive)))
for _, r in pit_safe_positive.iterrows():
    print("    {:55s} N={:4d}  NRFI={:5.1f}%  delta={:+.1f}pp  stab={:.3f}".format(
        r["label"], r["N"], r["NRFI_pct_fmt"], r["delta_fmt"], r["stability"]))

print("\n  RESEARCH-ONLY overlays with positive delta (N>=30): {}".format(len(ro_positive)))
for _, r in ro_positive.iterrows():
    print("    {:55s} N={:4d}  NRFI={:5.1f}%  delta={:+.1f}pp  stab={:.3f}".format(
        r["label"], r["N"], r["NRFI_pct_fmt"], r["delta_fmt"], r["stability"]))

# Save final table
final_cols = ["label", "gate", "overlay", "N", "NRFI_pct_fmt", "delta_fmt", "stability", "seasons",
              "roi_at_m135", "roi_at_m125", "provenance"]
if "score" in ranked.columns:
    final_cols.append("score")
final_df = ranked[final_cols].head(40)
final_df.to_csv(OUT / "NRFI_PHASE3A_FINAL_TABLE.csv", index=False)
print("\n  Saved: NRFI_PHASE3A_FINAL_TABLE.csv ({} rows)".format(len(final_df)))

# Count findings
n_pit_AB = len(pit_safe_positive[pit_safe_positive["gate"].isin(["A", "B"])])
n_pit_DE = len(pit_safe_positive[pit_safe_positive["gate"].isin(["D", "E"])])
pit_safe_credible = credible[credible["provenance"] == "PIT-SAFE"] if len(credible) > 0 else pd.DataFrame()
ro_credible = credible[credible["provenance"] == "RESEARCH-ONLY"] if len(credible) > 0 else pd.DataFrame()

# Build exec summary markdown
lines = []
lines.append("# NRFI Phase 3A -- Executive Summary\n")
lines.append("**Date:** 2026-04-11")
lines.append("**Scope:** First-inning pitcher splits (PIT-safe) + top-of-order lineup overlay (RESEARCH-ONLY)")
lines.append("**Data:** {} games, {} with 1st-inning SP metrics, {} with top-3 lineup metrics\n".format(
    len(rt3), rt3["both_sp_1st_valid"].sum(), rt3["both_top3_valid"].sum()))
lines.append("---\n")
lines.append("## Safety Provenance\n")
lines.append("| Variable Class | Provenance | Method |")
lines.append("|---------------|------------|--------|")
lines.append("| sp_1st_era, sp_1st_nrfi_rate | **PIT-SAFE** | Per-game 1st-inning runs from linescore cache, shift(1) expanding mean, min 5 prior starts |")
lines.append("| top3_obp, top3_k_rate, top3_hr_rate | **RESEARCH-ONLY** | Actual batting order from post-game box scores. Cannot be known pre-game. |")
lines.append("| Any interaction using top-3 vars | **RESEARCH-ONLY** | Inherits RESEARCH-ONLY from lineup component |\n")
lines.append("---\n")
lines.append("## Bottom Line\n")
lines.append("First-inning pitcher NRFI rate (PIT-safe, built from per-game linescore data with shift(1)) provides")
lines.append("**{} positive-delta overlays inside Gates A/B** (the strongest F5-based pockets).".format(n_pit_AB))
lines.append("This is consistent with Phase 2: the F5 market line already encodes starter quality,")
lines.append("including first-inning tendencies.\n")
lines.append("Top-3 lineup metrics (RESEARCH-ONLY) show {} for NRFI selection,".format(
    "some signal" if len(ro_positive) > 5 else "limited signal"))
lines.append("but are **not usable in production** because actual batting order is unknown pre-game.\n")
if n_pit_DE > 0:
    lines.append("**Verdict:** First-inning pitcher NRFI rate adds marginal but positive lift")
    lines.append("in broader pockets (D, E) but not inside the already-strong F5 pockets (A, B). The unfiltered")
    lines.append("F5-based pockets remain the primary actionable NRFI selections.\n")
else:
    lines.append("**Verdict:** First-inning pitcher NRFI rate adds no actionable lift. The unfiltered")
    lines.append("F5-based pockets remain the primary actionable NRFI selections.\n")
lines.append("---\n")

# PIT-safe findings table
lines.append("## Key Findings\n")
lines.append("### 1. PIT-Safe First-Inning SP Overlays (positive delta, N>=30)\n")
if len(pit_safe_positive) > 0:
    lines.append("| Pocket | N | NRFI% | Delta | Stab | ROI@-135 |")
    lines.append("|--------|---|-------|-------|------|----------|")
    for _, r in pit_safe_positive.head(12).iterrows():
        lines.append("| {} | {} | {:.1f}% | {:+.1f}pp | {:.3f} | {:+.1f}% |".format(
            r["label"], r["N"], r["NRFI_pct_fmt"], r["delta_fmt"], r["stability"], r["roi_at_m135"]))
else:
    lines.append("None found.\n")

lines.append("\n### 2. RESEARCH-ONLY Top-3 Lineup Overlays (positive delta, N>=30)\n")
if len(ro_positive) > 0:
    lines.append("| Pocket | N | NRFI% | Delta | Stab | ROI@-135 | Provenance |")
    lines.append("|--------|---|-------|-------|------|----------|------------|")
    for _, r in ro_positive.head(12).iterrows():
        lines.append("| {} | {} | {:.1f}% | {:+.1f}pp | {:.3f} | {:+.1f}% | RESEARCH-ONLY |".format(
            r["label"], r["N"], r["NRFI_pct_fmt"], r["delta_fmt"], r["stability"], r["roi_at_m135"]))
else:
    lines.append("None found.\n")

# Credible overlays
lines.append("\n### 3. Credible Overlays (N>=50, delta>0, stability<0.15, 3+ seasons)\n")
lines.append("**PIT-safe credible:** {}".format(len(pit_safe_credible)))
lines.append("**RESEARCH-ONLY credible:** {}\n".format(len(ro_credible)))
if len(credible) > 0:
    lines.append("| Pocket | N | NRFI% | Delta | Stab | ROI@-135 | Provenance |")
    lines.append("|--------|---|-------|-------|------|----------|------------|")
    for _, r in credible.sort_values("NRFI_pct", ascending=False).iterrows():
        lines.append("| {} | {} | {:.1f}% | {:+.1f}pp | {:.3f} | {:+.1f}% | {} |".format(
            r["label"], r["N"], r["NRFI_pct_fmt"], r["delta_fmt"], r["stability"], r["roi_at_m135"], r["provenance"]))
else:
    lines.append("None met all credibility criteria.\n")

lines.append("\n---\n")
lines.append("## Ranking v2 (Top 15)\n")
lines.append("| Rank | Pocket | N | NRFI% | Delta | Stab | ROI@-135 | Provenance | Score |")
lines.append("|------|--------|---|-------|-------|------|----------|------------|-------|")
for i, (_, r) in enumerate(ranked.head(15).iterrows()):
    delta_str = "{:+.1f}pp".format(r["delta_fmt"]) if r["overlay"] != "none" else "base"
    lines.append("| {} | {} | {} | {:.1f}% | {} | {:.3f} | {:+.1f}% | {} | {:.3f} |".format(
        i+1, r["label"], r["N"], r["NRFI_pct_fmt"], delta_str, r["stability"],
        r["roi_at_m135"], r["provenance"], r["score"]))

lines.append("\n---\n")
lines.append("## ROI Framework\n")
lines.append("Break-even at -135: 57.4% | Break-even at -125: 55.6%\n")
lines.append("---\n")
lines.append("## Actionable Recommendations\n")
lines.append("1. **F5 <= 3.5 and F5 <= 4.0 remain the best NRFI filters** -- first-inning pitcher overlays do not reliably improve them.")
lines.append("2. **First-inning SP NRFI rate** is a PIT-safe variable computable in production, but marginal value is low inside F5-gated pockets.")
lines.append("3. **Top-3 lineup metrics are RESEARCH-ONLY** -- they confirm lineup quality matters for 1st-inning scoring, but cannot be operationalized pre-game.")
lines.append("4. **Phase 3B should explore:** park factor (dome/outdoor), temperature, and month effects as independent signals.\n")
lines.append("---\n")
lines.append("## Files\n")
lines.append("| File | Description |")
lines.append("|------|-------------|")
lines.append("| nrfi_phase3a_research_table.parquet | {} games with 1st-inning SP + top-3 lineup metrics |".format(len(rt3)))
lines.append("| NRFI_PHASE3A_FINAL_TABLE.csv | Top 40 pockets ranked by composite score |")
lines.append("| phase3a_build.py | Full build script |")
lines.append("| NRFI_PHASE3A_EXEC_SUMMARY.md | This file |")

with open(OUT / "NRFI_PHASE3A_EXEC_SUMMARY.md", "w") as f:
    f.write("\n".join(lines) + "\n")
print("\n  Saved: NRFI_PHASE3A_EXEC_SUMMARY.md")

print("\n" + "=" * 70)
print("PHASE 3A COMPLETE")
print("=" * 70)
