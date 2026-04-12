#!/usr/bin/env python3
"""
MLB Sides Phase 4 — Reason-for-Favoritism / Win-Path Decomposition
Discovery: 2022-2023, Validation: 2024, OOS: 2025
All thresholds frozen from discovery only.
"""

import pandas as pd
import numpy as np
import os, warnings
warnings.filterwarnings("ignore")

OUT = "/root/mlb-model/research/recovery/mlb_sides_phase4_winpath"
os.makedirs(OUT, exist_ok=True)

# Team abbreviation mapping: PGL -> GT standard
PGL_TO_GT = {
    "AZ": "ARI", "CWS": "CHW", "KC": "KCR", "SD": "SDP",
    "SF": "SFG", "TB": "TBR", "WSH": "WSN", "ATH": "OAK"
}
# Reverse for GT -> PGL (needed for BP/offense which come from GT)
GT_TO_PGL = {v: k for k, v in PGL_TO_GT.items()}

def normalize_team(t, to="gt"):
    """Normalize team abbrev. to='gt' means PGL->GT, to='pgl' means GT->PGL."""
    if to == "gt":
        return PGL_TO_GT.get(t, t)
    else:
        return GT_TO_PGL.get(t, t)

# ─── LOAD DATA ───────────────────────────────────────────────
pgl = pd.read_parquet("/root/mlb-model/mlb/data/pitcher_game_logs.parquet")
gt  = pd.read_parquet("/root/mlb-model/sim/data/game_table.parquet")
canon = pd.read_parquet("/root/mlb-model/mlb_sim/data/mlb_odds_closing_canonical.parquet")

gt = gt[gt["home_score"].notna() & gt["away_score"].notna()].copy()
gt["date"] = pd.to_datetime(gt["date"])
gt["game_pk"] = gt["game_pk"].astype(int)
pgl["game_date"] = pd.to_datetime(pgl["game_date"])
pgl["game_pk"] = pgl["game_pk"].astype(int)
# Normalize PGL teams to GT convention
pgl["team_gt"] = pgl["team"].map(lambda t: normalize_team(t, "gt"))

canon["date"] = pd.to_datetime(canon["date"])
canon = canon[canon["game_pk"].notna()].copy()
canon["game_pk"] = pd.to_numeric(canon["game_pk"], errors="coerce")
canon = canon[canon["game_pk"].notna()].copy()
canon["game_pk"] = canon["game_pk"].astype(int)

print(f"Game table: {len(gt)} games")
print(f"Pitcher logs: {len(pgl)} rows")
print(f"Canon odds: {len(canon)} rows")

# ─── CLOSING LINES ──────────────────────────────────────────
dk = canon[canon["book_key"] == "draftkings"].sort_values("pull_timestamp").drop_duplicates("game_pk", keep="last")
fd = canon[canon["book_key"] == "fanduel"].sort_values("pull_timestamp").drop_duplicates("game_pk", keep="last")
cols = ["game_pk", "ml_home_price", "ml_away_price", "ml_home_implied", "ml_away_implied", "total_line"]
odds = pd.concat([dk[cols], fd[~fd["game_pk"].isin(dk["game_pk"])][cols]], ignore_index=True)
print(f"Odds rows: {len(odds)}")

# ─── MERGE + CLOSE-GAME UNIVERSE ────────────────────────────
gm = gt.merge(odds, on="game_pk", how="inner")
gm["fav_side"] = np.where(gm["ml_home_implied"] > gm["ml_away_implied"], "home",
                 np.where(gm["ml_away_implied"] > gm["ml_home_implied"], "away", "pick"))
gm = gm[gm["fav_side"] != "pick"].copy()
gm["fav_implied"] = np.where(gm["fav_side"] == "home", gm["ml_home_implied"], gm["ml_away_implied"])
gm_close = gm[(gm["fav_implied"] >= 0.512) & (gm["fav_implied"] <= 0.556)].copy()
print(f"Close-game universe: {len(gm_close)}")
print(f"  by season: {gm_close.groupby('season').size().to_dict()}")

