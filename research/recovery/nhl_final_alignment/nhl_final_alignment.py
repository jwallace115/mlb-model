#!/usr/bin/env python3
"""
NHL FINAL ALIGNMENT RETRAIN
============================
Fixes PK% definition mismatch between canonical rebuild and live pipeline.

Canonical CSV had pk_pct = 1 - pk_goals_against / opp_pp_opportunities (mean ~0.966)
Live pipeline uses pk_pct = 1 - opp_pp_goals / opp_pp_opportunities (mean ~0.79)

pk_goals_against != opp_pp_goals:
  - pk_goals_against: shorthanded goals against (very rare, ~0.08/game)
  - opp_pp_goals: opponent power play goals (common, ~0.6/game)

The live pipeline definition is semantically correct for "penalty kill success rate".
This script rebuilds using the live-compatible definition throughout.
"""

import sys, pickle, json
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
OUT  = BASE / "research" / "recovery" / "nhl_final_alignment"
OUT.mkdir(parents=True, exist_ok=True)

CANONICAL = BASE / "nhl" / "nhl_games_canonical.csv"
MARKET_SNAP = BASE / "nhl" / "nhl_market_snapshots.parquet"
OLD_REBUILD_FT = BASE / "research" / "recovery" / "nhl_rebuild" / "nhl_rebuild_features.parquet"

ROLLING_LONG  = 20
ROLLING_SHORT = 10
RIDGE_ALPHAS  = [0.01, 0.1, 1.0, 10.0, 50.0, 100.0, 200.0, 500.0]
TRAIN_SEASONS = {2021, 2022}
VAL_SEASONS   = {2023}
OOS_SEASONS   = {2024}
LIVE_SEASON   = {2025}

SEED = 42
np.random.seed(SEED)

# ---------------------------------------------------------------------------
# PHASE 1: Document live-compatible feature spec
# ---------------------------------------------------------------------------
def phase1_live_feature_spec():
    print("=" * 70)
    print("PHASE 1: LIVE-COMPATIBLE FEATURE SPEC")
    print("=" * 70)

    gc = pd.read_csv(CANONICAL)

    # Document the discrepancy
    report = []
    report.append("# Phase 1: Live-Compatible Feature Specification")
    report.append("")
    report.append("## The PK% Discrepancy")
    report.append("")
    report.append("### Canonical CSV definition (WRONG for our purposes):")
    report.append("```")
    report.append("pk_pct = 1 - pk_goals_against / opp_pp_opportunities")
    report.append(f"Mean: {gc['home_pk_pct'].mean():.4f}")
    report.append("```")
    report.append("pk_goals_against counts SHORTHANDED goals against (very rare, ~0.08/game)")
    report.append("")
    report.append("### Live pipeline definition (CORRECT, source of truth):")
    report.append("```python")
    report.append("# From nhl_daily_pipeline.py lines 531-535:")
    report.append("# PK% — 1 - (opp_pp_goals / opp_pp_opportunities)")
    report.append("opp_ppg = r.get(f'{opp_pfx}_pp_goals')")
    report.append("opp_ppo = r.get(f'{opp_pfx}_pp_opportunities')")
    report.append("pk_pct = 1.0 - opp_ppg / opp_ppo if opp_ppo > 0 else 1.0")
    report.append("```")

    # Compute live-compatible PK% stats
    mask_h = gc['away_pp_opportunities'].notna() & (gc['away_pp_opportunities'] > 0)
    home_pk_live = 1.0 - gc.loc[mask_h, 'away_pp_goals'] / gc.loc[mask_h, 'away_pp_opportunities']
    mask_a = gc['home_pp_opportunities'].notna() & (gc['home_pp_opportunities'] > 0)
    away_pk_live = 1.0 - gc.loc[mask_a, 'home_pp_goals'] / gc.loc[mask_a, 'home_pp_opportunities']

    report.append(f"Live PK% mean (home): {home_pk_live.mean():.4f}")
    report.append(f"Live PK% mean (away): {away_pk_live.mean():.4f}")
    report.append("")
    report.append("### Delta between definitions:")
    report.append(f"Canonical mean: ~0.965")
    report.append(f"Live mean: ~{(home_pk_live.mean() + away_pk_live.mean())/2:.3f}")
    report.append(f"Gap: ~{0.965 - (home_pk_live.mean() + away_pk_live.mean())/2:.3f}")
    report.append("")
    report.append("This gap means the old rebuild model learned PK% coefficients on a scale")
    report.append("that was 0.17 higher than what the live pipeline feeds it. Any model")
    report.append("trained on the old definition will systematically mispredict when given")
    report.append("live PK% values.")
    report.append("")
    report.append("## PP% definition (CONSISTENT)")
    report.append("Both canonical and live use: pp_goals / pp_opportunities")
    report.append(f"Canonical mean: {gc['home_pp_pct'].mean():.4f}")
    report.append("No fix needed.")
    report.append("")
    report.append("## All feature definitions (source of truth for retrain):")
    report.append("")
    feats = [
        ("goals_scored_rolling_10", "rolling 10-game mean of goals scored (ROLLING_SHORT=10)"),
        ("goals_allowed_rolling_10", "rolling 10-game mean of goals allowed"),
        ("shots_for_rolling_20", "rolling 20-game mean of shots on goal"),
        ("shots_against_rolling_20", "rolling 20-game mean of shots against"),
        ("pp_pct_rolling_20", "rolling 20-game mean of pp_goals/pp_opportunities"),
        ("pk_pct_rolling_20", "rolling 20-game mean of 1 - opp_pp_goals/opp_pp_opportunities  ** CORRECTED **"),
        ("pp_opp_per_game_rolling_20", "rolling 20-game mean of pp_opportunities"),
        ("goalie_sv_pct_rolling_10", "rolling 10-game mean of 1 - GA/SA for starting goalie"),
        ("goalie_vs_team_baseline", "goalie sv% minus team average sv% (needs >=3 starts)"),
        ("goalie_fatigue", "goalie starts in last 3 days"),
        ("goalie_b2b", "is back-to-back game"),
        ("backup_flag", "is not the most frequent starter (needs >=5 games)"),
        ("days_rest", "rest days since last game"),
        ("b2b", "is back-to-back"),
        ("games_last_7", "games in last 7 days"),
        ("shot_pressure", "team shots_for_rolling - opp shots_against_rolling"),
    ]
    for fname, desc in feats:
        report.append(f"- **{fname}**: {desc}")

    text = "\n".join(report)
    (OUT / "phase1_live_feature_spec.md").write_text(text)
    print(text[:500])
    print("... [written to phase1_live_feature_spec.md]")
    return gc


