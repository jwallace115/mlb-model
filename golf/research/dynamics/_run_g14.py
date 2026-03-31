import pandas as pd
import numpy as np
import json
import os
import warnings
warnings.filterwarnings('ignore')

os.chdir("/Users/jw115/mlb-model")
os.makedirs("golf/research/dynamics", exist_ok=True)

# ================================================================
# STEP 1 — LOAD DATA
# ================================================================
print("=" * 70)
print("STEP 1 — Load Data")
print("=" * 70)

rounds = pd.read_parquet("golf/data/canonical/player_rounds.parquet")
results = pd.read_parquet("golf/data/canonical/tournament_results.parquet")
pred = pd.read_parquet("golf/data/canonical/predictions.parquet")
odds = pd.read_parquet("golf/data/canonical/odds_outrights.parquet")
events = pd.read_parquet("golf/data/canonical/events.parquet")

pred = pred.rename(columns={'win_prob':'dg_win_prob','top_5_prob':'dg_top_5_prob',
                             'top_10_prob':'dg_top_10_prob','top_20_prob':'dg_top_20_prob',
                             'make_cut_prob':'dg_make_cut_prob'})

# Event ordering
event_order = events[['event_id','calendar_year']].drop_duplicates()
if 'start_date' in events.columns:
    event_order = events[['event_id','calendar_year','start_date']].drop_duplicates()
    event_order['start_date'] = pd.to_datetime(event_order['start_date'])
    event_order = event_order.sort_values('start_date')
else:
    event_order = event_order.sort_values(['calendar_year','event_id'])
event_order['event_seq'] = range(len(event_order))

rounds_seq = rounds.merge(event_order[['event_id','calendar_year','event_seq']],
                           on=['event_id','calendar_year'], how='left')
rounds_seq = rounds_seq.sort_values(['dg_id','event_seq','round_num'])

# Pre-compute field percentiles for tail_balance
round_pctiles = {}
for (eid, yr, rnd), grp in rounds_seq.groupby(['event_id','calendar_year','round_num']):
    sg_vals = grp['sg_total'].dropna()
    if len(sg_vals) >= 20:
        round_pctiles[(eid, yr, rnd)] = {'p10': sg_vals.quantile(0.10), 'p90': sg_vals.quantile(0.90)}

# Build player-events
player_events = pred[['event_id','calendar_year','dg_id']].drop_duplicates().merge(
    event_order[['event_id','calendar_year','event_seq']], on=['event_id','calendar_year'], how='left')
player_events = player_events.merge(
    results[['event_id','calendar_year','dg_id','made_cut','top_5','top_10','top_20','winner']],
    on=['event_id','calendar_year','dg_id'], how='left')
player_events = player_events.merge(
    pred[['event_id','calendar_year','dg_id','dg_make_cut_prob','dg_top_20_prob',
          'dg_top_10_prob','dg_top_5_prob','dg_win_prob']],
    on=['event_id','calendar_year','dg_id'], how='left')

# Compute tail_balance_50 and rolling_mean_sg_50 for each player-event
print("Computing tail_balance features...")
feat_data = []
players = player_events['dg_id'].unique()