gm_close["fav_team"] = np.where(gm_close["fav_side"] == "home", gm_close["home_team"], gm_close["away_team"])
gm_close["dog_team"] = np.where(gm_close["fav_side"] == "home", gm_close["away_team"], gm_close["home_team"])
gm_close["fav_score"] = np.where(gm_close["fav_side"] == "home", gm_close["home_score"], gm_close["away_score"])
gm_close["dog_score"] = np.where(gm_close["fav_side"] == "home", gm_close["away_score"], gm_close["home_score"])
gm_close["fav_won"] = (gm_close["fav_score"] > gm_close["dog_score"]).astype(int)
gm_close["fav_ml_price"] = np.where(gm_close["fav_side"] == "home", gm_close["ml_home_price"], gm_close["ml_away_price"])
gm_close["dog_ml_price"] = np.where(gm_close["fav_side"] == "home", gm_close["ml_away_price"], gm_close["ml_home_price"])
gm_close["fav_is_home"] = (gm_close["fav_side"] == "home").astype(int)

# ─── SP FEATURES (PIT-safe) ─────────────────────────────────
sp = pgl[pgl["starter_flag"] == 1].copy()
sp = sp.sort_values(["player_id", "season", "game_date"])
for col in ["earned_runs", "innings_pitched", "strikeouts", "walks", "home_runs_allowed"]:
    sp[f"cum_{col}"] = sp.groupby(["player_id", "season"])[col].transform(
        lambda x: x.shift(1).expanding().sum())
sp["sp_fip"] = np.where(sp["cum_innings_pitched"] > 0,
    (13*sp["cum_home_runs_allowed"] + 3*sp["cum_walks"] - 2*sp["cum_strikeouts"]) / sp["cum_innings_pitched"] + 3.10,
    np.nan)
sp_valid = sp[sp["cum_innings_pitched"] >= 10].copy()

# Identify home/away by matching team_gt to game_table home/away team
sp_valid = sp_valid.merge(gt[["game_pk", "home_team", "away_team"]].drop_duplicates("game_pk"),
                           on="game_pk", how="left")
sp_valid["is_home_sp"] = sp_valid["team_gt"] == sp_valid["home_team"]
sp_valid["is_away_sp"] = sp_valid["team_gt"] == sp_valid["away_team"]

home_sp_feat = sp_valid[sp_valid["is_home_sp"]][["game_pk", "sp_fip"]].rename(
    columns={"sp_fip": "home_sp_fip"}).drop_duplicates("game_pk")
away_sp_feat = sp_valid[sp_valid["is_away_sp"]][["game_pk", "sp_fip"]].rename(
    columns={"sp_fip": "away_sp_fip"}).drop_duplicates("game_pk")

print(f"Home SP features: {len(home_sp_feat)}, Away SP features: {len(away_sp_feat)}")

# ─── BP FEATURES (PIT-safe) ─────────────────────────────────
bp = pgl[pgl["starter_flag"] == 0].copy()
bp_game = bp.groupby(["team_gt", "season", "game_date"]).agg(
    bp_er=("earned_runs", "sum"), bp_ip=("innings_pitched", "sum")
).reset_index().sort_values(["team_gt", "season", "game_date"])
bp_game["bp_cum_er"] = bp_game.groupby(["team_gt", "season"])["bp_er"].transform(
    lambda x: x.shift(1).expanding().sum())
bp_game["bp_cum_ip"] = bp_game.groupby(["team_gt", "season"])["bp_ip"].transform(
    lambda x: x.shift(1).expanding().sum())
bp_game["bp_era"] = np.where(bp_game["bp_cum_ip"] >= 10,
    bp_game["bp_cum_er"] / bp_game["bp_cum_ip"] * 9, np.nan)

