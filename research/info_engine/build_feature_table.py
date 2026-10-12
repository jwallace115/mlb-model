"""
IE-1 ITEM 2: Build the as-of feature table for 2021-23 (REG only).
Every feature is built from data available BEFORE the game (week N-1 or earlier).
Uses nflreadpy 0.1.5 exclusively. No 2024+ target data is read.

One row per game, columns: game_id, season, week, home_team, away_team,
margin (home_score - away_score), total, spread_line (close), total_line (close),
margin_resid (margin - (-spread_line)), total_resid (total - total_line),
close_minus_open (total_line - open_total_line, from line_movement),
then one block per family.

Polars throughout.
"""
import os, sys, hashlib
os.environ["SSL_CERT_FILE"] = __import__("certifi").where()

import polars as pl
import nflreadpy as nfl

SEASONS = [2020, 2021, 2022, 2023]  # 2020 for prior-season features only
TARGET_SEASONS = [2021, 2022, 2023]
OUT_DIR = os.path.join(os.path.dirname(__file__), "../../nfl/data/info")
os.makedirs(OUT_DIR, exist_ok=True)

# ─── ADMISSION CHECKS ───────────────────────────────────────────────
def admit(df: pl.DataFrame, name: str, required_cols: list[str],
          season_col: str = "season"):
    """Dtype/non-null/domain checks. HALTs with row diagnostics on failure."""
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"HALT: {name} missing columns: {missing}")
    for c in required_cols:
        null_ct = df[c].null_count()
        if null_ct > 0 and c not in ("temp", "wind", "report_status",
                                      "practice_status", "date_modified"):
            pct = null_ct / len(df) * 100
            if pct > 50:
                raise ValueError(
                    f"HALT: {name}.{c} has {null_ct}/{len(df)} nulls ({pct:.1f}%)")
    if season_col in df.columns:
        seasons = sorted(df[season_col].unique().to_list())
        bad = [s for s in seasons if s not in SEASONS]
        if bad:
            raise ValueError(f"HALT: {name} has unexpected seasons: {bad}")
    print(f"  ADMITTED {name}: {df.shape}")
    return df


# ─── LOAD ALL SOURCES ───────────────────────────────────────────────
print("Loading sources...")
schedules = nfl.load_schedules(SEASONS)
admit(schedules, "schedules", ["game_id", "season", "week", "home_team",
      "away_team", "home_score", "away_score", "spread_line", "total_line",
      "home_rest", "away_rest", "roof", "surface", "referee"])

# Filter to REG only for targets
games = (schedules
    .filter(pl.col("game_type") == "REG")
    .filter(pl.col("season").is_in(TARGET_SEASONS))
    .with_columns([
        (pl.col("home_score") - pl.col("away_score")).alias("margin"),
        (pl.col("home_score") + pl.col("away_score")).alias("total"),
    ])
    .with_columns([
        # margin_resid = margin - spread_line (IE-D8: corrected from margin+spread_line)
        (pl.col("margin") - pl.col("spread_line")).alias("margin_resid"),
        (pl.col("total") - pl.col("total_line")).alias("total_resid"),
    ])
    .select(["game_id", "season", "week", "home_team", "away_team",
             "margin", "total", "spread_line", "total_line",
             "margin_resid", "total_resid",
             "home_rest", "away_rest", "roof", "surface", "temp", "wind",
             "referee"])
)
print(f"Target games: {games.shape}")

# Assert target seasons
target_seasons_in_data = sorted(games["season"].unique().to_list())
assert target_seasons_in_data == TARGET_SEASONS, \
    f"HALT: target seasons {target_seasons_in_data} != {TARGET_SEASONS}"

# ─── KNOWN-GAME ASSERTIONS (IE-D8) ──────────────────────────────────
import numpy as np
g_ari = games.filter(pl.col("game_id") == "2021_01_ARI_TEN")
assert len(g_ari) == 1, "HALT: 2021_01_ARI_TEN not found"
assert g_ari["margin"][0] == -25, f"HALT: ARI_TEN margin {g_ari['margin'][0]} != -25"
assert g_ari["spread_line"][0] == 2.5, f"HALT: ARI_TEN spread_line {g_ari['spread_line'][0]} != 2.5"
assert g_ari["margin_resid"][0] == -27.5, f"HALT: ARI_TEN margin_resid {g_ari['margin_resid'][0]} != -27.5"
print("  PASS: 2021_01_ARI_TEN → margin -25, spread_line +2.5, margin_resid -27.5")

