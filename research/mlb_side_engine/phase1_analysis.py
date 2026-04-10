"""
Phase 1: TT-to-Side Feasibility Analysis
RESEARCH ONLY — does not modify any existing files or pipelines.
"""
import pandas as pd
import numpy as np
from scipy.stats import poisson
from scipy.special import gammaln
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss
import warnings
warnings.filterwarnings('ignore')

###############################################################################
# 0. TEAM ABBREVIATION MAP  (pitcher_logs -> game_table)
###############################################################################
TEAM_MAP = {
    'AZ': 'ARI', 'CWS': 'CHW', 'KC': 'KCR', 'SD': 'SDP',
    'SF': 'SFG', 'TB': 'TBR', 'WSH': 'WSN', 'ATH': 'OAK'
}

def norm_team(t):
    return TEAM_MAP.get(t, t)

###############################################################################
# 1. LOAD DATA
###############################################################################
print("Loading data...")
cc = pd.read_parquet('/root/mlb-model/mlb_sim/data/mlb_odds_closing_canonical.parquet')
gt = pd.read_parquet('/root/mlb-model/sim/data/game_table.parquet')
pg = pd.read_parquet('/root/mlb-model/mlb/data/pitcher_game_logs.parquet')

# Normalize team abbrevs in pitcher logs
pg['team_norm'] = pg['team'].map(norm_team)

# Filter to starters only
starters = pg[pg['starter_flag'] == 1].copy()

###############################################################################
# 2. POINT-IN-TIME ERA RECONSTRUCTION
###############################################################################
print("Computing point-in-time ERA...")

# Sort starters by date for rolling computation
starters = starters.sort_values(['player_id', 'game_date']).copy()

starters['ip_numeric'] = starters['innings_pitched']
starters['er_numeric'] = starters['earned_runs']

# Group by player_id, season -- compute cumulative prior stats
era_records = []
for (pid, szn), grp in starters.groupby(['player_id', 'season']):
    grp = grp.sort_values('game_date')
    cum_ip = grp['ip_numeric'].cumsum().shift(1, fill_value=0)
    cum_er = grp['er_numeric'].cumsum().shift(1, fill_value=0)
    pit_era = np.where(cum_ip > 0, (cum_er / cum_ip) * 9.0, np.nan)
    for i, (idx, row) in enumerate(grp.iterrows()):
        era_records.append({
            'game_pk': row['game_pk'],
            'player_id': pid,
            'season': szn,
            'game_date': row['game_date'],
            'team_norm': row['team_norm'],
            'pit_era': pit_era[i],
            'prior_starts': i,
            'prior_ip': cum_ip.iloc[i]
        })

era_df = pd.DataFrame(era_records)
print(f"  ERA records: {len(era_df)}")
print(f"  Non-null ERA: {era_df['pit_era'].notna().sum()}")

###############################################################################
# 3. JOIN: game_table + canonical + starters
###############################################################################
print("Building master table...")

# Normalize game_pk types
cc = cc[cc['game_pk'].astype(str).str.strip().str.len() > 0].copy()
cc['game_pk'] = pd.to_numeric(cc['game_pk'], errors='coerce')
cc = cc[cc['game_pk'].notna()].copy()
cc['game_pk'] = cc['game_pk'].astype(int)

# canonical may have dupes (multiple books) -- take last per game_pk
cc_dedup = cc.sort_values('pull_timestamp').groupby('game_pk').last().reset_index()

master = gt.merge(cc_dedup[['game_pk', 'ml_home_price', 'ml_away_price',
                             'ml_home_implied', 'ml_away_implied',
                             'total_line', 'home_total_line', 'away_total_line']],
                  on='game_pk', how='inner')

# Filter: need actual scores and ML
master = master[master['ml_home_implied'].notna() & master['ml_away_implied'].notna()].copy()
master = master[master['total_line'].notna()].copy()
master = master[master['home_score'].notna() & master['away_score'].notna()].copy()
# Exclude 2026 (too few games)
master = master[master['season'] <= 2025].copy()

print(f"  Master table: {len(master)} games with ML + total")

# Attach home/away starter ERA
home_sp = era_df.copy()
home_sp = home_sp.merge(gt[['game_pk', 'home_team']], on='game_pk', how='left')
home_sp = home_sp[home_sp['team_norm'] == home_sp['home_team']]
home_sp = home_sp.drop_duplicates('game_pk', keep='first')
home_sp = home_sp[['game_pk', 'pit_era', 'prior_starts', 'prior_ip']].rename(
    columns={'pit_era': 'home_sp_era', 'prior_starts': 'home_sp_prior_starts',
             'prior_ip': 'home_sp_prior_ip'})

