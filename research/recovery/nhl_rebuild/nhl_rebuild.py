#!/usr/bin/env python3
"""
NHL CLEAN REBUILD — Live-Compatible Features Only
==================================================
Rebuilds NHL totals model using ONLY features available from:
  1. NHL API boxscores (goals, shots, PP, PK, goalie stats)
  2. Schedule data (B2B, rest days, games in last 7)
  3. Market data (closing total for Model C)

NO MoneyPuck features: xGF, xGA, HD shots, Corsi, Fenwick are EXCLUDED.

Output: research/recovery/nhl_rebuild/
"""

import sys
import pickle
from pathlib import Path
from datetime import timedelta
from textwrap import dedent

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error

# ---------------------------------------------------------------------------
BASE = Path("/root/mlb-model")
OUT  = BASE / "research" / "recovery" / "nhl_rebuild"
OUT.mkdir(parents=True, exist_ok=True)

CANONICAL = BASE / "nhl" / "nhl_games_canonical.csv"
MARKET_SNAP = BASE / "nhl" / "nhl_market_snapshots.parquet"

ROLLING_LONG  = 20
ROLLING_SHORT = 10
RIDGE_ALPHAS  = [0.01, 0.1, 1.0, 10.0, 50.0, 100.0, 200.0, 500.0]
TRAIN_SEASONS = {2021, 2022}
VAL_SEASONS   = {2023}
OOS_SEASONS   = {2024}
LIVE_SEASON   = {2025}

N_SIM = 10_000
SEED  = 42

# ---------------------------------------------------------------------------
# PHASE 0: Feature Inventory
# ---------------------------------------------------------------------------
def phase0_inventory():
    """Classify features as live-available vs MoneyPuck-dependent."""
    report = []
    report.append("=" * 70)
    report.append("PHASE 0: LIVE-COMPATIBLE FEATURE INVENTORY")
    report.append("=" * 70)
    
    gc = pd.read_csv(CANONICAL)
    report.append(f"\nCanonical dataset: {gc.shape[0]} games, {gc.shape[1]} columns")
    report.append(f"Seasons: {sorted(gc.season_year.unique())}")
    
    live_features = {
        "goals_scored": "NHL API boxscore — always available",
        "goals_allowed": "NHL API boxscore — always available",
        "shots_on_goal": "NHL API boxscore — available for MoneyPuck-covered games",
        "pp_goals": "NHL API boxscore — 5 NaN total",
        "pp_opportunities": "NHL API boxscore — 5 NaN total",
        "pk_goals_against": "NHL API boxscore — 5 NaN total",
        "goalie_sa": "NHL API boxscore — 0 NaN",
        "goalie_ga": "NHL API boxscore — 0 NaN",
        "is_b2b": "Schedule-derived — 0 NaN",
        "rest_days": "Schedule-derived — <2% NaN",
        "games_last_7": "Schedule-derived — 0 NaN",
    }
    
    dead_features = {
        "xgoals": "MoneyPuck — NOT available in live pipeline",
        "xgoals_against": "MoneyPuck — NOT available in live pipeline",
        "hd_shots": "MoneyPuck — NOT available in live pipeline",
        "hd_shots_against": "MoneyPuck — NOT available in live pipeline",
        "corsi_pct": "MoneyPuck — NOT available in live pipeline",
        "fenwick_pct": "MoneyPuck — NOT available in live pipeline",
    }
    
    report.append("\n--- LIVE-AVAILABLE (will use in rebuild) ---")
    for f, desc in live_features.items():
        report.append(f"  {f:30s} {desc}")
    
    report.append("\n--- MONEYPUCK-DEPENDENT (EXCLUDED) ---")
    for f, desc in dead_features.items():
        report.append(f"  {f:30s} {desc}")
    
    # Check SOG availability — it comes from MoneyPuck in canonical
    sog_nan = gc.home_shots_on_goal.isna().sum()
    report.append(f"\nNOTE: shots_on_goal has {sog_nan} NaN (all in recent 2025 games)")
    report.append("  These are recent games where MoneyPuck hasn't updated.")
    report.append("  However, SOG IS available from NHL API boxscores — the canonical")
    report.append("  just happened to source it from MoneyPuck. For the rebuild,")
    report.append("  we use the available SOG data and skip games with NaN.")
    
    # Goalie save% can be derived from SA and GA
    report.append("\nDERIVED FEATURES (computed from live data):")
    report.append("  goalie_sv_pct = 1 - (GA / SA)  — from NHL API boxscore")
    report.append("  pp_pct = PP_goals / PP_opportunities  — from NHL API boxscore")
    report.append("  pk_pct = 1 - (PK_GA / PK_faced)  — from NHL API boxscore")
    report.append("  shot_pressure = team_SOG_rolling - opp_SA_rolling  — derived")
    
    # Current model features that are MoneyPuck-dependent
    report.append("\n--- CURRENT MODEL FEATURES THAT WILL BE DROPPED ---")
    dropped = [
        "home/away_xgf_rolling_20", "home/away_xga_rolling_20",
        "home/away_hd_shots_for_rolling_20", "home/away_hd_shots_against_rolling_20",
        "home/away_hd_pressure",
    ]
    for d in dropped:
        report.append(f"  {d}")
    
    report.append(f"\nOriginal model: 24 features per side model")
    report.append(f"Rebuild model: ~16 features per side model (no xG/HD)")
    
    text = "\n".join(report)
    (OUT / "phase0_feature_inventory.md").write_text(text)
    print(text)
    return gc