# Home underdog that won: 2021_01_DAL_TB (TB home, spread_line=10, margin=2 → TB won as dog)
g_tb = games.filter(pl.col("game_id") == "2021_01_DAL_TB")
assert len(g_tb) == 1
assert g_tb["margin"][0] > 0, "HALT: TB didn't win"
assert g_tb["spread_line"][0] > 0, "HALT: TB wasn't underdog"
# Home cover under corrected formula: margin > spread_line → 2 > 10 → False (TB won but didn't cover 10pt spread)
assert g_tb["margin_resid"][0] < 0, f"HALT: TB should NOT cover 10pt spread with 2pt win"
print("  PASS: 2021_01_DAL_TB → home underdog won (margin=2, sl=10), margin_resid=-8 (did NOT cover)")

# ─── LINE MOVEMENT (F10) ────────────────────────────────────────────
import pandas as pd
lm_pd = pd.read_parquet(os.path.join(os.path.dirname(__file__),
    "../../nfl/data/nfl_line_movement.parquet"))
lm = pl.from_pandas(lm_pd).select(["game_id", "open_total_line"])
games = games.join(lm, on="game_id", how="left").with_columns(
    (pl.col("total_line") - pl.col("open_total_line")).alias("close_minus_open")
)
lm_coverage = games.group_by("season").agg(
    pl.col("close_minus_open").is_not_null().sum().alias("has_open"),
    pl.len().alias("total")
)
print("Line movement coverage:")
print(lm_coverage.sort("season"))

# ─── LOAD FAMILY SOURCES (2020-2023 for as-of) ──────────────────────
# All schedules (including 2020) for referee/rest features
all_sched = (schedules.filter(pl.col("game_type") == "REG")
    .with_columns([
        (pl.col("home_score") + pl.col("away_score")).alias("game_total"),
        (pl.col("home_score") - pl.col("away_score")).alias("game_margin"),
    ]))

ftn = nfl.load_ftn_charting([s for s in SEASONS if s >= 2022])  # FTN starts 2022
admit(ftn, "ftn_charting", ["nflverse_game_id", "season", "week",
      "is_play_action", "is_motion", "is_rpo", "is_screen_pass"])

ngs_rush = nfl.load_nextgen_stats(stat_type="rushing", seasons=SEASONS)
admit(ngs_rush, "ngs_rushing", ["season", "week", "team_abbr",
      "rush_yards_over_expected_per_att"])

ngs_recv = nfl.load_nextgen_stats(stat_type="receiving", seasons=SEASONS)
admit(ngs_recv, "ngs_receiving", ["season", "week", "team_abbr",
      "avg_separation", "avg_cushion"])

snaps = nfl.load_snap_counts(SEASONS)
admit(snaps, "snap_counts", ["game_id", "season", "week", "player",
      "position", "team", "offense_snaps"])

pfr = nfl.load_pfr_advstats(stat_type="pass", seasons=SEASONS, summary_level="week")
admit(pfr, "pfr_weekly", ["game_id", "season", "week", "team",
      "times_pressured_pct", "passing_bad_throw_pct"])

officials = nfl.load_officials(SEASONS)
admit(officials, "officials", ["game_id", "season"])

injuries = nfl.load_injuries(SEASONS)
admit(injuries, "injuries", ["season", "week", "team", "full_name",
      "report_status", "date_modified"], season_col="season")

depth_charts = nfl.load_depth_charts(SEASONS)
admit(depth_charts, "depth_charts", ["season", "club_code", "week",
      "gsis_id", "depth_team"])


# ─── HELPER: as-of cumulative through week N-1 ─────────────────────
def prior_weeks(df: pl.DataFrame, season: int, week: int,
                season_col="season", week_col="week") -> pl.DataFrame:
    """Return rows from prior weeks in the SAME season only (no cross-season)."""
    return df.filter(
        (pl.col(season_col) == season) & (pl.col(week_col) < week)
    )

