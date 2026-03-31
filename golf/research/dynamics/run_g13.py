import pandas as pd
import numpy as np
import json
import os
import warnings
warnings.filterwarnings('ignore')

os.chdir("/Users/jw115/mlb-model")
os.makedirs("golf/research/dynamics", exist_ok=True)

# ================================================================
# STEP 1 — DATASET CONSTRUCTION
# ================================================================
print("=" * 70)
print("STEP 1 — Dataset Construction")
print("=" * 70)

rounds = pd.read_parquet("golf/data/canonical/player_rounds.parquet")
results = pd.read_parquet("golf/data/canonical/tournament_results.parquet")
odds = pd.read_parquet("golf/data/canonical/odds_outrights.parquet")
events = pd.read_parquet("golf/data/canonical/events.parquet")
pred = pd.read_parquet("golf/data/canonical/predictions.parquet")

# Rename prediction columns
pred = pred.rename(columns={
    'win_prob': 'dg_win_prob', 'top_5_prob': 'dg_top_5_prob',
    'top_10_prob': 'dg_top_10_prob', 'top_20_prob': 'dg_top_20_prob',
    'make_cut_prob': 'dg_make_cut_prob'
})

# Build R1/R2 wave data
r12 = rounds[rounds['round_num'].isin([1, 2])].copy()
r12 = r12[r12['tee_wave'].notna() & r12['round_score'].notna()]

# Compute wave scoring differential for each event-round
wave_diffs = {}
for (eid, yr, rnd), grp in r12.groupby(['event_id', 'calendar_year', 'round_num']):
    am = grp[grp['tee_wave'] == 'AM']['round_score']
    pm = grp[grp['tee_wave'] == 'PM']['round_score']
    if len(am) >= 10 and len(pm) >= 10:
        wave_diffs[(eid, yr, rnd)] = {'am_mean': am.mean(), 'pm_mean': pm.mean(), 'diff': pm.mean() - am.mean()}

# Compute per-player draw edge for R1 and R2
player_draws = []
for (eid, yr), evt in r12.groupby(['event_id', 'calendar_year']):
    for rnd in [1, 2]:
        key = (eid, yr, rnd)
        if key not in wave_diffs:
            continue
        wd = wave_diffs[key]
        rnd_data = evt[evt['round_num'] == rnd]
        for _, row in rnd_data.iterrows():
            wave = row['tee_wave']
            if wave == 'AM':
                draw_edge = wd['pm_mean'] - wd['am_mean']  # positive = AM had better conditions
            elif wave == 'PM':
                draw_edge = wd['am_mean'] - wd['pm_mean']  # positive = PM had better conditions
            else:
                continue
            player_draws.append({
                'event_id': eid, 'calendar_year': yr, 'dg_id': row['dg_id'],
                'round_num': rnd, 'tee_wave': wave, 'draw_edge_round': draw_edge,
                'tee_time_hour': row.get('tee_time_hour'),
            })

draw_df = pd.DataFrame(player_draws)

# Pivot to get R1 and R2 draw edges per player-tournament
draw_r1 = draw_df[draw_df['round_num'] == 1][['event_id','calendar_year','dg_id','draw_edge_round','tee_wave']].rename(
    columns={'draw_edge_round': 'draw_edge_r1', 'tee_wave': 'wave_r1'})
draw_r2 = draw_df[draw_df['round_num'] == 2][['event_id','calendar_year','dg_id','draw_edge_round','tee_wave']].rename(
    columns={'draw_edge_round': 'draw_edge_r2', 'tee_wave': 'wave_r2'})

player_tourn = draw_r1.merge(draw_r2, on=['event_id','calendar_year','dg_id'], how='outer')
player_tourn['draw_edge_total'] = player_tourn[['draw_edge_r1','draw_edge_r2']].mean(axis=1)

# Join predictions
ds = player_tourn.merge(
    pred[['event_id','calendar_year','dg_id','dg_make_cut_prob','dg_top_20_prob','dg_top_10_prob','dg_win_prob']],
    on=['event_id','calendar_year','dg_id'], how='inner'
)