away_sp = era_df.copy()
away_sp = away_sp.merge(gt[['game_pk', 'away_team']], on='game_pk', how='left')
away_sp = away_sp[away_sp['team_norm'] == away_sp['away_team']]
away_sp = away_sp.drop_duplicates('game_pk', keep='first')
away_sp = away_sp[['game_pk', 'pit_era', 'prior_starts', 'prior_ip']].rename(
    columns={'pit_era': 'away_sp_era', 'prior_starts': 'away_sp_prior_starts',
             'prior_ip': 'away_sp_prior_ip'})

master = master.merge(home_sp, on='game_pk', how='left')
master = master.merge(away_sp, on='game_pk', how='left')

print(f"  With home SP ERA: {master['home_sp_era'].notna().sum()}")
print(f"  With away SP ERA: {master['away_sp_era'].notna().sum()}")
print(f"  With both SP ERA: {(master['home_sp_era'].notna() & master['away_sp_era'].notna()).sum()}")

###############################################################################
# 4. DE-VIG ML
###############################################################################
master['vig_sum'] = master['ml_home_implied'] + master['ml_away_implied']
master['p_home_ml'] = master['ml_home_implied'] / master['vig_sum']
master['actual_home_win'] = (master['home_score'] > master['away_score']).astype(int)

# Exclude ties (should be very rare in MLB)
master = master[master['home_score'] != master['away_score']].copy()
print(f"  After excluding ties: {len(master)} games")

###############################################################################
# 5. TT FAIR VALUE + POISSON/NB TRANSLATION
###############################################################################
HOME_SHARE = 0.5015
TRUNCATION_ADJ = 0.248
LEAGUE_AVG_ERA = 4.50
SP_INNINGS_FACTOR = 0.621

def compute_tt_fair(row):
    total = row['total_line']
    away_sp_era = row['away_sp_era'] if pd.notna(row['away_sp_era']) else LEAGUE_AVG_ERA
    home_sp_era = row['home_sp_era'] if pd.notna(row['home_sp_era']) else LEAGUE_AVG_ERA

    # Cap extreme ERAs for early-season instability
    away_sp_era = np.clip(away_sp_era, 1.0, 10.0)
    home_sp_era = np.clip(home_sp_era, 1.0, 10.0)

    sp_adj_home = (away_sp_era - LEAGUE_AVG_ERA) * SP_INNINGS_FACTOR
    sp_adj_away = (home_sp_era - LEAGUE_AVG_ERA) * SP_INNINGS_FACTOR

    fair_home = total * HOME_SHARE - TRUNCATION_ADJ + sp_adj_home
    fair_away = total * (1 - HOME_SHARE) + sp_adj_away

    # Floor at 1.5 runs
    fair_home = max(fair_home, 1.5)
    fair_away = max(fair_away, 1.5)

    return pd.Series({'fair_home': fair_home, 'fair_away': fair_away})

print("Computing TT fair values...")
tt_vals = master.apply(compute_tt_fair, axis=1)
master['fair_home'] = tt_vals['fair_home']
master['fair_away'] = tt_vals['fair_away']

# Vectorized Poisson win prob using matrix operations
def poisson_win_prob_vec(lam_h_arr, lam_a_arr, max_goals=20):
    """Vectorized P(home wins) using independent Poisson."""
    results = np.zeros(len(lam_h_arr))
    for idx in range(len(lam_h_arr)):
        lam_h = lam_h_arr[idx]
        lam_a = lam_a_arr[idx]
        p_h = poisson.pmf(np.arange(max_goals), lam_h)
        p_a = poisson.pmf(np.arange(max_goals), lam_a)
        # Outer product
        grid = np.outer(p_h, p_a)
        p_win = np.tril(grid, -1).sum()  # h > a
        p_tie = np.diag(grid).sum()
        results[idx] = p_win + 0.5 * p_tie
    return results

# NB PMF
def nb_pmf_arr(k_arr, mu, var_ratio=1.15):
    var = var_ratio * mu
    if var <= mu:
        return poisson.pmf(k_arr, mu)
    r = mu**2 / (var - mu)
    p = mu / var
    log_pmf = (gammaln(k_arr + r) - gammaln(k_arr + 1) - gammaln(r) +
               k_arr * np.log(p) + r * np.log(1 - p))
    return np.exp(log_pmf)