for i, pid in enumerate(players):
    p_rounds = rounds_seq[rounds_seq['dg_id'] == pid].sort_values(['event_seq','round_num'])
    p_events = player_events[player_events['dg_id'] == pid].sort_values('event_seq')

    for _, ev in p_events.iterrows():
        this_seq = ev['event_seq']
        prior = p_rounds[p_rounds['event_seq'] < this_seq]
        sg_vals = prior['sg_total'].dropna().values

        if len(sg_vals) < 20:
            continue

        last50 = sg_vals[-50:]
        rolling_mean = np.mean(last50)
        rolling_std = np.std(last50, ddof=1) if len(last50) > 1 else 0.01

        # Field-relative top/bottom decile rates
        top_count = bottom_count = checked = 0
        for _, rr in prior.tail(50).iterrows():
            sg = rr.get('sg_total')
            if pd.isna(sg): continue
            key = (rr['event_id'], rr['calendar_year'], rr.get('round_num'))
            pcts = round_pctiles.get(key)
            if pcts is None: continue
            checked += 1
            if sg >= pcts['p90']: top_count += 1
            if sg <= pcts['p10']: bottom_count += 1

        if checked >= 10:
            top_rate = top_count / checked
            bottom_rate = bottom_count / checked
            tail_balance = top_rate - bottom_rate
        else:
            tail_balance = np.nan

        feat_data.append({
            'event_id': ev['event_id'], 'calendar_year': ev['calendar_year'], 'dg_id': pid,
            'rolling_mean_sg_50': rolling_mean, 'rolling_std_sg_50': rolling_std,
            'tail_balance_50': tail_balance,
            'top_decile_rate_50': top_rate if checked >= 10 else np.nan,
            'bottom_decile_rate_50': bottom_rate if checked >= 10 else np.nan,
        })

    if (i+1) % 300 == 0:
        print(f"  {i+1}/{len(players)} players...", flush=True)

fdf = pd.DataFrame(feat_data)
df = fdf.merge(player_events, on=['event_id','calendar_year','dg_id'], how='inner')

df['split'] = 'train'
df.loc[df['calendar_year'] == 2023, 'split'] = 'validate'
df.loc[df['calendar_year'].isin([2024,2025]), 'split'] = 'oos'

tb_cov = df['tail_balance_50'].notna().mean()*100
print(f"Dataset: {len(df)} rows")
print(f"tail_balance_50 coverage: {tb_cov:.1f}%")
print(f"Splits: {df['split'].value_counts().to_dict()}")

# ================================================================
# STEP 2 — FREEZE TAIL BALANCE BUCKETS
# ================================================================
print("\n" + "=" * 70)
print("STEP 2 — Freeze Buckets")
print("=" * 70)

train = df[df['split'] == 'train']

# Skill bands
q25 = train['rolling_mean_sg_50'].quantile(0.25)
q50 = train['rolling_mean_sg_50'].quantile(0.50)
q75 = train['rolling_mean_sg_50'].quantile(0.75)

def skill_band(sg):
    if sg >= q75: return 'Elite'
    if sg >= q50: return 'Good'
    if sg >= q25: return 'Average'
    return 'Below'

df['skill_band'] = df['rolling_mean_sg_50'].apply(skill_band)

# Tail balance terciles within each skill band
tb_thresholds = {}
for band in ['Elite','Good','Average','Below']:
    bt = train[train['rolling_mean_sg_50'].apply(skill_band) == band]['tail_balance_50'].dropna()
    t33 = bt.quantile(0.333)
    t67 = bt.quantile(0.667)
    tb_thresholds[band] = (float(t33), float(t67))
    n = len(bt)
    print(f"  {band}: LOW<{t33:.4f}, MED {t33:.4f}-{t67:.4f}, HIGH>={t67:.4f} (N={n})")

# Pooled version
pooled_tb = train['tail_balance_50'].dropna()
pooled_t33 = float(pooled_tb.quantile(0.333))
pooled_t67 = float(pooled_tb.quantile(0.667))
print(f"  POOLED: LOW<{pooled_t33:.4f}, HIGH>={pooled_t67:.4f}")

def assign_tb_bucket(row):
    band = row['skill_band']
    val = row['tail_balance_50']
    if pd.isna(val): return 'MEDIUM'
    t33, t67 = tb_thresholds[band]
    if val >= t67: return 'HIGH'
    if val >= t33: return 'MEDIUM'
    return 'LOW'

def assign_tb_pooled(val):
    if pd.isna(val): return 'MEDIUM'
    if val >= pooled_t67: return 'HIGH'
    if val >= pooled_t33: return 'MEDIUM'
    return 'LOW'