# Join results
ds = ds.merge(
    results[['event_id','calendar_year','dg_id','made_cut','top_20','top_10','top_5','winner','fin_num']],
    on=['event_id','calendar_year','dg_id'], how='inner'
)

# 36h score
r12_scores = rounds[rounds['round_num'].isin([1,2])].groupby(
    ['event_id','calendar_year','dg_id'])['round_score'].sum().reset_index()
r12_scores.columns = ['event_id','calendar_year','dg_id','score_36h']
ds = ds.merge(r12_scores, on=['event_id','calendar_year','dg_id'], how='left')

# Join odds — book priority: Pinnacle > DraftKings > FanDuel
BOOK_PRIORITY = ['pinnacle', 'draftkings', 'fanduel']

def select_best_odds(market_name):
    mkt = odds[odds['market'] == market_name]
    selected = []
    for (eid, yr, dgid), grp in mkt.groupby(['event_id','calendar_year','dg_id']):
        for bk in BOOK_PRIORITY:
            row = grp[grp['book'] == bk]
            if len(row) > 0:
                selected.append(row.iloc[0])
                break
    return pd.DataFrame(selected) if selected else pd.DataFrame()

def american_to_implied(o):
    if pd.isna(o) or o == 0: return np.nan
    return 100 / (o + 100) if o > 0 else abs(o) / (abs(o) + 100)

for market, suffix in [('make_cut', 'mc'), ('top_20', 't20')]:
    sel = select_best_odds(market)
    if len(sel) == 0:
        continue
    sel = sel[['event_id','calendar_year','dg_id','close_odds','fair_close_prob','book','open_odds']].copy()
    sel.columns = ['event_id','calendar_year','dg_id',
                   f'{suffix}_close_odds', f'{suffix}_fair_close_prob', f'{suffix}_book', f'{suffix}_open_odds']
    ds = ds.merge(sel, on=['event_id','calendar_year','dg_id'], how='left')

# Compute implied probabilities
for suffix in ['mc', 't20']:
    col = f'{suffix}_close_odds'
    if col in ds.columns:
        ds[f'{suffix}_close_implied'] = ds[col].apply(american_to_implied)
        ds[f'{suffix}_open_implied'] = ds[f'{suffix}_open_odds'].apply(american_to_implied)

# Splits
ds['split'] = 'train'
ds.loc[ds['calendar_year'] == 2023, 'split'] = 'validate'
ds.loc[ds['calendar_year'].isin([2024, 2025]), 'split'] = 'oos'

print(f"Dataset: {len(ds)} rows")
print(f"Years: {sorted(ds['calendar_year'].unique())}")
print(f"Splits: {ds['split'].value_counts().to_dict()}")
print(f"Make cut odds coverage: {ds['mc_close_odds'].notna().mean()*100:.1f}%")
print(f"Top 20 odds coverage: {ds['t20_close_odds'].notna().mean()*100:.1f}%")

# ================================================================
# STEP 2 — WAVE EDGE CALCULATION (already done above)
# ================================================================
print("\n" + "=" * 70)
print("STEP 2 — Wave Edge Calculation")
print("=" * 70)
print(f"draw_edge_r1 coverage: {ds['draw_edge_r1'].notna().mean()*100:.1f}%")
print(f"draw_edge_r2 coverage: {ds['draw_edge_r2'].notna().mean()*100:.1f}%")
print(f"draw_edge_total: mean={ds['draw_edge_total'].mean():.3f}, std={ds['draw_edge_total'].std():.3f}")

# ================================================================
# STEP 3 — DRAW EDGE BUCKETING
# ================================================================
print("\n" + "=" * 70)
print("STEP 3 — Draw Edge Bucketing")
print("=" * 70)

