"""
Soccer V3 Poisson Challenger Model
===================================
Independent Poisson simulation model using team attack/defense strengths.
Strict leakage prevention: each game uses only prior data.
"""

import pandas as pd
import numpy as np
from scipy.stats import poisson
from scipy.special import expit as sigmoid
from sklearn.linear_model import LogisticRegression
import pickle, json, os, sys
from collections import defaultdict
from io import StringIO

os.chdir('/Users/jw115/mlb-model')

# Capture all output
output_lines = []
def tprint(*args, **kwargs):
    buf = StringIO()
    print(*args, file=buf, **kwargs)
    text = buf.getvalue()
    sys.stdout.write(text)
    sys.stdout.flush()
    output_lines.append(text)

# ── Load data ──────────────────────────────────────────────────────────
tprint("Loading data...")
canon = pd.read_parquet('soccer/data/soccer_canonical.parquet')
odds = pd.read_parquet('soccer/data/odds_historical.parquet')
pred_v22 = pd.read_parquet('soccer/data/soccer_v2_2_predictions.parquet')

active = ['EPL', 'BUN', 'SEA', 'LG1']
df = canon[canon['league_id'].isin(active)].copy()
df = df.sort_values('game_date').reset_index(drop=True)
tprint(f"Active league games: {len(df)}")

# xG with fallback to goals
df['home_xg'] = df['home_xg_raw'].fillna(df['home_score'])
df['away_xg'] = df['away_xg_raw'].fillna(df['away_score'])

# ── PART 1: Team Strength Model ───────────────────────────────────────
tprint("\n=== PART 1: Computing team strengths (strict chronological) ===")

# Pre-compute: for each game, gather historical stats
# We'll iterate chronologically and maintain running histories per team

# Data structures: team -> list of (game_date, season_year, league_id, xg_scored, xg_allowed)
team_history = defaultdict(list)

# League-level stats: league_id -> list of (game_date, season_year, home_xg, away_xg)
league_history = defaultdict(list)

# Prior season finals: (team, season_year) -> (attack_adj, defense_adj)
# We'll compute these on the fly

# Training split home/away factors per league
# First pass: compute from training data (pre 2023-24)
splits = pred_v22[['game_id', 'split']].drop_duplicates()
df = df.merge(splits, on='game_id', how='left')

train_data = df[df['split'] == 'train'].copy()
tprint(f"Training games: {len(train_data)}")

# Home/away factors per league from training data
home_away_factors = {}
league_base_rates = {}
for lg in active:
    lg_train = train_data[train_data['league_id'] == lg]
    if len(lg_train) == 0:
        continue
    avg_home = lg_train['home_xg'].mean()
    avg_away = lg_train['away_xg'].mean()
    avg_all = (avg_home + avg_away) / 2
    home_away_factors[lg] = {
        'home_factor': avg_home / avg_all,
        'away_factor': avg_away / avg_all,
        'avg_home_xg': float(avg_home),
        'avg_away_xg': float(avg_away),
        'base_rate': float(avg_all),  # avg goals per team per game
    }
    league_base_rates[lg] = float(avg_all)
    tprint(f"  {lg}: home_factor={avg_home/avg_all:.3f}, away_factor={avg_away/avg_all:.3f}, base_rate={avg_all:.3f}")

# Rest adjustment factors
REST_SHORT = 0.97   # <= 3 days
REST_NORMAL = 1.00  # 4-7 days
REST_LONG = 0.99    # > 7 days

# ── Main chronological loop ───────────────────────────────────────────
tprint("\nComputing game-by-game strengths...")

# Results storage
results = []

# Track last game date per team for rest calculation
team_last_game = {}

# Track season stats per team for prior-season blending
# (team, season_year) -> list of (attack_adj_raw, defense_adj_raw)
team_season_stats = defaultdict(list)

# Track prior season final stats
# (team) -> (final_attack_adj, final_defense_adj, season_year)
team_prior_season_final = {}

n_games = len(df)

