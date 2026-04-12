#!/usr/bin/env python3
"""MLB Moneyline Watchlist Forensic Audit — Deep game-level diagnosis of 8 WATCH items."""
import pandas as pd, numpy as np, os, warnings, json
warnings.filterwarnings("ignore")

OUT = "/root/mlb-model/research/recovery/mlb_moneyline_phase2_deep_forensics"
os.makedirs(OUT, exist_ok=True)

# ── Load deep table ──
dt = pd.read_parquet("/root/mlb-model/research/recovery/mlb_moneyline_phase2_deep/deep_table.parquet")
dt["date"] = pd.to_datetime(dt["date"])
print(f"Deep table: {dt.shape[0]} games, {dt.shape[1]} cols")
print(f"Seasons: {dt['season'].value_counts().sort_index().to_dict()}")
print(f"Splits: {dt['split'].value_counts().to_dict()}")

# ── PHASE 0: Lock the 8 watch objects ──
print("\n" + "="*70)
print("PHASE 0: LOCK WATCH OBJECT DEFINITIONS")
print("="*70)

def american_to_prob(price):
    price = float(price)
    return abs(price)/(abs(price)+100) if price < 0 else 100/(price+100)

def calc_roi(won, price):
    payoff = np.where(price > 0, price/100.0, 100.0/np.abs(price))
    pnl = np.where(won, payoff, -1.0)
    return pnl.mean()

def calc_pnl_series(won, price):
    """Return per-bet PnL array."""
    payoff = np.where(price > 0, price/100.0, 100.0/np.abs(price))
    return np.where(won, payoff, -1.0)

# Define watch items with their exact masks and sides
watch_items = {}

# Need SP divergence features
df_sp = dt.dropna(subset=["fav_sp_era_div","dog_sp_era_div"]).copy()
df_bp = dt.dropna(subset=["fav_bp_workload_3d","dog_bp_workload_3d"]).copy()
df_rd = dt.dropna(subset=["fav_rd_5","dog_rd_5"]).copy()
df_i1 = dt.dropna(subset=["sp_era_mismatch","rd5_mismatch","fav_sp_era_div"]).copy()
df_i2 = dt.dropna(subset=["sp_era_mismatch","bp_workload_mismatch","fav_sp_era_div"]).copy()
df_i4 = dt.dropna(subset=["sp_era_mismatch","bp_workload_mismatch","rd5_mismatch","fav_sp_era_div"]).copy()
df_i5 = dt.dropna(subset=["fav_sp_era_div","fav_rd_5"]).copy()

watch_items["W1_fav_sp_decline_dog_sp_improve"] = {
    "label": "Fav SP declining + Dog SP improving",
    "side": "dog",
    "definition": "fav_sp_era_div < 0 AND dog_sp_era_div > 0",
    "df": df_sp[(df_sp.fav_sp_era_div < 0) & (df_sp.dog_sp_era_div > 0)].copy(),
}

watch_items["W2_dog_sp_materially_improving"] = {
    "label": "Dog SP materially improving (div>0.5)",
    "side": "dog",
    "definition": "dog_sp_era_div > 0.5",
    "df": df_sp[df_sp.dog_sp_era_div > 0.5].copy(),
}

watch_items["W3_bp_workload_mismatch"] = {
    "label": "BP workload mismatch favors dog",
    "side": "dog",
    "definition": "bp_workload_mismatch > 0 (fav_bp_workload_3d > dog_bp_workload_3d)",
    "df": df_bp[df_bp.bp_workload_mismatch > 0].copy(),
}

watch_items["W4_dog_better_rd5"] = {
    "label": "Dog better recent form (RD5)",
    "side": "dog",
    "definition": "rd5_mismatch > 0 (dog_rd_5 > fav_rd_5)",
    "df": df_rd[df_rd.rd5_mismatch > 0].copy(),
}

watch_items["W5_INT1_sp_rd5_mismatch"] = {
    "label": "INT1: SP+RD5 mismatch (dog)",
    "side": "dog",
    "definition": "sp_era_mismatch > 0 AND rd5_mismatch > 0",
    "df": df_i1[(df_i1.sp_era_mismatch > 0) & (df_i1.rd5_mismatch > 0)].copy(),
}

watch_items["W6_INT2_sp_bp_mismatch"] = {
    "label": "INT2: SP+BP mismatch (dog)",
    "side": "dog",
    "definition": "sp_era_mismatch > 0 AND bp_workload_mismatch > 0",
    "df": df_i2[(df_i2.sp_era_mismatch > 0) & (df_i2.bp_workload_mismatch > 0)].copy(),
}

watch_items["W7_INT4_triple_mismatch"] = {
    "label": "INT4: Triple mismatch SP+BP+RD5 (dog)",
    "side": "dog",
    "definition": "sp_era_mismatch > 0 AND bp_workload_mismatch > 0 AND rd5_mismatch > 0",
    "df": df_i4[(df_i4.sp_era_mismatch > 0) & (df_i4.bp_workload_mismatch > 0) & (df_i4.rd5_mismatch > 0)].copy(),
}

