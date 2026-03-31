"""
TB Model v1.1 — Calibration refinement and deployment analysis
RESEARCH ONLY — do not deploy
"""
import pandas as pd
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import roc_auc_score, log_loss, brier_score_loss
from sklearn.calibration import calibration_curve
import warnings
warnings.filterwarnings('ignore')
import importlib, sys

OUT = 'research/mlb_props/tb_model_v1_1'

# ═══════════════════════════════════════════════════════════
# LOAD DATA
# ═══════════════════════════════════════════════════════════
print("Loading data...")
ds = pd.read_parquet('research/mlb_props/tb_model_v1/tb_model_dataset.parquet')
tb_raw = pd.read_parquet('research/mlb_props/tb_props/tb_props_dataset.parquet')
hl = pd.read_parquet('mlb/data/hitter_game_logs.parquet')

# Name-to-ID mapping
name_to_id = hl.drop_duplicates('player_name')[['player_name', 'player_id']]
tb_raw = tb_raw.merge(name_to_id.rename(columns={'player_name': 'player_name_out'}),
                      on='player_name_out', how='left')

print(f"  Model dataset: {len(ds)} rows")
print(f"  TB props raw: {len(tb_raw)} rows")

# ═══════════════════════════════════════════════════════════
# STEP 1 — VALIDATION SET AUDIT
# ═══════════════════════════════════════════════════════════
print("\n" + "="*60)
print("STEP 1 — VALIDATION SET AUDIT")
print("="*60)

# Audit TB props raw
audit_rows = []
for line_val in sorted(tb_raw['line'].unique()):
    sub = tb_raw[tb_raw['line'] == line_val]
    audit_rows.append({
        'line': line_val,
        'total': len(sub),
        'with_under_odds': sub['under_odds'].notna().sum(),
        'unique_batter_games': sub.groupby(['player_id', 'game_pk_out']).ngroups
    })
audit_df = pd.DataFrame(audit_rows)
print("\nBy Line:")
print(audit_df.to_string(index=False))

print("\nBy Book (all lines):")
book_audit = tb_raw.groupby('book').agg(
    total=('line', 'count'),
    with_under_odds=('under_odds', lambda x: x.notna().sum()),
    lines=('line', lambda x: sorted(x.unique()))
).sort_values('total', ascending=False)
print(book_audit.to_string())

print("\nBy Book x Line 1.5:")
l15 = tb_raw[tb_raw['line'] == 1.5]
bl15 = l15.groupby('book').agg(
    N=('line', 'count'),
    with_under=('under_odds', lambda x: x.notna().sum())
).sort_values('N', ascending=False)
print(bl15.to_string())

print("\nBy Book x Line 2.5:")
l25 = tb_raw[tb_raw['line'] == 2.5]
bl25 = l25.groupby('book').agg(
    N=('line', 'count'),
    with_under=('under_odds', lambda x: x.notna().sum())
).sort_values('N', ascending=False)
print(bl25.to_string())

# ═══════════════════════════════════════════════════════════
# STEP 2 — ISOTONIC CALIBRATION
# ═══════════════════════════════════════════════════════════
print("\n" + "="*60)
print("STEP 2 — ISOTONIC CALIBRATION")
print("="*60)

core_features = [
    'zero_tb_rate_last10', 'zero_tb_rate_last20', 'zero_tb_rate_season',
    'pct_2plus_tb_last20', 'pct_4plus_tb_last20', 'tb_variance_last20',
    'ondeck_iso_last20', 'ondeck_woba_proxy_last20',
    'weak_protection_flag', 'high_iso_flag', 'high_iso_x_weak_protection',
    'protector_type_enc',
    'opp_drs',
    'p_barrel_rate_last5', 'p_hard_hit_rate_last5', 'p_whiff_rate_last5',
    'p_avg_ip_last5',
    'batter_iso_last20', 'batter_slg_last20', 'batter_k_rate_last20',
    'batter_obp_last20',
    'batting_order_slot', 'park_factor',
]