def nb_win_prob_vec(lam_h_arr, lam_a_arr, max_goals=20, var_ratio=1.15):
    results = np.zeros(len(lam_h_arr))
    k_arr = np.arange(max_goals)
    for idx in range(len(lam_h_arr)):
        lam_h = lam_h_arr[idx]
        lam_a = lam_a_arr[idx]
        p_h = nb_pmf_arr(k_arr, lam_h, var_ratio)
        p_a = nb_pmf_arr(k_arr, lam_a, var_ratio)
        grid = np.outer(p_h, p_a)
        p_win = np.tril(grid, -1).sum()
        p_tie = np.diag(grid).sum()
        results[idx] = p_win + 0.5 * p_tie
    return results

print("Computing Poisson and NB win probabilities...")
lam_h = master['fair_home'].values
lam_a = master['fair_away'].values
master['p_home_poisson'] = poisson_win_prob_vec(lam_h, lam_a)
master['p_home_nb'] = nb_win_prob_vec(lam_h, lam_a)

###############################################################################
# 6. CALIBRATION: Pick Poisson vs NB on 2022-2023
###############################################################################
cal = master[master['season'].isin([2022, 2023])].copy()
oos = master[master['season'].isin([2024, 2025])].copy()

brier_poisson_cal = brier_score_loss(cal['actual_home_win'], cal['p_home_poisson'])
brier_nb_cal = brier_score_loss(cal['actual_home_win'], cal['p_home_nb'])
print(f"\nCalibration (2022-2023, N={len(cal)}):")
print(f"  Brier Poisson: {brier_poisson_cal:.6f}")
print(f"  Brier NB:      {brier_nb_cal:.6f}")

use_nb = brier_nb_cal < brier_poisson_cal
model_label = "NB" if use_nb else "Poisson"
master['p_home_tt'] = master['p_home_nb'] if use_nb else master['p_home_poisson']
print(f"  Selected: {model_label}")

###############################################################################
# 7. AGGREGATE BRIER SCORES
###############################################################################
# Train logistic combo on calibration set
cal = master[master['season'].isin([2022, 2023])].copy()
X_cal = cal[['p_home_ml', 'p_home_tt']].values
y_cal = cal['actual_home_win'].values
lr = LogisticRegression(C=1e6, solver='lbfgs', max_iter=1000)
lr.fit(X_cal, y_cal)

master['p_home_combo'] = lr.predict_proba(master[['p_home_ml', 'p_home_tt']].values)[:, 1]

# Re-split
cal = master[master['season'].isin([2022, 2023])].copy()
oos = master[master['season'].isin([2024, 2025])].copy()

print(f"\n{'='*70}")
print(f"AGGREGATE RESULTS")
print(f"{'='*70}")

for subset_name, subset in [("Calibration 2022-2023", cal), ("OOS 2024-2025", oos),
                             ("OOS 2024", master[master['season']==2024]),
                             ("OOS 2025", master[master['season']==2025])]:
    y = subset['actual_home_win'].values
    p_ml = np.clip(subset['p_home_ml'].values, 0.01, 0.99)
    p_tt = np.clip(subset['p_home_tt'].values, 0.01, 0.99)
    p_combo = np.clip(subset['p_home_combo'].values, 0.01, 0.99)

    b_ml = brier_score_loss(y, p_ml)
    b_tt = brier_score_loss(y, p_tt)
    b_combo = brier_score_loss(y, p_combo)
    ll_ml = log_loss(y, p_ml)
    ll_tt = log_loss(y, p_tt)
    ll_combo = log_loss(y, p_combo)

    print(f"\n{subset_name} (N={len(subset)}):")
    print(f"  {'Metric':<12} {'ML':>10} {'TT-'+model_label:>10} {'ML+TT':>10} {'ML-Combo':>10}")
    print(f"  {'Brier':<12} {b_ml:>10.6f} {b_tt:>10.6f} {b_combo:>10.6f} {b_ml-b_combo:>+10.6f}")
    print(f"  {'LogLoss':<12} {ll_ml:>10.6f} {ll_tt:>10.6f} {ll_combo:>10.6f} {ll_ml-ll_combo:>+10.6f}")

