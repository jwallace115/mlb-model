"""
Soccer V2.2c — Market Shrinkage Challenger
No retraining. No new calibrator. Just shrinkage on V2.2 outputs.
P_final = P_market + α * (P_model - P_market)
"""
import pandas as pd
import numpy as np
import json, os
from scipy.stats import spearmanr, norm
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss

# ================================================================
# LOAD DATA
# ================================================================
pred = pd.read_parquet('soccer/data/soccer_v2_2_predictions.parquet')
canon = pd.read_parquet('soccer/data/soccer_canonical.parquet')
odds = pd.read_parquet('soccer/data/odds_historical.parquet')

active = ['EPL', 'BUN', 'SEA', 'LG1']

def prepare(df):
    df = df.merge(canon[['game_id', 'over_price', 'under_price']], on='game_id', how='left')
    df = df.merge(odds[['game_id', 'market_fair_p_over_2_5']].rename(
        columns={'market_fair_p_over_2_5': 'mkt_p'}), on='game_id', how='left',
        suffixes=('', '_odds'))
    # Use the mkt_p from odds table; V2.2 predictions also have it
    if 'mkt_p' not in df.columns or df['mkt_p'].isna().all():
        df['mkt_p'] = df['market_fair_p_over_2_5']
    return df

val = pred[(pred['split'] == 'validate') & (pred['league_id'].isin(active))].copy()
oos = pred[(pred['split'] == 'oos') & (pred['league_id'].isin(active))].copy()
val = prepare(val)
oos = prepare(oos)

# Load raw book odds for multi-book ROI
raw_dfs = []
for lg in active:
    f = f'soccer/data/cache/fd_{lg}_2425.csv'
    if os.path.exists(f):
        df = pd.read_csv(f)
        df['league_id'] = lg
        raw_dfs.append(df)
raw_oos = pd.concat(raw_dfs, ignore_index=True)
raw_oos['Date_parsed'] = pd.to_datetime(raw_oos['Date'], dayfirst=True)

# Also load 2023-24 for validation
raw_val_dfs = []
for lg in active:
    f = f'soccer/data/cache/fd_{lg}_2324.csv'
    if os.path.exists(f):
        df = pd.read_csv(f)
        df['league_id'] = lg
        raw_val_dfs.append(df)
raw_val = pd.concat(raw_val_dfs, ignore_index=True) if raw_val_dfs else None
if raw_val is not None:
    raw_val['Date_parsed'] = pd.to_datetime(raw_val['Date'], dayfirst=True)


# ================================================================
# HELPER FUNCTIONS
# ================================================================
def apply_shrinkage(df, alpha):
    """P_final = P_market + alpha * (P_model - P_market)"""
    model_p = df['ridge_cal_p'].values
    market_p = df['market_fair_p_over_2_5'].values
    return np.clip(market_p + alpha * (model_p - market_p), 0.01, 0.99)


def merge_book_odds(signals_df, raw_df):
    """Merge Pinnacle and Max closing odds onto signals via date+league+scores."""
    sm = signals_df.merge(
        canon[['game_id', 'home_score', 'away_score']],
        on='game_id', how='left')
    sm['game_date_dt'] = pd.to_datetime(sm['game_date'])
    raw_slim = raw_df[['Date_parsed', 'league_id', 'FTHG', 'FTAG',
                        'B365C>2.5', 'B365C<2.5', 'PC>2.5', 'PC<2.5',
                        'MaxC>2.5', 'MaxC<2.5']].copy()
    merged = sm.merge(raw_slim,
                      left_on=['game_date_dt', 'league_id', 'home_score', 'away_score'],
                      right_on=['Date_parsed', 'league_id', 'FTHG', 'FTAG'],
                      how='left')
    merged = merged.drop_duplicates(subset='game_id', keep='first')
    return merged