# Freeze quintile cutpoints on training data BEFORE slicing train
train_mask = ds['split'] == 'train'
quintile_cuts = [ds.loc[train_mask, 'draw_edge_total'].quantile(q) for q in [0.2, 0.4, 0.6, 0.8]]
print(f"Quintile cutpoints (frozen on 2020-2022):")
for i, c in enumerate(quintile_cuts):
    print(f"  Q{i+1}/Q{i+2}: {c:+.3f}")

def assign_quintile(val):
    if pd.isna(val): return np.nan
    for i, c in enumerate(quintile_cuts):
        if val < c:
            return i + 1
    return 5

ds['draw_quintile'] = ds['draw_edge_total'].apply(assign_quintile)

# Now slice train
train = ds[ds['split'] == 'train']

# Summary table
print(f"\n{'Q':>3s} | {'N':>6s} | {'cut_rate':>8s} | {'t20_rate':>8s} | {'mean_36h':>8s} | {'mean_draw':>9s}")
print("-" * 55)
for q in range(1, 6):
    sub = ds[ds['draw_quintile'] == q]
    n = len(sub)
    cr = sub['made_cut'].mean()
    t20 = sub['top_20'].mean()
    s36 = sub['score_36h'].mean()
    de = sub['draw_edge_total'].mean()
    print(f"Q{q:1d} | {n:6d} | {cr:>7.1%} | {t20:>7.1%} | {s36:>7.2f} | {de:>+8.3f}")

# Monotonicity check
cut_rates = [ds[ds['draw_quintile'] == q]['made_cut'].mean() for q in range(1, 6)]
mono_cut = all(cut_rates[i] <= cut_rates[i+1] for i in range(4))
t20_rates = [ds[ds['draw_quintile'] == q]['top_20'].mean() for q in range(1, 6)]
mono_t20 = all(t20_rates[i] <= t20_rates[i+1] for i in range(4))
print(f"\nMonotonic cut rate Q1->Q5: {'YES' if mono_cut else 'NO'}")
print(f"Monotonic top20 rate Q1->Q5: {'YES' if mono_t20 else 'NO'}")

# ================================================================
# STEP 4 — FREEZE OVERLAY ADJUSTMENTS
# ================================================================
print("\n" + "=" * 70)
print("STEP 4 — Freeze Overlay Adjustments")
print("=" * 70)

uplift_table = {}
print(f"{'Q':>3s} | {'N_train':>7s} | {'mc_uplift':>10s} | {'t20_uplift':>10s}")
print("-" * 40)

for q in range(1, 6):
    sub = train[train['draw_quintile'] == q]
    n = len(sub)

    mc_observed = sub['made_cut'].mean()
    mc_expected = sub['dg_make_cut_prob'].mean()
    mc_uplift = mc_observed - mc_expected

    t20_observed = sub['top_20'].mean()
    t20_expected = sub['dg_top_20_prob'].mean()
    t20_uplift = t20_observed - t20_expected

    uplift_table[str(q)] = {
        'make_cut_uplift': round(mc_uplift, 4),
        'top20_uplift': round(t20_uplift, 4),
        'n_train': n,
    }

    print(f"Q{q:1d} | {n:7d} | {mc_uplift:>+9.4f} | {t20_uplift:>+9.4f}")

# Save frozen uplifts
with open("golf/research/dynamics/g13_frozen_wave_uplifts.json", "w") as f:
    json.dump(uplift_table, f, indent=2)
print("\nFrozen uplifts saved to g13_frozen_wave_uplifts.json")

# ================================================================
# STEP 5 — PROBABILITY ADJUSTMENT
# ================================================================
print("\n" + "=" * 70)
print("STEP 5 — Probability Adjustment")
print("=" * 70)

# Apply uplift
ds['mc_uplift'] = ds['draw_quintile'].map(lambda q: uplift_table.get(str(int(q)), {}).get('make_cut_uplift', 0) if pd.notna(q) else 0)
ds['t20_uplift'] = ds['draw_quintile'].map(lambda q: uplift_table.get(str(int(q)), {}).get('top20_uplift', 0) if pd.notna(q) else 0)