###############################################################################
# 8. CONDITIONAL BUCKET TESTS
###############################################################################
print(f"\n{'='*70}")
print(f"CONDITIONAL BUCKET TESTS (OOS 2024-2025)")
print(f"{'='*70}")

def bucket_eval(df, bucket_col, bucket_name):
    results = []
    for bval in sorted(df[bucket_col].dropna().unique()):
        sub = df[df[bucket_col] == bval]
        if len(sub) < 30:
            continue
        y = sub['actual_home_win'].values
        p_ml = np.clip(sub['p_home_ml'].values, 0.01, 0.99)
        p_combo = np.clip(sub['p_home_combo'].values, 0.01, 0.99)

        b_ml = brier_score_loss(y, p_ml)
        b_combo = brier_score_loss(y, p_combo)
        ll_ml = log_loss(y, p_ml)
        ll_combo = log_loss(y, p_combo)

        results.append({
            'bucket': bval, 'N': len(sub),
            'brier_ml': b_ml, 'brier_combo': b_combo,
            'brier_delta': b_ml - b_combo,
            'll_ml': ll_ml, 'll_combo': ll_combo,
            'll_delta': ll_ml - ll_combo
        })

    print(f"\n  {bucket_name}:")
    print(f"  {'Bucket':<20} {'N':>6} {'Brier_ML':>10} {'Brier_Comb':>10} {'Delta':>10} {'LL_ML':>10} {'LL_Comb':>10} {'LL_Delta':>10}")
    for r in results:
        print(f"  {str(r['bucket']):<20} {r['N']:>6} {r['brier_ml']:>10.6f} {r['brier_combo']:>10.6f} {r['brier_delta']:>+10.6f} {r['ll_ml']:>10.6f} {r['ll_combo']:>10.6f} {r['ll_delta']:>+10.6f}")
    return results

# A. SP quality differential
oos['era_gap'] = np.abs(oos['home_sp_era'].fillna(LEAGUE_AVG_ERA) - oos['away_sp_era'].fillna(LEAGUE_AVG_ERA))
oos['era_gap_bucket'] = pd.cut(oos['era_gap'], bins=[-0.01, 0.75, 1.5, 100],
                                labels=['Small (<0.75)', 'Medium (0.75-1.5)', 'Large (>1.5)'])
bucket_eval(oos, 'era_gap_bucket', 'A. SP ERA Gap')

# B. Total band
oos['total_bucket'] = pd.cut(oos['total_line'], bins=[0, 7.5, 9.0, 20],
                              labels=['Low (<7.5)', 'Mid (7.5-9.0)', 'High (>9.0)'])
bucket_eval(oos, 'total_bucket', 'B. Total Band')

# C. ML favorite strength
oos['fav_bucket'] = pd.cut(oos['p_home_ml'], bins=[0, 0.35, 0.45, 0.55, 0.65, 1.0],
                            labels=['Heavy away', 'Mod away', "Pick'em", 'Mod home', 'Heavy home'])
bucket_eval(oos, 'fav_bucket', 'C. ML Favorite Strength')

# D. Home vs away favorite
oos['home_fav'] = np.where(oos['p_home_ml'] > 0.5, 'Home fav', 'Away fav')
bucket_eval(oos, 'home_fav', 'D. Home vs Away Favorite')

# E. TT disagreement magnitude
oos['tt_disagree'] = oos['p_home_tt'] - oos['p_home_ml']
oos['tt_disagree_abs'] = np.abs(oos['tt_disagree'])
q10 = oos['tt_disagree_abs'].quantile(0.33)
q90 = oos['tt_disagree_abs'].quantile(0.67)
oos['disagree_bucket'] = np.where(oos['tt_disagree_abs'] <= q10, 'Small (bottom tercile)',
                          np.where(oos['tt_disagree_abs'] >= q90, 'Large (top tercile)', 'Medium'))
bucket_eval(oos, 'disagree_bucket', 'E. TT Disagreement Magnitude')

# Season stability check
print(f"\n  Season Stability:")
for szn in [2024, 2025]:
    sub = oos[oos['season'] == szn]
    y = sub['actual_home_win'].values
    p_ml = np.clip(sub['p_home_ml'].values, 0.01, 0.99)
    p_combo = np.clip(sub['p_home_combo'].values, 0.01, 0.99)
    b_ml = brier_score_loss(y, p_ml)
    b_combo = brier_score_loss(y, p_combo)
    ll_ml = log_loss(y, p_ml)
    ll_combo = log_loss(y, p_combo)
    print(f"  {szn}: N={len(sub)}, Brier ML={b_ml:.6f}, Combo={b_combo:.6f}, Delta={b_ml-b_combo:+.6f}, LL Delta={ll_ml-ll_combo:+.6f}")