def full_diagnostics(df, label, alpha, raw_book_df=None):
    """Run all four diagnostics. Returns dict of key metrics."""
    cal_p = df['v2_2c_p'].values
    actual = df['actual_over_2_5'].values
    market_p = df['market_fair_p_over_2_5'].values

    # Edge and market error
    edge = cal_p - market_p
    market_error = actual - market_p

    # Signal assignment
    signal_side = np.where(edge > 0, 'OVER', 'UNDER')
    abs_edge = np.abs(edge)
    is_bet = abs_edge >= 0.06
    win = np.where(signal_side == 'OVER', actual == 1, actual == 0).astype(int)

    # Tiers
    tier = np.where(abs_edge >= 0.10, 'HIGH',
           np.where(abs_edge >= 0.08, 'MEDIUM',
           np.where(abs_edge >= 0.06, 'LOW', 'NO_BET')))

    df = df.copy()
    df['edge'] = edge
    df['abs_edge'] = abs_edge
    df['signal_side'] = signal_side
    df['win'] = win
    df['tier'] = tier

    bets = df[df['tier'] != 'NO_BET'].copy()

    # Merge book odds if available
    if raw_book_df is not None:
        bets = merge_book_odds(bets, raw_book_df)
        bets['b365_odds'] = np.where(bets['signal_side'] == 'OVER',
                                      bets['B365C>2.5'], bets['B365C<2.5'])
        bets['pin_odds'] = np.where(bets['signal_side'] == 'OVER',
                                     bets['PC>2.5'], bets['PC<2.5'])
        bets['max_odds'] = np.where(bets['signal_side'] == 'OVER',
                                     bets['MaxC>2.5'], bets['MaxC<2.5'])
    else:
        bets['b365_odds'] = np.where(bets['signal_side'] == 'OVER',
                                      bets['over_price'], bets['under_price'])
        bets['pin_odds'] = np.nan
        bets['max_odds'] = np.nan

    # --- D1: Calibration ---
    logit_p = np.log(np.clip(cal_p, 1e-6, 1-1e-6) / (1 - np.clip(cal_p, 1e-6, 1-1e-6)))
    lr = LogisticRegression(C=1e10, solver='lbfgs')
    lr.fit(logit_p.reshape(-1, 1), actual)
    cal_slope = lr.coef_[0][0]
    cal_intercept = lr.intercept_[0]
    brier = brier_score_loss(actual, cal_p)
    bias = (actual.mean() - cal_p.mean())

    bins_cal = [0.0, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 1.01]
    labels_cal = ['<0.40', '0.40-0.45', '0.45-0.50', '0.50-0.55', '0.55-0.60', '0.60-0.65', '0.65+']
    bucket_col = pd.cut(cal_p, bins=bins_cal, labels=labels_cal, right=False)

    # --- D2: Edge calibration ---
    edge_bins = [-np.inf, -0.06, -0.03, 0.00, 0.03, 0.06, 0.10, np.inf]
    edge_labels = ['<=-0.06', '-0.06:-0.03', '-0.03:0.00', '0.00:0.03', '0.03:0.06', '0.06:0.10', '0.10+']
    edge_bucket = pd.cut(edge, bins=edge_bins, labels=edge_labels)

    bucket_errs = []
    for lab in edge_labels:
        mask = edge_bucket == lab
        if mask.sum() > 0:
            bucket_errs.append(market_error[mask].mean())
    sp_corr, sp_p = spearmanr(range(len(bucket_errs)), bucket_errs) if len(bucket_errs) >= 3 else (0, 1)

    # --- D3: Closing line test ---
    def roi_stats(sub, odds_col='b365_odds'):
        if len(sub) == 0:
            return {'n': 0, 'hit': 0, 'roi': 0, 'avg_odds': 0}
        valid = sub[sub[odds_col].notna() & (sub[odds_col] > 1)]
        if len(valid) == 0:
            return {'n': 0, 'hit': 0, 'roi': 0, 'avg_odds': 0}
        profit = np.where(valid['win'], valid[odds_col] - 1, -1.0)
        return {'n': len(valid), 'hit': valid['win'].mean(),
                'roi': profit.sum() / len(valid) * 100,
                'avg_odds': valid[odds_col].mean()}

    overall_b365 = roi_stats(bets, 'b365_odds')
    overall_pin = roi_stats(bets, 'pin_odds')
    overall_max = roi_stats(bets, 'max_odds')

    # By tier
    tier_results = {}
    for t in ['LOW', 'MEDIUM', 'HIGH']:
        sub = bets[bets['tier'] == t]
        tier_results[t] = {
            'b365': roi_stats(sub, 'b365_odds'),
            'pin': roi_stats(sub, 'pin_odds'),
            'max': roi_stats(sub, 'max_odds'),
        }

    # By league
    league_results = {}
    for lg in active:
        sub = bets[bets['league_id'] == lg]
        league_results[lg] = {
            'b365': roi_stats(sub, 'b365_odds'),
            'pin': roi_stats(sub, 'pin_odds'),
            'max': roi_stats(sub, 'max_odds'),
        }

    # --- D4: Edge overstatement ---
    over_bets = bets[bets['signal_side'] == 'OVER']
    if len(over_bets) > 0:
        claimed_edge = (over_bets['v2_2c_p'] - over_bets['market_fair_p_over_2_5']).mean()
        actual_edge = (over_bets['actual_over_2_5'] - over_bets['market_fair_p_over_2_5']).mean()
        overstatement = claimed_edge / actual_edge if abs(actual_edge) > 0.001 else float('inf')
    else:
        claimed_edge = actual_edge = overstatement = 0

    results = {
        'alpha': alpha,
        'cal_slope': cal_slope,
        'bias_pp': bias * 100,
        'brier': brier,
        'spearman': sp_corr,
        'spearman_p': sp_p,
        'n_bets': len(bets),
        'n_over': len(over_bets),
        'overall_b365': overall_b365,
        'overall_pin': overall_pin,
        'overall_max': overall_max,
        'tier': tier_results,
        'league': league_results,
        'claimed_edge': claimed_edge,
        'actual_edge': actual_edge,
        'overstatement': overstatement,
    }

    return results