# ─── OFFENSE FEATURES (PIT-safe) ────────────────────────────
home_g = gt[["game_pk", "date", "season", "home_team", "home_score"]].rename(
    columns={"home_team": "team", "home_score": "runs"})
away_g = gt[["game_pk", "date", "season", "away_team", "away_score"]].rename(
    columns={"away_team": "team", "away_score": "runs"})
tg = pd.concat([home_g, away_g]).sort_values(["team", "season", "date"])
tg["off_r20"] = tg.groupby(["team", "season"])["runs"].transform(
    lambda x: x.shift(1).rolling(20, min_periods=10).mean())

# ─── MERGE ALL TO CLOSE GAMES ───────────────────────────────
gm_close = gm_close.merge(home_sp_feat, on="game_pk", how="left")
gm_close = gm_close.merge(away_sp_feat, on="game_pk", how="left")

# BP merge: by team + date
bp_h = bp_game[bp_game["bp_era"].notna()][["team_gt", "game_date", "bp_era"]].rename(
    columns={"team_gt": "home_team", "game_date": "date", "bp_era": "home_bp_era"})
bp_a = bp_game[bp_game["bp_era"].notna()][["team_gt", "game_date", "bp_era"]].rename(
    columns={"team_gt": "away_team", "game_date": "date", "bp_era": "away_bp_era"})
gm_close = gm_close.merge(bp_h, on=["home_team", "date"], how="left")
gm_close = gm_close.merge(bp_a, on=["away_team", "date"], how="left")

# Offense merge: by team + date
off_h = tg[tg["off_r20"].notna()][["team", "date", "off_r20"]].rename(
    columns={"team": "home_team", "off_r20": "home_off_r20"}).drop_duplicates(["home_team", "date"])
off_a = tg[tg["off_r20"].notna()][["team", "date", "off_r20"]].rename(
    columns={"team": "away_team", "off_r20": "away_off_r20"}).drop_duplicates(["away_team", "date"])
gm_close = gm_close.merge(off_h, on=["home_team", "date"], how="left")
gm_close = gm_close.merge(off_a, on=["away_team", "date"], how="left")

# ─── COMPUTE GAPS ───────────────────────────────────────────
gm_close["fav_sp_fip"] = np.where(gm_close["fav_side"] == "home", gm_close["home_sp_fip"], gm_close["away_sp_fip"])
gm_close["dog_sp_fip"] = np.where(gm_close["fav_side"] == "home", gm_close["away_sp_fip"], gm_close["home_sp_fip"])
gm_close["sp_fip_diff"] = gm_close["fav_sp_fip"] - gm_close["dog_sp_fip"]

gm_close["fav_off"] = np.where(gm_close["fav_side"] == "home", gm_close["home_off_r20"], gm_close["away_off_r20"])
gm_close["dog_off"] = np.where(gm_close["fav_side"] == "home", gm_close["away_off_r20"], gm_close["home_off_r20"])
gm_close["off_diff"] = gm_close["fav_off"] - gm_close["dog_off"]

gm_close["fav_bp_era"] = np.where(gm_close["fav_side"] == "home", gm_close["home_bp_era"], gm_close["away_bp_era"])
gm_close["dog_bp_era"] = np.where(gm_close["fav_side"] == "home", gm_close["away_bp_era"], gm_close["home_bp_era"])
gm_close["bp_era_diff"] = gm_close["fav_bp_era"] - gm_close["dog_bp_era"]

print(f"\n=== FEATURE COVERAGE ===")
for c in ["home_sp_fip", "away_sp_fip", "sp_fip_diff", "off_diff", "bp_era_diff", "total_line"]:
    n = gm_close[c].notna().sum()
    print(f"  {c}: {n}/{len(gm_close)} ({100*n/len(gm_close):.1f}%)")

# Full-feature set
gm_full = gm_close.dropna(subset=["sp_fip_diff", "off_diff", "bp_era_diff", "total_line"]).copy()
print(f"\nFull-feature games: {len(gm_full)}")
print(f"  by season: {gm_full.groupby('season').size().to_dict()}")