targets = {
    'tb_zero': 'tb_zero_flag',
    'tb_over_1_5': 'tb_over_1_5',
    'tb_over_2_5': 'tb_over_2_5',
}

min_features = ['zero_tb_rate_last20', 'batter_iso_last20', 'batting_order_slot']
ds_clean = ds.dropna(subset=min_features + ['tb_zero_flag']).copy()

# Split: train GBT on 2022-2023, calibrate isotonic on 2024, validate on 2025
train_mask = ds_clean['season'].isin([2022, 2023])
cal_mask = ds_clean['season'] == 2024
val_mask = ds_clean['season'] == 2025

train_df = ds_clean[train_mask].copy()
cal_df = ds_clean[cal_mask].copy()
val_df = ds_clean[val_mask].copy()

print(f"\n  GBT Train (2022-2023): {len(train_df)}")
print(f"  Calibration (2024): {len(cal_df)}")
print(f"  Validation (2025): {len(val_df)}")

# Medians from training set for imputation
medians = train_df[core_features].median()
X_train = train_df[core_features].fillna(medians).values
X_cal = cal_df[core_features].fillna(medians).values
X_val = val_df[core_features].fillna(medians).values

models = {}
iso_calibrators = {}
cal_results = {}
cal_curve_rows = []

for model_name, target_col in targets.items():
    print(f"\n  === {model_name} ===")
    y_train = train_df[target_col].values
    y_cal = cal_df[target_col].values
    y_val = val_df[target_col].values

    # Train GBT
    gbm = GradientBoostingClassifier(
        n_estimators=300, max_depth=4, learning_rate=0.05,
        min_samples_leaf=50, subsample=0.8, max_features=0.7, random_state=42
    )
    gbm.fit(X_train, y_train)
    models[model_name] = gbm

    # Raw predictions on calibration and validation sets
    raw_cal = gbm.predict_proba(X_cal)[:, 1]
    raw_val = gbm.predict_proba(X_val)[:, 1]

    # Fit isotonic calibrator on 2024
    iso = IsotonicRegression(y_min=0.01, y_max=0.99, out_of_bounds='clip')
    iso.fit(raw_cal, y_cal)
    iso_calibrators[model_name] = iso

    # Calibrated predictions on validation
    cal_val = iso.transform(raw_val)

    # Metrics comparison
    raw_auc = roc_auc_score(y_val, raw_val)
    cal_auc = roc_auc_score(y_val, cal_val)
    raw_ll = log_loss(y_val, raw_val)
    cal_ll = log_loss(y_val, cal_val)
    raw_brier = brier_score_loss(y_val, raw_val)
    cal_brier = brier_score_loss(y_val, cal_val)

    print(f"    Raw  AUC={raw_auc:.4f}  LogLoss={raw_ll:.4f}  Brier={raw_brier:.4f}")
    print(f"    Cal  AUC={cal_auc:.4f}  LogLoss={cal_ll:.4f}  Brier={cal_brier:.4f}")

    cal_results[model_name] = {
        'raw_auc': raw_auc, 'cal_auc': cal_auc,
        'raw_logloss': raw_ll, 'cal_logloss': cal_ll,
        'raw_brier': raw_brier, 'cal_brier': cal_brier,
    }

    # Calibration curves (10 bins, quantile strategy)
    for label, probs in [('raw', raw_val), ('calibrated', cal_val)]:
        frac_pos, mean_pred = calibration_curve(y_val, probs, n_bins=10, strategy='quantile')
        for i, (fp, mp) in enumerate(zip(frac_pos, mean_pred)):
            cal_curve_rows.append({
                'model': model_name, 'type': label,
                'bin': i, 'predicted': round(mp, 4), 'actual': round(fp, 4)
            })

    # Detailed calibration at extremes
    print(f"    Calibration at extremes (raw vs calibrated):")
    bins = [0, 0.3, 0.4, 0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 1.0]
    for lo, hi in zip(bins[:-1], bins[1:]):
        mask_raw = (raw_val >= lo) & (raw_val < hi)
        mask_cal = (cal_val >= lo) & (cal_val < hi)
        n_raw = mask_raw.sum()
        n_cal = mask_cal.sum()
        if n_raw > 20:
            act_raw = y_val[mask_raw].mean()
            pred_raw = raw_val[mask_raw].mean()
            print(f"      Raw  [{lo:.2f}-{hi:.2f}): N={n_raw:5d}, pred={pred_raw:.3f}, actual={act_raw:.3f}, gap={pred_raw-act_raw:+.3f}")
        if n_cal > 20:
            act_cal = y_val[mask_cal].mean()
            pred_cal = cal_val[mask_cal].mean()
            print(f"      Cal  [{lo:.2f}-{hi:.2f}): N={n_cal:5d}, pred={pred_cal:.3f}, actual={act_cal:.3f}, gap={pred_cal-act_cal:+.3f}")

    # Store predictions
    val_df[f'raw_{model_name}'] = raw_val
    val_df[f'cal_{model_name}'] = cal_val