# ================================================================
# STEP 1: ALPHA SEARCH ON VALIDATION (2023-24)
# ================================================================
print("=" * 80)
print("STEP 1 — ALPHA SEARCH ON 2023-24 VALIDATION SET")
print("=" * 80)

alphas = [0.20, 0.25, 0.30, 0.35, 0.40, 0.50]

print(f"\n{'α':<6} {'Slope':>6} {'Bias':>7} {'Brier':>7} {'Spearman':>9} {'N bets':>7} "
      f"{'MED ROI':>8} {'BUN ROI':>8} {'Overst':>7} {'MED+BUN':>8}")
print("-" * 85)

val_results = []
for alpha in alphas:
    val['v2_2c_p'] = apply_shrinkage(val, alpha)
    r = full_diagnostics(val, f"VAL α={alpha}", alpha, raw_val)

    med_roi = r['tier']['MEDIUM']['b365']['roi'] if r['tier']['MEDIUM']['b365']['n'] > 0 else -999
    bun_roi = r['league']['BUN']['b365']['roi'] if r['league']['BUN']['b365']['n'] > 0 else -999
    combo = med_roi + bun_roi if med_roi > -999 and bun_roi > -999 else -999

    r['med_roi'] = med_roi
    r['bun_roi'] = bun_roi
    r['combo'] = combo
    val_results.append(r)

    print(f"{alpha:<6.2f} {r['cal_slope']:>6.2f} {r['bias_pp']:>+6.1f}pp {r['brier']:>7.4f} "
          f"{r['spearman']:>+8.3f} {r['n_bets']:>7} "
          f"{med_roi:>+7.1f}% {bun_roi:>+7.1f}% {r['overstatement']:>6.1f}x {combo:>+7.1f}")