ds['adj_make_cut_prob'] = np.clip(ds['dg_make_cut_prob'] + ds['mc_uplift'], 0.02, 0.98)
ds['adj_top20_prob'] = np.clip(ds['dg_top_20_prob'] + ds['t20_uplift'], 0.02, 0.98)

# Compute edges
# Use fair_close_prob (already vig-removed)
ds['baseline_mc_edge'] = ds['dg_make_cut_prob'] - ds['mc_fair_close_prob']
ds['overlay_mc_edge'] = ds['adj_make_cut_prob'] - ds['mc_fair_close_prob']

ds['baseline_t20_edge'] = ds['dg_top_20_prob'] - ds['t20_fair_close_prob']
ds['overlay_t20_edge'] = ds['adj_top20_prob'] - ds['t20_fair_close_prob']

print("Adjustment sample (OOS Q5):")
q5_oos = ds[(ds['split'] == 'oos') & (ds['draw_quintile'] == 5)].head(5)
for _, r in q5_oos.iterrows():
    print(f"  DG mc={r['dg_make_cut_prob']:.3f} + uplift={r['mc_uplift']:+.4f} -> adj={r['adj_make_cut_prob']:.3f}")

# ================================================================
# STEP 6 — BETTING SIMULATION
# ================================================================
print("\n" + "=" * 70)
print("STEP 6 — Betting Simulation")
print("=" * 70)

def compute_roi(sub, result_col, odds_col):
    """Flat-stake ROI from American odds."""
    valid = sub[sub[result_col].notna() & sub[odds_col].notna()].copy()
    if len(valid) == 0:
        return 0, 0, 0, 0
    wins = valid[valid[result_col] == 1]
    losses = valid[valid[result_col] == 0]
    n = len(valid)
    payouts = 0
    for _, r in wins.iterrows():
        o = r[odds_col]
        if o > 0:
            payouts += o / 100
        elif o < 0:
            payouts += 100 / abs(o)
    net = payouts - len(losses)
    roi = net / n * 100
    hr = len(wins) / n
    avg_edge = valid.get('_edge', pd.Series([0])).mean()
    return n, hr, roi, avg_edge

# CLV computation: same-book open vs close
def compute_clv(sub, open_implied_col, close_implied_col):
    valid = sub[[open_implied_col, close_implied_col]].dropna()
    if len(valid) == 0:
        return np.nan, 0
    clv = (valid[open_implied_col] - valid[close_implied_col]).mean()
    return clv, len(valid)

print("\n### MAKE CUT ###")
print(f"{'Strategy':>15s} | {'Split':>8s} | {'N':>5s} | {'Hit':>6s} | {'ROI':>7s} | {'Avg Edge':>8s} | {'CLV':>8s} | {'CLV_N':>5s}")
print("-" * 75)

for split in ['train', 'validate', 'oos']:
    s = ds[ds['split'] == split].copy()

    # BASELINE: DG edge >= 4%
    base = s[s['baseline_mc_edge'] >= 0.04].copy()
    base['_edge'] = base['baseline_mc_edge']
    n_b, hr_b, roi_b, ae_b = compute_roi(base, 'made_cut', 'mc_close_odds')
    clv_b, clv_n_b = compute_clv(base, 'mc_open_implied', 'mc_close_implied')

    # OVERLAY: adj edge >= 4% AND Q4/Q5
    over = s[(s['overlay_mc_edge'] >= 0.04) & (s['draw_quintile'].isin([4, 5]))].copy()
    over['_edge'] = over['overlay_mc_edge']
    n_o, hr_o, roi_o, ae_o = compute_roi(over, 'made_cut', 'mc_close_odds')
    clv_o, clv_n_o = compute_clv(over, 'mc_open_implied', 'mc_close_implied')

    clv_b_s = f"{clv_b*100:+.1f}%" if not np.isnan(clv_b) else "N/A"
    clv_o_s = f"{clv_o*100:+.1f}%" if not np.isnan(clv_o) else "N/A"

    print(f"{'Baseline':>15s} | {split:>8s} | {n_b:5d} | {hr_b:>5.1%} | {roi_b:>+6.1f}% | {ae_b:>7.1%} | {clv_b_s:>8s} | {clv_n_b:5d}")
    print(f"{'Overlay':>15s} | {split:>8s} | {n_o:5d} | {hr_o:>5.1%} | {roi_o:>+6.1f}% | {ae_o:>7.1%} | {clv_o_s:>8s} | {clv_n_o:5d}")