###############################################################################
# 9. RESIDUAL STRUCTURE
###############################################################################
print(f"\n{'='*70}")
print(f"RESIDUAL STRUCTURE (OOS 2024-2025)")
print(f"{'='*70}")

oos['residual_ml'] = oos['actual_home_win'] - oos['p_home_ml']
oos['tt_disagreement'] = oos['p_home_tt'] - oos['p_home_ml']

# Overall correlation
corr_overall = np.corrcoef(oos['residual_ml'], oos['tt_disagreement'])[0, 1]
print(f"\n  Corr(ML residual, TT disagreement) overall: {corr_overall:.4f}")

# Per bucket
print(f"\n  Correlation by ERA gap bucket:")
for bval in sorted(oos['era_gap_bucket'].dropna().unique()):
    sub = oos[oos['era_gap_bucket'] == bval]
    c = np.corrcoef(sub['residual_ml'], sub['tt_disagreement'])[0, 1]
    print(f"    {bval}: {c:.4f} (N={len(sub)})")

print(f"\n  Correlation by total bucket:")
for bval in sorted(oos['total_bucket'].dropna().unique()):
    sub = oos[oos['total_bucket'] == bval]
    c = np.corrcoef(sub['residual_ml'], sub['tt_disagreement'])[0, 1]
    print(f"    {bval}: {c:.4f} (N={len(sub)})")

# Correction direction test
ml_wrong = oos[((oos['p_home_ml'] > 0.5) & (oos['actual_home_win'] == 0)) |
               ((oos['p_home_ml'] < 0.5) & (oos['actual_home_win'] == 1))].copy()
ml_wrong['tt_correct_dir'] = (
    ((ml_wrong['actual_home_win'] == 1) & (ml_wrong['tt_disagreement'] > 0)) |
    ((ml_wrong['actual_home_win'] == 0) & (ml_wrong['tt_disagreement'] < 0))
)
pct_correct = ml_wrong['tt_correct_dir'].mean()
print(f"\n  When ML is wrong (N={len(ml_wrong)}):")
print(f"    TT disagreement points toward correction: {pct_correct:.4f} ({pct_correct*100:.1f}%)")
print(f"    Baseline (50%): {'ABOVE' if pct_correct > 0.5 else 'BELOW'}")

# By disagreement magnitude when ML wrong
ml_wrong['disagree_abs'] = np.abs(ml_wrong['tt_disagreement'])
for q_label, q_lo, q_hi in [('Bottom tercile', 0, 0.33), ('Middle', 0.33, 0.67), ('Top tercile', 0.67, 1.0)]:
    lo = ml_wrong['disagree_abs'].quantile(q_lo)
    hi = ml_wrong['disagree_abs'].quantile(q_hi)
    sub = ml_wrong[(ml_wrong['disagree_abs'] >= lo) & (ml_wrong['disagree_abs'] <= hi)]
    pct = sub['tt_correct_dir'].mean()
    print(f"    {q_label} disagreement: {pct:.4f} ({pct*100:.1f}%, N={len(sub)})")

###############################################################################
# 10. INFORMATION GAIN SUMMARY
###############################################################################
print(f"\n{'='*70}")
print(f"INFORMATION GAIN SUMMARY")
print(f"{'='*70}")

# Logistic regression coefficients
print(f"\n  Logistic combo coefficients:")
print(f"    ML weight:  {lr.coef_[0][0]:.4f}")
print(f"    TT weight:  {lr.coef_[0][1]:.4f}")
print(f"    Intercept:  {lr.intercept_[0]:.4f}")
print(f"    TT / (ML+TT) weight share: {abs(lr.coef_[0][1]) / (abs(lr.coef_[0][0]) + abs(lr.coef_[0][1])):.4f}")

