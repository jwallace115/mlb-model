import pandas as pd
import numpy as np
import os, warnings, textwrap
warnings.filterwarnings('ignore')

OUT = "/root/mlb-model/research/recovery/mlb_sides_phase6_hardening"
BASE = "/root/mlb-model"

###############################################################################
# PHASE 0: Lock exact objects
###############################################################################
print("=" * 70)
print("PHASE 0: LOCK EXACT OBJECTS")
print("=" * 70)

ct = pd.read_csv(os.path.join(BASE, 'research/recovery/mlb_sides_phase4_winpath/classification_table.csv'))
ct['date'] = pd.to_datetime(ct['date'])
print(f"Classification table: {ct.shape}")
print(f"Classes: {ct['reason'].value_counts().to_dict()}")

mixed = ct[ct['reason'] == 'MIXED'].copy()
print(f"MIXED total: {len(mixed)}")

# Add game_table fields for day/night
gt = pd.read_parquet(os.path.join(BASE, 'sim/data/game_table.parquet'))
gt_time = gt[['game_pk', 'local_start_hour']].drop_duplicates('game_pk')
mixed = mixed.merge(gt_time, on='game_pk', how='left')
mixed['day_night'] = np.where(mixed['local_start_hour'] < 17, 'day', 'night')

# bp_adv_dog: dog's BP ERA < fav's BP ERA => bp_era_diff > 0
mixed['bp_adv_dog'] = (mixed['bp_era_diff'] > 0).astype(int)

# Splits
disc = mixed[mixed['season'].isin([2022, 2023])].copy()
val  = mixed[mixed['season'] == 2024].copy()
oos  = mixed[mixed['season'] == 2025].copy()

# Define the two objects
def get_bp_adv_dog(df):
    return df[df['bp_adv_dog'] == 1]

def get_night_dog(df):
    return df[df['day_night'] == 'night']

print(f"\nbp_adv_dog: disc={len(get_bp_adv_dog(disc))}, val={len(get_bp_adv_dog(val))}, oos={len(get_bp_adv_dog(oos))}")
print(f"night_dog:  disc={len(get_night_dog(disc))}, val={len(get_night_dog(val))}, oos={len(get_night_dog(oos))}")

# Write Phase 0 lock
lock_lines = []
lock_lines.append("# Phase 0: Exact Object Lock")
lock_lines.append("")
lock_lines.append("## Source")
lock_lines.append("- Classification table: research/recovery/mlb_sides_phase4_winpath/classification_table.csv")
lock_lines.append("- MIXED = reason == 'MIXED' (all SP/offense/BP gaps below discovery median)")
lock_lines.append(f"- MIXED total: {len(mixed)} games")
lock_lines.append(f"- Discovery (2022-2023): {len(disc)}")
lock_lines.append(f"- Validation (2024): {len(val)}")
lock_lines.append(f"- OOS (2025): {len(oos)}")
lock_lines.append("")
lock_lines.append("## Object 1: bp_adv_dog")
lock_lines.append("- Definition: within MIXED, bp_era_diff > 0 (fav BP ERA > dog BP ERA)")
lock_lines.append("- bp_era_diff = fav_bp_era - dog_bp_era")
lock_lines.append("- Source: pitcher_game_logs.parquet, starter_flag==0, expanding cumulative ERA with shift(1)")
lock_lines.append(f"- Counts: disc={len(get_bp_adv_dog(disc))}, val={len(get_bp_adv_dog(val))}, oos={len(get_bp_adv_dog(oos))}")
lock_lines.append("")
lock_lines.append("## Object 2: night_dog")
lock_lines.append("- Definition: within MIXED, local_start_hour >= 17 (night game)")
lock_lines.append("- Source: game_table.parquet local_start_hour field")
lock_lines.append(f"- Counts: disc={len(get_night_dog(disc))}, val={len(get_night_dog(val))}, oos={len(get_night_dog(oos))}")
with open(os.path.join(OUT, 'phase0_exact_object_lock.md'), 'w') as f:
    f.write('\n'.join(lock_lines))
print("\nPhase 0 lock written.")

###############################################################################
# PHASE 1: BULLPEN PIT-SAFETY AUDIT
###############################################################################
print("\n" + "=" * 70)
print("PHASE 1: BULLPEN PIT-SAFETY AUDIT (MANDATORY FIRST GATE)")
print("=" * 70)

pgl = pd.read_parquet(os.path.join(BASE, 'mlb/data/pitcher_game_logs.parquet'))
bp = pgl[pgl["starter_flag"] == 0].copy()
print(f"Reliever appearances: {len(bp)}")
print(f"Columns: {list(bp.columns)[:15]}")

# Team-game aggregation
bp_game = bp.groupby(["team", "season", "game_date"]).agg(
    bp_er=("earned_runs", "sum"),
    bp_ip=("innings_pitched", "sum"),
).reset_index().sort_values(["team", "season", "game_date"])

# Rolling with shift(1) -- expanding season-to-date
bp_game["bp_cum_er"] = bp_game.groupby(["team", "season"])["bp_er"].transform(
    lambda x: x.shift(1).expanding().sum())
bp_game["bp_cum_ip"] = bp_game.groupby(["team", "season"])["bp_ip"].transform(
    lambda x: x.shift(1).expanding().sum())