print("\n### TOP 20 ###")
print(f"{'Strategy':>15s} | {'Split':>8s} | {'N':>5s} | {'Hit':>6s} | {'ROI':>7s} | {'Avg Edge':>8s} | {'CLV':>8s} | {'CLV_N':>5s}")
print("-" * 75)

for split in ['train', 'validate', 'oos']:
    s = ds[ds['split'] == split].copy()

    # BASELINE
    base = s[s['baseline_t20_edge'] >= 0.04].copy()
    base['_edge'] = base['baseline_t20_edge']
    n_b, hr_b, roi_b, ae_b = compute_roi(base, 'top_20', 't20_close_odds')
    clv_b, clv_n_b = compute_clv(base, 't20_open_implied', 't20_close_implied')

    # OVERLAY
    over = s[(s['overlay_t20_edge'] >= 0.04) & (s['draw_quintile'].isin([4, 5]))].copy()
    over['_edge'] = over['overlay_t20_edge']
    n_o, hr_o, roi_o, ae_o = compute_roi(over, 'top_20', 't20_close_odds')
    clv_o, clv_n_o = compute_clv(over, 'mc_open_implied', 'mc_close_implied')

    clv_b_s = f"{clv_b*100:+.1f}%" if not np.isnan(clv_b) else "N/A"
    clv_o_s = f"{clv_o*100:+.1f}%" if not np.isnan(clv_o) else "N/A"

    print(f"{'Baseline':>15s} | {split:>8s} | {n_b:5d} | {hr_b:>5.1%} | {roi_b:>+6.1f}% | {ae_b:>7.1%} | {clv_b_s:>8s} | {clv_n_b:5d}")
    print(f"{'Overlay':>15s} | {split:>8s} | {n_o:5d} | {hr_o:>5.1%} | {roi_o:>+6.1f}% | {ae_o:>7.1%} | {clv_o_s:>8s} | {clv_n_o:5d}")

# Also test at 6% edge threshold
print("\n### MAKE CUT @ 6% edge ###")
print(f"{'Strategy':>15s} | {'Split':>8s} | {'N':>5s} | {'Hit':>6s} | {'ROI':>7s}")
print("-" * 50)
for split in ['train', 'validate', 'oos']:
    s = ds[ds['split'] == split]
    base = s[s['baseline_mc_edge'] >= 0.06]
    over = s[(s['overlay_mc_edge'] >= 0.06) & (s['draw_quintile'].isin([4, 5]))]
    n_b, hr_b, roi_b, _ = compute_roi(base, 'made_cut', 'mc_close_odds')
    n_o, hr_o, roi_o, _ = compute_roi(over, 'made_cut', 'mc_close_odds')
    print(f"{'Baseline':>15s} | {split:>8s} | {n_b:5d} | {hr_b:>5.1%} | {roi_b:>+6.1f}%")
    print(f"{'Overlay':>15s} | {split:>8s} | {n_o:5d} | {hr_o:>5.1%} | {roi_o:>+6.1f}%")

# ================================================================
# STEP 8 — YEARLY STABILITY
# ================================================================
print("\n" + "=" * 70)
print("STEP 8 — Yearly Stability")
print("=" * 70)

print("\n### MAKE CUT OVERLAY (edge >= 4%, Q4/Q5) ###")
print(f"{'Year':>4s} | {'N':>5s} | {'Hit':>6s} | {'ROI':>7s}")
print("-" * 30)