# Select best α: maximize MEDIUM+BUN ROI while Spearman > 0.70
eligible = [r for r in val_results if r['spearman'] >= 0.70]
if not eligible:
    print("\nWARNING: No α achieves Spearman >= 0.70. Relaxing to best available.")
    eligible = val_results

best = max(eligible, key=lambda r: r['combo'])
chosen_alpha = best['alpha']
print(f"\n>>> CHOSEN α = {chosen_alpha} (MEDIUM+BUN = {best['combo']:+.1f}, Spearman = {best['spearman']:.3f})")

# Save parameters
params = {'alpha': chosen_alpha, 'method': 'market_shrinkage',
          'formula': 'P_final = P_market + alpha * (P_model - P_market)',
          'fit_on': 'validate_2023-24'}
os.makedirs('soccer/models/v2_2c', exist_ok=True)
with open('soccer/models/v2_2c/shrinkage_params.json', 'w') as f:
    json.dump(params, f, indent=2)
print(f"Saved: soccer/models/v2_2c/shrinkage_params.json")

# ================================================================
# STEP 2: FULL OOS EVALUATION WITH CHOSEN α
# ================================================================
print("\n" + "=" * 80)
print(f"STEP 2 — OOS EVALUATION (2024-25) WITH α = {chosen_alpha}")
print("=" * 80)

oos['v2_2c_p'] = apply_shrinkage(oos, chosen_alpha)
r = full_diagnostics(oos, f"OOS α={chosen_alpha}", chosen_alpha, raw_oos)

# --- D1: Calibration ---
print(f"\n--- Diagnostic 1: Calibration ---")
print(f"  Calibration slope: {r['cal_slope']:.4f}")
print(f"  Overall bias: {r['bias_pp']:+.1f}pp")
print(f"  Brier score: {r['brier']:.4f}")

cal_p = oos['v2_2c_p'].values
actual = oos['actual_over_2_5'].values
bins_cal = [0.0, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 1.01]
labels_cal = ['<0.40', '0.40-0.45', '0.45-0.50', '0.50-0.55', '0.55-0.60', '0.60-0.65', '0.65+']
bucket_col = pd.cut(cal_p, bins=bins_cal, labels=labels_cal, right=False)
print(f"\n  {'Bucket':<12} {'N':>5} {'Pred':>6} {'Actual':>7} {'Gap':>7}")
print(f"  {'-'*40}")
for lab in labels_cal:
    mask = bucket_col == lab
    if mask.sum() > 0:
        pred_avg = cal_p[mask].mean()
        act_avg = actual[mask].mean()
        gap = act_avg - pred_avg
        print(f"  {lab:<12} {mask.sum():>5} {pred_avg:>6.3f} {act_avg*100:>6.1f}% {gap:>+7.3f}")

# --- D2: Edge calibration ---
print(f"\n--- Diagnostic 2: Edge Calibration ---")
edge = cal_p - oos['market_fair_p_over_2_5'].values
market_error = actual - oos['market_fair_p_over_2_5'].values
edge_bins = [-np.inf, -0.06, -0.03, 0.00, 0.03, 0.06, 0.10, np.inf]
edge_labels = ['<=-0.06', '-0.06:-0.03', '-0.03:0.00', '0.00:0.03', '0.03:0.06', '0.06:0.10', '0.10+']
edge_bucket = pd.cut(edge, bins=edge_bins, labels=edge_labels)

print(f"\n  {'Bucket':<15} {'N':>5} {'Avg Edge':>9} {'Act O2.5':>9} {'Mkt Err':>9}")
print(f"  {'-'*50}")
bucket_errs = []
for lab in edge_labels:
    mask = edge_bucket == lab
    if mask.sum() > 0:
        ae = edge[mask].mean()
        ao = actual[mask].mean()
        me = market_error[mask].mean()
        bucket_errs.append(me)
        print(f"  {lab:<15} {mask.sum():>5} {ae:>+9.4f} {ao*100:>8.1f}% {me:>+9.4f}")