# Save calibration curves
cal_curves_df = pd.DataFrame(cal_curve_rows)
cal_curves_df.to_parquet(f'{OUT}/calibration_curves.parquet', index=False)

# ═══════════════════════════════════════════════════════════
# STEP 3 — RECOMPUTE FAIR ODDS / EDGE (ALL BOOK RECORDS)
# ═══════════════════════════════════════════════════════════
print("\n" + "="*60)
print("STEP 3 — RECOMPUTE FAIR ODDS / EDGE")
print("="*60)

# Join calibrated predictions to ALL tb_raw records (not just best book)
# Model predictions are per batter-game; market records are per batter-game-book-line
val_preds = val_df[['player_id', 'game_pk', 'total_bases',
                     'tb_zero_flag', 'tb_over_1_5', 'tb_over_2_5', 'tb_tail_flag',
                     'cal_tb_zero', 'cal_tb_over_1_5', 'cal_tb_over_2_5',
                     'raw_tb_zero', 'raw_tb_over_1_5', 'raw_tb_over_2_5']].copy()

# Derived probabilities
val_preds['cal_p_under_1_5'] = 1 - val_preds['cal_tb_over_1_5']
val_preds['cal_p_under_2_5'] = 1 - val_preds['cal_tb_over_2_5']
val_preds['cal_p_over_0_5'] = 1 - val_preds['cal_tb_zero']
val_preds['raw_p_under_1_5'] = 1 - val_preds['raw_tb_over_1_5']
val_preds['raw_p_under_2_5'] = 1 - val_preds['raw_tb_over_2_5']

# Join to ALL tb_raw records
mkt = tb_raw[['player_id', 'game_pk_out', 'line', 'book', 'over_odds', 'under_odds',
               'implied_over', 'implied_under', 'actual_tb',
               'over_hit', 'under_hit', 'push', 'over_pnl', 'under_pnl',
               'game_date', 'player_name']].copy()
mkt = mkt.rename(columns={'game_pk_out': 'game_pk'})

joined = mkt.merge(val_preds[['player_id', 'game_pk',
                               'cal_p_under_1_5', 'cal_p_under_2_5', 'cal_p_over_0_5',
                               'cal_tb_zero', 'cal_tb_over_1_5', 'cal_tb_over_2_5',
                               'raw_p_under_1_5', 'raw_p_under_2_5']],
                   on=['player_id', 'game_pk'], how='inner')

print(f"  Joined records: {len(joined)} (from {len(mkt)} market records)")

# Compute edge for relevant lines
# Under 1.5: model P(under) vs market (1 - implied_over)
joined['mkt_p_under'] = 1 - joined['implied_over']
joined['won_under'] = np.where(
    joined['line'] == 0.5, (joined['actual_tb'] == 0).astype(int),
    np.where(joined['line'] == 1.5, (joined['actual_tb'] < 2).astype(int),
    np.where(joined['line'] == 2.5, (joined['actual_tb'] < 3).astype(int),
    np.where(joined['line'] == 3.5, (joined['actual_tb'] < 4).astype(int), np.nan))))