# ─── DISCOVERY THRESHOLDS ───────────────────────────────────
disc = gm_full[gm_full["season"].isin([2022, 2023])].copy()
print(f"\nDiscovery: {len(disc)} games")

THRESH = {}
for name, col in [("sp", "sp_fip_diff"), ("off", "off_diff"), ("bp", "bp_era_diff")]:
    abs_vals = disc[col].abs()
    THRESH[f"{name}_material"] = abs_vals.quantile(0.67)
    THRESH[f"{name}_small"] = abs_vals.quantile(0.50)
THRESH["total_low"] = disc["total_line"].quantile(0.33)
THRESH["total_high"] = disc["total_line"].quantile(0.67)

# Fav-level terciles
SP_FIP_P33 = disc["fav_sp_fip"].quantile(0.33)
SP_FIP_P50 = disc["fav_sp_fip"].quantile(0.50)
BP_ERA_P33 = disc["fav_bp_era"].quantile(0.33)
BP_ERA_P50 = disc["fav_bp_era"].quantile(0.50)
OFF_P67 = disc["fav_off"].quantile(0.67)

print(f"\n=== FROZEN THRESHOLDS ===")
for k, v in THRESH.items():
    print(f"  {k}: {v:.3f}")
print(f"  SP_FIP p33={SP_FIP_P33:.3f} p50={SP_FIP_P50:.3f}")
print(f"  BP_ERA p33={BP_ERA_P33:.3f} p50={BP_ERA_P50:.3f}")
print(f"  OFF p67={OFF_P67:.3f}")

# ─── CLASSIFY ───────────────────────────────────────────────
def classify_reason(row):
    sp = abs(row["sp_fip_diff"])
    off = abs(row["off_diff"])
    bp = abs(row["bp_era_diff"])
    fav_sp_better = row["sp_fip_diff"] < 0
    fav_off_better = row["off_diff"] > 0
    fav_bp_better = row["bp_era_diff"] < 0
    
    sp_mat = sp >= THRESH["sp_material"]
    off_mat = off >= THRESH["off_material"]
    bp_mat = bp >= THRESH["bp_material"]
    sp_sm = sp < THRESH["sp_small"]
    off_sm = off < THRESH["off_small"]
    bp_sm = bp < THRESH["bp_small"]
    
    if fav_sp_better and sp_mat and sp >= off and sp >= bp:
        return "SP-LED"
    if fav_off_better and off_mat and sp_sm:
        return "OFFENSE-LED"
    if fav_bp_better and bp_mat and sp_sm and off_sm:
        return "BP-LED"
    if row["fav_is_home"] == 1 and sp_sm and off_sm and bp_sm:
        return "HOME-LED"
    return "MIXED"

def classify_winpath(row):
    sp = row["fav_sp_fip"]
    bp = row["fav_bp_era"]
    off = row["fav_off"]
    total = row["total_line"]
    
    if sp <= SP_FIP_P33 and bp <= BP_ERA_P50:
        return "STARTER-HOLD"
    if sp >= SP_FIP_P50 and (off >= OFF_P67 or bp <= BP_ERA_P33):
        return "LATE-CONVERT"
    if total <= THRESH["total_low"] and abs(row["sp_fip_diff"]) < THRESH["sp_material"] and abs(row["off_diff"]) < THRESH["off_material"]:
        return "GRIND-OUT"
    if total >= THRESH["total_high"] and abs(row["off_diff"]) >= THRESH["off_small"]:
        return "VOLATILE"
    return "UNCLASSIFIED"

gm_full["reason"] = gm_full.apply(classify_reason, axis=1)
gm_full["winpath"] = gm_full.apply(classify_winpath, axis=1)

print(f"\n=== REASON DISTRIBUTION ===")
print(gm_full.groupby(["season", "reason"]).size().unstack(fill_value=0))
print(f"\n=== WINPATH DISTRIBUTION ===")
print(gm_full.groupby(["season", "winpath"]).size().unstack(fill_value=0))