for idx, row in df.iterrows():
    game_id = row['game_id']
    game_date = row['game_date']
    season = row['season_year']
    league = row['league_id']
    home = row['home_team']
    away = row['away_team']

    if idx % 1000 == 0:
        tprint(f"  Processing game {idx}/{n_games} ({game_date})...")

    # ── Compute rolling stats for home team ──
    def get_team_strength(team, league_id):
        hist = team_history[team]
        if len(hist) == 0:
            return 1.0, 1.0, 0  # league average, 0 games

        # Get rolling 10 (or expanding if < 10)
        recent = hist[-10:]
        avg_attack = np.mean([h[3] for h in recent])
        avg_defense = np.mean([h[4] for h in recent])

        # League baseline: compute from league history (only past games)
        lg_hist = league_history[league_id]
        if len(lg_hist) == 0:
            return 1.0, 1.0, len(hist)

        # Rolling league average (last 100 games or all available)
        lg_recent = lg_hist[-200:]  # 200 entries = 100 games (each game adds 2)
        lg_avg_attack = np.mean([h[2] for h in lg_recent])  # all xg scored

        if lg_avg_attack == 0:
            return 1.0, 1.0, len(hist)

        attack_adj = avg_attack / lg_avg_attack
        defense_adj = avg_defense / lg_avg_attack  # relative to league avg scoring

        return attack_adj, defense_adj, len(hist)

    def get_season_games_count(team, season_year):
        """Count games played by team in current season (from history)"""
        return sum(1 for h in team_history[team] if h[1] == season_year)

    # Get raw strengths
    home_attack_adj, home_defense_adj, home_n = get_team_strength(home, league)
    away_attack_adj, away_defense_adj, away_n = get_team_strength(away, league)

    # ── Early-season prior blend ──
    home_season_games = get_season_games_count(home, season)
    away_season_games = get_season_games_count(away, season)

    def blend_with_prior(attack_adj, defense_adj, team, season_games):
        weight = min(season_games, 10) / 10.0
        if weight >= 1.0:
            return attack_adj, defense_adj

        # Get prior season final
        prior_attack, prior_defense = 1.0, 1.0  # default: league average
        if team in team_prior_season_final:
            prior_attack, prior_defense, _ = team_prior_season_final[team]

        blended_attack = weight * attack_adj + (1 - weight) * prior_attack
        blended_defense = weight * defense_adj + (1 - weight) * prior_defense
        return blended_attack, blended_defense

    home_attack_adj, home_defense_adj = blend_with_prior(home_attack_adj, home_defense_adj, home, home_season_games)
    away_attack_adj, away_defense_adj = blend_with_prior(away_attack_adj, away_defense_adj, away, away_season_games)

    # ── Home/away factors ──
    if league in home_away_factors:
        hf = home_away_factors[league]['home_factor']
        af = home_away_factors[league]['away_factor']
        base_rate = home_away_factors[league]['base_rate']
    else:
        hf, af, base_rate = 1.0, 1.0, 1.35  # fallback

    # ── Rest adjustment ──
    def get_rest_factor(team, current_date):
        if team not in team_last_game:
            return REST_NORMAL
        days_rest = (pd.Timestamp(current_date) - pd.Timestamp(team_last_game[team])).days
        if days_rest <= 3:
            return REST_SHORT
        elif days_rest > 7:
            return REST_LONG
        return REST_NORMAL

    home_rest = get_rest_factor(home, game_date)
    away_rest = get_rest_factor(away, game_date)

    # ── PART 2: Lambda estimation ──
    lambda_home = home_attack_adj * away_defense_adj * hf * base_rate * home_rest
    lambda_away = away_attack_adj * home_defense_adj * af * base_rate * away_rest

    # Clamp lambdas to reasonable range
    lambda_home = np.clip(lambda_home, 0.3, 4.5)
    lambda_away = np.clip(lambda_away, 0.3, 4.5)

    # ── PART 3: Poisson grid ──
    max_goals = 10
    home_probs = poisson.pmf(np.arange(max_goals + 1), lambda_home)
    away_probs = poisson.pmf(np.arange(max_goals + 1), lambda_away)
    grid = np.outer(home_probs, away_probs)

    # Compute probabilities
    p_over_1_5 = 1.0 - grid[0, 0] - grid[1, 0] - grid[0, 1]

    p_under_2_5 = 0.0
    for h in range(max_goals + 1):
        for a in range(max_goals + 1):
            if h + a <= 2:
                p_under_2_5 += grid[h, a]
    p_over_2_5 = 1.0 - p_under_2_5

    p_under_3_5 = 0.0
    for h in range(max_goals + 1):
        for a in range(max_goals + 1):
            if h + a <= 3:
                p_under_3_5 += grid[h, a]
    p_over_3_5 = 1.0 - p_under_3_5

    expected_total = lambda_home + lambda_away

    results.append({
        'game_id': game_id,
        'game_date': game_date,
        'season_year': season,
        'league_id': league,
        'home_team': home,
        'away_team': away,
        'split': row['split'],
        'home_attack_adj': home_attack_adj,
        'home_defense_adj': home_defense_adj,
        'away_attack_adj': away_attack_adj,
        'away_defense_adj': away_defense_adj,
        'lambda_home': lambda_home,
        'lambda_away': lambda_away,
        'expected_total': expected_total,
        'p_over_1_5': p_over_1_5,
        'p_over_2_5': p_over_2_5,
        'p_over_3_5': p_over_3_5,
        'home_rest_factor': home_rest,
        'away_rest_factor': away_rest,
        'home_season_games': home_season_games,
        'away_season_games': away_season_games,
    })

    # ── Update histories ──
    home_xg_val = row['home_xg']
    away_xg_val = row['away_xg']

    # Home team: scored home_xg, allowed away_xg
    team_history[home].append((game_date, season, league, home_xg_val, away_xg_val))
    # Away team: scored away_xg, allowed home_xg
    team_history[away].append((game_date, season, league, away_xg_val, home_xg_val))

    # League history: each "entry" is one team's xg_scored
    league_history[league].append((game_date, season, home_xg_val))
    league_history[league].append((game_date, season, away_xg_val))

    # Update last game dates
    team_last_game[home] = game_date
    team_last_game[away] = game_date

    # Update season stats for prior-season tracking
    # When season changes for a team, save the final stats
    # We track per-team what the "current season" is
    for team in [home, away]:
        team_hist = team_history[team]
        if len(team_hist) >= 2:
            prev_season = team_hist[-2][1]
            curr_season = team_hist[-1][1]
            if prev_season != curr_season:
                # Season just changed — save prior season final
                prev_games = [h for h in team_hist[:-1] if h[1] == prev_season]
                if len(prev_games) >= 5:
                    # Compute final season attack/defense adj
                    scored = np.mean([h[3] for h in prev_games[-10:]])
                    allowed = np.mean([h[4] for h in prev_games[-10:]])
                    lg = prev_games[-1][2]
                    lg_games = [h for h in league_history[lg] if h[1] == prev_season]
                    if len(lg_games) > 0:
                        lg_avg = np.mean([h[2] for h in lg_games])
                        if lg_avg > 0:
                            team_prior_season_final[team] = (scored / lg_avg, allowed / lg_avg, prev_season)