# Cal edge for each line
joined['cal_p_under'] = np.where(
    joined['line'] == 1.5, joined['cal_p_under_1_5'],
    np.where(joined['line'] == 2.5, joined['cal_p_under_2_5'],
    np.where(joined['line'] == 0.5, joined['cal_tb_zero'], np.nan)))
joined['cal_edge'] = joined['cal_p_under'] - joined['mkt_p_under']

# Raw edge for comparison
joined['raw_p_under'] = np.where(
    joined['line'] == 1.5, joined['raw_p_under_1_5'],
    np.where(joined['line'] == 2.5, joined['raw_p_under_2_5'], np.nan))
joined['raw_edge'] = joined['raw_p_under'] - joined['mkt_p_under']

# Focus on lines 1.5 and 2.5
for line_val in [1.5, 2.5]:
    sub = joined[joined['line'] == line_val]
    valid_edge = sub['cal_edge'].dropna()
    print(f"\n  Line {line_val}: {len(sub)} records, {sub['under_odds'].notna().sum()} with under_odds")
    print(f"    Cal edge: mean={valid_edge.mean():.4f}, median={valid_edge.median():.4f}, >0: {(valid_edge>0).mean()*100:.1f}%")
    print(f"    Win rate (under): {sub['won_under'].mean():.4f}")

# Save calibrated predictions
joined.to_parquet(f'{OUT}/calibrated_predictions.parquet', index=False)
print(f"\n  Saved calibrated_predictions.parquet: {len(joined)} rows")

# ═══════════════════════════════════════════════════════════
# STEP 4 — BOOKMAKER-SPECIFIC BACKTESTS
# ═══════════════════════════════════════════════════════════
print("\n" + "="*60)
print("STEP 4 — BOOKMAKER-SPECIFIC BACKTESTS")
print("="*60)

book_bt_rows = []

for line_val in [1.5, 2.5]:
    sub = joined[(joined['line'] == line_val) & joined['cal_edge'].notna()].copy()
    for book, grp in sub.groupby('book'):
        n = len(grp)
        if n < 10:
            continue
        win_rate = grp['won_under'].mean()
        mkt_p = grp['mkt_p_under'].mean()
        cal_edge = grp['cal_edge'].mean()
        raw_edge = grp['raw_edge'].mean() if grp['raw_edge'].notna().any() else np.nan

        # ROI where under_odds exist
        with_odds = grp.dropna(subset=['under_odds'])
        roi = with_odds['under_pnl'].mean() if len(with_odds) > 0 else np.nan
        n_odds = len(with_odds)

        # Theoretical flat-bet ROI estimate:
        # If we bet Under at implied prob = mkt_p and actual win rate = win_rate,
        # ROI ≈ (win_rate / mkt_p) - 1  [ignoring vig structure details]
        # More precise: use average vig assumption
        # For books without under_odds, assume standard -130 vig on Under side
        if n_odds == 0 and win_rate > 0:
            # Assume Under priced at -130 (payout 0.769 per dollar risked)
            theo_roi = win_rate * (1 + 100/130) - 1  # win_rate * 1.769 - 1
        else:
            theo_roi = np.nan

        flag = 'THIN' if n < 50 else ('MEDIUM' if n < 250 else 'SOLID')

        book_bt_rows.append({
            'line': line_val, 'book': book, 'N': n, 'N_with_odds': n_odds,
            'win_rate': round(win_rate, 4),
            'mkt_p_under': round(mkt_p, 4),
            'cal_edge_mean': round(cal_edge, 4),
            'raw_edge_mean': round(raw_edge, 4) if not np.isnan(raw_edge) else None,
            'roi_actual': round(roi, 4) if not np.isnan(roi) else None,
            'theo_roi': round(theo_roi, 4) if not np.isnan(theo_roi) else None,
            'sample_flag': flag,
        })

        if n >= 50:
            print(f"  {book:<16s} line={line_val} N={n:5d} N_odds={n_odds:3d} "
                  f"win={win_rate:.3f} mkt_p={mkt_p:.3f} cal_edge={cal_edge:+.4f} "
                  f"ROI={'N/A' if np.isnan(roi) else f'{roi:+.4f}'} [{flag}]")