df['tb_bucket'] = df.apply(assign_tb_bucket, axis=1)
df['tb_pooled'] = df['tail_balance_50'].apply(assign_tb_pooled)

# Refresh train after adding new columns
train = df[df['split'] == 'train']

# ================================================================
# STEP 3 — FROZEN UPLIFTS
# ================================================================
print("\n" + "=" * 70)
print("STEP 3 — Frozen Uplifts")
print("=" * 70)

uplift_data = {}
print(f"{'band':>8s} | {'bucket':>6s} | {'N':>5s} | {'t10_up':>8s} | {'t5_up':>8s} | {'win_up':>8s}")
print("-" * 55)

for band in ['Elite','Good','Average','Below']:
    uplift_data[band] = {}
    for bucket in ['LOW','MEDIUM','HIGH']:
        sub = train[(train['skill_band']==band) & (train['tb_bucket']==bucket)]
        n = len(sub)

        obs_t10 = sub['top_10'].mean() if n > 0 else 0
        obs_t5 = sub['top_5'].mean() if n > 0 else 0
        obs_win = sub['winner'].mean() if n > 0 else 0

        exp_t10 = sub['dg_top_10_prob'].mean() if n > 0 else 0
        exp_t5 = sub['dg_top_5_prob'].mean() if n > 0 else 0
        exp_win = sub['dg_win_prob'].mean() if n > 0 else 0

        t10_up = obs_t10 - exp_t10
        t5_up = obs_t5 - exp_t5
        win_up = obs_win - exp_win

        uplift_data[band][bucket] = {
            'top_10_uplift': round(t10_up, 5),
            'top_5_uplift': round(t5_up, 5),
            'win_uplift': round(win_up, 5),
            'n_train': n,
        }
        print(f"{band:>8s} | {bucket:>6s} | {n:5d} | {t10_up:>+7.4f} | {t5_up:>+7.4f} | {win_up:>+7.5f}")

# Save frozen uplifts
frozen = {
    'skill_band_cutpoints': {'q25': q25, 'q50': q50, 'q75': q75},
    'tb_thresholds_by_band': tb_thresholds,
    'tb_thresholds_pooled': {'t33': pooled_t33, 't67': pooled_t67},
    'uplifts': uplift_data,
}
with open("golf/research/dynamics/g14_frozen_tail_uplifts.json", "w") as f:
    json.dump(frozen, f, indent=2)
print("\nSaved g14_frozen_tail_uplifts.json")

# ================================================================
# STEP 4 — ADJUSTED PROBABILITIES
# ================================================================
print("\n" + "=" * 70)
print("STEP 4 — Adjusted Probabilities")
print("=" * 70)

def get_uplift(band, bucket, market):
    key = {'top_10': 'top_10_uplift', 'top_5': 'top_5_uplift', 'win': 'win_uplift'}[market]
    return uplift_data.get(band, {}).get(bucket, {}).get(key, 0)

for mkt in ['top_10','top_5','win']:
    dg_col = f'dg_{mkt}_prob'
    adj_col = f'adj_{mkt}_prob'
    df[adj_col] = df.apply(lambda r: np.clip(r[dg_col] + get_uplift(r['skill_band'], r['tb_bucket'], mkt), 0.01, 0.99), axis=1)

# Join odds with book priority
def american_to_implied(o):
    if pd.isna(o) or o == 0: return np.nan
    return 100/(o+100) if o > 0 else abs(o)/(abs(o)+100)

BOOK_PRIORITY = ['pinnacle','draftkings','fanduel']