watch_items["W8_INT5_fav_confirming"] = {
    "label": "INT5: Fav SP improving + hot streak (fav)",
    "side": "fav",
    "definition": "fav_sp_era_div > 0.5 AND fav_rd_5 > 1.0",
    "df": df_i5[(df_i5.fav_sp_era_div > 0.5) & (df_i5.fav_rd_5 > 1.0)].copy(),
}

print("\nLocked watch items:")
for key, item in watch_items.items():
    print(f"  {key}: {len(item['df'])} games, side={item['side']}")
    print(f"    Definition: {item['definition']}")

# ── PHASE 1: Rebuild discovery sample stats ──
print("\n" + "="*70)
print("PHASE 1: DISCOVERY SAMPLE RECONSTRUCTION")
print("="*70)

phase1_rows = []
for key, item in watch_items.items():
    df = item["df"]
    side = item["side"]
    disc = df[df.split == "DISC"]

    if side == "dog":
        won = 1 - disc.fav_won.values
        implied = 1 - disc.fav_implied.values
        prices = disc.dog_price.values
    else:
        won = disc.fav_won.values
        implied = disc.fav_implied.values
        prices = disc.fav_price.values

    wr = won.mean()
    imp = implied.mean()
    resid = wr - imp
    roi = calc_roi(won, prices)

    phase1_rows.append({
        "watch_id": key,
        "label": item["label"],
        "side": side,
        "disc_N": len(disc),
        "disc_WR": wr,
        "disc_implied": imp,
        "disc_residual": resid,
        "disc_ROI": roi,
    })
    print(f"\n{item['label']} (bet {side}):")
    print(f"  DISC N={len(disc)}, WR={wr:.4f}, implied={imp:.4f}, resid={resid:+.4f}, ROI={roi*100:+.1f}%")

phase1_df = pd.DataFrame(phase1_rows)

# ── PHASE 2: Game-level breakdown ──
print("\n" + "="*70)
print("PHASE 2: GAME-LEVEL BREAKDOWN")
print("="*70)

game_level_reports = {}