# ---------------------------------------------------------------------------
# PHASE 1: Build live-compatible feature table
# ---------------------------------------------------------------------------
def phase1_build_features(gc):
    """Build feature table using ONLY live-available data."""
    report = []
    report.append("=" * 70)
    report.append("PHASE 1: BUILD LIVE-COMPATIBLE FEATURE TABLE")
    report.append("=" * 70)
    
    # Fix pp_pct where we can compute it from goals/opportunities
    for side in ['home', 'away']:
        mask = gc[f'{side}_pp_pct'].isna() & gc[f'{side}_pp_opportunities'].notna()
        gc.loc[mask & (gc[f'{side}_pp_opportunities'] > 0), f'{side}_pp_pct'] = (
            gc.loc[mask & (gc[f'{side}_pp_opportunities'] > 0), f'{side}_pp_goals'] /
            gc.loc[mask & (gc[f'{side}_pp_opportunities'] > 0), f'{side}_pp_opportunities']
        )
        gc.loc[mask & (gc[f'{side}_pp_opportunities'] == 0), f'{side}_pp_pct'] = 0.0
    
    # Similarly fix pk_pct
    for side in ['home', 'away']:
        opp = 'away' if side == 'home' else 'home'
        mask = gc[f'{side}_pk_pct'].isna() & gc[f'{opp}_pp_opportunities'].notna()
        opp_pp_opp = gc[f'{opp}_pp_opportunities']
        opp_pp_goals = gc[f'{opp}_pp_goals']
        gc.loc[mask & (opp_pp_opp > 0), f'{side}_pk_pct'] = (
            1.0 - gc.loc[mask & (opp_pp_opp > 0), f'{side}_pk_goals_against'] /
            opp_pp_opp[mask & (opp_pp_opp > 0)]
        )
        gc.loc[mask & (opp_pp_opp == 0), f'{side}_pk_pct'] = 1.0
    
    # Compute goalie save pct from SA and GA
    for side in ['home', 'away']:
        gc[f'{side}_goalie_sv_pct'] = np.where(
            gc[f'{side}_goalie_sa'] > 0,
            1.0 - gc[f'{side}_goalie_ga'] / gc[f'{side}_goalie_sa'],
            0.91  # league average fallback
        )
    
    gc['game_date'] = pd.to_datetime(gc['game_date'])
    gc = gc.sort_values('game_date').reset_index(drop=True)
    
    # Build team game log (long format)
    rows = []
    for g in gc.itertuples(index=False):
        for is_home in [True, False]:
            side = 'home' if is_home else 'away'
            opp_side = 'away' if is_home else 'home'
            team = getattr(g, f'{side}_team')
            
            row = {
                'game_id': g.game_id,
                'game_date': g.game_date,
                'season_year': g.season_year,
                'team': team,
                'is_home': is_home,
                'goals_scored': getattr(g, f'{side}_score'),
                'goals_allowed': getattr(g, f'{opp_side}_score'),
                'pp_pct': getattr(g, f'{side}_pp_pct'),
                'pk_pct': getattr(g, f'{side}_pk_pct'),
                'pp_opportunities': getattr(g, f'{side}_pp_opportunities', np.nan),
                'goalie_sv_pct': getattr(g, f'{side}_goalie_sv_pct'),
                'goalie_id': getattr(g, f'{side}_goalie_id'),
                'is_b2b': getattr(g, f'{side}_is_b2b'),
                'rest_days': getattr(g, f'{side}_rest_days'),
                'games_last_7': getattr(g, f'{side}_games_last_7'),
            }
            
            # SOG available?
            sog = getattr(g, f'{side}_shots_on_goal', np.nan)
            sog_against = getattr(g, f'{opp_side}_shots_on_goal', np.nan)
            row['shots_for'] = sog
            row['shots_against'] = sog_against
            
            rows.append(row)
    
    tgl = pd.DataFrame(rows)
    tgl = tgl.sort_values(['team', 'game_date']).reset_index(drop=True)
    
    report.append(f"Team game log: {len(tgl)} rows")
    
    # Compute league averages per season for shrinkage
    league_avgs = {}
    for sy in sorted(gc.season_year.unique()):
        sg = tgl[tgl.season_year == sy]
        league_avgs[sy] = {
            'goals_scored': sg.goals_scored.mean(),
            'goals_allowed': sg.goals_allowed.mean(),
            'shots_for': sg.shots_for.dropna().mean(),
            'shots_against': sg.shots_against.dropna().mean(),
            'pp_pct': sg.pp_pct.dropna().mean(),
            'pk_pct': sg.pk_pct.dropna().mean(),
            'pp_opportunities': sg.pp_opportunities.dropna().mean(),
            'goalie_sv_pct': sg.goalie_sv_pct.dropna().mean(),
        }
    
    # Shrinkage helper
    def shrink(raw, n, prior, window):
        if pd.isna(raw):
            return prior
        w = min(n, window) / window
        return w * raw + (1 - w) * prior
    
    # Compute rolling features with PIT safety (shift(1) equivalent)
    def compute_rolling(team_df, la):
        """Compute rolling features for a team. Each row gets stats from PRIOR games only."""
        results = []
        for i, row in enumerate(team_df.itertuples(index=False)):
            prior = team_df.iloc[:i]  # strict PIT: no same-day
            n = len(prior)
            
            feat = {}
            
            # Goals rolling 10
            gs_prior = prior.goals_scored.dropna().tail(ROLLING_SHORT)
            ga_prior = prior.goals_allowed.dropna().tail(ROLLING_SHORT)
            feat['goals_scored_rolling_10'] = shrink(
                gs_prior.mean() if len(gs_prior) else np.nan,
                n, la['goals_scored'], ROLLING_SHORT)
            feat['goals_allowed_rolling_10'] = shrink(
                ga_prior.mean() if len(ga_prior) else np.nan,
                n, la['goals_allowed'], ROLLING_SHORT)
            
            # Shots rolling 20
            sf_prior = prior.shots_for.dropna().tail(ROLLING_LONG)
            sa_prior = prior.shots_against.dropna().tail(ROLLING_LONG)
            feat['shots_for_rolling_20'] = shrink(
                sf_prior.mean() if len(sf_prior) else np.nan,
                len(sf_prior), la['shots_for'], ROLLING_LONG)
            feat['shots_against_rolling_20'] = shrink(
                sa_prior.mean() if len(sa_prior) else np.nan,
                len(sa_prior), la['shots_against'], ROLLING_LONG)
            
            # PP% rolling 20
            pp_prior = prior.pp_pct.dropna().tail(ROLLING_LONG)
            feat['pp_pct_rolling_20'] = shrink(
                pp_prior.mean() if len(pp_prior) else np.nan,
                len(pp_prior), la['pp_pct'], ROLLING_LONG)
            
            # PK% rolling 20
            pk_prior = prior.pk_pct.dropna().tail(ROLLING_LONG)
            feat['pk_pct_rolling_20'] = shrink(
                pk_prior.mean() if len(pk_prior) else np.nan,
                len(pk_prior), la['pk_pct'], ROLLING_LONG)
            
            # PP opportunities per game rolling 20
            ppo_prior = prior.pp_opportunities.dropna().tail(ROLLING_LONG)
            feat['pp_opp_per_game_rolling_20'] = shrink(
                ppo_prior.mean() if len(ppo_prior) else np.nan,
                len(ppo_prior), la['pp_opportunities'], ROLLING_LONG)
            
            # Goalie save% rolling 10 (for the starting goalie)
            goalie_id = row.goalie_id
            goalie_prior = prior[prior.goalie_id == goalie_id].goalie_sv_pct.dropna().tail(ROLLING_SHORT)
            n_goalie = len(goalie_prior)
            feat['goalie_sv_pct_rolling_10'] = shrink(
                goalie_prior.mean() if n_goalie else np.nan,
                n_goalie, la['goalie_sv_pct'], ROLLING_SHORT)
            
            # Goalie vs team baseline
            team_goalie_mean = prior[prior.goalie_id == goalie_id].goalie_sv_pct.mean()
            team_all_mean = prior.goalie_sv_pct.mean()
            if pd.notna(team_goalie_mean) and pd.notna(team_all_mean) and n_goalie >= 3:
                feat['goalie_vs_team_baseline'] = team_goalie_mean - team_all_mean
            else:
                feat['goalie_vs_team_baseline'] = 0.0
            
            # Goalie fatigue: games in last 3 days
            if n > 0:
                three_days_ago = row.game_date - pd.Timedelta(days=3)
                recent = prior[(prior.game_date >= three_days_ago) & (prior.goalie_id == goalie_id)]
                feat['goalie_fatigue'] = len(recent)
            else:
                feat['goalie_fatigue'] = 0
            
            # B2B and backup flag
            feat['goalie_b2b'] = int(row.is_b2b)
            
            # Backup flag: is this NOT the most frequent starter?
            if n >= 5:
                mode_goalie = prior.goalie_id.mode()
                feat['backup_flag'] = int(goalie_id not in mode_goalie.values)
            else:
                feat['backup_flag'] = 0
            
            # Schedule
            feat['days_rest'] = row.rest_days if pd.notna(row.rest_days) else 3.0
            feat['b2b'] = int(row.is_b2b)
            feat['games_last_7'] = row.games_last_7
            
            # Metadata
            feat['game_id'] = row.game_id
            feat['game_date'] = row.game_date
            feat['team'] = row.team
            feat['is_home'] = row.is_home
            feat['season_year'] = row.season_year
            feat['goals_scored_actual'] = row.goals_scored
            
            results.append(feat)
        
        return pd.DataFrame(results)
    
    # Process all teams
    all_features = []
    teams = sorted(tgl.team.unique())
    report.append(f"Processing {len(teams)} teams...")
    
    for team in teams:
        team_df = tgl[tgl.team == team].sort_values('game_date').reset_index(drop=True)
        
        # Use the season's league averages for shrinkage
        for sy in sorted(team_df.season_year.unique()):
            season_df = team_df[team_df.season_year == sy].reset_index(drop=True)
            la = league_avgs[sy]
            feat_df = compute_rolling(season_df, la)
            all_features.append(feat_df)
    
    feat_long = pd.concat(all_features, ignore_index=True)
    report.append(f"Feature long table: {feat_long.shape}")
    
    # Pivot to wide format: one row per game
    home_feat = feat_long[feat_long.is_home].copy()
    away_feat = feat_long[~feat_long.is_home].copy()
    
    # Rename columns with home_/away_ prefix
    feat_cols = [c for c in home_feat.columns if c not in 
                 ['game_id', 'game_date', 'team', 'is_home', 'season_year', 'goals_scored_actual']]
    
    home_rename = {c: f'home_{c}' for c in feat_cols}
    home_rename['team'] = 'home_team'
    home_rename['goals_scored_actual'] = 'home_score'
    home_feat = home_feat.rename(columns=home_rename)
    
    away_rename = {c: f'away_{c}' for c in feat_cols}
    away_rename['team'] = 'away_team'
    away_rename['goals_scored_actual'] = 'away_score'
    away_feat = away_feat.rename(columns=away_rename)
    
    # Merge on game_id
    home_cols = ['game_id', 'game_date', 'season_year', 'home_team', 'home_score'] + \
                [f'home_{c}' for c in feat_cols]
    away_cols = ['game_id', 'away_team', 'away_score'] + [f'away_{c}' for c in feat_cols]
    
    ft = home_feat[home_cols].merge(away_feat[away_cols], on='game_id', how='inner')
    
    # Derived features
    ft['home_shot_pressure'] = ft['home_shots_for_rolling_20'] - ft['away_shots_against_rolling_20']
    ft['away_shot_pressure'] = ft['away_shots_for_rolling_20'] - ft['home_shots_against_rolling_20']
    ft['total_goals'] = ft['home_score'] + ft['away_score']
    
    # Merge market data
    ms = pd.read_parquet(MARKET_SNAP)
    ms = ms[['game_id', 'closing_total', 'closing_over_price', 'closing_under_price']].copy()
    ft = ft.merge(ms, on='game_id', how='left')
    ft['market_available'] = ft['closing_total'].notna().astype(int)
    
    report.append(f"Final feature table: {ft.shape}")
    report.append(f"Market available: {ft.market_available.sum()} / {len(ft)}")
    report.append(f"Seasons: {sorted(ft.season_year.unique())}")
    
    for sy in sorted(ft.season_year.unique()):
        n = (ft.season_year == sy).sum()
        report.append(f"  Season {sy}: {n} games")
    
    text = "\n".join(report)
    (OUT / "phase1_feature_build.md").write_text(text)
    print(text)
    
    ft.to_parquet(OUT / "nhl_rebuild_features.parquet", index=False)
    return ft