tprint(f"  Done. Processed {len(results)} games.")

# ── PART 4: Merge with market data ───────────────────────────────────
tprint("\n=== PART 4: Merging with market data ===")

result_df = pd.DataFrame(results)

# Merge odds
result_df = result_df.merge(
    odds[['game_id', 'market_fair_p_over_2_5']],
    on='game_id', how='left'
)

# Merge actual results + prices
result_df = result_df.merge(
    canon[['game_id', 'over_price', 'under_price', 'regulation_total_90']],
    on='game_id', how='left'
)

# Edge and actual
result_df['edge'] = result_df['p_over_2_5'] - result_df['market_fair_p_over_2_5']
result_df['actual_over_2_5'] = (result_df['regulation_total_90'] > 2.5).astype(int)
result_df['market_error'] = result_df['actual_over_2_5'] - result_df['market_fair_p_over_2_5']

tprint(f"Total games with market: {result_df['market_fair_p_over_2_5'].notna().sum()}")
tprint(f"Split distribution:\n{result_df['split'].value_counts().to_string()}")

# ── PART 5: Evaluation ───────────────────────────────────────────────
tprint("\n" + "=" * 70)
tprint("=== PART 5: OOS EVALUATION (2024-25) ===")
tprint("=" * 70)

oos = result_df[result_df['split'] == 'oos'].copy()
oos = oos[oos['market_fair_p_over_2_5'].notna()].copy()
tprint(f"\nOOS games: {len(oos)}")
tprint(f"OOS actual O2.5 rate: {oos['actual_over_2_5'].mean():.4f}")
tprint(f"OOS avg p_over_2_5: {oos['p_over_2_5'].mean():.4f}")
tprint(f"OOS avg market_fair_p: {oos['market_fair_p_over_2_5'].mean():.4f}")