for market in ['top_10','top_5','win']:
    mkt_odds = odds[odds['market'] == market]
    selected = []
    for (eid,yr,dgid), grp in mkt_odds.groupby(['event_id','calendar_year','dg_id']):
        for bk in BOOK_PRIORITY:
            row = grp[grp['book'] == bk]
            if len(row) > 0: selected.append(row.iloc[0]); break
    if not selected: continue
    sel_df = pd.DataFrame(selected)[['event_id','calendar_year','dg_id','close_odds',
                                      'fair_close_prob','book','open_odds']]
    sel_df.columns = ['event_id','calendar_year','dg_id',
                      f'{market}_close_odds', f'{market}_fair_close', f'{market}_book', f'{market}_open_odds']
    df = df.merge(sel_df, on=['event_id','calendar_year','dg_id'], how='left')

# Compute edges
for mkt in ['top_10','top_5','win']:
    fair_col = f'{mkt}_fair_close'
    df[f'baseline_{mkt}_edge'] = df[f'dg_{mkt}_prob'] - df[fair_col]
    df[f'overlay_{mkt}_edge'] = df[f'adj_{mkt}_prob'] - df[fair_col]

print("Adjusted probabilities computed.")
for mkt in ['top_10','top_5','win']:
    fair_col = f'{mkt}_fair_close'
    coverage = df[fair_col].notna().mean() * 100
    print(f"  {mkt} odds coverage: {coverage:.1f}%")

# ================================================================
# STEP 5 — BASELINE VS OVERLAY BACKTEST
# ================================================================
print("\n" + "=" * 70)
print("STEP 5 — Baseline vs Overlay")
print("=" * 70)

def compute_roi(sub, result_col, odds_col):
    valid = sub[sub[result_col].notna() & sub[odds_col].notna()]
    if len(valid) == 0: return 0, 0, 0
    wins = valid[valid[result_col] == 1]
    losses = valid[valid[result_col] == 0]
    n = len(valid)
    pay = sum(r[odds_col]/100 if r[odds_col] > 0 else 100/abs(r[odds_col]) for _, r in wins.iterrows())
    return n, len(wins)/n if n > 0 else 0, (pay-len(losses))/n*100

def compute_clv(sub, open_col, close_col):
    valid = sub[[open_col, close_col]].dropna()
    if len(valid) == 0: return np.nan, 0
    open_imp = valid[open_col].apply(american_to_implied)
    close_imp = valid[close_col].apply(american_to_implied)
    clv = (open_imp - close_imp).mean()
    return clv, len(valid)

MARKETS = {
    'top_10': {'result': 'top_10', 'odds': 'top_10_close_odds', 'open': 'top_10_open_odds'},
    'top_5': {'result': 'top_5', 'odds': 'top_5_close_odds', 'open': 'top_5_open_odds'},
    'win': {'result': 'winner', 'odds': 'win_close_odds', 'open': 'win_open_odds'},
}

THRESHOLDS = [0.02, 0.04, 0.06, 0.08]

for mkt, cfg in MARKETS.items():
    print(f"\n### {mkt.upper()} ###")
    hdr = f"{'strategy':>10s} | {'thresh':>6s} | {'split':>5s} | {'N':>5s} | {'hit':>6s} | {'ROI':>7s} | {'CLV':>8s}"
    print(hdr)
    print("-" * 60)

    for thresh in THRESHOLDS:
        for split in ['train','validate','oos']:
            s = df[df['split'] == split]

            # Baseline
            base = s[s[f'baseline_{mkt}_edge'] >= thresh]
            n_b, hr_b, roi_b = compute_roi(base, cfg['result'], cfg['odds'])
            clv_b, _ = compute_clv(base, cfg['open'], cfg['odds'])
            clv_b_s = f"{clv_b*100:+.1f}%" if not np.isnan(clv_b) else "N/A"

            # Overlay
            over = s[(s[f'overlay_{mkt}_edge'] >= thresh) & (s['tb_bucket'] == 'HIGH')]
            n_o, hr_o, roi_o = compute_roi(over, cfg['result'], cfg['odds'])
            clv_o, _ = compute_clv(over, cfg['open'], cfg['odds'])
            clv_o_s = f"{clv_o*100:+.1f}%" if not np.isnan(clv_o) else "N/A"

            print(f"{'Baseline':>10s} | {thresh:>5.0%} | {split:>5s} | {n_b:5d} | {hr_b:>5.1%} | {roi_b:>+6.1f}% | {clv_b_s:>8s}")
            print(f"{'Overlay':>10s} | {thresh:>5.0%} | {split:>5s} | {n_o:5d} | {hr_o:>5.1%} | {roi_o:>+6.1f}% | {clv_o_s:>8s}")