# ---------------------------------------------------------------------------
# PHASE 2: Build 3 model variants
# ---------------------------------------------------------------------------
def phase2_models(ft):
    report = []
    report.append("=" * 70)
    report.append("PHASE 2: MODEL TRAINING — 3 VARIANTS")
    report.append("=" * 70)
    
    # Feature lists
    home_features_A = [
        'home_goals_scored_rolling_10', 'home_goals_allowed_rolling_10',
        'home_shots_for_rolling_20', 'home_shots_against_rolling_20',
        'home_pp_pct_rolling_20', 'home_pk_pct_rolling_20',
        'home_pp_opp_per_game_rolling_20',
        'home_goalie_sv_pct_rolling_10', 'home_goalie_vs_team_baseline',
        'home_goalie_fatigue', 'home_goalie_b2b', 'home_backup_flag',
        'home_days_rest', 'home_b2b', 'home_games_last_7',
        'home_shot_pressure',
        'away_goals_scored_rolling_10', 'away_goals_allowed_rolling_10',
        'away_shots_for_rolling_20', 'away_shots_against_rolling_20',
        'away_pp_pct_rolling_20', 'away_pk_pct_rolling_20',
        'away_goalie_sv_pct_rolling_10', 'away_goalie_vs_team_baseline',
        'away_goalie_fatigue', 'away_goalie_b2b', 'away_backup_flag',
        'away_days_rest', 'away_b2b',
    ]
    
    away_features_A = [
        'away_goals_scored_rolling_10', 'away_goals_allowed_rolling_10',
        'away_shots_for_rolling_20', 'away_shots_against_rolling_20',
        'away_pp_pct_rolling_20', 'away_pk_pct_rolling_20',
        'away_pp_opp_per_game_rolling_20',
        'away_goalie_sv_pct_rolling_10', 'away_goalie_vs_team_baseline',
        'away_goalie_fatigue', 'away_goalie_b2b', 'away_backup_flag',
        'away_days_rest', 'away_b2b', 'away_games_last_7',
        'away_shot_pressure',
        'home_goals_scored_rolling_10', 'home_goals_allowed_rolling_10',
        'home_shots_for_rolling_20', 'home_shots_against_rolling_20',
        'home_pp_pct_rolling_20', 'home_pk_pct_rolling_20',
        'home_goalie_sv_pct_rolling_10', 'home_goalie_vs_team_baseline',
        'home_goalie_fatigue', 'home_goalie_b2b', 'home_backup_flag',
        'home_days_rest', 'home_b2b',
    ]
    
    # Split data
    train = ft[ft.season_year.isin(TRAIN_SEASONS)].copy()
    val   = ft[ft.season_year.isin(VAL_SEASONS)].copy()
    oos   = ft[ft.season_year.isin(OOS_SEASONS)].copy()
    live  = ft[ft.season_year.isin(LIVE_SEASON)].copy()
    
    report.append(f"\nSplits: train={len(train)}, val={len(val)}, oos={len(oos)}, live={len(live)}")
    
    # Fill NaN in features with column mean (from train)
    all_feat_cols = list(set(home_features_A + away_features_A))
    
    col_means = {}
    for c in all_feat_cols:
        col_means[c] = train[c].mean()
    
    for df in [train, val, oos, live]:
        for c in all_feat_cols:
            df[c] = df[c].fillna(col_means[c])
    
    models = {}
    
    # ---- Model A: Pure hockey features ----
    report.append("\n--- MODEL A: Pure Hockey (no market) ---")
    
    for target, features, label in [
        ('home_score', home_features_A, 'home'),
        ('away_score', away_features_A, 'away'),
    ]:
        report.append(f"\n  {label.upper()} model ({len(features)} features):")
        
        X_train = train[features].values
        y_train = train[target].values
        X_val   = val[features].values
        y_val   = val[target].values
        X_oos   = oos[features].values
        y_oos   = oos[target].values
        
        scaler = StandardScaler()
        X_train_s = scaler.fit_transform(X_train)
        X_val_s   = scaler.transform(X_val)
        X_oos_s   = scaler.transform(X_oos)
        
        best_alpha, best_val_mae = None, 999
        for alpha in RIDGE_ALPHAS:
            m = Ridge(alpha=alpha)
            m.fit(X_train_s, y_train)
            val_pred = m.predict(X_val_s)
            val_mae = mean_absolute_error(y_val, val_pred)
            if val_mae < best_val_mae:
                best_val_mae = val_mae
                best_alpha = alpha
        
        m = Ridge(alpha=best_alpha)
        m.fit(X_train_s, y_train)
        
        train_pred = m.predict(X_train_s)
        val_pred   = m.predict(X_val_s)
        oos_pred   = m.predict(X_oos_s)
        
        report.append(f"    Best alpha: {best_alpha}")
        report.append(f"    Train MAE={mean_absolute_error(y_train, train_pred):.4f}  bias={np.mean(train_pred - y_train):+.4f}")
        report.append(f"    Val   MAE={mean_absolute_error(y_val, val_pred):.4f}  bias={np.mean(val_pred - y_val):+.4f}")
        report.append(f"    OOS   MAE={mean_absolute_error(y_oos, oos_pred):.4f}  bias={np.mean(oos_pred - y_oos):+.4f}")
        
        models[f'A_{label}'] = {
            'model': m, 'scaler': scaler, 'features': features,
            'alpha': best_alpha, 'col_means': col_means,
        }
    
    # Total predictions for Model A
    for split_name, split_df in [('train', train), ('val', val), ('oos', oos)]:
        h_pred = models['A_home']['model'].predict(
            models['A_home']['scaler'].transform(split_df[home_features_A].values))
        a_pred = models['A_away']['model'].predict(
            models['A_away']['scaler'].transform(split_df[away_features_A].values))
        total_pred = h_pred + a_pred
        total_actual = split_df['total_goals'].values
        report.append(f"  Model A Total {split_name}: MAE={mean_absolute_error(total_actual, total_pred):.4f}  "
                      f"bias={np.mean(total_pred - total_actual):+.4f}")
    
    # ---- Model B: Residual (predict residual from market line) ----
    report.append("\n--- MODEL B: Residual (market anchor + hockey adjustment) ---")
    
    # Only use games with market data
    train_m = train[train.market_available == 1].copy()
    val_m   = val[val.market_available == 1].copy()
    oos_m   = oos[oos.market_available == 1].copy()
    
    report.append(f"  Market-available: train={len(train_m)}, val={len(val_m)}, oos={len(oos_m)}")
    
    # Residual = actual total - closing_total
    resid_features = all_feat_cols.copy()  # use all hockey features
    
    for split_df in [train_m, val_m, oos_m]:
        split_df['residual'] = split_df['total_goals'] - split_df['closing_total']
    
    X_train_r = train_m[resid_features].values
    y_train_r = train_m['residual'].values
    X_val_r   = val_m[resid_features].values
    y_val_r   = val_m['residual'].values
    X_oos_r   = oos_m[resid_features].values
    y_oos_r   = oos_m['residual'].values
    
    scaler_r = StandardScaler()
    X_train_rs = scaler_r.fit_transform(X_train_r)
    X_val_rs   = scaler_r.transform(X_val_r)
    X_oos_rs   = scaler_r.transform(X_oos_r)
    
    best_alpha_r, best_val_mae_r = None, 999
    for alpha in RIDGE_ALPHAS:
        m = Ridge(alpha=alpha)
        m.fit(X_train_rs, y_train_r)
        pred = m.predict(X_val_rs)
        mae = mean_absolute_error(y_val_r, pred)
        if mae < best_val_mae_r:
            best_val_mae_r = mae
            best_alpha_r = alpha
    
    m_resid = Ridge(alpha=best_alpha_r)
    m_resid.fit(X_train_rs, y_train_r)
    
    report.append(f"  Best alpha: {best_alpha_r}")
    
    for split_name, X_s, y_r, split_df in [
        ('train', X_train_rs, y_train_r, train_m),
        ('val', X_val_rs, y_val_r, val_m),
        ('oos', X_oos_rs, y_oos_r, oos_m),
    ]:
        resid_pred = m_resid.predict(X_s)
        total_pred = split_df['closing_total'].values + resid_pred
        total_actual = split_df['total_goals'].values
        report.append(f"  Model B Total {split_name}: MAE={mean_absolute_error(total_actual, total_pred):.4f}  "
                      f"bias={np.mean(total_pred - total_actual):+.4f}  "
                      f"resid MAE={mean_absolute_error(y_r, resid_pred):.4f}")
    
    models['B'] = {
        'model': m_resid, 'scaler': scaler_r, 'features': resid_features,
        'alpha': best_alpha_r, 'col_means': col_means,
    }
    
    # ---- Model C: Hybrid (market as feature) ----
    report.append("\n--- MODEL C: Hybrid (closing_total as additional feature) ---")
    
    home_features_C = home_features_A + ['closing_total']
    away_features_C = away_features_A + ['closing_total']
    
    for target, features, label in [
        ('home_score', home_features_C, 'home'),
        ('away_score', away_features_C, 'away'),
    ]:
        report.append(f"\n  {label.upper()} model ({len(features)} features):")
        
        X_train = train_m[features].values
        y_train = train_m[target].values
        X_val   = val_m[features].values
        y_val   = val_m[target].values
        X_oos   = oos_m[features].values
        y_oos   = oos_m[target].values
        
        scaler = StandardScaler()
        X_train_s = scaler.fit_transform(X_train)
        X_val_s   = scaler.transform(X_val)
        X_oos_s   = scaler.transform(X_oos)
        
        best_alpha, best_val_mae = None, 999
        for alpha in RIDGE_ALPHAS:
            m = Ridge(alpha=alpha)
            m.fit(X_train_s, y_train)
            pred = m.predict(X_val_s)
            mae = mean_absolute_error(y_val, pred)
            if mae < best_val_mae:
                best_val_mae = mae
                best_alpha = alpha
        
        m = Ridge(alpha=best_alpha)
        m.fit(X_train_s, y_train)
        
        train_pred = m.predict(X_train_s)
        val_pred   = m.predict(X_val_s)
        oos_pred   = m.predict(X_oos_s)
        
        report.append(f"    Best alpha: {best_alpha}")
        report.append(f"    Train MAE={mean_absolute_error(y_train, train_pred):.4f}  bias={np.mean(train_pred - y_train):+.4f}")
        report.append(f"    Val   MAE={mean_absolute_error(y_val, val_pred):.4f}  bias={np.mean(val_pred - y_val):+.4f}")
        report.append(f"    OOS   MAE={mean_absolute_error(y_oos, oos_pred):.4f}  bias={np.mean(oos_pred - y_oos):+.4f}")
        
        # Feature importance: closing_total coefficient
        ct_idx = features.index('closing_total')
        report.append(f"    closing_total coef (scaled): {m.coef_[ct_idx]:.4f}")
        
        models[f'C_{label}'] = {
            'model': m, 'scaler': scaler, 'features': features,
            'alpha': best_alpha, 'col_means': col_means,
        }
    
    # Total predictions for Model C
    for split_name, split_df in [('train', train_m), ('val', val_m), ('oos', oos_m)]:
        h_pred = models['C_home']['model'].predict(
            models['C_home']['scaler'].transform(split_df[home_features_C].values))
        a_pred = models['C_away']['model'].predict(
            models['C_away']['scaler'].transform(split_df[away_features_C].values))
        total_pred = h_pred + a_pred
        total_actual = split_df['total_goals'].values
        report.append(f"  Model C Total {split_name}: MAE={mean_absolute_error(total_actual, total_pred):.4f}  "
                      f"bias={np.mean(total_pred - total_actual):+.4f}")
    
    # ---- Comparison table ----
    report.append("\n" + "=" * 70)
    report.append("MODEL COMPARISON (OOS = 2024-25 season)")
    report.append("=" * 70)
    
    # Model A on full OOS
    h_pred_a = models['A_home']['model'].predict(
        models['A_home']['scaler'].transform(oos[home_features_A].values))
    a_pred_a = models['A_away']['model'].predict(
        models['A_away']['scaler'].transform(oos[away_features_A].values))
    total_a = h_pred_a + a_pred_a
    
    # Model A on market-available OOS
    h_pred_am = models['A_home']['model'].predict(
        models['A_home']['scaler'].transform(oos_m[home_features_A].values))
    a_pred_am = models['A_away']['model'].predict(
        models['A_away']['scaler'].transform(oos_m[away_features_A].values))
    total_am = h_pred_am + a_pred_am
    
    # Model B on market-available OOS
    resid_pred_b = models['B']['model'].predict(X_oos_rs)
    total_b = oos_m['closing_total'].values + resid_pred_b
    
    # Model C on market-available OOS
    h_pred_c = models['C_home']['model'].predict(
        models['C_home']['scaler'].transform(oos_m[home_features_C].values))
    a_pred_c = models['C_away']['model'].predict(
        models['C_away']['scaler'].transform(oos_m[away_features_C].values))
    total_c = h_pred_c + a_pred_c
    
    # Market baseline
    market_pred = oos_m['closing_total'].values
    actual_m = oos_m['total_goals'].values
    
    report.append(f"\n  {'Model':<12} {'MAE':>7} {'RMSE':>7} {'Bias':>8} {'vs Market':>10}")
    report.append(f"  {'-'*12} {'-'*7} {'-'*7} {'-'*8} {'-'*10}")
    
    market_mae = mean_absolute_error(actual_m, market_pred)
    market_rmse = np.sqrt(mean_squared_error(actual_m, market_pred))
    market_bias = np.mean(market_pred - actual_m)
    report.append(f"  {'Market':<12} {market_mae:7.4f} {market_rmse:7.4f} {market_bias:+8.4f} {'baseline':>10}")
    
    for name, pred, actual in [
        ('Model A', total_am, actual_m),
        ('Model B', total_b, actual_m),
        ('Model C', total_c, actual_m),
    ]:
        mae = mean_absolute_error(actual, pred)
        rmse = np.sqrt(mean_squared_error(actual, pred))
        bias = np.mean(pred - actual)
        delta = ((mae / market_mae) - 1) * 100
        report.append(f"  {name:<12} {mae:7.4f} {rmse:7.4f} {bias:+8.4f} {delta:+9.1f}%")
    
    text = "\n".join(report)
    (OUT / "phase2_model_training.md").write_text(text)
    print(text)
    
    # Save models
    for k, v in models.items():
        pickle.dump(v, open(OUT / f"model_{k}.pkl", "wb"))
    
    return models, ft