# ── Diagnostic 1: Calibration ──
tprint("\n--- Diagnostic 1: Calibration ---")

bins = [0, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 1.0]
labels = ['<0.40', '0.40-0.45', '0.45-0.50', '0.50-0.55', '0.55-0.60', '0.60-0.65', '0.65+']
oos['pred_bin'] = pd.cut(oos['p_over_2_5'], bins=bins, labels=labels, right=False)

tprint(f"\n{'Bucket':<12} {'N':>5} {'Avg Pred':>9} {'Actual':>8} {'Gap':>7}")
tprint("-" * 45)
for label in labels:
    bucket = oos[oos['pred_bin'] == label]
    if len(bucket) == 0:
        continue
    avg_pred = bucket['p_over_2_5'].mean()
    actual = bucket['actual_over_2_5'].mean()
    gap = actual - avg_pred
    tprint(f"{label:<12} {len(bucket):>5} {avg_pred:>9.4f} {actual:>8.4f} {gap:>+7.4f}")

# Platt calibration slope (logistic regression on OOS — diagnostic only)
from sklearn.linear_model import LogisticRegression
lr = LogisticRegression(C=1e10, solver='lbfgs', max_iter=1000)
X_cal = oos['p_over_2_5'].values.reshape(-1, 1)
y_cal = oos['actual_over_2_5'].values
lr.fit(X_cal, y_cal)
platt_slope = lr.coef_[0][0]
platt_intercept = lr.intercept_[0]
tprint(f"\nPlatt calibration slope: {platt_slope:.2f} (ideal=1.0)")
tprint(f"Platt intercept: {platt_intercept:.2f}")

# Brier score
brier = np.mean((oos['p_over_2_5'] - oos['actual_over_2_5']) ** 2)
tprint(f"Brier score: {brier:.4f}")

# Overall bias
bias_pp = (oos['p_over_2_5'].mean() - oos['actual_over_2_5'].mean()) * 100
tprint(f"Overall bias: {bias_pp:+.1f}pp")

# ── Diagnostic 2: Edge calibration ──
tprint("\n--- Diagnostic 2: Edge Calibration ---")

edge_bins = [-1, -0.06, -0.03, 0.00, 0.03, 0.06, 0.10, 1.0]
edge_labels = ['<=-0.06', '-0.06:-0.03', '-0.03:0.00', '0.00:0.03', '0.03:0.06', '0.06:0.10', '0.10+']
oos['edge_bin'] = pd.cut(oos['edge'], bins=edge_bins, labels=edge_labels, right=False)

tprint(f"\n{'Edge Bucket':<15} {'N':>5} {'Avg Edge':>9} {'Actual O2.5':>12} {'Avg Mkt Err':>12}")
tprint("-" * 58)
bucket_ranks = []
bucket_mkt_errs = []
for i, label in enumerate(edge_labels):
    bucket = oos[oos['edge_bin'] == label]
    if len(bucket) == 0:
        continue
    avg_edge = bucket['edge'].mean()
    actual_rate = bucket['actual_over_2_5'].mean()
    avg_mkt_err = bucket['market_error'].mean()
    tprint(f"{label:<15} {len(bucket):>5} {avg_edge:>+9.4f} {actual_rate:>12.4f} {avg_mkt_err:>+12.4f}")
    bucket_ranks.append(i)
    bucket_mkt_errs.append(avg_mkt_err)