# ---- FIELD STRENGTH ROBUSTNESS ----
print("\n### FIELD STRENGTH ROBUSTNESS (OOS) ###")

# Compute field strength: mean DG win_prob of top 30 in field
field_str = df.groupby(['event_id','calendar_year']).apply(
    lambda g: g.nlargest(30, 'dg_win_prob')['dg_win_prob'].mean()
).reset_index()
field_str.columns = ['event_id','calendar_year','field_strength']
df = df.merge(field_str, on=['event_id','calendar_year'], how='left')

# Freeze threshold on training
fs_median = train.merge(field_str, on=['event_id','calendar_year'], how='left')['field_strength'].median()
print(f"Field strength threshold (median, frozen): {fs_median:.4f}")

df['field_type'] = np.where(df['field_strength'] >= fs_median, 'strong', 'weak')

oos = df[df['split'] == 'oos']
for mkt, cfg in MARKETS.items():
    # Use best threshold (0.04 as default)
    thresh = 0.04
    over = oos[(oos[f'overlay_{mkt}_edge'] >= thresh) & (oos['tb_bucket'] == 'HIGH')]

    for ft in ['strong','weak']:
        sub = over[over['field_type'] == ft]
        n, hr, roi = compute_roi(sub, cfg['result'], cfg['odds'])
        print(f"  {mkt} | {ft:>6s} field | N={n:4d} | hit={hr:.1%} | ROI={roi:+.1f}%")

# ================================================================
# STEP 6 — YEARLY STABILITY
# ================================================================
print("\n" + "=" * 70)
print("STEP 6 — Yearly Stability")
print("=" * 70)

yearly_data = {}
for mkt, cfg in MARKETS.items():
    thresh = 0.04  # primary threshold
    yearly_data[mkt] = []
    print(f"\n### {mkt.upper()} overlay (edge >= 4%, HIGH tb) ###")
    hdr2 = f"{'year':>4s} | {'N':>5s} | {'hit':>6s} | {'ROI':>7s}"
    print(hdr2)
    print("-" * 28)

    pos_years = 0
    total_years = 0
    for yr in sorted(df['calendar_year'].unique()):
        sub = df[(df['calendar_year'] == yr) & (df[f'overlay_{mkt}_edge'] >= thresh) & (df['tb_bucket'] == 'HIGH')]
        n, hr, roi = compute_roi(sub, cfg['result'], cfg['odds'])
        yearly_data[mkt].append({'year': int(yr), 'n': n, 'hr': hr, 'roi': roi})
        if n > 0:
            total_years += 1
            if roi > 0: pos_years += 1
        print(f"{int(yr):4d} | {n:5d} | {hr:>5.1%} | {roi:>+6.1f}%")

    print(f"Positive years: {pos_years}/{total_years}")

# ================================================================
# STEP 7 — DEPLOYMENT GATE
# ================================================================
print("\n" + "=" * 70)
print("STEP 7 — Deployment Gate")
print("=" * 70)

N_GATES = {'top_10': 75, 'top_5': 50, 'win': 25}
verdicts = {}