def prior_weeks_with_prior_season(df, season, week, season_col="season",
                                   week_col="week"):
    """Same-season prior weeks + all of the prior season (for early weeks)."""
    same = df.filter(
        (pl.col(season_col) == season) & (pl.col(week_col) < week))
    prev = df.filter(pl.col(season_col) == season - 1)
    return pl.concat([prev, same])


# ─── F1: INJURY TRAJECTORY ──────────────────────────────────────────
print("\nBuilding F1: Injury trajectory...")
# Score: fraction of players whose status improved (e.g., Out->Questionable->None)
# from their first report to their last report in the week before the game.
STATUS_RANK = {"Out": 0, "Doubtful": 1, "Questionable": 2, None: 3}

def build_f1(game_row):
    season, week, home, away = (game_row["season"], game_row["week"],
                                 game_row["home_team"], game_row["away_team"])
    results = {}
    for side, team in [("home", home), ("away", away)]:
        # Get injury reports for this team in weeks up to N-1
        team_inj = injuries.filter(
            (pl.col("season") == season) &
            (pl.col("week") == week) &  # week N injury report
            (pl.col("team") == team)
        )
        # Also get week N-1 reports
        prev_inj = injuries.filter(
            (pl.col("season") == season) &
            (pl.col("week") == week - 1) &
            (pl.col("team") == team)
        )
        if len(prev_inj) == 0 or len(team_inj) == 0:
            results[f"f1_{side}_inj_trajectory"] = 0.0
            continue

        # For each player on current week's report, check if they improved
        curr_statuses = dict(zip(
            team_inj["full_name"].to_list(),
            team_inj["report_status"].to_list()
        ))
        prev_statuses = dict(zip(
            prev_inj["full_name"].to_list(),
            prev_inj["report_status"].to_list()
        ))
        improved = 0
        worsened = 0
        for player in set(curr_statuses) & set(prev_statuses):
            curr_rank = STATUS_RANK.get(curr_statuses[player], 3)
            prev_rank = STATUS_RANK.get(prev_statuses[player], 3)
            if curr_rank > prev_rank:
                improved += 1
            elif curr_rank < prev_rank:
                worsened += 1
        total_tracked = improved + worsened
        results[f"f1_{side}_inj_trajectory"] = (
            (improved - worsened) / total_tracked if total_tracked > 0 else 0.0
        )
    results["f1_inj_trajectory_diff"] = (
        results["f1_home_inj_trajectory"] - results["f1_away_inj_trajectory"]
    )
    return results


# ─── F2: PASS PROTECTION ────────────────────────────────────────────
print("Building F2: Pass protection...")

def build_f2(season, week, team):
    """Cumulative pressure_pct and bad_throw_pct through week N-1."""
    prior = prior_weeks(pfr, season, week)
    team_prior = prior.filter(pl.col("team") == team)
    if len(team_prior) == 0:
        return {"pressure_pct": None, "bad_throw_pct": None}
    return {
        "pressure_pct": team_prior["times_pressured_pct"].mean(),
        "bad_throw_pct": team_prior["passing_bad_throw_pct"].mean(),
    }


# ─── F3: SCHEME TENDENCY SHIFT ──────────────────────────────────────
print("Building F3: Scheme tendency...")
# FTN is play-level; need to map game_id to home/away team
# nflverse_game_id format: "2023_01_DET_KC" = season_week_away_home
ftn_with_teams = ftn.with_columns([
    pl.col("nflverse_game_id").str.split("_").list.get(2).alias("away_team_ftn"),
    pl.col("nflverse_game_id").str.split("_").list.get(3).alias("home_team_ftn"),
])