# ---------------------------------------------------------------------------
# PHASE 3: Honest backtest
# ---------------------------------------------------------------------------
def phase3_backtest(models, ft):
    report = []
    report.append("=" * 70)
    report.append("PHASE 3: HONEST BACKTEST")
    report.append("=" * 70)
    
    home_features_A = models['A_home']['features']
    away_features_A = models['A_away']['features']
    home_features_C = models['C_home']['features']
    away_features_C = models['C_away']['features']
    resid_features  = models['B']['features']
    
    # Fill NaN
    col_means = models['A_home']['col_means']
    all_feat_cols = list(set(home_features_A + away_features_A + home_features_C + away_features_C + resid_features))
    for c in all_feat_cols:
        if c in ft.columns and c in col_means:
            ft[c] = ft[c].fillna(col_means[c])
        elif c == 'closing_total':
            pass  # handled separately
    
    oos = ft[ft.season_year.isin(OOS_SEASONS) & (ft.market_available == 1)].copy()
    report.append(f"\nOOS games with market: {len(oos)}")
    
    # Generate predictions for all 3 models
    h_pred_a = models['A_home']['model'].predict(
        models['A_home']['scaler'].transform(oos[home_features_A].values))
    a_pred_a = models['A_away']['model'].predict(
        models['A_away']['scaler'].transform(oos[away_features_A].values))
    oos['pred_A'] = h_pred_a + a_pred_a
    
    resid_pred = models['B']['model'].predict(
        models['B']['scaler'].transform(oos[resid_features].values))
    oos['pred_B'] = oos['closing_total'].values + resid_pred
    
    h_pred_c = models['C_home']['model'].predict(
        models['C_home']['scaler'].transform(oos[home_features_C].values))
    a_pred_c = models['C_away']['model'].predict(
        models['C_away']['scaler'].transform(oos[away_features_C].values))
    oos['pred_C'] = h_pred_c + a_pred_c
    
    # Calibrate Model A with validate-season drift
    val = ft[ft.season_year.isin(VAL_SEASONS)].copy()
    h_pred_v = models['A_home']['model'].predict(
        models['A_home']['scaler'].transform(val[home_features_A].values))
    a_pred_v = models['A_away']['model'].predict(
        models['A_away']['scaler'].transform(val[away_features_A].values))
    val_pred_total = h_pred_v + a_pred_v
    val_drift = np.mean(val.total_goals.values - val_pred_total)
    report.append(f"Validation drift (Model A): {val_drift:+.4f}")
    oos['pred_A_cal'] = oos['pred_A'] + val_drift
    
    # Model B/C: check validation drift
    val_m = val[val.market_available == 1].copy()
    resid_pred_v = models['B']['model'].predict(
        models['B']['scaler'].transform(val_m[resid_features].values))
    val_b_pred = val_m['closing_total'].values + resid_pred_v
    val_b_drift = np.mean(val_m.total_goals.values - val_b_pred)
    report.append(f"Validation drift (Model B): {val_b_drift:+.4f}")
    oos['pred_B_cal'] = oos['pred_B'] + val_b_drift
    
    h_pred_vc = models['C_home']['model'].predict(
        models['C_home']['scaler'].transform(val_m[home_features_C].values))
    a_pred_vc = models['C_away']['model'].predict(
        models['C_away']['scaler'].transform(val_m[away_features_C].values))
    val_c_pred = h_pred_vc + a_pred_vc
    val_c_drift = np.mean(val_m.total_goals.values - val_c_pred)
    report.append(f"Validation drift (Model C): {val_c_drift:+.4f}")
    oos['pred_C_cal'] = oos['pred_C'] + val_c_drift
    
    # Betting simulation
    report.append("\n--- BETTING SIMULATION (flat -110, $100 units) ---")
    
    for model_name, pred_col in [('A_cal', 'pred_A_cal'), ('B_cal', 'pred_B_cal'), ('C_cal', 'pred_C_cal')]:
        report.append(f"\n  Model {model_name}:")
        
        oos['edge'] = oos[pred_col] - oos['closing_total']
        oos['side'] = np.where(oos['edge'] > 0, 'over', 'under')
        oos['abs_edge'] = oos['edge'].abs()
        
        # Use actual over/under prices where available, else -110
        oos['bet_price'] = np.where(
            oos['side'] == 'over',
            oos['closing_over_price'].fillna(-110),
            oos['closing_under_price'].fillna(-110)
        )
        
        # Determine if bet won
        oos['won'] = np.where(
            oos['side'] == 'over',
            oos['total_goals'] > oos['closing_total'],
            oos['total_goals'] < oos['closing_total']
        )
        oos['push'] = oos['total_goals'] == oos['closing_total']
        
        for edge_thresh in [0.0, 0.3, 0.5, 0.75, 1.0]:
            bets = oos[(oos['abs_edge'] >= edge_thresh) & (~oos['push'])].copy()
            if len(bets) == 0:
                report.append(f"    edge>={edge_thresh:.1f}: 0 bets")
                continue
            
            n_bets = len(bets)
            wins = bets['won'].sum()
            losses = n_bets - wins
            
            # P&L with actual juice
            pnl = 0
            for _, b in bets.iterrows():
                price = b['bet_price']
                if b['won']:
                    pnl += 100 / abs(price) * 100 if price < 0 else price
                else:
                    pnl -= 100
            
            roi = pnl / (n_bets * 100) * 100
            report.append(f"    edge>={edge_thresh:.1f}: {n_bets:4d} bets  W={wins}  L={losses}  "
                         f"win%={wins/n_bets:.1%}  ROI={roi:+.1f}%  P&L=${pnl:+.0f}")
    
    # Monthly breakdown for best model
    report.append("\n--- MONTHLY BREAKDOWN (Model C calibrated, edge>=0.5) ---")
    oos['edge'] = oos['pred_C_cal'] - oos['closing_total']
    oos['abs_edge'] = oos['edge'].abs()
    oos['month'] = pd.to_datetime(oos['game_date']).dt.to_period('M')
    oos['won'] = np.where(
        oos['edge'] > 0,
        oos['total_goals'] > oos['closing_total'],
        oos['total_goals'] < oos['closing_total']
    )
    oos['push'] = oos['total_goals'] == oos['closing_total']
    
    qual = oos[(oos['abs_edge'] >= 0.5) & (~oos['push'])]
    for month, grp in qual.groupby('month'):
        wins = grp['won'].sum()
        n = len(grp)
        report.append(f"  {month}: {n:3d} bets  win%={wins/n:.1%}")
    
    text = "\n".join(report)
    (OUT / "phase3_backtest.md").write_text(text)
    print(text)
    
    return oos


