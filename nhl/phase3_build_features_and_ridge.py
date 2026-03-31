#!/usr/bin/env python3
"""
NHL Totals Model — Phase 3: Feature Table + Ridge Baseline Models
=================================================================
Outputs
-------
  nhl/nhl_feature_table.parquet   — one row per game, all Phase 2 features
  nhl/ridge_home_model.pkl        — Model H (predicts home_score)
  nhl/ridge_away_model.pkl        — Model A (predicts away_score)
  nhl/phase3_model_audit.txt      — diagnostics 5A–5E
  nhl/feature_generation_log.txt  — construction log
"""

import sys
import pickle
from pathlib import Path
from datetime import timedelta

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
NHL_DIR       = Path(__file__).parent
CANONICAL_CSV = NHL_DIR / "nhl_games_canonical.csv"
FEATURE_TABLE = NHL_DIR / "nhl_feature_table.parquet"
HOME_MODEL    = NHL_DIR / "ridge_home_model.pkl"
AWAY_MODEL    = NHL_DIR / "ridge_away_model.pkl"
AUDIT_FILE    = NHL_DIR / "phase3_model_audit.txt"
LOG_FILE      = NHL_DIR / "feature_generation_log.txt"

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
ROLLING_LONG   = 20
ROLLING_SHORT  = 10
RIDGE_ALPHAS   = [0.01, 0.1, 1.0, 10.0, 100.0]
TRAIN_SEASONS  = {2021, 2022}
VAL_SEASONS    = {2023}
OOS_SEASONS    = {2024}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
_log_lines: list[str] = []

def log(msg: str = "") -> None:
    print(msg)
    _log_lines.append(msg)

# ---------------------------------------------------------------------------
# Shrinkage helper
# ---------------------------------------------------------------------------
def shrink(raw: float, n: int, league_avg: float, window: int) -> float:
    """Bayesian shrinkage toward league average."""
    w = min(n, window) / window
    return w * raw + (1.0 - w) * league_avg

# ---------------------------------------------------------------------------
# Step 1 — Load canonical
# ---------------------------------------------------------------------------
def load_canonical() -> pd.DataFrame:
    log(f"Loading {CANONICAL_CSV}")
    df = pd.read_csv(CANONICAL_CSV, parse_dates=["game_date"])
    df["game_date"] = df["game_date"].dt.date
    log(f"  {len(df):,} rows  seasons={sorted(df['season_year'].unique())}")
    return df

# ---------------------------------------------------------------------------
# Step 2 — Team game log (long format: one row per team per game)
# ---------------------------------------------------------------------------
def build_team_game_log(df: pd.DataFrame) -> pd.DataFrame:
    """
    One row per (team, game) from each team's own perspective.
    shots_for/against are derived from SOG columns:
      home perspective: shots_for=home_shots_on_goal, shots_against=away_shots_on_goal
      away perspective: shots_for=away_shots_on_goal, shots_against=home_shots_on_goal
    """
    rows = []
    for g in df.itertuples(index=False):
        # ---- home perspective ----
        rows.append({
            "game_id":             g.game_id,
            "game_date":           g.game_date,
            "season_year":         g.season_year,
            "team":                g.home_team,
            "is_home":             True,
            "goals_scored":        g.home_score,
            "goals_allowed":       g.away_score,
            "xgf":                 g.home_xgoals,
            "xga":                 g.home_xgoals_against,
            "shots_for":           g.home_shots_on_goal,
            "shots_against":       g.away_shots_on_goal,
            "hd_shots_for":        g.home_hd_shots,
            "hd_shots_against":    g.home_hd_shots_against,
            "pp_pct":              g.home_pp_pct,
            "pk_pct":              g.home_pk_pct,
            "pp_opp":              g.home_pp_opportunities,   # team's own PP opps
            "opp_pp_opp":          g.away_pp_opportunities,   # = team's penalties taken
        })
        # ---- away perspective ----
        rows.append({
            "game_id":             g.game_id,
            "game_date":           g.game_date,
            "season_year":         g.season_year,
            "team":                g.away_team,
            "is_home":             False,
            "goals_scored":        g.away_score,
            "goals_allowed":       g.home_score,
            "xgf":                 g.away_xgoals,
            "xga":                 g.away_xgoals_against,
            "shots_for":           g.away_shots_on_goal,
            "shots_against":       g.home_shots_on_goal,
            "hd_shots_for":        g.away_hd_shots,
            "hd_shots_against":    g.away_hd_shots_against,
            "pp_pct":              g.away_pp_pct,
            "pk_pct":              g.away_pk_pct,
            "pp_opp":              g.away_pp_opportunities,
            "opp_pp_opp":          g.home_pp_opportunities,
        })

    tgl = (pd.DataFrame(rows)
             .sort_values(["team", "season_year", "game_date", "game_id"])
             .reset_index(drop=True))
    log(f"  Team game log: {len(tgl):,} rows")
    return tgl