for mkt, cfg in MARKETS.items():
    best_verdict = "G14_INSUFFICIENT_EDGE"
    best_result = None

    for thresh in [0.02, 0.04, 0.06, 0.08]:
        oos_over = oos[(oos[f'overlay_{mkt}_edge'] >= thresh) & (oos['tb_bucket'] == 'HIGH')]
        n_o, hr_o, roi_o = compute_roi(oos_over, cfg['result'], cfg['odds'])
        clv_o, _ = compute_clv(oos_over, cfg['open'], cfg['odds'])

        # Baseline comparison
        oos_base = oos[oos[f'baseline_{mkt}_edge'] >= thresh]
        _, _, roi_b = compute_roi(oos_base, cfg['result'], cfg['odds'])

        # Yearly stability
        pos_yrs = 0
        total_yrs = 0
        for yr in df['calendar_year'].unique():
            yr_sub = df[(df['calendar_year'] == yr) & (df[f'overlay_{mkt}_edge'] >= thresh) & (df['tb_bucket'] == 'HIGH')]
            _, _, yr_roi = compute_roi(yr_sub, cfg['result'], cfg['odds'])
            if len(yr_sub) > 0:
                total_yrs += 1
                if yr_roi > 0: pos_yrs += 1

        gate_roi = roi_o >= 4.0
        gate_clv = (not np.isnan(clv_o)) and clv_o > 0
        gate_n = n_o >= N_GATES[mkt]
        gate_beats = roi_o > roi_b
        gate_stable = pos_yrs >= 3

        all_pass = gate_roi and gate_n and gate_beats and gate_stable

        status = "PASS" if all_pass else "FAIL"
        clv_str = "%.1f%%" % (clv_o*100) if not np.isnan(clv_o) else "N/A"
        print(f"\n  {mkt} @ {thresh:.0%}: N={n_o}, hit={hr_o:.1%}, ROI={roi_o:+.1f}%, "
              f"CLV={clv_str}, "
              f"base={roi_b:+.1f}%, stable={pos_yrs}/{total_yrs} -> {status}")
        y_roi = 'Y' if gate_roi else 'N'
        y_n = 'Y' if gate_n else 'N'
        y_beats = 'Y' if gate_beats else 'N'
        y_stable = 'Y' if gate_stable else 'N'
        y_clv = 'Y' if gate_clv else 'N'
        print(f"    Gates: ROI>=4%={y_roi} | N>={N_GATES[mkt]}={y_n} | "
              f"beats={y_beats} | stable={y_stable} | CLV>0={y_clv}")

        if all_pass and best_verdict != "G14_DEPLOYABLE":
            best_verdict = "G14_DEPLOYABLE"
            best_result = {'threshold': thresh, 'n': n_o, 'hr': hr_o, 'roi': roi_o,
                          'clv': clv_o, 'stability': f"{pos_yrs}/{total_yrs}"}
        elif gate_roi and n_o >= N_GATES[mkt] // 2 and best_verdict == "G14_INSUFFICIENT_EDGE":
            best_verdict = "G14_WATCHLIST"
            best_result = {'threshold': thresh, 'n': n_o, 'hr': hr_o, 'roi': roi_o}

    verdicts[mkt] = best_verdict
    print(f"\n  {mkt} VERDICT: {best_verdict}")

# ================================================================
# STEP 8 — OUTPUT REPORT
# ================================================================
print("\n" + "=" * 70)
print("STEP 8 — Final Report")
print("=" * 70)

report = f"""# G14 Tail Balance Overlay Validation

Generated: {pd.Timestamp.now().isoformat()[:19]}

## Dataset
- Player-events: {len(df):,} (2020-2025)
- tail_balance_50 coverage: {df['tail_balance_50'].notna().mean()*100:.1f}%
- Splits: train={len(df[df['split']=='train'])}, validate={len(df[df['split']=='validate'])}, oos={len(df[df['split']=='oos'])}

## Frozen Cutpoints (2020-2022)
### Skill Bands
- Below: SG < {q25:.3f}
- Average: {q25:.3f} to {q50:.3f}
- Good: {q50:.3f} to {q75:.3f}
- Elite: >= {q75:.3f}

### Tail Balance Terciles by Band
"""
for band in ['Elite','Good','Average','Below']:
    t33, t67 = tb_thresholds[band]
    report += f"- {band}: LOW<{t33:.4f}, HIGH>={t67:.4f}\n"