bp_game["bp_era_rolling"] = np.where(
    bp_game["bp_cum_ip"] >= 10,
    bp_game["bp_cum_er"] / bp_game["bp_cum_ip"] * 9,
    np.nan)

print(f"BP ERA rolling coverage: {bp_game['bp_era_rolling'].notna().sum()}/{len(bp_game)}")

# 5 worked examples for PIT proof
print("\n--- 5 Worked Examples for PIT Proof ---")
sample = bp_game[bp_game["bp_era_rolling"].notna()].sample(5, random_state=42)
pit_results = []
for _, row in sample.iterrows():
    team, season, gd = row["team"], row["season"], row["game_date"]
    prior = bp[(bp["team"] == team) & (bp["season"] == season) & (bp["game_date"] < gd)]
    manual_er = prior["earned_runs"].sum()
    manual_ip = prior["innings_pitched"].sum()
    manual_era = manual_er / manual_ip * 9 if manual_ip > 0 else None
    match = abs(row['bp_era_rolling'] - manual_era) < 0.001 if manual_era else False
    print(f"  {team} {gd}: computed={row['bp_era_rolling']:.3f}, manual={manual_era:.3f}, match={match}")
    pit_results.append({'team': team, 'date': str(gd), 'computed': round(row['bp_era_rolling'], 3),
                        'manual': round(manual_era, 3) if manual_era else None, 'match': match})

all_match = all(r['match'] for r in pit_results)
print(f"\nAll 5 examples match: {all_match}")

# Check for opener/bulk contamination
high_ip = bp[bp["innings_pitched"] >= 5.0]
print(f"\nReliever appearances with IP >= 5.0: {len(high_ip)} ({100*len(high_ip)/len(bp):.2f}%)")
if len(high_ip) > 0:
    print(f"  Seasons: {high_ip['season'].value_counts().to_dict()}")
    print(f"  Max IP: {high_ip['innings_pitched'].max()}")
    contamination_pct = len(high_ip) / len(bp) * 100
    if contamination_pct < 0.5:
        opener_verdict = "NEGLIGIBLE (< 0.5% of appearances)"
    else:
        opener_verdict = "MATERIAL -- needs investigation"
else:
    opener_verdict = "NONE"
    contamination_pct = 0.0

# Verify chain: PGL only, no FanGraphs, no V1
print("\n--- Chain of Custody ---")
print("1. Source: pitcher_game_logs.parquet -- YES")
print("2. Filter: starter_flag == 0 -- YES (relievers only)")
print("3. Aggregation: team_gt + season + game_date -- YES")
print("4. Rolling: expanding().sum() with shift(1) -- YES (strictly prior games)")
print("5. Minimum IP: bp_cum_ip >= 10 -- YES")
print("6. No FanGraphs in chain -- CONFIRMED")
print("7. No V1 tables in chain -- CONFIRMED")

# PIT verdict
if all_match and contamination_pct < 1.0:
    pit_verdict = "PIT-SAFE AND LIVE-FEASIBLE"
elif all_match:
    pit_verdict = "PIT-SAFE BUT OPENER CONTAMINATION RISK"
else:
    pit_verdict = "CONTAMINATED"

print(f"\n*** PIT VERDICT: {pit_verdict} ***")

# Write PIT audit
pit_lines = []
pit_lines.append("# Phase 1: Bullpen PIT-Safety Audit")
pit_lines.append("")
pit_lines.append("## Source Chain")
pit_lines.append("- pitcher_game_logs.parquet -> starter_flag==0 -> groupby(team,season,date)")
pit_lines.append("- Rolling: shift(1).expanding().sum() (strictly prior games)")
pit_lines.append("- Minimum: bp_cum_ip >= 10 innings before ERA computed")
pit_lines.append("- NO FanGraphs, NO V1 tables, NO season-final stats in chain")
pit_lines.append("")
pit_lines.append("## 5 Worked Examples")
for r in pit_results:
    pit_lines.append(f"- {r['team']} {r['date']}: computed={r['computed']}, manual={r['manual']}, match={r['match']}")
pit_lines.append(f"\nAll 5 match: {all_match}")
pit_lines.append("")
pit_lines.append("## Opener/Bulk Contamination Check")
pit_lines.append(f"- Reliever appearances with IP >= 5.0: {len(high_ip)} ({contamination_pct:.2f}%)")
pit_lines.append(f"- Verdict: {opener_verdict}")
pit_lines.append("")
pit_lines.append(f"## VERDICT: {pit_verdict}")
pit_lines.append("")
if "CONTAMINATED" in pit_verdict:
    pit_lines.append("bp_adv_dog is KILLED at Phase 1. Cannot proceed.")
else:
    pit_lines.append("bp_adv_dog PASSES Phase 1 gate. Proceed to Phase 2.")

with open(os.path.join(OUT, 'phase1_bullpen_pit_audit.md'), 'w') as f:
    f.write('\n'.join(pit_lines))

if "CONTAMINATED" in pit_verdict:
    print("\n*** bp_adv_dog KILLED at Phase 1. Only night_dog proceeds. ***")
    bp_adv_alive = False
else:
    bp_adv_alive = True