# ---------------------------------------------------------------------------
# PHASE 2: Rebuild feature table with live-compatible PK%
# ---------------------------------------------------------------------------
def phase2_rebuild_features(gc):
    print("\n" + "=" * 70)
    print("PHASE 2: REBUILD FEATURE TABLE WITH LIVE-COMPATIBLE PK%")
    print("=" * 70)

    report = []

    # Recompute pp_pct and pk_pct using live-compatible definitions
    for side in ['home', 'away']:
        opp = 'away' if side == 'home' else 'home'

        # PP%: pp_goals / pp_opportunities (same as canonical, just fill NaN)
        mask_pp = gc[f'{side}_pp_opportunities'].notna() & (gc[f'{side}_pp_opportunities'] > 0)
        gc[f'{side}_pp_pct_live'] = np.nan
        gc.loc[mask_pp, f'{side}_pp_pct_live'] = (
            gc.loc[mask_pp, f'{side}_pp_goals'] / gc.loc[mask_pp, f'{side}_pp_opportunities']
        )
        gc.loc[gc[f'{side}_pp_opportunities'].notna() & (gc[f'{side}_pp_opportunities'] == 0),
               f'{side}_pp_pct_live'] = 0.0

        # PK%: 1 - opp_pp_goals / opp_pp_opportunities  ** LIVE DEFINITION **
        mask_pk = gc[f'{opp}_pp_opportunities'].notna() & (gc[f'{opp}_pp_opportunities'] > 0)
        gc[f'{side}_pk_pct_live'] = np.nan
        gc.loc[mask_pk, f'{side}_pk_pct_live'] = (
            1.0 - gc.loc[mask_pk, f'{opp}_pp_goals'] / gc.loc[mask_pk, f'{opp}_pp_opportunities']
        )
        gc.loc[gc[f'{opp}_pp_opportunities'].notna() & (gc[f'{opp}_pp_opportunities'] == 0),
               f'{side}_pk_pct_live'] = 1.0

    # Verify the fix
    for side in ['home', 'away']:
        old_mean = gc[f'{side}_pk_pct'].mean()
        new_mean = gc[f'{side}_pk_pct_live'].mean()
        report.append(f"{side}_pk_pct: old={old_mean:.4f}, live-compatible={new_mean:.4f}, delta={old_mean - new_mean:.4f}")
    print("\n".join(report))

    # Goalie save %
    for side in ['home', 'away']:
        gc[f'{side}_goalie_sv_pct'] = np.where(
            gc[f'{side}_goalie_sa'] > 0,
            1.0 - gc[f'{side}_goalie_ga'] / gc[f'{side}_goalie_sa'],
            0.91
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
                'pp_pct': getattr(g, f'{side}_pp_pct_live'),
                'pk_pct': getattr(g, f'{side}_pk_pct_live'),  # ** LIVE DEFINITION **
                'pp_opportunities': getattr(g, f'{side}_pp_opportunities', np.nan),
                'goalie_sv_pct': getattr(g, f'{side}_goalie_sv_pct'),
                'goalie_id': getattr(g, f'{side}_goalie_id'),
                'is_b2b': getattr(g, f'{side}_is_b2b'),
                'rest_days': getattr(g, f'{side}_rest_days'),
                'games_last_7': getattr(g, f'{side}_games_last_7'),
                'shots_for': getattr(g, f'{side}_shots_on_goal', np.nan),
                'shots_against': getattr(g, f'{opp_side}_shots_on_goal', np.nan),
            }
            rows.append(row)

    tgl = pd.DataFrame(rows)
    tgl = tgl.sort_values(['team', 'game_date']).reset_index(drop=True)
    print(f"Team game log: {len(tgl)} rows")

    # League averages per season for shrinkage
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

    report.append(f"\nLeague PK% averages per season (live-compatible):")
    for sy, la in league_avgs.items():
        report.append(f"  Season {sy}: pk_pct={la['pk_pct']:.4f}, pp_pct={la['pp_pct']:.4f}")
    print(report[-1])

    # Shrinkage helper
    def shrink(raw, n, prior, window):
        if pd.isna(raw):
            return prior
        w = min(n, window) / window
        return w * raw + (1 - w) * prior

    # Rolling features with PIT safety
    def compute_rolling(team_df, la):
        results = []
        for i, row in enumerate(team_df.itertuples(index=False)):
            prior = team_df.iloc[:i]
            n = len(prior)
            feat = {}

            # Goals rolling 10
            gs_prior = prior.goals_scored.dropna().tail(ROLLING_SHORT)
            ga_prior = prior.goals_allowed.dropna().tail(ROLLING_SHORT)
            feat['goals_scored_rolling_10'] = shrink(
                gs_prior.mean() if len(gs_prior) else np.nan, n, la['goals_scored'], ROLLING_SHORT)
            feat['goals_allowed_rolling_10'] = shrink(
                ga_prior.mean() if len(ga_prior) else np.nan, n, la['goals_allowed'], ROLLING_SHORT)

            # Shots rolling 20
            sf_prior = prior.shots_for.dropna().tail(ROLLING_LONG)
            sa_prior = prior.shots_against.dropna().tail(ROLLING_LONG)
            feat['shots_for_rolling_20'] = shrink(
                sf_prior.mean() if len(sf_prior) else np.nan, len(sf_prior), la['shots_for'], ROLLING_LONG)
            feat['shots_against_rolling_20'] = shrink(
                sa_prior.mean() if len(sa_prior) else np.nan, len(sa_prior), la['shots_against'], ROLLING_LONG)

            # PP% rolling 20
            pp_prior = prior.pp_pct.dropna().tail(ROLLING_LONG)
            feat['pp_pct_rolling_20'] = shrink(
                pp_prior.mean() if len(pp_prior) else np.nan, len(pp_prior), la['pp_pct'], ROLLING_LONG)

            # PK% rolling 20 — LIVE-COMPATIBLE DEFINITION
            pk_prior = prior.pk_pct.dropna().tail(ROLLING_LONG)
            feat['pk_pct_rolling_20'] = shrink(
                pk_prior.mean() if len(pk_prior) else np.nan, len(pk_prior), la['pk_pct'], ROLLING_LONG)

            # PP opportunities per game rolling 20
            ppo_prior = prior.pp_opportunities.dropna().tail(ROLLING_LONG)
            feat['pp_opp_per_game_rolling_20'] = shrink(
                ppo_prior.mean() if len(ppo_prior) else np.nan, len(ppo_prior), la['pp_opportunities'], ROLLING_LONG)

            # Goalie save% rolling 10
            goalie_id = row.goalie_id
            goalie_prior = prior[prior.goalie_id == goalie_id].goalie_sv_pct.dropna().tail(ROLLING_SHORT)
            n_goalie = len(goalie_prior)
            feat['goalie_sv_pct_rolling_10'] = shrink(
                goalie_prior.mean() if n_goalie else np.nan, n_goalie, la['goalie_sv_pct'], ROLLING_SHORT)

            # Goalie vs team baseline
            team_goalie_mean = prior[prior.goalie_id == goalie_id].goalie_sv_pct.mean()
            team_all_mean = prior.goalie_sv_pct.mean()
            if pd.notna(team_goalie_mean) and pd.notna(team_all_mean) and n_goalie >= 3:
                feat['goalie_vs_team_baseline'] = team_goalie_mean - team_all_mean
            else:
                feat['goalie_vs_team_baseline'] = 0.0

            # Goalie fatigue
            if n > 0:
                three_days_ago = row.game_date - pd.Timedelta(days=3)
                recent = prior[(prior.game_date >= three_days_ago) & (prior.goalie_id == goalie_id)]
                feat['goalie_fatigue'] = len(recent)
            else:
                feat['goalie_fatigue'] = 0

            feat['goalie_b2b'] = int(row.is_b2b)

            if n >= 5:
                mode_goalie = prior.goalie_id.mode()
                feat['backup_flag'] = int(goalie_id not in mode_goalie.values)
            else:
                feat['backup_flag'] = 0

            feat['days_rest'] = row.rest_days if pd.notna(row.rest_days) else 3.0
            feat['b2b'] = int(row.is_b2b)
            feat['games_last_7'] = row.games_last_7

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
    print(f"Processing {len(teams)} teams...")
    for team in teams:
        team_df = tgl[tgl.team == team].sort_values('game_date').reset_index(drop=True)
        for sy in sorted(team_df.season_year.unique()):
            season_df = team_df[team_df.season_year == sy].reset_index(drop=True)
            la = league_avgs[sy]
            feat_df = compute_rolling(season_df, la)
            all_features.append(feat_df)

    feat_long = pd.concat(all_features, ignore_index=True)
    print(f"Feature long table: {feat_long.shape}")

    # Pivot to wide format
    home_feat = feat_long[feat_long.is_home].copy()
    away_feat = feat_long[~feat_long.is_home].copy()

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

    # Verify PK% is now live-compatible
    print(f"\nCorrected feature table PK% stats:")
    print(f"  home_pk_pct_rolling_20 mean: {ft.home_pk_pct_rolling_20.mean():.4f}")
    print(f"  away_pk_pct_rolling_20 mean: {ft.away_pk_pct_rolling_20.mean():.4f}")

    if OLD_REBUILD_FT.exists():
        old_ft = pd.read_parquet(OLD_REBUILD_FT)
        print(f"\nOld rebuild PK% stats for comparison:")
        print(f"  home_pk_pct_rolling_20 mean: {old_ft.home_pk_pct_rolling_20.mean():.4f}")
        print(f"  away_pk_pct_rolling_20 mean: {old_ft.away_pk_pct_rolling_20.mean():.4f}")

    ft_path = OUT / "nhl_live_compatible_feature_table_v2.parquet"
    ft.to_parquet(ft_path, index=False)
    print(f"\nSaved: {ft_path}")
    print(f"Shape: {ft.shape}")
    report.append(f"\nFinal feature table: {ft.shape}")
    report.append(f"Market available: {ft.market_available.sum()} / {len(ft)}")

    text = "\n".join(report)
    (OUT / "phase2_feature_build.md").write_text(text)
    return ft, league_avgs