# ---------------------------------------------------------------------------
# Step 3 — Goalie game log (long format: one row per goalie start per game)
# ---------------------------------------------------------------------------
def build_goalie_game_log(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for g in df.itertuples(index=False):
        for side in ("home", "away"):
            goalie_id   = getattr(g, f"{side}_goalie_id")
            sa          = getattr(g, f"{side}_goalie_sa")
            ga          = getattr(g, f"{side}_goalie_ga")
            team        = g.home_team if side == "home" else g.away_team
            sv_pct      = (1.0 - ga / sa) if sa > 0 else np.nan
            rows.append({
                "game_id":     g.game_id,
                "game_date":   g.game_date,
                "season_year": g.season_year,
                "team":        team,
                "goalie_id":   goalie_id,
                "sv_pct":      sv_pct,
                "sa":          sa,
                "ga":          ga,
            })

    ggl = (pd.DataFrame(rows)
              .sort_values(["goalie_id", "season_year", "game_date", "game_id"])
              .reset_index(drop=True))
    log(f"  Goalie game log: {len(ggl):,} rows  unique goalies={ggl['goalie_id'].nunique()}")
    return ggl

# ---------------------------------------------------------------------------
# Step 4 — Team rolling features
# ---------------------------------------------------------------------------
def _rmean(series: pd.Series, n_window: int) -> tuple[float, int]:
    """Rolling mean of last n_window non-null values. Returns (mean, n_used)."""
    vals = series.dropna().tail(n_window)
    if len(vals) == 0:
        return np.nan, 0
    return float(vals.mean()), len(vals)

def compute_team_rolling(tgl: pd.DataFrame) -> pd.DataFrame:
    """
    For each (team, season, game), compute rolling stats from strictly prior
    games in the same season. Returns one row per (team, game_id) with
    raw mean and n_games for each feature.
    """
    records = []
    for (team, season), grp in tgl.groupby(["team", "season_year"], sort=True):
        grp = grp.sort_values(["game_date", "game_id"]).reset_index(drop=True)
        for i in range(len(grp)):
            gid   = grp.at[i, "game_id"]
            prior = grp.iloc[:i]   # strictly prior games, same season

            rec = {"team": team, "season_year": season, "game_id": gid}

            for col, key, n_win, opp_col in [
                # Offensive process
                ("xgf",             "xgf",           ROLLING_LONG,  None),
                ("shots_for",       "sf",             ROLLING_LONG,  None),
                ("hd_shots_for",    "hdsf",           ROLLING_LONG,  None),
                # Defensive process
                ("xga",             "xga",            ROLLING_LONG,  None),
                ("shots_against",   "sa",             ROLLING_LONG,  None),
                ("hd_shots_against","hdsa",           ROLLING_LONG,  None),
                # Special teams (null-safe: exclude 0-opp games)
                ("pp_pct",          "pp_pct",         ROLLING_LONG,  "pp_opp"),
                ("pk_pct",          "pk_pct",         ROLLING_LONG,  "opp_pp_opp"),
                ("pp_opp",          "pp_opp",         ROLLING_LONG,  None),
                ("opp_pp_opp",      "pen_taken",      ROLLING_LONG,  None),
                # Recent scoring form
                ("goals_scored",    "gs",             ROLLING_SHORT, None),
                ("goals_allowed",   "ga_form",        ROLLING_SHORT, None),
            ]:
                if len(prior) == 0:
                    rec[key + "_raw"], rec[key + "_n"] = np.nan, 0
                    continue
                if opp_col is not None:
                    data = prior.loc[prior[opp_col] > 0, col]
                else:
                    data = prior[col]
                raw, n = _rmean(data, n_win)
                rec[key + "_raw"] = raw
                rec[key + "_n"]   = n

            records.append(rec)

    result = pd.DataFrame(records)
    log(f"  Team rolling features: {len(result):,} rows")
    return result

# ---------------------------------------------------------------------------
# Step 5 — Goalie rolling features (per-goalie SV%, last 10 same-season starts)
# ---------------------------------------------------------------------------
def compute_goalie_rolling(ggl: pd.DataFrame) -> pd.DataFrame:
    records = []
    for (goalie_id, season), grp in ggl.groupby(["goalie_id", "season_year"], sort=True):
        grp = grp.sort_values(["game_date", "game_id"]).reset_index(drop=True)
        for i in range(len(grp)):
            prior  = grp.iloc[:i]
            raw, n = _rmean(prior["sv_pct"], ROLLING_SHORT)
            records.append({
                "goalie_id":   goalie_id,
                "season_year": season,
                "game_id":     grp.at[i, "game_id"],
                "sv_raw":      raw,
                "sv_n":        n,
            })

    result = pd.DataFrame(records)
    log(f"  Goalie rolling: {len(result):,} rows")
    return result

# ---------------------------------------------------------------------------
# Step 6 — Team goalie pool SV% (for vs_team_baseline)
# ---------------------------------------------------------------------------
def compute_team_goalie_pool(ggl: pd.DataFrame) -> pd.DataFrame:
    """
    For each (team, season, game), rolling mean SV% of all goalies who started
    for this team in the last ROLLING_SHORT starts before this game.
    """
    records = []
    for (team, season), grp in ggl.groupby(["team", "season_year"], sort=True):
        grp = grp.sort_values(["game_date", "game_id"]).reset_index(drop=True)
        for i in range(len(grp)):
            prior      = grp.iloc[:i]
            raw, n     = _rmean(prior["sv_pct"], ROLLING_SHORT)
            records.append({
                "team":         team,
                "season_year":  season,
                "game_id":      grp.at[i, "game_id"],
                "goalie_id":    grp.at[i, "goalie_id"],
                "pool_sv_raw":  raw,
                "pool_sv_n":    n,
            })

    result = pd.DataFrame(records)
    log(f"  Team goalie pool: {len(result):,} rows")
    return result

# ---------------------------------------------------------------------------
# Step 7 — Goalie fatigue and b2b (same-season only)
# ---------------------------------------------------------------------------
def compute_goalie_fatigue(ggl: pd.DataFrame) -> pd.DataFrame:
    records = []
    for (goalie_id, season), grp in ggl.groupby(["goalie_id", "season_year"], sort=True):
        grp = grp.sort_values(["game_date", "game_id"]).reset_index(drop=True)
        for i in range(len(grp)):
            cur_date  = grp.at[i, "game_date"]
            prior     = grp.iloc[:i]
            if len(prior) == 0:
                fatigue, b2b = 0, 0
            else:
                cutoff  = cur_date - timedelta(days=7)
                fatigue = int(((prior["game_date"] > cutoff) & (prior["game_date"] < cur_date)).sum())
                b2b     = int((prior["game_date"] == cur_date - timedelta(days=1)).any())
            records.append({
                "goalie_id":   goalie_id,
                "season_year": season,
                "game_id":     grp.at[i, "game_id"],
                "fatigue":     fatigue,
                "b2b":         b2b,
            })

    return pd.DataFrame(records)

# ---------------------------------------------------------------------------
# Step 8 — Backup flag (historical approximation)
# ---------------------------------------------------------------------------
def compute_backup_flags(ggl: pd.DataFrame) -> pd.DataFrame:
    """
    For each (team, season, game): backup_flag=1 if today's starter is not
    the team's #1 starter (by cumulative games-started rank through prior game).
    backup_flag=0 for first game of season (no prior data to rank from).
    """
    records = []
    for (team, season), grp in ggl.groupby(["team", "season_year"], sort=True):
        grp        = grp.sort_values(["game_date", "game_id"]).reset_index(drop=True)
        starts_cnt: dict[int, int] = {}
        for i in range(len(grp)):
            gid  = int(grp.at[i, "goalie_id"])
            if not starts_cnt:
                backup = 0
            else:
                top = max(starts_cnt, key=lambda k: starts_cnt[k])
                backup = 0 if gid == top else 1
            records.append({
                "team":        team,
                "season_year": season,
                "game_id":     grp.at[i, "game_id"],
                "goalie_id":   gid,
                "backup_flag": backup,
            })
            starts_cnt[gid] = starts_cnt.get(gid, 0) + 1

    return pd.DataFrame(records)

# ---------------------------------------------------------------------------
# Step 9 — Season league averages (for shrinkage priors)
# ---------------------------------------------------------------------------
def compute_league_avgs(tgl: pd.DataFrame, ggl: pd.DataFrame) -> dict:
    """
    Returns {season: {stat_key: mean}} computed from all team-games in the season.
    Used as the shrinkage prior: 'current_season_league_avg'.
    In training, we use all games in the season (conservative approximation).
    """
    avgs = {}
    for season, sg in tgl.groupby("season_year"):
        d: dict[str, float] = {}
        d["xgf"]         = sg["xgf"].mean()
        d["sf"]          = sg["shots_for"].mean()
        d["hdsf"]        = sg["hd_shots_for"].mean()
        d["xga"]         = sg["xga"].mean()
        d["sa"]          = sg["shots_against"].mean()
        d["hdsa"]        = sg["hd_shots_against"].mean()
        d["pp_pct"]      = sg.loc[sg["pp_opp"] > 0, "pp_pct"].mean()
        d["pk_pct"]      = sg.loc[sg["opp_pp_opp"] > 0, "pk_pct"].mean()
        d["pp_opp"]      = sg["pp_opp"].mean()
        d["pen_taken"]   = sg["opp_pp_opp"].mean()
        d["gs"]          = sg["goals_scored"].mean()
        d["ga_form"]     = sg["goals_allowed"].mean()
        d["sv_pct"]      = ggl.loc[ggl["season_year"] == season, "sv_pct"].dropna().mean()
        avgs[season] = d
    return avgs

# ---------------------------------------------------------------------------
# Step 10 — Assemble game-level feature table
# ---------------------------------------------------------------------------
def build_feature_table(df: pd.DataFrame) -> pd.DataFrame:
    log("\n=== Building Feature Table ===")

    tgl = build_team_game_log(df)
    ggl = build_goalie_game_log(df)

    log("  Computing team rolling features...")
    team_roll = compute_team_rolling(tgl)

    log("  Computing goalie rolling features...")
    goalie_roll = compute_goalie_rolling(ggl)

    log("  Computing team goalie pool...")
    team_pool = compute_team_goalie_pool(ggl)

    log("  Computing goalie fatigue/b2b...")
    goalie_fat = compute_goalie_fatigue(ggl)

    log("  Computing backup flags...")
    backup_df = compute_backup_flags(ggl)

    log("  Computing season league averages...")
    league_avgs = compute_league_avgs(tgl, ggl)

    # ---- Build O(1) lookup dicts ----
    # team rolling: (team, game_id) → Series
    troll_lut: dict[tuple, dict] = {}
    for rec in team_roll.to_dict("records"):
        troll_lut[(rec["team"], rec["game_id"])] = rec

    # goalie rolling: (goalie_id, game_id) → (sv_raw, sv_n)
    groll_lut: dict[tuple, tuple] = {}
    for rec in goalie_roll.to_dict("records"):
        groll_lut[(rec["goalie_id"], rec["game_id"])] = (rec["sv_raw"], rec["sv_n"])

    # team goalie pool: (team, game_id, goalie_id) → (pool_sv_raw, pool_sv_n)
    pool_lut: dict[tuple, tuple] = {}
    for rec in team_pool.to_dict("records"):
        pool_lut[(rec["team"], rec["game_id"], rec["goalie_id"])] = (
            rec["pool_sv_raw"], rec["pool_sv_n"]
        )

    # goalie fatigue: (goalie_id, game_id) → (fatigue, b2b)
    fat_lut: dict[tuple, tuple] = {}
    for rec in goalie_fat.to_dict("records"):
        fat_lut[(rec["goalie_id"], rec["game_id"])] = (rec["fatigue"], rec["b2b"])

    # backup flags: (team, game_id, goalie_id) → backup_flag
    bak_lut: dict[tuple, int] = {}
    for rec in backup_df.to_dict("records"):
        bak_lut[(rec["team"], rec["game_id"], rec["goalie_id"])] = rec["backup_flag"]

    # ---- Helper: get rolling feature with shrinkage ----
    def _g(team: str, gid, la: dict, key: str, window: int = ROLLING_LONG) -> float:
        rec = troll_lut.get((team, gid))
        if rec is None:
            return la[key]
        raw, n = rec[key + "_raw"], rec[key + "_n"]
        if np.isnan(raw) or n == 0:
            return la[key]
        return shrink(raw, n, la[key], window)

    # ---- Helper: goalie SV% with shrinkage ----
    def _gsv(goalie_id: int, gid, la: dict, window: int = ROLLING_SHORT) -> tuple[float, int]:
        raw, n = groll_lut.get((goalie_id, gid), (np.nan, 0))
        if np.isnan(raw) or n == 0:
            return la["sv_pct"], 0
        return shrink(raw, n, la["sv_pct"], window), n

    # ---- Assemble one row per game ----
    log("  Assembling game-level feature rows...")
    rows = []
    for g in df.itertuples(index=False):
        gid    = g.game_id
        season = g.season_year
        home   = g.home_team
        away   = g.away_team
        la     = league_avgs[season]

        h_gid = int(g.home_goalie_id)
        a_gid = int(g.away_goalie_id)

        # -- Goalie features --
        h_sv, h_sv_n = _gsv(h_gid, gid, la)
        a_sv, a_sv_n = _gsv(a_gid, gid, la)

        # vs_team_baseline
        h_pool_raw, h_pool_n = pool_lut.get((home, gid, h_gid), (np.nan, 0))
        a_pool_raw, a_pool_n = pool_lut.get((away, gid, a_gid), (np.nan, 0))
        h_pool_sv = shrink(h_pool_raw, h_pool_n, la["sv_pct"], ROLLING_SHORT) if h_pool_n > 0 else la["sv_pct"]
        a_pool_sv = shrink(a_pool_raw, a_pool_n, la["sv_pct"], ROLLING_SHORT) if a_pool_n > 0 else la["sv_pct"]
        h_vs_baseline = h_sv - h_pool_sv
        a_vs_baseline = a_sv - a_pool_sv

        h_fat, h_b2b_g = fat_lut.get((h_gid, gid), (0, 0))
        a_fat, a_b2b_g = fat_lut.get((a_gid, gid), (0, 0))
        h_bak = bak_lut.get((home, gid, h_gid), 0)
        a_bak = bak_lut.get((away, gid, a_gid), 0)

        # -- Team offensive/defensive rolling features --
        # Offensive process (B)
        h_xgf   = _g(home, gid, la, "xgf")
        h_sf    = _g(home, gid, la, "sf")
        h_hdsf  = _g(home, gid, la, "hdsf")
        a_xgf   = _g(away, gid, la, "xgf")
        a_sf    = _g(away, gid, la, "sf")
        a_hdsf  = _g(away, gid, la, "hdsf")

        # Defensive process (A/C)
        h_xga   = _g(home, gid, la, "xga")
        h_sa    = _g(home, gid, la, "sa")
        h_hdsa  = _g(home, gid, la, "hdsa")
        a_xga   = _g(away, gid, la, "xga")
        a_sa    = _g(away, gid, la, "sa")
        a_hdsa  = _g(away, gid, la, "hdsa")

        # Special teams (D)
        h_pp_pct  = _g(home, gid, la, "pp_pct")
        h_pk_pct  = _g(home, gid, la, "pk_pct")
        h_pp_opp  = _g(home, gid, la, "pp_opp")
        a_pp_pct  = _g(away, gid, la, "pp_pct")
        a_pk_pct  = _g(away, gid, la, "pk_pct")
        a_pp_opp  = _g(away, gid, la, "pp_opp")

        # Penalties taken (F2)
        h_pen = _g(home, gid, la, "pen_taken")
        a_pen = _g(away, gid, la, "pen_taken")

        # Scoring form (F)
        h_gs_form  = _g(home, gid, la, "gs",      ROLLING_SHORT)
        h_ga_form  = _g(home, gid, la, "ga_form", ROLLING_SHORT)
        a_gs_form  = _g(away, gid, la, "gs",      ROLLING_SHORT)
        a_ga_form  = _g(away, gid, la, "ga_form", ROLLING_SHORT)

        # Shot pressure (F2 — derived from rolling features)
        h_shot_pressure = h_sf  - a_sa
        a_shot_pressure = a_sf  - h_sa
        h_hd_pressure   = h_hdsf - a_hdsa
        a_hd_pressure   = a_hdsf - h_hdsa

        # Rest/schedule (E) — direct from canonical
        h_rest = g.home_rest_days   # may be NaN for first game of season
        a_rest = g.away_rest_days
        h_b2b  = int(g.home_is_b2b)
        a_b2b  = int(g.away_is_b2b)
        h_g7   = float(g.home_games_last_7)
        a_g7   = float(g.away_games_last_7)

        rows.append({
            # Identifiers / targets / market
            "game_id":              gid,
            "game_date":            g.game_date,
            "season_year":          season,
            "home_team":            home,
            "away_team":            away,
            "home_score":           g.home_score,
            "away_score":           g.away_score,
            "total_goals":          g.total_goals,
            "closing_total":        g.total_line,
            "market_available":     bool(g.market_available),

            # Section A/C — Team defensive process
            "home_xga_rolling_20":              h_xga,
            "home_shots_against_rolling_20":    h_sa,
            "home_hd_shots_against_rolling_20": h_hdsa,
            "away_xga_rolling_20":              a_xga,
            "away_shots_against_rolling_20":    a_sa,
            "away_hd_shots_against_rolling_20": a_hdsa,

            # Section A Layer 2 — Goalie features (home)
            "home_goalie_sv_pct_rolling_10":    h_sv,
            "home_goalie_vs_team_baseline":     h_vs_baseline,
            "home_goalie_fatigue":              h_fat,
            "home_goalie_b2b":                  h_b2b_g,
            "home_backup_flag":                 h_bak,

            # Section A Layer 2 — Goalie features (away)
            "away_goalie_sv_pct_rolling_10":    a_sv,
            "away_goalie_vs_team_baseline":     a_vs_baseline,
            "away_goalie_fatigue":              a_fat,
            "away_goalie_b2b":                  a_b2b_g,
            "away_backup_flag":                 a_bak,

            # Section B — Team offensive process
            "home_xgf_rolling_20":              h_xgf,
            "home_shots_for_rolling_20":        h_sf,
            "home_hd_shots_for_rolling_20":     h_hdsf,
            "away_xgf_rolling_20":              a_xgf,
            "away_shots_for_rolling_20":        a_sf,
            "away_hd_shots_for_rolling_20":     a_hdsf,

            # Section D — Special teams
            "home_pp_pct_rolling_20":           h_pp_pct,
            "home_pk_pct_rolling_20":           h_pk_pct,
            "home_pp_opp_per_game_rolling_20":  h_pp_opp,
            "away_pp_pct_rolling_20":           a_pp_pct,
            "away_pk_pct_rolling_20":           a_pk_pct,
            "away_pp_opp_per_game_rolling_20":  a_pp_opp,

            # Section E — Rest / schedule
            "home_days_rest":                   h_rest,
            "away_days_rest":                   a_rest,
            "home_b2b":                         h_b2b,
            "away_b2b":                         a_b2b,
            "home_games_last_7":                h_g7,
            "away_games_last_7":                a_g7,

            # Section F — Recent scoring form
            "home_goals_scored_rolling_10":     h_gs_form,
            "home_goals_allowed_rolling_10":    h_ga_form,
            "away_goals_scored_rolling_10":     a_gs_form,
            "away_goals_allowed_rolling_10":    a_ga_form,

            # Section F2 — Shot pressure, HD pressure, penalty volume
            "home_shot_pressure":               h_shot_pressure,
            "away_shot_pressure":               a_shot_pressure,
            "home_hd_pressure":                 h_hd_pressure,
            "away_hd_pressure":                 a_hd_pressure,
            "home_penalties_taken_rolling_20":  h_pen,
            "away_penalties_taken_rolling_20":  a_pen,
        })

    ft = pd.DataFrame(rows)
    log(f"  Feature table: {len(ft):,} rows, {len(ft.columns)} columns")
    return ft

# ---------------------------------------------------------------------------
# Model feature lists
# ---------------------------------------------------------------------------
# Model H predicts home_score:
#   offensive inputs = home team's offense
#   defensive inputs = away team's defense + away goalie Layer 2
HOME_FEATURES = [
    # Home offensive process
    "home_xgf_rolling_20",
    "home_shots_for_rolling_20",
    "home_hd_shots_for_rolling_20",
    # Away defensive process (Layer 1)
    "away_xga_rolling_20",
    "away_shots_against_rolling_20",
    "away_hd_shots_against_rolling_20",
    # Away goalie (Layer 2)
    "away_goalie_sv_pct_rolling_10",
    "away_goalie_vs_team_baseline",
    "away_goalie_fatigue",
    "away_goalie_b2b",
    "away_backup_flag",
    # Special teams (home PP vs away PK)
    "home_pp_pct_rolling_20",
    "home_pp_opp_per_game_rolling_20",
    "away_pk_pct_rolling_20",
    "home_penalties_taken_rolling_20",
    # Schedule
    "home_days_rest",
    "home_b2b",
    "home_games_last_7",
    "away_days_rest",
    "away_b2b",
    # Recent scoring form
    "home_goals_scored_rolling_10",
    "home_goals_allowed_rolling_10",
    # Shot pressure
    "home_shot_pressure",
    "home_hd_pressure",
]

# Model A predicts away_score:
#   offensive inputs = away team's offense
#   defensive inputs = home team's defense + home goalie Layer 2
AWAY_FEATURES = [
    # Away offensive process
    "away_xgf_rolling_20",
    "away_shots_for_rolling_20",
    "away_hd_shots_for_rolling_20",
    # Home defensive process (Layer 1)
    "home_xga_rolling_20",
    "home_shots_against_rolling_20",
    "home_hd_shots_against_rolling_20",
    # Home goalie (Layer 2)
    "home_goalie_sv_pct_rolling_10",
    "home_goalie_vs_team_baseline",
    "home_goalie_fatigue",
    "home_goalie_b2b",
    "home_backup_flag",
    # Special teams (away PP vs home PK)
    "away_pp_pct_rolling_20",
    "away_pp_opp_per_game_rolling_20",
    "home_pk_pct_rolling_20",
    "away_penalties_taken_rolling_20",
    # Schedule
    "away_days_rest",
    "away_b2b",
    "away_games_last_7",
    "home_days_rest",
    "home_b2b",
    # Recent scoring form
    "away_goals_scored_rolling_10",
    "away_goals_allowed_rolling_10",
    # Shot pressure
    "away_shot_pressure",
    "away_hd_pressure",
]

HOME_TARGET = "home_score"
AWAY_TARGET = "away_score"

# ---------------------------------------------------------------------------
# Step 11 — Train/validate/OOS split
# ---------------------------------------------------------------------------
def split_data(ft: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    train = ft[ft["season_year"].isin(TRAIN_SEASONS)].copy()
    val   = ft[ft["season_year"].isin(VAL_SEASONS)].copy()
    oos   = ft[ft["season_year"].isin(OOS_SEASONS)].copy()
    log(f"\n  Train: {len(train):,} | Validate: {len(val):,} | OOS: {len(oos):,}")
    return train, val, oos

# ---------------------------------------------------------------------------
# Step 12 — Fill NaNs using train column means
# ---------------------------------------------------------------------------
def fill_nulls(
    train: pd.DataFrame, val: pd.DataFrame, oos: pd.DataFrame, feats: list[str]
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.Series]:
    means = train[feats].mean()
    train[feats] = train[feats].fillna(means)
    val[feats]   = val[feats].fillna(means)
    oos[feats]   = oos[feats].fillna(means)
    return train, val, oos, means

# ---------------------------------------------------------------------------
# Step 13 — Train Ridge with alpha grid search on validate
# ---------------------------------------------------------------------------
def train_ridge(
    train: pd.DataFrame, val: pd.DataFrame,
    features: list[str], target: str, label: str
) -> tuple[Ridge, StandardScaler, float]:
    log(f"\n  {label}  (target={target})")

    X_tr = train[features].to_numpy()
    y_tr = train[target].to_numpy()
    X_va = val[features].to_numpy()
    y_va = val[target].to_numpy()

    scaler     = StandardScaler()
    X_tr_sc    = scaler.fit_transform(X_tr)
    X_va_sc    = scaler.transform(X_va)

    best_alpha, best_mae = None, float("inf")
    for alpha in RIDGE_ALPHAS:
        m   = Ridge(alpha=alpha, fit_intercept=True)
        m.fit(X_tr_sc, y_tr)
        mae = mean_absolute_error(y_va, m.predict(X_va_sc))
        rmse = np.sqrt(mean_squared_error(y_va, m.predict(X_va_sc)))
        log(f"    alpha={alpha:8.2f}  val_MAE={mae:.4f}  val_RMSE={rmse:.4f}")
        if mae < best_mae:
            best_mae, best_alpha = mae, alpha

    log(f"    Best alpha: {best_alpha}  (val_MAE={best_mae:.4f})")
    model = Ridge(alpha=best_alpha, fit_intercept=True)
    model.fit(X_tr_sc, y_tr)
    return model, scaler, best_alpha

# ---------------------------------------------------------------------------
# Step 14 — Diagnostics 5A–5E
# ---------------------------------------------------------------------------
def run_diagnostics(
    ft, train, val, oos,
    hm, hs, am, as_,
    h_feats, a_feats
) -> list[str]:
    lines: list[str] = []

    def dlog(msg: str = "") -> None:
        lines.append(msg)
        log(msg)

    def eval_split(model, scaler, df, feats, target, label, split):
        X = scaler.transform(df[feats].to_numpy())
        y = df[target].to_numpy()
        p = model.predict(X)
        mae  = mean_absolute_error(y, p)
        rmse = np.sqrt(mean_squared_error(y, p))
        bias = float(np.mean(p - y))
        dlog(f"    {label} {split:12s}  MAE={mae:.4f}  RMSE={rmse:.4f}  bias={bias:+.4f}")
        return p

    all_feats = sorted(set(h_feats + a_feats))
    hr = "=" * 68

    dlog(hr)
    dlog("PHASE 3 MODEL DIAGNOSTIC REPORT")
    dlog(hr)

    # ---- 5A: Leakage / split check ----
    dlog()
    dlog("[5A] Leakage Check — Season boundaries and split integrity")
    dlog("-" * 60)

    n_inf = int(np.isinf(ft[all_feats].select_dtypes("number")).sum().sum())
    n_nan = int(ft[all_feats].isna().sum().sum())
    dlog(f"  Feature table: {len(ft):,} rows, {len(all_feats)} model features")
    dlog(f"  Inf values in features:  {n_inf}")
    dlog(f"  NaN values in features:  {n_nan}  (before null-fill step)")

    for name, split, expected in [
        ("Train",    train, TRAIN_SEASONS),
        ("Validate", val,   VAL_SEASONS),
        ("OOS",      oos,   OOS_SEASONS),
    ]:
        found = set(map(int, split["season_year"].unique()))
        ok = "PASS" if found == expected else "FAIL"
        dlog(f"  {ok}  {name}: seasons={sorted(found)}  expected={sorted(expected)}")

    # ---- 5B: Feature coverage after null-fill ----
    dlog()
    dlog("[5B] Feature Coverage (after null-fill)")
    dlog("-" * 60)
    for name, split in [("Train", train), ("Validate", val), ("OOS", oos)]:
        cov = split[all_feats].notna().mean() * 100
        mn, mx, mu = cov.min(), cov.max(), cov.mean()
        tag = "PASS" if mn >= 99.9 else "WARN"
        dlog(f"  {tag}  {name}: min={mn:.1f}%  max={mx:.1f}%  mean={mu:.1f}%")
        if mn < 99.9:
            low = cov[cov < 99.9].index.tolist()
            dlog(f"        Low-coverage features: {low}")

    # ---- 5C: Train / validate performance ----
    dlog()
    dlog("[5C] Train and Validate Performance")
    dlog("-" * 60)
    for name, split in [("Train", train), ("Validate", val)]:
        hp = eval_split(hm, hs, split, h_feats, HOME_TARGET, "Model H", name)
        ap = eval_split(am, as_, split, a_feats, AWAY_TARGET, "Model A", name)
        tot_mae = mean_absolute_error(
            split[HOME_TARGET].values + split[AWAY_TARGET].values, hp + ap
        )
        dlog(f"    Total  {name:12s}  MAE={tot_mae:.4f}")

    # ---- 5D: OOS performance ----
    dlog()
    dlog("[5D] OOS (2024-25) Performance")
    dlog("-" * 60)
    hp_oos = eval_split(hm, hs, oos, h_feats, HOME_TARGET, "Model H", "OOS")
    ap_oos = eval_split(am, as_, oos, a_feats, AWAY_TARGET, "Model A", "OOS")
    tot_true = oos[HOME_TARGET].values + oos[AWAY_TARGET].values
    tot_pred = hp_oos + ap_oos
    tot_mae  = mean_absolute_error(tot_true, tot_pred)
    tot_rmse = np.sqrt(mean_squared_error(tot_true, tot_pred))
    dlog(f"    Total  OOS           MAE={tot_mae:.4f}  RMSE={tot_rmse:.4f}")

    # Quintile calibration
    dlog()
    dlog("  Projected total quintile calibration (OOS):")
    cal = pd.DataFrame({"proj": tot_pred, "act": tot_true})
    cal["q"] = pd.qcut(cal["proj"], 5, labels=False, duplicates="drop")
    for q, qdf in cal.groupby("q"):
        dlog(f"    Q{q+1}: proj={qdf['proj'].mean():.2f}  actual={qdf['act'].mean():.2f}  n={len(qdf)}")

    # ---- 5E: Market comparison ----
    dlog()
    dlog("[5E] Market Line Comparison (OOS, market_available=True)")
    dlog("-" * 60)
    oos_mkt = oos[oos["market_available"] & oos["closing_total"].notna()].copy()

    if len(oos_mkt) == 0:
        dlog("  WARN  No OOS games with market line — skipping")
    else:
        hp_m = hm.predict(hs.transform(oos_mkt[h_feats].to_numpy()))
        ap_m = am.predict(as_.transform(oos_mkt[a_feats].to_numpy()))
        proj = hp_m + ap_m
        act  = oos_mkt[HOME_TARGET].values + oos_mkt[AWAY_TARGET].values
        mkt  = oos_mkt["closing_total"].values

        model_mae  = mean_absolute_error(act, proj)
        market_mae = mean_absolute_error(act, mkt)
        model_bias = float(np.mean(proj - act))
        mkt_bias   = float(np.mean(mkt - act))

        dlog(f"  Games with market line: {len(oos_mkt):,}")
        dlog(f"  Model  MAE={model_mae:.4f}  bias={model_bias:+.4f}")
        dlog(f"  Market MAE={market_mae:.4f}  bias={mkt_bias:+.4f}")

        pct_worse = (model_mae / market_mae - 1) * 100
        tag = "PASS" if pct_worse <= 15 else "WARN"
        dlog(f"  {tag}  Model MAE is {pct_worse:+.1f}% vs market MAE")

        raw_edge = proj - mkt
        dlog()
        dlog("  Raw edge (proj − market) distribution:")
        for pct, val in zip(
            [10, 25, 50, 75, 90],
            np.percentile(raw_edge, [10, 25, 50, 75, 90])
        ):
            dlog(f"    p{pct:02d}: {val:+.3f}")
        dlog(f"    mean={raw_edge.mean():+.3f}  std={raw_edge.std():.3f}")

    dlog()
    dlog(hr)
    dlog("END OF DIAGNOSTIC REPORT")
    dlog(hr)

    return lines

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    log("=" * 68)
    log("NHL Phase 3: Feature Table + Ridge Baseline Models")
    log("=" * 68)

    df = load_canonical()
    ft = build_feature_table(df)

    log(f"\nSaving feature table → {FEATURE_TABLE}")
    ft.to_parquet(FEATURE_TABLE, index=False)
    log(f"  Saved {len(ft):,} rows, {len(ft.columns)} columns")

    train, val, oos = split_data(ft)

    all_feats = sorted(set(HOME_FEATURES + AWAY_FEATURES))
    log(f"\nFilling nulls from train column means  ({len(all_feats)} feature cols)...")
    train, val, oos, col_means = fill_nulls(train, val, oos, all_feats)

    log("\n=== Training Ridge Models ===")
    hm, hs, h_alpha = train_ridge(train, val, HOME_FEATURES, HOME_TARGET, "Model H (home_score)")
    am, as_, a_alpha = train_ridge(train, val, AWAY_FEATURES, AWAY_TARGET, "Model A (away_score)")

    log(f"\nSaving models...")
    for path, model, scaler, feats, alpha in [
        (HOME_MODEL, hm, hs, HOME_FEATURES, h_alpha),
        (AWAY_MODEL, am, as_, AWAY_FEATURES, a_alpha),
    ]:
        with open(path, "wb") as f:
            pickle.dump({
                "model":    model,
                "scaler":   scaler,
                "features": feats,
                "alpha":    alpha,
                "col_means": col_means[feats].to_dict(),
            }, f)
        log(f"  Saved: {path}")

    log("\n=== Running Diagnostics ===")
    diag_lines = run_diagnostics(ft, train, val, oos, hm, hs, am, as_, HOME_FEATURES, AWAY_FEATURES)

    with open(AUDIT_FILE, "w") as f:
        f.write("\n".join(diag_lines))
    log(f"\nAudit saved → {AUDIT_FILE}")

    with open(LOG_FILE, "w") as f:
        f.write("\n".join(_log_lines))
    log(f"Log  saved → {LOG_FILE}")

    log("\nPhase 3 complete.")


if __name__ == "__main__":
    main()