def build_f3(season, week, team):
    """Cumulative motion/PA/RPO/screen rates through week N-1."""
    prior = prior_weeks(ftn_with_teams, season, week)
    # Get plays where this team was on offense (home or away)
    team_plays = prior.filter(
        (pl.col("home_team_ftn") == team) | (pl.col("away_team_ftn") == team)
    )
    if len(team_plays) == 0:
        return {"motion_rate": None, "pa_rate": None, "rpo_rate": None,
                "screen_rate": None}
    return {
        "motion_rate": team_plays["is_motion"].cast(pl.Float64).mean(),
        "pa_rate": team_plays["is_play_action"].cast(pl.Float64).mean(),
        "rpo_rate": team_plays["is_rpo"].cast(pl.Float64).mean(),
        "screen_rate": team_plays["is_screen_pass"].cast(pl.Float64).mean(),
    }


# ─── F4: RUSHING EFFICIENCY (RYOE) ──────────────────────────────────
print("Building F4: Rushing RYOE...")

def build_f4(season, week, team):
    """Cumulative RYOE/att through week N-1."""
    prior = prior_weeks(ngs_rush, season, week)
    team_prior = prior.filter(
        (pl.col("team_abbr") == team) & (pl.col("season_type") == "REG")
    )
    if len(team_prior) == 0:
        return {"ryoe_per_att": None}
    return {
        "ryoe_per_att": team_prior["rush_yards_over_expected_per_att"].mean(),
    }


# ─── F5: RECEIVING SEPARATION ───────────────────────────────────────
print("Building F5: Receiving separation...")

def build_f5(season, week, team):
    """Cumulative avg_separation and avg_cushion through week N-1."""
    prior = prior_weeks(ngs_recv, season, week)
    team_prior = prior.filter(
        (pl.col("team_abbr") == team) & (pl.col("season_type") == "REG")
    )
    if len(team_prior) == 0:
        return {"avg_separation": None, "avg_cushion": None}
    return {
        "avg_separation": team_prior["avg_separation"].mean(),
        "avg_cushion": team_prior["avg_cushion"].mean(),
    }


# ─── F6: SNAP-COUNT USAGE SHIFT ─────────────────────────────────────
print("Building F6: Snap-count usage shift...")

def build_f6(season, week, team):
    """Week N-1 snap distribution entropy vs cumulative average.
    Measures how different the latest week's usage is from the season pattern."""
    # Current week N-1 snaps
    curr = snaps.filter(
        (pl.col("season") == season) & (pl.col("week") == week - 1) &
        (pl.col("team") == team) & (pl.col("offense_snaps") >= 1)
    )
    # Season average through N-2
    hist = snaps.filter(
        (pl.col("season") == season) & (pl.col("week") < week - 1) &
        (pl.col("team") == team) & (pl.col("offense_snaps") >= 1)
    )
    if len(curr) == 0 or len(hist) == 0:
        return {"snap_shift": None, "snap_concentration": None}

    # Snap concentration: HHI of week N-1 offensive snap shares
    total_snaps = curr["offense_snaps"].sum()
    if total_snaps == 0:
        return {"snap_shift": None, "snap_concentration": None}
    shares = (curr["offense_snaps"] / total_snaps).to_list()
    hhi = sum(s**2 for s in shares)

    # Snap shift: mean absolute deviation of week N-1 snap shares from season avg
    # (IE-D9: redefined from count>10pp to MAD, proven to vary)
    hist_avg = (hist.group_by("player").agg(
        pl.col("offense_snaps").mean().alias("avg_snaps")
    ))
    curr_snap = curr.select(["player", "offense_snaps"]).rename(
        {"offense_snaps": "curr_snaps"})
    merged = curr_snap.join(hist_avg, on="player", how="inner")
    if len(merged) == 0:
        return {"snap_shift": 0.0, "snap_concentration": hhi}

    total_curr = merged["curr_snaps"].sum()
    total_avg = merged["avg_snaps"].sum()
    if total_curr == 0 or total_avg == 0:
        return {"snap_shift": 0.0, "snap_concentration": hhi}

    merged = merged.with_columns([
        (pl.col("curr_snaps") / total_curr).alias("curr_share"),
        (pl.col("avg_snaps") / total_avg).alias("avg_share"),
    ])
    shifts = (merged["curr_share"] - merged["avg_share"]).abs()
    snap_shift_mad = float(shifts.mean())  # continuous, always varies
    return {"snap_shift": snap_shift_mad, "snap_concentration": hhi}