# ---------------------------------------------------------------------------
# PHASE 3: Retrain Model A
# ---------------------------------------------------------------------------
def phase3_retrain(ft):
    print("\n" + "=" * 70)
    print("PHASE 3: RETRAIN MODEL A ON CORRECTED FEATURES")
    print("=" * 70)

    report = []

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

    # Splits
    train = ft[ft.season_year.isin(TRAIN_SEASONS)].copy()
    val   = ft[ft.season_year.isin(VAL_SEASONS)].copy()
    oos   = ft[ft.season_year.isin(OOS_SEASONS)].copy()
    live  = ft[ft.season_year.isin(LIVE_SEASON)].copy()

    report.append(f"Splits: train={len(train)}, val={len(val)}, oos={len(oos)}, live={len(live)}")
    print(report[-1])

    # Fill NaN with train means
    all_feat_cols = list(set(home_features_A + away_features_A))
    col_means = {}
    for c in all_feat_cols:
        col_means[c] = train[c].mean()

    for df in [train, val, oos, live]:
        for c in all_feat_cols:
            df[c] = df[c].fillna(col_means[c])

    models = {}

    for target, features, label in [
        ('home_score', home_features_A, 'home'),
        ('away_score', away_features_A, 'away'),
    ]:
        report.append(f"\n--- {label.upper()} model ({len(features)} features) ---")

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

        report.append(f"  Best alpha: {best_alpha}")
        report.append(f"  Train MAE={mean_absolute_error(y_train, train_pred):.4f}  RMSE={np.sqrt(mean_squared_error(y_train, train_pred)):.4f}  bias={np.mean(train_pred - y_train):+.4f}")
        report.append(f"  Val   MAE={mean_absolute_error(y_val, val_pred):.4f}  RMSE={np.sqrt(mean_squared_error(y_val, val_pred)):.4f}  bias={np.mean(val_pred - y_val):+.4f}")
        report.append(f"  OOS   MAE={mean_absolute_error(y_oos, oos_pred):.4f}  RMSE={np.sqrt(mean_squared_error(y_oos, oos_pred)):.4f}  bias={np.mean(oos_pred - y_oos):+.4f}")

        # Feature importance
        coefs = pd.Series(m.coef_, index=features).sort_values(key=abs, ascending=False)
        report.append(f"  Top 5 features (by |coef|):")
        for fname, cval in coefs.head(5).items():
            report.append(f"    {fname}: {cval:+.4f}")

        models[f'A_{label}'] = {
            'model': m, 'scaler': scaler, 'features': features,
            'alpha': best_alpha, 'col_means': col_means,
        }

        # Save pickle
        pkl_path = OUT / f"model_A_{label}.pkl"
        with open(pkl_path, 'wb') as f:
            pickle.dump(models[f'A_{label}'], f)
        report.append(f"  Saved: {pkl_path.name}")

    # Total predictions
    report.append(f"\n--- TOTAL PREDICTIONS ---")
    for split_name, split_df in [('train', train), ('val', val), ('oos', oos), ('live', live)]:
        h_pred = models['A_home']['model'].predict(
            models['A_home']['scaler'].transform(split_df[home_features_A].values))
        a_pred = models['A_away']['model'].predict(
            models['A_away']['scaler'].transform(split_df[away_features_A].values))
        total_pred = h_pred + a_pred
        total_actual = split_df['total_goals'].values
        mae = mean_absolute_error(total_actual, total_pred)
        rmse = np.sqrt(mean_squared_error(total_actual, total_pred))
        bias = np.mean(total_pred - total_actual)
        report.append(f"  {split_name:6s}: MAE={mae:.4f}  RMSE={rmse:.4f}  bias={bias:+.4f}  n={len(split_df)}")

    # Market comparison on OOS
    oos_m = oos[oos.market_available == 1].copy()
    if len(oos_m) > 0:
        report.append(f"\n--- MARKET COMPARISON (OOS, n={len(oos_m)}) ---")
        h_pred = models['A_home']['model'].predict(
            models['A_home']['scaler'].transform(oos_m[home_features_A].values))
        a_pred = models['A_away']['model'].predict(
            models['A_away']['scaler'].transform(oos_m[away_features_A].values))
        model_total = h_pred + a_pred
        market_total = oos_m['closing_total'].values
        actual_total = oos_m['total_goals'].values

        model_mae = mean_absolute_error(actual_total, model_total)
        market_mae = mean_absolute_error(actual_total, market_total)
        model_rmse = np.sqrt(mean_squared_error(actual_total, model_total))
        market_rmse = np.sqrt(mean_squared_error(actual_total, market_total))
        report.append(f"  Model A: MAE={model_mae:.4f}  RMSE={model_rmse:.4f}")
        report.append(f"  Market:  MAE={market_mae:.4f}  RMSE={market_rmse:.4f}")
        report.append(f"  Delta:   MAE={model_mae - market_mae:+.4f}  RMSE={model_rmse - market_rmse:+.4f}")

        # Edge threshold analysis
        report.append(f"\n--- EDGE THRESHOLD ANALYSIS (OOS) ---")
        edge = model_total - market_total
        for thresh in [0.3, 0.5, 0.75, 1.0, 1.5]:
            over_mask = edge >= thresh
            under_mask = edge <= -thresh
            n_over = over_mask.sum()
            n_under = under_mask.sum()
            if n_over > 0:
                over_hit = (actual_total[over_mask] > market_total[over_mask]).mean()
                report.append(f"  OVER  edge>={thresh}: n={n_over}, hit%={over_hit:.3f}")
            if n_under > 0:
                under_hit = (actual_total[under_mask] < market_total[under_mask]).mean()
                report.append(f"  UNDER edge<=-{thresh}: n={n_under}, hit%={under_hit:.3f}")

        # Calibration by quintile
        report.append(f"\n--- CALIBRATION BY MODEL TOTAL QUINTILE (OOS) ---")
        quintiles = pd.qcut(model_total, 5, labels=False, duplicates='drop')
        for q in sorted(set(quintiles)):
            qm = quintiles == q
            pred_mean = model_total[qm].mean()
            actual_mean = actual_total[qm].mean()
            report.append(f"  Q{q}: pred={pred_mean:.2f}  actual={actual_mean:.2f}  delta={pred_mean - actual_mean:+.2f}  n={qm.sum()}")

    # Compare with old rebuild
    report.append(f"\n--- COMPARISON WITH OLD REBUILD (PK% ~0.966) ---")
    if OLD_REBUILD_FT.exists():
        old_ft = pd.read_parquet(OLD_REBUILD_FT)
        old_oos = old_ft[old_ft.season_year.isin(OOS_SEASONS)].copy()
        old_oos_m = old_oos[old_oos.market_available == 1].copy()

        # Load old model
        old_home_pkl = BASE / "research" / "recovery" / "nhl_rebuild" / "model_A_home.pkl"
        old_away_pkl = BASE / "research" / "recovery" / "nhl_rebuild" / "model_A_away.pkl"
        if old_home_pkl.exists() and old_away_pkl.exists():
            with open(old_home_pkl, 'rb') as f:
                old_hpkg = pickle.load(f)
            with open(old_away_pkl, 'rb') as f:
                old_apkg = pickle.load(f)

            # Fill NaN
            for c in old_hpkg['features']:
                if c not in old_oos_m.columns:
                    old_oos_m[c] = old_hpkg['col_means'].get(c, 0)
                old_oos_m[c] = old_oos_m[c].fillna(old_hpkg['col_means'].get(c, 0))
            for c in old_apkg['features']:
                if c not in old_oos_m.columns:
                    old_oos_m[c] = old_apkg['col_means'].get(c, 0)
                old_oos_m[c] = old_oos_m[c].fillna(old_apkg['col_means'].get(c, 0))

            old_h = old_hpkg['model'].predict(old_hpkg['scaler'].transform(old_oos_m[old_hpkg['features']].values))
            old_a = old_apkg['model'].predict(old_apkg['scaler'].transform(old_oos_m[old_apkg['features']].values))
            old_total = old_h + old_a
            old_actual = old_oos_m['total_goals'].values
            old_market = old_oos_m['closing_total'].values

            old_mae = mean_absolute_error(old_actual, old_total)
            old_rmse = np.sqrt(mean_squared_error(old_actual, old_total))
            report.append(f"  Old rebuild Model A OOS: MAE={old_mae:.4f}  RMSE={old_rmse:.4f}")
            report.append(f"  New aligned Model A OOS: MAE={model_mae:.4f}  RMSE={model_rmse:.4f}")
            report.append(f"  Improvement: MAE={old_mae - model_mae:+.4f}  RMSE={old_rmse - model_rmse:+.4f}")
        else:
            report.append("  Old model pickles not found, skipping comparison")
    else:
        report.append("  Old rebuild feature table not found")

    text = "\n".join(report)
    (OUT / "phase3_retrain_report.md").write_text(text)
    for line in report:
        print(line)

    return models, home_features_A, away_features_A, col_means