from scipy.stats import spearmanr
if len(bucket_ranks) >= 3:
    spearman_corr, spearman_p = spearmanr(bucket_ranks, bucket_mkt_errs)
    tprint(f"\nSpearman correlation (edge bucket rank vs avg market error): {spearman_corr:.2f} (p={spearman_p:.3f})")
else:
    spearman_corr = float('nan')
    tprint("\nInsufficient buckets for Spearman correlation")

# ── Diagnostic 3A: Closing line test (thresholds 0.06/0.08/0.10) ──
tprint("\n--- Diagnostic 3A: Closing Line Test (V2.2 thresholds) ---")

def compute_roi(subset, side_col='bet_side'):
    """Compute ROI at actual odds and at -110"""
    if len(subset) == 0:
        return 0, 0, 0, 0

    overs = subset[subset[side_col] == 'OVER']
    unders = subset[subset[side_col] == 'UNDER']

    # ROI at actual odds
    total_wagered = len(subset)
    total_return = 0
    for _, r in subset.iterrows():
        if r[side_col] == 'OVER':
            price = r['over_price']
            won = r['actual_over_2_5'] == 1
        else:
            price = r['under_price']
            won = r['actual_over_2_5'] == 0
        if pd.notna(price) and price > 0:
            if won:
                total_return += price - 1  # net profit
            else:
                total_return -= 1  # lost stake
        else:
            total_wagered -= 1  # skip if no price

    roi_actual = (total_return / max(total_wagered, 1)) * 100

    # ROI at -110
    hit_count = 0
    valid = 0
    for _, r in subset.iterrows():
        if r[side_col] == 'OVER':
            hit = r['actual_over_2_5'] == 1
        else:
            hit = r['actual_over_2_5'] == 0
        hit_count += int(hit)
        valid += 1

    hit_rate = hit_count / max(valid, 1)
    roi_110 = (hit_rate * (1 + 100/110) - 1) * 100  # -110 payout

    return roi_actual, roi_110, hit_rate, total_wagered

THRESHOLD_A = 0.06

# Active bets
oos_active = oos[oos['edge'].abs() >= THRESHOLD_A].copy()
oos_active['bet_side'] = np.where(oos_active['edge'] > 0, 'OVER', 'UNDER')

# Tier assignment
def assign_tier(edge):
    ae = abs(edge)
    if ae >= 0.10:
        return 'HIGH'
    elif ae >= 0.08:
        return 'MEDIUM'
    else:
        return 'LOW'

oos_active['tier'] = oos_active['edge'].apply(assign_tier)

tprint(f"\nActive bets (|edge| >= {THRESHOLD_A}): {len(oos_active)}")

# Overall
roi_a, roi_110, hit, n_w = compute_roi(oos_active)
tprint(f"Overall: N={n_w}, hit={hit:.3f}, ROI@actual={roi_a:+.1f}%, ROI@-110={roi_110:+.1f}%")

# By tier
tprint("\nBy Tier:")
for tier in ['LOW', 'MEDIUM', 'HIGH']:
    sub = oos_active[oos_active['tier'] == tier]
    if len(sub) == 0:
        continue
    r_a, r_110, h, n = compute_roi(sub)
    tprint(f"  {tier}: N={n}, hit={h:.3f}, ROI@actual={r_a:+.1f}%, ROI@-110={r_110:+.1f}%")

# By league
tprint("\nBy League:")
league_rois_a = {}
for lg in active:
    sub = oos_active[oos_active['league_id'] == lg]
    if len(sub) == 0:
        continue
    r_a, r_110, h, n = compute_roi(sub)
    league_rois_a[lg] = r_a
    tprint(f"  {lg}: N={n}, hit={h:.3f}, ROI@actual={r_a:+.1f}%, ROI@-110={r_110:+.1f}%")

# MEDIUM only
med_only = oos_active[oos_active['tier'] == 'MEDIUM']
r_a_med, _, _, n_med = compute_roi(med_only)
tprint(f"\nMEDIUM-only: N={n_med}, ROI@actual={r_a_med:+.1f}%")