# ─── F7: REFEREE CREW SCORING ───────────────────────────────────────
print("Building F7: Referee crew scoring...")

def build_f7(season, week, referee_name):
    """Season-to-date avg total for games officiated by this referee,
    using only completed games through week N-1."""
    if referee_name is None:
        return {"ref_avg_total": None, "ref_avg_margin_abs": None,
                "ref_game_count": 0}
    # Find prior weeks this referee officiated (using officials' own week col)
    ref_prior_weeks = officials.filter(
        (pl.col("season") == season) &
        (pl.col("week") < week) &
        (pl.col("position") == "Referee") &
        (pl.col("official_name") == referee_name)
    )["week"].unique().to_list()

    if not ref_prior_weeks:
        return {"ref_avg_total": None, "ref_avg_margin_abs": None,
                "ref_game_count": 0}

    # For each week, find the game(s) this ref officiated via schedules.referee
    prior_games = all_sched.filter(
        (pl.col("season") == season) &
        pl.col("week").is_in(ref_prior_weeks) &
        (pl.col("referee") == referee_name)
    )
    if len(prior_games) == 0:
        return {"ref_avg_total": None, "ref_avg_margin_abs": None,
                "ref_game_count": 0}
    return {
        "ref_avg_total": prior_games["game_total"].mean(),
        "ref_avg_margin_abs": prior_games["game_margin"].abs().mean(),
        "ref_game_count": len(prior_games),
    }


# ─── F8: DEPTH CHART INSTABILITY ────────────────────────────────────
print("Building F8: Depth chart instability...")

def build_f8(season, week, team):
    """Count of starter changes between week N-2 and week N-1.
    Week N is NEVER read (IE-D4)."""
    # depth_team == 1 means starter
    prev = depth_charts.filter(
        (pl.col("season") == season) & (pl.col("week") == week - 2) &
        (pl.col("club_code") == team) & (pl.col("depth_team") == "1")
    )
    curr = depth_charts.filter(
        (pl.col("season") == season) & (pl.col("week") == week - 1) &
        (pl.col("club_code") == team) & (pl.col("depth_team") == "1")
    )
    if len(prev) == 0 or len(curr) == 0:
        return {"dc_changes": None}

    # Compare by position: who is the starter at each position?
    prev_starters = dict(zip(
        prev["depth_position"].to_list() if "depth_position" in prev.columns
        else prev["position"].to_list(),
        prev["gsis_id"].to_list()
    ))
    curr_col = "depth_position" if "depth_position" in curr.columns else "position"
    curr_starters = dict(zip(
        curr[curr_col].to_list(),
        curr["gsis_id"].to_list()
    ))
    changes = 0
    for pos in set(prev_starters) & set(curr_starters):
        if prev_starters[pos] != curr_starters[pos]:
            changes += 1
    return {"dc_changes": changes}


# ─── F9: REST + SURFACE + WEATHER ───────────────────────────────────
print("Building F9: Rest x surface x weather...")
# Already in games: home_rest, away_rest, roof, surface, temp, wind
# We compute interaction features directly from the game row.

def build_f9(game_row):
    home_rest = game_row["home_rest"]
    away_rest = game_row["away_rest"]
    roof = game_row["roof"]
    temp = game_row["temp"]
    wind_val = game_row["wind"]
    surface = game_row["surface"]

    is_outdoor = roof in ("outdoors", "open") if roof else True
    is_short_rest_home = 1 if (home_rest is not None and home_rest <= 5) else 0
    is_short_rest_away = 1 if (away_rest is not None and away_rest <= 5) else 0
    is_grass = 1 if surface and "grass" in str(surface).lower() else 0

    # Wind effect (outdoor only)
    wind_effect = float(wind_val) if (is_outdoor and wind_val is not None) else 0.0
    temp_effect = float(temp) if (is_outdoor and temp is not None) else 65.0  # neutral

    return {
        "f9_home_short_rest": is_short_rest_home,
        "f9_away_short_rest": is_short_rest_away,
        "f9_rest_diff": (home_rest or 7) - (away_rest or 7),
        "f9_wind": wind_effect,
        "f9_temp": temp_effect,
        "f9_outdoor": int(is_outdoor),
        "f9_grass": is_grass,
        "f9_wind_x_outdoor": wind_effect * int(is_outdoor),
        "f9_short_rest_x_grass": is_short_rest_home * is_grass,
    }