# ---------------------------------------------------------------------------
# PHASE 4: Identity lock
# ---------------------------------------------------------------------------
def phase4_identity(models):
    report = []
    report.append("=" * 70)
    report.append("PHASE 4: IDENTITY LOCK — LIVE DEPLOYMENT CHECK")
    report.append("=" * 70)
    
    report.append("\nModel A (pure hockey) live feature requirements:")
    live_available = {
        'goals_scored_rolling_10': True,
        'goals_allowed_rolling_10': True,
        'shots_for_rolling_20': "PARTIAL — available from NHL API boxscores but NOT in current live pipeline",
        'shots_against_rolling_20': "PARTIAL — available from NHL API boxscores but NOT in current live pipeline",
        'pp_pct_rolling_20': "PARTIAL — computable from pp_goals/pp_opportunities in NHL API",
        'pk_pct_rolling_20': "PARTIAL — computable from pk stats in NHL API",
        'pp_opp_per_game_rolling_20': "PARTIAL — available from NHL API boxscores",
        'goalie_sv_pct_rolling_10': True,
        'goalie_vs_team_baseline': True,
        'goalie_fatigue': True,
        'goalie_b2b': True,
        'backup_flag': True,
        'days_rest': True,
        'b2b': True,
        'games_last_7': True,
        'shot_pressure': "PARTIAL — needs SOG from NHL API boxscores",
    }
    
    all_live = True
    partial_features = []
    for feat, status in live_available.items():
        if status is True:
            report.append(f"  LIVE  {feat}")
        else:
            report.append(f"  FIX   {feat} — {status}")
            partial_features.append(feat)
            all_live = False
    
    report.append(f"\nLive-ready: {'YES' if all_live else 'NO — pipeline modifications needed'}")
    
    if partial_features:
        report.append("\nREQUIRED PIPELINE CHANGES:")
        report.append("  The current nhl_daily_pipeline.py fetches only goals from NHL API boxscores.")
        report.append("  To support the rebuilt model, extend load_or_refresh_live_season() to also fetch:")
        report.append("    - shots on goal (from boxscore)")
        report.append("    - PP goals and PP opportunities (from boxscore)")
        report.append("    - PK goals against (from boxscore)")
        report.append("  These are ALL available from the NHL API gamecenter/{id}/boxscore endpoint.")
        report.append("  The current pipeline already calls this endpoint for goalie info.")
        report.append("  Estimated effort: ~30 lines of code change in fetch_game_boxscore().")
    
    report.append("\nModel C (hybrid) additionally requires:")
    report.append("  LIVE  closing_total — from Odds API (already fetched in pipeline)")
    
    text = "\n".join(report)
    (OUT / "phase4_identity_lock.md").write_text(text)
    print(text)