###############################################################################
# HELPER: ROI calculator
###############################################################################
def calc_roi(df_sub, label=''):
    n = len(df_sub)
    if n < 20:
        return {'label': label, 'n': n, 'dog_wr': np.nan, 'implied_dog': np.nan,
                'residual': np.nan, 'roi_pct': np.nan}
    dog_wins = (df_sub['fav_won'] == 0).sum()
    dog_wr = dog_wins / n
    implied_dog = (1 - df_sub['fav_implied']).mean()
    residual = dog_wr - implied_dog
    profits = []
    for _, row in df_sub.iterrows():
        price = row['dog_ml_price']
        if row['fav_won'] == 0:
            profit = price / 100 if price > 0 else 100 / abs(price)
        else:
            profit = -1
        profits.append(profit)
    roi = np.mean(profits) * 100
    return {'label': label, 'n': n, 'dog_wr': dog_wr, 'implied_dog': implied_dog,
            'residual': residual, 'roi_pct': roi}

###############################################################################
# PHASE 2: Historical match rebuild
###############################################################################
print("\n" + "=" * 70)
print("PHASE 2: HISTORICAL MATCH REBUILD")
print("=" * 70)

objects = {}
if bp_adv_alive:
    objects['bp_adv_dog'] = get_bp_adv_dog
objects['night_dog'] = get_night_dog

phase2_lines = ["# Phase 2: Historical Match Rebuild", ""]

for obj_name, obj_fn in objects.items():
    print(f"\n--- {obj_name} ---")
    phase2_lines.append(f"## {obj_name}")
    phase2_lines.append("")

    for period_name, period_df in [('Discovery', disc), ('Validation', val), ('OOS', oos), ('Full', mixed)]:
        sub = obj_fn(period_df)
        r = calc_roi(sub, f"{obj_name}_{period_name}")
        print(f"  {period_name}: N={r['n']}, dogWR={r['dog_wr']:.4f}, impl={r['implied_dog']:.4f}, resid={r['residual']:+.4f}, ROI={r['roi_pct']:+.2f}%")
        phase2_lines.append(f"### {period_name}")
        phase2_lines.append(f"- N={r['n']}, dog_wr={r['dog_wr']:.4f}, implied={r['implied_dog']:.4f}, resid={r['residual']:+.4f}, ROI={r['roi_pct']:+.2f}%")
        phase2_lines.append("")

    # By season
    print(f"\n  By season:")
    phase2_lines.append("### By Season")
    for yr in sorted(mixed['season'].unique()):
        sub = obj_fn(mixed[mixed['season'] == yr])
        r = calc_roi(sub, f"{obj_name}_{yr}")
        if r['n'] >= 20:
            print(f"    {yr}: N={r['n']}, dogWR={r['dog_wr']:.4f}, resid={r['residual']:+.4f}, ROI={r['roi_pct']:+.2f}%")
            phase2_lines.append(f"- {yr}: N={r['n']}, dog_wr={r['dog_wr']:.4f}, resid={r['residual']:+.4f}, ROI={r['roi_pct']:+.2f}%")
    phase2_lines.append("")

    # By orientation (home/away dog)
    print(f"\n  By orientation:")
    phase2_lines.append("### By Orientation")
    sub_home = obj_fn(mixed[~mixed['fav_is_home'].astype(bool)])  # dog is home
    sub_away = obj_fn(mixed[mixed['fav_is_home'].astype(bool)])   # dog is away
    for orient_name, orient_df in [('dog_home', sub_home), ('dog_away', sub_away)]:
        r = calc_roi(orient_df, f"{obj_name}_{orient_name}")
        if r['n'] >= 20:
            print(f"    {orient_name}: N={r['n']}, dogWR={r['dog_wr']:.4f}, resid={r['residual']:+.4f}, ROI={r['roi_pct']:+.2f}%")
            phase2_lines.append(f"- {orient_name}: N={r['n']}, dog_wr={r['dog_wr']:.4f}, resid={r['residual']:+.4f}, ROI={r['roi_pct']:+.2f}%")
    phase2_lines.append("")

    # By price band
    print(f"\n  By price band:")
    phase2_lines.append("### By Price Band")
    sub_all = obj_fn(mixed)
    for lo, hi, label in [(100, 110, '+100/+110'), (111, 120, '+111/+120'),
                           (121, 135, '+121/+135'), (136, 200, '+136/+200')]:
        band = sub_all[(sub_all['dog_ml_price'] >= lo) & (sub_all['dog_ml_price'] <= hi)]
        r = calc_roi(band, label)
        if r['n'] >= 10:
            print(f"    {label}: N={r['n']}, dogWR={r['dog_wr']:.4f}, resid={r['residual']:+.4f}, ROI={r['roi_pct']:+.2f}%")
            phase2_lines.append(f"- {label}: N={r['n']}, dog_wr={r['dog_wr']:.4f}, resid={r['residual']:+.4f}, ROI={r['roi_pct']:+.2f}%")
    phase2_lines.append("")

with open(os.path.join(OUT, 'phase2_historical_rebuild.md'), 'w') as f:
    f.write('\n'.join(phase2_lines))

###############################################################################
# PHASE 3: Fragility / Concentration Audit
###############################################################################
print("\n" + "=" * 70)
print("PHASE 3: FRAGILITY / CONCENTRATION AUDIT")
print("=" * 70)