# ─── ECONOMICS ──────────────────────────────────────────────
def calc_roi(prices, outcomes):
    valid = pd.notna(prices) & pd.notna(outcomes)
    p = prices[valid].values.astype(float)
    o = outcomes[valid].values.astype(float)
    n = len(p)
    if n == 0:
        return np.nan, 0
    profit = 0
    for price, won in zip(p, o):
        if won:
            profit += (price / 100) if price > 0 else (100 / abs(price))
        else:
            profit -= 1
    return profit / n * 100, n

def analyze(df, label):
    n = len(df)
    if n == 0:
        return None
    wr = df["fav_won"].mean()
    imp = df["fav_implied"].mean()
    resid = wr - imp
    roi_f, _ = calc_roi(df["fav_ml_price"], df["fav_won"])
    roi_d, _ = calc_roi(df["dog_ml_price"], 1 - df["fav_won"])
    return dict(label=label, N=n, WR=round(wr,4), ImpWR=round(imp,4),
                Resid=round(resid,4), ROI_fav=round(roi_f,2), ROI_dog=round(roi_d,2))

# ─── MAIN ANALYSIS ──────────────────────────────────────────
phases = [("Discovery", [2022, 2023]), ("..2022", [2022]), ("..2023", [2023]),
          ("Validation", [2024]), ("OOS", [2025])]
all_results = []

def run_analysis(dim_name, dim_col, categories, title):
    print(f"\n{'='*100}")
    print(title)
    print("="*100)
    
    for pname, seas in phases:
        pdf = gm_full[gm_full["season"].isin(seas)]
        if pname in ["Discovery", "Validation", "OOS"]:
            print(f"\n--- {pname} (N={len(pdf)}) ---")
        
        for cat in categories:
            cell = pdf[pdf[dim_col] == cat]
            r = analyze(cell, cat)
            if r:
                r["phase"] = pname
                r["dim"] = dim_name
                all_results.append(r)
                if pname in ["Discovery", "Validation", "OOS"]:
                    flag = " ***" if r["N"] >= 150 and abs(r["Resid"]) >= 0.02 else ""
                    print(f"  {cat:18s}  N={r['N']:4d}  WR={r['WR']:.4f}  ImpWR={r['ImpWR']:.4f}  Resid={r['Resid']:+.4f}  ROI_fav={r['ROI_fav']:+.2f}%  ROI_dog={r['ROI_dog']:+.2f}%{flag}")
        
        # Baseline
        r = analyze(pdf, "BASELINE")
        if r:
            r["phase"] = pname
            r["dim"] = "baseline"
            all_results.append(r)
            if pname in ["Discovery", "Validation", "OOS"]:
                print(f"  {'BASELINE':18s}  N={r['N']:4d}  WR={r['WR']:.4f}  ImpWR={r['ImpWR']:.4f}  Resid={r['Resid']:+.4f}  ROI_fav={r['ROI_fav']:+.2f}%  ROI_dog={r['ROI_dog']:+.2f}%")

run_analysis("reason", "reason", ["SP-LED", "OFFENSE-LED", "BP-LED", "HOME-LED", "MIXED"],
             "PART A: REASON FOR FAVORITISM — FAV SIDE")

run_analysis("winpath", "winpath", ["STARTER-HOLD", "LATE-CONVERT", "GRIND-OUT", "VOLATILE", "UNCLASSIFIED"],
             "PART B: WIN-PATH PROFILE — FAV SIDE")

# ─── CROSS-TAB ──────────────────────────────────────────────
print(f"\n{'='*100}")
print("PART C: REASON x WINPATH CROSS-TAB")
print("="*100)

disc2 = gm_full[gm_full["season"].isin([2022, 2023])]
ct = pd.crosstab(disc2["reason"], disc2["winpath"], margins=True)
print(ct)