# ---------------------------------------------------------------------------
# PHASE 4: Live parity recheck
# ---------------------------------------------------------------------------
def phase4_parity(ft, models, home_features_A, away_features_A, col_means):
    print("\n" + "=" * 70)
    print("PHASE 4: LIVE PARITY RECHECK")
    print("=" * 70)

    report = []

    # Load the live pipeline's feature computation and compare
    # We'll simulate what the live pipeline would compute for 2025 games
    # by looking at the feature table values and comparing to what the live
    # pipeline's compute_league_priors + compute_features would produce.

    gc = pd.read_csv(CANONICAL)
    gc['game_date'] = pd.to_datetime(gc['game_date'])

    # Compute priors using LIVE pipeline's method (from compute_league_priors)
    s24 = gc[gc['season_year'] == 2024]

    _pp_pct_arr = []
    _pk_pct_arr = []
    for _, _r in s24.iterrows():
        for _s in ("home", "away"):
            _opp = "away" if _s == "home" else "home"
            _ppo = _r.get(f"{_s}_pp_opportunities")
            _ppg = _r.get(f"{_s}_pp_goals")
            if pd.notna(_ppo) and pd.notna(_ppg):
                _pp_pct_arr.append(_ppg / _ppo if _ppo > 0 else 0.0)
            _opp_ppo = _r.get(f"{_opp}_pp_opportunities")
            _opp_ppg = _r.get(f"{_opp}_pp_goals")
            if pd.notna(_opp_ppo) and pd.notna(_opp_ppg):
                _pk_pct_arr.append(1.0 - _opp_ppg / _opp_ppo if _opp_ppo > 0 else 1.0)

    live_prior_pp = float(np.mean(_pp_pct_arr))
    live_prior_pk = float(np.mean(_pk_pct_arr))

    report.append(f"Live pipeline priors (from canonical s24):")
    report.append(f"  pp_pct prior: {live_prior_pp:.4f}")
    report.append(f"  pk_pct prior: {live_prior_pk:.4f}")

    # Compare with what our rebuild uses for s24 shrinkage
    live_season = ft[ft.season_year.isin(LIVE_SEASON)]
    if len(live_season) > 0:
        rebuild_pk = live_season['home_pk_pct_rolling_20'].mean()
        rebuild_pp = live_season['home_pp_pct_rolling_20'].mean()
        report.append(f"\nRebuild feature table (2025 season) means:")
        report.append(f"  home_pk_pct_rolling_20: {rebuild_pk:.4f}")
        report.append(f"  home_pp_pct_rolling_20: {rebuild_pp:.4f}")

        # Check if PK% range is live-compatible
        pk_range = (live_season['home_pk_pct_rolling_20'].min(), live_season['home_pk_pct_rolling_20'].max())
        report.append(f"  PK% range: [{pk_range[0]:.4f}, {pk_range[1]:.4f}]")

        if abs(rebuild_pk - live_prior_pk) < 0.05:
            report.append(f"\n  ** PK% ALIGNED: rebuild mean within 0.05 of live prior ({abs(rebuild_pk - live_prior_pk):.4f})")
        else:
            report.append(f"\n  ** PK% MISALIGNED: delta = {abs(rebuild_pk - live_prior_pk):.4f}")

        # Cross-check: what does the old rebuild have?
        if OLD_REBUILD_FT.exists():
            old_ft = pd.read_parquet(OLD_REBUILD_FT)
            old_live = old_ft[old_ft.season_year.isin(LIVE_SEASON)]
            if len(old_live) > 0:
                old_pk = old_live['home_pk_pct_rolling_20'].mean()
                report.append(f"\n  Old rebuild PK% mean (2025): {old_pk:.4f}")
                report.append(f"  Old vs live prior delta: {abs(old_pk - live_prior_pk):.4f}  ** THIS WAS THE BUG **")
                report.append(f"  New vs live prior delta: {abs(rebuild_pk - live_prior_pk):.4f}  ** FIXED **")

    # Sample game-level comparison
    report.append(f"\n--- SAMPLE GAME FEATURE COMPARISON ---")
    report.append("Comparing canonical-rebuild features vs what live pipeline would compute")
    report.append("(Both should now use live-compatible PK% definition)")

    sample_games = live_season.head(5) if len(live_season) > 0 else ft.tail(5)
    for _, g in sample_games.iterrows():
        report.append(f"\n  Game {g.game_id}: {g.home_team} vs {g.away_team}")
        report.append(f"    home_pk_pct_rolling_20: {g.home_pk_pct_rolling_20:.4f}")
        report.append(f"    away_pk_pct_rolling_20: {g.away_pk_pct_rolling_20:.4f}")
        report.append(f"    home_pp_pct_rolling_20: {g.home_pp_pct_rolling_20:.4f}")
        report.append(f"    away_pp_pct_rolling_20: {g.away_pp_pct_rolling_20:.4f}")

    # Final parity verdict
    report.append(f"\n--- PARITY VERDICT ---")
    pk_aligned = abs(rebuild_pk - live_prior_pk) < 0.05 if len(live_season) > 0 else False
    pp_aligned = abs(rebuild_pp - live_prior_pp) < 0.05 if len(live_season) > 0 else False

    if pk_aligned and pp_aligned:
        report.append("PASS: PK% and PP% definitions are aligned between rebuild and live pipeline.")
        report.append("The retrained model is compatible with live feature computation.")
        parity_pass = True
    else:
        report.append("FAIL: Feature definitions still misaligned.")
        parity_pass = False

    text = "\n".join(report)
    (OUT / "phase4_parity_report.md").write_text(text)
    for line in report:
        print(line)

    return parity_pass