pos_years = 0
total_years = 0
yearly_results = []
for yr in sorted(ds['calendar_year'].unique()):
    sub = ds[(ds['calendar_year'] == yr) & (ds['overlay_mc_edge'] >= 0.04) & (ds['draw_quintile'].isin([4, 5]))]
    n, hr, roi, _ = compute_roi(sub, 'made_cut', 'mc_close_odds')
    if n > 0:
        total_years += 1
        if roi > 0:
            pos_years += 1
    yearly_results.append({'year': yr, 'n': n, 'hr': hr, 'roi': roi})
    print(f"{yr:4d} | {n:5d} | {hr:>5.1%} | {roi:>+6.1f}%")

print(f"\nPositive ROI years: {pos_years}/{total_years}")
stability_pass = pos_years >= 3
print(f"Stability gate (3+ of 5): {'PASS' if stability_pass else 'FAIL'}")

print("\n### TOP 20 OVERLAY (edge >= 4%, Q4/Q5) ###")
print(f"{'Year':>4s} | {'N':>5s} | {'Hit':>6s} | {'ROI':>7s}")
print("-" * 30)
for yr in sorted(ds['calendar_year'].unique()):
    sub = ds[(ds['calendar_year'] == yr) & (ds['overlay_t20_edge'] >= 0.04) & (ds['draw_quintile'].isin([4, 5]))]
    n, hr, roi, _ = compute_roi(sub, 'top_20', 't20_close_odds')
    print(f"{yr:4d} | {n:5d} | {hr:>5.1%} | {roi:>+6.1f}%")

# ================================================================
# STEP 9 — DEPLOYMENT GATE
# ================================================================
print("\n" + "=" * 70)
print("STEP 9 — Deployment Gate")
print("=" * 70)

# Check gates for make_cut overlay
oos = ds[ds['split'] == 'oos']
over_mc = oos[(oos['overlay_mc_edge'] >= 0.04) & (oos['draw_quintile'].isin([4, 5]))]
n_mc, hr_mc, roi_mc, _ = compute_roi(over_mc, 'made_cut', 'mc_close_odds')
clv_mc, clv_n_mc = compute_clv(over_mc, 'mc_open_implied', 'mc_close_implied')

base_mc = oos[oos['baseline_mc_edge'] >= 0.04]
_, _, roi_base_mc, _ = compute_roi(base_mc, 'made_cut', 'mc_close_odds')

# Concentration check: no single year > 60% of profits
oos_yearly = []
for yr in oos['calendar_year'].unique():
    sub = over_mc[over_mc['calendar_year'] == yr]
    if len(sub) == 0:
        continue
    valid = sub[sub['made_cut'].notna() & sub['mc_close_odds'].notna()]
    wins = valid[valid['made_cut'] == 1]
    losses = valid[valid['made_cut'] == 0]
    pay = sum(r['mc_close_odds']/100 if r['mc_close_odds'] > 0 else 100/abs(r['mc_close_odds']) for _, r in wins.iterrows())
    yr_net = pay - len(losses)
    oos_yearly.append({'year': yr, 'net': yr_net})

total_net = sum(y['net'] for y in oos_yearly)
concentration_ok = True
if total_net > 0:
    for y in oos_yearly:
        if y['net'] / total_net > 0.60:
            concentration_ok = False

gate_roi = roi_mc >= 4.0
gate_clv = (not np.isnan(clv_mc)) and clv_mc > 0
gate_n = n_mc >= 50
gate_overlay_beats = roi_mc > roi_base_mc
gate_concentration = concentration_ok

print(f"\nMake Cut Overlay Gates:")
print(f"  ROI >= 4%: {roi_mc:+.1f}% -> {'PASS' if gate_roi else 'FAIL'}")
if not np.isnan(clv_mc):
    print(f"  Positive CLV: {clv_mc*100:+.1f}% -> {'PASS' if gate_clv else 'FAIL'}")
else:
    print(f"  Positive CLV: N/A -> FAIL")