print("\n--- Cross-cells (disc N>=50) ---")
for reason in ["SP-LED", "OFFENSE-LED", "BP-LED", "HOME-LED", "MIXED"]:
    for wp in ["STARTER-HOLD", "LATE-CONVERT", "GRIND-OUT", "VOLATILE", "UNCLASSIFIED"]:
        dc = disc2[(disc2["reason"] == reason) & (disc2["winpath"] == wp)]
        if len(dc) >= 50:
            lbl = f"{reason}+{wp}"
            for pname, seas in phases:
                pdf = gm_full[gm_full["season"].isin(seas)]
                cell = pdf[(pdf["reason"] == reason) & (pdf["winpath"] == wp)]
                r = analyze(cell, lbl)
                if r:
                    r["phase"] = pname
                    r["dim"] = "cross"
                    all_results.append(r)
            
            for pname in ["Discovery", "Validation", "OOS"]:
                match = [x for x in all_results if x["label"] == lbl and x["phase"] == pname and x["dim"] == "cross"]
                if match:
                    m = match[0]
                    print(f"  {lbl:35s}  {pname:10s}  N={m['N']:4d}  Resid={m['Resid']:+.4f}  ROI_fav={m['ROI_fav']:+.2f}%  ROI_dog={m['ROI_dog']:+.2f}%")

# ─── REASON x TOTAL BUCKET ──────────────────────────────────
print(f"\n{'='*100}")
print("PART D: REASON x TOTAL BUCKET")
print("="*100)

gm_full["total_bucket"] = pd.cut(gm_full["total_line"],
    bins=[0, THRESH["total_low"], THRESH["total_high"], 20],
    labels=["LOW", "MID", "HIGH"])

for pname, seas in [("Discovery", [2022, 2023]), ("Validation", [2024]), ("OOS", [2025])]:
    pdf = gm_full[gm_full["season"].isin(seas)]
    print(f"\n--- {pname} ---")
    for reason in ["SP-LED", "OFFENSE-LED", "HOME-LED", "MIXED"]:
        for tb in ["LOW", "MID", "HIGH"]:
            cell = pdf[(pdf["reason"] == reason) & (pdf["total_bucket"] == tb)]
            if len(cell) >= 30:
                r = analyze(cell, f"{reason}+{tb}")
                if r:
                    r["phase"] = pname
                    r["dim"] = "reason_total"
                    all_results.append(r)
                    print(f"  {reason:15s} x {tb:4s}  N={r['N']:4d}  Resid={r['Resid']:+.4f}  ROI_fav={r['ROI_fav']:+.2f}%  ROI_dog={r['ROI_dog']:+.2f}%")

# ─── SURVIVOR IDENTIFICATION ────────────────────────────────
print(f"\n{'='*100}")
print("PART E: SURVIVOR IDENTIFICATION")
print("="*100)

survivors = []

def get_result(label, phase, dim=None):
    matches = [x for x in all_results if x["label"] == label and x["phase"] == phase]
    if dim:
        matches = [x for x in matches if x["dim"] == dim]
    return matches[0] if matches else None

# Discovery cells: N>=150 and |Resid|>=0.02
disc_hits = [x for x in all_results if x["phase"] == "Discovery" and x["N"] >= 150 and abs(x["Resid"]) >= 0.02 and x["dim"] != "baseline"]
print(f"\nCandidates (disc N>=150, |Resid|>=0.02): {len(disc_hits)}")