print(f"\n  Spearman: {r['spearman']:.3f} (p={r['spearman_p']:.3f})")

# --- D3: Closing line test ---
print(f"\n--- Diagnostic 3: Closing Line Test ---")
print(f"\n  Overall:")
for book, key in [('B365', 'overall_b365'), ('Pinnacle', 'overall_pin'), ('Max', 'overall_max')]:
    s = r[key]
    if s['n'] > 0:
        print(f"    {book}: N={s['n']}, Hit={s['hit']*100:.1f}%, ROI={s['roi']:+.1f}%, Avg odds={s['avg_odds']:.3f}")

print(f"\n  By Tier:")
for t in ['LOW', 'MEDIUM', 'HIGH']:
    tr = r['tier'][t]
    b = tr['b365']
    p = tr['pin']
    m = tr['max']
    if b['n'] > 0:
        thin = " THIN" if b['n'] < 30 else ""
        print(f"    {t}: N={b['n']}, Hit={b['hit']*100:.1f}%, B365={b['roi']:+.1f}%, Pin={p['roi']:+.1f}%, Max={m['roi']:+.1f}%{thin}")

print(f"\n  By League:")
for lg in active:
    lr_ = r['league'][lg]
    b = lr_['b365']
    p = lr_['pin']
    m = lr_['max']
    if b['n'] > 0:
        thin = " THIN" if b['n'] < 30 else ""
        print(f"    {lg}: N={b['n']}, Hit={b['hit']*100:.1f}%, B365={b['roi']:+.1f}%, Pin={p['roi']:+.1f}%, Max={m['roi']:+.1f}%{thin}")

# Special combos
med_bets = oos[(oos['v2_2c_p'] - oos['market_fair_p_over_2_5']).abs() >= 0.08]
med_bets = med_bets[(oos['v2_2c_p'] - oos['market_fair_p_over_2_5']).abs() < 0.10]
# Actually recompute cleanly
bets_df = oos.copy()
bets_df['edge_c'] = bets_df['v2_2c_p'] - bets_df['market_fair_p_over_2_5']
bets_df['abs_edge_c'] = bets_df['edge_c'].abs()
bets_df['tier_c'] = np.where(bets_df['abs_edge_c'] >= 0.10, 'HIGH',
                    np.where(bets_df['abs_edge_c'] >= 0.08, 'MEDIUM',
                    np.where(bets_df['abs_edge_c'] >= 0.06, 'LOW', 'NO_BET')))
bets_df['signal_c'] = np.where(bets_df['edge_c'] > 0, 'OVER', 'UNDER')
bets_df['win_c'] = np.where(bets_df['signal_c'] == 'OVER',
                             bets_df['actual_over_2_5'] == 1,
                             bets_df['actual_over_2_5'] == 0).astype(int)

# BUN + MEDIUM
bm = bets_df[(bets_df['league_id'] == 'BUN') & (bets_df['tier_c'] == 'MEDIUM')]
if len(bm) > 0:
    bm_profit = np.where(bm['win_c'], bm['over_price'] - 1, -1.0)
    print(f"\n  BUN+MEDIUM: N={len(bm)}, Hit={bm['win_c'].mean()*100:.1f}%, ROI@B365={bm_profit.sum()/len(bm)*100:+.1f}%")

# --- D4: Edge overstatement ---
print(f"\n--- Diagnostic 4: Edge Overstatement ---")
print(f"  OVER bets: N={r['n_over']}")
print(f"  Claimed edge: {r['claimed_edge']:+.4f}")
print(f"  Actual edge: {r['actual_edge']:+.4f}")
print(f"  Overstatement: {r['overstatement']:.1f}x")

# ================================================================
# COMPARISON TABLE
# ================================================================
print(f"\n" + "=" * 80)
print("COMPARISON TABLE")
print("=" * 80)

med_b365 = r['tier']['MEDIUM']['b365']
bun_b365 = r['league']['BUN']['b365']
epl_b365 = r['league']['EPL']['b365']
lg1_b365 = r['league']['LG1']['b365']
sea_b365 = r['league']['SEA']['b365']