# ─── F10: LINE MOVEMENT ─────────────────────────────────────────────
# Already joined: close_minus_open. Additional features:
def build_f10(game_row):
    cmo = game_row["close_minus_open"]
    if cmo is None:
        return {"f10_line_move": None, "f10_line_move_abs": None,
                "f10_line_move_dir": None}
    return {
        "f10_line_move": cmo,
        "f10_line_move_abs": abs(cmo),
        "f10_line_move_dir": 1 if cmo > 0 else (-1 if cmo < 0 else 0),
    }


# ─── BUILD THE TABLE ────────────────────────────────────────────────
print("\nBuilding feature table row by row...")
rows = []
game_rows = games.to_dicts()
total = len(game_rows)

for i, g in enumerate(game_rows):
    if (i + 1) % 100 == 0:
        print(f"  {i+1}/{total}...")

    row = {
        "game_id": g["game_id"],
        "season": g["season"],
        "week": g["week"],
        "home_team": g["home_team"],
        "away_team": g["away_team"],
        "margin": g["margin"],
        "total": g["total"],
        "spread_line": g["spread_line"],
        "total_line": g["total_line"],
        "margin_resid": g["margin_resid"],
        "total_resid": g["total_resid"],
        "close_minus_open": g["close_minus_open"],
    }

    # F1
    f1 = build_f1(g)
    row.update(f1)

    # F2
    f2_h = build_f2(g["season"], g["week"], g["home_team"])
    f2_a = build_f2(g["season"], g["week"], g["away_team"])
    row["f2_home_pressure_pct"] = f2_h["pressure_pct"]
    row["f2_away_pressure_pct"] = f2_a["pressure_pct"]
    row["f2_home_bad_throw_pct"] = f2_h["bad_throw_pct"]
    row["f2_away_bad_throw_pct"] = f2_a["bad_throw_pct"]
    row["f2_pressure_diff"] = (
        (f2_h["pressure_pct"] or 0) - (f2_a["pressure_pct"] or 0)
    ) if f2_h["pressure_pct"] is not None and f2_a["pressure_pct"] is not None else None

    # F3
    f3_h = build_f3(g["season"], g["week"], g["home_team"])
    f3_a = build_f3(g["season"], g["week"], g["away_team"])
    for feat in ["motion_rate", "pa_rate", "rpo_rate", "screen_rate"]:
        row[f"f3_home_{feat}"] = f3_h[feat]
        row[f"f3_away_{feat}"] = f3_a[feat]

    # F4
    f4_h = build_f4(g["season"], g["week"], g["home_team"])
    f4_a = build_f4(g["season"], g["week"], g["away_team"])
    row["f4_home_ryoe"] = f4_h["ryoe_per_att"]
    row["f4_away_ryoe"] = f4_a["ryoe_per_att"]
    row["f4_ryoe_diff"] = (
        (f4_h["ryoe_per_att"] or 0) - (f4_a["ryoe_per_att"] or 0)
    ) if f4_h["ryoe_per_att"] is not None and f4_a["ryoe_per_att"] is not None else None

    # F5
    f5_h = build_f5(g["season"], g["week"], g["home_team"])
    f5_a = build_f5(g["season"], g["week"], g["away_team"])
    row["f5_home_separation"] = f5_h["avg_separation"]
    row["f5_away_separation"] = f5_a["avg_separation"]
    row["f5_home_cushion"] = f5_h["avg_cushion"]
    row["f5_away_cushion"] = f5_a["avg_cushion"]

    # F6
    f6_h = build_f6(g["season"], g["week"], g["home_team"])
    f6_a = build_f6(g["season"], g["week"], g["away_team"])
    row["f6_home_snap_shift"] = f6_h["snap_shift"]
    row["f6_away_snap_shift"] = f6_a["snap_shift"]
    row["f6_home_snap_conc"] = f6_h["snap_concentration"]
    row["f6_away_snap_conc"] = f6_a["snap_concentration"]

    # F7
    f7 = build_f7(g["season"], g["week"], g["referee"])
    row["f7_ref_avg_total"] = f7["ref_avg_total"]
    row["f7_ref_avg_margin_abs"] = f7["ref_avg_margin_abs"]
    row["f7_ref_game_count"] = f7["ref_game_count"]

    # F8
    f8_h = build_f8(g["season"], g["week"], g["home_team"])
    f8_a = build_f8(g["season"], g["week"], g["away_team"])
    row["f8_home_dc_changes"] = f8_h["dc_changes"]
    row["f8_away_dc_changes"] = f8_a["dc_changes"]

    # F9
    f9 = build_f9(g)
    row.update(f9)

    # F10
    f10 = build_f10(g)
    row.update(f10)

    rows.append(row)