# BUN + MEDIUM
bun_med = oos_active[(oos_active['league_id'] == 'BUN') & (oos_active['tier'] == 'MEDIUM')]
if len(bun_med) > 0:
    r_a_bm, _, h_bm, n_bm = compute_roi(bun_med)
    tprint(f"BUN+MEDIUM: N={n_bm}, hit={h_bm:.3f}, ROI@actual={r_a_bm:+.1f}%")

# ── Diagnostic 3B: V3-native thresholds ──
tprint("\n--- Diagnostic 3B: V3-Native Thresholds (tuned on validation) ---")

val = result_df[result_df['split'] == 'validate'].copy()
val = val[val['market_fair_p_over_2_5'].notna()].copy()
tprint(f"Validation games: {len(val)}")

best_thresh = 0.06
best_roi = -999
best_n = 0

tprint(f"\n{'Threshold':>10} {'N':>5} {'Hit%':>7} {'ROI@-110':>10}")
tprint("-" * 36)
for thresh in np.arange(0.02, 0.16, 0.01):
    val_active = val[val['edge'].abs() >= thresh].copy()
    if len(val_active) < 30:
        continue
    val_active['bet_side'] = np.where(val_active['edge'] > 0, 'OVER', 'UNDER')

    hit_count = 0
    for _, r in val_active.iterrows():
        if r['bet_side'] == 'OVER':
            hit_count += int(r['actual_over_2_5'] == 1)
        else:
            hit_count += int(r['actual_over_2_5'] == 0)

    hit_rate = hit_count / len(val_active)
    roi_110 = (hit_rate * (1 + 100/110) - 1) * 100
    tprint(f"{thresh:>10.2f} {len(val_active):>5} {hit_rate:>7.3f} {roi_110:>+10.1f}%")

    if roi_110 > best_roi:
        best_roi = roi_110
        best_thresh = thresh
        best_n = len(val_active)

tprint(f"\nOptimal validation threshold: {best_thresh:.2f} (N={best_n}, ROI@-110={best_roi:+.1f}%)")

# Apply to OOS
oos_b = oos[oos['edge'].abs() >= best_thresh].copy()
oos_b['bet_side'] = np.where(oos_b['edge'] > 0, 'OVER', 'UNDER')
oos_b['tier'] = oos_b['edge'].apply(assign_tier)

tprint(f"\nOOS with V3-native threshold ({best_thresh:.2f}):")
roi_b_a, roi_b_110, hit_b, n_b = compute_roi(oos_b)
tprint(f"  Overall: N={n_b}, hit={hit_b:.3f}, ROI@actual={roi_b_a:+.1f}%, ROI@-110={roi_b_110:+.1f}%")

league_rois_b = {}
for lg in active:
    sub = oos_b[oos_b['league_id'] == lg]
    if len(sub) == 0:
        continue
    r_a, r_110, h, n = compute_roi(sub)
    league_rois_b[lg] = r_a
    tprint(f"  {lg}: N={n}, hit={h:.3f}, ROI@actual={r_a:+.1f}%")

# MEDIUM B
med_b = oos_b[oos_b['tier'] == 'MEDIUM']
if len(med_b) > 0:
    r_a_med_b, _, _, n_med_b = compute_roi(med_b)
else:
    r_a_med_b, n_med_b = 0, 0

# ── Diagnostic 4: Edge overstatement ──
tprint("\n--- Diagnostic 4: Edge Overstatement ---")

# Version A
over_bets_a = oos_active[oos_active['bet_side'] == 'OVER']
if len(over_bets_a) > 0:
    claimed_edge_a = (over_bets_a['p_over_2_5'] - over_bets_a['market_fair_p_over_2_5']).mean()
    actual_edge_a = (over_bets_a['actual_over_2_5'] - over_bets_a['market_fair_p_over_2_5']).mean()
    if actual_edge_a != 0:
        overstatement_a = claimed_edge_a / actual_edge_a
    else:
        overstatement_a = float('inf')
    tprint(f"\nVersion A (threshold={THRESHOLD_A}):")
    tprint(f"  OVER bets: N={len(over_bets_a)}")
    tprint(f"  Mean claimed edge: {claimed_edge_a:.4f}")
    tprint(f"  Mean actual edge:  {actual_edge_a:.4f}")
    tprint(f"  Overstatement: {overstatement_a:.1f}x")