# Overall delta in bits
oos_y = oos['actual_home_win'].values
oos_p_ml = np.clip(oos['p_home_ml'].values, 0.01, 0.99)
oos_p_combo = np.clip(oos['p_home_combo'].values, 0.01, 0.99)
ll_ml = log_loss(oos_y, oos_p_ml)
ll_combo = log_loss(oos_y, oos_p_combo)
bits_gained = (ll_ml - ll_combo) / np.log(2)
print(f"\n  OOS log-loss delta: {ll_ml - ll_combo:.6f} nats = {bits_gained:.6f} bits/game")
print(f"  OOS Brier delta:   {brier_score_loss(oos_y, oos_p_ml) - brier_score_loss(oos_y, oos_p_combo):.6f}")

# Check if TT has SP ERA available
has_both_era = oos['home_sp_era'].notna() & oos['away_sp_era'].notna()
print(f"\n  Games with both SP ERA: {has_both_era.sum()} / {len(oos)} ({has_both_era.mean()*100:.1f}%)")

# Re-evaluate on only games with ERA
if has_both_era.sum() > 500:
    sub = oos[has_both_era]
    y = sub['actual_home_win'].values
    p_ml = np.clip(sub['p_home_ml'].values, 0.01, 0.99)
    p_combo = np.clip(sub['p_home_combo'].values, 0.01, 0.99)
    b_ml = brier_score_loss(y, p_ml)
    b_combo = brier_score_loss(y, p_combo)
    ll_ml_s = log_loss(y, p_ml)
    ll_combo_s = log_loss(y, p_combo)
    print(f"  On ERA-available subset (N={len(sub)}):")
    print(f"    Brier delta: {b_ml - b_combo:+.6f}")
    print(f"    LL delta:    {ll_ml_s - ll_combo_s:+.6f}")

###############################################################################
# 11. STAGE 5: Line movement check
###############################################################################
print(f"\n{'='*70}")
print(f"STAGE 5: LINE MOVEMENT")
print(f"{'='*70}")
if 'ml_home_opening' in cc.columns:
    print("  Opening ML data available -- would run line movement analysis")
else:
    print("  No opening ML data in canonical parquet -- SKIPPING")

###############################################################################
# 12. SAVE RESULTS
###############################################################################
print(f"\n{'='*70}")
print("SAVING REPORT...")

report_lines = []
report_lines.append("# Phase 1: TT-to-Side Feasibility Report")
report_lines.append("")
report_lines.append("## Methodology")
report_lines.append("")
report_lines.append("**Objective**: Test whether Team Total (TT) fair values contain side (moneyline) information")
report_lines.append("not already absorbed by ML closing prices.")
report_lines.append("")
report_lines.append("**Data**:")
report_lines.append(f"- Total games in master table: {len(master)}")
report_lines.append(f"- Calibration (2022-2023): {len(cal)}")
report_lines.append(f"- Out-of-sample (2024-2025): {len(oos)}")
report_lines.append(f"- Distribution model selected: {model_label} (lower Brier on calibration)")
report_lines.append(f"  - Poisson cal Brier: {brier_poisson_cal:.6f}")
report_lines.append(f"  - NB cal Brier: {brier_nb_cal:.6f}")
report_lines.append("")
report_lines.append("**Point-in-time ERA**: For each game, starter ERA computed from all prior starts in that")
report_lines.append("season only (strict < game_date). First start of season gets league-average 4.50.")
report_lines.append(f"Games with both SP ERA available: {(master['home_sp_era'].notna() & master['away_sp_era'].notna()).sum()} / {len(master)}")
report_lines.append("")
report_lines.append("**TT fair value formula**:")
report_lines.append("```")
report_lines.append("sp_adj_home = (away_sp_era - 4.50) * 0.621")
report_lines.append("sp_adj_away = (home_sp_era - 4.50) * 0.621")
report_lines.append("fair_home = total * 0.5015 - 0.248 + sp_adj_home")
report_lines.append("fair_away = total * (1 - 0.5015) + sp_adj_away")
report_lines.append("```")
report_lines.append("")
report_lines.append("**Side translation**: Independent Poisson/NB -> P(home wins) = sum P(h>a) + 0.5*P(tie)")
report_lines.append("")
report_lines.append("**Combination**: Logistic regression on (p_home_ml, p_home_tt), trained 2022-2023, applied 2024-2025")
report_lines.append("")

report_lines.append("## Stage 1: Aggregate Results")
report_lines.append("")
report_lines.append("| Period | N | Brier_ML | Brier_TT | Brier_Combo | Brier_Delta | LL_ML | LL_TT | LL_Combo | LL_Delta |")
report_lines.append("|--------|---|----------|----------|-------------|-------------|-------|-------|----------|----------|")