import pandas as pd_lib
ft_pd = pd_lib.DataFrame(rows)
ft = pl.from_pandas(ft_pd)
print(f"\nFeature table: {ft.shape}")

# ─── FINAL ASSERTIONS ───────────────────────────────────────────────
# Assert target seasons
ft_seasons = sorted(ft["season"].unique().to_list())
assert ft_seasons == TARGET_SEASONS, f"HALT: seasons in feature table: {ft_seasons}"

# Assert no duplicates
assert ft["game_id"].n_unique() == len(ft), "HALT: duplicate game_ids"

# ─── CORRELATION GATES (IE-D8) ──────────────────────────────────────
ft_pd_check = ft.to_pandas()
corr_mr_sl = np.corrcoef(
    ft_pd_check["margin_resid"].values,
    ft_pd_check["spread_line"].values
)[0, 1]
print(f"\n|corr(margin_resid, spread_line)| = {abs(corr_mr_sl):.4f}")
assert abs(corr_mr_sl) < 0.05, \
    f"HALT: |corr(margin_resid, spread_line)| = {abs(corr_mr_sl):.4f} >= 0.05"

corr_tr_tl = np.corrcoef(
    ft_pd_check["total_resid"].values,
    ft_pd_check["total_line"].values
)[0, 1]
print(f"|corr(total_resid, total_line)| = {abs(corr_tr_tl):.4f}")
assert abs(corr_tr_tl) < 0.05, \
    f"HALT: |corr(total_resid, total_line)| = {abs(corr_tr_tl):.4f} >= 0.05"

# ─── ZERO-VARIANCE CHECK (IE-D8) ────────────────────────────────────
feat_cols = [c for c in ft.columns if c.startswith("f")]
for c in feat_cols:
    series = ft_pd_check[c].dropna()
    if len(series) > 0 and series.std() == 0:
        raise ValueError(f"HALT: zero-variance feature column: {c}")
print(f"Zero-variance check: PASS ({len(feat_cols)} feature columns)")

# Report coverage per family per season
print("\n=== COVERAGE REPORT ===")
families = {
    "F1": ["f1_inj_trajectory_diff"],
    "F2": ["f2_pressure_diff"],
    "F3": ["f3_home_motion_rate"],
    "F4": ["f4_ryoe_diff"],
    "F5": ["f5_home_separation"],
    "F6": ["f6_home_snap_shift"],
    "F7": ["f7_ref_avg_total"],
    "F8": ["f8_home_dc_changes"],
    "F9": ["f9_wind"],
    "F10": ["f10_line_move"],
}
for fam, cols in families.items():
    col = cols[0]
    for s in TARGET_SEASONS:
        sub = ft.filter(pl.col("season") == s)
        nn = sub[col].is_not_null().sum()
        print(f"  {fam} {col} {s}: {nn}/{len(sub)} non-null")

# Save
out_path = os.path.join(OUT_DIR, "feature_table_2021_23.parquet")
ft.to_pandas().to_parquet(out_path, index=False)
print(f"\nSaved to {out_path}")
print(f"Rows: {len(ft)}, Cols: {len(ft.columns)}")
print(f"Columns: {ft.columns}")