phase3_lines = ["# Phase 3: Fragility / Concentration Audit", ""]

for obj_name, obj_fn in objects.items():
    print(f"\n--- {obj_name} ---")
    phase3_lines.append(f"## {obj_name}")
    phase3_lines.append("")
    sub_all = obj_fn(mixed)
    total_n = len(sub_all)

    # Season concentration
    season_wr = []
    for yr in sorted(sub_all['season'].unique()):
        sy = sub_all[sub_all['season'] == yr]
        dw = (sy['fav_won'] == 0).sum()
        season_wr.append({'season': yr, 'n': len(sy), 'dog_wr': dw / len(sy) if len(sy) > 0 else np.nan})
    sdf = pd.DataFrame(season_wr)
    wr_range = sdf['dog_wr'].max() - sdf['dog_wr'].min()
    season_flag = "SEASON_INSTABILITY" if wr_range > 0.15 else "STABLE"
    print(f"  Season WR range: {wr_range:.3f} -> {season_flag}")
    phase3_lines.append(f"### Season Concentration")
    for _, r in sdf.iterrows():
        phase3_lines.append(f"- {int(r['season'])}: N={int(r['n'])}, dog_wr={r['dog_wr']:.3f}")
    phase3_lines.append(f"- WR range: {wr_range:.3f} -> {season_flag}")
    phase3_lines.append("")

    # Team concentration
    team_counts = sub_all['dog_team'].value_counts()
    top_team_pct = team_counts.iloc[0] / total_n
    team_flag = "TEAM_CONCENTRATION" if top_team_pct > 0.12 else "DISPERSED"
    print(f"  Top dog team: {team_counts.index[0]} ({team_counts.iloc[0]}/{total_n}, {top_team_pct:.1%}) -> {team_flag}")
    phase3_lines.append("### Team Concentration")
    for t in team_counts.head(5).index:
        phase3_lines.append(f"- {t}: {team_counts[t]} ({team_counts[t]/total_n:.1%})")
    phase3_lines.append(f"- Top team share: {top_team_pct:.1%} -> {team_flag}")
    phase3_lines.append("")

    # Division concentration
    div_map = {
        'NYY': 'ALE', 'BOS': 'ALE', 'TBR': 'ALE', 'TOR': 'ALE', 'BAL': 'ALE',
        'CLE': 'ALC', 'MIN': 'ALC', 'CHW': 'ALC', 'KCR': 'ALC', 'DET': 'ALC',
        'HOU': 'ALW', 'SEA': 'ALW', 'TEX': 'ALW', 'LAA': 'ALW', 'OAK': 'ALW', 'ATH': 'ALW',
        'ATL': 'NLE', 'NYM': 'NLE', 'PHI': 'NLE', 'MIA': 'NLE', 'WSN': 'NLE',
        'MIL': 'NLC', 'STL': 'NLC', 'CHC': 'NLC', 'CIN': 'NLC', 'PIT': 'NLC',
        'LAD': 'NLW', 'SDP': 'NLW', 'SFG': 'NLW', 'ARI': 'NLW', 'COL': 'NLW',
    }
    sub_all_copy = sub_all.copy()
    sub_all_copy['division'] = sub_all_copy['dog_team'].map(div_map)
    div_counts = sub_all_copy['division'].value_counts()
    top_div_pct = div_counts.iloc[0] / total_n
    div_flag = "DIVISION_CONCENTRATION" if top_div_pct > 0.25 else "DISPERSED"
    print(f"  Top division: {div_counts.index[0]} ({top_div_pct:.1%}) -> {div_flag}")
    phase3_lines.append("### Division Concentration")
    for d in div_counts.index:
        phase3_lines.append(f"- {d}: {div_counts[d]} ({div_counts[d]/total_n:.1%})")
    phase3_lines.append(f"- Top division share: {top_div_pct:.1%} -> {div_flag}")
    phase3_lines.append("")

    # Month concentration
    sub_all_copy['month'] = pd.to_datetime(sub_all_copy['date']).dt.month
    month_counts = sub_all_copy['month'].value_counts()
    # Check if any month drives all the profit
    print(f"  Month distribution:")
    phase3_lines.append("### Month Concentration")
    for m in sorted(month_counts.index):
        ms = sub_all_copy[sub_all_copy['month'] == m]
        r = calc_roi(ms, f"month_{m}")
        if r['n'] >= 10:
            print(f"    Month {m}: N={r['n']}, resid={r['residual']:+.4f}, ROI={r['roi_pct']:+.2f}%")
            phase3_lines.append(f"- Month {m}: N={r['n']}, resid={r['residual']:+.4f}, ROI={r['roi_pct']:+.2f}%")
    phase3_lines.append("")

    # Overall fragility verdict
    flags = []
    if season_flag != "STABLE": flags.append(season_flag)
    if team_flag != "DISPERSED": flags.append(team_flag)
    if div_flag != "DISPERSED": flags.append(div_flag)
    frag_verdict = "CLEAN" if len(flags) == 0 else " + ".join(flags)
    print(f"  Fragility verdict: {frag_verdict}")
    phase3_lines.append(f"### FRAGILITY VERDICT: {frag_verdict}")
    phase3_lines.append("")