print(f"""
| Metric                  | V2.2   | V2.2b  | V2.2c (α={chosen_alpha}) |
|-------------------------|--------|--------|----------------------|
| Calibration slope       | 0.64   | 0.99   | {r['cal_slope']:.2f}                 |
| Overall bias (pp)       | -3.8   | -4.2   | {r['bias_pp']:+.1f}                 |
| Brier score             | 0.2393 | 0.2391 | {r['brier']:.4f}               |
| Spearman (edge→mkt err) | 0.93   | 0.36   | {r['spearman']:.2f}                 |
| Edge overstatement      | 4.4x   | 6.8x   | {r['overstatement']:.1f}x                  |
| N active bets           | 413    | 357    | {r['n_bets']}                  |
| Overall ROI @ B365      | -1.3%  | -2.9%  | {r['overall_b365']['roi']:+.1f}%                |
| Overall ROI @ Pinnacle  | +0.4%  | —      | {r['overall_pin']['roi']:+.1f}%                |
| Overall ROI @ Max       | +3.3%  | —      | {r['overall_max']['roi']:+.1f}%                |
| BUN ROI @ B365          | +7.5%  | +7.1%  | {bun_b365['roi']:+.1f}%                |
| EPL ROI @ B365          | -4.9%  | -2.0%  | {epl_b365['roi']:+.1f}%                |
| LG1 ROI @ B365          | -3.0%  | +1.8%  | {lg1_b365['roi']:+.1f}%                |
| SEA ROI @ B365          | -9.2%  | -46.4% | {sea_b365['roi']:+.1f}%                |
| MEDIUM ROI @ B365       | +10.1% | -3.7%  | {med_b365['roi']:+.1f}%                |
| HIGH ROI @ B365         | +0.1%  | +1.4%  | {r['tier']['HIGH']['b365']['roi']:+.1f}%                |
| LOW ROI @ B365          | -7.9%  | -5.4%  | {r['tier']['LOW']['b365']['roi']:+.1f}%                |
""")

# ================================================================
# DECISION GATE
# ================================================================
print("=" * 80)
print("DECISION GATE")
print("=" * 80)

g1 = r['spearman'] >= 0.70
g2 = abs(r['overstatement']) < 2.0
g3 = bun_b365['roi'] > 0 if bun_b365['n'] > 0 else False
g4 = med_b365['roi'] > 0 if med_b365['n'] > 0 else False

print(f"  1. Spearman >= 0.70:       {'PASS' if g1 else 'FAIL'} ({r['spearman']:.3f})")
print(f"  2. Edge overstatement < 2x: {'PASS' if g2 else 'FAIL'} ({r['overstatement']:.1f}x)")
print(f"  3. BUN ROI positive:       {'PASS' if g3 else 'FAIL'} ({bun_b365['roi']:+.1f}%)")
print(f"  4. MEDIUM ROI positive:    {'PASS' if g4 else 'FAIL'} ({med_b365['roi']:+.1f}%)")

all_pass = g1 and g2 and g3 and g4
verdict = "PROMOTE V2.2c TO SHADOW" if all_pass else "KEEP V2.2 + INVESTIGATE"
print(f"\n  >>> VERDICT: {verdict}")

# Save OOS predictions
oos_out = oos[['game_id', 'game_date', 'league_id', 'actual_over_2_5',
               'market_fair_p_over_2_5', 'ridge_cal_p', 'v2_2c_p']].copy()
oos_out['edge_v2_2c'] = oos_out['v2_2c_p'] - oos_out['market_fair_p_over_2_5']
oos_out['alpha'] = chosen_alpha
oos_out.to_parquet('soccer/models/v2_2c/v2_2c_predictions_oos.parquet', index=False)
print(f"\nSaved: soccer/models/v2_2c/v2_2c_predictions_oos.parquet")