else:
    overstatement_a = float('nan')

# Version B
over_bets_b = oos_b[oos_b['bet_side'] == 'OVER']
if len(over_bets_b) > 0:
    claimed_edge_b = (over_bets_b['p_over_2_5'] - over_bets_b['market_fair_p_over_2_5']).mean()
    actual_edge_b = (over_bets_b['actual_over_2_5'] - over_bets_b['market_fair_p_over_2_5']).mean()
    if actual_edge_b != 0:
        overstatement_b = claimed_edge_b / actual_edge_b
    else:
        overstatement_b = float('inf')
    tprint(f"\nVersion B (threshold={best_thresh}):")
    tprint(f"  OVER bets: N={len(over_bets_b)}")
    tprint(f"  Mean claimed edge: {claimed_edge_b:.4f}")
    tprint(f"  Mean actual edge:  {actual_edge_b:.4f}")
    tprint(f"  Overstatement: {overstatement_b:.1f}x")
else:
    overstatement_b = float('nan')

# ── PART 6: Comparison table ──
tprint("\n" + "=" * 70)
tprint("=== PART 6: Comparison Table ===")
tprint("=" * 70)

# Collect V3 metrics
v3a_overall_roi = roi_a
v3b_overall_roi = roi_b_a
v3a_bun_roi = league_rois_a.get('BUN', float('nan'))
v3b_bun_roi = league_rois_b.get('BUN', float('nan'))
v3a_epl_roi = league_rois_a.get('EPL', float('nan'))
v3b_epl_roi = league_rois_b.get('EPL', float('nan'))
v3a_lg1_roi = league_rois_a.get('LG1', float('nan'))
v3b_lg1_roi = league_rois_b.get('LG1', float('nan'))
v3a_sea_roi = league_rois_a.get('SEA', float('nan'))
v3b_sea_roi = league_rois_b.get('SEA', float('nan'))

def fmt(v, suffix=''):
    if pd.isna(v) or v == float('inf') or v == float('-inf'):
        return 'N/A'
    if suffix == '%':
        return f"{v:+.1f}%"
    elif suffix == 'x':
        return f"{v:.1f}x"
    elif suffix == 'pp':
        return f"{v:+.1f}"
    else:
        return f"{v:.2f}"

table = f"""
| Metric                    | V2.2     | V2.2b    | V3 (A)    | V3 (B)    |
|---------------------------|----------|----------|-----------|-----------|
| Calibration slope         | 0.64     | 0.99     | {platt_slope:.2f}      | {platt_slope:.2f}      |
| Overall bias (pp)         | -3.8     | -4.2     | {fmt(bias_pp, 'pp'):>9} | {fmt(bias_pp, 'pp'):>9} |
| Brier score               | 0.2393   | 0.2391   | {brier:.4f}    | {brier:.4f}    |
| Spearman (edge->mkt err)  | 0.93     | 0.36     | {fmt(spearman_corr):>9} | {fmt(spearman_corr):>9} |
| Edge overstatement        | 4.4x     | 6.8x     | {fmt(overstatement_a, 'x'):>9} | {fmt(overstatement_b, 'x'):>9} |
| Overall ROI @ actual      | -1.3%    | -2.9%    | {fmt(v3a_overall_roi, '%'):>9} | {fmt(v3b_overall_roi, '%'):>9} |
| BUN ROI @ actual          | +7.5%    | +7.1%    | {fmt(v3a_bun_roi, '%'):>9} | {fmt(v3b_bun_roi, '%'):>9} |
| EPL ROI @ actual          | -4.9%    | -2.0%    | {fmt(v3a_epl_roi, '%'):>9} | {fmt(v3b_epl_roi, '%'):>9} |
| LG1 ROI @ actual          | -3.0%    | +1.8%    | {fmt(v3a_lg1_roi, '%'):>9} | {fmt(v3b_lg1_roi, '%'):>9} |
| SEA ROI @ actual          | -9.2%    | -46.4%   | {fmt(v3a_sea_roi, '%'):>9} | {fmt(v3b_sea_roi, '%'):>9} |
| MEDIUM ROI @ actual       | +10.1%   | -3.7%    | {fmt(r_a_med, '%'):>9} | {fmt(r_a_med_b, '%'):>9} |
| N active bets             | 413      | 357      | {len(oos_active):>9} | {n_b:>9} |
"""
tprint(table)