for dr in disc_hits:
    vr = get_result(dr["label"], "Validation", dr.get("dim"))
    orr = get_result(dr["label"], "OOS", dr.get("dim"))
    bet_side = "fav" if dr["Resid"] > 0 else "dog"
    
    val_ok = vr and ((bet_side == "fav" and vr["Resid"] > 0) or (bet_side == "dog" and vr["Resid"] < 0))
    oos_ok = orr and ((bet_side == "fav" and orr["Resid"] > 0) or (bet_side == "dog" and orr["Resid"] < 0))
    
    status = "KEEP" if val_ok and oos_ok else ("MONITOR" if val_ok else "KILL")
    
    print(f"\n  {dr['label']:35s} [{dr['dim']}]  bet={bet_side}")
    print(f"    Disc:  N={dr['N']:4d}  Resid={dr['Resid']:+.4f}  ROI_fav={dr['ROI_fav']:+.2f}%  ROI_dog={dr['ROI_dog']:+.2f}%")
    if vr:
        print(f"    Val:   N={vr['N']:4d}  Resid={vr['Resid']:+.4f}  ROI_fav={vr['ROI_fav']:+.2f}%  ROI_dog={vr['ROI_dog']:+.2f}%")
    if orr:
        print(f"    OOS:   N={orr['N']:4d}  Resid={orr['Resid']:+.4f}  ROI_fav={orr['ROI_fav']:+.2f}%  ROI_dog={orr['ROI_dog']:+.2f}%")
    print(f"    --> {status}")
    
    survivors.append(dict(
        label=dr["label"], dim=dr["dim"], bet_side=bet_side, status=status,
        disc_n=dr["N"], disc_resid=dr["Resid"], disc_roi_fav=dr["ROI_fav"], disc_roi_dog=dr["ROI_dog"],
        val_n=vr["N"] if vr else 0, val_resid=vr["Resid"] if vr else np.nan,
        oos_n=orr["N"] if orr else 0, oos_resid=orr["Resid"] if orr else np.nan,
    ))

# Marginal signals
print("\n--- Marginal (disc N>=100 & <150, |Resid|>=0.025) ---")
marginals = [x for x in all_results if x["phase"] == "Discovery" and 100 <= x["N"] < 150 and abs(x["Resid"]) >= 0.025 and x["dim"] != "baseline"]
for dr in marginals:
    vr = get_result(dr["label"], "Validation", dr.get("dim"))
    orr = get_result(dr["label"], "OOS", dr.get("dim"))
    print(f"  {dr['label']:35s}  Disc: N={dr['N']}, Resid={dr['Resid']:+.4f}")
    if vr:
        print(f"  {'':35s}  Val:  N={vr['N']}, Resid={vr['Resid']:+.4f}")
    if orr:
        print(f"  {'':35s}  OOS:  N={orr['N']}, Resid={orr['Resid']:+.4f}")

# ─── SAVE ────────────────────────────────────────────────────
pd.DataFrame(all_results).to_csv(f"{OUT}/MLB_SIDES_PHASE4_FINAL_TABLE.csv", index=False)
pd.DataFrame(survivors).to_csv(f"{OUT}/survivors.csv", index=False)
gm_full[["game_pk", "date", "season", "home_team", "away_team", "fav_side", "fav_team", "dog_team",
         "fav_implied", "fav_ml_price", "dog_ml_price", "total_line",
         "fav_sp_fip", "dog_sp_fip", "sp_fip_diff",
         "fav_off", "dog_off", "off_diff",
         "fav_bp_era", "dog_bp_era", "bp_era_diff",
         "fav_is_home", "reason", "winpath", "fav_won"]].to_csv(
    f"{OUT}/classification_table.csv", index=False)

print(f"\nSaved to {OUT}/")

# ─── FINAL BOARD ─────────────────────────────────────────────
keep_n = sum(1 for s in survivors if s["status"] == "KEEP")
monitor_n = sum(1 for s in survivors if s["status"] == "MONITOR")
kill_n = sum(1 for s in survivors if s["status"] == "KILL")
print(f"\n=== FINAL BOARD: {keep_n} KEEP, {monitor_n} MONITOR, {kill_n} KILL ===")
for s in survivors:
    print(f"  {s['label']:35s}  {s['status']:8s}  bet={s['bet_side']}  D_resid={s['disc_resid']:+.4f}  V_resid={s.get('val_resid', 'nan')}  O_resid={s.get('oos_resid', 'nan')}")