book_bt_df = pd.DataFrame(book_bt_rows)
book_bt_df.to_parquet(f'{OUT}/bookmaker_backtests.parquet', index=False)

# ═══════════════════════════════════════════════════════════
# STEP 5 — ODDS-BUCKET DEPLOYMENT ANALYSIS
# ═══════════════════════════════════════════════════════════
print("\n" + "="*60)
print("STEP 5 — ODDS-BUCKET ANALYSIS")
print("="*60)

def odds_bucket(odds):
    if pd.isna(odds): return None
    if odds >= -110: return '-110 or better'
    elif odds >= -125: return '-111 to -125'
    elif odds >= -140: return '-126 to -140'
    else: return 'worse than -140'

odds_bt_rows = []
for line_val in [1.5, 2.5]:
    sub = joined[(joined['line'] == line_val) & joined['under_odds'].notna() & joined['cal_edge'].notna()].copy()
    sub['odds_bucket'] = sub['under_odds'].apply(odds_bucket)

    for bucket, grp in sub.groupby('odds_bucket'):
        if len(grp) < 5:
            continue
        odds_bt_rows.append({
            'line': line_val, 'odds_bucket': bucket, 'N': len(grp),
            'cal_edge': round(grp['cal_edge'].mean(), 4),
            'win_rate': round(grp['won_under'].mean(), 4),
            'roi': round(grp['under_pnl'].mean(), 4),
            'avg_under_odds': round(grp['under_odds'].mean(), 1),
        })
        print(f"  line={line_val} {bucket:<18s} N={len(grp):4d} "
              f"cal_edge={grp['cal_edge'].mean():+.4f} win={grp['won_under'].mean():.3f} "
              f"ROI={grp['under_pnl'].mean():+.4f}")

odds_bt_df = pd.DataFrame(odds_bt_rows)
odds_bt_df.to_parquet(f'{OUT}/odds_bucket_analysis.parquet', index=False)

# ═══════════════════════════════════════════════════════════
# STEP 6 — THRESHOLD / COHORT OPTIMIZATION
# ═══════════════════════════════════════════════════════════
print("\n" + "="*60)
print("STEP 6 — DEPLOYMENT COHORT ANALYSIS")
print("="*60)

cohort_rows = []

for line_val in [1.5, 2.5]:
    for book_filter, book_label in [(None, 'all_books'), ('betonlineag', 'betonlineag'), ('fanduel', 'fanduel')]:
        sub = joined[(joined['line'] == line_val) & joined['cal_edge'].notna()].copy()
        if book_filter:
            sub = sub[sub['book'] == book_filter]
        if len(sub) < 20:
            continue

        # Confidence percentile thresholds
        for pct_label, pct in [('top_10', 0.90), ('top_20', 0.80), ('top_30', 0.70), ('top_40', 0.60)]:
            threshold = sub['cal_p_under'].quantile(pct)
            cohort = sub[sub['cal_p_under'] >= threshold]
            if len(cohort) < 10:
                continue
            n = len(cohort)
            wr = cohort['won_under'].mean()
            edge = cohort['cal_edge'].mean()
            with_odds = cohort.dropna(subset=['under_odds'])
            roi = with_odds['under_pnl'].mean() if len(with_odds) > 0 else np.nan
            n_odds = len(with_odds)
            avg_odds = with_odds['under_odds'].mean() if n_odds > 0 else np.nan

            cohort_rows.append({
                'line': line_val, 'book': book_label, 'cohort': pct_label,
                'filter_type': 'confidence',
                'threshold': round(threshold, 4), 'N': n, 'N_with_odds': n_odds,
                'win_rate': round(wr, 4), 'cal_edge': round(edge, 4),
                'roi': round(roi, 4) if not np.isnan(roi) else None,
                'avg_odds': round(avg_odds, 1) if not np.isnan(avg_odds) else None,
            })

        # Edge thresholds
        for edge_thresh in [0.03, 0.05, 0.07, 0.10]:
            cohort = sub[sub['cal_edge'] >= edge_thresh]
            if len(cohort) < 10:
                continue
            n = len(cohort)
            wr = cohort['won_under'].mean()
            edge = cohort['cal_edge'].mean()
            with_odds = cohort.dropna(subset=['under_odds'])
            roi = with_odds['under_pnl'].mean() if len(with_odds) > 0 else np.nan
            n_odds = len(with_odds)
            avg_odds = with_odds['under_odds'].mean() if n_odds > 0 else np.nan

            cohort_rows.append({
                'line': line_val, 'book': book_label, 'cohort': f'edge>={edge_thresh}',
                'filter_type': 'edge',
                'threshold': edge_thresh, 'N': n, 'N_with_odds': n_odds,
                'win_rate': round(wr, 4), 'cal_edge': round(edge, 4),
                'roi': round(roi, 4) if not np.isnan(roi) else None,
                'avg_odds': round(avg_odds, 1) if not np.isnan(avg_odds) else None,
            })