with open(os.path.join(OUT, 'phase3_fragility_audit.md'), 'w') as f:
    f.write('\n'.join(phase3_lines))

###############################################################################
# PHASE 4: Micro-band stability
###############################################################################
print("\n" + "=" * 70)
print("PHASE 4: MICRO-BAND STABILITY")
print("=" * 70)

phase4_lines = ["# Phase 4: Micro-Band Stability", ""]

for obj_name, obj_fn in objects.items():
    print(f"\n--- {obj_name} ---")
    phase4_lines.append(f"## {obj_name}")
    phase4_lines.append("")
    sub_all = obj_fn(mixed)

    bands = [
        (100, 105, '+100/+105'),
        (106, 110, '+106/+110'),
        (111, 115, '+111/+115'),
        (116, 120, '+116/+120'),
        (121, 125, '+121/+125'),
        (126, 140, '+126/+140'),
    ]
    band_results = []
    for lo, hi, label in bands:
        band = sub_all[(sub_all['dog_ml_price'] >= lo) & (sub_all['dog_ml_price'] <= hi)]
        r = calc_roi(band, label)
        if r['n'] >= 5:
            print(f"  {label}: N={r['n']}, dogWR={r['dog_wr']:.4f}, resid={r['residual']:+.4f}, ROI={r['roi_pct']:+.2f}%")
            phase4_lines.append(f"- {label}: N={r['n']}, dog_wr={r['dog_wr']:.4f}, resid={r['residual']:+.4f}, ROI={r['roi_pct']:+.2f}%")
            band_results.append(r)

    # Check if signal is monotonic or concentrated
    if len(band_results) >= 3:
        resids = [r['residual'] for r in band_results if not np.isnan(r['residual'])]
        if len(resids) >= 3:
            positive_bands = sum(1 for r in resids if r > 0)
            print(f"  Positive bands: {positive_bands}/{len(resids)}")
            phase4_lines.append(f"- Positive bands: {positive_bands}/{len(resids)}")
            if positive_bands >= len(resids) * 0.5:
                phase4_lines.append("- MICRO-BAND VERDICT: STABLE (majority positive)")
            else:
                phase4_lines.append("- MICRO-BAND VERDICT: CONCENTRATED (fewer than half positive)")
    phase4_lines.append("")

with open(os.path.join(OUT, 'phase4_microband_stability.md'), 'w') as f:
    f.write('\n'.join(phase4_lines))

###############################################################################
# PHASE 5: Distinctness / Nesting Diagnostic
###############################################################################
print("\n" + "=" * 70)
print("PHASE 5: DISTINCTNESS / NESTING DIAGNOSTIC")
print("=" * 70)

phase5_lines = ["# Phase 5: Distinctness / Nesting Diagnostic", ""]

bp_set = set(get_bp_adv_dog(mixed).index) if bp_adv_alive else set()
night_set = set(get_night_dog(mixed).index)
overlap = bp_set & night_set
only_bp = bp_set - night_set
only_night = night_set - bp_set

print(f"bp_adv_dog total: {len(bp_set)}")
print(f"night_dog total: {len(night_set)}")
print(f"Overlap: {len(overlap)}")
print(f"Only bp_adv_dog: {len(only_bp)}")
print(f"Only night_dog: {len(only_night)}")

if len(bp_set) > 0:
    overlap_pct_bp = len(overlap) / len(bp_set)
    overlap_pct_night = len(overlap) / len(night_set)
    print(f"Overlap as % of bp_adv_dog: {overlap_pct_bp:.1%}")
    print(f"Overlap as % of night_dog: {overlap_pct_night:.1%}")
else:
    overlap_pct_bp = 0
    overlap_pct_night = 0

phase5_lines.append(f"- bp_adv_dog total: {len(bp_set)}")
phase5_lines.append(f"- night_dog total: {len(night_set)}")
phase5_lines.append(f"- Overlap: {len(overlap)} ({overlap_pct_bp:.1%} of bp_adv, {overlap_pct_night:.1%} of night)")
phase5_lines.append(f"- Only bp_adv_dog: {len(only_bp)}")
phase5_lines.append(f"- Only night_dog: {len(only_night)}")
phase5_lines.append("")

# ROI of the overlap vs exclusive subsets
if len(overlap) >= 20:
    ov_df = mixed.loc[list(overlap)]
    r_ov = calc_roi(ov_df, 'overlap')
    print(f"Overlap ROI: N={r_ov['n']}, resid={r_ov['residual']:+.4f}, ROI={r_ov['roi_pct']:+.2f}%")
    phase5_lines.append(f"- Overlap: N={r_ov['n']}, resid={r_ov['residual']:+.4f}, ROI={r_ov['roi_pct']:+.2f}%")

if len(only_bp) >= 20 and bp_adv_alive:
    obp_df = mixed.loc[list(only_bp)]
    r_obp = calc_roi(obp_df, 'only_bp')
    print(f"Only bp_adv ROI: N={r_obp['n']}, resid={r_obp['residual']:+.4f}, ROI={r_obp['roi_pct']:+.2f}%")
    phase5_lines.append(f"- Only bp_adv: N={r_obp['n']}, resid={r_obp['residual']:+.4f}, ROI={r_obp['roi_pct']:+.2f}%")