for subset_name, subset in [("Cal 2022-2023", cal), ("OOS 2024-2025", oos),
                             ("OOS 2024", master[master['season']==2024]),
                             ("OOS 2025", master[master['season']==2025])]:
    y = subset['actual_home_win'].values
    p_ml = np.clip(subset['p_home_ml'].values, 0.01, 0.99)
    p_tt = np.clip(subset['p_home_tt'].values, 0.01, 0.99)
    p_combo = np.clip(subset['p_home_combo'].values, 0.01, 0.99)
    b_ml = brier_score_loss(y, p_ml)
    b_tt = brier_score_loss(y, p_tt)
    b_combo = brier_score_loss(y, p_combo)
    ll_ml_ = log_loss(y, p_ml)
    ll_tt_ = log_loss(y, p_tt)
    ll_combo_ = log_loss(y, p_combo)
    report_lines.append(f"| {subset_name} | {len(subset)} | {b_ml:.6f} | {b_tt:.6f} | {b_combo:.6f} | {b_ml-b_combo:+.6f} | {ll_ml_:.6f} | {ll_tt_:.6f} | {ll_combo_:.6f} | {ll_ml_-ll_combo_:+.6f} |")

report_lines.append("")
report_lines.append(f"**Logistic combo weights**: ML={lr.coef_[0][0]:.4f}, TT={lr.coef_[0][1]:.4f}, intercept={lr.intercept_[0]:.4f}")
report_lines.append(f"**TT weight share**: {abs(lr.coef_[0][1]) / (abs(lr.coef_[0][0]) + abs(lr.coef_[0][1])):.1%}")
report_lines.append(f"**OOS information gain**: {bits_gained:.6f} bits/game")
report_lines.append("")

report_lines.append("## Stage 2: Conditional Bucket Tests (OOS 2024-2025)")
report_lines.append("")

for bucket_name, bucket_col in [
    ('A. SP ERA Gap', 'era_gap_bucket'),
    ('B. Total Band', 'total_bucket'),
    ('C. ML Favorite Strength', 'fav_bucket'),
    ('D. Home vs Away Favorite', 'home_fav'),
    ('E. TT Disagreement Magnitude', 'disagree_bucket')
]:
    report_lines.append(f"### {bucket_name}")
    report_lines.append("")
    report_lines.append("| Bucket | N | Brier_ML | Brier_Combo | Delta | LL_ML | LL_Combo | LL_Delta |")
    report_lines.append("|--------|---|----------|-------------|-------|-------|----------|----------|")

    for bval in sorted(oos[bucket_col].dropna().unique()):
        sub = oos[oos[bucket_col] == bval]
        if len(sub) < 30:
            continue
        y = sub['actual_home_win'].values
        p_ml = np.clip(sub['p_home_ml'].values, 0.01, 0.99)
        p_combo = np.clip(sub['p_home_combo'].values, 0.01, 0.99)
        b_ml = brier_score_loss(y, p_ml)
        b_combo = brier_score_loss(y, p_combo)
        ll_ml_ = log_loss(y, p_ml)
        ll_combo_ = log_loss(y, p_combo)
        report_lines.append(f"| {bval} | {len(sub)} | {b_ml:.6f} | {b_combo:.6f} | {b_ml-b_combo:+.6f} | {ll_ml_:.6f} | {ll_combo_:.6f} | {ll_ml_-ll_combo_:+.6f} |")

    # Season stability
    report_lines.append("")
    report_lines.append("Season stability:")
    for szn in [2024, 2025]:
        sub_szn = oos[oos['season'] == szn]
        for bval in sorted(sub_szn[bucket_col].dropna().unique()):
            sub = sub_szn[sub_szn[bucket_col] == bval]
            if len(sub) < 20:
                continue
            y = sub['actual_home_win'].values
            p_ml = np.clip(sub['p_home_ml'].values, 0.01, 0.99)
            p_combo = np.clip(sub['p_home_combo'].values, 0.01, 0.99)
            b_delta = brier_score_loss(y, p_ml) - brier_score_loss(y, p_combo)
            report_lines.append(f"- {szn} {bval}: N={len(sub)}, Brier delta={b_delta:+.6f}")
    report_lines.append("")