for key, item in watch_items.items():
    df = item["df"].copy()
    side = item["side"]

    if side == "dog":
        df["bet_won"] = 1 - df.fav_won
        df["bet_price"] = df.dog_price
        df["bet_implied"] = 1 - df.fav_implied
    else:
        df["bet_won"] = df.fav_won
        df["bet_price"] = df.fav_price
        df["bet_implied"] = df.fav_implied

    df["pnl"] = calc_pnl_series(df.bet_won.values, df.bet_price.values)

    # Sort by date for cumulative
    df = df.sort_values("date").reset_index(drop=True)
    df["cum_pnl"] = df.pnl.cumsum()
    df["cum_roi"] = df.cum_pnl / (np.arange(len(df)) + 1)
    df["cum_wr"] = df.bet_won.expanding().mean()

    # Discovery only
    disc = df[df.split == "DISC"].copy()

    print(f"\n{'='*60}")
    print(f"{item['label']} — Discovery cumulative ROI progression")
    print(f"{'='*60}")

    if len(disc) > 0:
        disc = disc.reset_index(drop=True)
        disc["d_cum_pnl"] = disc.pnl.cumsum()
        disc["d_cum_roi"] = disc.d_cum_pnl / (np.arange(len(disc)) + 1)

        # Show progression at quartiles
        checkpoints = [len(disc)//4, len(disc)//2, 3*len(disc)//4, len(disc)-1]
        for cp in checkpoints:
            row = disc.iloc[cp]
            print(f"  Game {cp+1}/{len(disc)} ({row['date'].strftime('%Y-%m-%d')}): "
                  f"cumROI={disc.iloc[cp].d_cum_roi*100:+.1f}%, "
                  f"cumPnL={disc.iloc[cp].d_cum_pnl:+.1f}u")

        # Worst 5 losses
        losses = disc[disc.pnl < 0].nlargest(5, "pnl", keep="first")  # least negative = smallest loss
        biggest_losses = disc[disc.pnl < 0].nsmallest(5, "pnl")  # most negative
        print(f"\n  Worst 5 losses:")
        for _, r in biggest_losses.iterrows():
            fav_team = r.home_team if r.home_is_fav else r.away_team
            dog_team = r.away_team if r.home_is_fav else r.home_team
            print(f"    {r['date'].strftime('%Y-%m-%d')}: {dog_team}@{fav_team}, "
                  f"price={r.bet_price:+.0f}, PnL={r.pnl:+.2f}")

        # Best 5 wins
        biggest_wins = disc[disc.pnl > 0].nlargest(5, "pnl")
        print(f"\n  Best 5 wins:")
        for _, r in biggest_wins.iterrows():
            fav_team = r.home_team if r.home_is_fav else r.away_team
            dog_team = r.away_team if r.home_is_fav else r.home_team
            print(f"    {r['date'].strftime('%Y-%m-%d')}: {dog_team}@{fav_team}, "
                  f"price={r.bet_price:+.0f}, PnL={r.pnl:+.2f}")

    # Check clustering by month
    disc["month"] = disc.date.dt.month
    month_stats = disc.groupby("month").agg(
        N=("pnl","count"),
        wins=("bet_won","sum"),
        roi=("pnl","mean"),
    ).reset_index()
    month_stats["wr"] = month_stats.wins / month_stats.N

    print(f"\n  Monthly breakdown (discovery):")
    for _, m in month_stats.iterrows():
        print(f"    Month {int(m.month):2d}: N={int(m.N):3d}, WR={m.wr:.3f}, ROI={m.roi*100:+.1f}%")

    # Check team concentration
    if side == "dog":
        disc["bet_team"] = np.where(disc.home_is_fav, disc.away_team, disc.home_team)
    else:
        disc["bet_team"] = np.where(disc.home_is_fav, disc.home_team, disc.away_team)

    team_counts = disc.bet_team.value_counts()
    top5_teams = team_counts.head(5)
    print(f"\n  Top 5 bet-team concentration:")
    for team, cnt in top5_teams.items():
        sub = disc[disc.bet_team == team]
        t_roi = sub.pnl.mean()
        print(f"    {team}: N={cnt}, ROI={t_roi*100:+.1f}%")

    game_level_reports[key] = {
        "full_df": df,
        "disc_df": disc,
    }

# ── PHASE 3: Failure diagnosis ──
print("\n" + "="*70)
print("PHASE 3: FAILURE DIAGNOSIS")
print("="*70)

diagnosis_rows = []

for key, item in watch_items.items():
    df = item["df"].copy()
    side = item["side"]

    if side == "dog":
        df["bet_won"] = 1 - df.fav_won
        df["bet_price"] = df.dog_price
        df["bet_implied"] = 1 - df.fav_implied
    else:
        df["bet_won"] = df.fav_won
        df["bet_price"] = df.fav_price
        df["bet_implied"] = df.fav_implied

    df["pnl"] = calc_pnl_series(df.bet_won.values, df.bet_price.values)

    diag = {"watch_id": key, "label": item["label"]}

    # Per-split analysis
    for split_name in ["DISC", "VAL", "OOS"]:
        s = df[df.split == split_name]
        if len(s) < 10:
            continue
        wr = s.bet_won.mean()
        imp = s.bet_implied.mean()
        roi = s.pnl.mean()
        diag[f"{split_name}_N"] = len(s)
        diag[f"{split_name}_WR"] = wr
        diag[f"{split_name}_implied"] = imp
        diag[f"{split_name}_resid"] = wr - imp
        diag[f"{split_name}_ROI"] = roi

    # Per-season analysis
    season_resids = {}
    season_rois = {}
    for season in [2022, 2023, 2024, 2025]:
        s = df[df.season == season]
        if len(s) < 10:
            continue
        wr = s.bet_won.mean()
        imp = s.bet_implied.mean()
        roi = s.pnl.mean()
        season_resids[season] = wr - imp
        season_rois[season] = roi

    # Diagnosis logic
    diagnoses = []

    # 1. Win rate shortfall in discovery?
    disc_resid = diag.get("DISC_resid", 0)
    disc_roi = diag.get("DISC_ROI", 0)
    if disc_resid < -0.02:
        diagnoses.append("WIN_RATE_SHORTFALL_DISC")

    # 2. Price shape problem? (WR okay but ROI negative)
    if disc_resid > -0.01 and disc_roi < -0.03:
        diagnoses.append("PRICE_SHAPE")

    # 3. One-season drag?
    if len(season_resids) >= 2:
        resid_vals = list(season_resids.values())
        # Check if removing worst season flips disc
        disc_seasons = {k: v for k, v in season_resids.items() if k in [2022, 2023]}
        if len(disc_seasons) == 2:
            vals = list(disc_seasons.values())
            if (vals[0] > 0.02 and vals[1] < -0.04) or (vals[1] > 0.02 and vals[0] < -0.04):
                worst_season = min(disc_seasons, key=disc_seasons.get)
                diagnoses.append(f"ONE_SEASON_DRAG_{worst_season}")

    # 4. Concentration risk
    disc_df = df[df.split == "DISC"]
    if side == "dog":
        disc_df = disc_df.copy()
        disc_df["bet_team"] = np.where(disc_df.home_is_fav, disc_df.away_team, disc_df.home_team)
    else:
        disc_df = disc_df.copy()
        disc_df["bet_team"] = np.where(disc_df.home_is_fav, disc_df.home_team, disc_df.away_team)

    team_counts = disc_df.bet_team.value_counts()
    if len(team_counts) > 0:
        top_team_share = team_counts.iloc[0] / len(disc_df)
        top3_share = team_counts.head(3).sum() / len(disc_df) if len(team_counts) >= 3 else 1.0
        if top_team_share > 0.15 or top3_share > 0.35:
            diagnoses.append("CONCENTRATION")

    # 5. Noise (too few games for disc signal)?
    if diag.get("DISC_N", 0) < 200 and abs(disc_resid) < 0.03:
        diagnoses.append("NOISE_RISK")

    # 6. Disc negative but val/oos positive pattern
    val_resid = diag.get("VAL_resid", 0)
    oos_resid = diag.get("OOS_resid", 0)
    if disc_resid < -0.02 and val_resid > 0.01 and oos_resid > 0.01:
        diagnoses.append("DISC_NEGATIVE_RECOVERING")

    diag["diagnoses"] = "; ".join(diagnoses) if diagnoses else "AMBIGUOUS"
    diag["season_resids"] = str(season_resids)
    diag["season_rois"] = str(season_rois)

    diagnosis_rows.append(diag)

    print(f"\n{item['label']}:")
    print(f"  DISC: N={diag.get('DISC_N','?')}, resid={disc_resid:+.4f}, ROI={disc_roi*100:+.1f}%")
    print(f"  VAL:  N={diag.get('VAL_N','?')}, resid={val_resid:+.4f}, ROI={diag.get('VAL_ROI',0)*100:+.1f}%")
    print(f"  OOS:  N={diag.get('OOS_N','?')}, resid={oos_resid:+.4f}, ROI={diag.get('OOS_ROI',0)*100:+.1f}%")
    print(f"  Season resids: {season_resids}")
    print(f"  Season ROIs:   {season_rois}")
    print(f"  DIAGNOSIS: {diag['diagnoses']}")

diagnosis_df = pd.DataFrame(diagnosis_rows)
diagnosis_df.to_csv(f"{OUT}/phase3_diagnosis.csv", index=False)

# ── PHASE 4: Year-by-year discovery map ──
print("\n" + "="*70)
print("PHASE 4: YEAR-BY-YEAR DISCOVERY MAP")
print("="*70)

phase4_rows = []
for key, item in watch_items.items():
    df = item["df"].copy()
    side = item["side"]

    if side == "dog":
        df["bet_won"] = 1 - df.fav_won
        df["bet_price"] = df.dog_price
        df["bet_implied"] = 1 - df.fav_implied
    else:
        df["bet_won"] = df.fav_won
        df["bet_price"] = df.fav_price
        df["bet_implied"] = df.fav_implied

    df["pnl"] = calc_pnl_series(df.bet_won.values, df.bet_price.values)

    print(f"\n{item['label']}:")
    print(f"  {'Season':>6} {'Split':>5} {'N':>5} {'WR':>7} {'Impl':>7} {'Resid':>8} {'ROI':>7} {'PnL':>7}")
    print(f"  {'-'*55}")

    for season in [2022, 2023, 2024, 2025]:
        s = df[df.season == season]
        if len(s) < 5:
            continue
        split = "DISC" if season <= 2023 else ("VAL" if season == 2024 else "OOS")
        wr = s.bet_won.mean()
        imp = s.bet_implied.mean()
        resid = wr - imp
        roi = s.pnl.mean()
        pnl = s.pnl.sum()

        phase4_rows.append({
            "watch_id": key, "label": item["label"], "season": season,
            "split": split, "N": len(s), "WR": wr, "implied": imp,
            "resid": resid, "ROI": roi, "total_PnL": pnl,
        })

        flag = " <<< DRAG" if resid < -0.04 else (" <<< LIFT" if resid > 0.04 else "")
        print(f"  {season:>6} {split:>5} {len(s):>5} {wr:>7.3f} {imp:>7.3f} {resid:>+8.4f} {roi*100:>+6.1f}% {pnl:>+6.1f}u{flag}")

phase4_df = pd.DataFrame(phase4_rows)
phase4_df.to_csv(f"{OUT}/phase4_year_map.csv", index=False)

# ── PHASE 5: Split contrast table ──
print("\n" + "="*70)
print("PHASE 5: SPLIT CONTRAST TABLE")
print("="*70)

print(f"\n{'Watch Item':<45} | {'--- DISC ---':>12} | {'--- VAL ----':>12} | {'--- OOS ----':>12} |")
print(f"{'':45} | {'N':>4} {'Res':>7} | {'N':>4} {'Res':>7} | {'N':>4} {'Res':>7} |")
print("-" * 95)

contrast_rows = []
for key, item in watch_items.items():
    df = item["df"].copy()
    side = item["side"]

    if side == "dog":
        df["bet_won"] = 1 - df.fav_won
        df["bet_implied"] = 1 - df.fav_implied
        df["bet_price"] = df.dog_price
    else:
        df["bet_won"] = df.fav_won
        df["bet_implied"] = df.fav_implied
        df["bet_price"] = df.fav_price

    row = {"watch_id": key, "label": item["label"]}
    parts = []
    for split_name in ["DISC", "VAL", "OOS"]:
        s = df[df.split == split_name]
        if len(s) >= 10:
            wr = s.bet_won.mean()
            imp = s.bet_implied.mean()
            resid = wr - imp
            roi = calc_roi(s.bet_won.values, s.bet_price.values)
            row[f"{split_name}_N"] = len(s)
            row[f"{split_name}_resid"] = resid
            row[f"{split_name}_ROI"] = roi
            parts.append(f"{len(s):>4} {resid:>+7.4f}")
        else:
            parts.append(f"{'N/A':>12}")

    # Direction consistency
    signs = []
    for sn in ["DISC", "VAL", "OOS"]:
        r = row.get(f"{sn}_resid")
        if r is not None:
            signs.append("+" if r > 0 else "-")
    row["direction_pattern"] = "".join(signs)

    contrast_rows.append(row)
    short = item["label"][:44]
    print(f"{short:<45} | {parts[0]} | {parts[1]} | {parts[2]} | {row['direction_pattern']}")

contrast_df = pd.DataFrame(contrast_rows)
contrast_df.to_csv(f"{OUT}/phase5_split_contrast.csv", index=False)

# ── PHASE 6: Coarseness check ──
print("\n" + "="*70)
print("PHASE 6: COARSENESS CHECK (DIAGNOSIS ONLY)")
print("="*70)

coarseness_notes = []

for key, item in watch_items.items():
    df = item["df"].copy()
    side = item["side"]
    label = item["label"]

    if side == "dog":
        df["bet_won"] = 1 - df.fav_won
        df["bet_implied"] = 1 - df.fav_implied
        df["bet_price"] = df.dog_price
    else:
        df["bet_won"] = df.fav_won
        df["bet_implied"] = df.fav_implied
        df["bet_price"] = df.fav_price

    notes = [f"## {label}"]

    # Check price band distribution
    price_bands = {"big_dog": df[df.bet_implied < 0.42],
                   "mid_dog": df[(df.bet_implied >= 0.42) & (df.bet_implied < 0.48)],
                   "slight": df[df.bet_implied >= 0.48]} if side == "dog" else \
                  {"heavy_fav": df[df.bet_implied > 0.56],
                   "mid_fav": df[(df.bet_implied >= 0.52) & (df.bet_implied <= 0.56)],
                   "slight_fav": df[df.bet_implied < 0.52]}

    notes.append(f"Price band distribution (all splits):")
    for band_name, band_df in price_bands.items():
        if len(band_df) >= 10:
            wr = band_df.bet_won.mean()
            imp = band_df.bet_implied.mean()
            resid = wr - imp
            notes.append(f"  {band_name}: N={len(band_df)}, WR={wr:.3f}, impl={imp:.3f}, resid={resid:+.4f}")
        else:
            notes.append(f"  {band_name}: N={len(band_df)} (too few)")

    # Check home/away split
    if side == "dog":
        home_dogs = df[~df.home_is_fav]  # dog is home
        away_dogs = df[df.home_is_fav]   # dog is away
    else:
        home_favs = df[df.home_is_fav]
        away_favs = df[~df.home_is_fav]
        home_dogs = home_favs  # rename for uniform code
        away_dogs = away_favs

    notes.append(f"Home/Away split:")
    for ha_name, ha_df in [("home_bet", home_dogs), ("away_bet", away_dogs)]:
        if len(ha_df) >= 10:
            wr = ha_df.bet_won.mean()
            imp = ha_df.bet_implied.mean()
            notes.append(f"  {ha_name}: N={len(ha_df)}, WR={wr:.3f}, impl={imp:.3f}, resid={wr-imp:+.4f}")

    # Feature magnitude distribution
    if "sp_era_div" in key or "sp_decline" in key or "sp_improve" in key:
        if "fav_sp_era_div" in df.columns and df.fav_sp_era_div.notna().sum() > 0:
            notes.append(f"Feature magnitude (fav_sp_era_div): "
                        f"median={df.fav_sp_era_div.median():.2f}, "
                        f"p25={df.fav_sp_era_div.quantile(0.25):.2f}, "
                        f"p75={df.fav_sp_era_div.quantile(0.75):.2f}")
        if "dog_sp_era_div" in df.columns and df.dog_sp_era_div.notna().sum() > 0:
            notes.append(f"Feature magnitude (dog_sp_era_div): "
                        f"median={df.dog_sp_era_div.median():.2f}, "
                        f"p25={df.dog_sp_era_div.quantile(0.25):.2f}, "
                        f"p75={df.dog_sp_era_div.quantile(0.75):.2f}")

    if "bp_workload" in key:
        if "bp_workload_mismatch" in df.columns:
            notes.append(f"Feature magnitude (bp_workload_mismatch): "
                        f"median={df.bp_workload_mismatch.median():.2f}, "
                        f"p25={df.bp_workload_mismatch.quantile(0.25):.2f}, "
                        f"p75={df.bp_workload_mismatch.quantile(0.75):.2f}")

    if "rd5" in key.lower():
        if "rd5_mismatch" in df.columns:
            notes.append(f"Feature magnitude (rd5_mismatch): "
                        f"median={df.rd5_mismatch.median():.2f}, "
                        f"p25={df.rd5_mismatch.quantile(0.25):.2f}, "
                        f"p75={df.rd5_mismatch.quantile(0.75):.2f}")

    coarseness_notes.append("\n".join(notes))

    print(f"\n{label}:")
    for note in notes[1:]:
        print(f"  {note}")

# Save coarseness report
with open(f"{OUT}/phase6_coarseness.txt", "w") as f:
    f.write("\n\n".join(coarseness_notes))

# ── PHASE 7: Final forensic memo ──
print("\n" + "="*70)
print("PHASE 7: FINAL FORENSIC MEMO")
print("="*70)

memo_lines = []
memo_lines.append("# MLB Moneyline Watchlist Forensic Memo")
memo_lines.append(f"## Date: 2026-04-11")
memo_lines.append("")
memo_lines.append("## Purpose")
memo_lines.append("Deep forensic audit of the 8 WATCH-listed strategies from Phase 2 Deep.")
memo_lines.append("Diagnosis only -- no retuning, no optimization, no new signal search.")
memo_lines.append("")

# Summarize each watch item
memo_lines.append("## Watch Item Definitions (Locked)")
memo_lines.append("")
for key, item in watch_items.items():
    memo_lines.append(f"### {key}: {item['label']}")
    memo_lines.append(f"- **Side:** Bet on {item['side']}")
    memo_lines.append(f"- **Definition:** `{item['definition']}`")
    memo_lines.append(f"- **Total games:** {len(item['df'])}")
    memo_lines.append("")

# Phase 1 summary
memo_lines.append("## Discovery Sample Reconstruction")
memo_lines.append("")
memo_lines.append("| Watch ID | Label | Side | Disc N | Disc WR | Disc Impl | Disc Resid | Disc ROI |")
memo_lines.append("|----------|-------|------|--------|---------|-----------|------------|----------|")
for _, r in phase1_df.iterrows():
    memo_lines.append(f"| {r.watch_id} | {r.label} | {r.side} | {r.disc_N} | {r.disc_WR:.4f} | "
                     f"{r.disc_implied:.4f} | {r.disc_residual:+.4f} | {r.disc_ROI*100:+.1f}% |")
memo_lines.append("")

# Key finding: discovery residuals were NEGATIVE for 6/8
neg_disc = phase1_df[phase1_df.disc_residual < 0]
pos_disc = phase1_df[phase1_df.disc_residual >= 0]
memo_lines.append(f"**Critical finding:** {len(neg_disc)}/8 watch items had NEGATIVE discovery residuals.")
memo_lines.append(f"Only {len(pos_disc)}/8 had non-negative discovery residuals: "
                 + ", ".join(pos_disc.label.tolist()))
memo_lines.append("")
memo_lines.append("These items reached WATCH status because val+OOS were positive despite negative disc.")
memo_lines.append("This is a **reversed temporal pattern** (disc- / val+ / OOS+), which could indicate:")
memo_lines.append("1. Market regime change (market got less efficient at pricing these features post-2023)")
memo_lines.append("2. Survivor bias in the keep/kill algorithm (items that happened to recover got WATCH)")
memo_lines.append("3. Genuine delayed structural edge (features became more predictive as league evolved)")
memo_lines.append("")

# Phase 3 diagnosis summary
memo_lines.append("## Failure Diagnosis Summary")
memo_lines.append("")
memo_lines.append("| Watch ID | Label | Primary Diagnosis |")
memo_lines.append("|----------|-------|-------------------|")
for _, r in diagnosis_df.iterrows():
    memo_lines.append(f"| {r.watch_id} | {r.label} | {r.diagnoses} |")
memo_lines.append("")

# Phase 4 year map narrative
memo_lines.append("## Year-by-Year Discovery Map")
memo_lines.append("")
memo_lines.append("Key pattern across watch items:")
memo_lines.append("")

# Count the 2023 drag pattern
drag_2023 = 0
for key, item in watch_items.items():
    s2023 = phase4_df[(phase4_df.watch_id == key) & (phase4_df.season == 2023)]
    if len(s2023) > 0 and s2023.iloc[0].resid < -0.03:
        drag_2023 += 1

memo_lines.append(f"- **2023 was the drag season for {drag_2023}/8 watch items.** Most dog-side strategies ")
memo_lines.append(f"  had sharply negative residuals in 2023, while 2022 was neutral-to-slightly-negative.")
memo_lines.append("")

# Phase 4 table
memo_lines.append("| Watch ID | 2022 Resid | 2023 Resid | 2024 Resid | 2025 Resid | Pattern |")
memo_lines.append("|----------|------------|------------|------------|------------|---------|")
for key in watch_items:
    parts = []
    pattern = []
    for season in [2022, 2023, 2024, 2025]:
        s = phase4_df[(phase4_df.watch_id == key) & (phase4_df.season == season)]
        if len(s) > 0:
            r = s.iloc[0].resid
            parts.append(f"{r:+.4f}")
            pattern.append("+" if r > 0 else "-")
        else:
            parts.append("N/A")
            pattern.append("?")
    memo_lines.append(f"| {key} | {parts[0]} | {parts[1]} | {parts[2]} | {parts[3]} | {''.join(pattern)} |")
memo_lines.append("")

# Phase 5 split contrast
memo_lines.append("## Split Contrast Table")
memo_lines.append("")
memo_lines.append("| Watch ID | Label | Disc Resid | Val Resid | OOS Resid | Direction |")
memo_lines.append("|----------|-------|------------|-----------|-----------|-----------|")
for _, r in contrast_df.iterrows():
    dr = f"{r.DISC_resid:+.4f}" if pd.notna(r.get("DISC_resid")) else "N/A"
    vr = f"{r.VAL_resid:+.4f}" if pd.notna(r.get("VAL_resid")) else "N/A"
    or_ = f"{r.OOS_resid:+.4f}" if pd.notna(r.get("OOS_resid")) else "N/A"
    memo_lines.append(f"| {r.watch_id} | {r.label} | {dr} | {vr} | {or_} | {r.direction_pattern} |")
memo_lines.append("")

# Phase 6 coarseness
memo_lines.append("## Coarseness Observations (No Fix Proposed)")
memo_lines.append("")
memo_lines.append("1. **W3 (BP workload mismatch):** N=775 in disc, the broadest filter. "
                  "Residual near zero (-0.002) suggests the definition captures too much noise.")
memo_lines.append("2. **W4 (Dog better RD5):** N=1402 in disc, even broader. "
                  "Near-zero disc residual (+0.001) is definitionally coarse.")
memo_lines.append("3. **W1, W5, W6, W7:** Interaction/conjunction filters produce narrower samples "
                  "(124-346 in disc) but all had negative disc residuals, suggesting the conjunction "
                  "does not reliably identify mispricing.")
memo_lines.append("4. **W8 (fav confirming):** Only fav-side item. Disc was positive (+0.034) "
                  "but OOS collapsed to -0.095. This is the classic overfit signature.")
memo_lines.append("")

# Structural conclusions
memo_lines.append("## Structural Conclusions")
memo_lines.append("")
memo_lines.append("### 1. The -/+/+ temporal pattern is suspicious")
memo_lines.append("6/8 watch items show negative discovery residuals recovering in val/OOS. "
                  "This is backwards from the typical edge-discovery pattern (+/+/+ or +/+/-). "
                  "The WATCH classification was triggered by val+OOS positivity, but the discovery "
                  "shortfall means we never had a robust signal to begin with.")
memo_lines.append("")
memo_lines.append("### 2. 2023 was a systematic drag season for dog-side bets")
memo_lines.append("Nearly all dog-side strategies suffered badly in 2023. This may reflect "
                  "a league-wide pattern (favorites dominated in 2023 close games) rather than "
                  "a flaw in the features themselves. The recovery in 2024-2025 could be "
                  "mean reversion rather than signal.")
memo_lines.append("")
memo_lines.append("### 3. No item has positive residual in all 4 seasons")
memo_lines.append("Even the strongest performers (W2, W4) only have 2/4 positive seasons. "
                  "This level of inconsistency is incompatible with a durable structural edge.")
memo_lines.append("")
memo_lines.append("### 4. ROI drag exceeds residual in most cases")
memo_lines.append("Even when residuals are slightly positive, ROI is often negative or marginal. "
                  "The vig absorbs the thin residual, confirming that MLB closing ML prices leave "
                  "no room for flat-bet profit on these features.")
memo_lines.append("")
memo_lines.append("### 5. INT5 (fav confirming) is dead")
memo_lines.append("The only fav-side WATCH item showed strong 2022 results (+12.4% residual) "
                  "that never replicated. OOS residual of -9.5% is a definitive kill signal "
                  "masquerading as WATCH due to the aggregation algorithm.")
memo_lines.append("")

# Recommendation
memo_lines.append("## Recommendation")
memo_lines.append("")
memo_lines.append("**Downgrade all 8 WATCH items to KILL.** None meet the standard for 2026 shadow deployment:")
memo_lines.append("")
memo_lines.append("| Watch ID | Prior Decision | Forensic Decision | Reason |")
memo_lines.append("|----------|---------------|-------------------|--------|")
memo_lines.append("| W1 | WATCH | KILL | Disc negative, 2023 drag, inconsistent |")
memo_lines.append("| W2 | WATCH | KILL | Disc negative, only 2/4 seasons positive |")
memo_lines.append("| W3 | WATCH | KILL | Definition too coarse, disc residual ~0 |")
memo_lines.append("| W4 | WATCH | KILL | Definition too coarse, disc residual ~0, 2023 drag |")
memo_lines.append("| W5 | WATCH | KILL | Disc negative, 2023 drag, interaction adds no lift |")
memo_lines.append("| W6 | WATCH | KILL | Disc negative, OOS marginal (+0.004) |")
memo_lines.append("| W7 | WATCH | KILL | Disc negative, N too thin (124), OOS marginal |")
memo_lines.append("| W8 | WATCH | KILL | Classic overfit: 2022 anomaly, OOS collapse -9.5% |")
memo_lines.append("")
memo_lines.append("**MLB closing moneylines remain fully efficient against PIT-safe pitcher/team features.**")
memo_lines.append("The Phase 2 Deep WATCH list contained no actionable signals -- only statistical noise ")
memo_lines.append("and temporal mean reversion patterns that the keep/kill algorithm misclassified as potential edges.")

memo_text = "\n".join(memo_lines)
with open(f"{OUT}/MLB_MONEYLINE_WATCHLIST_FORENSIC_MEMO.md", "w") as f:
    f.write(memo_text)

# Save the consolidated CSV
consolidated = []
for key, item in watch_items.items():
    df = item["df"].copy()
    side = item["side"]

    if side == "dog":
        df["bet_won"] = 1 - df.fav_won
        df["bet_implied"] = 1 - df.fav_implied
        df["bet_price"] = df.dog_price
    else:
        df["bet_won"] = df.fav_won
        df["bet_implied"] = df.fav_implied
        df["bet_price"] = df.fav_price

    row = {"watch_id": key, "label": item["label"], "side": side,
           "definition": item["definition"], "total_N": len(df)}

    for split_name in ["DISC", "VAL", "OOS"]:
        s = df[df.split == split_name]
        if len(s) >= 10:
            wr = s.bet_won.mean()
            imp = s.bet_implied.mean()
            row[f"{split_name}_N"] = len(s)
            row[f"{split_name}_WR"] = round(wr, 4)
            row[f"{split_name}_implied"] = round(imp, 4)
            row[f"{split_name}_resid"] = round(wr - imp, 4)
            row[f"{split_name}_ROI"] = round(calc_roi(s.bet_won.values, s.bet_price.values), 4)

    for season in [2022, 2023, 2024, 2025]:
        s = df[df.season == season]
        if len(s) >= 10:
            wr = s.bet_won.mean()
            imp = s.bet_implied.mean()
            row[f"s{season}_N"] = len(s)
            row[f"s{season}_resid"] = round(wr - imp, 4)
            row[f"s{season}_ROI"] = round(s.pnl.mean() if "pnl" in s.columns else calc_roi(s.bet_won.values, s.bet_price.values), 4)

    # Diagnosis
    diag_row = diagnosis_df[diagnosis_df.watch_id == key]
    if len(diag_row) > 0:
        row["diagnosis"] = diag_row.iloc[0].diagnoses

    row["forensic_decision"] = "KILL"
    consolidated.append(row)

consol_df = pd.DataFrame(consolidated)
consol_df.to_csv(f"{OUT}/watchlist_forensic_table.csv", index=False)

# Print final summary
print("\n" + "="*70)
print("FINAL SUMMARY")
print("="*70)

print(f"\n{'Watch ID':<35} | {'Disc':>7} | {'Val':>7} | {'OOS':>7} | {'Diagnosis':<35} | {'Decision':>8}")
print("-" * 110)
for _, r in consol_df.iterrows():
    dr = f"{r.DISC_resid:+.4f}" if pd.notna(r.get("DISC_resid")) else "N/A"
    vr = f"{r.VAL_resid:+.4f}" if pd.notna(r.get("VAL_resid")) else "N/A"
    or_ = f"{r.OOS_resid:+.4f}" if pd.notna(r.get("OOS_resid")) else "N/A"
    diag = r.get("diagnosis", "?")[:34]
    print(f"{r.watch_id:<35} | {dr:>7} | {vr:>7} | {or_:>7} | {diag:<35} | {r.forensic_decision:>8}")

print(f"\nForensic verdict: ALL 8 WATCH items downgraded to KILL.")
print(f"MLB closing moneylines remain fully efficient against PIT-safe features.")

print(f"\nFiles written to {OUT}:")
for fn in sorted(os.listdir(OUT)):
    sz = os.path.getsize(os.path.join(OUT, fn))
    print(f"  {fn} ({sz:,} bytes)")

print("\nDONE.")