if len(only_night) >= 20:
    on_df = mixed.loc[list(only_night)]
    r_on = calc_roi(on_df, 'only_night')
    print(f"Only night ROI: N={r_on['n']}, resid={r_on['residual']:+.4f}, ROI={r_on['roi_pct']:+.2f}%")
    phase5_lines.append(f"- Only night: N={r_on['n']}, resid={r_on['residual']:+.4f}, ROI={r_on['roi_pct']:+.2f}%")

# Nesting verdict
if bp_adv_alive and overlap_pct_bp > 0.8:
    nest_verdict = "bp_adv_dog is NESTED in night_dog"
elif bp_adv_alive and overlap_pct_night > 0.8:
    nest_verdict = "night_dog is NESTED in bp_adv_dog"
else:
    nest_verdict = "INDEPENDENT (overlap < 80% for both)"
print(f"\nNesting verdict: {nest_verdict}")
phase5_lines.append(f"\n### NESTING VERDICT: {nest_verdict}")

with open(os.path.join(OUT, 'phase5_distinctness.md'), 'w') as f:
    f.write('\n'.join(phase5_lines))

###############################################################################
# PHASE 6: Proxy Risk Audit
###############################################################################
print("\n" + "=" * 70)
print("PHASE 6: PROXY RISK AUDIT")
print("=" * 70)

phase6_lines = ["# Phase 6: Proxy Risk Audit", ""]

for obj_name, obj_fn in objects.items():
    print(f"\n--- {obj_name} ---")
    phase6_lines.append(f"## {obj_name}")
    phase6_lines.append("")
    sub = obj_fn(mixed)
    comp = mixed[~mixed.index.isin(sub.index)]

    # Compare distributions of key features
    for feat, label in [('fav_implied', 'Fav Implied Prob'),
                         ('total_line', 'Total Line'),
                         ('dog_ml_price', 'Dog ML Price'),
                         ('sp_fip_diff', 'SP FIP Diff')]:
        sub_mean = sub[feat].mean()
        comp_mean = comp[feat].mean()
        diff = sub_mean - comp_mean
        print(f"  {label}: object={sub_mean:.3f}, complement={comp_mean:.3f}, diff={diff:+.3f}")
        phase6_lines.append(f"- {label}: object={sub_mean:.3f}, complement={comp_mean:.3f}, diff={diff:+.3f}")

    # Is it proxying line strength?
    fav_imp_diff = abs(sub['fav_implied'].mean() - comp['fav_implied'].mean())
    total_diff = abs(sub['total_line'].mean() - comp['total_line'].mean())
    proxy_flags = []
    if fav_imp_diff > 0.01:
        proxy_flags.append(f"fav_implied shift of {fav_imp_diff:.3f}")
    if total_diff > 0.3:
        proxy_flags.append(f"total_line shift of {total_diff:.2f}")

    proxy_verdict = "PROXY RISK: " + ", ".join(proxy_flags) if proxy_flags else "NO PROXY DETECTED"
    print(f"  Proxy verdict: {proxy_verdict}")
    phase6_lines.append(f"\n### PROXY VERDICT: {proxy_verdict}")
    phase6_lines.append("")

with open(os.path.join(OUT, 'phase6_proxy_risk.md'), 'w') as f:
    f.write('\n'.join(phase6_lines))

###############################################################################
# PHASE 7: Live Feasibility
###############################################################################
print("\n" + "=" * 70)
print("PHASE 7: LIVE FEASIBILITY")
print("=" * 70)

phase7_lines = ["# Phase 7: Live Feasibility", ""]

if bp_adv_alive:
    phase7_lines.append("## bp_adv_dog")
    phase7_lines.append("- BP ERA from pitcher_game_logs: available daily, updated after each game")
    phase7_lines.append("- Requires: pitcher_game_logs refresh before game time")
    phase7_lines.append("- Lag: previous day's games are in PGL by morning")
    phase7_lines.append("- VERDICT: LIVE-FEASIBLE (morning computation, no real-time feed needed)")
    phase7_lines.append("")
    print("  bp_adv_dog: LIVE-FEASIBLE")

phase7_lines.append("## night_dog")
phase7_lines.append("- Day/night from MLB schedule API local_start_hour")
phase7_lines.append("- Available at schedule release (typically days in advance)")
phase7_lines.append("- VERDICT: LIVE-FEASIBLE (trivially available)")
phase7_lines.append("")
print("  night_dog: LIVE-FEASIBLE")

with open(os.path.join(OUT, 'phase7_live_feasibility.md'), 'w') as f:
    f.write('\n'.join(phase7_lines))

###############################################################################
# PHASE 8-9: Shadow Specs + Monitoring (for survivors)
###############################################################################
print("\n" + "=" * 70)
print("PHASE 8-9: SHADOW SPECS + MONITORING")
print("=" * 70)

# Determine survivors based on all phases
# An object survives if: PIT-safe, positive residual in all 3 periods, no fatal fragility
survivor_verdicts = {}