# ── PART 7: Decision gate ──
tprint("=" * 70)
tprint("=== PART 7: Decision Gate ===")
tprint("=" * 70)

# Use best version (A or B) for gate
best_bun = max(v3a_bun_roi if not pd.isna(v3a_bun_roi) else -999,
               v3b_bun_roi if not pd.isna(v3b_bun_roi) else -999)
best_overstatement = min(
    overstatement_a if not (pd.isna(overstatement_a) or overstatement_a == float('inf')) else 999,
    overstatement_b if not (pd.isna(overstatement_b) or overstatement_b == float('inf')) else 999
)

gate1 = best_bun > 7.1
gate2 = platt_slope >= 0.85
gate3 = best_overstatement < 2.0

tprint(f"\n1. BUN ROI > V2.2b (+7.1%): best={fmt(best_bun, '%')} -> {'PASS' if gate1 else 'FAIL'}")
tprint(f"2. Calibration slope >= 0.85: slope={platt_slope:.2f} -> {'PASS' if gate2 else 'FAIL'}")
tprint(f"3. Edge overstatement < 2x: best={fmt(best_overstatement, 'x')} -> {'PASS' if gate3 else 'FAIL'}")

if gate1 and gate2 and gate3:
    verdict = "ADVANCE V3"
else:
    verdict = "V2.2b REMAINS CHALLENGER"

tprint(f"\nFinal verdict: {verdict}")

# ── PART 8: Save outputs ─────────────────────────────────────────────
tprint("\n=== PART 8: Saving outputs ===")

# V3 parameters
params = {
    'home_away_factors': home_away_factors,
    'league_base_rates': league_base_rates,
    'rest_adjustments': {
        'short_rest_lte_3d': REST_SHORT,
        'normal_rest_4_7d': REST_NORMAL,
        'long_rest_gt_7d': REST_LONG,
    },
    'rolling_window': 10,
    'max_goals_grid': 10,
    'threshold_a': THRESHOLD_A,
    'threshold_b': float(best_thresh),
    'active_leagues': active,
}
with open('soccer/models/v3/v3_parameters.json', 'w') as f:
    json.dump(params, f, indent=2)
tprint("Saved: soccer/models/v3/v3_parameters.json")

# OOS predictions
oos_save = oos[['game_id', 'game_date', 'season_year', 'league_id', 'home_team', 'away_team',
                'lambda_home', 'lambda_away', 'expected_total', 'p_over_1_5', 'p_over_2_5', 'p_over_3_5',
                'market_fair_p_over_2_5', 'edge', 'actual_over_2_5', 'regulation_total_90',
                'over_price', 'under_price', 'home_attack_adj', 'home_defense_adj',
                'away_attack_adj', 'away_defense_adj']].copy()
oos_save.to_parquet('soccer/models/v3/v3_predictions_oos.parquet', index=False)
tprint("Saved: soccer/models/v3/v3_predictions_oos.parquet")

# Evaluation markdown
eval_md = "# Soccer V3 Poisson Challenger Model — Evaluation\n\n"
eval_md += f"Generated: 2026-03-28\n\n"
eval_md += "## Model Description\n\n"
eval_md += "Independent Poisson simulation model using rolling 10-game team attack/defense strengths,\n"
eval_md += "league-level home/away factors, early-season prior blending, and rest adjustments.\n"
eval_md += "xG-based where available, falling back to actual goals.\n\n"
eval_md += "## Diagnostics\n\n"
eval_md += "".join(output_lines[output_lines.index([l for l in output_lines if 'PART 5' in l][0]):])
eval_md += f"\n\n## Verdict\n\n**{verdict}**\n"

with open('soccer/research/v3_evaluation.md', 'w') as f:
    f.write(eval_md)
tprint("Saved: soccer/research/v3_evaluation.md")

tprint("\nDone!")