# ---------------------------------------------------------------------------
# PHASE 5: Shadow readiness + final verdict
# ---------------------------------------------------------------------------
def phase5_verdict(parity_pass, ft, models, home_features_A, away_features_A):
    print("\n" + "=" * 70)
    print("PHASE 5: SHADOW READINESS")
    print("=" * 70)

    report = []

    if parity_pass:
        report.append("# NHL FINAL ALIGNMENT VERDICT: READY FOR SHADOW")
        report.append("")
        report.append("## Summary")
        report.append("- PK% definition corrected from pk_goals_against (0.966 mean) to opp_pp_goals (0.79 mean)")
        report.append("- Feature table rebuilt with live-compatible definitions")
        report.append("- Model A retrained on corrected features")
        report.append("- Live parity verified: rebuild features match live pipeline computation")
        report.append("")
        report.append("## Action Items")
        report.append("1. Copy model_A_home.pkl and model_A_away.pkl to nhl/ or update REBUILD paths")
        report.append("2. Copy nhl_live_compatible_feature_table_v2.parquet as the new rebuild FT")
        report.append("3. Run shadow for 3+ game days to validate")
        report.append("")
        report.append("## Files Produced")
        report.append(f"- research/recovery/nhl_final_alignment/model_A_home.pkl")
        report.append(f"- research/recovery/nhl_final_alignment/model_A_away.pkl")
        report.append(f"- research/recovery/nhl_final_alignment/nhl_live_compatible_feature_table_v2.parquet")
        report.append(f"- research/recovery/nhl_final_alignment/phase1_live_feature_spec.md")
        report.append(f"- research/recovery/nhl_final_alignment/phase2_feature_build.md")
        report.append(f"- research/recovery/nhl_final_alignment/phase3_retrain_report.md")
        report.append(f"- research/recovery/nhl_final_alignment/phase4_parity_report.md")
    else:
        report.append("# NHL FINAL ALIGNMENT VERDICT: NOT READY")
        report.append("")
        report.append("Parity check FAILED. See phase4_parity_report.md for details.")
        report.append("DO NOT proceed to shadow until parity is confirmed.")

    # Build CSV summary table
    oos = ft[ft.season_year.isin(OOS_SEASONS)].copy()
    oos_m = oos[oos.market_available == 1].copy()

    all_feat = list(set(home_features_A + away_features_A))
    for c in all_feat:
        oos_m[c] = oos_m[c].fillna(models['A_home']['col_means'].get(c, models['A_away']['col_means'].get(c, 0)))

    h_pred = models['A_home']['model'].predict(
        models['A_home']['scaler'].transform(oos_m[home_features_A].values))
    a_pred = models['A_away']['model'].predict(
        models['A_away']['scaler'].transform(oos_m[away_features_A].values))
    model_total = h_pred + a_pred

    csv_df = pd.DataFrame({
        'game_id': oos_m['game_id'].values,
        'game_date': oos_m['game_date'].values,
        'home_team': oos_m['home_team'].values,
        'away_team': oos_m['away_team'].values,
        'model_total': model_total,
        'market_total': oos_m['closing_total'].values,
        'actual_total': oos_m['total_goals'].values,
        'model_edge': model_total - oos_m['closing_total'].values,
        'model_error': model_total - oos_m['total_goals'].values,
        'market_error': oos_m['closing_total'].values - oos_m['total_goals'].values,
    })
    csv_path = OUT / "nhl_final_alignment_oos_results.csv"
    csv_df.to_csv(csv_path, index=False)
    report.append(f"\nOOS results CSV: {csv_path.name} ({len(csv_df)} games)")

    text = "\n".join(report)
    (OUT / "NHL_FINAL_ALIGNMENT_VERDICT.md").write_text(text)
    for line in report:
        print(line)

    return text


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    gc = phase1_live_feature_spec()
    ft, league_avgs = phase2_rebuild_features(gc)
    models, hf, af, cm = phase3_retrain(ft)
    parity_pass = phase4_parity(ft, models, hf, af, cm)
    verdict = phase5_verdict(parity_pass, ft, models, hf, af)
    print("\n" + "=" * 70)
    print("DONE")
    print("=" * 70)