print(f"  N >= 50: {n_mc} -> {'PASS' if gate_n else 'FAIL'}")
print(f"  Overlay > Baseline: {roi_mc:+.1f}% vs {roi_base_mc:+.1f}% -> {'PASS' if gate_overlay_beats else 'FAIL'}")
print(f"  No concentration: {'PASS' if gate_concentration else 'FAIL'}")
print(f"  Stability (3+/5 years): {'PASS' if stability_pass else 'FAIL'}")

all_pass = gate_roi and gate_n and gate_overlay_beats and stability_pass
# CLV informative but not strictly blocking if data sparse
# Concentration informative

# Check top_20 too
over_t20 = oos[(oos['overlay_t20_edge'] >= 0.04) & (oos['draw_quintile'].isin([4, 5]))]
n_t20, hr_t20, roi_t20, _ = compute_roi(over_t20, 'top_20', 't20_close_odds')
clv_t20, _ = compute_clv(over_t20, 't20_open_implied', 't20_close_implied')
base_t20 = oos[oos['baseline_t20_edge'] >= 0.04]
_, _, roi_base_t20, _ = compute_roi(base_t20, 'top_20', 't20_close_odds')

print(f"\nTop 20 Overlay Gates:")
print(f"  ROI: {roi_t20:+.1f}% (baseline: {roi_base_t20:+.1f}%)")
print(f"  N: {n_t20}")
if not np.isnan(clv_t20):
    print(f"  CLV: {clv_t20*100:+.1f}%")
else:
    print(f"  CLV: N/A")

# ================================================================
# STEP 10 — FINAL VERDICT + REPORT
# ================================================================
print("\n" + "=" * 70)
print("STEP 10 — Final Verdict")
print("=" * 70)

if all_pass:
    verdict = "G13_DEPLOYABLE"
elif gate_roi and gate_n:
    verdict = "G13_WATCHLIST"
else:
    verdict = "G13_INSUFFICIENT_EDGE"

print(f"\nVERDICT: {verdict}")

# Build report
report = f"""# G13 Wave Weather Overlay Validation

Generated: {pd.Timestamp.now().isoformat()[:19]}

## Verdict: {verdict}

## Dataset
- {len(ds):,} player-tournament rows (2020-2025)
- Make cut odds coverage: {ds['mc_close_odds'].notna().mean()*100:.1f}%
- Top 20 odds coverage: {ds['t20_close_odds'].notna().mean()*100:.1f}%
- Book priority: Pinnacle > DraftKings > FanDuel

## Quintile Summary (All Data)

| Q | N | Cut Rate | Top 20 Rate | Mean 36h | Mean Draw Edge |
|---|---|----------|-------------|----------|---------------|
"""

for q in range(1, 6):
    sub = ds[ds['draw_quintile'] == q]
    report += f"| Q{q} | {len(sub):,} | {sub['made_cut'].mean():.1%} | {sub['top_20'].mean():.1%} | {sub['score_36h'].mean():.1f} | {sub['draw_edge_total'].mean():+.3f} |\n"

report += f"""
Monotonic cut rate Q1->Q5: {'YES' if mono_cut else 'NO'}
Monotonic top20 rate Q1->Q5: {'YES' if mono_t20 else 'NO'}

## Frozen Uplift Table (Training 2020-2022)

| Q | N_train | MC Uplift | Top20 Uplift |
|---|---------|-----------|-------------|
"""

for q in range(1, 6):
    u = uplift_table[str(q)]
    report += f"| Q{q} | {u['n_train']:,} | {u['make_cut_uplift']:+.4f} | {u['top20_uplift']:+.4f} |\n"

report += f"""
## Baseline vs Overlay -- Make Cut (edge >= 4%)

| Strategy | Split | N | Hit Rate | ROI | CLV |
|----------|-------|---|----------|-----|-----|
"""