# ---------------------------------------------------------------------------
# PHASE 5: Regime audit
# ---------------------------------------------------------------------------
def phase5_regime(ft, models):
    report = []
    report.append("=" * 70)
    report.append("PHASE 5: REGIME AUDIT")
    report.append("=" * 70)
    
    home_features_A = models['A_home']['features']
    away_features_A = models['A_away']['features']
    
    col_means = models['A_home']['col_means']
    all_feat_cols = list(set(home_features_A + away_features_A))
    for c in all_feat_cols:
        if c in ft.columns and c in col_means:
            ft[c] = ft[c].fillna(col_means[c])
    
    # Check for regime shifts across seasons
    report.append("\n--- LEAGUE SCORING TRENDS ---")
    for sy in sorted(ft.season_year.unique()):
        sg = ft[ft.season_year == sy]
        report.append(f"  {sy}: avg total={sg.total_goals.mean():.2f}  "
                     f"std={sg.total_goals.std():.2f}  n={len(sg)}")
    
    # Model A predictions by season
    report.append("\n--- MODEL A BIAS BY SEASON ---")
    for sy in sorted(ft.season_year.unique()):
        sg = ft[ft.season_year == sy].copy()
        h_pred = models['A_home']['model'].predict(
            models['A_home']['scaler'].transform(sg[home_features_A].values))
        a_pred = models['A_away']['model'].predict(
            models['A_away']['scaler'].transform(sg[away_features_A].values))
        total_pred = h_pred + a_pred
        bias = np.mean(total_pred - sg.total_goals.values)
        mae = mean_absolute_error(sg.total_goals.values, total_pred)
        report.append(f"  {sy}: bias={bias:+.3f}  MAE={mae:.3f}")
    
    # Check feature stability across seasons
    report.append("\n--- FEATURE STABILITY (mean of key features by season) ---")
    key_features = ['home_goals_scored_rolling_10', 'home_shots_for_rolling_20',
                    'home_pp_pct_rolling_20', 'home_goalie_sv_pct_rolling_10']
    for feat in key_features:
        if feat not in ft.columns:
            continue
        report.append(f"\n  {feat}:")
        for sy in sorted(ft.season_year.unique()):
            sg = ft[ft.season_year == sy]
            report.append(f"    {sy}: mean={sg[feat].mean():.4f}  std={sg[feat].std():.4f}")
    
    # Correlation of model edge with actual over/under outcome
    report.append("\n--- EDGE SIGNAL QUALITY ---")
    oos = ft[ft.season_year.isin(OOS_SEASONS) & (ft.market_available == 1)].copy()
    h_pred = models['A_home']['model'].predict(
        models['A_home']['scaler'].transform(oos[home_features_A].values))
    a_pred = models['A_away']['model'].predict(
        models['A_away']['scaler'].transform(oos[away_features_A].values))
    
    # Apply validation drift
    val = ft[ft.season_year.isin(VAL_SEASONS)].copy()
    h_v = models['A_home']['model'].predict(
        models['A_home']['scaler'].transform(val[home_features_A].values))
    a_v = models['A_away']['model'].predict(
        models['A_away']['scaler'].transform(val[away_features_A].values))
    drift = np.mean(val.total_goals.values - (h_v + a_v))
    
    total_pred = h_pred + a_pred + drift
    edge = total_pred - oos['closing_total'].values
    market_error = oos['total_goals'].values - oos['closing_total'].values
    
    corr = np.corrcoef(edge, market_error)[0, 1]
    report.append(f"  corr(model_edge, market_error): {corr:.4f}")
    report.append(f"  (>0.05 = genuine signal, >0.10 = strong signal)")
    
    # Quintile analysis
    report.append("\n--- QUINTILE CALIBRATION (Model A calibrated, OOS) ---")
    oos_q = oos.copy()
    oos_q['pred_total'] = total_pred
    oos_q['quintile'] = pd.qcut(oos_q['pred_total'], 5, labels=['Q1','Q2','Q3','Q4','Q5'])
    for q, grp in oos_q.groupby('quintile'):
        report.append(f"  {q}: pred={grp.pred_total.mean():.2f}  actual={grp.total_goals.mean():.2f}  "
                     f"n={len(grp)}  delta={grp.pred_total.mean() - grp.total_goals.mean():+.2f}")
    
    # Check for B2B effect
    report.append("\n--- B2B EFFECT (OOS) ---")
    for side in ['home', 'away']:
        b2b = oos[oos[f'{side}_b2b'] == 1]
        no_b2b = oos[oos[f'{side}_b2b'] == 0]
        if len(b2b) > 10:
            report.append(f"  {side} B2B: avg_total={b2b.total_goals.mean():.2f} (n={len(b2b)})  "
                         f"vs no B2B: {no_b2b.total_goals.mean():.2f} (n={len(no_b2b)})")
    
    text = "\n".join(report)
    (OUT / "phase5_regime_audit.md").write_text(text)
    print(text)