report += """
## Frozen Uplift Table (Training 2020-2022)

| Band | Bucket | N | T10 Uplift | T5 Uplift | Win Uplift |
|------|--------|---|------------|-----------|------------|
"""
for band in ['Elite','Good','Average','Below']:
    for bucket in ['LOW','MEDIUM','HIGH']:
        u = uplift_data[band][bucket]
        report += f"| {band} | {bucket} | {u['n_train']} | {u['top_10_uplift']:+.4f} | {u['top_5_uplift']:+.4f} | {u['win_uplift']:+.5f} |\n"

report += """
## Baseline vs Overlay (OOS 2024-2025)

| Market | Strategy | Threshold | N | Hit Rate | ROI | CLV |
|--------|----------|-----------|---|----------|-----|-----|
"""
for mkt, cfg in MARKETS.items():
    for thresh in [0.04, 0.06]:
        oos_d = df[df['split'] == 'oos']
        base = oos_d[oos_d[f'baseline_{mkt}_edge'] >= thresh]
        over = oos_d[(oos_d[f'overlay_{mkt}_edge'] >= thresh) & (oos_d['tb_bucket'] == 'HIGH')]
        n_b, hr_b, roi_b = compute_roi(base, cfg['result'], cfg['odds'])
        n_o, hr_o, roi_o = compute_roi(over, cfg['result'], cfg['odds'])
        clv_b, _ = compute_clv(base, cfg['open'], cfg['odds'])
        clv_o, _ = compute_clv(over, cfg['open'], cfg['odds'])
        clv_b_s = f"{clv_b*100:+.1f}%" if not np.isnan(clv_b) else "N/A"
        clv_o_s = f"{clv_o*100:+.1f}%" if not np.isnan(clv_o) else "N/A"
        report += f"| {mkt} | Baseline | {thresh:.0%} | {n_b} | {hr_b:.1%} | {roi_b:+.1f}% | {clv_b_s} |\n"
        report += f"| {mkt} | Overlay | {thresh:.0%} | {n_o} | {hr_o:.1%} | {roi_o:+.1f}% | {clv_o_s} |\n"

report += """
## Field Strength Robustness (OOS, edge >= 4%)

| Market | Field | N | Hit Rate | ROI |
|--------|-------|---|----------|-----|
"""
for mkt, cfg in MARKETS.items():
    over = oos[(oos[f'overlay_{mkt}_edge'] >= 0.04) & (oos['tb_bucket'] == 'HIGH')]
    for ft in ['strong','weak']:
        sub = over[over['field_type'] == ft]
        n, hr, roi = compute_roi(sub, cfg['result'], cfg['odds'])
        report += f"| {mkt} | {ft} | {n} | {hr:.1%} | {roi:+.1f}% |\n"

report += """
## Yearly Stability

"""
for mkt in ['top_10','top_5','win']:
    report += f"### {mkt.upper()} (edge >= 4%, HIGH tb)\n"
    report += "| Year | N | Hit Rate | ROI |\n|------|---|----------|-----|\n"
    for yd in yearly_data[mkt]:
        report += f"| {yd['year']} | {yd['n']} | {yd['hr']:.1%} | {yd['roi']:+.1f}% |\n"
    report += "\n"

report += f"""## Final Verdict

| Market | Verdict |
|--------|---------|
| Top 10 | {verdicts.get('top_10', 'N/A')} |
| Top 5 | {verdicts.get('top_5', 'N/A')} |
| Win | {verdicts.get('win', 'N/A')} |
"""

with open("golf/research/dynamics/g14_tail_overlay_validation.md", "w") as f:
    f.write(report)

print(report)
print(f"\nOutput files:")
print(f"  golf/research/dynamics/g14_frozen_tail_uplifts.json")
print(f"  golf/research/dynamics/g14_tail_overlay_validation.md")