cohort_df = pd.DataFrame(cohort_rows)

# Print key cohorts
print("\n  === Under 1.5 — All Books ===")
print(cohort_df[(cohort_df['line']==1.5) & (cohort_df['book']=='all_books')].to_string(index=False))
print("\n  === Under 1.5 — BetOnline ===")
print(cohort_df[(cohort_df['line']==1.5) & (cohort_df['book']=='betonlineag')].to_string(index=False))
print("\n  === Under 2.5 — All Books ===")
print(cohort_df[(cohort_df['line']==2.5) & (cohort_df['book']=='all_books')].to_string(index=False))
print("\n  === Under 2.5 — BetOnline ===")
print(cohort_df[(cohort_df['line']==2.5) & (cohort_df['book']=='betonlineag')].to_string(index=False))
print("\n  === Under 1.5 — FanDuel ===")
print(cohort_df[(cohort_df['line']==1.5) & (cohort_df['book']=='fanduel')].to_string(index=False))
print("\n  === Under 2.5 — FanDuel ===")
print(cohort_df[(cohort_df['line']==2.5) & (cohort_df['book']=='fanduel')].to_string(index=False))

cohort_df.to_parquet(f'{OUT}/deployment_cohort_analysis.parquet', index=False)

# ═══════════════════════════════════════════════════════════
# STEP 7 — STABILITY CHECKS
# ═══════════════════════════════════════════════════════════
print("\n" + "="*60)
print("STEP 7 — STABILITY CHECKS")
print("="*60)

joined['month'] = pd.to_datetime(joined['game_date']).dt.month
joined['half'] = np.where(joined['month'] <= 6, 'H1', 'H2')

stability_rows = []
for line_val in [1.5, 2.5]:
    for book_filter, book_label in [(None, 'all_books'), ('betonlineag', 'betonlineag'), ('fanduel', 'fanduel')]:
        for half in ['H1', 'H2']:
            sub = joined[(joined['line'] == line_val) & (joined['half'] == half) & joined['cal_edge'].notna()]
            if book_filter:
                sub = sub[sub['book'] == book_filter]
            if len(sub) < 20:
                continue

            # Test key cohorts
            for pct_label, pct in [('top_20', 0.80), ('top_30', 0.70)]:
                threshold = sub['cal_p_under'].quantile(pct)
                cohort = sub[sub['cal_p_under'] >= threshold]
                if len(cohort) < 10:
                    continue
                wr = cohort['won_under'].mean()
                edge = cohort['cal_edge'].mean()
                with_odds = cohort.dropna(subset=['under_odds'])
                roi = with_odds['under_pnl'].mean() if len(with_odds) > 0 else np.nan

                stability_rows.append({
                    'line': line_val, 'book': book_label, 'half': half,
                    'cohort': pct_label, 'N': len(cohort),
                    'N_with_odds': len(with_odds),
                    'win_rate': round(wr, 4), 'cal_edge': round(edge, 4),
                    'roi': round(roi, 4) if not np.isnan(roi) else None,
                })

            # Edge threshold
            for edge_thresh in [0.05, 0.07]:
                cohort = sub[sub['cal_edge'] >= edge_thresh]
                if len(cohort) < 10:
                    continue
                wr = cohort['won_under'].mean()
                edge = cohort['cal_edge'].mean()
                with_odds = cohort.dropna(subset=['under_odds'])
                roi = with_odds['under_pnl'].mean() if len(with_odds) > 0 else np.nan

                stability_rows.append({
                    'line': line_val, 'book': book_label, 'half': half,
                    'cohort': f'edge>={edge_thresh}', 'N': len(cohort),
                    'N_with_odds': len(with_odds),
                    'win_rate': round(wr, 4), 'cal_edge': round(edge, 4),
                    'roi': round(roi, 4) if not np.isnan(roi) else None,
                })