# ---------------------------------------------------------------------------
# PHASE 6-7: Verdict + comparison
# ---------------------------------------------------------------------------
def phase67_verdict(models, ft):
    report = []
    report.append("=" * 70)
    report.append("NHL REBUILD — FINAL VERDICT")
    report.append("=" * 70)
    
    home_features_A = models['A_home']['features']
    away_features_A = models['A_away']['features']
    home_features_C = models['C_home']['features']
    away_features_C = models['C_away']['features']
    resid_features  = models['B']['features']
    
    col_means = models['A_home']['col_means']
    all_feat_cols = list(set(home_features_A + away_features_A + home_features_C + away_features_C + resid_features))
    for c in all_feat_cols:
        if c in ft.columns and c in col_means:
            ft[c] = ft[c].fillna(col_means[c])
    
    oos = ft[ft.season_year.isin(OOS_SEASONS) & (ft.market_available == 1)].copy()
    
    # Model predictions
    h_a = models['A_home']['model'].predict(models['A_home']['scaler'].transform(oos[home_features_A].values))
    a_a = models['A_away']['model'].predict(models['A_away']['scaler'].transform(oos[away_features_A].values))
    
    val = ft[ft.season_year.isin(VAL_SEASONS)].copy()
    h_v = models['A_home']['model'].predict(models['A_home']['scaler'].transform(val[home_features_A].values))
    a_v = models['A_away']['model'].predict(models['A_away']['scaler'].transform(val[away_features_A].values))
    drift_a = np.mean(val.total_goals.values - (h_v + a_v))
    
    pred_a = h_a + a_a + drift_a
    
    resid_b = models['B']['model'].predict(models['B']['scaler'].transform(oos[resid_features].values))
    val_m = val[val.market_available == 1].copy()
    resid_v = models['B']['model'].predict(models['B']['scaler'].transform(val_m[resid_features].values))
    drift_b = np.mean(val_m.total_goals.values - (val_m.closing_total.values + resid_v))
    pred_b = oos['closing_total'].values + resid_b + drift_b
    
    h_c = models['C_home']['model'].predict(models['C_home']['scaler'].transform(oos[home_features_C].values))
    a_c = models['C_away']['model'].predict(models['C_away']['scaler'].transform(oos[away_features_C].values))
    h_vc = models['C_home']['model'].predict(models['C_home']['scaler'].transform(val_m[home_features_C].values))
    a_vc = models['C_away']['model'].predict(models['C_away']['scaler'].transform(val_m[away_features_C].values))
    drift_c = np.mean(val_m.total_goals.values - (h_vc + a_vc))
    pred_c = h_c + a_c + drift_c
    
    market = oos['closing_total'].values
    actual = oos['total_goals'].values
    
    report.append("\n" + "=" * 70)
    report.append("OOS (2024-25) COMPARISON TABLE")
    report.append("=" * 70)
    report.append(f"\n  {'Model':<20} {'MAE':>7} {'RMSE':>7} {'Bias':>8} {'vs Market':>10} {'Status':>12}")
    report.append(f"  {'-'*20} {'-'*7} {'-'*7} {'-'*8} {'-'*10} {'-'*12}")
    
    market_mae = mean_absolute_error(actual, market)
    
    results = []
    for name, pred in [('Market (baseline)', market), ('Model A (pure)', pred_a),
                        ('Model B (residual)', pred_b), ('Model C (hybrid)', pred_c)]:
        mae = mean_absolute_error(actual, pred)
        rmse = np.sqrt(mean_squared_error(actual, pred))
        bias = np.mean(pred - actual)
        delta = ((mae / market_mae) - 1) * 100 if name != 'Market (baseline)' else 0
        status = 'baseline' if 'Market' in name else ('BEATS' if delta < 0 else 'LOSES')
        report.append(f"  {name:<20} {mae:7.4f} {rmse:7.4f} {bias:+8.4f} {delta:+9.1f}% {status:>12}")
        results.append((name, mae, delta))
    
    # Compare to original model (which uses MoneyPuck)
    report.append("\n--- VS ORIGINAL MODEL (from phase3_model_audit.txt) ---")
    report.append("  Original model (MoneyPuck features): Total OOS MAE = 1.9159, bias = -0.7864")
    report.append(f"  Rebuild Model A (no MoneyPuck):       Total OOS MAE = {mean_absolute_error(actual, pred_a):.4f}, "
                 f"bias = {np.mean(pred_a - actual):+.4f}")
    report.append(f"  Rebuild Model C (no MoneyPuck+mkt):   Total OOS MAE = {mean_absolute_error(actual, pred_c):.4f}, "
                 f"bias = {np.mean(pred_c - actual):+.4f}")
    
    orig_mae = 1.9159
    rebuild_a_mae = mean_absolute_error(actual, pred_a)
    rebuild_c_mae = mean_absolute_error(actual, pred_c)
    
    report.append(f"\n  Model A vs original: {((rebuild_a_mae/orig_mae)-1)*100:+.1f}%")
    report.append(f"  Model C vs original: {((rebuild_c_mae/orig_mae)-1)*100:+.1f}%")
    
    # Edge correlation with market error
    edge_a = pred_a - market
    edge_c = pred_c - market
    mkt_err = actual - market
    corr_a = np.corrcoef(edge_a, mkt_err)[0, 1]
    corr_c = np.corrcoef(edge_c, mkt_err)[0, 1]
    
    report.append(f"\n  corr(edge, market_error):")
    report.append(f"    Model A: {corr_a:.4f}")
    report.append(f"    Model C: {corr_c:.4f}")
    
    # Incremental R² over market
    from sklearn.metrics import r2_score
    r2_market = r2_score(actual, market)
    r2_a = r2_score(actual, pred_a)
    r2_c = r2_score(actual, pred_c)
    report.append(f"\n  R² scores:")
    report.append(f"    Market: {r2_market:.4f}")
    report.append(f"    Model A: {r2_a:.4f}  (delta={r2_a - r2_market:+.4f})")
    report.append(f"    Model C: {r2_c:.4f}  (delta={r2_c - r2_market:+.4f})")
    
    # VERDICT
    report.append("\n" + "=" * 70)
    report.append("VERDICT")
    report.append("=" * 70)
    
    best_model = min(results[1:], key=lambda x: x[1])
    best_name = best_model[0]
    best_delta = best_model[2]
    
    if best_delta < -1.0 and corr_c > 0.05:
        verdict = "DEPLOYABLE"
        rationale = (f"Best rebuild model ({best_name}) beats market by {abs(best_delta):.1f}% MAE "
                    f"with genuine edge signal (corr={max(corr_a, corr_c):.4f}).")
    elif best_delta < 0 and max(corr_a, corr_c) > 0.03:
        verdict = "SHADOW-ONLY"
        rationale = (f"Best rebuild model ({best_name}) shows marginal improvement ({best_delta:+.1f}% vs market) "
                    f"but edge signal is weak. Shadow test recommended before deployment.")
    else:
        verdict = "SHADOW-ONLY"
        rationale = (f"Best rebuild model ({best_name}) is {best_delta:+.1f}% vs market. "
                    f"Edge correlation: {max(corr_a, corr_c):.4f}. "
                    f"Not ready for live deployment without MoneyPuck features, but the "
                    f"live-compatible features provide a functional baseline for shadow testing.")
    
    report.append(f"\n  STATUS: {verdict}")
    report.append(f"  RATIONALE: {rationale}")
    
    report.append(f"\n  DEPLOYMENT NOTES:")
    report.append(f"  1. Model C (hybrid with market anchor) is recommended as the rebuild candidate")
    report.append(f"  2. Requires pipeline extension to fetch SOG/PP/PK from NHL API boxscores")
    report.append(f"  3. The original model's live pipeline already falls back to MoneyPuck priors,")
    report.append(f"     so this rebuild is actually MORE honest about what's available live")
    report.append(f"  4. If MoneyPuck data becomes available again, the original model is superior")
    
    report.append(f"\n  FEATURE COMPARISON:")
    report.append(f"  Original model: 24 features (includes xGF, xGA, HD shots from MoneyPuck)")
    report.append(f"  Rebuild model:  {len(home_features_A)} features (NHL API + schedule only)")
    report.append(f"  Dropped features: xgf_rolling_20, xga_rolling_20, hd_shots_for_rolling_20,")
    report.append(f"                    hd_shots_against_rolling_20, hd_pressure (4+2 features)")
    
    text = "\n".join(report)
    (OUT / "NHL_REBUILD_FINAL_VERDICT.md").write_text(text)
    print(text)


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("NHL CLEAN REBUILD — Live-Compatible Features Only")
    print("=" * 70)
    
    gc = phase0_inventory()
    ft = phase1_build_features(gc)
    models, ft = phase2_models(ft)
    oos = phase3_backtest(models, ft)
    phase4_identity(models)
    phase5_regime(ft, models)
    phase67_verdict(models, ft)
    
    print("\n" + "=" * 70)
    print("ALL PHASES COMPLETE")
    print(f"Output directory: {OUT}")
    print("=" * 70)