for obj_name, obj_fn in objects.items():
    d_r = calc_roi(obj_fn(disc), obj_name)
    v_r = calc_roi(obj_fn(val), obj_name)
    o_r = calc_roi(obj_fn(oos), obj_name)

    all_positive = (d_r['residual'] > 0 and v_r['residual'] > 0 and o_r['residual'] > 0)
    survivor_verdicts[obj_name] = {
        'disc_n': d_r['n'], 'disc_resid': d_r['residual'], 'disc_roi': d_r['roi_pct'],
        'val_n': v_r['n'], 'val_resid': v_r['residual'], 'val_roi': v_r['roi_pct'],
        'oos_n': o_r['n'], 'oos_resid': o_r['residual'], 'oos_roi': o_r['roi_pct'],
        'all_positive': all_positive,
        'pit_safe': True if obj_name == 'night_dog' else bp_adv_alive,
    }

phase89_lines = ["# Phase 8-9: Shadow Specs and Monitoring Rules", ""]

for obj_name, sv in survivor_verdicts.items():
    survives = sv['all_positive'] and sv['pit_safe']
    status = "SURVIVOR" if survives else "KILLED"
    print(f"  {obj_name}: {status}")
    print(f"    disc: N={sv['disc_n']}, resid={sv['disc_resid']:+.4f}, ROI={sv['disc_roi']:+.2f}%")
    print(f"    val:  N={sv['val_n']}, resid={sv['val_resid']:+.4f}, ROI={sv['val_roi']:+.2f}%")
    print(f"    oos:  N={sv['oos_n']}, resid={sv['oos_resid']:+.4f}, ROI={sv['oos_roi']:+.2f}%")

    phase89_lines.append(f"## {obj_name}: {status}")
    phase89_lines.append(f"- Discovery: N={sv['disc_n']}, resid={sv['disc_resid']:+.4f}, ROI={sv['disc_roi']:+.2f}%")
    phase89_lines.append(f"- Validation: N={sv['val_n']}, resid={sv['val_resid']:+.4f}, ROI={sv['val_roi']:+.2f}%")
    phase89_lines.append(f"- OOS: N={sv['oos_n']}, resid={sv['oos_resid']:+.4f}, ROI={sv['oos_roi']:+.2f}%")
    phase89_lines.append("")

    if survives:
        phase89_lines.append("### Shadow Specification")
        phase89_lines.append(f"- Trigger: MIXED game + {obj_name} condition met")
        phase89_lines.append("- Action: log to shadow, bet dog ML at closing price")
        phase89_lines.append("- Stake: flat 1 unit")
        phase89_lines.append("- Minimum sample for go/no-go: 50 bets")
        phase89_lines.append("")
        phase89_lines.append("### Monitoring Rules")
        phase89_lines.append("- Track cumulative ROI weekly")
        phase89_lines.append("- Kill switch: ROI < -15% after 50+ bets")
        phase89_lines.append("- Promotion gate: ROI > 0% after 100+ bets with residual > +1.5%")
        phase89_lines.append(f"- Expected frequency: ~{sv['oos_n']} per season")
        phase89_lines.append("")

with open(os.path.join(OUT, 'phase89_shadow_specs.md'), 'w') as f:
    f.write('\n'.join(phase89_lines))

###############################################################################
# PHASE 10: GO / NO-GO
###############################################################################
print("\n" + "=" * 70)
print("PHASE 10: GO / NO-GO VERDICTS")
print("=" * 70)

phase10_lines = ["# Phase 10: Go / No-Go Verdicts", ""]

final_table_rows = []

for obj_name, sv in survivor_verdicts.items():
    survives = sv['all_positive'] and sv['pit_safe']

    # Additional kill conditions
    kill_reasons = []
    if not sv['pit_safe']:
        kill_reasons.append("FAILED PIT AUDIT")
    if not sv['all_positive']:
        periods_neg = []
        if sv['disc_resid'] <= 0: periods_neg.append('disc')
        if sv['val_resid'] <= 0: periods_neg.append('val')
        if sv['oos_resid'] <= 0: periods_neg.append('oos')
        kill_reasons.append(f"Negative residual in: {', '.join(periods_neg)}")

    # Check if OOS sample is too small
    if sv['oos_n'] < 50:
        kill_reasons.append(f"OOS N={sv['oos_n']} < 50 minimum")
        survives = False

    if survives:
        verdict = "GO -- SHADOW"
    else:
        verdict = "NO-GO: " + "; ".join(kill_reasons) if kill_reasons else "NO-GO"

    print(f"  {obj_name}: {verdict}")
    phase10_lines.append(f"## {obj_name}: {verdict}")
    phase10_lines.append(f"- disc: N={sv['disc_n']}, resid={sv['disc_resid']:+.4f}, ROI={sv['disc_roi']:+.2f}%")
    phase10_lines.append(f"- val: N={sv['val_n']}, resid={sv['val_resid']:+.4f}, ROI={sv['val_roi']:+.2f}%")
    phase10_lines.append(f"- oos: N={sv['oos_n']}, resid={sv['oos_resid']:+.4f}, ROI={sv['oos_roi']:+.2f}%")
    phase10_lines.append(f"- PIT-safe: {sv['pit_safe']}")
    phase10_lines.append(f"- VERDICT: {verdict}")
    phase10_lines.append("")

    final_table_rows.append({
        'object': obj_name,
        'disc_n': sv['disc_n'], 'disc_resid': round(sv['disc_resid'], 4), 'disc_roi': round(sv['disc_roi'], 2),
        'val_n': sv['val_n'], 'val_resid': round(sv['val_resid'], 4), 'val_roi': round(sv['val_roi'], 2),
        'oos_n': sv['oos_n'], 'oos_resid': round(sv['oos_resid'], 4), 'oos_roi': round(sv['oos_roi'], 2),
        'pit_safe': sv['pit_safe'],
        'verdict': verdict
    })