stability_df = pd.DataFrame(stability_rows)
print("\n  Under 1.5 — All Books stability:")
print(stability_df[(stability_df['line']==1.5) & (stability_df['book']=='all_books')].to_string(index=False))
print("\n  Under 1.5 — BetOnline stability:")
print(stability_df[(stability_df['line']==1.5) & (stability_df['book']=='betonlineag')].to_string(index=False))
print("\n  Under 2.5 — All Books stability:")
print(stability_df[(stability_df['line']==2.5) & (stability_df['book']=='all_books')].to_string(index=False))
print("\n  Under 2.5 — BetOnline stability:")
print(stability_df[(stability_df['line']==2.5) & (stability_df['book']=='betonlineag')].to_string(index=False))
print("\n  Under 1.5 — FanDuel stability:")
print(stability_df[(stability_df['line']==1.5) & (stability_df['book']=='fanduel')].to_string(index=False))
print("\n  Under 2.5 — FanDuel stability:")
print(stability_df[(stability_df['line']==2.5) & (stability_df['book']=='fanduel')].to_string(index=False))

# ═══════════════════════════════════════════════════════════
# STEP 8 — FEATURE IMPORTANCE RECHECK
# ═══════════════════════════════════════════════════════════
print("\n" + "="*60)
print("STEP 8 — FEATURE IMPORTANCE")
print("="*60)

importance_rows = []
for model_name, gbm in models.items():
    imp = gbm.feature_importances_
    sorted_idx = np.argsort(imp)[::-1]
    print(f"\n  {model_name} — Top 15:")
    for rank, i in enumerate(sorted_idx[:15]):
        feat = core_features[i]
        importance = imp[i]
        importance_rows.append({
            'model': model_name, 'rank': rank + 1,
            'feature': feat, 'importance': round(importance, 4)
        })
        print(f"    {rank+1:2d}. {feat:<35s} {importance:.4f}")

importance_df = pd.DataFrame(importance_rows)
importance_df.to_parquet(f'{OUT}/feature_importance_v1_1.parquet', index=False)

# ═══════════════════════════════════════════════════════════
# FINAL SUMMARY
# ═══════════════════════════════════════════════════════════
print("\n" + "="*60)
print("FINAL SUMMARY")
print("="*60)

print("\n  Calibration improvement:")
for name, r in cal_results.items():
    print(f"    {name}: LogLoss {r['raw_logloss']:.4f} -> {r['cal_logloss']:.4f} "
          f"({r['cal_logloss']-r['raw_logloss']:+.4f}), "
          f"Brier {r['raw_brier']:.4f} -> {r['cal_brier']:.4f} "
          f"({r['cal_brier']-r['raw_brier']:+.4f})")

print("\n  Key cohort ROIs (Under 1.5, all books):")
key = cohort_df[(cohort_df['line']==1.5) & (cohort_df['book']=='all_books')]
print(key[['cohort','N','N_with_odds','win_rate','cal_edge','roi']].to_string(index=False))

print("\n  Key cohort ROIs (Under 1.5, BetOnline):")
key2 = cohort_df[(cohort_df['line']==1.5) & (cohort_df['book']=='betonlineag')]
print(key2[['cohort','N','N_with_odds','win_rate','cal_edge','roi']].to_string(index=False))

print("\nDone. All files saved.")