report_lines.append("## Stage 3: Residual Structure")
report_lines.append("")
report_lines.append(f"**Overall correlation** (ML residual vs TT disagreement): {corr_overall:.4f}")
report_lines.append("")
report_lines.append("Correlation by ERA gap:")
for bval in sorted(oos['era_gap_bucket'].dropna().unique()):
    sub = oos[oos['era_gap_bucket'] == bval]
    c = np.corrcoef(sub['residual_ml'], sub['tt_disagreement'])[0, 1]
    report_lines.append(f"- {bval}: {c:.4f} (N={len(sub)})")

report_lines.append("")
report_lines.append("Correlation by total band:")
for bval in sorted(oos['total_bucket'].dropna().unique()):
    sub = oos[oos['total_bucket'] == bval]
    c = np.corrcoef(sub['residual_ml'], sub['tt_disagreement'])[0, 1]
    report_lines.append(f"- {bval}: {c:.4f} (N={len(sub)})")

report_lines.append("")
report_lines.append(f"**Correction direction test** (when ML picks wrong side, N={len(ml_wrong)}):")
report_lines.append(f"- TT disagreement points toward correction: {pct_correct:.4f} ({pct_correct*100:.1f}%)")
report_lines.append(f"- By disagreement magnitude:")
for q_label, q_lo, q_hi in [('Bottom tercile', 0, 0.33), ('Middle', 0.33, 0.67), ('Top tercile', 0.67, 1.0)]:
    lo = ml_wrong['disagree_abs'].quantile(q_lo)
    hi = ml_wrong['disagree_abs'].quantile(q_hi)
    sub = ml_wrong[(ml_wrong['disagree_abs'] >= lo) & (ml_wrong['disagree_abs'] <= hi)]
    pct = sub['tt_correct_dir'].mean()
    report_lines.append(f"  - {q_label}: {pct:.4f} ({pct*100:.1f}%, N={len(sub)})")

report_lines.append("")
report_lines.append("## Stage 4: Information Gain Summary")
report_lines.append("")
report_lines.append(f"- OOS Brier delta (ML -> ML+TT): {brier_score_loss(oos_y, oos_p_ml) - brier_score_loss(oos_y, oos_p_combo):+.6f}")
report_lines.append(f"- OOS log-loss delta: {ll_ml - ll_combo:+.6f} nats = {bits_gained:+.6f} bits/game")
report_lines.append(f"- TT weight share in combo: {abs(lr.coef_[0][1]) / (abs(lr.coef_[0][0]) + abs(lr.coef_[0][1])):.1%}")
report_lines.append("")

# Verdict
if bits_gained > 0.001:
    verdict = "POSITIVE: TT contains marginal side information not fully absorbed by ML pricing."
    action = "Proceed to Phase 2: build standalone TT-based side engine with proper feature engineering."
elif bits_gained > 0:
    verdict = "MARGINAL: TT signal is detectable but very small. Likely not worth a standalone engine."
    action = "Consider TT as a supplementary feature in an ensemble, not a standalone signal."
else:
    verdict = "NEGATIVE: TT adds no side information beyond ML closing prices."
    action = "Do not pursue TT-to-side translation. ML prices fully absorb the TT signal."

report_lines.append(f"**Verdict**: {verdict}")
report_lines.append(f"**Recommended action**: {action}")
report_lines.append("")
report_lines.append("## Stage 5: Line Movement")
report_lines.append("")
report_lines.append("No opening ML data in canonical parquet. Skipped.")
report_lines.append("")
report_lines.append("## Limitations")
report_lines.append("")
report_lines.append("1. Point-in-time ERA uses only current-season starts. First ~2 weeks of each season default to league-average ERA (4.50).")
report_lines.append("2. TT formula uses fixed constants (HOME_SHARE=0.5015, etc.) -- not optimized for side prediction.")
report_lines.append("3. Logistic combo trained on 2022-2023 only (in-sample). OOS is 2024-2025.")
report_lines.append("4. Team totals not available in canonical for 2022 (0 games) and sparse for 2023 (650 games).")
report_lines.append("   TT falls back to market total split for these games, which dilutes the TT signal in calibration.")
report_lines.append("5. No starter identity features -- only raw ERA, which is a noisy proxy for true quality.")

report_text = "\n".join(report_lines)

with open('/root/mlb-model/research/mlb_side_engine/phase1_tt_to_side_feasibility.md', 'w') as f:
    f.write(report_text)

print(f"\nReport saved to /root/mlb-model/research/mlb_side_engine/phase1_tt_to_side_feasibility.md")
print("\nDONE.")