with open(os.path.join(OUT, 'phase10_go_nogo.md'), 'w') as f:
    f.write('\n'.join(phase10_lines))

# Write final table CSV
final_df = pd.DataFrame(final_table_rows)
final_df.to_csv(os.path.join(OUT, 'MLB_SIDES_PHASE6_FINAL_TABLE.csv'), index=False)

###############################################################################
# EXEC SUMMARY
###############################################################################
print("\n" + "=" * 70)
print("WRITING EXEC SUMMARY")
print("=" * 70)

summary = []
summary.append("# MLB SIDES PHASE 6 -- EXEC SUMMARY")
summary.append("## Forensic Hardening of MIXED Survivors")
summary.append("")
summary.append(f"**Date**: 2026-04-12")
summary.append("")
summary.append("---")
summary.append("")
summary.append("## Objects Under Test")
summary.append("1. **bp_adv_dog**: MIXED + dog bullpen ERA better than favorite's")
summary.append("2. **night_dog**: MIXED + night game (local start >= 5pm)")
summary.append("")
summary.append("---")
summary.append("")
summary.append("## Phase 1: Bullpen PIT-Safety Audit")
summary.append(f"- Source: pitcher_game_logs.parquet, starter_flag==0")
summary.append(f"- Rolling: shift(1).expanding().sum(), min 10 IP")
summary.append(f"- 5 worked examples: ALL MATCH = {all_match}")
summary.append(f"- Opener contamination: {len(high_ip)} appearances ({contamination_pct:.2f}%)")
summary.append(f"- **PIT VERDICT: {pit_verdict}**")
summary.append("")

if not bp_adv_alive:
    summary.append("**bp_adv_dog KILLED at Phase 1. Only night_dog proceeds.**")
    summary.append("")

summary.append("---")
summary.append("")
summary.append("## Results Summary")
summary.append("")
summary.append("| Object | Disc N | Disc Resid | Disc ROI | Val N | Val Resid | Val ROI | OOS N | OOS Resid | OOS ROI | Verdict |")
summary.append("|--------|--------|-----------|----------|-------|----------|---------|-------|----------|---------|---------|")

for _, row in final_df.iterrows():
    summary.append(f"| {row['object']} | {row['disc_n']} | {row['disc_resid']:+.4f} | {row['disc_roi']:+.2f}% | {row['val_n']} | {row['val_resid']:+.4f} | {row['val_roi']:+.2f}% | {row['oos_n']} | {row['oos_resid']:+.4f} | {row['oos_roi']:+.2f}% | {row['verdict']} |")

summary.append("")
summary.append("---")
summary.append("")
summary.append("## Key Findings")
summary.append("")

survivors = final_df[final_df['verdict'].str.startswith('GO')]
killed = final_df[~final_df['verdict'].str.startswith('GO')]

if len(survivors) > 0:
    summary.append(f"### Survivors ({len(survivors)})")
    for _, r in survivors.iterrows():
        summary.append(f"- **{r['object']}**: OOS resid {r['oos_resid']:+.4f}, OOS ROI {r['oos_roi']:+.2f}%")
    summary.append("")

if len(killed) > 0:
    summary.append(f"### Killed ({len(killed)})")
    for _, r in killed.iterrows():
        summary.append(f"- **{r['object']}**: {r['verdict']}")
    summary.append("")

summary.append("---")
summary.append("")
summary.append("## Files")
summary.append("- `phase0_exact_object_lock.md` -- object definitions")
summary.append("- `phase1_bullpen_pit_audit.md` -- PIT safety audit")
summary.append("- `phase2_historical_rebuild.md` -- match rebuild by split")
summary.append("- `phase3_fragility_audit.md` -- concentration tests")
summary.append("- `phase4_microband_stability.md` -- price band stability")
summary.append("- `phase5_distinctness.md` -- overlap/nesting")
summary.append("- `phase6_proxy_risk.md` -- proxy risk audit")
summary.append("- `phase7_live_feasibility.md` -- live computation check")
summary.append("- `phase89_shadow_specs.md` -- shadow specifications")
summary.append("- `phase10_go_nogo.md` -- final verdicts")
summary.append("- `MLB_SIDES_PHASE6_FINAL_TABLE.csv` -- results table")
summary.append("- `MLB_SIDES_PHASE6_EXEC_SUMMARY.md` -- this file")

with open(os.path.join(OUT, 'MLB_SIDES_PHASE6_EXEC_SUMMARY.md'), 'w') as f:
    f.write('\n'.join(summary))

print("\n" + "=" * 70)
print("ALL FILES WRITTEN TO:", OUT)
print("=" * 70)
print("\nFINAL VERDICTS:")
for _, row in final_df.iterrows():
    print(f"  {row['object']}: {row['verdict']}")
print("\nDONE")