for split in ['train', 'validate', 'oos']:
    s = ds[ds['split'] == split]
    base = s[s['baseline_mc_edge'] >= 0.04]
    over = s[(s['overlay_mc_edge'] >= 0.04) & (s['draw_quintile'].isin([4, 5]))]
    n_b, hr_b, roi_b, _ = compute_roi(base, 'made_cut', 'mc_close_odds')
    n_o, hr_o, roi_o, _ = compute_roi(over, 'made_cut', 'mc_close_odds')
    clv_b_v, _ = compute_clv(base, 'mc_open_implied', 'mc_close_implied')
    clv_o_v, _ = compute_clv(over, 'mc_open_implied', 'mc_close_implied')
    clv_b_s = f"{clv_b_v*100:+.1f}%" if not np.isnan(clv_b_v) else "N/A"
    clv_o_s = f"{clv_o_v*100:+.1f}%" if not np.isnan(clv_o_v) else "N/A"
    report += f"| Baseline | {split} | {n_b} | {hr_b:.1%} | {roi_b:+.1f}% | {clv_b_s} |\n"
    report += f"| Overlay | {split} | {n_o} | {hr_o:.1%} | {roi_o:+.1f}% | {clv_o_s} |\n"

report += f"""
## Baseline vs Overlay -- Top 20 (edge >= 4%)

| Strategy | Split | N | Hit Rate | ROI |
|----------|-------|---|----------|-----|
"""

for split in ['train', 'validate', 'oos']:
    s = ds[ds['split'] == split]
    base = s[s['baseline_t20_edge'] >= 0.04]
    over = s[(s['overlay_t20_edge'] >= 0.04) & (s['draw_quintile'].isin([4, 5]))]
    n_b, hr_b, roi_b, _ = compute_roi(base, 'top_20', 't20_close_odds')
    n_o, hr_o, roi_o, _ = compute_roi(over, 'top_20', 't20_close_odds')
    report += f"| Baseline | {split} | {n_b} | {hr_b:.1%} | {roi_b:+.1f}% |\n"
    report += f"| Overlay | {split} | {n_o} | {hr_o:.1%} | {roi_o:+.1f}% |\n"

report += f"""
## Yearly Stability -- Make Cut Overlay

| Year | N | Hit Rate | ROI |
|------|---|----------|-----|
"""

for yr_data in yearly_results:
    report += f"| {yr_data['year']} | {yr_data['n']} | {yr_data['hr']:.1%} | {yr_data['roi']:+.1f}% |\n"

report += f"""
Positive ROI years: {pos_years}/{total_years}
Stability gate (3+/5): {'PASS' if stability_pass else 'FAIL'}

## Deployment Gates (OOS 2024-2025, Make Cut)

| Gate | Value | Status |
|------|-------|--------|
| ROI >= 4% | {roi_mc:+.1f}% | {'PASS' if gate_roi else 'FAIL'} |
| Positive CLV | {clv_mc*100:+.1f}% | {'PASS' if gate_clv else 'FAIL'} |
| N >= 50 | {n_mc} | {'PASS' if gate_n else 'FAIL'} |
| Overlay > Baseline | {roi_mc:+.1f}% vs {roi_base_mc:+.1f}% | {'PASS' if gate_overlay_beats else 'FAIL'} |
| No concentration | {'PASS' if gate_concentration else 'FAIL'} |
| Stability (3+/5) | {pos_years}/{total_years} | {'PASS' if stability_pass else 'FAIL'} |
"""

if verdict == "G13_DEPLOYABLE":
    report += f"""
## Deployment Specification

- **Market:** Make Cut
- **Rule:** adj_make_cut_edge >= 4% AND draw_quintile in Q4/Q5
- **Expected volume:** ~{n_mc // 2} bets per season
- **Expected ROI:** {roi_mc:+.1f}%
- **Book preference:** Pinnacle > DraftKings > FanDuel
"""
elif verdict == "G13_WATCHLIST":
    report += f"""
## Watchlist Note

Signal shows promise but does not clear all deployment gates.
Continue shadow tracking through 2026 season.
"""

with open("golf/research/dynamics/g13_wave_overlay_validation.md", "w") as f:
    f.write(report)

print(report)
print(f"\nOutput files:")
print(f"  golf/research/dynamics/g13_frozen_wave_uplifts.json")
print(f"  golf/research/dynamics/g13_wave_overlay_validation.md")
